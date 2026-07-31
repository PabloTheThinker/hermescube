"""Session-end consolidation pipeline (extracted from CubeMemoryProvider).

Captures immutable context at submit time so a later on_session_switch cannot
mis-attribute work. Provider methods that must run on the live instance
(auto-extract, evolve, maturity) are called via the provider handle.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SessionEndCtx:
    cube: Any
    engine: Any
    hermes_home: str
    session_id: str
    agent_identity: str
    auto_extract: bool
    replay_enabled: bool
    observe_enabled: bool
    digest_enabled: bool
    pulse_enabled: bool
    peer_cadence: float
    skip: bool
    breaker_open: bool
    engram: Any
    hive_enabled: bool
    hive_root: str
    interview_on_pilgrimage: bool
    path_kw: dict[str, Any]
    vault: str
    chamber: str
    colony: Any
    cubewave: Any


def capture_session_end_ctx(provider: Any) -> SessionEndCtx:
    """Freeze provider fields for the background session-end worker."""
    return SessionEndCtx(
        cube=provider._cube,
        engine=provider._engine,
        hermes_home=provider._hermes_home,
        session_id=provider._session_id,
        agent_identity=provider._agent_identity,
        auto_extract=provider._auto_extract,
        replay_enabled=provider._replay_on_session_end,
        observe_enabled=provider._observe_on_session_end,
        digest_enabled=provider._session_digest_enabled,
        pulse_enabled=bool(getattr(provider, "_living_pulse_on_session_end", True)),
        peer_cadence=float(provider._peer_card_cadence_s or 0),
        skip=provider._should_skip_writes(),
        breaker_open=provider._is_evolve_breaker_open(),
        engram=getattr(provider, "_engram", None),
        hive_enabled=bool(getattr(provider, "_hive_on_session_end", False)),
        hive_root=getattr(provider, "_hive_path", "")
        or os.environ.get("HERMESCUBE_HIVE", ""),
        interview_on_pilgrimage=bool(
            getattr(provider, "_interview_on_pilgrimage", False)
        ),
        path_kw={
            "agent_identity": provider._agent_identity or "",
            "agent_workspace": getattr(provider, "_agent_workspace", "") or "",
            "nest_profiles": bool(getattr(provider, "_nest_profiles", False)),
        },
        vault=getattr(provider, "_vault", "") or "",
        chamber=getattr(provider, "_chamber", "") or "",
        colony=getattr(provider, "_colony", None),
        cubewave=getattr(provider, "_cubewave", None),
    )


def run_session_end_work(
    provider: Any,
    ctx: SessionEndCtx,
    messages_snap: list[dict[str, Any]],
) -> None:
    """Heavy session-end work — intended to run on the sync queue."""
    cube = ctx.cube
    hermes_home = ctx.hermes_home
    session_id = ctx.session_id
    agent_identity = ctx.agent_identity
    skip = ctx.skip
    engram = ctx.engram
    path_kw = ctx.path_kw
    vault = ctx.vault

    t0 = time.perf_counter()
    stages: dict[str, float] = {}
    start_count = int(getattr(cube, "entry_count", 0) or 0)
    meta_stages: dict[str, Any] = {}

    # Flush batched durable turns before any session-end consolidation
    t_flush = time.perf_counter()
    try:
        if hasattr(provider, "flush_pending_turns"):
            fr = provider.flush_pending_turns()
            meta_stages["flush_pending"] = fr
    except Exception as e:
        meta_stages["flush_pending_error"] = str(e)
    stages["flush_pending_ms"] = (time.perf_counter() - t_flush) * 1000.0

    if ctx.auto_extract and not skip:
        prev = provider._session_id
        try:
            provider._session_id = session_id
            provider._auto_extract_facts(messages_snap)
        finally:
            provider._session_id = prev
    stages["auto_extract_ms"] = (time.perf_counter() - t0) * 1000.0

    try:
        entries = list(cube.read_l1() or [])
    except Exception:
        entries = []
    l1_reads = 1
    t_stage = time.perf_counter()

    triage_plan: dict = {}
    if not skip and len(entries) >= 4 and hermes_home:
        try:
            from hermescube.triage import run_triage

            triage_plan = run_triage(
                cube,
                hermes_home=hermes_home,
                per_route_limit=8,
                entries=entries,
                **path_kw,
            )
        except Exception:
            triage_plan = {}
    stages["triage_ms"] = (time.perf_counter() - t_stage) * 1000.0
    t_stage = time.perf_counter()

    if not skip and len(entries) >= 6:
        try:
            from hermescube.conflict import (
                annotate_numeric_pairs,
                scan_numeric_conflict_pairs,
            )

            pairs = scan_numeric_conflict_pairs(entries, limit=6)
            if pairs:
                annotate_numeric_pairs(cube, pairs)
                entries = list(cube.read_l1() or [])
                l1_reads += 1
        except Exception:
            pass

    should_crystal = bool(
        triage_plan.get("should_crystalize", True) if triage_plan else True
    )
    crystalized = False
    if not skip and len(entries) >= 4 and should_crystal:
        try:
            from hermescube.wisdom import crystalize

            st = crystalize(
                cube,
                min_cluster=2,
                max_crystals=8,
                entries=entries,
                triage_plan=triage_plan or None,
                max_candidates=200,
            )
            crystalized = bool(
                (st or {}).get("crystals_made") or (st or {}).get("crystals")
            )
            if crystalized:
                entries = list(cube.read_l1() or [])
                l1_reads += 1
        except Exception:
            pass
    stages["crystalize_ms"] = (time.perf_counter() - t_stage) * 1000.0
    t_stage = time.perf_counter()

    if ctx.replay_enabled and not skip and len(entries) >= 6 and engram:
        try:
            from hermescube.sleep_replay import sleep_replay

            rstats = sleep_replay(cube, engram, max_patterns=16, entries=entries)
            engram.save()
            if rstats.get("patterns_added"):
                logger.info("sleep_replay: %s", rstats)
        except Exception:
            pass

    if ctx.observe_enabled and not skip and messages_snap:
        try:
            from hermescube.trajectory import observe_messages

            obs_msgs = (
                messages_snap[-40:] if len(messages_snap) > 40 else messages_snap
            )
            observe_messages(
                cube,
                obs_msgs,
                hermes_home=hermes_home,
                min_tools=3,
                max_forge=2,
            )
        except Exception:
            pass
    stages["observe_ms"] = (time.perf_counter() - t_stage) * 1000.0

    if not skip:
        try:
            if ctx.digest_enabled and messages_snap:
                from hermescube.session_digest import (
                    digest_entry_description,
                    digest_messages,
                )

                dig = digest_messages(messages_snap, open_intents=[])
                cube.append(
                    entry_type="landmark",
                    description=digest_entry_description(dig),
                    data={
                        "source": "session_digest",
                        "session_id": session_id,
                        "trust": 0.65,
                        "durable": True,
                        "verification": "observed",
                        **({"vault": vault} if vault else {}),
                    },
                    outcome="success",
                )
                entries = list(cube.read_l1() or [])
                l1_reads += 1
            from hermescube.peer_card import refresh_card

            refresh_card(
                entries,
                hermes_home=hermes_home,
                peer_name=agent_identity or "user",
                min_interval_s=ctx.peer_cadence,
                **path_kw,
            )
        except Exception:
            pass

    if ctx.pulse_enabled and not skip and len(entries) >= 4:
        try:
            from hermescube.living import chamber_pulse

            chamber_pulse(
                cube,
                hermes_home=hermes_home,
                engram=engram,
                max_connect=3,
                do_crystalize=False,
                do_peer=False,
                entries=entries,
                **path_kw,
            )
        except Exception:
            pass

        # Persist corpus-mined entities onto thin entries (assoc recall lift)
        try:
            from hermescube.mirror import enrich_entries_with_mined_entities

            er = enrich_entries_with_mined_entities(cube, entries, max_touch=12)
            if er.get("enriched"):
                entries = list(cube.read_l1() or [])
                l1_reads += 1
                stages["entity_enrich"] = float(er.get("enriched") or 0)
        except Exception as e:
            logger.debug("entity enrich skipped: %s", e)

    if not skip and len(entries) >= 4 and hermes_home:
        try:
            from hermescube.growth_merge import merge_session_growth

            end_count = int(getattr(cube, "entry_count", 0) or 0)
            merge_session_growth(
                cube,
                hermes_home=hermes_home,
                engram=engram,
                session_stats={
                    "durable_writes": max(0, end_count - int(start_count or 0)),
                    "crystalized": crystalized,
                },
                entries=entries,
                **path_kw,
            )
        except Exception as e:
            logger.debug("growth_merge skipped: %s", e)

    end_count = int(getattr(cube, "entry_count", 0) or 0)
    durable_delta = max(0, end_count - int(start_count or 0))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if hermes_home and not skip:
        try:
            from hermescube.cuboasis import cuboasis_status, record_progress

            record_progress(
                hermes_home,
                "session_end",
                detail=f"entries {start_count}→{end_count}",
                metrics={
                    "durable_delta": durable_delta,
                    "crystalized": 1 if crystalized else 0,
                    "triage_consolidate": int(
                        (triage_plan.get("counts") or {}).get("consolidate") or 0
                    ),
                    "session_end_ms": round(elapsed_ms, 2),
                    "l1_reads": l1_reads,
                    **{k: round(v, 2) for k, v in stages.items()},
                },
                **path_kw,
            )
            cuboasis_status(
                cube,
                hermes_home,
                active_vault=vault,
                active_chamber=ctx.chamber,
                colony=ctx.colony,
                engram=engram,
                cubewave=ctx.cubewave,
                entries=entries,
                **path_kw,
            )
        except Exception as e:
            logger.debug("progress ledger skipped: %s", e)

    try:
        setattr(provider, "_last_session_end_l1_reads", l1_reads)
        setattr(provider, "_last_session_end_ms", elapsed_ms)
        setattr(provider, "_last_session_end_stages", stages)
    except Exception:
        pass

    idle = (
        bool(triage_plan)
        and not should_crystal
        and not crystalized
        and durable_delta == 0
    )
    if cube.entry_count > 0 and not ctx.breaker_open and not idle:
        try:
            from hermescube.self_evolution import run_grounded_evolve

            run_grounded_evolve(provider, label="session_end")
            provider._record_evolve_success()
        except Exception:
            provider._record_evolve_failure()

    if hermes_home and not skip:
        try:
            from hermescube.self_evolution import run_critic, verify_predictions

            verify_predictions(hermes_home, cube=cube)
            run_critic(hermes_home)
        except Exception as e:
            logger.debug("harness verifier/critic skipped: %s", e)

    pilgrimage_report: dict[str, Any] = {}
    if ctx.hive_enabled and ctx.hive_root and not skip:
        try:
            from hermescube import hive as hive_mod

            pilgrimage_report = (
                hive_mod.pilgrimage(
                    ctx.hive_root,
                    hermes_home=hermes_home or str(Path.home() / ".hermes"),
                    agent_id=agent_identity or "hermes",
                    interview=ctx.interview_on_pilgrimage,
                )
                or {}
            )
            if provider._engine:
                provider._engine.invalidate_cache()
        except Exception as e:
            logger.warning("hive pilgrimage failed: %s", e)

    growth_report: dict[str, Any] = {}
    if hermes_home and not skip:
        try:
            if pilgrimage_report.get("growth"):
                growth_report = pilgrimage_report["growth"]
            else:
                from hermescube.genealogy import tick_session

                growth_report = tick_session(
                    hermes_home,
                    cube=cube,
                    durable_writes=durable_delta,
                )
            provider._refresh_maturity()
        except Exception as e:
            logger.debug("genealogy tick skipped: %s", e)

    if (
        hermes_home
        and not skip
        and not pilgrimage_report.get("curator")
        and growth_report.get("bump") == "major"
    ):
        try:
            from hermescube.curator import run_curator

            run_curator(
                hermes_home,
                cube=cube,
                lessons=[],
                era_milestone=True,
            )
        except Exception as e:
            logger.debug("curator skipped: %s", e)

    with provider._state_lock:
        provider._prefetch_cache.clear()
