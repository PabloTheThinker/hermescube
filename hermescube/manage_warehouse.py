"""Warehouse manage actions — bootstrap, add/remove, relations, hygiene, journey."""

from __future__ import annotations

import json
from typing import Any

from hermescube.cube import ENTRY_TYPES, OUTCOMES
from hermescube.threats import scan_text, sanitize_for_storage

def handle_bootstrap(provider: Any, args: dict[str, Any]) -> str:
    """Import hot Hermes memories + install bundled Cube skills."""
    if not provider._cube or not provider._hermes_home:
        return json.dumps({"error": "Memory not initialized"})
    mode = str(args.get("mode") or args.get("content") or "all").strip().lower()
    force = False
    if mode.endswith(":force") or mode in ("import:force", "force"):
        force = True
        mode = mode.replace(":force", "").replace("force", "import") or "import"
    if mode in ("reimport", "refresh"):
        mode, force = "import", True
    try:
        from hermescube.bootstrap import run_bootstrap

        report = run_bootstrap(
            provider._cube,
            provider._hermes_home,
            mode=mode or "all",
            force=force,
            vault=getattr(provider, "_vault", "") or "",
            session_id=provider._session_id or "",
            overwrite_skills=bool(args.get("overwrite") or force),
        )
        provider._last_bootstrap = report
        if provider._engine and (report.get("import") or {}).get("imported"):
            try:
                provider._engine.invalidate_cache()
            except Exception:
                pass
            provider._refresh_snapshot()
        return json.dumps(report, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_relations(provider: Any, args: dict[str, Any]) -> str:
    """SPO relations: query / record / stats / expire."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    try:
        from hermescube.relations import RelationStore

        store = provider._relation_store()
        content = str(args.get("content") or args.get("query") or "").strip()
        mode = str(args.get("mode") or "").lower()
        if not mode:
            if content.startswith("record:") or "|" in content and content.count("|") >= 2:
                mode = "record"
            elif content in ("", "stats"):
                mode = "stats"
            else:
                mode = "query"
        if mode == "stats":
            return json.dumps({"status": "relations", **store.stats()}, default=str)
        if mode == "record":
            raw = content[7:] if content.lower().startswith("record:") else content
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 3:
                return json.dumps({
                    "error": "record needs subject|predicate|object",
                })
            rel = store.record(parts[0], parts[1], parts[2])
            return json.dumps({"status": "recorded", **rel.to_dict()}, default=str)
        if mode == "expire":
            raw = content[7:] if content.lower().startswith("expire:") else content
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) < 3:
                return json.dumps({"error": "expire needs subject|predicate|object"})
            n = store.expire(parts[0], parts[1], parts[2])
            return json.dumps({"status": "expired", "count": n})
        # query
        entity = content
        if content.lower().startswith("query:"):
            entity = content[6:].strip()
        hits = store.query(entity, limit=int(args.get("top_k") or 20))
        return json.dumps(
            {
                "status": "relations",
                "entity": entity,
                "count": len(hits),
                "relations": [h.to_dict() for h in hits],
            },
            default=str,
        )
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_hygiene(provider: Any, args: dict[str, Any]) -> str:
    """Prune noise from journey + cube + Hermespace world; re-push clean wisdom."""
    try:
        from hermescube.journey import run_hygiene

        if not provider._cube:
            return json.dumps({"error": "Memory not initialized"})
        out = run_hygiene(
            hermes_home=provider._hermes_home,
            agent_id=str(args.get("agent_id") or "hermes-agent"),
            cube=provider._cube,
            sync_world=bool(args.get("sync_world", True)),
        )
        provider._prefetch_cache.clear()
        if provider._engine:
            try:
                provider._engine.invalidate_cache()
            except Exception:
                pass
        return json.dumps({"status": "hygiene", **out})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_prune(provider: Any, args: dict[str, Any]) -> str:
    """Prune journey timeline events (edit surface)."""
    try:
        from hermescube.journey import prune_events, write_markdown, wisdom_from_cube

        kinds = args.get("drop_kinds") or None
        if isinstance(kinds, str):
            kinds = [kinds]
        ids = args.get("drop_entry_ids") or args.get("entry_ids") or None
        if isinstance(ids, str):
            ids = [ids]
        keep_last = args.get("keep_last")
        if keep_last is not None:
            keep_last = int(keep_last)
        stats = prune_events(
            provider._hermes_home,
            drop_noise=bool(args.get("drop_noise", True)),
            drop_kinds=kinds,
            drop_entry_ids=ids,
            keep_last=keep_last,
        )
        ents = list(provider._cube.read_l1() or []) if provider._cube else []
        w = wisdom_from_cube(entries=ents)
        write_markdown(provider._hermes_home, cube_wisdom=w)
        return json.dumps({"status": "pruned", **stats, "wisdom_n": len(w)})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_journey(provider: Any, args: dict[str, Any]) -> str:
    """Show journey timeline and optionally push wisdom to Hermespace world."""
    try:
        from hermescube.journey import (
            read_events,
            render_markdown,
            write_markdown,
            wisdom_from_cube,
            push_to_hermespace_world,
        )

        hh = provider._hermes_home
        cube_path = provider._cube_path or ""
        ents = list(provider._cube.read_l1() or []) if provider._cube else []
        wisdom = wisdom_from_cube(cube_path, entries=ents)
        write_markdown(hh, cube_wisdom=wisdom)
        events = read_events(hh, limit=30)
        out: dict[str, Any] = {
            "status": "ok",
            "events": events[-20:],
            "wisdom": [{"text": t, "confidence": c} for t, c in wisdom[:10]],
            "markdown": render_markdown(hh, cube_wisdom=wisdom, limit=20)[:4000],
        }
        if args.get("sync_world"):
            out["world"] = push_to_hermespace_world(
                hermes_home=hh,
                agent_id=str(args.get("agent_id") or "hermes-agent"),
                entries=ents,
            )
        return json.dumps(out)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_crystalize(provider: Any, args: dict[str, Any]) -> str:
    """Consolidate near-duplicate memories into belief crystals."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    dry = bool(args.get("dry_run") or False)
    try:
        from hermescube.wisdom import crystalize, functional_loop_stats

        stats = crystalize(provider._cube, dry_run=dry)
        if not dry and stats.get("crystals"):
            provider._prefetch_cache.clear()
            if provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
        ents = list(provider._cube.read_l1() or [])
        loop = functional_loop_stats(ents)
        if not dry and stats.get("crystals"):
            try:
                from hermescube.journey import log_event, write_markdown, wisdom_from_cube

                log_event(
                    "crystalize",
                    f"Formed {stats.get('crystals')} crystals from "
                    f"{stats.get('candidates')} candidates",
                    hermes_home=provider._hermes_home,
                    meta=stats,
                )
                cube_path = provider._cube_path or ""
                w = wisdom_from_cube(cube_path) if cube_path else []
                write_markdown(provider._hermes_home, cube_wisdom=w)
            except Exception:
                pass
        return json.dumps({"status": "crystalized", "stats": stats, "loop": loop})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_replay(provider: Any, args: dict[str, Any]) -> str:
    """Offline sleep replay → Engram Net consolidation."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.sleep_replay import sleep_replay

        net = getattr(provider, "_engram", None)
        if net is None:
            from hermescube.engram_net import EngramNet, default_path as engram_path

            net = EngramNet(provider._paths.engram)
            provider._engram = net
            if provider._engine is not None:
                setattr(provider._engine, "_engram_net", net)
        stats = sleep_replay(
            provider._cube,
            net,
            max_patterns=int(args.get("max_patterns") or 24),
        )
        net.save()
        try:
            from hermescube.journey import log_event

            log_event(
                "sleep_replay",
                f"bundles={stats.get('bundles')} patterns={stats.get('patterns_added')}",
                hermes_home=provider._hermes_home,
                meta=stats,
            )
        except Exception:
            pass
        return json.dumps({"status": "replayed", "stats": stats})
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_add(provider: Any, args: dict[str, Any]) -> str:
    """Handle hermescube_manage add action."""
    content = args.get("content", "")
    entry_type = args.get("entry_type", "belief")
    outcome = args.get("outcome", "none")

    if not content:
        return json.dumps({"error": "content is required"})

    if entry_type not in ENTRY_TYPES:
        return json.dumps({
            "error": f"Invalid entry_type: {entry_type!r}. "
                     f"Must be one of: {sorted(ENTRY_TYPES.keys())}"
        })
    if outcome not in OUTCOMES:
        return json.dumps({
            "error": f"Invalid outcome: {outcome!r}. "
                     f"Must be one of: {sorted(OUTCOMES.keys())}"
        })

    threats = scan_text(content)
    if any(t.severity == "block" for t in threats):
        return json.dumps({"error": "Content blocked by threat scanning"})

    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})

    from hermescube.memory_gate import (
        capture_candidate,
        decide_write_path,
        enrich_entry_data,
        memory_safety,
    )

    safety = memory_safety(content, content)
    path = decide_write_path(safety, policy=getattr(provider, "_memory_policy", "auto-safe"), explicit=True)
    if path == "block":
        # Still queue as blocked candidate for audit
        queued = capture_candidate(
            provider._hermes_home,
            sanitize_for_storage(content, provider._char_limit),
            record_type="fact",
            source="hermescube_manage",
            evidence_state="prepared_not_observed",
            session_id=provider._session_id,
            entry_type=entry_type,
            **provider._path_kw(),
        )
        return json.dumps(
            {
                "error": "Content blocked by memory safety gate",
                "safety": safety,
                "candidate": queued,
            },
            default=str,
        )

    as_candidate = str(args.get("mode") or "").lower() in (
        "candidate",
        "capture",
        "review-first",
    )
    if as_candidate or path == "candidate":
        queued = capture_candidate(
            provider._hermes_home,
            sanitize_for_storage(content, provider._char_limit),
            record_type="fact",
            source="hermescube_manage",
            evidence_state="prepared_not_observed",
            session_id=provider._session_id,
            entry_type=entry_type,
            **provider._path_kw(),
        )
        return json.dumps({"status": "candidate", **queued}, default=str)

    entry = provider._cube.append(
        entry_type=entry_type,
        description=sanitize_for_storage(content, provider._char_limit),
        data=enrich_entry_data(
            {
                "source": "hermescube_manage",
                "session_id": provider._session_id,
                "platform": provider._platform,
                "trust": 0.72 if entry_type in ("focus", "resolve") else 0.5,
                "durable": True,
                "verification": "user_authored",
                **(
                    {"vault": provider._vault, "topic": (provider._agent_workspace or "")[:80]}
                    if getattr(provider, "_vault", "")
                    else {}
                ),
                **(
                    {
                        "user_id": provider._user_id,
                        **(
                            {"user_id_alt": provider._user_id_alt}
                            if getattr(provider, "_user_id_alt", "")
                            else {}
                        ),
                    }
                    if getattr(provider, "_user_id", "")
                    else {}
                ),
            },
            evidence_state="verified",
            safety=safety,
        ),
        outcome=outcome,
    )
    try:
        from hermescube.relations import ingest_entry

        ingest_entry(entry, provider._relation_store())
    except Exception:
        pass
    closed_info = None
    try:
        from hermescube.journey import log_event

        log_event(
            "manage_add",
            f"[{entry_type}] {content.strip()[:180]}",
            hermes_home=provider._hermes_home,
            entry_id=entry.id,
        )
    except Exception:
        pass

    # Prospective: successful resolve closes matching open focus
    if entry_type in ("resolve", "evolution") or (
        entry_type == "landmark" and outcome == "success"
    ):
        try:
            from hermescube.prospective import try_close_on_resolve

            # default outcome none still tries if wording looks done
            closed_info = try_close_on_resolve(provider._cube, entry)
            if closed_info.get("closed") and provider._engine:
                try:
                    provider._engine.invalidate_cache()
                except Exception:
                    pass
                provider._prefetch_cache.clear()
        except Exception:
            closed_info = None

    out: dict[str, Any] = {
        "status": "added",
        "id": entry.id,
        "type": entry.entry_type,
    }
    if closed_info and closed_info.get("closed"):
        out["prospective"] = closed_info

    # Soft contradiction flags (belief/resolve)
    if (
        provider._conflict_detect
        and entry_type in ("belief", "resolve", "trait")
        and not provider._should_skip_writes()
    ):
        try:
            from hermescube.conflict import find_conflicts, annotate_conflicts

            ents = list(provider._cube.read_l1() or [])
            confs = find_conflicts(content, [e for e in ents if e.id != entry.id])
            if confs:
                n = annotate_conflicts(provider._cube, entry, confs)
                out["conflicts"] = confs
                out["conflict_markers"] = n
        except Exception:
            pass

    # Care flag
    if args.get("care") or args.get("critical"):
        try:
            # already written — append care marker linked
            provider._cube.append(
                entry_type=entry_type,
                description=f"[CARE] {sanitize_for_storage(content, 120)}",
                data={
                    "care": True,
                    "critical": True,
                    "care_of": entry.id,
                    "source": "hermescube_manage",
                    "trust": 0.9,
                },
                outcome="success",
            )
            out["care"] = True
        except Exception:
            pass

    return json.dumps(out)

def handle_remove(provider: Any, args: dict[str, Any]) -> str:
    """Handle hermescube_manage remove action."""
    entry_id = args.get("entry_id", "")
    if not entry_id:
        return json.dumps({"error": "entry_id is required"})

    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})

    entry = provider._cube.read_entry(entry_id)
    if not entry:
        return json.dumps({"error": f"Entry {entry_id} not found"})

    provider._cube.append(
        entry_type=entry.entry_type,
        description=f"[SUPERSEDED] {entry.description[:150]}",
        data={
            "supersedes": entry_id,
            "source": "hermescube_manage",
            "session_id": provider._session_id,
        },
        outcome="superseded",
    )

    return json.dumps({"status": "superseded", "id": entry_id})

