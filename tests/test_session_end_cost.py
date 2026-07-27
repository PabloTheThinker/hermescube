"""Phase 3 — session-end L1 once + triage-capped crystalize."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from hermescube.cube import CubeFile
from hermescube.growth_merge import merge_session_growth
from hermescube.triage import run_triage, triage_entries
from hermescube.wisdom import crystalize, crystalize_id_cap


def _fill(cube: CubeFile, n: int) -> None:
    for i in range(n):
        cube.append(
            "belief",
            f"Fact number {i} about AuthService Redis Postgres cluster {i % 7}",
            data={"trust": 0.7, "durable": True, "source": "seed"},
        )


def test_crystalize_respects_candidate_cap(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "c.cube"))
    _fill(c, 80)
    ents = c.read_l1()
    plan = triage_entries(ents, per_route_limit=8)
    ids = crystalize_id_cap(plan, ents, max_candidates=30)
    assert ids is not None
    assert len(ids) <= 30
    st = crystalize(
        c,
        dry_run=True,
        entries=ents,
        candidate_ids=ids,
        max_candidates=30,
    )
    assert "crystals" in st
    c.close()


def test_session_end_style_single_l1_read(tmp_path: Path):
    """Closure reads L1 once when no crystalize/digest appends fire."""
    hh = tmp_path / "hh"
    (hh / "memories").mkdir(parents=True)
    c = CubeFile.create(str(hh / "memories" / "memory.cube"))
    _fill(c, 12)
    # Force triage skip crystalize by emptying consolidate via dry plan
    real_read = c.read_l1
    calls = {"n": 0}

    def counted():
        calls["n"] += 1
        return real_read()

    with patch.object(c, "read_l1", side_effect=counted):
        entries = list(c.read_l1() or [])
        assert calls["n"] == 1
        plan = run_triage(
            c, hermes_home=str(hh), entries=entries, persist=False
        )
        # crystalize with provided entries — no extra read
        crystalize(
            c,
            dry_run=True,
            entries=entries,
            triage_plan=plan,
            max_candidates=50,
        )
        merge_session_growth(
            c,
            hermes_home=str(hh),
            session_stats={"durable_writes": 2, "crystalized": False},
            dry_run=True,
            entries=entries,
        )
        assert calls["n"] == 1
    c.close()


def test_growth_merge_fires_when_axes_ge_2(tmp_path: Path):
    hh = tmp_path / "hh"
    (hh / "memories").mkdir(parents=True)
    c = CubeFile.create(str(hh / "memories" / "memory.cube"))
    c.append(
        "belief",
        "AuthService uses Redis for sessions",
        data={"crystal": True, "trust": 0.9, "source": "seed"},
        outcome="success",
    )
    c.append(
        "landmark",
        "[SESSION] shipped auth hardening",
        data={"source": "session_digest", "trust": 0.7},
        outcome="success",
    )
    result = merge_session_growth(
        c,
        hermes_home=str(hh),
        session_stats={"durable_writes": 2, "crystalized": True},
        dry_run=True,
    )
    assert result.axes.merge_ready()
    assert len(result.axes.present()) >= 2
    assert result.merged is True
    assert result.reason == "dry_run"
    c.close()
