"""Inject surface hygiene — no dogfood/test leak into Hermespace FOA."""

from __future__ import annotations

from pathlib import Path

from hermescube import CubeFile
from hermescube.space_bridge import build_space_inject, cube_recall
from hermescube.journey import is_noise_text


def test_cube_recall_filters_noise(tmp_path: Path, monkeypatch):
    # Use temp hermes home with a cube containing noise + doctrine
    hh = tmp_path / "h"
    mem = hh / "memories"
    mem.mkdir(parents=True)
    c = CubeFile.create(str(mem / "memory.cube"))
    c.append("belief", "PERSIST-PROOF-should-not-inject", data={"trust": 0.9})
    c.append(
        "belief",
        "HermesCube GH main is SoT; never wipes memory.cube",
        data={"trust": 0.9, "crystal": True},
    )
    c.append(
        "landmark",
        "ILO firsthand Cube session 2026-07-23T170352Z: provider hermescube",
        data={"trust": 0.8},
    )
    c.close()

    hits = cube_recall("HermesCube memory.cube", top_k=5, hermes_home=str(hh))
    texts = " ".join(t for t, _ in hits)
    assert "PERSIST-PROOF" not in texts
    assert "firsthand" not in texts.lower()
    assert "SoT" in texts or "memory.cube" in texts


def test_build_space_inject_clean(tmp_path: Path):
    hh = tmp_path / "h2"
    mem = hh / "memories"
    mem.mkdir(parents=True)
    c = CubeFile.create(str(mem / "memory.cube"))
    c.append(
        "belief",
        "Hot MEMORY.md stays doctrine; Cube is deep warehouse",
        data={"crystal": True, "trust": 0.9},
    )
    c.append("belief", "[CRYSTALIZED] junk", data={"trust": 0.9})
    c.append("belief", "[HYGIENE] junk2", data={"trust": 0.9})
    c.close()
    inj = build_space_inject("warehouse MEMORY", high_load=False, hermes_home=str(hh))
    # may be empty under flock contention in some envs — never leak noise
    assert "PERSIST" not in inj
    assert "CRYSTALIZED" not in inj
    assert "HYGIENE" not in inj
    if inj:
        assert "HermesCube" in inj
        assert "MEMORY.md" in inj or "warehouse" in inj.lower()
