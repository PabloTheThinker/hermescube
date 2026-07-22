"""Colony stigmergy tests — original Cube, not holographic port."""

from hermescube.colony import ColonyGraph, dance_payload, resource_kind
from hermescube.provider import CubeMemoryProvider
import tempfile
from pathlib import Path


def test_resource_kinds():
    assert resource_kind("trait", "User prefers dark mode") == "preference"
    assert resource_kind("relationship", "Alex = lead") == "social"
    assert resource_kind("landmark", "Mission path $HERMES_HOME") == "route"


def test_pheromone_deposit_and_boost():
    g = ColonyGraph()
    g.deposit(["pablo", "mission zero", "cash"], amount=1.0)
    b = g.trail_boost(["pablo"], ["mission zero"])
    assert b > 1.0
    b2 = g.trail_boost(["pablo"], ["unrelated_xyz"])
    assert b2 >= 1.0
    assert b >= b2


def test_markdown_board(tmp_path: Path):
    g = ColonyGraph(tmp_path / "g.json")
    g.deposit(["alpha", "beta"], amount=2.0)

    class E:
        id = "abc123"
        description = "Alpha Beta route home"
        entry_type = "landmark"
        data = {"entities": ["Alpha", "Beta"]}

    g.register_dance(E())
    md = tmp_path / "COLONY.md"
    g.write_markdown_board(md)
    text = md.read_text()
    assert "Colony board" in text
    assert "trails" in text.lower() or "alpha" in text.lower()


def test_provider_writes_colony_board():
    with tempfile.TemporaryDirectory() as td:
        p = CubeMemoryProvider()
        p.initialize(session_id="c", hermes_home=td, platform="cli")
        p._cube.append(
            "relationship",
            "Pablo Navarro = Vektra CEO",
            data={"source": "seed", "trust": 0.9},
        )
        p._cube.append(
            "landmark",
            "Pablo Navarro Mission Zero cash board",
            data={"source": "seed", "trust": 0.9},
        )
        # refresh snapshot for prefetch
        p._refresh_snapshot()
        text = p.prefetch("who is Pablo")
        assert text
        board = Path(td) / "memories" / "COLONY.md"
        assert board.is_file(), board
        body = board.read_text()
        assert "Colony" in body
        p.shutdown()
