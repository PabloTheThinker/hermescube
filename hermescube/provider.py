"""CubeMemoryProvider — HermesAgent MemoryProvider backed by HermesCube.

Implements the Hermes ``MemoryProvider`` ABC (when available) for
integration with HermesAgent's memory system. Stores conversation turns
in a .cube archive with HAR-powered semantic retrieval.

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
from abc import ABC
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hermescube.cube import OUTCOMES, ENTRY_TYPES, CubeFile, CubeEntry
from hermescube.har import HARQueryEngine
from hermescube import hrr
from hermescube.threats import scan_text, sanitize_for_storage

logger = logging.getLogger(__name__)

try:
    from agent.memory_provider import MemoryProvider as _HermesMemoryProvider
except Exception:  # standalone / tests without Hermes runtime
    class _HermesMemoryProvider(ABC):
        """Local stand-in when Hermes Agent is not importable."""
        pass

# Pyright: Hermes import may be untyped / missing; keep a stable base symbol.
_ProviderBase = _HermesMemoryProvider

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

# Hermes context_compressor merge-into-tail markers (algorithm port; no import required)
_MERGED_PRIOR_CONTEXT_HEADER = "[PRIOR CONTEXT — for reference only; not a new message]"
_MERGED_SUMMARY_DELIMITER = "[END OF PRIOR CONTEXT — COMPACTION SUMMARY BELOW]"

def _user_content_for_extract(msg: dict[str, Any]) -> str | None:
    """Return harvestable user text, or None if the row is compressor prose.

    Merge-into-tail messages wrap real prior content BEFORE the delimiter and
    the generated handoff summary AFTER it. Drop only the summary suffix;
    skip pure compaction summary messages entirely (holographic #57690).
    """
    content = msg.get("content", "")
    if not isinstance(content, str):
        return None
    if _MERGED_SUMMARY_DELIMITER in content:
        pre = content.split(_MERGED_SUMMARY_DELIMITER, 1)[0]
        if pre.startswith(_MERGED_PRIOR_CONTEXT_HEADER):
            pre = pre[len(_MERGED_PRIOR_CONTEXT_HEADER) :]
        pre = pre.strip()
        return pre or None
    try:
        from agent.context_compressor import is_compaction_summary_message

        if is_compaction_summary_message(msg):
            return None
    except Exception:
        pass
    stripped = content.lstrip()
    if stripped.startswith(
        (
            "[Context compression",
            "[Compressed",
            "Summary of conversation",
            "Summary:",
            "[COMPACTION",
        )
    ):
        return None
    return content

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

    def flush(self, timeout: float = 5.0) -> bool:
        """Drain background work without hanging forever.

        Honors ``timeout``: waits up to that many seconds for in-flight
        work, then abandons the wait (daemon workers may still finish).
        Never cancels pending futures — dropping them silently lost
        memories (see TestSyncQueueRegression).

        Returns True if the queue drained within ``timeout``.
        """
        with self._lock:
            if self._executor is None:
                return True
            executor = self._executor
            self._executor = None

        done = threading.Event()

        def _shutdown() -> None:
            try:
                executor.shutdown(wait=True, cancel_futures=False)
            except Exception as e:
                logger.warning("sync queue shutdown error: %s", e)
            finally:
                done.set()

        t = threading.Thread(
            target=_shutdown, name="hermescube_flush", daemon=True
        )
        t.start()
        if done.wait(timeout=max(0.1, float(timeout))):
            return True
        logger.warning(
            "sync queue flush timed out after %.1fs — abandoning wait "
            "(in-flight work may still finish on daemon threads)",
            timeout,
        )
        try:
            executor.shutdown(wait=False, cancel_futures=False)
        except Exception:
            pass
        return False

# ── Provider ─────────────────────────────────────────────────────────

class CubeMemoryProvider(_ProviderBase):  # type: ignore[misc,valid-type]
    """HermesAgent MemoryProvider backed by a HermesCube archive.

    Stores conversation turns as cube entries with HAR-powered retrieval.
    Subclasses Hermes ``MemoryProvider`` when the agent package is present.

    Tools registered:
        hermescube_search   — semantic search over past conversations
        hermescube_manage   — add/remove memories programmatically
        hermescube_feedback — rate a memory entry (trains trust)
        hermescube_probe    — entity-focused graph probe

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
        self._memory_policy = "auto-safe"  # review-first | auto-safe | off
        self._auto_bootstrap = True  # seed MEMORY.md + skills on empty warehouse
        self._last_bootstrap: dict[str, Any] | None = None
        self._query_rewrite = False
        # Cadence knobs (Nous-style cost control — local)
        self._peer_card_cadence_s = 3600.0  # rebuild peer card at most hourly
        self._session_digest_enabled = True
        self._observe_on_session_end = True
        self._replay_on_session_end = True
        self._conflict_detect = True
        self._living_pulse_on_session_end = True

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
        self._parent_session_id: str = ""
        self._branch_id: str = "main"
        self._state_lock = threading.RLock()
        # Hive nexus (optional shared collective)
        self._hive_path: str = ""
        self._hive_on_session_end: bool = False
        # Grounded self-evolution harness
        self._witness_detect: bool = True
        # Peer interview during pilgrimage (interview-me at the hive)
        self._interview_on_pilgrimage: bool = False

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
        self._cubewave = None
        self._chamber = ""  # session soft chamber affinity for scoped prefetch
        self._last_prefetch_query = ""
        self._last_prefetch_ids: list[str] = []
        self._paths = None

        # Turn tracking
        self._turn_count: int = 0
        self._turns_since_memory: int = 0
        self._nudge_prefetch_line: bool = False
        self._user_id: str = ""
        self._user_id_alt: str = ""
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
            user_id (str):           Gateway platform user id
            user_id_alt (str):       Alternate stable platform user id
            parent_session_id (str): Parent session for subagents
        """
        self._hermes_home = kwargs.get("hermes_home", "")
        self._session_id = session_id
        self._platform = kwargs.get("platform", "cli")
        self._agent_context = kwargs.get("agent_context", "primary")
        self._agent_identity = kwargs.get("agent_identity", "")
        self._agent_workspace = kwargs.get("agent_workspace", "")
        self._skip_memory = kwargs.get("skip_memory", False)
        self._parent_session_id = str(kwargs.get("parent_session_id") or "")
        self._user_id = str(kwargs.get("user_id") or "").strip()
        self._user_id_alt = str(kwargs.get("user_id_alt") or "").strip()
        # Hermes already passes a profile-scoped hermes_home. Keep one
        # cube per home; subagent traces use branch_id metadata instead.
        self._branch_id = "main"
        if self._agent_context == "subagent" and session_id:
            from hermescube.branches import branch_id_for_child

            self._branch_id = branch_id_for_child(
                session_id, parent_session_id=self._parent_session_id
            )

        # Load plugin config from this session's hermes_home
        plugin_config = _load_plugin_config(self._hermes_home or None)
        if plugin_config:
            self._auto_extract = _coerce_bool(
                plugin_config.get("auto_extract"), self._auto_extract
            )
            try:
                from hermescube.memory_gate import normalize_policy

                self._memory_policy = normalize_policy(
                    str(plugin_config.get("memory_policy") or self._memory_policy)
                )
            except Exception:
                self._memory_policy = "auto-safe"
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
            self._living_pulse_on_session_end = _coerce_bool(
                plugin_config.get("living_pulse_on_session_end"),
                self._living_pulse_on_session_end,
            )
            self._hive_path = str(plugin_config.get("hive_path") or "").strip()
            self._hive_on_session_end = _coerce_bool(
                plugin_config.get("hive_on_session_end"), False
            )
            self._witness_detect = _coerce_bool(
                plugin_config.get("witness_detect"), True
            )
            self._interview_on_pilgrimage = _coerce_bool(
                plugin_config.get("interview_on_pilgrimage"), False
            )
            self._auto_bootstrap = _coerce_bool(
                plugin_config.get("auto_bootstrap"), self._auto_bootstrap
            )
        else:
            self._query_rewrite = _query_rewrite_enabled(None)
            self._hive_path = os.environ.get("HERMESCUBE_HIVE", "").strip()
            self._hive_on_session_end = False

        # Framework path housing
        from hermescube.framework.paths import (
            migrate_legacy_sidecars,
            resolve_cube_paths,
            should_nest_profiles,
        )
        from hermescube.framework.void import CubeVoid
        from hermescube.colony import ColonyGraph

        # Nest sidecars when both identity and workspace are set so two
        # workspaces under one HERMES_HOME do not share engram/relations.
        self._nest_profiles = should_nest_profiles(
            self._agent_identity, self._agent_workspace
        )
        self._paths = resolve_cube_paths(
            self._hermes_home or None,
            agent_identity=self._agent_identity or "",
            agent_workspace=self._agent_workspace or "",
            nest_profiles=self._nest_profiles,
        )
        self._paths.ensure()
        if self._nest_profiles:
            try:
                migrate_legacy_sidecars(self._paths)
            except Exception as e:
                logger.debug("sidecar migrate: %s", e)
        self._vault = (self._agent_workspace or self._agent_identity or "").strip()
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
        if getattr(self, "_vault", ""):
            setattr(self._engine, "_active_vault", self._vault)
        if getattr(self, "_user_id", ""):
            setattr(self._engine, "_active_user_id", self._user_id)
            if getattr(self, "_user_id_alt", ""):
                setattr(self._engine, "_active_user_id_alt", self._user_id_alt)

        # Living genealogy — fresh cubes start at 0.0.0 and grow with experience
        try:
            from hermescube.genealogy import ensure_genesis
            from hermescube import __version__ as _pkg_v

            ensure_genesis(
                self._hermes_home or None,
                agent_id=self._agent_identity or "hermes",
                package_version=_pkg_v,
            )
            self._refresh_maturity()
        except Exception as e:
            logger.debug("genealogy genesis skipped: %s", e)

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

            self._yield = YieldGradient(self._paths.yield_gradient)
            setattr(self._engine, "_yield_gradient", self._yield)
        except Exception as e:
            logger.debug("yield gradient skipped: %s", e)
            self._yield = None

        # Engram Net — Hebbian + Hopfield-style associative field (Cube-native neural)
        try:
            from hermescube.engram_net import EngramNet, default_path as engram_path

            self._engram = EngramNet(self._paths.engram)
            setattr(self._engine, "_engram_net", self._engram)
        except Exception as e:
            logger.debug("engram net skipped: %s", e)
            self._engram = None

        # Cubewave — ELM/LMS brainwave field inside Cuboasis (pocket-dimension neural)
        try:
            from hermescube.cubewave import Cubewave

            self._cubewave = Cubewave(self._paths.cubewave)
            setattr(self._engine, "_cubewave", self._cubewave)
        except Exception as e:
            logger.debug("cubewave skipped: %s", e)
            self._cubewave = None

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

        # First-run: import hot MEMORY.md/USER.md + install Cube skills so the
        # connecting agent can search immediately (idempotent; skip for subagents).
        if (
            getattr(self, "_auto_bootstrap", True)
            and self._hermes_home
            and not self._should_skip_writes()
            and self._agent_context == "primary"
        ):
            try:
                from hermescube.bootstrap import needs_auto_bootstrap, run_bootstrap

                if needs_auto_bootstrap(self._cube, self._hermes_home):
                    self._last_bootstrap = run_bootstrap(
                        self._cube,
                        self._hermes_home,
                        mode="all",
                        vault=getattr(self, "_vault", "") or "",
                        session_id=self._session_id or "",
                    )
                    if self._engine:
                        try:
                            self._engine.invalidate_cache()
                        except Exception:
                            pass
                    self._refresh_snapshot()
                    logger.info(
                        "HermesCube auto-bootstrap: imported=%s skills=%s",
                        (self._last_bootstrap.get("import") or {}).get("imported"),
                        (self._last_bootstrap.get("skills") or {}).get("installed"),
                    )
            except Exception as e:
                logger.debug("auto-bootstrap skipped: %s", e)

    def _refresh_maturity(self) -> None:
        """Push living genealogy era/strength onto the HAR engine for ranking."""
        if not self._engine or not self._hermes_home:
            return
        try:
            from hermescube.genealogy import load_genealogy

            g = load_genealogy(self._hermes_home)
            setattr(
                self._engine,
                "_maturity",
                {
                    "era": g.get("era") or "eden",
                    "strength": float(g.get("strength") or 0),
                    "version": g.get("version") or "0.0.0",
                },
            )
        except Exception:
            pass

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
            wave = getattr(self, "_cubewave", None)
            if wave is not None:
                wave.save()
            yg = getattr(self, "_yield", None)
            if yg is not None and hasattr(yg, "save"):
                yg.save()
        except Exception as e:
            logger.debug("shutdown engram/cubewave/yield save failed: %s", e)

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
                "key": "memory_policy",
                "description": (
                    "Cuboasis write policy for auto-extract: "
                    "review-first (candidates), auto-safe (safe→durable), off"
                ),
                "required": False,
                "default": "auto-safe",
                "choices": ["review-first", "auto-safe", "off"],
            },
            {
                "key": "auto_bootstrap",
                "description": (
                    "On first connect to an empty warehouse: import MEMORY.md/"
                    "USER.md and install HermesCube skills automatically"
                ),
                "required": False,
                "default": "true",
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
            {
                "key": "living_pulse_on_session_end",
                "description": "Run multi-chamber living pulse on session_end (catalog/connect/peer)",
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
        """Return OpenAI function-calling tool schemas.

        Subagents get read-only recall tools: search, probe, feedback.
        Durable writes, hive, and HQ operations belong to the parent —
        work flows upward; privilege does not flow down.
        """
        schemas = self._all_tool_schemas()
        if self._agent_context == "subagent":
            allowed = {"hermescube_search", "hermescube_probe", "hermescube_feedback"}
            return [s for s in schemas if s.get("name") in allowed]
        return schemas

    def _all_tool_schemas(self) -> list[dict[str, Any]]:
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
                    "Operate the HermesCube warehouse. First session: action=bootstrap "
                    "mode=all to import MEMORY.md/USER.md and install Cube skills. "
                    "Daily: add durable facts; triage/crystalize/merge to compound; "
                    "cuboasis for review-first governance."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "bootstrap",
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
                                "pulse",
                                "hive",
                                "witness",
                                "harness",
                                "hq",
                                "interview",
                                "growth",
                                "curate",
                                "triage",
                                "merge",
                                "relations",
                                "space",
                                "connect",
                                "progress",
                                "cuboasis",
                                "nexus",
                                "dream",
                            ],
                            "description": (
                                "bootstrap (import hot memories + install skills) · "
                                "warehouse ops + living pulse + consent + peer + hive "
                                "+ witness + harness + hq + interview + growth + curate "
                                "+ triage / merge / relations "
                                "+ space / connect / progress / cuboasis · "
                                "dream (solo soul dream / hive circle together)"
                            ),
                        },
                        "circle_action": {
                            "type": "string",
                            "enum": [
                                "open",
                                "join",
                                "signal",
                                "score",
                                "close",
                                "draw",
                                "list",
                                "status",
                                "dialogue",
                                "skim",
                            ],
                            "description": (
                                "For action=dream mode=circle: open/join/signal/"
                                "dialogue/skim/score/close/draw/list/status"
                            ),
                        },
                        "circle_id": {
                            "type": "string",
                            "description": "Dream circle id (action=dream circle ops)",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Dream circle topic (mode=circle:open)",
                        },
                        "interview_action": {
                            "type": "string",
                            "enum": ["dialogue", "list", "mint"],
                            "description": (
                                "For action=interview: dialogue (interview a peer), "
                                "list past interviews, mint a skill draft from a brief"
                            ),
                        },
                        "hq_action": {
                            "type": "string",
                            "enum": [
                                "route", "charter", "charters", "claim",
                                "handoff", "complete", "handoffs",
                                "verify", "baseline",
                            ],
                            "description": (
                                "For action=hq: route a task to its lane owner, "
                                "register/list charters, claim task ownership, "
                                "handoff (route + distilled context packet + ledger), "
                                "complete a handoff, review handoffs, verify fleet, "
                                "freeze/verify baseline"
                            ),
                        },
                        "hive_action": {
                            "type": "string",
                            "enum": ["status", "pilgrimage", "draw", "offer"],
                            "description": "For action=hive: status / pilgrimage / draw / offer",
                        },
                        "harness_action": {
                            "type": "string",
                            "enum": ["status", "critic", "verify", "gardener"],
                            "description": "For action=harness: status / critic / verify / gardener",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "For action=witness: friction severity",
                        },
                        "focus": {
                            "type": "string",
                            "description": "For hive draw/pilgrimage: focus query to pull relevant collective wisdom",
                        },
                        "agent": {
                            "type": "string",
                            "description": (
                                "Peer agent id — for interview dialogue (subject) "
                                "or hq charter"
                            ),
                        },
                        "mode": {
                            "type": "string",
                            "enum": [
                                "clarify", "discover", "brief",
                                "decision", "retrospective", "profile",
                            ],
                            "description": "For action=interview: interview-me mode",
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
            if self._agent_context == "subagent":
                return json.dumps(
                    {
                        "error": "subagent boundary: durable memory writes flow "
                        "upward — return your findings to the parent agent"
                    }
                )
            return self._handle_manage(args)
        elif tool_name == "hermescube_feedback":
            return self._handle_feedback(args)
        elif tool_name == "hermescube_probe":
            return self._handle_probe(args)
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    # ── MemoryProvider ABC: system prompt ──────────────────────────

    def system_prompt_block(self) -> str:
        """Instant operating manual — implemented in ``agent_manual``."""
        from hermescube.agent_manual import build_system_prompt_block

        return build_system_prompt_block(self)

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

        # Apply session chamber soft-filter to HAR for this recall
        chamber = str(getattr(self, "_chamber", "") or "").strip()
        if self._engine is not None:
            setattr(self._engine, "_chamber_filter", chamber)

        vault_key = getattr(self, "_vault", "") or ""
        uid_key = getattr(self, "_user_id", "") or ""
        cache_key = hashlib.md5(
            f"{retrieval_query}|ch:{chamber}|v:{vault_key}|u:{uid_key}".encode()
        ).hexdigest()
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

        if results:
            try:
                self._last_prefetch_ids = [
                    str(getattr(e, "id", "") or "")
                    for e, _ in results
                    if getattr(e, "id", None)
                ]
            except Exception:
                self._last_prefetch_ids = []
            # periodic engram / cubewave flush
            try:
                if self._turn_count % 5 == 0:
                    net = getattr(self, "_engram", None)
                    if net is not None:
                        net.save()
                    wave = getattr(self, "_cubewave", None)
                    if wave is not None:
                        wave.save()
            except Exception:
                pass
            if self._void is not None:
                body = self._void.format_prefetch(results)
            else:
                lines = ["[Relevant memories from past sessions:]"]
                for entry, _score in results[:5]:
                    ts = entry.timestamp[:10] if entry.timestamp else "unknown"
                    lines.append(f"- [{ts}] [{entry.entry_type}] {entry.description}")
                body = "\n".join(lines)
        else:
            self._last_prefetch_ids = []
            body = ""
        rel_block = self._relational_prefetch_assist(retrieval_query, results or [])
        parts: list[str] = []
        if body:
            parts.append(body)
        if rel_block:
            parts.append(rel_block)
        if getattr(self, "_nudge_prefetch_line", False):
            parts.append(
                "[Memory review due: hermescube_manage triage → crystalize / relations]"
            )
            self._nudge_prefetch_line = False
        return "\n\n".join(parts)

    @staticmethod
    def _query_looks_relational(query: str) -> bool:
        q = (query or "").lower()
        cues = (
            "who ",
            "who's",
            "whose ",
            "owns ",
            "owned ",
            "related",
            "relation",
            "belongs",
            "responsible",
            "depends on",
            "linked to",
        )
        return any(c in q for c in cues)

    def _relational_prefetch_assist(
        self,
        query: str,
        results: list,
    ) -> str:
        """Append SPO relations when the query looks relational."""
        if not self._hermes_home or not self._query_looks_relational(query):
            return ""
        try:
            from hermescube.mirror import extract_entities
            from hermescube.relations import RelationStore, format_for_prompt

            store = self._relation_store()
            entities = extract_entities(query, max_entities=4)
            for entry, _ in (results or [])[:4]:
                data = getattr(entry, "data", None) or {}
                for ent in data.get("entities") or []:
                    if str(ent) not in entities:
                        entities.append(str(ent))
                if len(entities) >= 6:
                    break
            hits = []
            seen: set[str] = set()
            for ent in entities:
                for r in store.query(str(ent), limit=3):
                    if r.relation_id in seen:
                        continue
                    seen.add(r.relation_id)
                    hits.append(r)
                if len(hits) >= 6:
                    break
            return format_for_prompt(hits, limit=6)
        except Exception:
            return ""

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
        """Persist a completed turn (idempotent event + optional tool trajectory).

        When called directly, the cubelog append is synchronous. Under Hermes
        Agent, ``MemoryManager`` may invoke this on a background worker after
        the user-visible turn returns — Hermes ``state.db`` remains the
        primary transcript durability; Cube ingestion is idempotent and
        reconciles via content hashes.
        """
        if not self._cube or self._should_skip_writes():
            return

        user_clean = sanitize_for_storage(user_content, self._char_limit)
        assistant_clean = sanitize_for_storage(assistant_content, self._char_limit)

        if not user_clean and not assistant_clean:
            return

        # Witness detection: real friction feeds the grounded-evolution gate
        if self._witness_detect and self._hermes_home:
            try:
                from hermescube.self_evolution import detect_friction, record_witness

                friction = detect_friction(user_clean, assistant_clean)
                if friction:
                    record_witness(
                        self._hermes_home,
                        friction["quote"],
                        severity=friction["severity"],
                        kind=friction["kind"],
                        session_id=session_id or self._session_id,
                        source="sync_turn",
                    )
            except Exception:
                pass

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

        entry_type = self._classify_turn(user_clean, assistant_clean)
        desc = user_clean[:200] if user_clean else "(empty turn)"
        uq = (user_clean or "").strip()
        aq = (assistant_clean or "").strip()
        is_question = uq.endswith("?") or uq.lower().startswith(
            ("who ", "what ", "where ", "when ", "why ", "how ", "can ", "should ")
        )
        extra: dict[str, Any] = {"timestamp": time.time()}
        if is_question and aq:
            desc = aq[:200]
            extra["question"] = uq[:200]
            extra["indexed_from"] = "assistant"
            extra["trust"] = 0.45
        else:
            extra["trust"] = 0.55
        vault = getattr(self, "_vault", "") or ""
        if vault:
            extra["vault"] = vault
            if self._agent_workspace:
                extra["topic"] = str(self._agent_workspace)[:80]
        uid = getattr(self, "_user_id", "") or ""
        if uid:
            extra["user_id"] = uid
            alt = getattr(self, "_user_id_alt", "") or ""
            if alt:
                extra["user_id_alt"] = alt

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

        try:
            from hermescube.ingest import ingest_turn

            result = ingest_turn(
                self._cube,
                user_content=user_clean,
                assistant_content=assistant_clean,
                session_id=session_id or self._session_id,
                hermes_home=self._hermes_home or None,
                platform=self._platform,
                agent_context=self._agent_context,
                agent_identity=self._agent_identity,
                parent_session_id=self._parent_session_id,
                branch_id=self._branch_id,
                turn=self._turn_count,
                messages=messages,
                char_limit=self._char_limit,
                entry_type=entry_type,
                outcome=outcome,
                description=desc,
                extra_data=extra,
            )
            if result.get("skipped") == "duplicate":
                return
            if not result.get("ok"):
                if result.get("skipped") == "threat":
                    return
                logger.error("sync_turn ingest failed: %s", result)
                return
            # Keep β attention warm on durable appends
            if self._engine and result.get("entry_id"):
                try:
                    ents = self._cube.read_l1() or []
                    added = next(
                        (e for e in reversed(ents) if e.id == result.get("entry_id")),
                        None,
                    )
                    if added is not None and added.vector is not None:
                        self._engine.update_beta_on_append(added.vector)
                except Exception:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
            for fet, fdesc in fact_lines:
                try:
                    from hermescube.events import event_to_entry_data, make_event
                    from hermescube.memory_gate import (
                        capture_candidate,
                        gate_text_for_write,
                    )

                    gated = gate_text_for_write(
                        fdesc,
                        policy=getattr(self, "_memory_policy", "auto-safe") or "auto-safe",
                        explicit=False,
                        tags=[vault] if vault else None,
                    )
                    write_path = gated.get("path") or "skip"
                    if write_path in ("skip", "block"):
                        continue
                    if write_path == "candidate":
                        capture_candidate(
                            self._hermes_home,
                            fdesc,
                            record_type=fet or "fact",
                            source="sync_extract",
                            entry_type=fet or "belief",
                            session_id=session_id or self._session_id,
                            tags=[vault] if vault else None,
                            **self._path_kw(),
                        )
                        continue
                    fev = make_event(
                        "claim",
                        session_id=session_id or self._session_id,
                        platform=self._platform,
                        agent_context=self._agent_context,
                        agent_identity=self._agent_identity,
                        source="extract",
                        branch_id=self._branch_id,
                        confidence=0.7,
                        verification="observed",
                        payload={"text": fdesc, "claim_type": fet},
                        parent_event_ids=[result.get("event_id") or ""],
                    )
                    fdata = event_to_entry_data(
                        fev,
                        source="extract",
                        trust=0.7,
                        durable=True,
                        session_id=session_id or self._session_id,
                    )
                    if vault:
                        fdata["vault"] = vault
                    if uid:
                        fdata["user_id"] = uid
                        alt = getattr(self, "_user_id_alt", "") or ""
                        if alt:
                            fdata["user_id_alt"] = alt
                    self._cube.append(
                        entry_type=fet,
                        description=fdesc,
                        data=fdata,
                        outcome="none",
                    )
                except Exception:
                    pass
            if self._engine:
                try:
                    self._engine.invalidate_cache()
                except Exception:
                    pass
            with self._state_lock:
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
                    from hermescube.consolidate import run_branched_evolve

                    run_branched_evolve(self, label="auto_evolve")
                    self._entries_since_evolve = 0
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
        """True when consolidate nudge is due (peek — does not reset counter)."""
        if self._memory_nudge_interval <= 0:
            return False
        return self._turns_since_memory >= self._memory_nudge_interval

    def _take_memory_review_nudge(self) -> bool:
        """Emit consolidate nudge once; reset turn counter only when taken."""
        if not self.should_review_memory():
            return False
        self._turns_since_memory = 0
        return True

    def on_session_end(self, messages: list[dict[str, Any]]) -> None:
        """Session complete — consolidation runs on the sync queue.

        Heavy operations run on the sync queue; the queue is flushed
        before return so Hermes ``commit_session_boundary_async`` can
        safely run ``on_session_switch`` next without misattribution.
        """
        if not self._engine or not self._cube:
            return

        from hermescube.session_end import capture_session_end_ctx, run_session_end_work

        ctx = capture_session_end_ctx(self)
        messages_snap = list(messages or [])

        def _session_end_work() -> None:
            run_session_end_work(self, ctx, messages_snap)

        self._sync_queue.submit(_session_end_work)
        # Hermes MemoryManager serializes session_end → session_switch;
        # flush so closure finishes before switch can rebind identity.
        try:
            flush_ok = self._sync_queue.flush(timeout=30.0)
            setattr(self, "_last_session_end_flush_ok", bool(flush_ok))
        except Exception as e:
            logger.debug("session_end flush: %s", e)
            setattr(self, "_last_session_end_flush_ok", False)

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
        if parent_session_id:
            self._parent_session_id = str(parent_session_id)
        if kwargs.get("user_id") is not None:
            self._user_id = str(kwargs.get("user_id") or "").strip()
            if self._engine is not None:
                setattr(self._engine, "_active_user_id", self._user_id)
        if kwargs.get("user_id_alt") is not None:
            self._user_id_alt = str(kwargs.get("user_id_alt") or "").strip()
            if self._engine is not None:
                setattr(self._engine, "_active_user_id_alt", self._user_id_alt)

        if reset:
            self._turn_count = 0
            self._turns_since_memory = 0
            self._nudge_prefetch_line = False
            self._prefetch_cache.clear()

        if rewound:
            self._prefetch_cache.clear()
            # Invalidate the cube + engine caches — assigning
            # self._entries_cache creates a dead attribute on the provider.
            if self._cube is not None:
                self._cube._entries_cache = None
            if self._engine is not None:
                self._engine.invalidate_cache()

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
            if role == "user":
                content = _user_content_for_extract(msg)
            else:
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
        """Mirror built-in MEMORY.md / USER.md writes with temporal supersession.

        Hermes keeps hot MEMORY.md; Cube is the larger durable archive.
        ``replace`` / ``remove`` close prior mirrored facts using
        ``metadata['old_text']`` when Hermes supplies it.
        """
        if not self._cube or self._should_skip_writes():
            return

        write_meta = dict(metadata or {})
        old_text = str(write_meta.get("old_text") or "").strip()
        entry_type = "trait" if target == "user" else "belief"
        extension = "MEMORY.md" if target == "memory" else "USER.md"

        def _supersede_old(reason: str) -> None:
            if not old_text:
                return
            try:
                from hermescube.claims import make_claim, claim_to_entry_data
                from hermescube.events import event_to_entry_data, make_event

                needle = sanitize_for_storage(old_text, self._char_limit)
                # Append a supersession tombstone (append-only archive)
                ev = make_event(
                    "memory_write",
                    session_id=self._session_id,
                    platform=self._platform,
                    agent_context=self._agent_context,
                    agent_identity=self._agent_identity,
                    actor="user",
                    source=f"builtin_{target}",
                    branch_id="main",
                    confidence=0.9,
                    verification="user_authored",
                    payload={"action": action, "old_text": needle, "reason": reason},
                    valid_to=time.time(),
                )
                claim = make_claim(
                    needle,
                    claim_type=entry_type,
                    evidence_event_ids=[ev.event_id],
                    confidence=0.9,
                    verification="user_authored",
                    origin="user",
                    meta={"status": "superseded", "reason": reason},
                )
                claim.status = "superseded"
                claim.valid_to = time.time()
                self._cube.append(
                    entry_type=entry_type,
                    description=f"[SUPERSEDED] {needle[:180]}",
                    data=claim_to_entry_data(
                        claim,
                        **event_to_entry_data(
                            ev,
                            source=f"builtin_{target}",
                            mirror=True,
                            durable=True,
                            trust=0.9,
                            extension_of=extension,
                            provenance=write_meta,
                            action=action,
                            superseded=True,
                        ),
                    ),
                    outcome="superseded",
                )
            except Exception as e:
                logger.debug("supersede old memory failed: %s", e)

        if action == "remove":
            _supersede_old("remove")
            if self._engine:
                self._engine.invalidate_cache()
            with self._state_lock:
                self._prefetch_cache.clear()
            return

        if action in ("add", "replace") and content:
            threats = scan_text(content)
            if any(t.severity == "block" for t in threats):
                return

            safe_content = sanitize_for_storage(content, self._char_limit)
            if action == "replace":
                _supersede_old("replace")
            try:
                from hermescube.claims import make_claim, claim_to_entry_data
                from hermescube.events import event_to_entry_data, make_event

                ev = make_event(
                    "memory_write",
                    session_id=self._session_id,
                    platform=self._platform,
                    agent_context=self._agent_context,
                    agent_identity=self._agent_identity,
                    actor="user",
                    source=f"builtin_{target}",
                    branch_id="main",
                    confidence=0.85,
                    verification="user_authored",
                    payload={"action": action, "text": safe_content},
                )
                claim = make_claim(
                    safe_content,
                    claim_type=entry_type,
                    evidence_event_ids=[ev.event_id],
                    confidence=0.85,
                    verification="user_authored",
                    origin="user",
                )
                self._cube.append(
                    entry_type=entry_type,
                    description=safe_content,
                    data=claim_to_entry_data(
                        claim,
                        **event_to_entry_data(
                            ev,
                            source=f"builtin_{target}",
                            mirror=True,
                            durable=True,
                            trust=0.85,
                            extension_of=extension,
                            provenance=write_meta,
                            action=action,
                        ),
                    ),
                )
                # Cuboasis: durable claim → SPO relation store
                try:
                    from hermescube.cuboasis import bridge_claim_to_relation

                    store = self._relation_store() if self._hermes_home else None
                    if store is not None:
                        bridge_claim_to_relation(claim, store)
                except Exception as bridge_err:
                    logger.debug("claim→SPO bridge skip: %s", bridge_err)
                if self._engine:
                    self._engine.invalidate_cache()
                with self._state_lock:
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
        """Subagent completion — branch-tagged observation + verified promote."""
        if not self._cube or self._should_skip_writes():
            return

        cube = self._cube
        hermes_home = self._hermes_home
        parent_session_id = self._session_id
        platform = self._platform
        agent_identity = self._agent_identity
        char_limit = self._char_limit
        hive_root = getattr(self, "_hive_path", "")

        def _do_delegation() -> None:
            # HQ handoff ledger: the delegation becomes fleet history
            if hive_root:
                try:
                    from hermescube.hq import record_handoff

                    record_handoff(
                        hive_root,
                        from_agent=agent_identity or "hermes",
                        to_agent=f"subagent:{child_session_id or 'anon'}",
                        task=task,
                        status="completed" if result else "failed",
                    )
                except Exception:
                    pass
            try:
                from hermescube.branches import record_delegation_branch

                record_delegation_branch(
                    cube,
                    hermes_home=hermes_home or Path.home() / ".hermes",
                    task=task,
                    result=result,
                    child_session_id=child_session_id,
                    parent_session_id=parent_session_id,
                    platform=platform,
                    agent_identity=agent_identity,
                    char_limit=char_limit,
                    promote_success=True,
                )
            except Exception as e:
                logger.warning("delegation branch record failed: %s", e)
            if result:
                try:
                    from hermescube.trajectory import observe_delegation

                    observe_delegation(
                        cube,
                        task,
                        result,
                        hermes_home=hermes_home,
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
        Compaction-safe: harvest pre-delimiter user text; never store
        compressor handoff prose (Hermes holographic #57690 algorithm).

        Cuboasis memory_policy gates durable writes:
          review-first → candidates; auto-safe → durable when safe;
          blocked/needs_review → candidate queue.
        """
        if not self._cube:
            return

        from hermescube.memory_gate import (
            capture_candidate,
            decide_write_path,
            enrich_entry_data,
            memory_safety,
        )

        policy = getattr(self, "_memory_policy", "auto-safe")
        extracted = 0
        queued = 0
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = _user_content_for_extract(msg)
            if not isinstance(content, str) or len(content) < 10:
                continue

            for category, pattern in _AUTO_EXTRACT_PATTERNS:
                m = pattern.search(content)
                if m:
                    try:
                        text = sanitize_for_storage(content[:400], self._char_limit)
                        threats = scan_text(text)
                        if any(t.severity == "block" for t in threats):
                            break
                        safety = memory_safety(text, text, tags=[category])
                        path = decide_write_path(safety, policy=policy, explicit=False)
                        if path == "skip":
                            break
                        if path in ("candidate", "block"):
                            capture_candidate(
                                self._hermes_home,
                                text,
                                record_type="fact" if category != "user_pref" else "preference",
                                source="auto_extract",
                                evidence_state="prepared_not_observed",
                                tags=[category],
                                session_id=self._session_id,
                                entry_type="belief" if category != "user_pref" else "trait",
                                **self._path_kw(),
                            )
                            queued += 1
                            break
                        # durable
                        self._cube.append(
                            entry_type="belief" if category != "user_pref" else "trait",
                            description=text,
                            data=enrich_entry_data(
                                {
                                    "category": category,
                                    "source": "auto_extract",
                                    "session_id": self._session_id,
                                    "durable": True,
                                    "verification": "observed",
                                    **(
                                        {"user_id": self._user_id}
                                        if getattr(self, "_user_id", "")
                                        else {}
                                    ),
                                    **(
                                        {"vault": self._vault}
                                        if getattr(self, "_vault", "")
                                        else {}
                                    ),
                                },
                                evidence_state="observed",
                                safety=safety,
                            ),
                        )
                        extracted += 1
                    except Exception as e:
                        logger.debug("auto_extract append failed: %s", e)
                    break

        if extracted or queued:
            logger.info(
                "Auto-extract session %s: durable=%d candidates=%d policy=%s",
                self._session_id,
                extracted,
                queued,
                policy,
            )

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
        from hermescube.tools_recall import handle_search

        return handle_search(self, args)

    def _handle_probe(self, args: dict[str, Any]) -> str:
        from hermescube.tools_recall import handle_probe

        return handle_probe(self, args)

    def _handle_manage(self, args: dict[str, Any]) -> str:
        """Handle hermescube_manage tool call."""
        from hermescube.manage import dispatch_manage

        return dispatch_manage(self, args)

    def _path_kw(self) -> dict[str, Any]:
        return {
            "agent_identity": self._agent_identity or "",
            "agent_workspace": self._agent_workspace or "",
            "nest_profiles": bool(getattr(self, "_nest_profiles", False)),
        }

    def _relation_store(self):
        from hermescube.relations import RelationStore

        if getattr(self, "_paths", None) is not None:
            return RelationStore(path=self._paths.relations)
        return RelationStore(self._hermes_home, **self._path_kw())

    def _handle_feedback(self, args: dict[str, Any]) -> str:
        from hermescube.tools_recall import handle_feedback

        return handle_feedback(self, args)

