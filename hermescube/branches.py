"""Subagent memory branches — isolate unverified child work until promotion.

Hermes subagents run with skip_memory=True; the parent observes via
``on_delegation``. Branches keep child traces attributable and prevent
unverified deductions from polluting the main semantic surface until
explicit promotion.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from hermescube.events import event_to_entry_data, make_event
from hermescube.threats import sanitize_for_storage, scan_text


def branches_dir(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "branches"


def branch_id_for_child(child_session_id: str, *, parent_session_id: str = "") -> str:
    child = (child_session_id or "child").strip() or "child"
    parent = (parent_session_id or "main").strip() or "main"
    return f"sub:{parent[:12]}:{child[:12]}"


def record_delegation_branch(
    cube: Any,
    *,
    hermes_home: str | Path,
    task: str,
    result: str,
    child_session_id: str = "",
    parent_session_id: str = "",
    platform: str = "cli",
    agent_identity: str = "",
    char_limit: int = 2200,
    promote_success: bool = True,
) -> dict[str, Any]:
    """Write a branch-tagged landmark; optionally promote verified outcome."""
    safe_task = sanitize_for_storage(task, char_limit)
    safe_result = sanitize_for_storage(result, char_limit)
    for text in (safe_task, safe_result):
        if any(t.severity == "block" for t in scan_text(text)):
            return {"ok": False, "error": "blocked_threat"}

    bid = branch_id_for_child(child_session_id, parent_session_id=parent_session_id)
    outcome = "success" if (safe_result or "").strip() else "failure"
    event = make_event(
        "delegation",
        session_id=parent_session_id,
        parent_session_id=parent_session_id,
        platform=platform,
        agent_context="primary",
        agent_identity=agent_identity,
        actor="agent",
        source="on_delegation",
        branch_id=bid,
        confidence=0.7 if outcome == "success" else 0.4,
        verification="tool_verified" if outcome == "success" else "unverified",
        payload={
            "task": safe_task,
            "result": safe_result,
            "child_session_id": child_session_id,
        },
    )
    data = event_to_entry_data(
        event,
        child_session_id=child_session_id,
        result=safe_result,
        type="delegation",
        branch_id=bid,
        durable=True,
    )
    desc = sanitize_for_storage(f"Delegated: {safe_task[:150]}", char_limit)
    entry = cube.append(
        entry_type="landmark",
        description=desc,
        data=data,
        outcome=outcome,
    )

    # Persist branch ledger (sidecar)
    root = branches_dir(hermes_home)
    root.mkdir(parents=True, exist_ok=True)
    ledger = root / f"{bid.replace(':', '_')}.jsonl"
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "branch_id": bid,
                    "entry_id": getattr(entry, "id", None),
                    "event_id": event.event_id,
                    "outcome": outcome,
                    "task": safe_task[:300],
                }
            )
            + "\n"
        )

    promoted = None
    if promote_success and outcome == "success" and safe_result:
        # Promote a compact verified outcome onto main branch
        pe = make_event(
            "delegation",
            session_id=parent_session_id,
            parent_session_id=parent_session_id,
            platform=platform,
            agent_identity=agent_identity,
            actor="agent",
            source="branch_promote",
            branch_id="main",
            confidence=0.75,
            verification="tool_verified",
            parent_event_ids=[event.event_id],
            payload={"task": safe_task[:400], "result": safe_result[:800]},
        )
        promoted = cube.append(
            entry_type="resolve",
            description=sanitize_for_storage(
                f"[BRANCH→MAIN] {safe_task[:80]} → {safe_result[:120]}",
                char_limit,
            ),
            data=event_to_entry_data(
                pe,
                type="delegation_promote",
                from_branch=bid,
                durable=True,
                trust=0.75,
            ),
            outcome="success",
        )

    return {
        "ok": True,
        "branch_id": bid,
        "entry_id": getattr(entry, "id", None),
        "promoted_id": getattr(promoted, "id", None) if promoted else None,
        "outcome": outcome,
        "ledger": str(ledger),
    }


def list_branches(hermes_home: str | Path) -> list[dict[str, Any]]:
    root = branches_dir(hermes_home)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("*.jsonl")):
        try:
            lines = p.read_text(encoding="utf-8").strip().splitlines()
            last = json.loads(lines[-1]) if lines else {}
            n = len(lines)
        except Exception:
            last = {}
            n = 0
        out.append(
            {
                "path": str(p),
                "name": p.name,
                "events": n,
                "last": last,
            }
        )
    return out
