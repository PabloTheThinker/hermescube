"""Declarative config schema for the HermesCube memory provider.

Rendered by the Hermes Agent desktop UI and web dashboard config panels
without any bespoke UI code. See ``plugins/memory/config_schema.py`` for
the generic rendering contract.

This file must not import from the agent runtime — it is loaded by the
web server via ``importlib``, not via regular package import.
"""

from plugins.memory.config_schema import (
    ProviderField,
    ProviderConfigSchema,
    KIND_BOOL,
    KIND_NUMBER,
    KIND_TEXT,
    STORAGE_FLAT_JSON,
)

CONFIG_SCHEMA = ProviderConfigSchema(
    name="hermescube",
    label="HermesCube (Holographic Memory)",
    storage=STORAGE_FLAT_JSON,
    docs_url="https://github.com/PabloTheThinker/hermescube#readme",
    fields=(
        # ── Core ─────────────────────────────────────────────
        ProviderField(
            key="dim",
            label="Vector dimension",
            kind=KIND_NUMBER,
            default="256",
            description="HRR vector dimension. Larger = more capacity but slower. 256 is recommended.",
            inline=True,
            group="Core",
        ),
        ProviderField(
            key="l2_buckets",
            label="Topic buckets",
            kind=KIND_NUMBER,
            default="64",
            description="Number of L2 k-means topic clusters for HAR retrieval.",
            inline=True,
            group="Core",
        ),
        ProviderField(
            key="char_limit",
            label="Entry char limit",
            kind=KIND_NUMBER,
            default="2200",
            description="Maximum characters per stored memory entry.",
            group="Core",
        ),
        ProviderField(
            key="evolve_interval",
            label="Auto-evolve interval",
            kind=KIND_NUMBER,
            default="50",
            description="Trigger auto-evolve after this many new entries. 0 disables.",
            group="Core",
        ),
        ProviderField(
            key="memory_nudge_interval",
            label="Memory nudge interval",
            kind=KIND_NUMBER,
            default="10",
            description="Prompt the agent to review memory every N turns. 0 disables.",
            group="Core",
        ),
        # ── Session End ──────────────────────────────────────
        ProviderField(
            key="auto_extract",
            label="Auto-extract facts",
            kind=KIND_BOOL,
            default="false",
            description="Auto-extract facts from conversations at session end using regex patterns.",
            inline=True,
            group="Session End",
        ),
        ProviderField(
            key="query_rewrite",
            label="LLM query rewrite",
            kind=KIND_BOOL,
            default="false",
            description="Rewrite conversational messages into retrieval queries via the auxiliary LLM client before HAR search.",
            group="Session End",
        ),
        ProviderField(
            key="session_digest",
            label="Session digest",
            kind=KIND_BOOL,
            default="true",
            description="Write session digest landmarks on session end.",
            inline=True,
            group="Session End",
        ),
        ProviderField(
            key="observe_on_session_end",
            label="Trajectory observation",
            kind=KIND_BOOL,
            default="true",
            description="Observe tool chains at session end and forge procedure drafts from successful multi-tool sequences.",
            group="Session End",
        ),
        ProviderField(
            key="replay_on_session_end",
            label="Sleep replay",
            kind=KIND_BOOL,
            default="true",
            description="Run offline engram consolidation (sleep replay) on session end. Strengthens associative wiring from high-value entries.",
            group="Session End",
        ),
        ProviderField(
            key="living_pulse_on_session_end",
            label="Living pulse",
            kind=KIND_BOOL,
            default="true",
            description="Run the multi-chamber living archive pulse on session end. Refreshes peer card, wisdom, catalog, connects dots.",
            group="Session End",
        ),
        # ── Social ────────────────────────────────────────────
        ProviderField(
            key="peer_card_cadence_s",
            label="Peer card cadence (seconds)",
            kind=KIND_NUMBER,
            default="3600",
            description="Minimum seconds between peer card rebuilds. Lower = fresher card, higher = less I/O. Default 3600 (hourly).",
            group="Social",
        ),
        ProviderField(
            key="conflict_detect",
            label="Conflict detection",
            kind=KIND_BOOL,
            default="true",
            description="Detect contradictory beliefs/resolves on manage add and flag them for operator review. Uses lexical opposition + Jaccard similarity.",
            group="Social",
        ),
    ),
)
