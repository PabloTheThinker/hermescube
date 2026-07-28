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
                            ],
                            "description": (
                                "bootstrap (import hot memories + install skills) · "
                                "warehouse ops + living pulse + consent + peer + hive "
                                "+ witness + harness + hq + interview + growth + curate "
                                "+ triage / merge / relations "
                                "+ space / connect / progress / cuboasis"
                            ),
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

        if action == "bootstrap":
            return self._handle_manage_bootstrap(args)
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
        elif action == "pulse":
            return self._handle_manage_pulse(args)
        elif action == "hive":
            return self._handle_manage_hive(args)
        elif action == "witness":
            return self._handle_manage_witness(args)
        elif action == "harness":
            return self._handle_manage_harness(args)
        elif action == "hq":
            return self._handle_manage_hq(args)
        elif action == "interview":
            return self._handle_manage_interview(args)
        elif action == "growth":
            return self._handle_manage_growth(args)
        elif action == "curate":
            return self._handle_manage_curate(args)
        elif action == "triage":
            return self._handle_manage_triage(args)
        elif action == "merge":
            return self._handle_manage_merge(args)
        elif action == "relations":
            return self._handle_manage_relations(args)
        elif action == "space":
            return self._handle_manage_space(args)
        elif action == "connect":
            return self._handle_manage_connect(args)
        elif action == "progress":
            return self._handle_manage_progress(args)
        elif action in ("cuboasis", "nexus"):
            return self._handle_manage_cuboasis(args)
        return json.dumps({"error": f"Unknown action: {action}"})

    def _handle_manage_bootstrap(self, args: dict[str, Any]) -> str:
        """Import hot Hermes memories + install bundled Cube skills."""
        if not self._cube or not self._hermes_home:
            return json.dumps({"error": "Memory not initialized"})
        mode = str(args.get("mode") or args.get("content") or "all").strip().lower()
        force = False
        if mode.endswith(":force") or mode in ("import:force", "force"):
            force = True
            mode = mode.replace(":force", "").replace("force", "import") or "import"
        if mode in ("reimport", "refresh"):
            mode, force = "import", True
        try:
            from hermescube.bootstrap import run_bootstrap

            report = run_bootstrap(
                self._cube,
                self._hermes_home,
                mode=mode or "all",
                force=force,
                vault=getattr(self, "_vault", "") or "",
                session_id=self._session_id or "",
                overwrite_skills=bool(args.get("overwrite") or force),
            )
            self._last_bootstrap = report
            if self._engine and (report.get("import") or {}).get("imported"):
                try:
                    self._engine.invalidate_cache()
                except Exception:
                    pass
                self._refresh_snapshot()
            return json.dumps(report, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_curate(self, args: dict[str, Any]) -> str:
        """Run the growth curator — refine skills from lessons, forge/garden."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        try:
            from hermescube.curator import run_curator

            lesson = str(args.get("content") or args.get("query") or "").strip()
            lessons = [lesson] if lesson else []
            # Also pull recent hive draws from the cube as lessons
            if self._cube and not lessons:
                for e in list(self._cube.read_l1() or [])[-40:]:
                    desc = e.description or ""
                    if desc.startswith("[HIVE:") or desc.startswith("[INTERVIEW:"):
                        lessons.append(desc)
            force_era = str(args.get("mode") or "").lower() == "milestone"
            report = run_curator(
                self._hermes_home,
                cube=self._cube,
                lessons=lessons[-12:],
                era_milestone=force_era,
            )
            self._refresh_maturity()
            return json.dumps({"status": "curate", **report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})


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

    def _handle_manage_triage(self, args: dict[str, Any]) -> str:
        """Build / return / apply consolidation triage plan."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.triage import run_triage, load_plan

            pkw = self._path_kw()
            mode = str(args.get("mode") or args.get("content") or "").lower()
            if mode == "load":
                plan = load_plan(self._hermes_home, **pkw) or {}
                return json.dumps({"status": "triage", "loaded": True, **plan}, default=str)
            if mode in ("apply", "run", "execute"):
                from hermescube.cuboasis import apply_triage

                report = apply_triage(
                    self._cube,
                    self._hermes_home,
                    forge_limit=int(args.get("top_k") or 2),
                    **pkw,
                )
                if self._engine:
                    self._engine.invalidate_cache()
                return json.dumps({"status": "triage_apply", **report}, default=str)
            plan = run_triage(
                self._cube,
                hermes_home=self._hermes_home,
                per_route_limit=int(args.get("top_k") or 8),
                **pkw,
            )
            return json.dumps({"status": "triage", **plan}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_merge(self, args: dict[str, Any]) -> str:
        """Multi-axis growth merge (AgentDrive-inspired, Cube-native)."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.growth_merge import merge_session_growth

            dry = str(args.get("mode") or "").lower() == "dry"
            result = merge_session_growth(
                self._cube,
                hermes_home=self._hermes_home,
                engram=getattr(self, "_engram", None),
                session_stats={"durable_writes": 1},
                dry_run=dry,
                **self._path_kw(),
            )
            if result.merged and not dry and self._engine:
                self._engine.invalidate_cache()
                self._refresh_maturity()
            return json.dumps({"status": "merge", **result.to_dict()}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_relations(self, args: dict[str, Any]) -> str:
        """SPO relations: query / record / stats / expire."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        try:
            from hermescube.relations import RelationStore

            store = self._relation_store()
            content = str(args.get("content") or args.get("query") or "").strip()
            mode = str(args.get("mode") or "").lower()
            if not mode:
                if content.startswith("record:") or "|" in content and content.count("|") >= 2:
                    mode = "record"
                elif content in ("", "stats"):
                    mode = "stats"
                else:
                    mode = "query"
            if mode == "stats":
                return json.dumps({"status": "relations", **store.stats()}, default=str)
            if mode == "record":
                raw = content[7:] if content.lower().startswith("record:") else content
                parts = [p.strip() for p in raw.split("|")]
                if len(parts) < 3:
                    return json.dumps({
                        "error": "record needs subject|predicate|object",
                    })
                rel = store.record(parts[0], parts[1], parts[2])
                return json.dumps({"status": "recorded", **rel.to_dict()}, default=str)
            if mode == "expire":
                raw = content[7:] if content.lower().startswith("expire:") else content
                parts = [p.strip() for p in raw.split("|")]
                if len(parts) < 3:
                    return json.dumps({"error": "expire needs subject|predicate|object"})
                n = store.expire(parts[0], parts[1], parts[2])
                return json.dumps({"status": "expired", "count": n})
            # query
            entity = content
            if content.lower().startswith("query:"):
                entity = content[6:].strip()
            hits = store.query(entity, limit=int(args.get("top_k") or 20))
            return json.dumps(
                {
                    "status": "relations",
                    "entity": entity,
                    "count": len(hits),
                    "relations": [h.to_dict() for h in hits],
                },
                default=str,
            )
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_space(self, args: dict[str, Any]) -> str:
        """Space map — vaults + chambers (organization without a second store)."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.cuboasis import space_map, chamber_filter_ids

            mode = str(args.get("mode") or args.get("content") or "status").strip().lower()
            pkw = self._path_kw()
            if mode.startswith("chamber:"):
                ch = mode.split(":", 1)[1].strip().lower()
                self._chamber = ch
                if self._engine is not None:
                    setattr(self._engine, "_chamber_filter", ch)
                ids = chamber_filter_ids(self._cube, ch, limit=int(args.get("top_k") or 40))
                return json.dumps(
                    {
                        "status": "space",
                        "chamber": ch,
                        "active": True,
                        "ids": ids,
                        "count": len(ids),
                    },
                    default=str,
                )
            if mode in ("chamber_clear", "clear_chamber", "all"):
                self._chamber = ""
                if self._engine is not None:
                    setattr(self._engine, "_chamber_filter", "")
            if mode == "set" and args.get("query"):
                # Soft-set active vault for this session (affinity tag)
                self._vault = str(args.get("query") or "").strip()[:80]
                if self._engine is not None:
                    setattr(self._engine, "_active_vault", self._vault)
                with self._state_lock:
                    self._prefetch_cache.clear()
            report = space_map(
                self._cube,
                hermes_home=self._hermes_home,
                active_vault=getattr(self, "_vault", "") or "",
                **pkw,
            )
            report["active_chamber"] = getattr(self, "_chamber", "") or ""
            return json.dumps({"status": "space", **report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_connect(self, args: dict[str, Any]) -> str:
        """Unified neighbors — SPO + colony + engram + HAR related."""
        entity = str(args.get("content") or args.get("query") or "").strip()
        if not entity:
            return json.dumps({"error": "entity required in content/query"})
        try:
            from hermescube.cuboasis import connect_entity

            report = connect_entity(
                entity,
                cube=self._cube,
                hermes_home=self._hermes_home,
                relation_store=self._relation_store() if self._hermes_home else None,
                colony=getattr(self, "_colony", None),
                engram=getattr(self, "_engram", None),
                cubewave=getattr(self, "_cubewave", None),
                engine=self._engine,
                limit=int(args.get("top_k") or 12),
                **self._path_kw(),
            )
            return json.dumps({"status": "connect", **report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_progress(self, args: dict[str, Any]) -> str:
        """Progress ledger — proof the compounding loop moved."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        try:
            from hermescube.cuboasis import progress_status, record_progress

            mode = str(args.get("mode") or "").strip().lower()
            content = str(args.get("content") or "").strip()
            if mode == "record" or content.startswith("record:"):
                detail = content[7:].strip() if content.lower().startswith("record:") else content
                rec = record_progress(
                    self._hermes_home,
                    "manual",
                    detail=detail or "operator note",
                    **self._path_kw(),
                )
                return json.dumps({"status": "progress", **rec}, default=str)
            report = progress_status(
                self._hermes_home,
                cube=self._cube,
                limit=int(args.get("top_k") or 20),
                **self._path_kw(),
            )
            return json.dumps({"status": "progress", **report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_cuboasis(self, args: dict[str, Any]) -> str:
        """Cuboasis pane + governance: capture/review/approve/reject/sync/doctor."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        mode = str(args.get("mode") or args.get("content") or "status").strip().lower()
        # Allow content to carry capture text when mode is set separately
        content = str(args.get("content") or args.get("query") or "").strip()
        if mode in ("status", "", "show") and content and not content.startswith(("approve:", "reject:")):
            # bare content with default mode → treat as capture
            if content not in ("status", "show", "sync", "doctor", "review", "rejected"):
                mode = "capture"

        pkw = self._path_kw()
        try:
            from hermescube import memory_gate as gate
            from hermescube.cuboasis import cuboasis_status, record_progress

            if mode in ("capture", "candidate"):
                text = content
                if text.lower().startswith("capture:"):
                    text = text[8:].strip()
                if not text:
                    return json.dumps({"error": "capture requires content"})
                rec = gate.capture_candidate(
                    self._hermes_home,
                    text,
                    source="cuboasis_capture",
                    session_id=self._session_id,
                    entry_type=str(args.get("entry_type") or "belief"),
                    **pkw,
                )
                record_progress(
                    self._hermes_home,
                    "candidate_capture",
                    detail=rec.get("candidate_id", ""),
                    metrics={"pending": 1},
                    **pkw,
                )
                return json.dumps({**rec, "status": "capture"}, default=str)

            if mode in ("review", "queue", "pending"):
                report = gate.list_candidates(
                    self._hermes_home,
                    status="pending",
                    limit=int(args.get("top_k") or 40),
                    **pkw,
                )
                return json.dumps({"status": "review", **report}, default=str)

            if mode.startswith("approve:") or mode == "approve":
                cid = mode.split(":", 1)[1].strip() if ":" in mode else content
                if cid.lower().startswith("approve:"):
                    cid = cid[8:].strip()
                if not cid:
                    return json.dumps({"error": "approve needs candidate_id"})
                if not self._cube:
                    return json.dumps({"error": "Memory not initialized"})
                report = gate.approve_candidate(
                    self._hermes_home,
                    cid,
                    cube=self._cube,
                    **pkw,
                )
                if report.get("ok") and self._engine:
                    self._engine.invalidate_cache()
                record_progress(
                    self._hermes_home,
                    "candidate_approve",
                    detail=cid,
                    metrics={"approved": 1 if report.get("ok") else 0},
                    **pkw,
                )
                return json.dumps({"status": "approve", **report}, default=str)

            if mode.startswith("reject:") or mode == "reject":
                cid = mode.split(":", 1)[1].strip() if ":" in mode else content
                reason = ""
                if "|" in cid:
                    cid, reason = [x.strip() for x in cid.split("|", 1)]
                if cid.lower().startswith("reject:"):
                    cid = cid[7:].strip()
                if not cid:
                    return json.dumps({"error": "reject needs candidate_id"})
                report = gate.reject_candidate(
                    self._hermes_home,
                    cid,
                    reason=reason or "rejected",
                    **pkw,
                )
                record_progress(
                    self._hermes_home,
                    "candidate_reject",
                    detail=cid,
                    metrics={"rejected": 1 if report.get("ok") else 0},
                    **pkw,
                )
                return json.dumps({"status": "reject", **report}, default=str)

            if mode in ("rejected", "negative"):
                report = gate.recall_rejected(
                    self._hermes_home,
                    content if content not in ("rejected", "negative") else "",
                    limit=int(args.get("top_k") or 12),
                    **pkw,
                )
                return json.dumps({"status": "rejected", **report}, default=str)

            if mode in ("sync", "curate", "curation"):
                if not self._cube:
                    return json.dumps({"error": "Memory not initialized"})
                report = gate.curation_sync_report(
                    self._cube,
                    self._hermes_home,
                    limit=int(args.get("top_k") or 24),
                    **pkw,
                )
                return json.dumps({"status": "sync", **report}, default=str)

            if mode == "doctor":
                report = gate.oasis_doctor_card(
                    self._cube,
                    self._hermes_home,
                    engram=getattr(self, "_engram", None),
                    cubewave=getattr(self, "_cubewave", None),
                    relation_store=self._relation_store() if self._hermes_home else None,
                    **pkw,
                )
                return json.dumps({"status": "doctor", **report}, default=str)

            # default status pane
            if not self._cube:
                return json.dumps({"error": "Memory not initialized"})
            report = cuboasis_status(
                self._cube,
                self._hermes_home,
                active_vault=getattr(self, "_vault", "") or "",
                active_chamber=getattr(self, "_chamber", "") or "",
                colony=getattr(self, "_colony", None),
                engram=getattr(self, "_engram", None),
                cubewave=getattr(self, "_cubewave", None),
                relation_store=self._relation_store(),
                **pkw,
            )
            return json.dumps({"status": "cuboasis", **report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_nexus(self, args: dict[str, Any]) -> str:
        """Deprecated alias for cuboasis."""
        return self._handle_manage_cuboasis(args)

    def _handle_manage_growth(self, args: dict[str, Any]) -> str:
        """Living cube genealogy — version, strength, eras, skill lineage."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        sub = str(args.get("content") or args.get("mode") or "status").strip().lower()
        try:
            from hermescube import genealogy as gen

            if sub in ("status", "", "show"):
                return json.dumps(
                    {"status": "growth", **gen.growth_status(
                        self._hermes_home, cube=self._cube
                    )},
                    default=str,
                )
            if sub == "epochs":
                return json.dumps(
                    {
                        "status": "epochs",
                        "epochs": gen.list_epochs(self._hermes_home, limit=30),
                    },
                    default=str,
                )
            if sub.startswith("refine:"):
                # refine:<skill_name> — lesson in mode/query fields
                skill = sub.split(":", 1)[1].strip()
                lesson = str(args.get("query") or args.get("description") or "").strip()
                if not lesson:
                    return json.dumps({"error": "lesson text required in query"})
                return json.dumps(
                    {
                        "status": "refine",
                        **gen.refine_skill(
                            self._hermes_home,
                            skill,
                            lesson=lesson,
                            cube=self._cube,
                        ),
                    },
                    default=str,
                )
            return json.dumps({"error": f"unknown growth subcommand: {sub}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_interview(self, args: dict[str, Any]) -> str:
        """Peer interview (interview-me protocol) at the Hive.

        dialogue — offline peer dialogue that inspects a subject soul,
        asks highest-value questions, produces a brief, optionally mints
        a consent-gated skill draft.
        list / mint — review past interviews / mint from a closed session.
        """
        hive_root = getattr(self, "_hive_path", "") or os.environ.get(
            "HERMESCUBE_HIVE", ""
        )
        if not hive_root:
            return json.dumps(
                {
                    "error": "hive not configured",
                    "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
                }
            )
        try:
            from hermescube import interview as iv

            sub = str(args.get("interview_action") or "dialogue").strip()
            agent_id = self._agent_identity or "hermes"

            if sub == "list":
                return json.dumps(
                    {"status": "list", "interviews": iv.list_interviews(hive_root)},
                    default=str,
                )

            if sub == "dialogue":
                subject = str(args.get("agent") or "").strip()
                if not subject:
                    return json.dumps(
                        {"error": "agent required (peer subject to interview)"}
                    )
                topic = str(args.get("content") or args.get("focus") or "shared craft")
                mode = str(args.get("mode") or "discover")
                # Prefer subject's offered knowledge; fall back to local cube
                # only when interviewing about knowledge already drawn in.
                r = iv.peer_dialogue(
                    hive_root,
                    interviewer=agent_id,
                    subject=subject,
                    topic=topic,
                    mode=mode if mode in iv.MODES else "discover",
                    subject_cube=self._cube,
                    hermes_home=self._hermes_home or str(Path.home() / ".hermes"),
                    persist=True,
                    mint=True,
                )
                return json.dumps({"status": "dialogue", **r}, default=str)

            if sub == "mint":
                session_id = str(args.get("content") or args.get("entry_id") or "").strip()
                if not session_id:
                    return json.dumps({"error": "content required (session id)"})
                path = iv.interviews_dir(hive_root) / f"{session_id}.json"
                if not path.is_file():
                    return json.dumps({"error": f"session not found: {session_id}"})
                session = json.loads(path.read_text(encoding="utf-8"))
                brief = session.get("brief") or iv.produce_brief(session)
                r = iv.mint_skill_draft(
                    brief,
                    hermes_home=self._hermes_home or str(Path.home() / ".hermes"),
                )
                return json.dumps({"status": "mint", **r}, default=str)

            return json.dumps({"error": f"unknown interview_action: {sub}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_hq(self, args: dict[str, Any]) -> str:
        """Fleet HQ ops: route / charter / claim / handoffs / verify / baseline.

        Requires a configured hive (the hive root doubles as fleet HQ).
        """
        hive_root = getattr(self, "_hive_path", "") or os.environ.get(
            "HERMESCUBE_HIVE", ""
        )
        if not hive_root:
            return json.dumps(
                {
                    "error": "HQ not configured",
                    "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
                }
            )
        try:
            from hermescube import hq as hq_mod

            sub = str(args.get("hq_action") or "route").strip()
            agent_id = self._agent_identity or "hermes"
            if sub == "route":
                task = str(args.get("content") or args.get("task") or "").strip()
                if not task:
                    return json.dumps({"error": "content required (task to route)"})
                return json.dumps(
                    {"status": "route", **hq_mod.route_task(hive_root, task)},
                    default=str,
                )
            if sub == "charter":
                r = hq_mod.register_charter(
                    hive_root,
                    str(args.get("agent") or agent_id),
                    role=str(args.get("role") or "specialist"),
                    lane=str(args.get("lane") or args.get("content") or ""),
                    keywords=[
                        k.strip()
                        for k in str(args.get("keywords") or "").split(",")
                        if k.strip()
                    ],
                    boundaries=[
                        b.strip()
                        for b in str(args.get("boundaries") or "").split(";")
                        if b.strip()
                    ],
                )
                return json.dumps({"status": "charter", **r}, default=str)
            if sub == "charters":
                return json.dumps(
                    {"status": "charters", "charters": hq_mod.list_charters(hive_root)},
                    default=str,
                )
            if sub == "claim":
                task = str(args.get("content") or args.get("task") or "").strip()
                if not task:
                    return json.dumps({"error": "content required (task to claim)"})
                return json.dumps(
                    {
                        "status": "claim",
                        **hq_mod.claim_task(hive_root, agent_id, task),
                    },
                    default=str,
                )
            if sub == "handoffs":
                return json.dumps(
                    {
                        "status": "handoffs",
                        "handoffs": hq_mod.list_handoffs(hive_root, limit=20),
                    },
                    default=str,
                )
            if sub == "handoff":
                # Route → distill context → record: the full delegation package
                task = str(args.get("content") or args.get("task") or "").strip()
                if not task:
                    return json.dumps({"error": "content required (task to hand off)"})
                to_agent = str(args.get("agent") or "").strip()
                routed = None
                if not to_agent:
                    routed = hq_mod.route_task(hive_root, task)
                    if not routed.get("ok"):
                        return json.dumps({"error": routed.get("error")})
                    to_agent = str(routed["owner"])
                packet: dict[str, Any] = {"context": "", "sha": ""}
                if self._cube:
                    packet = hq_mod.build_handoff_packet(
                        self._cube, task, from_agent=agent_id, to_agent=to_agent
                    )
                rec = hq_mod.record_handoff(
                    hive_root,
                    from_agent=agent_id,
                    to_agent=to_agent,
                    task=task,
                    status="pending",
                    packet_sha=str(packet.get("sha") or ""),
                )
                return json.dumps(
                    {
                        "status": "handoff",
                        "id": rec["id"],
                        "to_agent": to_agent,
                        "routed_via": (routed or {}).get("via"),
                        "context": packet.get("context") or "(no cube evidence)",
                        "note": (
                            "Deliver this context with the delegation; settle with "
                            "hq_action=complete content=<id> when done."
                        ),
                    },
                    default=str,
                )
            if sub == "complete":
                hid = str(args.get("content") or "").strip()
                if not hid:
                    return json.dumps({"error": "content required (handoff id)"})
                return json.dumps(
                    {
                        "status": "complete",
                        **hq_mod.update_handoff_status(hive_root, hid, "completed"),
                    },
                    default=str,
                )
            if sub == "verify":
                return json.dumps(
                    {"status": "verify", **hq_mod.verify_fleet(hive_root)},
                    default=str,
                )
            if sub == "baseline":
                mode = str(args.get("content") or "verify").strip()
                if mode == "freeze":
                    return json.dumps(
                        {"status": "baseline", **hq_mod.freeze_baseline(hive_root)},
                        default=str,
                    )
                return json.dumps(
                    {"status": "baseline", **hq_mod.verify_baseline(hive_root)},
                    default=str,
                )
            return json.dumps({"error": f"unknown hq_action: {sub}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_witness(self, args: dict[str, Any]) -> str:
        """Record real friction in the witness ledger (grounded evolution)."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        content = str(args.get("content") or "").strip()
        if not content:
            return json.dumps({"error": "content required (describe the friction)"})
        try:
            from hermescube.self_evolution import record_witness

            rec = record_witness(
                self._hermes_home,
                content,
                severity=str(args.get("severity") or "medium"),
                kind="manual",
                session_id=self._session_id,
                source="manage",
            )
            return json.dumps({"status": "witness", "recorded": rec}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_harness(self, args: dict[str, Any]) -> str:
        """Self-evolution harness ops: status / critic / gardener / verify."""
        if not self._hermes_home:
            return json.dumps({"error": "hermes_home not set"})
        try:
            from hermescube import self_evolution as se

            sub = str(
                args.get("harness_action") or args.get("content") or "status"
            ).strip()
            if sub == "status":
                return json.dumps(
                    {"status": "harness", **se.harness_status(self._hermes_home)},
                    default=str,
                )
            if sub == "critic":
                return json.dumps(
                    {"status": "critic", **se.run_critic(self._hermes_home)},
                    default=str,
                )
            if sub == "verify":
                stats = se.verify_predictions(self._hermes_home, cube=self._cube)
                return json.dumps({"status": "verify", **stats}, default=str)
            if sub == "gardener":
                if not self._cube:
                    return json.dumps({"error": "Memory not initialized"})
                r = se.run_gardener(self._cube, self._hermes_home)
                return json.dumps({"status": "gardener", **r}, default=str)
            return json.dumps({"error": f"unknown harness_action: {sub}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_hive(self, args: dict[str, Any]) -> str:
        """Hive nexus ops: status / pilgrimage / draw / offer.

        Requires ``plugins.hermescube.hive_path`` (or HERMESCUBE_HIVE env).
        The hive is a shared directory; transport (NFS/sync) is operator's.
        """
        hive_root = (
            getattr(self, "_hive_path", "")
            or os.environ.get("HERMESCUBE_HIVE", "")
        )
        if not hive_root:
            return json.dumps(
                {
                    "error": "hive not configured",
                    "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
                }
            )
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube import hive as hive_mod

            sub = str(args.get("hive_action") or args.get("content") or "status").strip()
            agent_id = self._agent_identity or "hermes"
            if sub == "status":
                return json.dumps(
                    {"status": "hive", **hive_mod.hive_status(hive_root)}, default=str
                )
            if sub == "offer":
                rows = hive_mod.build_offering(self._cube, agent_id=agent_id)
                if not rows:
                    return json.dumps({"status": "offer", "rows": 0})
                m = hive_mod.write_offering(hive_root, rows, agent_id=agent_id)
                return json.dumps({"status": "offer", **m}, default=str)
            if sub == "draw":
                r = hive_mod.draw_wisdom(
                    hive_root,
                    self._cube,
                    agent_id=agent_id,
                    focus=str(args.get("focus") or ""),
                )
                if self._engine:
                    self._engine.invalidate_cache()
                with self._state_lock:
                    self._prefetch_cache.clear()
                return json.dumps({"status": "draw", **r}, default=str)
            if sub == "pilgrimage":
                do_interview = bool(
                    args.get("interview")
                    or getattr(self, "_interview_on_pilgrimage", False)
                )
                r = hive_mod.pilgrimage(
                    hive_root,
                    hermes_home=self._hermes_home or str(Path.home() / ".hermes"),
                    agent_id=agent_id,
                    focus=str(args.get("focus") or ""),
                    interview=do_interview,
                )
                if self._engine:
                    self._engine.invalidate_cache()
                with self._state_lock:
                    self._prefetch_cache.clear()
                return json.dumps({"status": "pilgrimage", **r}, default=str)
            return json.dumps({"error": f"unknown hive_action: {sub}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_pulse(self, args: dict[str, Any]) -> str:
        """Multi-chamber living pulse — catalog, connect dots, peer, doctrine."""
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.living import chamber_pulse

            report = chamber_pulse(
                self._cube,
                hermes_home=self._hermes_home,
                engram=getattr(self, "_engram", None),
                max_connect=int(args.get("max_connect") or 4),
                do_crystalize=bool(args.get("crystalize", True)),
                do_peer=bool(args.get("peer", True)),
                **self._path_kw(),
            )
            if report.get("ok"):
                self._prefetch_cache.clear()
                if self._engine:
                    try:
                        self._engine.invalidate_cache()
                    except Exception:
                        pass
            return json.dumps({"status": "pulse", "report": report}, default=str)
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _handle_manage_promote(self, args: dict[str, Any]) -> str:
        if not self._cube:
            return json.dumps({"error": "Memory not initialized"})
        try:
            from hermescube.consent import promote

            name = str(args.get("name") or args.get("content") or "").strip()
            if not name:
                return json.dumps({"error": "name required (draft filename)"})
            install = bool(
                args.get("install_to_skills")
                or args.get("install")
                or False
            )
            overwrite = bool(args.get("overwrite") or False)
            r = promote(
                name,
                hermes_home=self._hermes_home,
                cube=self._cube,
                install_to_skills=install,
                overwrite=overwrite,
            )
            # Falsifiable prediction: promoted procedure must earn trust
            if r.get("ok") and self._hermes_home:
                try:
                    from hermescube.self_evolution import make_prediction

                    entry_id = str(r.get("entry_id") or "")
                    if entry_id:
                        make_prediction(
                            self._hermes_home,
                            f"promoted procedure '{name}' earns trust >= 0.6",
                            check={
                                "type": "entry_feedback",
                                "entry_id": entry_id,
                                "min_trust": 0.6,
                            },
                            source=f"promote:{name}",
                        )
                except Exception:
                    pass
                # Living version advances on promote; skill_bridge records
                # skill_install itself so we don't double-bump.
                if not r.get("installed"):
                    try:
                        from hermescube.genealogy import record_growth

                        record_growth(
                            self._hermes_home,
                            "promote",
                            detail=f"promote: {name}",
                            cube=self._cube,
                        )
                    except Exception:
                        pass
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

                net = EngramNet(self._paths.engram)
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

        from hermescube.memory_gate import (
            capture_candidate,
            decide_write_path,
            enrich_entry_data,
            memory_safety,
        )

        safety = memory_safety(content, content)
        path = decide_write_path(safety, policy=getattr(self, "_memory_policy", "auto-safe"), explicit=True)
        if path == "block":
            # Still queue as blocked candidate for audit
            queued = capture_candidate(
                self._hermes_home,
                sanitize_for_storage(content, self._char_limit),
                record_type="fact",
                source="hermescube_manage",
                evidence_state="prepared_not_observed",
                session_id=self._session_id,
                entry_type=entry_type,
                **self._path_kw(),
            )
            return json.dumps(
                {
                    "error": "Content blocked by memory safety gate",
                    "safety": safety,
                    "candidate": queued,
                },
                default=str,
            )

        as_candidate = str(args.get("mode") or "").lower() in (
            "candidate",
            "capture",
            "review-first",
        )
        if as_candidate or path == "candidate":
            queued = capture_candidate(
                self._hermes_home,
                sanitize_for_storage(content, self._char_limit),
                record_type="fact",
                source="hermescube_manage",
                evidence_state="prepared_not_observed",
                session_id=self._session_id,
                entry_type=entry_type,
                **self._path_kw(),
            )
            return json.dumps({"status": "candidate", **queued}, default=str)

        entry = self._cube.append(
            entry_type=entry_type,
            description=sanitize_for_storage(content, self._char_limit),
            data=enrich_entry_data(
                {
                    "source": "hermescube_manage",
                    "session_id": self._session_id,
                    "platform": self._platform,
                    "trust": 0.72 if entry_type in ("focus", "resolve") else 0.5,
                    "durable": True,
                    "verification": "user_authored",
                    **(
                        {"vault": self._vault, "topic": (self._agent_workspace or "")[:80]}
                        if getattr(self, "_vault", "")
                        else {}
                    ),
                    **(
                        {
                            "user_id": self._user_id,
                            **(
                                {"user_id_alt": self._user_id_alt}
                                if getattr(self, "_user_id_alt", "")
                                else {}
                            ),
                        }
                        if getattr(self, "_user_id", "")
                        else {}
                    ),
                },
                evidence_state="verified",
                safety=safety,
            ),
            outcome=outcome,
        )
        try:
            from hermescube.relations import ingest_entry

            ingest_entry(entry, self._relation_store())
        except Exception:
            pass
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

        # Cubewave: LMS + edge update from usefulness (pocket-dimension learning)
        try:
            wave = getattr(self, "_cubewave", None)
            if wave is not None:
                cohort = args.get("cohort_ids") or args.get("entry_ids")
                ids = [entry_id]
                if isinstance(cohort, list):
                    ids.extend(str(x) for x in cohort if x)
                elif getattr(self, "_last_prefetch_ids", None):
                    ids.extend(str(x) for x in self._last_prefetch_ids[:12])
                q = (
                    args.get("query")
                    or getattr(self, "_last_prefetch_query", None)
                    or (entry.description or "")[:120]
                )
                wave.learn_feedback(
                    ids,
                    helpful=(action == "helpful"),
                    query_text=str(q or ""),
                )
                wave.save()
        except Exception:
            pass

        # Progress ledger — usefulness signal
        if self._hermes_home:
            try:
                from hermescube.cuboasis import record_progress

                record_progress(
                    self._hermes_home,
                    "feedback",
                    detail=f"{action} {entry_id[:12]}",
                    metrics={
                        "helpful": 1 if action == "helpful" else 0,
                        "unhelpful": 1 if action == "unhelpful" else 0,
                        "trust": new_trust,
                    },
                    **self._path_kw(),
                )
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

        # Skills evolve: helpful feedback on a procedure/skill entry appends
        # a lesson and bumps the skill's patch version.
        refine_info: dict[str, Any] | None = None
        if action == "helpful" and self._hermes_home:
            try:
                d = entry.data if isinstance(entry.data, dict) else {}
                desc = entry.description or ""
                is_proc = bool(
                    d.get("procedure")
                    or d.get("skill_path")
                    or desc.startswith(
                        ("[PROCEDURE]", "[PROMOTED]", "[SKILL INSTALLED]")
                    )
                )
                if is_proc:
                    from hermescube.genealogy import refine_skill

                    skill_name = ""
                    if d.get("skill_path"):
                        skill_name = Path(str(d["skill_path"])).parent.name
                    elif desc.startswith("[SKILL INSTALLED]"):
                        skill_name = desc.split("]", 1)[-1].strip().split()[0]
                    elif d.get("draft"):
                        skill_name = Path(str(d["draft"])).stem
                    if skill_name:
                        refine_info = refine_skill(
                            self._hermes_home,
                            skill_name,
                            lesson=f"reinforced in use (trust → {new_trust}): {desc[:160]}",
                            cube=self._cube,
                        )
                    else:
                        from hermescube.genealogy import record_growth

                        record_growth(
                            self._hermes_home,
                            "feedback_up",
                            detail=f"trust↑ on procedure: {desc[:80]}",
                            cube=self._cube,
                        )
            except Exception:
                pass

        out: dict[str, Any] = {
            "status": "rated",
            "id": entry_id,
            "action": action,
            "trust": new_trust,
        }
        if refine_info and refine_info.get("ok"):
            out["skill_refined"] = {
                "skill": refine_info.get("skill"),
                "version": refine_info.get("to_version"),
            }
        return json.dumps(out)
