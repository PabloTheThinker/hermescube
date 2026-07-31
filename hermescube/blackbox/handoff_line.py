"""Blackbox handoff line — holds continuity if the cube book is damaged.

Each handoff lifecycle event is sealed as:
  1) a small FlightRecord under memories/blackbox/handoffs/<id>-<event>.json
  2) an append-only JSONL line under memories/blackbox/handoff-line.jsonl

The JSONL is the 'hold the line' stream: recoverable without memory.cube.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hermescube.blackbox.flight import FlightEvent, FlightRecord, integrity_hash, new_record_id, utc_now
from hermescube.blackbox.redact import redact_obj


def blackbox_root(hermes_home: str | Path) -> Path:
    root = Path(hermes_home) / "memories" / "blackbox"
    (root / "handoffs").mkdir(parents=True, exist_ok=True)
    return root


def record_handoff_event(
    packet: dict[str, Any],
    *,
    event: str,
    hermes_home: str | Path,
    agent_id: str = "",
) -> dict[str, Any]:
    """Seal a handoff open/take/complete/abandon into the blackbox line."""
    home = Path(hermes_home)
    root = blackbox_root(home)
    hid = str(packet.get("id") or "unknown")
    ev = (event or "update").strip().lower()

    # Redact packet copy for storage
    safe_packet, n_red = redact_obj(packet)

    events = [
        FlightEvent(
            ts=utc_now(),
            kind="handoff",
            name=ev,
            summary=(packet.get("goal") or "")[:400],
            detail={
                "handoff_id": hid,
                "status": packet.get("status"),
                "severity": packet.get("severity"),
                "opened_by": packet.get("opened_by"),
                "taken_by": packet.get("taken_by"),
                "next_steps": packet.get("next_steps"),
                "blockers": packet.get("blockers"),
                "files": packet.get("files"),
                "completion_note": (packet.get("completion_note") or "")[:500],
            },
            refs={"handoff_id": hid, "session_id": packet.get("session_id") or ""},
        ).canonical(),
        FlightEvent(
            ts=utc_now(),
            kind="artifact",
            name="handoff_packet",
            summary=f"packet snapshot @ {ev}",
            detail=safe_packet,
            refs={"handoff_id": hid},
        ).canonical(),
    ]

    fid = new_record_id()
    integ = integrity_hash(events)
    rec = FlightRecord(
        id=fid,
        created_at=utc_now(),
        schema_version="hermescube.blackbox.handoff.v1",
        source={
            "kind": "handoff_line",
            "tool": "hermescube.blackbox.handoff_line",
            "agent_id": agent_id or packet.get("taken_by") or packet.get("opened_by") or "",
        },
        session={
            "session_id": packet.get("session_id") or "",
            "handoff_id": hid,
            "event": ev,
        },
        events=events,
        redactions_count=int(n_red or 0),
        integrity={
            **integ,
            "sealed_at": utc_now(),
        },
        meta={
            "holds_the_line": True,
            "purpose": "continuity if memory.cube is damaged",
            "handoff_id": hid,
        },
    )

    # 1) sealed flight file
    flight_path = root / "handoffs" / f"{hid}-{ev}-{fid[-8:]}.json"
    payload = rec.to_dict()
    flight_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        flight_path.chmod(0o600)
    except OSError:
        pass

    # 2) append-only hold-the-line stream (no vectors, plain JSONL)
    line = {
        "ts": utc_now(),
        "event": ev,
        "handoff_id": hid,
        "flight_id": fid,
        "goal": (packet.get("goal") or "")[:500],
        "status": packet.get("status"),
        "severity": packet.get("severity"),
        "next_steps": packet.get("next_steps") or [],
        "blockers": packet.get("blockers") or [],
        "files": packet.get("files") or [],
        "context": (packet.get("context") or "")[:1500],
        "opened_by": packet.get("opened_by"),
        "taken_by": packet.get("taken_by"),
        "session_id": packet.get("session_id"),
        "completion_note": (packet.get("completion_note") or "")[:500],
        "events_hash": integ.get("sha256"),
        "flight_path": str(flight_path),
    }
    line_path = root / "handoff-line.jsonl"
    with open(line_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    try:
        line_path.chmod(0o600)
    except OSError:
        pass

    return {
        "ok": True,
        "flight_id": fid,
        "flight_path": str(flight_path),
        "line_path": str(line_path),
        "events_hash": integ.get("sha256"),
        "redactions": n_red,
    }


def recover_handoffs_from_blackbox(
    hermes_home: str | Path,
    *,
    handoff_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Read the hold-the-line stream (works even if cube is gone)."""
    root = Path(hermes_home) / "memories" / "blackbox"
    line_path = root / "handoff-line.jsonl"
    if not line_path.is_file():
        return {"ok": True, "lines": [], "path": str(line_path), "note": "no handoff line yet"}
    rows: list[dict[str, Any]] = []
    for raw in line_path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if handoff_id and rec.get("handoff_id") != handoff_id:
            continue
        rows.append(rec)
    rows = rows[-limit:]
    return {
        "ok": True,
        "path": str(line_path),
        "count": len(rows),
        "lines": rows,
    }


def rebuild_open_from_blackbox(hermes_home: str | Path) -> dict[str, Any]:
    """If open/ packets missing but line has latest open/take, restore open JSON.

    Does not touch memory.cube. Safe recovery path when cube is messed up
    but blackbox handoff line survived.
    """
    from hermescube.handoff import handoffs_root

    home = Path(hermes_home)
    rec = recover_handoffs_from_blackbox(home, limit=500)
    lines = rec.get("lines") or []
    # last event per handoff_id
    latest: dict[str, dict[str, Any]] = {}
    for row in lines:
        hid = row.get("handoff_id")
        if hid:
            latest[str(hid)] = row

    restored = []
    root = handoffs_root(home)
    for hid, row in latest.items():
        status = (row.get("status") or row.get("event") or "").lower()
        # only restore if still open or taken
        if row.get("event") in ("complete", "abandon") or status in ("completed", "abandoned"):
            continue
        if status not in ("open", "taken") and row.get("event") not in ("open", "take"):
            continue
        packet = {
            "schema": "hermescube.handoff.v1",
            "id": hid,
            "status": "taken" if row.get("event") == "take" or status == "taken" else "open",
            "label": "recovered-from-blackbox",
            "goal": row.get("goal") or "",
            "next_steps": row.get("next_steps") or [],
            "blockers": row.get("blockers") or [],
            "files": row.get("files") or [],
            "context": (row.get("context") or "") + "\n[recovered from blackbox handoff-line]",
            "cube_evidence": [],
            "flight_id": row.get("flight_id") or "",
            "opened_by": row.get("opened_by") or "blackbox-recovery",
            "session_id": row.get("session_id") or "",
            "severity": row.get("severity") or "high",
            "created_at": row.get("ts") or utc_now(),
            "updated_at": utc_now(),
            "taken_by": row.get("taken_by") or "",
            "taken_at": row.get("ts") if row.get("event") == "take" else "",
            "completed_at": "",
            "completion_note": "",
            "recovered_from_blackbox": True,
        }
        path = root / "open" / f"{hid}.json"
        if path.is_file():
            continue
        path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        restored.append(hid)
    return {"ok": True, "restored": restored, "scanned": len(latest)}
