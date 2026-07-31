"""Agent continuity handoff — the 3am page when the agent breaks.

Problem (community): the model isn't the bottleneck — the *handoff* is.
When a Hermes agent dies mid-work, the next agent (or a fresh session)
needs a sealed brief from the cube — not a full transcript dump.

Design:
  $HERMES_HOME/memories/handoffs/
    open/<id>.json       live packets any connecting agent can take
    archive/<id>.json    completed / abandoned
    ledger.jsonl         audit trail

Any agent that dials this HERMES_HOME sees open handoffs on connect.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "hermescube.handoff.v1"
STUCK_HOURS = 48.0


def _utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _home(hermes_home: str | Path | None = None) -> Path:
    from hermescube.security import resolve_hermes_home

    return resolve_hermes_home(hermes_home)


def handoffs_root(hermes_home: str | Path | None = None) -> Path:
    root = _home(hermes_home) / "memories" / "handoffs"
    (root / "open").mkdir(parents=True, exist_ok=True)
    (root / "archive").mkdir(parents=True, exist_ok=True)
    return root


def _ledger_append(home: Path, rec: dict[str, Any]) -> None:
    path = handoffs_root(home) / "ledger.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "work").strip().lower()).strip("-")
    return (s[:n] or "work").rstrip("-")


def _blackbox_seal(home: Path, packet: dict[str, Any], event: str, agent_id: str = "") -> dict[str, Any]:
    """Record handoff into unified blackbox hold-the-line rail."""
    try:
        from hermescube.blackbox.hold_line import seal_from_handoff_packet

        bb = seal_from_handoff_packet(
            packet,
            event=event,
            hermes_home=home,
            agent_id=agent_id,
        )
        if bb.get("flight_id"):
            packet["flight_id"] = bb["flight_id"]
            packet["blackbox"] = {
                "flight_id": bb.get("flight_id"),
                "flight_path": bb.get("seal_path") or bb.get("flight_path"),
                "events_hash": bb.get("events_hash"),
                "line_path": bb.get("line_path"),
            }
        return bb
    except Exception as e:
        # fallback to legacy handoff_line
        try:
            from hermescube.blackbox.handoff_line import record_handoff_event

            return record_handoff_event(
                packet, event=event, hermes_home=home, agent_id=agent_id
            )
        except Exception as e2:
            return {"ok": False, "error": f"{e}; fallback {e2}"}


def open_handoff(
    *,
    goal: str,
    hermes_home: str | Path | None = None,
    next_steps: list[str] | None = None,
    blockers: list[str] | None = None,
    files: list[str] | None = None,
    context: str = "",
    agent_id: str = "",
    session_id: str = "",
    flight_id: str = "",
    cube_evidence: list[str] | None = None,
    severity: str = "normal",
    label: str = "",
) -> dict[str, Any]:
    """Create an open continuity packet for the next agent."""
    home = _home(hermes_home)
    hid = f"ho_{uuid.uuid4().hex[:12]}"
    goal_s = (goal or "").strip()
    if not goal_s:
        return {"ok": False, "error": "goal required"}
    packet = {
        "schema": SCHEMA,
        "id": hid,
        "status": "open",
        "label": label or _slug(goal_s),
        "goal": goal_s[:2000],
        "next_steps": [str(x)[:500] for x in (next_steps or [])][:12],
        "blockers": [str(x)[:500] for x in (blockers or [])][:12],
        "files": [str(x)[:400] for x in (files or [])][:30],
        "context": (context or "")[:4000],
        "cube_evidence": [str(x)[:200] for x in (cube_evidence or [])][:20],
        "flight_id": flight_id or "",
        "opened_by": agent_id or os.environ.get("HERMES_AGENT_ID") or "unknown",
        "session_id": session_id or "",
        "severity": severity if severity in ("low", "normal", "high", "critical") else "normal",
        "created_at": _utc(),
        "updated_at": _utc(),
        "taken_by": "",
        "taken_at": "",
        "completed_at": "",
        "completion_note": "",
    }
    path = handoffs_root(home) / "open" / f"{hid}.json"
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    _ledger_append(
        home,
        {"ts": _utc(), "event": "open", "id": hid, "goal": goal_s[:200], "agent": packet["opened_by"]},
    )
    # Blackbox holds the line (independent of memory.cube)
    bb = _blackbox_seal(home, packet, "open", agent_id=packet["opened_by"])
    if packet.get("blackbox"):
        path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    # landmark in cube if available
    try:
        from hermescube.cube import CubeFile

        cube_path = home / "memories" / "memory.cube"
        if cube_path.is_file():
            with CubeFile.open(str(cube_path)) as cube:
                cube.append(
                    entry_type="focus",
                    description=f"[HANDOFF OPEN] {goal_s[:180]}",
                    data={
                        "handoff_id": hid,
                        "kind": "agent_continuity",
                        "status": "open",
                        "session_id": session_id,
                        "flight_id": packet.get("flight_id") or "",
                    },
                    outcome="pending",
                )
    except Exception:
        pass
    return {"ok": True, "id": hid, "path": str(path), "packet": packet, "blackbox": bb}


def list_open(hermes_home: str | Path | None = None) -> list[dict[str, Any]]:
    home = _home(hermes_home)
    root = handoffs_root(home) / "open"
    out: list[dict[str, Any]] = []
    for p in sorted(root.glob("ho_*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def get_handoff(handoff_id: str, hermes_home: str | Path | None = None) -> dict[str, Any] | None:
    home = _home(hermes_home)
    for sub in ("open", "archive"):
        p = handoffs_root(home) / sub / f"{handoff_id}.json"
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def take_handoff(
    handoff_id: str,
    *,
    agent_id: str = "",
    hermes_home: str | Path | None = None,
) -> dict[str, Any]:
    """Claim an open handoff for the connecting agent."""
    home = _home(hermes_home)
    path = handoffs_root(home) / "open" / f"{handoff_id}.json"
    if not path.is_file():
        return {"ok": False, "error": f"open handoff not found: {handoff_id}"}
    packet = json.loads(path.read_text(encoding="utf-8"))
    if packet.get("status") not in ("open", "taken"):
        return {"ok": False, "error": f"not takeable: status={packet.get('status')}"}
    packet["status"] = "taken"
    packet["taken_by"] = agent_id or "agent"
    packet["taken_at"] = _utc()
    packet["updated_at"] = _utc()
    bb = _blackbox_seal(home, packet, "take", agent_id=packet["taken_by"])
    path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    _ledger_append(
        home,
        {"ts": _utc(), "event": "take", "id": handoff_id, "agent": packet["taken_by"], "flight_id": packet.get("flight_id")},
    )
    return {"ok": True, "packet": packet, "prompt": format_prompt_strip([packet]), "blackbox": bb}


def complete_handoff(
    handoff_id: str,
    *,
    note: str = "",
    agent_id: str = "",
    hermes_home: str | Path | None = None,
    abandon: bool = False,
) -> dict[str, Any]:
    home = _home(hermes_home)
    src = handoffs_root(home) / "open" / f"{handoff_id}.json"
    if not src.is_file():
        return {"ok": False, "error": f"open handoff not found: {handoff_id}"}
    packet = json.loads(src.read_text(encoding="utf-8"))
    packet["status"] = "abandoned" if abandon else "completed"
    packet["completed_at"] = _utc()
    packet["updated_at"] = _utc()
    packet["completion_note"] = (note or "")[:2000]
    if agent_id:
        packet["closed_by"] = agent_id
    bb = _blackbox_seal(
        home,
        packet,
        "abandon" if abandon else "complete",
        agent_id=agent_id or packet.get("taken_by") or "",
    )
    dest = handoffs_root(home) / "archive" / f"{handoff_id}.json"
    dest.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    try:
        dest.chmod(0o600)
        src.unlink()
    except OSError:
        pass
    _ledger_append(
        home,
        {
            "ts": _utc(),
            "event": packet["status"],
            "id": handoff_id,
            "agent": agent_id or packet.get("taken_by") or "",
            "note": (note or "")[:200],
            "flight_id": packet.get("flight_id"),
        },
    )
    try:
        from hermescube.cube import CubeFile

        cube_path = home / "memories" / "memory.cube"
        if cube_path.is_file():
            with CubeFile.open(str(cube_path)) as cube:
                cube.append(
                    entry_type="resolve",
                    description=f"[HANDOFF {packet['status'].upper()}] {packet.get('goal', '')[:160]}",
                    data={
                        "handoff_id": handoff_id,
                        "kind": "agent_continuity",
                        "status": packet["status"],
                        "flight_id": packet.get("flight_id") or "",
                    },
                    outcome="success" if not abandon else "none",
                )
    except Exception:
        pass
    return {"ok": True, "packet": packet, "blackbox": bb}


def format_prompt_strip(packets: list[dict[str, Any]], *, limit: int = 5) -> str:
    """Compact strip for system/prefetch injection — continuity, not a novel."""
    if not packets:
        return ""
    lines = [
        "<agent-handoff>",
        "Open continuity packets from HermesCube (prior agent may have broken).",
        "Take work with hermescube_handoff action=take, finish with action=complete.",
        "",
    ]
    for p in packets[:limit]:
        lines.append(f"### {p.get('id')} · {p.get('status')} · {p.get('severity', 'normal')}")
        lines.append(f"Goal: {p.get('goal', '')}")
        if p.get("blockers"):
            lines.append("Blockers: " + "; ".join(p["blockers"][:5]))
        if p.get("next_steps"):
            lines.append("Next: " + "; ".join(p["next_steps"][:5]))
        if p.get("files"):
            lines.append("Files: " + ", ".join(p["files"][:8]))
        if p.get("context"):
            lines.append("Context: " + str(p["context"])[:400])
        lines.append("")
    lines.append("</agent-handoff>")
    return "\n".join(lines)


def status_report(hermes_home: str | Path | None = None) -> dict[str, Any]:
    home = _home(hermes_home)
    open_p = list_open(home)
    now = time.time()
    stuck = []
    for p in open_p:
        try:
            created = p.get("created_at") or ""
            # rough age from ISO
            if created.endswith("Z"):
                created = created[:-1] + "+00:00"
            ts = datetime.fromisoformat(created).timestamp()
            age_h = (now - ts) / 3600.0
            if age_h >= STUCK_HOURS:
                stuck.append({"id": p["id"], "age_hours": round(age_h, 1), "goal": p.get("goal", "")[:120]})
        except Exception:
            continue
    return {
        "ok": True,
        "open": len(open_p),
        "stuck": stuck,
        "packets": [
            {
                "id": p.get("id"),
                "goal": (p.get("goal") or "")[:120],
                "status": p.get("status"),
                "severity": p.get("severity"),
                "opened_by": p.get("opened_by"),
                "created_at": p.get("created_at"),
            }
            for p in open_p[:20]
        ],
        "prompt": format_prompt_strip(open_p),
    }


def auto_snapshot_from_session(
    *,
    hermes_home: str | Path | None = None,
    messages: list[dict[str, Any]] | None = None,
    agent_id: str = "",
    session_id: str = "",
    min_user_chars: int = 40,
) -> dict[str, Any]:
    """If the session looks unfinished, open a handoff automatically.

    Heuristic: last user message looks like a task and assistant did not
    clearly close with done/complete — 3am crash insurance.
    """
    msgs = messages or []
    if len(msgs) < 2:
        return {"ok": True, "opened": False, "reason": "too_short"}

    last_user = ""
    last_asst = ""
    for m in reversed(msgs):
        role = (m.get("role") or "").lower()
        content = m.get("content")
        if isinstance(content, list):
            content = " ".join(
                str(p.get("text") or "") for p in content if isinstance(p, dict)
            )
        text = str(content or "").strip()
        if role == "user" and not last_user:
            last_user = text
        elif role == "assistant" and not last_asst:
            last_asst = text
        if last_user and last_asst:
            break

    if len(last_user) < min_user_chars:
        return {"ok": True, "opened": False, "reason": "no_task_signal"}

    closed = any(
        w in last_asst.lower()
        for w in (
            "done.",
            "all set",
            "completed",
            "shipped",
            "nothing else",
            "you're good",
            "you are good",
            "handoff complete",
        )
    )
    # task-ish user
    taskish = any(
        w in last_user.lower()
        for w in (
            "fix",
            "build",
            "implement",
            "debug",
            "deploy",
            "please",
            "continue",
            "finish",
            "ship",
            "error",
            "broken",
            "failing",
        )
    )
    if closed or not taskish:
        return {"ok": True, "opened": False, "reason": "looks_closed_or_chat"}

    # evidence from cube
    evidence: list[str] = []
    try:
        from hermescube.cube import CubeFile

        home = _home(hermes_home)
        cp = home / "memories" / "memory.cube"
        if cp.is_file():
            with CubeFile.open(str(cp)) as cube:
                for e in list(cube.read_l1() or [])[-8:]:
                    d = (getattr(e, "description", "") or "")[:120]
                    if d:
                        evidence.append(d)
    except Exception:
        pass

    files = sorted(set(re.findall(r"(?:[\w./-]+\.(?:py|ts|tsx|js|md|yaml|yml|json|toml))", last_user + "\n" + last_asst)))[:15]
    goal = last_user[:500]
    next_steps = []
    if last_asst:
        # pull lines that look like next actions
        for line in last_asst.splitlines():
            s = line.strip()
            if s.startswith(("- ", "* ", "1.", "2.", "Next")):
                next_steps.append(s.lstrip("-* 0123456789.")[:200])
            if len(next_steps) >= 5:
                break

    return open_handoff(
        goal=goal,
        hermes_home=hermes_home,
        next_steps=next_steps or ["Resume from last user goal; check blockers and files."],
        blockers=[],
        files=files,
        context=f"Auto snapshot. Last assistant tail:\n{last_asst[:1200]}",
        agent_id=agent_id,
        session_id=session_id,
        cube_evidence=evidence,
        severity="high",
        label="auto-session-end",
    )


def connect_brief(hermes_home: str | Path | None = None) -> str:
    """What any connecting agent should see first."""
    return status_report(hermes_home).get("prompt") or ""
