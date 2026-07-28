"""Anatomical center tests — circulatory Cube ↔ Hermespace integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hermescube import center
from hermescube.center import CENTER_API_VERSION, ANATOMY
from hermescube.space_bridge import GENERATOR_API_VERSION


def test_center_api_extends_heart():
    assert CENTER_API_VERSION.startswith("1.")
    assert GENERATOR_API_VERSION.startswith("1.")
    assert "heart" in ANATOMY
    assert "nervous_foa" in ANATOMY
    assert "immune" in ANATOMY


def test_strip_budget_sweller_levels():
    assert center.strip_budget("low") == 900
    assert center.strip_budget("high") == 420
    assert center.strip_budget("protect") == 280
    assert center.strip_budget(0.9) == 280
    assert center.strip_budget(0.7) == 420
    assert center.strip_budget(high_load=True) == 420


def test_center_status_organs():
    with tempfile.TemporaryDirectory() as td:
        st = center.center_status(hermes_home=td)
        assert st["api_version"] == CENTER_API_VERSION
        assert st["role"] == "center"
        assert "nous_methods" in st
        assert "space_methods" in st
        # ensure then ready
        from hermescube.space_bridge import ensure_heart

        ensure_heart(hermes_home=td)
        st2 = center.center_status(hermes_home=td)
        assert st2["ok"] is True
        assert st2["heart"]["heart_ready"] is True
        assert st2["organs"]["heart"]["ready"] is True
        assert st2["organs"]["nervous_foa"]["ready"] is None


def test_beat_systole_diastole():
    with tempfile.TemporaryDirectory() as td:
        home = str(Path(td))
        out = center.beat(
            "Hermespace FOA under load prefers dense cube blood",
            seals="Operator seals a landmark from the desk into the heart",
            entry_type="landmark",
            load="high",
            hermes_home=home,
            agent_id="ilo",
        )
        assert out["ok"] is True
        assert out["phases"]["ensure"]["ok"] is True
        assert out["phases"]["systole"]["count"] >= 1
        assert "diastole" in out["phases"]
        assert out["load_level"] == "high"
        # strip present or empty cold — heart header when content exists
        block = out.get("block") or ""
        if block:
            assert "HermesCube" in block
            assert len(block) <= 500


def test_supply_and_return_aliases():
    with tempfile.TemporaryDirectory() as td:
        home = str(Path(td))
        ret = center.systole(
            ["Belief A from desk", "Belief B from desk"],
            hermes_home=home,
        )
        assert ret["count"] == 2
        sup = center.diastole("Belief from desk", load="mid", hermes_home=home)
        assert sup["phase"] == "diastole"
        assert sup["max_chars"] == 640


def test_autonomic_tick():
    with tempfile.TemporaryDirectory() as td:
        home = str(Path(td))
        center.return_flow(
            "Wisdom that charges the world on autonomic tick",
            hermes_home=home,
            trust=0.9,
        )
        report = center.autonomic_tick(hermes_home=home, agent_id="bench")
        assert report["phase"] == "autonomic"
        assert report["ok"] is True
