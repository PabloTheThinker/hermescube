"""Recall tool handlers — search / probe / feedback (peeled from provider)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRUST_HELPFUL_DELTA = 0.05
TRUST_UNHELPFUL_DELTA = -0.10

def handle_search(provider: Any, args: dict[str, Any]) -> str:
    """Handle hermescube_search tool call."""
    query = args.get("query", "")
    entry_type = args.get("entry_type")
    top_k = args.get("top_k", 10)

    if not provider._engine:
        return json.dumps({"error": "Memory not initialized"})

    results = provider._engine.query(query, top_k=top_k)

    if entry_type:
        results = [(e, s) for e, s in results if e.entry_type == entry_type]

    formatted = []
    for entry, score in results:
        formatted.append({
            "id": entry.id,
            "type": entry.entry_type,
            "description": entry.description,
            "outcome": entry.outcome,
            "score": round(score, 4),
            "timestamp": entry.timestamp,
            "trust": entry.data.get("trust", 0.5) if entry.data else 0.5,
        })

    return json.dumps({"results": formatted, "count": len(formatted)})

def handle_probe(provider: Any, args: dict[str, Any]) -> str:
    """Entity probe/related — agent hyper-memory tools."""
    action = args.get("action", "probe")
    entity = (args.get("entity") or "").strip()
    limit = int(args.get("limit") or 8)
    if not entity:
        return json.dumps({"error": "entity is required"})
    if not provider._engine:
        return json.dumps({"error": "Memory not initialized"})
    if action == "related" and hasattr(provider._engine, "related"):
        results = provider._engine.related(entity, top_k=limit)
    else:
        results = provider._engine.query(entity, top_k=limit)
    formatted = []
    for entry, score in results:
        formatted.append({
            "id": entry.id,
            "type": entry.entry_type,
            "description": entry.description,
            "score": round(float(score), 4),
            "entities": (entry.data or {}).get("entities") if entry.data else [],
        })
    return json.dumps({
        "action": action,
        "entity": entity,
        "results": formatted,
        "count": len(formatted),
    })

def handle_feedback(provider: Any, args: dict[str, Any]) -> str:
    """Handle hermescube_feedback tool call."""
    action = args.get("action", "")
    entry_id = args.get("entry_id", "")

    if not entry_id:
        return json.dumps({"error": "entry_id is required"})
    if action not in ("helpful", "unhelpful"):
        return json.dumps({"error": f"Invalid action: {action!r}"})

    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})

    entry = provider._cube.read_entry(entry_id)
    if not entry:
        return json.dumps({"error": f"Entry {entry_id} not found"})

    current_trust = entry.data.get("trust", 0.5) if entry.data else 0.5
    # Asymmetric deltas: penalty > reward (holographic pattern)
    delta = TRUST_HELPFUL_DELTA if action == "helpful" else TRUST_UNHELPFUL_DELTA
    new_trust = round(max(0.0, min(1.0, current_trust + delta)), 2)

    updated_data = dict(entry.data) if entry.data else {}
    updated_data["trust"] = new_trust
    updated_data["feedback_count"] = updated_data.get("feedback_count", 0) + 1

    provider._cube.append(
        entry_type=entry.entry_type,
        description=entry.description,
        data={
            **updated_data,
            "supersedes": entry_id,
            "source": "hermescube_feedback",
            "session_id": provider._session_id,
        },
        outcome="superseded",
    )

    # Colony: helpful = reinforce pheromone trail (ant food found)
    if action == "helpful":
        if provider._void is not None:
            try:
                provider._void.reinforce(entry, amount=0.5)
            except Exception:
                pass
        elif provider._colony is not None:
            try:
                ents = (entry.data or {}).get("entities") if entry.data else None
                if not ents:
                    from hermescube import mirror as mirror_mod
                    ents = mirror_mod.extract_entities(entry.description or "")
                if ents:
                    provider._colony.deposit(list(ents), amount=0.5)
                    provider._colony.register_dance(entry)
                    provider._colony.save()
                    provider._colony.mark_dirty()
                    if provider._paths:
                        provider._colony.maybe_write_markdown_board(
                            provider._paths.colony_board, force=True
                        )
            except Exception:
                pass

    # Yield Gradient: query-local payoff (closed learning loop)
    # Prefer last prefetch query so boost is conditioned on *how* it was asked
    try:
        q = (
            args.get("query")
            or getattr(provider, "_last_prefetch_query", None)
            or (entry.description or "")[:120]
        )
        yg = getattr(provider, "_yield", None)
        if yg is not None and q:
            yg.record(str(q), entry_id, helpful=(action == "helpful"))
    except Exception:
        pass

    # Engram Net: strengthen/weaken co-activation among judged set
    try:
        net = getattr(provider, "_engram", None)
        if net is not None:
            cohort = args.get("cohort_ids") or args.get("entry_ids")
            ids = [entry_id]
            if isinstance(cohort, list):
                ids.extend(str(x) for x in cohort if x)
            elif getattr(provider, "_last_prefetch_ids", None):
                ids.extend(str(x) for x in provider._last_prefetch_ids[:12])
            net.learn_feedback(ids, helpful=(action == "helpful"))
            net.save()
    except Exception:
        pass

    # Cubewave: LMS + edge update from usefulness (pocket-dimension learning)
    try:
        wave = getattr(provider, "_cubewave", None)
        if wave is not None:
            cohort = args.get("cohort_ids") or args.get("entry_ids")
            ids = [entry_id]
            if isinstance(cohort, list):
                ids.extend(str(x) for x in cohort if x)
            elif getattr(provider, "_last_prefetch_ids", None):
                ids.extend(str(x) for x in provider._last_prefetch_ids[:12])
            q = (
                args.get("query")
                or getattr(provider, "_last_prefetch_query", None)
                or (entry.description or "")[:120]
            )
            wave.learn_feedback(
                ids,
                helpful=(action == "helpful"),
                query_text=str(q or ""),
            )
            wave.save()
    except Exception:
        pass

    # Progress ledger — usefulness signal
    if provider._hermes_home:
        try:
            from hermescube.cuboasis import record_progress

            record_progress(
                provider._hermes_home,
                "feedback",
                detail=f"{action} {entry_id[:12]}",
                metrics={
                    "helpful": 1 if action == "helpful" else 0,
                    "unhelpful": 1 if action == "unhelpful" else 0,
                    "trust": new_trust,
                },
                **provider._path_kw(),
            )
        except Exception:
            pass

    try:
        from hermescube.journey import log_event

        log_event(
            "feedback_" + action,
            (entry.description or "")[:180],
            hermes_home=provider._hermes_home,
            entry_id=entry_id,
        )
    except Exception:
        pass

    # Skills evolve: helpful feedback on a procedure/skill entry appends
    # a lesson and bumps the skill's patch version.
    refine_info: dict[str, Any] | None = None
    if action == "helpful" and provider._hermes_home:
        try:
            d = entry.data if isinstance(entry.data, dict) else {}
            desc = entry.description or ""
            is_proc = bool(
                d.get("procedure")
                or d.get("skill_path")
                or desc.startswith(
                    ("[PROCEDURE]", "[PROMOTED]", "[SKILL INSTALLED]")
                )
            )
            if is_proc:
                from hermescube.genealogy import refine_skill

                skill_name = ""
                if d.get("skill_path"):
                    skill_name = Path(str(d["skill_path"])).parent.name
                elif desc.startswith("[SKILL INSTALLED]"):
                    skill_name = desc.split("]", 1)[-1].strip().split()[0]
                elif d.get("draft"):
                    skill_name = Path(str(d["draft"])).stem
                if skill_name:
                    refine_info = refine_skill(
                        provider._hermes_home,
                        skill_name,
                        lesson=f"reinforced in use (trust → {new_trust}): {desc[:160]}",
                        cube=provider._cube,
                    )
                else:
                    from hermescube.genealogy import record_growth

                    record_growth(
                        provider._hermes_home,
                        "feedback_up",
                        detail=f"trust↑ on procedure: {desc[:80]}",
                        cube=provider._cube,
                    )
        except Exception:
            pass

    out: dict[str, Any] = {
        "status": "rated",
        "id": entry_id,
        "action": action,
        "trust": new_trust,
    }
    if refine_info and refine_info.get("ok"):
        out["skill_refined"] = {
            "skill": refine_info.get("skill"),
            "version": refine_info.get("to_version"),
        }
    return json.dumps(out)
