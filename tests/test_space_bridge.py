"""Space bridge tests (no Hermespace required)."""

import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube import space_bridge


def test_build_space_inject_high_load_small():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        cp = home / "memories" / "memory.cube"
        CubeFile.create(str(cp))
        with CubeFile.open(str(cp)) as c:
            c.append(
                "relationship",
                "Pablo Navarro = Vektra CEO for company agents",
                data={"source": "seed", "trust": 0.9, "durable": True},
            )
            c.append(
                "landmark",
                "HermesCube is the deep memory module for Hermespace high load",
                data={"source": "seed", "trust": 0.9, "durable": True},
            )
        block = space_bridge.build_space_inject(
            "Hermespace high load memory module",
            high_load=True,
            hermes_home=str(home),
        )
        assert "HermesCube" in block
        assert len(block) <= 500
        assert "deep memory" in block.lower() or "module" in block.lower()


def test_seal_and_status():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        CubeFile.create(str(home / "memories" / "memory.cube"))
        assert space_bridge.seal_to_cube(
            "Space sealed a decision about FOA cube integration",
            hermes_home=str(home),
        )
        st = space_bridge.module_status(hermes_home=str(home))
        assert st["available"]
        assert st["entries"] >= 1
