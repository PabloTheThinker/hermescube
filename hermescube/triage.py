"""Consolidation triage — route Cube entries before offline work.

Adapted from AgentDrive's memory triage (working / reconsolidate /
consolidate / archive) with Cube-native signals: type priors, trust,
crystal depth, conflict markers, and bio half-life retention.

Deterministic, no LLM. Writes ``memories/triage_plan.json`` so doctor and
session-end can see *what work to do* instead of always running everything.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from hermescube import bio_rank

ROUTE_ACTIONS: dict[str, dict[str, str]] = {
    "working_set": {
        "action": "prefer_in_prefetch",
        "instruction": "Keep these near the top of scarce prompt context.",
    },
    "reconsolidate": {
        "action": "resolve_conflicts",
        "instruction": "Run conflict checks / feedback before treating as doctrine.",
    },
    "consolidate": {
        "action": "crystalize_or_forge",
        "instruction": "Promote into crystals, procedures, or growth merges.",
    },
    "archive": {
        "action": "leave_cold",
        "instruction": "Addressable via search; skip offline promotion this cycle.",
    },
}


def plan_path(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).triage_plan


def forgetting_curve_strength(
    age_days: float,
    *,
    rehearsal_count: int = 0,
    half_life_days: float = 7.0,
) -> float:
    age = max(0.0, float(age_days))
    half_life = max(0.25, float(half_life_days))
    rehearsal_boost = 1.0 + math.log1p(max(0, int(rehearsal_count)))
    return round(math.exp(-age / (half_life * rehearsal_boost)), 4)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _age_days(entry: Any, *, now: float | None = None) -> float:
    now = now if now is not None else time.time()
    ts = getattr(entry, "timestamp", "") or ""
    try:
        if len(ts) >= 19:
            t = datetime.fromisoformat(ts[:19]).timestamp()
            return max(0.0, (now - t) / 86400.0)
    except (ValueError, TypeError, OSError):
        pass
    data = getattr(entry, "data", None) or {}
    formed = data.get("formed_at")
    if isinstance(formed, (int, float)) and formed > 0:
        return max(0.0, (now - float(formed)) / 86400.0)
    return 3.0  # unknown → mild age


def _trust(entry: Any) -> float:
    data = getattr(entry, "data", None) or {}
    t = data.get("trust")
    if isinstance(t, (int, float)):
        return _clamp(float(t))
    src = str(data.get("source") or "")
    if src in ("wisdom_crystalizer", "growth_merge", "hermescube_manage", "seed"):
        return 0.75
    if src in ("sync_turn", "turn", "session_digest"):
        return 0.45
    return 0.55


@dataclass(frozen=True)
class TriageCandidate:
    item_id: str
    source: str
    memory_kind: str = "episodic"
    age_days: float = 0.0
    rehearsal_count: int = 0
    salience: float = 0.5
    retrieval_relevance: float = 0.5
    coherence: float = 0.5
    trust: float = 0.7
    novelty: float = 0.3
    contradiction_pressure: float = 0.0
    consolidation_depth: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TriageResult:
    item_id: str
    source: str
    memory_kind: str
    route: str
    retention_strength: float
    working_score: float
    consolidation_score: float
    reconsolidation_score: float
    why: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def entry_to_candidate(entry: Any, *, now: float | None = None) -> TriageCandidate | None:
    """Project a CubeEntry into a triage candidate. Returns None for noise."""
    eid = str(getattr(entry, "id", "") or "")
    if not eid:
        return None
    et = (getattr(entry, "entry_type", "") or "").lower()
    outcome = (getattr(entry, "outcome", "") or "").lower()
    desc = (getattr(entry, "description", "") or "").strip()
    data = getattr(entry, "data", None) or {}
    if outcome == "superseded":
        return None
    if et in ("enter", "leave", "epoch_transition"):
        return None
    if len(desc) < 8:
        return None
    if data.get("growth_merge") and data.get("crystal"):
        # already a merge crystal — archive unless conflicting
        consolidation_depth = 0.95
    elif data.get("crystal"):
        consolidation_depth = 0.9
    elif data.get("procedure") or desc.startswith("[PROCEDURE]"):
        consolidation_depth = 0.7
    else:
        consolidation_depth = 0.15 if et in ("belief", "resolve", "trait") else 0.35

    prior = bio_rank.type_prior(et)
    salience = _clamp((prior - 0.9) / 0.3)  # map ~[0.9,1.18] → [0,1]
    salience = _clamp(0.35 * salience + 0.45 * _trust(entry) + (0.2 if data.get("durable") else 0.0))

    contradiction = 0.0
    if data.get("conflict_with") or data.get("conflicts"):
        contradiction = 0.7
    if "conflict" in str(data.get("tags") or "").lower():
        contradiction = max(contradiction, 0.55)

    rehearsal = 0
    for key in ("yield_hits", "retrievals", "rehearsal_count"):
        if isinstance(data.get(key), (int, float)):
            rehearsal = max(rehearsal, int(data[key]))

    hl_hours = bio_rank.half_life_hours(et)
    half_life_days = max(0.5, hl_hours / 24.0)

    return TriageCandidate(
        item_id=eid,
        source=str(data.get("source") or et or "cube"),
        memory_kind=et or "episodic",
        age_days=_age_days(entry, now=now),
        rehearsal_count=rehearsal,
        salience=salience,
        retrieval_relevance=_clamp(0.4 + 0.3 * salience),
        coherence=_clamp(1.0 - 0.5 * contradiction),
        trust=_trust(entry),
        novelty=_clamp(1.0 - consolidation_depth),
        contradiction_pressure=contradiction,
        consolidation_depth=consolidation_depth,
        metadata={
            "entry_type": et,
            "half_life_days": round(half_life_days, 3),
            "description": desc[:120],
        },
    )


def _score_candidate(c: TriageCandidate) -> TriageResult:
    hl = float((c.metadata or {}).get("half_life_days") or 7.0)
    retention = forgetting_curve_strength(
        c.age_days, rehearsal_count=c.rehearsal_count, half_life_days=hl
    )
    salience = _clamp(c.salience)
    relevance = _clamp(c.retrieval_relevance)
    coherence = _clamp(c.coherence)
    trust = _clamp(c.trust)
    novelty = _clamp(c.novelty)
    contradiction = _clamp(c.contradiction_pressure)
    depth = _clamp(c.consolidation_depth)

    working = 0.36 * relevance + 0.24 * salience + 0.18 * retention + 0.12 * trust + 0.10 * novelty
    consolidation = (
        0.30 * salience
        + 0.24 * novelty
        + 0.20 * trust
        + 0.16 * (1.0 - depth)
        + 0.10 * coherence
    )
    reconsolidation = (
        0.36 * contradiction
        + 0.24 * (1.0 - coherence)
        + 0.18 * relevance
        + 0.12 * salience
        + 0.10 * retention
    )

    # Explicit conflict markers always reopen — even when the item is also
    # a strong working-set candidate (salience must not bury contradictions).
    if contradiction >= 0.5 or (
        reconsolidation >= 0.58 and (contradiction >= 0.35 or coherence <= 0.55)
    ):
        route = "reconsolidate"
        why = "important but conflicted; reopen before reuse"
    elif working >= 0.66:
        route = "working_set"
        why = "high salience/retention; prefer in active context"
    elif consolidation >= 0.62:
        route = "consolidate"
        why = "high-signal material not yet abstracted"
    else:
        route = "archive"
        why = "low immediate promotion value; leave cold"

    return TriageResult(
        item_id=c.item_id,
        source=c.source,
        memory_kind=c.memory_kind,
        route=route,
        retention_strength=retention,
        working_score=round(working, 4),
        consolidation_score=round(consolidation, 4),
        reconsolidation_score=round(reconsolidation, 4),
        why=why,
        metadata=dict(c.metadata),
    )


def build_control_plan(queues: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    route_order = ["working_set", "reconsolidate", "consolidate", "archive"]
    steps = []
    for route in route_order:
        items = queues.get(route, [])
        action = ROUTE_ACTIONS[route]
        steps.append(
            {
                "route": route,
                "action": action["action"],
                "instruction": action["instruction"],
                "count": len(items),
                "item_ids": [str(i.get("item_id", "")) for i in items],
            }
        )
    if queues.get("working_set"):
        next_focus = "reason_over_working_set"
    elif queues.get("reconsolidate"):
        next_focus = "resolve_reconsolidation_queue"
    elif queues.get("consolidate"):
        next_focus = "schedule_consolidation"
    else:
        next_focus = "no_active_memory_work"
    return {
        "next_focus": next_focus,
        "primary_context_order": route_order,
        "steps": steps,
    }


def triage_entries(
    entries: list[Any],
    *,
    per_route_limit: int = 8,
    now: float | None = None,
) -> dict[str, Any]:
    """Route Cube entries into consolidation queues."""
    now = now if now is not None else time.time()
    candidates: list[TriageCandidate] = []
    for e in entries:
        c = entry_to_candidate(e, now=now)
        if c is not None:
            candidates.append(c)

    scored = [_score_candidate(c) for c in candidates]
    route_priority = {
        "working_set": 3,
        "reconsolidate": 2,
        "consolidate": 1,
        "archive": 0,
    }
    scored.sort(
        key=lambda r: (
            route_priority.get(r.route, 0),
            max(r.working_score, r.consolidation_score, r.reconsolidation_score),
        ),
        reverse=True,
    )

    queues: dict[str, list[dict[str, Any]]] = {
        "working_set": [],
        "reconsolidate": [],
        "consolidate": [],
        "archive": [],
    }
    for result in scored:
        q = queues[result.route]
        if len(q) < per_route_limit:
            q.append(result.to_dict())

    plan = {
        "model": "hermescube-triage-v1",
        "ts": now,
        "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "scanned": len(candidates),
        "queues": queues,
        "counts": {k: len(v) for k, v in queues.items()},
        "control_plan": build_control_plan(queues),
        "should_crystalize": len(queues["consolidate"]) > 0,
        "should_conflict_scan": len(queues["reconsolidate"]) > 0,
    }
    return plan


def save_plan(
    hermes_home: str | Path | None,
    plan: dict[str, Any],
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    path = plan_path(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    return path


def load_plan(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any] | None:
    path = plan_path(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_triage(
    cube: Any,
    *,
    hermes_home: str | Path | None = None,
    per_route_limit: int = 8,
    persist: bool = True,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Read L1, triage, optionally persist the plan."""
    try:
        entries = list(cube.read_l1() or []) if cube is not None else []
    except Exception as e:
        return {"error": str(e), "counts": {}}
    plan = triage_entries(entries, per_route_limit=per_route_limit)
    if persist and hermes_home is not None:
        try:
            plan["path"] = str(
                save_plan(
                    hermes_home,
                    plan,
                    agent_identity=agent_identity,
                    agent_workspace=agent_workspace,
                    nest_profiles=nest_profiles,
                )
            )
        except Exception as e:
            plan["persist_error"] = str(e)
    return plan
