"""Capture Hermes state.db sessions into FlightRecords."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from hermescube.blackbox.flight import (
    FlightEvent,
    FlightRecord,
    integrity_hash,
    new_record_id,
    utc_now,
)
from hermescube.blackbox.redact import redact_obj, redact_text


def _default_state_db() -> Path:
    home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
    return Path(home) / "state.db"


def _summarize(text: str | None, limit: int = 240) -> str | None:
    if not text:
        return None
    t = " ".join(text.split())
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return value
        if s[0] in "[{":
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return value
    return value


def _resolve_session(
    con: sqlite3.Connection,
    *,
    session_id: str | None,
    title: str | None,
    latest: bool,
) -> sqlite3.Row:
    if latest or (not session_id and not title):
        # Hermes state.db: started_at / ended_at (not updated_at)
        for sql in (
            "SELECT * FROM sessions ORDER BY COALESCE(ended_at, started_at) DESC, id DESC LIMIT 1",
            "SELECT * FROM sessions ORDER BY started_at DESC, id DESC LIMIT 1",
            "SELECT * FROM sessions ORDER BY id DESC LIMIT 1",
        ):
            try:
                row = con.execute(sql).fetchone()
                if row:
                    return row
            except sqlite3.OperationalError:
                continue
        raise RuntimeError("No sessions in state.db")
    if session_id:
        row = con.execute(
            "SELECT * FROM sessions WHERE id = ? OR id LIKE ? LIMIT 1",
            (session_id, f"{session_id}%"),
        ).fetchone()
        if row:
            return row
    if title:
        row = con.execute(
            "SELECT * FROM sessions WHERE title LIKE ? OR display_name LIKE ? ORDER BY id DESC LIMIT 1",
            (f"%{title}%", f"%{title}%"),
        ).fetchone()
        if row:
            return row
    raise RuntimeError(f"Session not found: id={session_id!r} title={title!r}")


def capture_session(
    session_id: str | None = None,
    *,
    db_path: str | Path | None = None,
    title: str | None = None,
    latest: bool = False,
    include_system: bool = False,
    max_events: int | None = None,
    redact: bool = True,
) -> FlightRecord:
    path = Path(db_path) if db_path else _default_state_db()
    if not path.exists():
        raise FileNotFoundError(f"Hermes state DB not found: {path}")

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        # discover columns
        cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)").fetchall()}
        session_row = _resolve_session(
            con, session_id=session_id, title=title, latest=latest
        )
        sid = session_row["id"]
        rows = con.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,)
        ).fetchall()
    finally:
        con.close()

    events: list[dict[str, Any]] = []
    redactions = 0
    for row in rows:
        role = (row["role"] or "").lower()
        content = row["content"] if "content" in row.keys() else None
        tool_calls_raw = row["tool_calls"] if "tool_calls" in row.keys() else None
        tool_name = row["tool_name"] if "tool_name" in row.keys() else None
        ts = None
        for k in ("timestamp", "created_at", "ts"):
            if k in row.keys() and row[k] is not None:
                ts = str(row[k])
                break

        if role == "system" and not include_system:
            if not any(e.get("kind") == "system_meta" for e in events):
                events.append(
                    FlightEvent(
                        ts=ts,
                        kind="system_meta",
                        name="system_prompt",
                        summary="system prompt present (content omitted by default)",
                        detail={"omitted": True, "chars": len(content or "")},
                    ).canonical()
                )
            continue

        tool_calls = _parse_jsonish(tool_calls_raw)
        detail: Any
        kind: str
        name: str | None = tool_name

        if role == "tool":
            kind = "tool_result"
            detail = _parse_jsonish(content)
            summary = _summarize(
                content if isinstance(content, str) else json.dumps(detail, default=str)
            )
        elif tool_calls:
            kind = "tool_call"
            detail = tool_calls
            names = []
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
                        names.append(fn.get("name") or tc.get("name") or "tool")
            name = ",".join(names) if names else name
            summary = f"tool_call: {name}" if name else "tool_call"
        elif role == "user":
            kind = "user"
            detail = content
            summary = _summarize(content if isinstance(content, str) else str(content))
        elif role == "assistant":
            kind = "assistant"
            detail = content
            summary = _summarize(content if isinstance(content, str) else str(content))
        else:
            kind = role or "message"
            detail = content
            summary = _summarize(content if isinstance(content, str) else str(content))

        refs = {"message_id": row["id"] if "id" in row.keys() else None}
        if redact:
            detail, n1 = redact_obj(detail)
            summary, n2 = redact_text(summary)
            redactions += n1 + n2
        events.append(
            FlightEvent(
                ts=ts, kind=kind, name=name, summary=summary, detail=detail, refs=refs
            ).canonical()
        )
        if max_events and len(events) >= max_events:
            break

    session_meta = {
        "id": sid,
        "title": session_row["title"] if "title" in session_row.keys() else None,
        "model": session_row["model"] if "model" in session_row.keys() else None,
        "source": session_row["source"] if "source" in session_row.keys() else None,
    }
    if redact:
        session_meta, n = redact_obj(session_meta)
        redactions += n

    record = FlightRecord(
        id=new_record_id(),
        created_at=utc_now(),
        schema_version="1.0",
        source={"type": "hermes_state_db", "path": str(path), "cube_organ": "blackbox"},
        session=session_meta,
        events=events,
        redactions_count=redactions,
        integrity=integrity_hash(events),
        meta={"engine": "hermescube.blackbox", "inspired_by": "asimons81/hermes-blackbox"},
    )
    return record


def save_record(record: FlightRecord | dict[str, Any], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = record.to_dict() if isinstance(record, FlightRecord) else record
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")
    return p


def load_record(path: str | Path) -> FlightRecord:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return FlightRecord.from_dict(data)
