"""Cuboasis manage actions — space, connect, progress, governance, triage, merge."""

from __future__ import annotations

import json
from typing import Any

def handle_triage(provider: Any, args: dict[str, Any]) -> str:
    """Build / return / apply consolidation triage plan."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.triage import run_triage, load_plan

        pkw = provider._path_kw()
        mode = str(args.get("mode") or args.get("content") or "").lower()
        if mode == "load":
            plan = load_plan(provider._hermes_home, **pkw) or {}
            return json.dumps({"status": "triage", "loaded": True, **plan}, default=str)
        if mode in ("apply", "run", "execute"):
            from hermescube.cuboasis import apply_triage

            report = apply_triage(
                provider._cube,
                provider._hermes_home,
                forge_limit=int(args.get("top_k") or 2),
                **pkw,
            )
            if provider._engine:
                provider._engine.invalidate_cache()
            return json.dumps({"status": "triage_apply", **report}, default=str)
        plan = run_triage(
            provider._cube,
            hermes_home=provider._hermes_home,
            per_route_limit=int(args.get("top_k") or 8),
            **pkw,
        )
        return json.dumps({"status": "triage", **plan}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_merge(provider: Any, args: dict[str, Any]) -> str:
    """Multi-axis growth merge (AgentDrive-inspired, Cube-native)."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.growth_merge import merge_session_growth

        dry = str(args.get("mode") or "").lower() == "dry"
        result = merge_session_growth(
            provider._cube,
            hermes_home=provider._hermes_home,
            engram=getattr(provider, "_engram", None),
            session_stats={"durable_writes": 1},
            dry_run=dry,
            **provider._path_kw(),
        )
        if result.merged and not dry and provider._engine:
            provider._engine.invalidate_cache()
            provider._refresh_maturity()
        return json.dumps({"status": "merge", **result.to_dict()}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_space(provider: Any, args: dict[str, Any]) -> str:
    """Space map — vaults + chambers (organization without a second store)."""
    if not provider._cube:
        return json.dumps({"error": "Memory not initialized"})
    try:
        from hermescube.cuboasis import space_map, chamber_filter_ids

        mode = str(args.get("mode") or args.get("content") or "status").strip().lower()
        pkw = provider._path_kw()
        if mode.startswith("chamber:"):
            ch = mode.split(":", 1)[1].strip().lower()
            provider._chamber = ch
            if provider._engine is not None:
                setattr(provider._engine, "_chamber_filter", ch)
            ids = chamber_filter_ids(provider._cube, ch, limit=int(args.get("top_k") or 40))
            return json.dumps(
                {
                    "status": "space",
                    "chamber": ch,
                    "active": True,
                    "ids": ids,
                    "count": len(ids),
                },
                default=str,
            )
        if mode in ("chamber_clear", "clear_chamber", "all"):
            provider._chamber = ""
            if provider._engine is not None:
                setattr(provider._engine, "_chamber_filter", "")
        if mode == "set" and args.get("query"):
            # Soft-set active vault for this session (affinity tag)
            provider._vault = str(args.get("query") or "").strip()[:80]
            if provider._engine is not None:
                setattr(provider._engine, "_active_vault", provider._vault)
            with provider._state_lock:
                provider._prefetch_cache.clear()
        report = space_map(
            provider._cube,
            hermes_home=provider._hermes_home,
            active_vault=getattr(provider, "_vault", "") or "",
            **pkw,
        )
        report["active_chamber"] = getattr(provider, "_chamber", "") or ""
        return json.dumps({"status": "space", **report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_connect(provider: Any, args: dict[str, Any]) -> str:
    """Unified neighbors — SPO + colony + engram + HAR related."""
    entity = str(args.get("content") or args.get("query") or "").strip()
    if not entity:
        return json.dumps({"error": "entity required in content/query"})
    try:
        from hermescube.cuboasis import connect_entity

        report = connect_entity(
            entity,
            cube=provider._cube,
            hermes_home=provider._hermes_home,
            relation_store=provider._relation_store() if provider._hermes_home else None,
            colony=getattr(provider, "_colony", None),
            engram=getattr(provider, "_engram", None),
            cubewave=getattr(provider, "_cubewave", None),
            engine=provider._engine,
            limit=int(args.get("top_k") or 12),
            **provider._path_kw(),
        )
        return json.dumps({"status": "connect", **report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_progress(provider: Any, args: dict[str, Any]) -> str:
    """Progress ledger — proof the compounding loop moved."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    try:
        from hermescube.cuboasis import progress_status, record_progress

        mode = str(args.get("mode") or "").strip().lower()
        content = str(args.get("content") or "").strip()
        if mode == "record" or content.startswith("record:"):
            detail = content[7:].strip() if content.lower().startswith("record:") else content
            rec = record_progress(
                provider._hermes_home,
                "manual",
                detail=detail or "operator note",
                **provider._path_kw(),
            )
            return json.dumps({"status": "progress", **rec}, default=str)
        report = progress_status(
            provider._hermes_home,
            cube=provider._cube,
            limit=int(args.get("top_k") or 20),
            **provider._path_kw(),
        )
        return json.dumps({"status": "progress", **report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_cuboasis(provider: Any, args: dict[str, Any]) -> str:
    """Cuboasis pane + governance: capture/review/approve/reject/sync/doctor."""
    if not provider._hermes_home:
        return json.dumps({"error": "hermes_home not set"})
    mode = str(args.get("mode") or args.get("content") or "status").strip().lower()
    # Allow content to carry capture text when mode is set separately
    content = str(args.get("content") or args.get("query") or "").strip()
    if mode in ("status", "", "show") and content and not content.startswith(("approve:", "reject:")):
        # bare content with default mode → treat as capture
        if content not in ("status", "show", "sync", "doctor", "review", "rejected"):
            mode = "capture"

    pkw = provider._path_kw()
    try:
        from hermescube import memory_gate as gate
        from hermescube.cuboasis import cuboasis_status, record_progress

        if mode in ("capture", "candidate"):
            text = content
            if text.lower().startswith("capture:"):
                text = text[8:].strip()
            if not text:
                return json.dumps({"error": "capture requires content"})
            rec = gate.capture_candidate(
                provider._hermes_home,
                text,
                source="cuboasis_capture",
                session_id=provider._session_id,
                entry_type=str(args.get("entry_type") or "belief"),
                **pkw,
            )
            record_progress(
                provider._hermes_home,
                "candidate_capture",
                detail=rec.get("candidate_id", ""),
                metrics={"pending": 1},
                **pkw,
            )
            return json.dumps({**rec, "status": "capture"}, default=str)

        if mode in ("review", "queue", "pending"):
            report = gate.list_candidates(
                provider._hermes_home,
                status="pending",
                limit=int(args.get("top_k") or 40),
                **pkw,
            )
            return json.dumps({"status": "review", **report}, default=str)

        if mode.startswith("approve:") or mode == "approve":
            cid = mode.split(":", 1)[1].strip() if ":" in mode else content
            if cid.lower().startswith("approve:"):
                cid = cid[8:].strip()
            if not cid:
                return json.dumps({"error": "approve needs candidate_id"})
            if not provider._cube:
                return json.dumps({"error": "Memory not initialized"})
            report = gate.approve_candidate(
                provider._hermes_home,
                cid,
                cube=provider._cube,
                **pkw,
            )
            if report.get("ok") and provider._engine:
                provider._engine.invalidate_cache()
            record_progress(
                provider._hermes_home,
                "candidate_approve",
                detail=cid,
                metrics={"approved": 1 if report.get("ok") else 0},
                **pkw,
            )
            return json.dumps({"status": "approve", **report}, default=str)

        if mode.startswith("reject:") or mode == "reject":
            cid = mode.split(":", 1)[1].strip() if ":" in mode else content
            reason = ""
            if "|" in cid:
                cid, reason = [x.strip() for x in cid.split("|", 1)]
            if cid.lower().startswith("reject:"):
                cid = cid[7:].strip()
            if not cid:
                return json.dumps({"error": "reject needs candidate_id"})
            report = gate.reject_candidate(
                provider._hermes_home,
                cid,
                reason=reason or "rejected",
                **pkw,
            )
            record_progress(
                provider._hermes_home,
                "candidate_reject",
                detail=cid,
                metrics={"rejected": 1 if report.get("ok") else 0},
                **pkw,
            )
            return json.dumps({"status": "reject", **report}, default=str)

        if mode in ("rejected", "negative"):
            report = gate.recall_rejected(
                provider._hermes_home,
                content if content not in ("rejected", "negative") else "",
                limit=int(args.get("top_k") or 12),
                **pkw,
            )
            return json.dumps({"status": "rejected", **report}, default=str)

        if mode in ("sync", "curate", "curation"):
            if not provider._cube:
                return json.dumps({"error": "Memory not initialized"})
            report = gate.curation_sync_report(
                provider._cube,
                provider._hermes_home,
                limit=int(args.get("top_k") or 24),
                **pkw,
            )
            return json.dumps({"status": "sync", **report}, default=str)

        if mode == "doctor":
            report = gate.oasis_doctor_card(
                provider._cube,
                provider._hermes_home,
                engram=getattr(provider, "_engram", None),
                cubewave=getattr(provider, "_cubewave", None),
                relation_store=provider._relation_store() if provider._hermes_home else None,
                **pkw,
            )
            return json.dumps({"status": "doctor", **report}, default=str)

        # default status pane
        if not provider._cube:
            return json.dumps({"error": "Memory not initialized"})
        report = cuboasis_status(
            provider._cube,
            provider._hermes_home,
            active_vault=getattr(provider, "_vault", "") or "",
            active_chamber=getattr(provider, "_chamber", "") or "",
            colony=getattr(provider, "_colony", None),
            engram=getattr(provider, "_engram", None),
            cubewave=getattr(provider, "_cubewave", None),
            relation_store=provider._relation_store(),
            **pkw,
        )
        return json.dumps({"status": "cuboasis", **report}, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})

def handle_nexus(provider: Any, args: dict[str, Any]) -> str:
    """Deprecated alias for cuboasis."""
    return handle_cuboasis(provider, args)

