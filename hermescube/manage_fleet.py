"""Fleet manage actions — hive, HQ, interview."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

def handle_interview(provider: Any, args: dict[str, Any]) -> str:
    """Peer interview (interview-me protocol) at the Hive.

    dialogue — offline peer dialogue that inspects a subject soul,
    asks highest-value questions, produces a brief, optionally mints
    a consent-gated skill draft.
    list / mint — review past interviews / mint from a closed session.
    """
    hive_root = getattr(provider, "_hive_path", "") or os.environ.get(
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
        agent_id = provider._agent_identity or "hermes"

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
                subject_cube=provider._cube,
                hermes_home=provider._hermes_home or str(Path.home() / ".hermes"),
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
                hermes_home=provider._hermes_home or str(Path.home() / ".hermes"),
            )
            return json.dumps({"status": "mint", **r}, default=str)

        return json.dumps({"error": f"unknown interview_action: {sub}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_hq(provider: Any, args: dict[str, Any]) -> str:
    """Fleet HQ ops: route / charter / claim / handoffs / verify / baseline.

    Requires a configured hive (the hive root doubles as fleet HQ).
    """
    hive_root = getattr(provider, "_hive_path", "") or os.environ.get(
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
        agent_id = provider._agent_identity or "hermes"
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
            if provider._cube:
                packet = hq_mod.build_handoff_packet(
                    provider._cube, task, from_agent=agent_id, to_agent=to_agent
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

def handle_hive(provider: Any, args: dict[str, Any]) -> str:
    """Hive nexus ops: status / pilgrimage / draw / offer.

    Requires ``plugins.hermescube.hive_path`` (or HERMESCUBE_HIVE env).
    The hive is a shared directory; transport (NFS/sync) is operator's.
    """
    hive_root = (
        getattr(provider, "_hive_path", "")
        or os.environ.get("HERMESCUBE_HIVE", "")
    )
    if not hive_root:
        return json.dumps(
            {
                "error": "hive not configured",
                "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
            }
        )
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube import hive as hive_mod

        sub = str(args.get("hive_action") or args.get("content") or "status").strip()
        agent_id = provider._agent_identity or "hermes"
        if sub == "status":
            return json.dumps(
                {"status": "hive", **hive_mod.hive_status(hive_root)}, default=str
            )
        if sub == "offer":
            rows = hive_mod.build_offering(provider._cube, agent_id=agent_id)
            if not rows:
                return json.dumps({"status": "offer", "rows": 0})
            m = hive_mod.write_offering(hive_root, rows, agent_id=agent_id)
            return json.dumps({"status": "offer", **m}, default=str)
        if sub == "draw":
            r = hive_mod.draw_wisdom(
                hive_root,
                provider._cube,
                agent_id=agent_id,
                focus=str(args.get("focus") or ""),
            )
            if provider._engine:
                provider._engine.invalidate_cache()
            with provider._state_lock:
                provider._prefetch_cache.clear()
            return json.dumps({"status": "draw", **r}, default=str)
        if sub == "pilgrimage":
            do_interview = bool(
                args.get("interview")
                or getattr(provider, "_interview_on_pilgrimage", False)
            )
            r = hive_mod.pilgrimage(
                hive_root,
                hermes_home=provider._hermes_home or str(Path.home() / ".hermes"),
                agent_id=agent_id,
                focus=str(args.get("focus") or ""),
                interview=do_interview,
            )
            if provider._engine:
                provider._engine.invalidate_cache()
            with provider._state_lock:
                provider._prefetch_cache.clear()
            return json.dumps({"status": "pilgrimage", **r}, default=str)
        return json.dumps({"error": f"unknown hive_action: {sub}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

