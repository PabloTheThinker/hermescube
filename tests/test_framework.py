"""Framework housing tests."""

from pathlib import Path
import tempfile

from hermescube.framework.paths import resolve_cube_paths
from hermescube.framework.config import coerce_bool, query_rewrite_enabled
from hermescube.framework.lexindex import LexIndex
from hermescube.framework.void import CubeVoid
from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
from hermescube.colony import ColonyGraph
from hermescube import mirror


def test_paths_profile():
    p = resolve_cube_paths("/tmp/hh", agent_identity="coder")
    assert p.cube.name == "memory.cube"
    assert "profiles" in str(p.memories_dir)
    assert "coder" in str(p.memories_dir)


def test_config_helpers():
    assert coerce_bool("yes") is True
    assert coerce_bool("0") is False
    assert query_rewrite_enabled({}) is False


def test_entity_hygiene():
    ents = mirror.extract_entities(
        "Mission Zero EOY 2026: cash-first; Pablo Navarro = Vektra CEO"
    )
    low = " ".join(e.lower() for e in ents)
    assert "mission zero" in low or "Mission Zero" in ents
    assert any("pablo" in e.lower() for e in ents)
    # bare fragments should not dominate
    assert "Zero" not in ents
    assert "Mission" not in ents or any(" " in e for e in ents if "mission" in e.lower())


def test_lexindex_candidates():
    class E:
        def __init__(self, i, d):
            self.id = i
            self.description = d
            self.entry_type = "belief"
            self.data = {}

    idx = LexIndex()
    idx.build([E("1", "dark mode preference"), E("2", "ship gate secrets")])
    c = idx.candidate_ids("dark mode")
    assert c and "1" in c


def test_void_recall_and_board():
    with tempfile.TemporaryDirectory() as td:
        paths = resolve_cube_paths(td)
        paths.ensure()
        cube = CubeFile.create(str(paths.cube))
        cube.append("relationship", "Pablo Navarro = Vektra CEO", data={"source": "seed", "trust": 0.9})
        cube.append("landmark", "Mission Zero cash-first board", data={"source": "seed", "trust": 0.9})
        eng = HARQueryEngine(cube)
        col = ColonyGraph(paths.colony_graph)
        void = CubeVoid(cube, eng, paths, colony=col)
        void.rebuild_lex()
        hits = void.recall("who is Pablo", top_k=3)
        assert hits
        text = void.format_prefetch(hits)
        assert "Pablo" in text
        # force board
        void.flush_board()
        assert paths.colony_board.is_file()
        cube.close()
