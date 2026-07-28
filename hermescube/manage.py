"""Dispatch hermescube_manage actions (extracted from CubeMemoryProvider).

Handlers live in domain modules; the provider keeps a thin `_handle_manage`
that calls `dispatch_manage`.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from hermescube import manage_cuboasis
from hermescube import manage_fleet
from hermescube import manage_growth
from hermescube import manage_warehouse

_ACTIONS: dict[str, Callable[[Any, dict[str, Any]], str]] = {
    "bootstrap": manage_warehouse.handle_bootstrap,
    "add": manage_warehouse.handle_add,
    "remove": manage_warehouse.handle_remove,
    "relations": manage_warehouse.handle_relations,
    "hygiene": manage_warehouse.handle_hygiene,
    "prune": manage_warehouse.handle_prune,
    "crystalize": manage_warehouse.handle_crystalize,
    "replay": manage_warehouse.handle_replay,
    "journey": manage_warehouse.handle_journey,
    "triage": manage_cuboasis.handle_triage,
    "merge": manage_cuboasis.handle_merge,
    "space": manage_cuboasis.handle_space,
    "connect": manage_cuboasis.handle_connect,
    "progress": manage_cuboasis.handle_progress,
    "cuboasis": manage_cuboasis.handle_cuboasis,
    "growth": manage_growth.handle_growth,
    "curate": manage_growth.handle_curate,
    "promote": manage_growth.handle_promote,
    "reject": manage_growth.handle_reject,
    "drafts": manage_growth.handle_drafts,
    "pulse": manage_growth.handle_pulse,
    "forge": manage_growth.handle_forge,
    "intents": manage_growth.handle_intents,
    "observe": manage_growth.handle_observe,
    "peer": manage_growth.handle_peer,
    "witness": manage_growth.handle_witness,
    "harness": manage_growth.handle_harness,
    "hive": manage_fleet.handle_hive,
    "hq": manage_fleet.handle_hq,
    "interview": manage_fleet.handle_interview,
    "nexus": manage_cuboasis.handle_cuboasis,  # deprecated alias
}


def dispatch_manage(provider: Any, args: dict[str, Any]) -> str:
    """Route a manage tool call to the domain handler."""
    action = str(args.get("action") or "")
    handler = _ACTIONS.get(action)
    if handler is None:
        return json.dumps({"error": f"Unknown action: {action}"})
    return handler(provider, args)


def known_actions() -> list[str]:
    return sorted(_ACTIONS)
