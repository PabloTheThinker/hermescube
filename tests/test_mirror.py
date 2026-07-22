"""Tests for mirror layer (entity graph + expand)."""

from hermescube import mirror
from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
import tempfile
import os


def test_extract_entities():
    ents = mirror.extract_entities('Pablo Navarro = Vektra CEO. Path $HERMES_HOME/memories')
    low = {e.lower() for e in ents}
    assert any("pablo" in e for e in low)
    assert any("hermes_home" in e or "$HERMES_HOME" in ents or "HERMES_HOME" in "".join(ents))


def test_mirror_expand_pulls_coentity():
    class E:
        def __init__(self, i, d, parents=None):
            self.id = i
            self.description = d
            self.data = {}
            self.causal_parents = parents or []
            self.entry_type = "landmark"
            self.outcome = "none"
            self.timestamp = "2026-07-22T00:00:00"

    a = E("a", "Pablo Navarro runs Mission Zero cash board")
    b = E("b", "Mission Zero EOY 2026 is cash-first")
    c = E("c", "Unrelated widgets factory")
    idx = mirror.build_entity_index([a, b, c])
    out = mirror.mirror_expand([(a, 1.0)], [a, b, c], top_k=3, entity_index=idx)
    ids = [e.id for e, _ in out]
    assert "a" in ids
    assert "b" in ids  # co-entity Mission Zero


def test_har_mirror_integration():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.cube")
        cube = CubeFile.create(path)
        e1 = cube.append("relationship", "Pablo Navarro = Vektra CEO")
        cube.append("landmark", "Pablo Navarro Mission Zero cash-first board")
        cube.append("belief", "Unrelated cryptography paper notes")
        eng = HARQueryEngine(cube)
        hits = eng.query("who is Pablo", top_k=3)
        descs = " ".join(e.description for e, _ in hits)
        assert "Pablo" in descs
        cube.close()
