"""Hold the line — one blackbox rail for all of HermesCube.

If memory.cube is damaged, this stream still has the spine of what mattered:

  $HERMES_HOME/memories/blackbox/hold-the-line.jsonl   # append-only SoT line
  $HERMES_HOME/memories/blackbox/seals/<organ>-*.json   # integrity flights

Organs that seal here: handoff, checkpoint, connect, security, cube_critical,
flight, breathe, session, provider_flush, doctor.

Handoff-specific path (handoff-line.jsonl) remains for back-compat and also
mirrors into this unified line.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from hermescube.blackbox.flight import (
    FlightEvent,
    FlightRecord,
    integrity_hash,
    new_record_id,
    utc_now,
)
from hermescube.blackbox.redact import redact_obj

_LOCK = threading.RLock()

# Critical cube entry types that dual-write a short seal (not every landmark)
CRITICAL_ENTRY_TYPES = frozenset(
    {
        "resolve",
        "belief",
        "trait",
        "focus",
        "relationship",
        "evolution",
    }
)

LINE_NAME = "hold-the-line.jsonl"
SEALS_DIR = "seals"


def blackbox_root(hermes_home: str | Path) -> Path:
    root = Path(hermes_home) / "memories" / "blackbox"
    (root / SEALS_DIR).mkdir(parents=True, exist_ok=True)
    (root / "handoffs").mkdir(parents=True, exist_ok=True)
    return root


def line_path(hermes_home: str | Path) -> Path:
    return blackbox_root(hermes_home) / LINE_NAME


def record(
    *,
    hermes_home: str | Path,
    organ: str,
    event: str,
    summary: str = "",
    payload: dict[str, Any] | None = None,
    agent_id: str = "",
    session_id: str = "",
    ref_id: str = "",
    severity: str = "normal",
    also_handoff_line: bool = False,
) -> dict[str, Any]:
    """Seal one organ event onto the unified hold-the-line rail."""
    home = Path(hermes_home)
    root = blackbox_root(home)
    organ_s = (organ or "cube").strip().lower()[:40]
    event_s = (event or "event").strip().lower()[:40]
    payload = dict(payload or {})
    safe_payload, n_red = redact_obj(payload)

    events = [
        FlightEvent(
            ts=utc_now(),
            kind=organ_s,
            name=event_s,
            summary=(summary or "")[:500],
            detail=safe_payload if isinstance(safe_payload, dict) else {"value": safe_payload},
            refs={"ref_id": ref_id, "session_id": session_id or "", "organ": organ_s},
        ).canonical()
    ]
    fid = new_record_id()
    integ = integrity_hash(events)
    rec = FlightRecord(
        id=fid,
        created_at=utc_now(),
        schema_version="hermescube.blackbox.hold.v1",
        source={
            "kind": "hold_the_line",
            "organ": organ_s,
            "tool": "hermescube.blackbox.hold_line",
            "agent_id": agent_id or "",
        },
        session={"session_id": session_id or "", "ref_id": ref_id or "", "event": event_s},
        events=events,
        redactions_count=int(n_red or 0),
        integrity={**integ, "sealed_at": utc_now()},
        meta={
            "holds_the_line": True,
            "organ": organ_s,
            "event": event_s,
            "severity": severity,
        },
    )

    seal_path = root / SEALS_DIR / f"{organ_s}-{event_s}-{fid[-10:]}.json"
    with _LOCK:
        seal_path.write_text(
            json.dumps(rec.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        try:
            seal_path.chmod(0o600)
        except OSError:
            pass

        line = {
            "ts": utc_now(),
            "organ": organ_s,
            "event": event_s,
            "summary": (summary or "")[:500],
            "ref_id": ref_id or "",
            "flight_id": fid,
            "session_id": session_id or "",
            "agent_id": agent_id or "",
            "severity": severity,
            "payload": safe_payload if isinstance(safe_payload, dict) else {},
            "events_hash": integ.get("sha256"),
            "seal_path": str(seal_path),
        }
        lp = root / LINE_NAME
        with open(lp, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        try:
            lp.chmod(0o600)
        except OSError:
            pass

        if also_handoff_line or organ_s == "handoff":
            hlp = root / "handoff-line.jsonl"
            # compact handoff-compatible row
            hrow = {
                "ts": line["ts"],
                "event": event_s,
                "handoff_id": ref_id or (safe_payload or {}).get("id") or "",
                "flight_id": fid,
                "goal": (summary or "")[:500],
                "status": (safe_payload or {}).get("status") or event_s,
                "severity": severity,
                "next_steps": (safe_payload or {}).get("next_steps") or [],
                "blockers": (safe_payload or {}).get("blockers") or [],
                "files": (safe_payload or {}).get("files") or [],
                "context": str((safe_payload or {}).get("context") or "")[:1500],
                "opened_by": (safe_payload or {}).get("opened_by") or agent_id,
                "taken_by": (safe_payload or {}).get("taken_by") or "",
                "session_id": session_id or "",
                "completion_note": str((safe_payload or {}).get("completion_note") or "")[:500],
                "events_hash": integ.get("sha256"),
                "flight_path": str(seal_path),
                "organ": "handoff",
            }
            with open(hlp, "a", encoding="utf-8") as f:
                f.write(json.dumps(hrow, ensure_ascii=False) + "\n")
            try:
                hlp.chmod(0o600)
            except OSError:
                pass

    return {
        "ok": True,
        "flight_id": fid,
        "seal_path": str(seal_path),
        "line_path": str(root / LINE_NAME),
        "events_hash": integ.get("sha256"),
        "redactions": n_red,
        "organ": organ_s,
        "event": event_s,
    }


def tail(
    hermes_home: str | Path,
    *,
    organ: str | None = None,
    limit: int = 40,
) -> dict[str, Any]:
    lp = line_path(hermes_home)
    if not lp.is_file():
        return {"ok": True, "lines": [], "path": str(lp), "count": 0}
    rows: list[dict[str, Any]] = []
    for raw in lp.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if organ and rec.get("organ") != organ:
            continue
        rows.append(rec)
    rows = rows[-max(1, limit) :]
    return {"ok": True, "path": str(lp), "count": len(rows), "lines": rows}


def status(hermes_home: str | Path) -> dict[str, Any]:
    lp = line_path(hermes_home)
    root = blackbox_root(hermes_home)
    n = 0
    organs: dict[str, int] = {}
    if lp.is_file():
        for raw in lp.read_text(encoding="utf-8", errors="replace").splitlines():
            if not raw.strip():
                continue
            n += 1
            try:
                o = json.loads(raw).get("organ") or "?"
            except json.JSONDecodeError:
                o = "?"
            organs[o] = organs.get(o, 0) + 1
    seals = list((root / SEALS_DIR).glob("*.json")) if (root / SEALS_DIR).is_dir() else []
    return {
        "ok": True,
        "line_path": str(lp),
        "line_events": n,
        "organs": organs,
        "seals": len(seals),
        "holds_the_line": True,
        "note": "Unified blackbox rail for all HermesCube organs. Survives memory.cube loss.",
    }


def seal_cube_entry(
    hermes_home: str | Path,
    *,
    entry_type: str,
    description: str,
    entry_id: str = "",
    data: dict[str, Any] | None = None,
    outcome: str = "",
    agent_id: str = "",
    session_id: str = "",
) -> dict[str, Any] | None:
    """Seal critical durable cube writes only (skip chitchat landmarks)."""
    et = (entry_type or "").lower()
    if et not in CRITICAL_ENTRY_TYPES:
        # always seal handoff-tagged descriptions
        if not (description or "").startswith("[HANDOFF"):
            return None
        et = "handoff"
    return record(
        hermes_home=hermes_home,
        organ="cube",
        event=f"append_{et}",
        summary=(description or "")[:400],
        payload={
            "entry_type": entry_type,
            "entry_id": entry_id,
            "outcome": outcome,
            "data_keys": list((data or {}).keys())[:20],
            "snippet": (description or "")[:300],
        },
        agent_id=agent_id,
        session_id=session_id,
        ref_id=entry_id or "",
        severity="high" if et in ("resolve", "focus") else "normal",
    )


def seal_from_handoff_packet(
    packet: dict[str, Any],
    *,
    event: str,
    hermes_home: str | Path,
    agent_id: str = "",
) -> dict[str, Any]:
    """Bridge for handoff module — one call into the unified rail."""
    return record(
        hermes_home=hermes_home,
        organ="handoff",
        event=event,
        summary=str(packet.get("goal") or "")[:500],
        payload=packet,
        agent_id=agent_id or str(packet.get("taken_by") or packet.get("opened_by") or ""),
        session_id=str(packet.get("session_id") or ""),
        ref_id=str(packet.get("id") or ""),
        severity=str(packet.get("severity") or "normal"),
        also_handoff_line=True,
    )
