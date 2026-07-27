"""Growth merge — multi-axis session compounding."""

from __future__ import annotations

from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.engram_net import EngramNet
from hermescube.growth_merge import detect_axes, merge_session_growth


def test_detect_axes_requires_two_surfaces(tmp_path: Path):
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    axes = detect_axes(cube, hermes_home=tmp_path)
    assert not axes.merge_ready()
    assert axes.present() == []

    cube.append(
        entry_type="belief",
        description="redis cache reduces auth-service latency",
        data={"crystal": True, "source": "wisdom_crystalizer", "trust": 0.9},
        outcome="success",
    )
    axes = detect_axes(cube, hermes_home=tmp_path, session_stats={"durable_writes": 0})
    assert axes.wisdom
    assert not axes.merge_ready()  # wisdom alone


def test_merge_emits_growth_crystal(tmp_path: Path):
    hh = tmp_path / "home"
    (hh / "memories").mkdir(parents=True)
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    a = cube.append(
        entry_type="belief",
        description="prefer structured logging across services",
        data={"source": "sync_turn", "trust": 0.6, "durable": True},
        outcome="success",
    )
    b = cube.append(
        entry_type="landmark",
        description="[PROCEDURE] deploy via canary then promote",
        data={"procedure": True, "source": "trajectory", "trust": 0.7},
        outcome="success",
    )
    net = EngramNet(hh / "memories" / "engram_net.json")
    net.learn_coactivation([a.id, b.id], strength=1.0)

    result = merge_session_growth(
        cube,
        hermes_home=hh,
        engram=net,
        session_stats={"durable_writes": 2, "crystalized": False},
    )
    assert result.merged
    assert len(result.axes.present()) >= 2
    entries = list(cube.read_l1() or [])
    merges = [
        e
        for e in entries
        if (getattr(e, "data", None) or {}).get("growth_merge")
    ]
    assert len(merges) == 1
    assert merges[0].entry_type == "evolution"

    # Second call should not spam
    again = merge_session_growth(
        cube,
        hermes_home=hh,
        engram=net,
        session_stats={"durable_writes": 2},
    )
    assert not again.merged
    assert "recent" in again.reason


def test_dry_run_does_not_write(tmp_path: Path):
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    cube.append(
        entry_type="belief",
        description="auth-service uses redis for sessions",
        data={"crystal": True, "source": "wisdom_crystalizer"},
        outcome="success",
    )
    n_before = cube.entry_count
    result = merge_session_growth(
        cube,
        hermes_home=tmp_path,
        session_stats={"durable_writes": 3},
        dry_run=True,
    )
    assert result.merged
    assert result.reason == "dry_run"
    assert cube.entry_count == n_before
