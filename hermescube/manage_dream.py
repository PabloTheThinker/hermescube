"""Manage handlers for CubeDream (L1 soul + L2 circle)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def handle_dream(provider: Any, args: dict[str, Any]) -> str:
    """hermescube_manage action=dream — solo / circle ops."""
    mode = str(args.get("mode") or args.get("content") or "status").strip().lower()
    pkw = provider._path_kw() if hasattr(provider, "_path_kw") else {}
    hh = provider._hermes_home
    agent = provider._agent_identity or "hermes"
    hive_root = (
        getattr(provider, "_hive_path", "")
        or os.environ.get("HERMESCUBE_HIVE", "")
    )

    try:
        from hermescube import dream as dream_mod
        from hermescube import dream_circle as circle_mod

        if mode in ("status", "", "show", "due"):
            pending = 0
            try:
                from hermescube.memory_gate import list_candidates

                pending = int(
                    (
                        list_candidates(hh, status="pending", limit=1, **pkw) or {}
                    ).get("count")
                    or 0
                )
            except Exception:
                pending = 0
            report = dream_mod.dream_status(
                hh, candidate_pending=pending, **pkw
            )
            if hive_root:
                report["circles"] = circle_mod.list_circles(hive_root, limit=8)
            return json.dumps(report, default=str)

        if mode in ("solo", "soul"):
            return json.dumps(
                dream_mod.run_solo_dream(
                    provider._cube,
                    hh,
                    engram=getattr(provider, "_engram", None),
                    apply=False,
                    **pkw,
                ),
                default=str,
            )

        if mode in ("solo:apply", "soul:apply", "apply"):
            dry = str(args.get("crystalize") or "").lower() != "commit"
            report = dream_mod.run_solo_dream(
                provider._cube,
                hh,
                engram=getattr(provider, "_engram", None),
                apply=True,
                dry_crystalize=dry,
                **pkw,
            )
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
            return json.dumps(report, default=str)

        if mode in ("propose", "memory_md", "l4", "hot_md"):
            return json.dumps(
                dream_mod.propose_memory_md(
                    hh, cube=provider._cube, **pkw
                ),
                default=str,
            )

        if mode in ("auto-circle", "auto_circle", "night"):
            if not hive_root:
                return json.dumps(
                    {
                        "error": "hive not configured",
                        "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
                    }
                )
            homes = {agent: hh}
            # Optional peers: content="id1:/path1,id2:/path2"
            peers = str(args.get("peers") or args.get("content") or "").strip()
            if peers and ":" in peers:
                for part in peers.split(","):
                    part = part.strip()
                    if ":" not in part:
                        continue
                    aid, path = part.split(":", 1)
                    homes[aid.strip()] = path.strip()
            topic = str(args.get("topic") or "night chorus").strip()
            pairs: list[tuple[str, str]] = []
            pair_s = str(args.get("interview") or "").strip()
            if pair_s and ":" in pair_s:
                a, b = pair_s.split(":", 1)
                pairs.append((a.strip(), b.strip()))
            return json.dumps(
                circle_mod.run_auto_circle(
                    hive_root,
                    agent_homes=homes,
                    topic=topic,
                    opened_by=agent,
                    interview_pairs=pairs or None,
                    skim=str(args.get("skim") or "1") not in ("0", "false", "no"),
                ),
                default=str,
            )

        if mode.startswith("circle:") or mode in (
            "circle",
            "open",
            "join",
            "signal",
            "score",
            "close",
            "draw",
            "list",
            "dialogue",
            "skim",
            "adversary",
        ):
            if not hive_root:
                return json.dumps(
                    {
                        "error": "hive not configured",
                        "hint": "set plugins.hermescube.hive_path or HERMESCUBE_HIVE",
                    }
                )
            sub = mode.split(":", 1)[1] if ":" in mode else mode
            if sub in ("circle", ""):
                sub = str(args.get("circle_action") or "list").strip()
            circle_id = str(
                args.get("circle_id") or args.get("id") or args.get("query") or ""
            ).strip()

            if sub == "open":
                topic = str(args.get("topic") or args.get("content") or "").strip()
                return json.dumps(
                    circle_mod.open_circle(
                        hive_root, opened_by=agent, topic=topic
                    ),
                    default=str,
                )
            if sub == "list":
                return json.dumps(
                    {"ok": True, "circles": circle_mod.list_circles(hive_root)},
                    default=str,
                )
            if sub == "status":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                return json.dumps(
                    circle_mod.circle_status(hive_root, circle_id), default=str
                )
            if sub == "join":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                return json.dumps(
                    circle_mod.join_circle(
                        hive_root, circle_id, agent_id=agent
                    ),
                    default=str,
                )
            if sub == "signal":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                content = str(args.get("content") or "").strip()
                if content:
                    return json.dumps(
                        circle_mod.post_signal(
                            hive_root,
                            circle_id,
                            agent_id=agent,
                            summary=content,
                        ),
                        default=str,
                    )
                if not provider._cube:
                    return json.dumps({"error": "Memory not initialized"})
                return json.dumps(
                    circle_mod.signal_from_cube(
                        hive_root,
                        circle_id,
                        provider._cube,
                        agent_id=agent,
                    ),
                    default=str,
                )
            if sub == "score":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                return json.dumps(
                    circle_mod.score_circle(
                        hive_root, circle_id, scorer=agent
                    ),
                    default=str,
                )
            if sub == "close":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                return json.dumps(
                    circle_mod.close_circle(
                        hive_root, circle_id, closer=agent
                    ),
                    default=str,
                )
            if sub == "draw":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                if not provider._cube:
                    return json.dumps({"error": "Memory not initialized"})
                r = circle_mod.draw_circle(
                    hive_root,
                    circle_id,
                    provider._cube,
                    agent_id=agent,
                )
                if r.get("drawn") and provider._engine:
                    try:
                        provider._engine.invalidate_cache()
                    except Exception:
                        pass
                return json.dumps(r, default=str)

            if sub == "dialogue":
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                subject = str(args.get("agent") or args.get("subject") or "").strip()
                if not subject:
                    return json.dumps({"error": "subject agent required"})
                topic = str(args.get("topic") or args.get("content") or "").strip()
                return json.dumps(
                    circle_mod.dialogue_in_circle(
                        hive_root,
                        circle_id,
                        interviewer=agent,
                        subject=subject,
                        topic=topic,
                        hermes_home=hh,
                        subject_cube=provider._cube if subject == agent else None,
                        mint=bool(args.get("mint")),
                    ),
                    default=str,
                )

            if sub in ("skim", "adversary", "adversarial"):
                if not circle_id:
                    return json.dumps({"error": "circle_id required"})
                ents = list(provider._cube.read_l1() or []) if provider._cube else []
                return json.dumps(
                    circle_mod.adversarial_skim(
                        hive_root, circle_id, local_entries=ents
                    ),
                    default=str,
                )

            return json.dumps({"error": f"unknown circle action: {sub}"})

        return json.dumps(
            {
                "error": f"unknown dream mode: {mode}",
                "hint": (
                    "status|solo|solo:apply|propose|auto-circle|"
                    "circle:open|signal|dialogue|skim|score|close|draw"
                ),
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})
