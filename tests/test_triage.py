"""Consolidation triage queues."""

from __future__ import annotations

from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.triage import (
    forgetting_curve_strength,
    load_plan,
    run_triage,
    triage_entries,
)


def test_forgetting_curve_rehearsal_extends_retention():
    base = forgetting_curve_strength(14.0, rehearsal_count=0, half_life_days=7.0)
    rehearsed = forgetting_curve_strength(14.0, rehearsal_count=5, half_life_days=7.0)
    assert rehearsed > base
    assert 0.0 < base < 1.0


def test_triage_routes_conflict_to_reconsolidate(tmp_path: Path):
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    cube.append(
        entry_type="belief",
        description="never use redis for session state in auth-service",
        data={"trust": 0.8, "conflict_with": ["abc"], "durable": True},
        outcome="success",
    )
    cube.append(
        entry_type="landmark",
        description="misc deploy note about canary rollout timing windows",
        data={"trust": 0.4, "source": "sync_turn"},
        outcome="success",
    )
    plan = triage_entries(list(cube.read_l1() or []), per_route_limit=8)
    assert plan["counts"]["reconsolidate"] >= 1
    assert plan["should_conflict_scan"] is True
    ids = {i["item_id"] for i in plan["queues"]["reconsolidate"]}
    # conflicted belief must land in reconsolidate
    assert any(i in ids for i in [e.id for e in cube.read_l1()])


def test_run_triage_persists_plan(tmp_path: Path):
    hh = tmp_path / "home"
    (hh / "memories").mkdir(parents=True)
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    for i in range(5):
        cube.append(
            entry_type="belief",
            description=f"durable preference number {i} about logging format",
            data={"trust": 0.7, "durable": True, "source": "hermescube_manage"},
            outcome="success",
        )
    plan = run_triage(cube, hermes_home=hh, persist=True)
    assert Path(plan["path"]).is_file()
    loaded = load_plan(hh)
    assert loaded is not None
    assert loaded["model"] == "hermescube-triage-v1"
    assert "control_plan" in loaded
