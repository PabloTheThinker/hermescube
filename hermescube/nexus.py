"""Backward-compat shim — Nexus renamed to Cuboasis (0.40).

Prefer ``hermescube.cuboasis``. This module re-exports the same API so
older imports and manage action aliases keep working.
"""

from __future__ import annotations

from hermescube.cuboasis import (  # noqa: F401
    apply_triage,
    bridge_claim_to_relation,
    chamber_filter_ids,
    connect_entity,
    cuboasis_state_path,
    cuboasis_status,
    filter_by_chamber,
    nexus_state_path,
    nexus_status,
    progress_path,
    progress_status,
    progress_usefulness,
    prompt_strip,
    record_progress,
    space_map,
)

__all__ = [
    "apply_triage",
    "bridge_claim_to_relation",
    "chamber_filter_ids",
    "connect_entity",
    "cuboasis_state_path",
    "cuboasis_status",
    "filter_by_chamber",
    "nexus_state_path",
    "nexus_status",
    "progress_path",
    "progress_status",
    "progress_usefulness",
    "prompt_strip",
    "record_progress",
    "space_map",
]
