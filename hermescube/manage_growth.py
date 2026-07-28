"""Growth / living manage actions — genealogy, consent, pulse, forge, observe."""

from __future__ import annotations

import json
from typing import Any

def handle_curate(provider: Any, args: dict[str, Any]) -> str:
    """Run the growth curator — refine skills from lessons, forge/garden."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    try:
        from hermescube.curator import run_curator

        lesson = str(args.get("content") or args.get("query") or "").strip()
        lessons = [lesson] if lesson else []
        # Also pull recent hive draws from the cube as lessons
        if provider._cube and not lessons:
            for e in list(provider._cube.read_l1() or [])[-40:]:
                desc = e.description or ""
                if desc.startswith("[HIVE:") or desc.startswith("[INTERVIEW:"):
                    lessons.append(desc)
        force_era = str(args.get("mode") or "").lower() == "milestone"
        report = run_curator(
            provider._hermes_home,
            cube=provider._cube,
            lessons=lessons[-12:],
            era_milestone=force_era,
        )
        provider._refresh_maturity()
        return json.dumps({"status": "curate", **report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


def handle_growth(provider: Any, args: dict[str, Any]) -> str:
    """Living cube genealogy — version, strength, eras, skill lineage."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    sub = str(args.get("content") or args.get("mode") or "status").strip().lower()
    try:
        from hermescube import genealogy as gen

        if sub in ("status", "", "show"):
            return json.dumps(
                {"status": "growth", **gen.growth_status(
                    provider._hermes_home, cube=provider._cube
                )},
                default=str,
            )
        if sub == "epochs":
            return json.dumps(
                {
                    "status": "epochs",
                    "epochs": gen.list_epochs(provider._hermes_home, limit=30),
                },
                default=str,
            )
        if sub.startswith("refine:"):
            # refine:<skill_name> — lesson in mode/query fields
            skill = sub.split(":", 1)[1].strip()
            lesson = str(args.get("query") or args.get("description") or "").strip()
            if not lesson:
                return json.dumps({"error": "lesson text required in query"})
            return json.dumps(
                {
                    "status": "refine",
                    **gen.refine_skill(
                        provider._hermes_home,
                        skill,
                        lesson=lesson,
                        cube=provider._cube,
                    ),
                },
                default=str,
            )
        return json.dumps({"error": f"unknown growth subcommand: {sub}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_witness(provider: Any, args: dict[str, Any]) -> str:
    """Record real friction in the witness ledger (grounded evolution)."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    content = str(args.get("content") or "").strip()
    if not content:
        return json.dumps({"error": "content required (describe the friction)"})
    try:
        from hermescube.self_evolution import record_witness

        rec = record_witness(
            provider._hermes_home,
            content,
            severity=str(args.get("severity") or "medium"),
            kind="manual",
            session_id=provider._session_id,
            source="manage",
        )
        return json.dumps({"status": "witness", "recorded": rec}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_harness(provider: Any, args: dict[str, Any]) -> str:
    """Self-evolution harness ops: status / critic / gardener / verify."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    try:
        from hermescube import self_evolution as se

        sub = str(
            args.get("harness_action") or args.get("content") or "status"
        ).strip()
        if sub == "status":
            return json.dumps(
                {"status": "harness", **se.harness_status(provider._hermes_home)},
                default=str,
            )
        if sub == "critic":
            return json.dumps(
                {"status": "critic", **se.run_critic(provider._hermes_home)},
                default=str,
            )
        if sub == "verify":
            stats = se.verify_predictions(provider._hermes_home, cube=provider._cube)
            return json.dumps({"status": "verify", **stats}, default=str)
        if sub == "gardener":
            if not provider._cube:
                return json.dumps({"error": "Memory not initialized"})
            r = se.run_gardener(provider._cube, provider._hermes_home)
            return json.dumps({"status": "gardener", **r}, default=str)
        return json.dumps({"error": f"unknown harness_action: {sub}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_pulse(provider: Any, args: dict[str, Any]) -> str:
    """Multi-chamber living pulse — catalog, connect dots, peer, doctrine."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.living import chamber_pulse

        report = chamber_pulse(
            provider._cube,
            hermes_home=provider._hermes_home,
            engram=getattr(provider, "_engram", None),
            max_connect=int(args.get("max_connect") or 4),
            do_crystalize=bool(args.get("crystalize", True)),
            do_peer=bool(args.get("peer", True)),
            **provider._path_kw(),
        )
        if report.get("ok"):
            provider._prefetch_cache.clear()
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
        return json.dumps({"status": "pulse", "report": report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_promote(provider: Any, args: dict[str, Any]) -> str:
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.consent import promote

        name = str(args.get("name") or args.get("content") or "").strip()
        if not name:
            return json.dumps({"error": "name required (draft filename)"})
        install = bool(
            args.get("install_to_skills")
            or args.get("install")
            or False
        )
        overwrite = bool(args.get("overwrite") or False)
        r = promote(
            name,
            hermes_home=provider._hermes_home,
            cube=provider._cube,
            install_to_skills=install,
            overwrite=overwrite,
        )
        # Falsifiable prediction: promoted procedure must earn trust
        if r.get("ok") and provider._hermes_home:
            try:
                from hermescube.self_evolution import make_prediction

                entry_id = str(r.get("entry_id") or "")
                if entry_id:
                    make_prediction(
                        provider._hermes_home,
                        f"promoted procedure '{name}' earns trust >= 0.6",
                        check={
                            "type": "entry_feedback",
                            "entry_id": entry_id,
                            "min_trust": 0.6,
                        },
                        source=f"promote:{name}",
                    )
            except Exception:
                pass
            # Living version advances on promote; skill_bridge records
            # skill_install itself so we don't double-bump.
            if not r.get("installed"):
                try:
                    from hermescube.genealogy import record_growth

                    record_growth(
                        provider._hermes_home,
                        "promote",
                        detail=f"promote: {name}",
                        cube=provider._cube,
                    )
                except Exception:
                    pass
        return json.dumps({"status": "promote", **r})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_reject(provider: Any, args: dict[str, Any]) -> str:
    try:
        from hermescube.consent import reject

        name = str(args.get("name") or args.get("content") or "").strip()
        if not name:
            return json.dumps({"error": "name required"})
        r = reject(
            name,
            hermes_home=provider._hermes_home,
            reason=str(args.get("reason") or ""),
        )
        return json.dumps({"status": "reject", **r})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_drafts(provider: Any, args: dict[str, Any]) -> str:
    try:
        from hermescube.consent import list_pending

        return json.dumps(
            {"status": "ok", "pending": list_pending(provider._hermes_home)}
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_peer(provider: Any, args: dict[str, Any]) -> str:
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.peer_card import refresh_card, load_card

        force = bool(args.get("force") or args.get("refresh"))
        ents = list(provider._cube.read_l1() or [])
        if force:
            r = refresh_card(
                ents,
                hermes_home=provider._hermes_home,
                peer_name=provider._agent_identity or "user",
                min_interval_s=0,
            )
        else:
            card = load_card(provider._hermes_home)
            if not card:
                r = refresh_card(
                    ents,
                    hermes_home=provider._hermes_home,
                    peer_name=provider._agent_identity or "user",
                    min_interval_s=0,
                )
            else:
                r = {"skipped": True, "card": card}
        return json.dumps({"status": "ok", **{k: v for k, v in r.items() if k != "card"}, "card": r.get("card")})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_observe(provider: Any, args: dict[str, Any]) -> str:
    """Forge procedure drafts from tool trajectories in provided messages or last note."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.trajectory import observe_messages, extract_trajectories

        messages = args.get("messages")
        if not messages and args.get("tools"):
            # synthetic: list of tool names
            names = args.get("tools") or []
            if isinstance(names, str):
                names = [n.strip() for n in names.split(",") if n.strip()]
            goal = str(args.get("goal") or args.get("content") or "manual observe")
            messages = [
                {"role": "user", "content": goal},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": n, "arguments": "{}"}} for n in names
                    ],
                },
            ]
        if not messages:
            return json.dumps(
                {
                    "error": "messages or tools required",
                    "hint": "pass tools=['terminal','patch','pytest'] goal='...'",
                }
            )
        min_tools = int(args.get("min_tools") or 3)
        stats = observe_messages(
            provider._cube,
            messages,
            hermes_home=provider._hermes_home,
            min_tools=min_tools,
            max_forge=int(args.get("max_forge") or 3),
            write_drafts=bool(args.get("write_drafts", True)),
        )
        preview = extract_trajectories(messages, min_tools=min_tools)
        if stats.get("forged"):
            provider._prefetch_cache.clear()
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
        return json.dumps(
            {
                "status": "observed",
                "stats": stats,
                "preview": [
                    {
                        "goal": t.get("goal"),
                        "tools": t.get("tool_names"),
                        "fp": t.get("fingerprint"),
                    }
                    for t in preview[:5]
                ],
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_intents(provider: Any, args: dict[str, Any]) -> str:
    """List open prospective focuses; optional close by id."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.prospective import open_focuses, close_focus, status

        ents = list(provider._cube.read_l1() or [])
        close_id = (args.get("close_id") or args.get("entry_id") or "").strip()
        if close_id:
            focus = next((e for e in ents if e.id == close_id), None)
            if focus is None:
                return json.dumps({"error": f"focus not found: {close_id}"})
            closed = close_focus(
                provider._cube,
                focus,
                resolve_id="manual",
                resolve_desc=str(args.get("note") or "manual close"),
                match=1.0,
            )
            provider._prefetch_cache.clear()
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
            return json.dumps(
                {
                    "status": "closed",
                    "focus_id": close_id,
                    "closed_id": getattr(closed, "id", None) if closed else None,
                }
            )
        st = status(ents)
        return json.dumps({"status": "ok", "prospective": st})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_forge(provider: Any, args: dict[str, Any]) -> str:
    """Promote durable successes into procedure drafts (Nous skills-from-experience)."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.procedure import forge, list_candidates, list_drafts

        dry = bool(args.get("dry_run") or False)
        limit = int(args.get("limit") or 8)
        write_drafts = args.get("write_drafts")
        if write_drafts is None:
            write_drafts = True
        ents = list(provider._cube.read_l1() or [])
        cands = list_candidates(ents, limit=limit)
        stats = forge(
            provider._cube,
            hermes_home=provider._hermes_home,
            limit=limit,
            write_drafts=bool(write_drafts),
            dry_run=dry,
        )
        if not dry and stats.get("forged"):
            provider._prefetch_cache.clear()
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
        return json.dumps(
            {
                "status": "forged",
                "stats": stats,
                "candidates_preview": [
                    {
                        "id": e.id,
                        "type": e.entry_type,
                        "description": (e.description or "")[:120],
                        "outcome": e.outcome,
                    }
                    for e in cands[:8]
                ],
                "drafts_on_disk": list_drafts(provider._hermes_home)[:20],
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

