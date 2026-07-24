"""CubeMemoryProvider — HermesAgent MemoryProvider backed by HermesCube.

Implements the MemoryProvider ABC interface for integration with
HermesAgent's memory system. Stores conversation turns in a .cube
archive with HAR-powered semantic retrieval.

Registered as a plugin via the ``register(ctx)`` pattern. Activation is
controlled by ``memory.provider: hermescube`` in config.yaml.

Usage:
    from hermescube.provider import CubeMemoryProvider

    provider = CubeMemoryProvider()
    provider.initialize(session_id="abc123", hermes_home="/home/user/.hermes")
    results = provider.prefetch("what did we discuss about memory?")
    provider.sync_turn(user_msg, assistant_msg, session_id="abc123")
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermescube.cube import OUTCOMES, ENTRY_TYPES, CubeFile, CubeEntry
from hermescube.har import HARQueryEngine
from hermescube import hrr
from hermescube.threats import scan_text, sanitize_for_storage

logger = logging.getLogger(__name__)


# ── Configuration ────────────────────────────────────────────────────

DEFAULT_DIM = 256
DEFAULT_L2_BUCKETS = 64
DEFAULT_CHAR_LIMIT = 2200
DEFAULT_PREFETCH_TOP_K = 10
DEFAULT_EVOLVE_INTERVAL = 50
DEFAULT_SYNC_WORKERS = 1
DEFAULT_MEMORY_NUDGE_INTERVAL = 10
CONSOLIDATION_SIMILARITY_THRESHOLD = 0.85

# Asymmetric trust deltas: penalty outweights reward (holographic pattern)
_TRUST_HELPFUL_DELTA = 0.05
_TRUST_UNHELPFUL_DELTA = -0.10

# Circuit breaker for evolve operations
_EVOLVE_BREAKER_THRESHOLD = 3
_EVOLVE_BREAKER_COOLDOWN_SECS = 300


# ── Config loading (framework housing) ─────────────────────────────

from hermescube.framework.config import (  # noqa: E402
    coerce_bool as _coerce_bool,
    load_plugin_config as _load_plugin_config,
    query_rewrite_enabled as _query_rewrite_enabled,
)


def _try_query_rewrite(message: str, *, enabled: bool = False) -> str:
    """Optional HermesAgent-style query rewrite (slow — LLM).

    Default path returns ``message`` unchanged. When enabled, uses
    ``rewrite_memory_query()`` if available; failures fall back to raw.
    """
    if not enabled:
        return message
    try:
        from plugins.memory.query_rewrite import rewrite_memory_query
        rewritten = rewrite_memory_query(message)
        if rewritten and len(rewritten.strip()) >= 3:
            return rewritten.strip()
    except Exception:
        pass
    return message


# Auto-extract regex patterns (Hermes provider style — Cube-owned patterns)
_AUTO_EXTRACT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("user_pref", re.compile(
        r"\bI\s+(?:prefer|like|love|use|want|need|always|never|usually)\s+(.+)",
        re.IGNORECASE,
    )),
    ("user_pref", re.compile(
        r"\bmy\s+(?:favorite|preferred|default)\s+\w+\s+is\s+(.+)",
        re.IGNORECASE,
    )),
    ("project", re.compile(
        r"\bwe\s+(?:decided|agreed|chose)\s+(?:to\s+)?(.+)",
        re.IGNORECASE,
    )),
    ("project", re.compile(
        r"\bthe\s+project\s+(?:uses|needs|requires)\s+(.+)",
        re.IGNORECASE,
    )),
    ("tool", re.compile(
        r"\bthe\s+tool\s+(?:should|must|can't|cannot|doesn't|does\s+not)\s+(.+)",
        re.IGNORECASE,
    )),
]


# ── Frozen snapshot ──────────────────────────────────────────────────

@dataclass
class _FrozenSnapshot:
    """Cached state at session start — never mutated mid-session."""
    beta: hrr.Array
    l2_centroids: list[Any]
    entry_count: int


# ── Background sync ──────────────────────────────────────────────────

class _SyncQueue:
    """Background sync worker — single-threaded, never blocks the turn."""

    def __init__(self) -> None:
        self._executor: ThreadPoolExecutor | None = None
        self._lock = threading.Lock()

    def _get_executor(self) -> ThreadPoolExecutor:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=DEFAULT_SYNC_WORKERS,
                    thread_name_prefix="hermescube_sync",
                )
            return self._executor

    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        executor = self._get_executor()
        try:
            executor.submit(fn, *args, **kwargs)
        except RuntimeError as e:
            logger.warning("sync submit failed (executor shut down?): %s", e)

    def flush(self, timeout: float = 5.0) -> None:
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=False)
                self._executor = None


# ── Provider ─────────────────────────────────────────────────────────

class CubeMemoryProvider:
    """HermesAgent MemoryProvider backed by a HermesCube archive.

    Stores conversation turns as cube entries with HAR-powered retrieval.
    Implements the MemoryProvider ABC interface for HermesAgent integration.

    Tools registered:
        hermescube_search   — semantic search over past conversations
        hermescube_manage   — add/remove memories programmatically
        hermescube_feedback — rate a memory entry (trains trust)

    All tool names are prefixed with ``hermescube_`` to avoid shadowing
    the built-in ``memory`` tool and other reserved core tool names.
    """

    def __init__(
        self,
        dim: int = DEFAULT_DIM,
        l2_buckets: int = DEFAULT_L2_BUCKETS,
        char_limit: int = DEFAULT_CHAR_LIMIT,
        evolve_interval: int = DEFAULT_EVOLVE_INTERVAL,
        memory_nudge_interval: int = DEFAULT_MEMORY_NUDGE_INTERVAL,
        auto_extract: bool = False,
    ) -> None:
        self._dim = dim
        self._l2_buckets = l2_buckets
        self._char_limit = char_limit
        self._evolve_interval = evolve_interval
        self._memory_nudge_interval = memory_nudge_interval
        self._auto_extract = auto_extract
        self._query_rewrite = False
        # Cadence knobs (Nous-style cost control — local)
        self._peer_card_cadence_s = 3600.0  # rebuild peer card at most hourly
        self._session_digest_enabled = True
        self._observe_on_session_end = True
        self._replay_on_session_end = True
        self._conflict_detect = True

        self._cube: CubeFile | None = None
        self._engine: HARQueryEngine | None = None
        self._cube_path: str = ""
        self._session_id: str = ""
        self._hermes_home: str = ""

        # Provider-scoped identity from initialize() kwargs
        self._agent_context: str = "primary"
        self._agent_identity: str = ""
        self._agent_workspace: str = ""
        self._platform: str = "cli"
        self._skip_memory: bool = False

        # Frozen snapshot (set at initialize, never mutated mid-session)
        self._snapshot: _FrozenSnapshot | None = None

        # Background sync
        self._sync_queue = _SyncQueue()

        # Prefetch cache (query hash → results)
        self._prefetch_cache: dict[str, list[tuple[CubeEntry, float]]] = {}
        self._prefetch_cache_max = 64

        # Colony stigmergy (ants/bees) — original Cube layer
        self._colony = None
        self._void = None
        self._yield = None
        self._engram = None
        self._last_prefetch_query = ""
        self._last_prefetch_ids: list[str] = []
        self._paths = None

        # Turn tracking
        self._turn_count: int = 0
        self._turns_since_memory: int = 0
        self._entries_since_evolve: int = 0

        # Circuit breaker for evolve
        self._evolve_failures: int = 0
        self._evolve_breaker_until: float = 0.0
        self._evolve_lambda_trained: bool = False

    # ── MemoryProvider ABC: properties ────────────────────────────

    @property
    def name(self) -> str:
        return "hermescube"

    # ── MemoryProvider ABC: core methods ──────────────────────────

    def is_available(self) -> bool:
        """Check if cube file is accessible.

        HermesCube is always available — no API keys or network deps.
        """
        if self._cube_path:
            return os.path.isfile(self._cube_path)
        return True

    def initialize(self, session_id: str = "", **kwargs: Any) -> None:
        """Open or create cube file, load frozen snapshot.

        Config is loaded from config.yaml under ``plugins.hermescube``
        (or ``memory.hermescube``), then overridden by constructor args.

        kwargs recognized:
            hermes_home (str):       Hermes home directory
            platform (str):          "cli", "telegram", "discord", "cron", etc.
            agent_context (str):     "primary", "subagent", "cron", "flush"
            agent_identity (str):    Profile name (e.g. "coder")
            agent_workspace (str):   Shared workspace name (e.g. "hermes")
            skip_memory (bool):      True for subagents that shouldn't write
        """
        self._hermes_home = kwargs.get("hermes_home", "")
        self._session_id = session_id
        self._platform = kwargs.get("platform", "cli")
        self._agent_context = kwargs.get("agent_context", "primary")
        self._agent_identity = kwargs.get("agent_identity", "")
        self._agent_workspace = kwargs.get("agent_workspace", "")
        self._skip_memory = kwargs.get("skip_memory", False)

        # Load plugin config from this session's hermes_home
        plugin_config = _load_plugin_config(self._hermes_home or None)
        if plugin_config:
            self._auto_extract = _coerce_bool(
                plugin_config.get("auto_extract"), self._auto_extract
            )
            self._query_rewrite = _query_rewrite_enabled(plugin_config)
            self._evolve_interval = int(
                plugin_config.get("evolve_interval", self._evolve_interval)
            )
            self._memory_nudge_interval = int(
                plugin_config.get("memory_nudge_interval", self._memory_nudge_interval)
            )
            self._char_limit = int(
                plugin_config.get("char_limit", self._char_limit)
            )
            self._peer_card_cadence_s = float(
                plugin_config.get("peer_card_cadence_s", self._peer_card_cadence_s)
            )
            self._session_digest_enabled = _coerce_bool(
                plugin_config.get("session_digest"), self._session_digest_enabled
            )
            self._observe_on_session_end = _coerce_bool(
                plugin_config.get("observe_on_session_end"), self._observe_on_session_end
            )
            self._replay_on_session_end = _coerce_bool(
                plugin_config.get("replay_on_session_end"), self._replay_on_session_end
            )
            self._conflict_detect = _coerce_bool(
                plugin_config.get("conflict_detect"), self._conflict_detect
            )
        else:
            self._query_rewrite = _query_rewrite_enabled(None)

        # Framework path housing
        from hermescube.framework.paths import resolve_cube_paths
        from hermescube.framework.void import CubeVoid
        from hermescube.colony import ColonyGraph

        self._paths = resolve_cube_paths(
            self._hermes_home or None,
            agent_identity=self._agent_identity,
            agent_workspace=self._agent_workspace,
        )
        self._paths.ensure()
        cube_dir = self._paths.memories_dir
        self._cube_path = str(self._paths.cube)

        # Open or create
        if os.path.isfile(self._cube_path):
            self._cube = CubeFile.open(self._cube_path)
        else:
            self._cube = CubeFile.create(
                self._cube_path,
                dim=self._dim,
                l2_buckets=self._l2_buckets,
            )

        self._engine = HARQueryEngine(self._cube)

        # Colony + void OS
        try:
            self._colony = ColonyGraph(self._paths.colony_graph)
            try:
                for e in (self._cube.read_l1() or [])[-80:]:
                    self._colony.register_dance(e)
            except Exception:
                pass
            setattr(self._engine, "_colony", self._colony)
        except Exception as e:
            logger.debug("colony init skipped: %s", e)
            self._colony = None

        self._void = CubeVoid(
            self._cube, self._engine, self._paths, colony=self._colony
        )
        try:
            self._void.rebuild_lex()
            setattr(self._engine, "_lexindex", self._void.lex)
        except Exception as e:
            logger.debug("lexindex build: %s", e)

        # Yield Gradient — query-conditioned learning loop (Nous-inspired principle)
        try:
            from hermescube.yield_trail import YieldGradient, default_path

            self._yield = YieldGradient(default_path(self._hermes_home or Path.home() / ".hermes"))
            setattr(self._engine, "_yield_gradient", self._yield)
        except Exception as e:
            logger.debug("yield gradient skipped: %s", e)
            self._yield = None

        # Engram Net — Hebbian + Hopfield-style associative field (Cube-native neural)
        try:
            from hermescube.engram_net import EngramNet, default_path as engram_path

            self._engram = EngramNet(engram_path(self._hermes_home or Path.home() / ".hermes"))
            setattr(self._engine, "_engram_net", self._engram)
        except Exception as e:
            logger.debug("engram net skipped: %s", e)
            self._engram = None

        # Load trained embedder from disk if available
        embedder_path = str(self._paths.embedder)
        if os.path.isfile(embedder_path):
            from hermescube.embed import LearnedEmbedder
            self._engine._embedder = LearnedEmbedder.load(embedder_path)
            if self._engine._embedder.is_trained:
                self._evolve_lambda_trained = True

        # Load frozen snapshot
        beta = self._cube.read_l3()
        try:
            centroids = self._cube.read_l2()
        except Exception as e:
            logger.warning("read_l2 failed during initialize: %s", e)
            centroids = []
        self._snapshot = _FrozenSnapshot(
            beta=beta,
            l2_centroids=centroids,
            entry_count=self._cube.entry_count,
        )

    def _should_skip_writes(self) -> bool:
        """True when we should NOT persist data.

        Skips writes for: cron contexts (system prompts would corrupt
        user representations), flush-only contexts, explicit skip_memory flag.
        """
        if self._skip_memory:
            return True
        if self._agent_context in ("cron", "flush"):
            return True
        return False

    # ── Circuit breaker ────────────────────────────────────────────

    def _is_evolve_breaker_open(self) -> bool:
        """True if the evolve circuit breaker is tripped."""
        if self._evolve_failures < _EVOLVE_BREAKER_THRESHOLD:
            return False
        if time.monotonic() >= self._evolve_breaker_until:
            self._evolve_failures = 0
            return False
        return True

    def _record_evolve_success(self) -> None:
        self._evolve_failures = 0

    def _record_evolve_failure(self) -> None:
        self._evolve_failures += 1
        if self._evolve_failures >= _EVOLVE_BREAKER_THRESHOLD:
            self._evolve_breaker_until = time.monotonic() + _EVOLVE_BREAKER_COOLDOWN_SECS
            logger.warning(
                "HermesCube evolve circuit breaker tripped after %d consecutive "
                "failures. Pausing evolve for %ds.",
                self._evolve_failures, _EVOLVE_BREAKER_COOLDOWN_SECS,
            )

    def _refresh_snapshot(self) -> None:
        """Re-read β + L2 from cube and update the frozen snapshot."""
        if not self._cube:
            return
        beta = self._cube.read_l3()
        try:
            centroids = self._cube.read_l2()
        except Exception as e:
            logger.warning("read_l2 failed during _refresh_snapshot: %s", e)
            centroids = []
        self._snapshot = _FrozenSnapshot(
            beta=beta,
            l2_centroids=centroids,
            entry_count=self._cube.entry_count,
        )
        self._prefetch_cache.clear()

    def shutdown(self) -> None:
        """Flush background sync, close cube, save embedder.

        Idempotent — safe to call multiple times. Does not break
        sibling instances of the same provider (no shared state).
        """
        # Save embedder before shutdown (once)
        if (self._engine and self._engine._embedder
                and self._engine._embedder.is_trained
                and self._cube_path):
            try:
                embedder_path = str(Path(self._cube_path).parent / "memory.embedder")
                self._engine._embedder.save(embedder_path)
            except Exception as e:
                logger.debug("shutdown embedder save failed: %s", e)

        # Drain background sync
        try:
            self._sync_queue.flush(timeout=5.0)
        except Exception as e:
            logger.debug("shutdown sync flush failed: %s", e)

        try:
            net = getattr(self, "_engram", None)
            if net is not None:
                net.save()
            yg = getattr(self, "_yield", None)
            if yg is not None and hasattr(yg, "save"):
                yg.save()
        except Exception as e:
            logger.debug("shutdown engram/yield save failed: %s", e)

        # Close cube (idempotent — close() is safe on None)
        if self._cube:
            try:
                self._cube.close()
            except Exception as e:
                logger.debug("shutdown cube close failed: %s", e)
            self._cube = None
        self._engine = None

    # ── MemoryProvider ABC: config ─────────────────────────────────

    def get_config_schema(self) -> list[dict[str, Any]]:
        """Return config fields for 'hermes memory setup' wizard.

        HermesCube is local-only — no API keys or network deps.
        """
        return [
            {
                "key": "auto_extract",
                "description": (
                    "Auto-extract facts from conversations at session end "
                    "using pattern matching"
                ),
                "required": False,
                "default": "false",
                "choices": ["true", "false"],
            },
            {
                "key": "dim",
                "description": "HRR vector dimension (256 recommended)",
                "required": False,
                "default": "256",
            },
            {
                "key": "l2_buckets",
                "description": "Number of L2 topic buckets for HAR clustering",
                "required": False,
                "default": "64",
            },
            {
                "key": "char_limit",
                "description": "Maximum characters per memory entry",
                "required": False,
                "default": "2200",
            },
            {
                "key": "evolve_interval",
                "description": "Auto-evolve after this many entries (0 to disable)",
                "required": False,
                "default": "50",
            },
            {
                "key": "memory_nudge_interval",
                "description": (
                    "Remind agent to review memory every N turns "
                    "(0 to disable)"
                ),
                "required": False,
                "default": "10",
            },
            {
                "key": "peer_card_cadence_s",
                "description": "Min seconds between peer-card rebuilds (0=every session_end)",
                "required": False,
                "default": "3600",
            },
            {
                "key": "session_digest",
                "description": "Write a non-LLM session digest landmark on session_end",
                "required": False,
                "default": "true",
                "choices": ["true", "false"],
            },
            {
                "key": "observe_on_session_end",
                "description": "Auto trajectory-observe on session_end",
                "required": False,
                "default": "true",
                "choices": ["true", "false"],
            },
            {
                "key": "replay_on_session_end",
                "description": "Auto sleep-replay into Engram on session_end",
                "required": False,
                "default": "true",
                "choices": ["true", "false"],
            },
            {
                "key": "conflict_detect",
                "description": "Soft-flag contradictions on belief/resolve add",
                "required": False,
                "default": "true",
                "choices": ["true", "false"],
            },
        ]

    def save_config(self, values: dict[str, Any], hermes_home: str) -> None:
        """Write config to config.yaml under ``plugins.hermescube``.

        Merge-preserving: reads existing config, updates only the
        hermescube block, writes back. Follows the Holographic
        provider's pattern exactly.
        """
        config_path = Path(hermes_home) / "config.yaml"
        try:
            import yaml
            existing: dict[str, Any] = {}
            if config_path.exists():
                with open(config_path, encoding="utf-8-sig") as f:
                    existing = yaml.safe_load(f) or {}
            existing.setdefault("plugins", {})
            existing["plugins"]["hermescube"] = values
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.dump(existing, f, default_flow_style=False)
        except Exception as e:
            logger.warning("could not write config.yaml: %s", e)
            # Fallback: write to hermescube.json in memories dir
            config_dir = Path(hermes_home) / "memories"
            config_dir.mkdir(parents=True, exist_ok=True)
            json_path = config_dir / "hermescube.json"
            json_path.write_text(json.dumps(values, indent=2))

    def backup_paths(self) -> list[str]:
        """Cube files live under HERMES_HOME/memories/ — included in backup."""
        return []

    # ── MemoryProvider ABC: tool schemas ───────────────────────────

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return OpenAI function-calling tool schemas."""
        return [
            {
                "name": "hermescube_search",
                "description": (
                    "Search persistent memory for relevant past conversations, "
                    "decisions, and facts using holographic associative retrieval. "
                    "Returns ranked results with scores. Use this to recall context "
                    "from previous sessions before answering questions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query",
                        },
                        "entry_type": {
                            "type": "string",
                            "enum": [
                                "landmark", "belief", "trait", "focus",
                                "resolve", "evolution", "relationship",
                                "enter", "leave", "epoch_transition",
                            ],
                            "description": "Filter by entry type (optional)",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Max results (default 10)",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hermescube_manage",
                "description": (
                    "Add, remove, or crystalize entries in persistent memory. "
                    "Use add for durable facts; crystalize consolidates near-duplicates "
                    "into active wisdom beliefs (offline, no LLM)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "add",
                                "remove",
                                "crystalize",
                                "journey",
                                "hygiene",
                                "prune",
                                "forge",
                                "replay",
                                "intents",
                                "observe",
                                "promote",
                                "reject",
                                "drafts",
                                "peer",
                            ],
                            "description": "warehouse ops + consent promote/reject + peer card",
                        },
                        "entry_type": {
                            "type": "string",
                            "enum": [
                                "landmark", "belief", "trait", "focus",
                                "resolve", "evolution", "relationship",
                            ],
                            "description": "Entry type for add action",
                        },
                        "content": {
                            "type": "string",
                            "description": "Memory content (for add)",
                        },
                        "entry_id": {
                            "type": "string",
                            "description": "Entry ID (for remove)",
                        },
                        "outcome": {
                            "type": "string",
                            "enum": ["none", "success", "failure", "pending", "superseded"],
                            "description": "Outcome (for add, default none)",
                        },
                    },
                    "required": ["action"],
                },
            },
            {
                "name": "hermescube_feedback",
                "description": (
                    "Rate a memory entry retrieved via hermescube_search. "
                    "Mark 'helpful' if the entry was accurate and useful, "
                    "'unhelpful' if outdated or incorrect. This trains the "
                    "memory system — good entries rise, bad entries sink."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["helpful", "unhelpful"],
                            "description": "Rating for this memory entry",
                        },
                        "entry_id": {
                            "type": "string",
                            "description": "The entry ID to rate (from hermescube_search result)",
                        },
                    },
                    "required": ["action", "entry_id"],
                },
            },
            {
                "name": "hermescube_probe",
                "description": (
                    "Entity-focused recall (agent hyper-memory). "
                    "probe: everything about a person/place/thing. "
                    "related: neighbors via entity graph + colony trails."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["probe", "related"],
                            "description": "probe=about entity; related=graph neighbors",
                        },
                        "entity": {
                            "type": "string",
                            "description": "Entity name (person, project, path token)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results (default 8)",
                        },
                    },
                    "required": ["action", "entity"],
                },
            },
        ]

    def handle_tool_call(
        self, tool_name: str, args: dict[str, Any], **kwargs: Any
    ) -> str:
        """Dispatch memory tool calls."""
        if tool_name == "hermescube_search":
            return self._handle_search(args)
        elif tool_name == "hermescube_manage":
            return self._handle_manage(args)
        elif tool_name == "hermescube_feedback":
            return self._handle_feedback(args)
        elif tool_name == "hermescube_probe":
            return self._handle_probe(args)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # ── MemoryProvider ABC: system prompt ──────────────────────────

    def system_prompt_block(self) -> str:
        """Return memory capabilities block for system prompt (meta-memory).

        Quicksilver / Hermes 0.19: this runs on agent init / prompt assembly —
        never full-scan L1 here. Header counts only.
        """
        if not self._cube:
            return ""

        entry_count = self._cube.entry_count
        type_counts = self._cube.count_by_type()

        lines = [
            "# HermesCube — deep memory warehouse (extension layer)",
            "Purpose: long-tail durable recall **alongside** hot MEMORY.md/USER.md — not a replacement.",
            "Hermes layering (0.19 contract):",
            "  MEMORY.md  = short always-on doctrine (char budget)",
            "  memory tool = atomic batch writes (mirrored into cube via on_memory_write)",
            "  Cube        = WAL chat turns + deep archive + entity/colony graph",
            "  Hermespace  = FOA desk; optional space_bridge injects a tiny cube strip under load",
            f"Stored: {entry_count} memories · path under $HERMES_HOME/memories/",
        ]

        if type_counts:
            top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]
            type_str = ", ".join(f"{t}:{c}" for t, c in top_types)
            lines.append(f"Types: {type_str}")

        lines.extend([
            "Day-to-day: turn WAL sync; built-in memory tool writes mirrored; evolve on session_end.",
            "Hemispheres: awake=prefetch/query · sleep=evolve/consolidate",
            "",
            "Tools:",
            "- hermescube_search — deep recall (lex-first + HRR/bio rank)",
            "- hermescube_probe — entity focus (person/project/path)",
            "- hermescube_manage — durable facts (prefer declarative)",
            "- hermescube_feedback — train trust on retrieved entries",
            "",
            "Guidance:",
            "- Short doctrine → built-in memory tool; history-shaped answers → cube search first",
            "- Prefetch is injected by Hermes as <memory-context> — treat as reference, not user speech",
            "- DO NOT store temp todos / session fluff",
        ])
        # Active wisdom strip (crystals / beliefs)
        try:
            from hermescube.wisdom import active_wisdom, functional_loop_stats

            ents = []
            # cheap: use engine cache if warm else skip full read on huge archives
            if self._engine is not None:
                try:
                    self._engine.refresh_cache()
                    ents = list(getattr(self._engine, "_entries", None) or [])
                except Exception:
                    ents = []
            if not ents and self._cube and self._cube.entry_count <= 200:
                ents = list(self._cube.read_l1() or [])
            if ents:
                stats = functional_loop_stats(ents)
                lines.append("")
                lines.append(
                    f"Functional loop: crystals={stats.get('crystal_count')} "
                    f"beliefs={stats.get('belief_count')} "
                    f"wisdom_ratio={stats.get('wisdom_ratio')} "
                    f"dup_pressure={stats.get('dup_pressure')} "
                    f"healthy={stats.get('healthy')}"
                )
                wisdom = active_wisdom(ents, limit=5)
                if wisdom:
                    lines.append("Active wisdom:")
                    for w in wisdom:
                        tag = "crystal" if (w.data or {}).get("crystal") else (w.entry_type or "belief")
                        lines.append(f"  · [{tag}] {(w.description or '')[:100]}")
                # Prospective open intents (focus until resolve)
                try:
                    from hermescube.prospective import prompt_strip

                    strip = prompt_strip(ents, limit=4, high_load=False)
                    if strip:
                        lines.append("")
                        lines.append(strip)
                except Exception:
                    pass
                try:
                    from hermescube.peer_card import load_card, prompt_strip as peer_strip

                    card = load_card(self._hermes_home)
                    ps = peer_strip(card, max_lines=5)
                    if ps:
                        lines.append("")
                        lines.append(ps)
                except Exception:
                    pass
        except Exception:
            pass

        return "\n".join(lines)

    # ── MemoryProvider ABC: prefetch ──────────────────────────────

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        """Recall relevant memories via CubeVoid (framework housing)."""
        if not self._engine or not self._snapshot:
            return ""
        if not query or not query.strip():
            return ""

        retrieval_query = _try_query_rewrite(
            query, enabled=bool(getattr(self, "_query_rewrite", False))
        )
        self._last_prefetch_query = retrieval_query
        self._last_prefetch_ids = []

        cache_key = hashlib.md5(retrieval_query.encode()).hexdigest()
        if cache_key in self._prefetch_cache:
            results = self._prefetch_cache[cache_key]
        else:
            if self._void is not None:
                results = self._void.recall(
                    retrieval_query,
                    top_k=DEFAULT_PREFETCH_TOP_K,
                    beta=self._snapshot.beta,
                    centroids=self._snapshot.l2_centroids,
                )
            else:
                results = self._engine.query(
                    retrieval_query,
                    top_k=DEFAULT_PREFETCH_TOP_K,
                    beta=self._snapshot.beta,
                    centroids=self._snapshot.l2_centroids,
                )
            if len(self._prefetch_cache) >= self._prefetch_cache_max:
                oldest_key = next(iter(self._prefetch_cache))
                del self._prefetch_cache[oldest_key]
            self._prefetch_cache[cache_key] = results

        if not results:
            return ""
        try:
            self._last_prefetch_ids = [
                str(getattr(e, "id", "") or "") for e, _ in results if getattr(e, "id", None)
            ]
        except Exception:
            self._last_prefetch_ids = []
        # periodic engram flush
        try:
            net = getattr(self, "_engram", None)
            if net is not None and self._turn_count % 5 == 0:
                net.save()
        except Exception:
            pass
        if self._void is not None:
            return self._void.format_prefetch(results)
        # minimal fallback
        lines = ["[Relevant memories from past sessions:]"]
        for entry, _score in results[:5]:
            ts = entry.timestamp[:10] if entry.timestamp else "unknown"
            lines.append(f"- [{ts}] [{entry.entry_type}] {entry.description}")
        return "\n".join(lines)

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        """Background prefetch for next turn (non-blocking)."""
        self._sync_queue.submit(self.prefetch, query, session_id=session_id)

    # ── MemoryProvider ABC: sync ──────────────────────────────────

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        """Store completed conversation turn — durable (sync append).

        Day-to-day contract: turns hit cubelog WAL **before** return so a
        crash does not drop the exchange. Heavy evolve stays background.
        """
        if not self._cube or self._should_skip_writes():
            return

        user_clean = sanitize_for_storage(user_content, self._char_limit)
        assistant_clean = sanitize_for_storage(assistant_content, self._char_limit)

        if not user_clean and not assistant_clean:
            return

        # Functional memory gate: skip pure chitchat (prevents landmark spam)
        try:
            from hermescube.wisdom import is_durable_turn

            if not is_durable_turn(user_clean or "", assistant_clean or ""):
                self._turn_count += 1
                return
        except Exception:
            pass

        for text in [user_clean, assistant_clean]:
            threats = scan_text(text)
            if any(t.severity == "block" for t in threats):
                return

        desc = user_clean[:200] if user_clean else "(empty turn)"
        data: dict[str, Any] = {
            "user": user_clean,
            "assistant": assistant_clean,
            "session_id": session_id or self._session_id,
            "turn": self._turn_count,
            "timestamp": time.time(),
            "platform": self._platform,
            "agent_context": self._agent_context,
            "source": "sync_turn",
        }

        entry_type = self._classify_turn(user_clean, assistant_clean)

        uq = (user_clean or "").strip()
        aq = (assistant_clean or "").strip()
        is_question = uq.endswith("?") or uq.lower().startswith(
            ("who ", "what ", "where ", "when ", "why ", "how ", "can ", "should ")
        )
        if is_question and aq:
            desc = aq[:200]
            data["question"] = uq[:200]
            data["indexed_from"] = "assistant"
            data.setdefault("trust", 0.45)
        else:
            data.setdefault("trust", 0.55)

        outcome = "none"
        if assistant_clean:
            lower = assistant_clean.lower()
            if any(w in lower for w in ["done", "completed", "fixed", "resolved", "implemented"]):
                outcome = "success"
            elif any(w in lower for w in ["failed", "error", "couldn't", "unable"]):
                outcome = "failure"

        try:
            from hermescube import bio_rank as _br
            fact_lines = _br.extract_fact_lines(aq or assistant_clean or "")
        except Exception:
            fact_lines = []

        # SYNC durable write — cubelog is O(1); do not queue this
        try:
            added = self._cube.append(
                entry_type=entry_type,
                description=desc,
                data=data,
                outcome=outcome,
            )
            for fet, fdesc in fact_lines:
                try:
                    self._cube.append(
                        entry_type=fet,
                        description=fdesc,
                        data={
                            "source": "extract",
                            "trust": 0.7,
                            "durable": True,
                            "session_id": session_id or self._session_id,
                        },
                        outcome="none",
                    )
                except Exception:
                    pass
            if self._engine and added.vector is not None:
                try:
                    self._engine.update_beta_on_append(added.vector)
                except Exception:
                    if self._engine:
                        self._engine.invalidate_cache()
            self._prefetch_cache.clear()
        except Exception as e:
            logger.error("sync_turn durable write failed: %s", e)
            return

        # Background: evolve only (never block the agent turn)
        self._entries_since_evolve += 1
        evolve_interval = self._evolve_interval
        if (
            evolve_interval > 0
            and self._entries_since_evolve >= evolve_interval
            and not self._is_evolve_breaker_open()
        ):
            def _bg_evolve() -> None:
                try:
                    self.evolve_consolidated()
                    self._entries_since_evolve = 0
                    self._refresh_snapshot()
                    self._record_evolve_success()
                except Exception as e:
                    self._record_evolve_failure()
                    logger.warning("auto-evolve failed: %s", e)

            self._sync_queue.submit(_bg_evolve)

    # ── MemoryProvider ABC: lifecycle hooks ───────────────────────

    def on_turn_start(self, turn_number: int, message: str, **kwargs: Any) -> None:
        """Notify provider of new turn. Triggers memory nudge when interval hit."""
        self._turn_count = turn_number
        self._turns_since_memory += 1

    def should_review_memory(self) -> bool:
        """Check if agent should be nudged to review/consolidate memory."""
        if self._memory_nudge_interval <= 0:
            return False
        if self._turns_since_memory >= self._memory_nudge_interval:
            self._turns_since_memory = 0
            return True
        return False

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        """Session complete — final consolidation + flush sync."""
        if not self._engine or not self._cube:
            return

        # Auto-extract facts if configured (runs regardless of entry count)
        if self._auto_extract and not self._should_skip_writes():
            self._auto_extract_facts(messages)

        # Wisdom crystalizer — episodic → active beliefs (offline, no LLM)
        if not self._should_skip_writes() and self._cube.entry_count >= 4:
            try:
                from hermescube.wisdom import crystalize

                stats = crystalize(self._cube, min_cluster=2, max_crystals=8)
                if stats.get("crystals"):
                    logger.info("wisdom crystalize: %s", stats)
                    self._prefetch_cache.clear()
                    if self._engine:
                        try:
                            self._engine.invalidate_cache()
                        except Exception:
                            pass
            except Exception as e:
                logger.debug("wisdom crystalize skipped: %s", e)

        # Sleep replay — Engram Net consolidation (CLS offline teaching)
        if (
            self._replay_on_session_end
            and not self._should_skip_writes()
            and self._cube.entry_count >= 6
        ):
            try:
                net = getattr(self, "_engram", None)
                if net is not None:
                    from hermescube.sleep_replay import sleep_replay

                    rstats = sleep_replay(self._cube, net, max_patterns=16)
                    net.save()
                    if rstats.get("patterns_added"):
                        logger.info("sleep_replay: %s", rstats)
            except Exception as e:
                logger.debug("sleep_replay skipped: %s", e)

        # Trajectory observe — successful multi-tool chains → procedure drafts
        if (
            self._observe_on_session_end
            and not self._should_skip_writes()
            and messages
        ):
            try:
                from hermescube.trajectory import observe_messages

                tstats = observe_messages(
                    self._cube,
                    messages,
                    hermes_home=self._hermes_home,
                    min_tools=3,
                    max_forge=2,
                )
                if tstats.get("forged"):
                    logger.info("trajectory_observe: %s", tstats)
                    self._prefetch_cache.clear()
            except Exception as e:
                logger.debug("trajectory_observe skipped: %s", e)

        # Session digest (non-LLM narrative) + peer card cadence refresh
        if not self._should_skip_writes():
            try:
                ents = list(self._cube.read_l1() or [])
                open_i = []
                try:
                    from hermescube.prospective import open_focuses

                    open_i = [
                        (e.description or "")[:80]
                        for e in open_focuses(ents, limit=3)
                        if e.description
                    ]
                except Exception:
                    pass
                if self._session_digest_enabled and messages:
                    from hermescube.session_digest import (
                        digest_messages,
                        digest_entry_description,
                    )

                    dig = digest_messages(messages, open_intents=open_i)
                    self._cube.append(
                        entry_type="landmark",
                        description=digest_entry_description(dig),
                        data={
                            "source": "session_digest",
                            "session_id": self._session_id,
                            "trust": 0.65,
                            "durable": True,
                        },
                        outcome="success",
                    )
                from hermescube.peer_card import refresh_card

                refresh_card(
                    ents,
                    hermes_home=self._hermes_home,
                    peer_name=self._agent_identity or "user",
                    min_interval_s=float(self._peer_card_cadence_s or 0),
                )
            except Exception as e:
                logger.debug("session_digest/peer_card skipped: %s", e)

        if self._cube.entry_count > 0:
            # Avoid evolve if breaker is open
            if not self._is_evolve_breaker_open():
                try:
                    self.evolve_consolidated()
                    self._refresh_snapshot()
                    self._record_evolve_success()
                except Exception as e:
                    self._record_evolve_failure()
                    logger.warning("session-end evolve failed: %s", e)
        self._sync_queue.flush(timeout=5.0)

    def on_session_switch(
        self,
        new_session_id: str,
        *,
        parent_session_id: str = "",
        reset: bool = False,
        rewound: bool = False,
        **kwargs: Any,
    ) -> None:
        """Session rotated — update session tracking.

        Follows the HermesAgent MemoryProvider contract:
        - reset=True: genuinely new session, flush all per-session state
        - reset=False: /resume or /branch, continues logically
        - rewound=True: transcript truncated, invalidate document caches
        """
        self._session_id = new_session_id

        if reset:
            self._turn_count = 0
            self._turns_since_memory = 0
            self._prefetch_cache.clear()

        if rewound:
            self._prefetch_cache.clear()
            self._entries_cache = None

    def on_pre_compress(self, messages: list[dict[str, Any]]) -> str:
        """Extract structured insights before context compression."""
        if not messages or self._should_skip_writes():
            return ""

        insights: list[str] = []
        user_msgs: list[str] = []
        assistant_msgs: list[str] = []
        decisions: list[str] = []
        constraints: list[str] = []

        for msg in messages[-20:]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 10:
                continue

            if role == "user":
                user_msgs.append(content[:300])
                lower = content.lower()
                if any(w in lower for w in ["must", "should", "never", "always", "don't", "require"]):
                    constraints.append(content[:200])
            elif role == "assistant":
                assistant_msgs.append(content[:300])
                lower = content.lower()
                if any(w in lower for w in ["decided", "chose", "recommend", "approach", "solution"]):
                    decisions.append(content[:200])

        if user_msgs:
            insights.append(f"Current topic: {user_msgs[-1][:150]}")
        if decisions:
            insights.append(f"Recent decisions: {'; '.join(d[:100] for d in decisions[-3:])}")
        if constraints:
            insights.append(f"Constraints: {'; '.join(c[:100] for c in constraints[-3:])}")
        if assistant_msgs:
            insights.append(f"Last response preview: {assistant_msgs[-1][:150]}")

        if not insights:
            return ""

        summary = " | ".join(insights)
        cube = self._cube
        session_id = self._session_id

        if cube:
            def _do_compress_write() -> None:
                cube.append(
                    entry_type="epoch_transition",
                    description=summary[:500],
                    data={
                        "type": "compression_insight",
                        "session_id": session_id,
                        "message_count": len(messages),
                        "decisions": decisions[-3:],
                        "constraints": constraints[-3:],
                    },
                )
            self._sync_queue.submit(_do_compress_write)

        return "[Context compression insights — preserved in HermesCube memory:]\n" + "\n".join(insights)

    def on_memory_write(
        self,
        action: str,
        target: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mirror built-in MEMORY.md / USER.md writes into the cube (extension layer).

        Hermes keeps hot MEMORY.md; Cube is the larger durable archive.
        Day-to-day: when the agent uses the built-in memory tool, Cube
        receives a durable copy so nothing lives only in the short file.
        """
        if not self._cube or self._should_skip_writes():
            return

        if action == "remove":
            # Soft-mark only — cube is append-only
            return

        if action in ("add", "replace") and content:
            threats = scan_text(content)
            if any(t.severity == "block" for t in threats):
                return

            entry_type = "trait" if target == "user" else "belief"
            safe_content = sanitize_for_storage(content, self._char_limit)
            write_meta = dict(metadata or {})
            # SYNC durable — same day-to-day no-loss contract as sync_turn
            try:
                self._cube.append(
                    entry_type=entry_type,
                    description=safe_content,
                    data={
                        "source": f"builtin_{target}",
                        "mirror": True,
                        "durable": True,
                        "trust": 0.85,
                        "extension_of": "MEMORY.md" if target == "memory" else "USER.md",
                        "provenance": write_meta,
                        "action": action,
                    },
                )
                if self._engine:
                    self._engine.invalidate_cache()
                self._prefetch_cache.clear()
            except Exception as e:
                logger.error("on_memory_write durable mirror failed: %s", e)

    def on_delegation(
        self,
        task: str,
        result: str,
        *,
        child_session_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Subagent completion — store delegation result via sync queue."""
        if not self._cube or self._should_skip_writes():
            return

        cube = self._cube
        desc = sanitize_for_storage(f"Delegated: {task[:150]}", self._char_limit)
        safe_result = sanitize_for_storage(result, self._char_limit)
        outcome = "success" if result else "failure"

        def _do_delegation() -> None:
            cube.append(
                entry_type="landmark",
                description=desc,
                data={
                    "child_session_id": child_session_id,
                    "result": safe_result,
                    "type": "delegation",
                },
                outcome=outcome,
            )
            if outcome == "success":
                try:
                    from hermescube.trajectory import observe_delegation

                    observe_delegation(
                        cube,
                        task,
                        result,
                        hermes_home=self._hermes_home,
                        child_session_id=child_session_id,
                    )
                except Exception:
                    pass

        self._sync_queue.submit(_do_delegation)

    # ── Evolution: HermesAgent-style consolidation ────────────────

    def evolve_consolidated(self) -> dict[str, Any]:
        """Offline sleep consolidation (unihemispheric — never on prefetch).

        Phases (bio / SCM-inspired):
        - NREM-like: k-means L2 + β update + dedup (stabilize)
        - REM-like: topic quality hubs (novel association surface)
        - Forgetting: superseded weighting via outcome (soft; append-only)
        """
        if not self._engine or not self._cube:
            return {"note": "not initialized"}

        from hermescube import bio_rank

        # NREM: structural consolidate
        stats = self._engine.evolve()
        stats["phase"] = "sleep_consolidate"

        if self._engine._embedder and self._engine._embedder.is_trained:
            embedder_path = str(Path(self._cube_path).parent / "memory.embedder")
            self._engine._embedder.save(embedder_path)
            self._evolve_lambda_trained = True

        deduped = self._deduplicate_entries()
        stats["deduped"] = deduped
        stats["nrem"] = {"clusters": stats.get("clusters"), "deduped": deduped}

        # REM: hub surface
        topics = self._score_topics()
        stats["topics"] = topics
        stats["quality_score"] = round(
            sum(t["quality"] for t in topics) / max(len(topics), 1), 3
        )
        stats["rem_hubs"] = [
            {"terms": (t.get("terms") or [])[:4], "quality": t.get("quality")}
            for t in sorted(topics, key=lambda x: -float(x.get("quality", 0)))[:5]
        ]

        try:
            entries = self._cube.read_l1()
            stats["meta"] = bio_rank.meta_memory_report(entries, topics)
        except Exception as e:
            logger.debug("meta_memory_report failed: %s", e)

        return stats

    def _deduplicate_entries(self) -> int:
        """Find and merge near-identical entries."""
        if not self._cube:
            return 0

        entries = self._cube.read_l1()
        if len(entries) < 2:
            return 0

        by_type: dict[str, list[CubeEntry]] = {}
        for e in entries:
            by_type.setdefault(e.entry_type, []).append(e)

        deduped = 0
        seen_ids: set[str] = set()

        for etype, type_entries in by_type.items():
            if len(type_entries) < 2:
                continue

            for i, e1 in enumerate(type_entries):
                if e1.id in seen_ids:
                    continue
                for e2 in type_entries[i + 1:]:
                    if e2.id in seen_ids:
                        continue
                    sim = hrr.cosine_sim(e1.vector, e2.vector)
                    if sim > CONSOLIDATION_SIMILARITY_THRESHOLD:
                        if len(e1.description) >= len(e2.description):
                            self._supersede_entry(e2, e1.id)
                        else:
                            self._supersede_entry(e1, e2.id)
                            seen_ids.add(e1.id)
                        seen_ids.add(e2.id)
                        deduped += 1

        return deduped

    def _supersede_entry(self, entry: CubeEntry, superseded_by: str) -> None:
        """Mark an entry as superseded by another."""
        if not self._cube:
            return
        self._cube.append(
            entry_type=entry.entry_type,
            description=f"[SUPERSEDED by {superseded_by}] {entry.description[:100]}",
            data={
                "supersedes": entry.id,
                "superseded_by": superseded_by,
                "source": "auto_dedup",
            },
            outcome="superseded",
        )

    def _score_topics(self) -> list[dict[str, Any]]:
        """Score each L2 topic bucket for quality."""
        if not self._cube:
            return []

        try:
            buckets = self._cube.read_l2()
        except Exception as e:
            logger.warning("read_l2 failed in _score_topics: %s", e)
            return []

        # Read L1 once, build lookup — avoid re-reading per bucket
        entries = self._cube.read_l1()
        id_to_entry = {e.id: e for e in entries}

        topics: list[dict[str, Any]] = []
        for i, bucket in enumerate(buckets):
            if not bucket.entry_ids:
                continue

            entry_count = len(bucket.entry_ids)
            term_count = len(bucket.terms)

            close_count = 0
            for eid in bucket.entry_ids:
                entry = id_to_entry.get(eid)
                if entry:
                    sim = hrr.cosine_sim(bucket.centroid, entry.vector)
                    if sim > 0.3:
                        close_count += 1

            coherence = close_count / max(entry_count, 1)

            quality = (
                0.4 * min(entry_count / 10, 1.0)
                + 0.3 * min(term_count / 5, 1.0)
                + 0.3 * coherence
            )

            topics.append({
                "bucket": i,
                "entries": entry_count,
                "terms": bucket.terms[:5],
                "coherence": round(coherence, 3),
                "quality": round(quality, 3),
            })

        return sorted(topics, key=lambda t: -t["quality"])

    # ── Auto-extract ───────────────────────────────────────────────

    def _auto_extract_facts(self, messages: list[dict[str, Any]]) -> None:
        """Extract facts from conversation messages using regex patterns.

        Mirrors the Holographic provider's approach: match known
        patterns for user preferences, project decisions, and tool quirks.
        """
        if not self._cube:
            return

        extracted = 0
        for msg in messages:
            if msg.get("role") != "user":
                continue
            # Hermes 0.19 holo fix class: skip compaction handoff "user" summaries
            try:
                from agent.context_compressor import is_compaction_summary_message
                if is_compaction_summary_message(msg):
                    continue
            except Exception:
                content0 = msg.get("content", "")
                if isinstance(content0, str) and content0.lstrip().startswith(
                    ("[Context compression", "[Compressed", "Summary of conversation")
                ):
                    continue
            content = msg.get("content", "")
            if not isinstance(content, str) or len(content) < 10:
                continue

            for category, pattern in _AUTO_EXTRACT_PATTERNS:
                m = pattern.search(content)
                if m:
                    try:
                        self._cube.append(
                            entry_type="belief" if category != "user_pref" else "trait",
                            description=sanitize_for_storage(
                                content[:400], self._char_limit
                            ),
                            data={
                                "category": category,
                                "source": "auto_extract",
                                "session_id": self._session_id,
                            },
                        )
                        extracted += 1
                    except Exception as e:
                        logger.debug("auto_extract append failed: %s", e)
                    break

        if extracted:
            logger.info("Auto-extracted %d facts from session %s",
                        extracted, self._session_id)

    # ── Internal helpers ──────────────────────────────────────────

    def _classify_turn(self, user_msg: str, assistant_msg: str) -> str:
        """Classify conversation turn into entry type (bio / hierarchical)."""
        lower = (user_msg + " " + assistant_msg).lower()

        # Elephant social recognition
        if any(
            w in lower
            for w in (
                "relationship",
                "my friend",
                "my mom",
                "my partner",
                "client ",
                " co-worker",
                "coworker",
                "family",
            )
        ):
            return "relationship"
        if any(w in lower for w in ["prefer", "like", "always", "never", "style"]):
            return "trait"
        if any(w in lower for w in ["decided", "conclusion", "learned", "realized"]):
            return "belief"
        if any(w in lower for w in ["fixed", "resolved", "completed", "deployed"]):
            return "resolve"
        if any(w in lower for w in ["priority", "focus", "sprint", "goal"]):
            return "focus"
        if any(w in lower for w in ["changed", "evolved", "migrated", "refactored"]):
            return "evolution"
        # Spatial / route (elephant maps)
        if any(
            w in lower
            for w in ("address", "server", "host", "path ", "route", "vps", "domain")
        ):
            return "landmark"
        return "landmark"

    # ── Tool handlers ─────────────────────────────────────────────

    def _handle_search(self, args: dict[str, Any]) -> str:
        """Handle hermescube_search tool call."""
        query = args.get("query", "")
        entry_type = args.get("entry_type")
        top_k = args.get("top_k", 10)

        if not self._engine:
            return json.dumps({"error": "Memory not initialized"})

        results = self._engine.query(query, top_k=top_k)

        if entry_type:
            results = [(e, s) for e, s in results if e.entry_type == entry_type]

        formatted = []
        for entry, score in results:
            formatted.append({
                "id": entry.id,
                "type": entry.entry_type,
                "description": entry.description,
                "outcome": entry.outcome,
                "score": round(score, 4),
                "timestamp": entry.timestamp,
                "trust": entry.data.get("trust", 0.5) if entry.data else 0.5,
            })

        return json.dumps({"results": formatted, "count": len(formatted)})

    def _handle_probe(self, args: dict[str, Any]) -> str:
        """Entity probe/related — agent hyper-memory tools."""
        action = args.get("action", "probe")
        entity = (args.get("entity") or "").strip()
        limit = int(args.get("limit") or 8)
        if not entity:
            return json.dumps({"error": "entity is required"})
        if not self._engine:
            return json.dumps({"error": "Memory not initialized"})
        if action == "related" and hasattr(self._engine, "related"):
            results = self._engine.related(entity, top_k=limit)
        else:
            results = self._engine.query(entity, top_k=limit)
        formatted = []
        for entry, score in results:
            formatted.append({
                "id": entry.id,
                "type": entry.entry_type,
                "description": entry.description,
                "score": round(float(score), 4),
                "entities": (entry.data or {}).get("entities") if entry.data else [],
            })
        return json.dumps({
            "action": action,
            "entity": entity,
            "results": formatted,
            "count": len(formatted),
        })

    def _handle_manage(self, args: dict[str, Any]) -> str:
        """Handle hermescube_manage tool call."""
        action = args.get("action", "")

        if action == "add":
            return self._handle_manage_add(args)
        elif action == "remove":
            return self._handle_manage_remove(args)
        elif action == "crystalize":
            return self._handle_manage_crystalize(args)
        elif action == "replay":
            return self._handle_manage_replay(args)
        elif action == "journey":
            return self._handle_manage_journey(args)
        elif action == "hygiene":
            return self._handle_manage_hygiene(args)
        elif action == "prune":
            return self._handle_manage_prune(args)
        elif action == "forge":
            return self._handle_manage_forge(args)
        elif action == "intents":
            return self._handle_manage_intents(args)
        elif action == "observe":
            return self._handle_manage_observe(args)
        elif action == "promote":
            return self._handle_manage_promote(args)
        elif action == "reject":
            return self._handle_manage_reject(args)
        elif action == "drafts":
            return self._handle_manage_drafts(args)
        elif action == "peer":
            return self._handle_manage_peer(args)
        return json.dumps({"error": f"Unknown action: {action}"})

    def _handle_manage_promote(self, args: dict[str, Any]) -> str:
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.consent import promote

            name = str(args.get("name") or args.get("content") or "").strip()
            if not name:
                return json.dumps({"error": "name required (draft filename)"})
            r = promote(name, hermes_home=self._hermes_home, cube=self._cube)
            return json.dumps({"status": "promote", **r})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_reject(self, args: dict[str, Any]) -> str:
        try:
            from hermescube.consent import reject

            name = str(args.get("name") or args.get("content") or "").strip()
            if not name:
                return json.dumps({"error": "name required"})
            r = reject(
                name,
                hermes_home=self._hermes_home,
                reason=str(args.get("reason") or ""),
            )
            return json.dumps({"status": "reject", **r})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_drafts(self, args: dict[str, Any]) -> str:
        try:
            from hermescube.consent import list_pending

            return json.dumps(
                {"status": "ok", "pending": list_pending(self._hermes_home)}
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_peer(self, args: dict[str, Any]) -> str:
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.peer_card import refresh_card, load_card

            force = bool(args.get("force") or args.get("refresh"))
            ents = list(self._cube.read_l1() or [])
            if force:
                r = refresh_card(
                    ents,
                    hermes_home=self._hermes_home,
                    peer_name=self._agent_identity or "user",
                    min_interval_s=0,
                )
            else:
                card = load_card(self._hermes_home)
                if not card:
                    r = refresh_card(
                        ents,
                        hermes_home=self._hermes_home,
                        peer_name=self._agent_identity or "user",
                        min_interval_s=0,
                    )
                else:
                    r = {"skipped": True, "card": card}
            return json.dumps({"status": "ok", **{k: v for k, v in r.items() if k != "card"}, "card": r.get("card")})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_observe(self, args: dict[str, Any]) -> str:
        """Forge procedure drafts from tool trajectories in provided messages or last note."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.trajectory import observe_messages, extract_trajectories

            messages = args.get("messages")
            if not messages and args.get("tools"):
                # synthetic: list of tool names
                names = args.get("tools") or []
                if isinstance(names, str):
                    names = [n.strip() for n in names.split(",") if n.strip()]
                goal = str(args.get("goal") or args.get("content") or "manual observe")
                messages = [
                    {"role": "user", "content": goal},
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": n, "arguments": "{}"}} for n in names
                        ],
                    },
                ]
            if not messages:
                return json.dumps(
                    {
                        "error": "messages or tools required",
                        "hint": "pass tools=['terminal','patch','pytest'] goal='...'",
                    }
                )
            min_tools = int(args.get("min_tools") or 3)
            stats = observe_messages(
                self._cube,
                messages,
                hermes_home=self._hermes_home,
                min_tools=min_tools,
                max_forge=int(args.get("max_forge") or 3),
                write_drafts=bool(args.get("write_drafts", True)),
            )
            preview = extract_trajectories(messages, min_tools=min_tools)
            if stats.get("forged"):
                self._prefetch_cache.clear()
                if self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
            return json.dumps(
                {
                    "status": "observed",
                    "stats": stats,
                    "preview": [
                        {
                            "goal": t.get("goal"),
                            "tools": t.get("tool_names"),
                            "fp": t.get("fingerprint"),
                        }
                        for t in preview[:5]
                    ],
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_intents(self, args: dict[str, Any]) -> str:
        """List open prospective focuses; optional close by id."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.prospective import open_focuses, close_focus, status

            ents = list(self._cube.read_l1() or [])
            close_id = (args.get("close_id") or args.get("entry_id") or "").strip()
            if close_id:
                focus = next((e for e in ents if e.id == close_id), None)
                if focus is None:
                    return json.dumps({"error": f"focus not found: {close_id}"})
                closed = close_focus(
                    self._cube,
                    focus,
                    resolve_id="manual",
                    resolve_desc=str(args.get("note") or "manual close"),
                    match=1.0,
                )
                self._prefetch_cache.clear()
                if self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
                return json.dumps(
                    {
                        "status": "closed",
                        "focus_id": close_id,
                        "closed_id": getattr(closed, "id", None) if closed else None,
                    }
                )
            st = status(ents)
            return json.dumps({"status": "ok", "prospective": st})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_forge(self, args: dict[str, Any]) -> str:
        """Promote durable successes into procedure drafts (Nous skills-from-experience)."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.procedure import forge, list_candidates, list_drafts

            dry = bool(args.get("dry_run") or False)
            limit = int(args.get("limit") or 8)
            write_drafts = args.get("write_drafts")
            if write_drafts is None:
                write_drafts = True
            ents = list(self._cube.read_l1() or [])
            cands = list_candidates(ents, limit=limit)
            stats = forge(
                self._cube,
                hermes_home=self._hermes_home,
                limit=limit,
                write_drafts=bool(write_drafts),
                dry_run=dry,
            )
            if not dry and stats.get("forged"):
                self._prefetch_cache.clear()
                if self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
            return json.dumps(
                {
                    "status": "forged",
                    "stats": stats,
                    "candidates_preview": [
                        {
                            "id": e.id,
                            "type": e.entry_type,
                            "description": (e.description or "")[:120],
                            "outcome": e.outcome,
                        }
                        for e in cands[:8]
                    ],
                    "drafts_on_disk": list_drafts(self._hermes_home)[:20],
                }
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_hygiene(self, args: dict[str, Any]) -> str:
        """Prune noise from journey + cube + Hermespace world; re-push clean wisdom."""
        try:
            from hermescube.journey import run_hygiene

            if not self._cube:
                return json.dumps({"error": "Memory not initialized"})
            out = run_hygiene(
                hermes_home=self._hermes_home,
                agent_id=str(args.get("agent_id") or "hermes-agent"),
                cube=self._cube,
                sync_world=bool(args.get("sync_world", True)),
            )
            self._prefetch_cache.clear()
            if self._engine:
                try:
                    self._engine.invalidate_cache()
                except Exception:
                    pass
            return json.dumps({"status": "hygiene", **out})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_prune(self, args: dict[str, Any]) -> str:
        """Prune journey timeline events (edit surface)."""
        try:
            from hermescube.journey import prune_events, write_markdown, wisdom_from_cube

            kinds = args.get("drop_kinds") or None
            if isinstance(kinds, str):
                kinds = [kinds]
            ids = args.get("drop_entry_ids") or args.get("entry_ids") or None
            if isinstance(ids, str):
                ids = [ids]
            keep_last = args.get("keep_last")
            if keep_last is not None:
                keep_last = int(keep_last)
            stats = prune_events(
                self._hermes_home,
                drop_noise=bool(args.get("drop_noise", True)),
                drop_kinds=kinds,
                drop_entry_ids=ids,
                keep_last=keep_last,
            )
            ents = list(self._cube.read_l1() or []) if self._cube else []
            w = wisdom_from_cube(entries=ents)
            write_markdown(self._hermes_home, cube_wisdom=w)
            return json.dumps({"status": "pruned", **stats, "wisdom_n": len(w)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_journey(self, args: dict[str, Any]) -> str:
        """Show journey timeline and optionally push wisdom to Hermespace world."""
        try:
            from hermescube.journey import (
                read_events,
                render_markdown,
                write_markdown,
                wisdom_from_cube,
                push_to_hermespace_world,
            )

            hh = self._hermes_home
            cube_path = self._cube_path or ""
            ents = list(self._cube.read_l1() or []) if self._cube else []
            wisdom = wisdom_from_cube(cube_path, entries=ents)
            write_markdown(hh, cube_wisdom=wisdom)
            events = read_events(hh, limit=30)
            out: dict[str, Any] = {
                "status": "ok",
                "events": events[-20:],
                "wisdom": [{"text": t, "confidence": c} for t, c in wisdom[:10]],
                "markdown": render_markdown(hh, cube_wisdom=wisdom, limit=20)[:4000],
            }
            if args.get("sync_world"):
                out["world"] = push_to_hermespace_world(
                    hermes_home=hh,
                    agent_id=str(args.get("agent_id") or "hermes-agent"),
                    entries=ents,
                )
            return json.dumps(out)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_crystalize(self, args: dict[str, Any]) -> str:
        """Consolidate near-duplicate memories into belief crystals."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        dry = bool(args.get("dry_run") or False)
        try:
            from hermescube.wisdom import crystalize, functional_loop_stats

            stats = crystalize(self._cube, dry_run=dry)
            if not dry and stats.get("crystals"):
                self._prefetch_cache.clear()
                if self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
            ents = list(self._cube.read_l1() or [])
            loop = functional_loop_stats(ents)
            if not dry and stats.get("crystals"):
                try:
                    from hermescube.journey import log_event, write_markdown, wisdom_from_cube

                    log_event(
                        "crystalize",
                        f"Formed {stats.get('crystals')} crystals from "
                        f"{stats.get('candidates')} candidates",
                        hermes_home=self._hermes_home,
                        meta=stats,
                    )
                    cube_path = self._cube_path or ""
                    w = wisdom_from_cube(cube_path) if cube_path else []
                    write_markdown(self._hermes_home, cube_wisdom=w)
                except Exception:
                    pass
            return json.dumps({"status": "crystalized", "stats": stats, "loop": loop})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_replay(self, args: dict[str, Any]) -> str:
        """Offline sleep replay → Engram Net consolidation."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.sleep_replay import sleep_replay

            net = getattr(self, "_engram", None)
            if net is None:
                from hermescube.engram_net import EngramNet, default_path as engram_path

                net = EngramNet(engram_path(self._hermes_home or Path.home() / ".hermes"))
                self._engram = net
                if self._engine is not None:
                    setattr(self._engine, "_engram_net", net)
            stats = sleep_replay(
                self._cube,
                net,
                max_patterns=int(args.get("max_patterns") or 24),
            )
            net.save()
            try:
                from hermescube.journey import log_event

                log_event(
                    "sleep_replay",
                    f"bundles={stats.get('bundles')} patterns={stats.get('patterns_added')}",
                    hermes_home=self._hermes_home,
                    meta=stats,
                )
            except Exception:
                pass
            return json.dumps({"status": "replayed", "stats": stats})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_add(self, args: dict[str, Any]) -> str:
        """Handle hermescube_manage add action."""
        content = args.get("content", "")
        entry_type = args.get("entry_type", "belief")
        outcome = args.get("outcome", "none")

        if not content:
            return json.dumps({"error": "content is required"})

        if entry_type not in ENTRY_TYPES:
            return json.dumps({
                "error": f"Invalid entry_type: {entry_type!r}. "
                         f"Must be one of: {sorted(ENTRY_TYPES.keys())}"
            })
        if outcome not in OUTCOMES:
            return json.dumps({
                "error": f"Invalid outcome: {outcome!r}. "
                         f"Must be one of: {sorted(OUTCOMES.keys())}"
            })

        threats = scan_text(content)
        if any(t.severity == "block" for t in threats):
            return json.dumps({"error": "Content blocked by threat scanning"})

        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})

        entry = self._cube.append(
            entry_type=entry_type,
            description=sanitize_for_storage(content, self._char_limit),
            data={
                "source": "hermescube_manage",
                "session_id": self._session_id,
                "platform": self._platform,
                "trust": 0.72 if entry_type in ("focus", "resolve") else 0.5,
            },
            outcome=outcome,
        )
        closed_info = None
        try:
            from hermescube.journey import log_event

            log_event(
                "manage_add",
                f"[{entry_type}] {content.strip()[:180]}",
                hermes_home=self._hermes_home,
                entry_id=entry.id,
            )
        except Exception:
            pass

        # Prospective: successful resolve closes matching open focus
        if entry_type in ("resolve", "evolution") or (
            entry_type == "landmark" and outcome == "success"
        ):
            try:
                from hermescube.prospective import try_close_on_resolve

                # default outcome none still tries if wording looks done
                closed_info = try_close_on_resolve(self._cube, entry)
                if closed_info.get("closed") and self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
                    self._prefetch_cache.clear()
            except Exception:
                closed_info = None

        out: dict[str, Any] = {
            "status": "added",
            "id": entry.id,
            "type": entry.entry_type,
        }
        if closed_info and closed_info.get("closed"):
            out["prospective"] = closed_info

        # Soft contradiction flags (belief/resolve)
        if (
            self._conflict_detect
            and entry_type in ("belief", "resolve", "trait")
            and not self._should_skip_writes()
        ):
            try:
                from hermescube.conflict import find_conflicts, annotate_conflicts

                ents = list(self._cube.read_l1() or [])
                confs = find_conflicts(content, [e for e in ents if e.id != entry.id])
                if confs:
                    n = annotate_conflicts(self._cube, entry, confs)
                    out["conflicts"] = confs
                    out["conflict_markers"] = n
            except Exception:
                pass

        # Care flag
        if args.get("care") or args.get("critical"):
            try:
                # already written — append care marker linked
                self._cube.append(
                    entry_type=entry_type,
                    description=f"[CARE] {sanitize_for_storage(content, 120)}",
                    data={
                        "care": True,
                        "critical": True,
                        "care_of": entry.id,
                        "source": "hermescube_manage",
                        "trust": 0.9,
                    },
                    outcome="success",
                )
                out["care"] = True
            except Exception:
                pass

        return json.dumps(out)

    def _handle_manage_remove(self, args: dict[str, Any]) -> str:
        """Handle hermescube_manage remove action."""
        entry_id = args.get("entry_id", "")
        if not entry_id:
            return json.dumps({"error": "entry_id is required"})

        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})

        entry = self._cube.read_entry(entry_id)
        if not entry:
            return json.dumps({"error": f"Entry {entry_id} not found"})

        self._cube.append(
            entry_type=entry.entry_type,
            description=f"[SUPERSEDED] {entry.description[:150]}",
            data={
                "supersedes": entry_id,
                "source": "hermescube_manage",
                "session_id": self._session_id,
            },
            outcome="superseded",
        )

        return json.dumps({"status": "superseded", "id": entry_id})

    def _handle_feedback(self, args: dict[str, Any]) -> str:
        """Handle hermescube_feedback tool call."""
        action = args.get("action", "")
        entry_id = args.get("entry_id", "")

        if not entry_id:
            return json.dumps({"error": "entry_id is required"})
        if action not in ("helpful", "unhelpful"):
            return json.dumps({"error": f"Invalid action: {action!r}"})

        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})

        entry = self._cube.read_entry(entry_id)
        if not entry:
            return json.dumps({"error": f"Entry {entry_id} not found"})

        current_trust = entry.data.get("trust", 0.5) if entry.data else 0.5
        # Asymmetric deltas: penalty > reward (holographic pattern)
        delta = _TRUST_HELPFUL_DELTA if action == "helpful" else _TRUST_UNHELPFUL_DELTA
        new_trust = round(max(0.0, min(1.0, current_trust + delta)), 2)

        updated_data = dict(entry.data) if entry.data else {}
        updated_data["trust"] = new_trust
        updated_data["feedback_count"] = updated_data.get("feedback_count", 0) + 1

        self._cube.append(
            entry_type=entry.entry_type,
            description=entry.description,
            data={
                **updated_data,
                "supersedes": entry_id,
                "source": "hermescube_feedback",
                "session_id": self._session_id,
            },
            outcome="superseded",
        )

        # Colony: helpful = reinforce pheromone trail (ant food found)
        if action == "helpful":
            if self._void is not None:
                try:
                    self._void.reinforce(entry, amount=0.5)
                except Exception:
                    pass
            elif self._colony is not None:
                try:
                    ents = (entry.data or {}).get("entities") if entry.data else None
                    if not ents:
                        from hermescube import mirror as mirror_mod
                        ents = mirror_mod.extract_entities(entry.description or "")
                    if ents:
                        self._colony.deposit(list(ents), amount=0.5)
                        self._colony.register_dance(entry)
                        self._colony.save()
                        self._colony.mark_dirty()
                        if self._paths:
                            self._colony.maybe_write_markdown_board(
                                self._paths.colony_board, force=True
                            )
                except Exception:
                    pass

        # Yield Gradient: query-local payoff (closed learning loop)
        # Prefer last prefetch query so boost is conditioned on *how* it was asked
        try:
            q = (
                args.get("query")
                or getattr(self, "_last_prefetch_query", None)
                or (entry.description or "")[:120]
            )
            yg = getattr(self, "_yield", None)
            if yg is not None and q:
                yg.record(str(q), entry_id, helpful=(action == "helpful"))
        except Exception:
            pass

        # Engram Net: strengthen/weaken co-activation among judged set
        try:
            net = getattr(self, "_engram", None)
            if net is not None:
                cohort = args.get("cohort_ids") or args.get("entry_ids")
                ids = [entry_id]
                if isinstance(cohort, list):
                    ids.extend(str(x) for x in cohort if x)
                elif getattr(self, "_last_prefetch_ids", None):
                    ids.extend(str(x) for x in self._last_prefetch_ids[:12])
                net.learn_feedback(ids, helpful=(action == "helpful"))
                net.save()
        except Exception:
            pass

        try:
            from hermescube.journey import log_event

            log_event(
                "feedback_" + action,
                (entry.description or "")[:180],
                hermes_home=self._hermes_home,
                entry_id=entry_id,
            )
        except Exception:
            pass

        return json.dumps({
            "status": "rated",
            "id": entry_id,
            "action": action,
            "trust": new_trust,
        })
