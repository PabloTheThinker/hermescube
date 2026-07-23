"""Wisdom Crystalizer + durable-turn gate tests."""

from __future__ import annotations

from pathlib import Path

from hermescube import CubeFile, HARQueryEngine
from hermescube.wisdom import (
    crystalize,
    is_durable_turn,
    active_wisdom,
    functional_loop_stats,
    jaccard,
    tokens,
)


def test_is_durable_turn_gates_chitchat():
    assert not is_durable_turn("ok", "sure")
    assert not is_durable_turn("thanks", "np")
    assert not is_durable_turn("proceed", "go")
    assert is_durable_turn("hello", "hi there")
    assert is_durable_turn("Message 3", "Response 3")
    assert is_durable_turn(
        "Remember HermesCube is the deep warehouse",
        "Locked. MEMORY.md stays hot doctrine.",
    )
    assert is_durable_turn(
        "what is the path?",
        "Path: $HERMES_HOME/memories/memory.cube is the cube file",
    )


def test_jaccard_and_crystalize(tmp_path: Path):
    path = str(tmp_path / "w.cube")
    c = CubeFile.create(path)
    # near-duplicate facts
    c.append("landmark", "HermesCube never wipes memory.cube on update", data={"source": "hermescube_manage", "trust": 0.8})
    c.append("belief", "hermescube update never overwrites memory.cube data", data={"source": "hermescube_manage", "trust": 0.75})
    c.append("landmark", "HermesCube update pulls plugin but never wipes cube", data={"source": "seed", "trust": 0.7})
    c.append("trait", "Pablo prefers short monotropic reports under high load", data={"source": "hermescube_manage", "trust": 0.8})
    c.append("belief", "Under high load prefer short monotropic reports", data={"source": "hermescube_manage", "trust": 0.7})
    c.append("landmark", "ZP3 client agent runs on Hostinger VPS", data={"source": "seed", "trust": 0.9})

    dry = crystalize(c, dry_run=True)
    assert dry["crystals"] >= 1

    stats = crystalize(c, dry_run=False)
    assert stats["crystals"] >= 1
    ents = c.read_l1()
    crystals = [e for e in ents if (e.data or {}).get("crystal")]
    assert crystals
    loop = functional_loop_stats(ents)
    assert loop["crystal_count"] >= 1
    wisdom = active_wisdom(ents, limit=5)
    assert wisdom
    assert (wisdom[0].data or {}).get("crystal") or wisdom[0].entry_type == "belief"

    # crystals rank in query
    eng = HARQueryEngine(c)
    hits = eng.query("hermescube update never wipe cube", top_k=5)
    assert hits
    # top should be crystal or high belief
    top = hits[0][0]
    assert "wipe" in (top.description or "").lower() or "memory.cube" in (top.description or "").lower()
    c.close()


def test_tokens_stable():
    a = tokens("HermesCube warehouse MEMORY.md doctrine")
    b = tokens("doctrine MEMORY.md HermesCube warehouse")
    assert a == b
    assert jaccard(a, b) == 1.0
