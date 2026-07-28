"""Agent-facing operating manual assembled into Hermes system_prompt_block.

Kept out of provider.py so the MemoryProvider stays a thin socket while the
manual can evolve independently.
"""

from __future__ import annotations

from typing import Any


def build_system_prompt_block(provider: Any) -> str:
    """Instant operating manual for any agent that connects to HermesCube.

    Quicksilver / Hermes 0.19: prompt assembly — never full-scan L1 here.
    """
    cube = getattr(provider, "_cube", None)
    if not cube:
        return ""

    entry_count = int(cube.entry_count or 0)
    type_counts = cube.count_by_type()
    policy = getattr(provider, "_memory_policy", "auto-safe") or "auto-safe"
    hermes_home = getattr(provider, "_hermes_home", None) or None
    path_kw = provider._path_kw() if hasattr(provider, "_path_kw") else {}

    ready: dict[str, Any] = {}
    try:
        from hermescube.bootstrap import bootstrap_status

        ready = bootstrap_status(cube, hermes_home)
    except Exception:
        ready = {"needs_import": entry_count == 0, "hint": ""}

    lines = [
        "# HermesCube — your deep memory warehouse",
        "",
        "## Mental model (read once)",
        "| Layer | Job |",
        "|-------|-----|",
        "| MEMORY.md / USER.md | Hot pocket notebook — always injected |",
        "| Built-in memory tool | Short doctrine writes (mirrored into Cube) |",
        "| **HermesCube** | Deep warehouse — prefetch, search, durable archive |",
        "",
        "Cube **extends** hot memory; it does not replace it.",
        f"Warehouse: {entry_count} entries under `$HERMES_HOME/memories/memory.cube` · policy={policy}",
        "Path: **solo** (prefetch / search / feedback / triage / Cuboasis) — "
        "fleet (hive/HQ/interview) only if connected.",
    ]

    if type_counts:
        top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]
        type_str = ", ".join(f"{t}:{c}" for t, c in top_types)
        lines.append(f"Types: {type_str}")

    if ready.get("needs_import") or ready.get("needs_skills"):
        hot = ", ".join(ready.get("hot_files") or []) or "(none found yet)"
        lines.extend(
            [
                "",
                "## Start here — seed the warehouse",
                f"Hot files found: {hot}",
                "Call now: `hermescube_manage action=bootstrap mode=all`",
                "→ imports MEMORY.md/USER.md/SOUL.md + installs skills "
                "`hermescube-operate` / `hermescube-import` / `interview-me`",
                "Then: `hermescube_search query=\"what do we know about the user\"`",
            ]
        )
    elif getattr(provider, "_last_bootstrap", None):
        imp = (provider._last_bootstrap or {}).get("import") or {}
        sk = (provider._last_bootstrap or {}).get("skills") or {}
        lines.extend(
            [
                "",
                "## Bootstrap (this session)",
                f"Auto-imported {imp.get('imported', 0)} hot facts · "
                f"skills installed={sk.get('installed') or sk.get('skipped') or []}",
            ]
        )

    try:
        from hermescube.genealogy import prompt_strip

        strip = prompt_strip(hermes_home)
        if strip:
            lines.append(strip)
    except Exception:
        pass
    try:
        from hermescube.cuboasis import prompt_strip as cuboasis_strip

        nstrip = cuboasis_strip(
            hermes_home,
            cube=cube,
            active_vault=getattr(provider, "_vault", "") or "",
            active_chamber=getattr(provider, "_chamber", "") or "",
            cubewave=getattr(provider, "_cubewave", None),
            memory_policy=policy,
            **path_kw,
        )
        if nstrip:
            lines.append(nstrip)
    except Exception:
        pass

    # Density honesty — agents should know when vectors dominate disk
    try:
        dens = cube.density_stats() if hasattr(cube, "density_stats") else {}
        share = dens.get("text_plus_data_share")
        if dens.get("entries", 0) >= 20 and isinstance(share, (int, float)):
            lines.append(
                f"Density: text+data={share:.1%} of archive · "
                f"vectors≈{dens.get('vec_bytes_estimate', 0)} B "
                "(use `hermescube dense` for portable text backup)"
            )
    except Exception:
        pass

    lines.extend(
        [
            "",
            "## Tools",
            "- `hermescube_search` — deep recall before answering history questions",
            "- `hermescube_probe` — entity focus (person / project / path)",
            "- `hermescube_manage` — bootstrap · add · triage · crystalize · merge · "
            "relations · cuboasis · …",
            "- `hermescube_feedback` — helpful/unhelpful on recalled entry ids",
            "",
            "## Everyday loop",
            "1. Prefetch arrives as `<memory-context>` — quoted evidence, not user speech",
            "2. History questions → search/probe first",
            "3. Short doctrine → built-in memory tool; durable warehouse facts → `manage add`",
            "4. Rate useful recalls with feedback (trains yield + Cubewave)",
            "5. When nudged: `triage` → `crystalize` → `merge` / `relations`",
            "6. If candidates pending>0: `cuboasis mode=review` then approve/reject",
            "",
            "## Rules",
            "- Prefer user_authored / tool_verified over unverified when conflicting",
            "- Do NOT store temp todos, secrets, raw logs, or full transcripts",
            "- Real friction → `manage action=witness`",
            "- Skills: follow `hermescube-operate` (daily) and `hermescube-import` (seed)",
        ]
    )

    if getattr(provider, "_hive_path", ""):
        lines.append(
            "Hive connected — `manage action=hive|interview|hq`. "
            "[HIVE:agent] = peer wisdom, not user facts."
        )
        try:
            from hermescube.hq import lane_strip

            strip = lane_strip(
                provider._hive_path, getattr(provider, "_agent_identity", "") or "hermes"
            )
            if strip:
                lines.append(strip)
        except Exception:
            pass

    if entry_count > 0:
        try:
            from hermescube.wisdom import active_wisdom, functional_loop_stats

            ents: list[Any] = []
            engine = getattr(provider, "_engine", None)
            if engine is not None:
                try:
                    engine.refresh_cache()
                    ents = list(getattr(engine, "_entries", None) or [])
                except Exception:
                    ents = []
            if not ents and entry_count <= 200:
                ents = list(cube.read_l1() or [])
            if ents:
                stats = functional_loop_stats(ents)
                lines.append(
                    f"Functional loop: crystals={stats.get('crystal_count')} "
                    f"beliefs={stats.get('belief_count')} "
                    f"healthy={stats.get('healthy')}"
                )
                wisdom = active_wisdom(
                    ents, limit=4, vault=getattr(provider, "_vault", "") or ""
                )
                if wisdom:
                    lines.append("Active wisdom:")
                    for w in wisdom:
                        tag = (
                            "crystal"
                            if (w.data or {}).get("crystal")
                            else (w.entry_type or "belief")
                        )
                        lines.append(f"  · [{tag}] {(w.description or '')[:100]}")
                try:
                    from hermescube.living import prompt_strip as living_strip

                    ls = living_strip(
                        hermes_home,
                        high_load=False,
                        vault=getattr(provider, "_vault", "") or "",
                        **path_kw,
                    )
                    if ls:
                        lines.append(ls)
                except Exception:
                    pass
        except Exception:
            pass

    if hasattr(provider, "_take_memory_review_nudge") and provider._take_memory_review_nudge():
        lines.append("")
        nudge = (
            "### Memory review due\n"
            "- `hermescube_manage action=triage` → then `crystalize` if needed\n"
            "- `relations` / `merge` when Living strip says ready"
        )
        if policy == "review-first":
            nudge += "\n- Also `cuboasis mode=review` for the candidate queue"
        lines.append(nudge)
        provider._nudge_prefetch_line = True

    if hermes_home:
        try:
            from hermescube.dream import reminder_strip

            pending = 0
            try:
                from hermescube.memory_gate import list_candidates

                pending = int(
                    (
                        list_candidates(
                            hermes_home, status="pending", limit=1, **path_kw
                        )
                        or {}
                    ).get("count")
                    or 0
                )
            except Exception:
                pending = 0
            strip = reminder_strip(
                hermes_home, candidate_pending=pending, **path_kw
            )
            if strip:
                lines.extend(["", strip.rstrip()])
        except Exception:
            pass

    return "\n".join(lines)
