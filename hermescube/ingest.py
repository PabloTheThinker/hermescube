"""Idempotent trajectory ingestion and Hermes state reconciliation helpers.

Hermes persists turns in state.db before MemoryManager queues provider
``sync_turn``. Cube durability is therefore best-effort relative to Hermes;
this module makes ingestion idempotent via content hashes and supports a
cursor for later state.db reconciliation.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from hermescube.events import content_hash, event_to_entry_data, make_event
from hermescube.threats import sanitize_for_storage, scan_text

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()


def ingest_path(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "ingest_cursor.json"


def load_cursor(hermes_home: str | Path) -> dict[str, Any]:
    path = ingest_path(hermes_home)
    if not path.is_file():
        return {"seen_hashes": [], "last_session_id": "", "updated_at": 0.0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"seen_hashes": [], "last_session_id": "", "updated_at": 0.0}
        data.setdefault("seen_hashes", [])
        return data
    except Exception:
        return {"seen_hashes": [], "last_session_id": "", "updated_at": 0.0}


def save_cursor(hermes_home: str | Path, cursor: dict[str, Any]) -> None:
    path = ingest_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Cap seen hashes to keep the sidecar small
    seen = list(cursor.get("seen_hashes") or [])
    if len(seen) > 5000:
        seen = seen[-5000:]
    cursor = dict(cursor)
    cursor["seen_hashes"] = seen
    cursor["updated_at"] = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cursor, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def has_seen(cursor: dict[str, Any], ch: str) -> bool:
    seen = cursor.get("seen_hashes") or []
    return ch in seen


def mark_seen(cursor: dict[str, Any], ch: str) -> None:
    seen = list(cursor.get("seen_hashes") or [])
    if ch not in seen:
        seen.append(ch)
    cursor["seen_hashes"] = seen


def turn_hash(
    user_content: str,
    assistant_content: str,
    *,
    session_id: str = "",
    turn: int | None = None,
) -> str:
    return content_hash("turn", session_id, turn, user_content, assistant_content)


def extract_tool_trajectory(messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Pull tool calls/results from an OpenAI-style messages list."""
    if not messages:
        return []
    out: list[dict[str, Any]] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                out.append(
                    {
                        "kind": "tool_call",
                        "id": tc.get("id") or "",
                        "name": fn.get("name") or tc.get("name") or "",
                        "arguments": fn.get("arguments") or tc.get("arguments") or "",
                    }
                )
        elif role == "tool":
            content = msg.get("content")
            if not isinstance(content, str):
                content = json.dumps(content, default=str) if content is not None else ""
            out.append(
                {
                    "kind": "tool_result",
                    "tool_call_id": msg.get("tool_call_id") or "",
                    "name": msg.get("name") or "",
                    "content": content[:4000],
                }
            )
    return out


def ingest_turn(
    cube: Any,
    *,
    user_content: str,
    assistant_content: str,
    session_id: str = "",
    hermes_home: str | Path | None = None,
    platform: str = "cli",
    agent_context: str = "primary",
    agent_identity: str = "",
    parent_session_id: str = "",
    branch_id: str = "main",
    turn: int = 0,
    messages: list[dict[str, Any]] | None = None,
    char_limit: int = 2200,
    entry_type: str = "landmark",
    outcome: str = "none",
    description: str = "",
    extra_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a turn event if unseen. Returns status dict."""
    user_clean = sanitize_for_storage(user_content, char_limit)
    assistant_clean = sanitize_for_storage(assistant_content, char_limit)
    for text in (user_clean, assistant_clean):
        threats = scan_text(text)
        if any(t.severity == "block" for t in threats):
            return {"ok": False, "skipped": "threat", "entry_id": None}

    ch = turn_hash(user_clean, assistant_clean, session_id=session_id, turn=turn)
    cursor: dict[str, Any] = {"seen_hashes": []}
    home = hermes_home
    if home:
        with _LOCK:
            cursor = load_cursor(home)
            if has_seen(cursor, ch):
                return {"ok": True, "skipped": "duplicate", "content_hash": ch, "entry_id": None}

    tools = extract_tool_trajectory(messages)
    event = make_event(
        "turn",
        session_id=session_id,
        parent_session_id=parent_session_id,
        platform=platform,
        agent_context=agent_context,
        agent_identity=agent_identity,
        actor="agent",
        source="sync_turn",
        branch_id=branch_id,
        confidence=0.55,
        verification="observed",
        payload={
            "user": user_clean,
            "assistant": assistant_clean,
            "turn": turn,
            "tools": tools[:40],
            "tool_count": len(tools),
        },
    )
    # Preserve hash stability with turn_hash
    event.content_hash = ch

    data = event_to_entry_data(
        event,
        user=user_clean,
        assistant=assistant_clean,
        turn=turn,
        platform=platform,
        agent_context=agent_context,
        source="sync_turn",
        tools=tools[:40] if tools else None,
        durable=True,
        **(extra_data or {}),
    )
    # Drop None tools key noise
    if data.get("tools") is None:
        data.pop("tools", None)

    desc = (description or user_clean[:200] or "(empty turn)").strip()
    try:
        added = cube.append(
            entry_type=entry_type,
            description=desc,
            data=data,
            outcome=outcome,
        )
    except Exception as e:
        logger.error("ingest_turn append failed: %s", e)
        return {"ok": False, "error": str(e), "content_hash": ch, "entry_id": None}

    if home:
        with _LOCK:
            cursor = load_cursor(home)
            mark_seen(cursor, ch)
            cursor["last_session_id"] = session_id
            save_cursor(home, cursor)

    return {
        "ok": True,
        "skipped": None,
        "content_hash": ch,
        "entry_id": getattr(added, "id", None),
        "event_id": event.event_id,
        "tool_count": len(tools),
    }


def reconcile_message_ids(
    hermes_home: str | Path,
    message_ids: Iterable[str],
) -> dict[str, Any]:
    """Record Hermes message ids as seen for future reconciliation passes."""
    with _LOCK:
        cursor = load_cursor(hermes_home)
        ids = list(cursor.get("hermes_message_ids") or [])
        existing = set(ids)
        added = 0
        for mid in message_ids:
            m = str(mid or "").strip()
            if m and m not in existing:
                ids.append(m)
                existing.add(m)
                added += 1
        if len(ids) > 10000:
            ids = ids[-10000:]
        cursor["hermes_message_ids"] = ids
        save_cursor(hermes_home, cursor)
        return {"ok": True, "added": added, "tracked": len(ids)}
