"""Tests for mirror layer (entity graph + expand)."""

from hermescube import mirror
from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
import tempfile
import os


def test_extract_entities():
    ents = mirror.extract_entities("Pablo Navarro = Vektra CEO. Path $HERMES_HOME/memories")
    low = {e.lower() for e in ents}
    blob = " ".join(ents)
    assert any("pablo" in e for e in low)
    assert "HERMES_HOME" in blob or "hermes_home" in low


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
    assert "b" in ids


def test_har_mirror_integration():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.cube")
        cube = CubeFile.create(path)
        cube.append("relationship", "Pablo Navarro = Vektra CEO")
        cube.append("landmark", "Pablo Navarro Mission Zero cash-first board")
        cube.append("belief", "Unrelated cryptography paper notes")
        eng = HARQueryEngine(cube)
        hits = eng.query("who is Pablo", top_k=3)
        descs = " ".join(e.description for e, _ in hits)
        assert "Pablo" in descs
        cube.close()

def test_extract_machine_identifiers():
    ents = {e.lower() for e in mirror.extract_entities(
        "Deployed auth-service v2.1 to the eu-west cluster from memory.cube"
    )}
    assert "auth-service" in ents
    assert "eu-west" in ents
    assert "memory.cube" in ents


def test_extract_bare_proper_noun_but_not_leading_verb():
    ents = {e.lower() for e in mirror.extract_entities(
        "Grafana dashboard tracks auth-service latency"
    )}
    assert "grafana" in ents
    # sentence-opening inflected verbs must not become entities
    verbs = mirror.extract_entities("Deployed the service and Migrated the database")
    assert not {e.lower() for e in verbs} & {"deployed", "migrated"}


def test_multiword_name_does_not_leak_fragments():
    ents = mirror.extract_entities("Alice Nguyen reviewed the change")
    assert "Alice Nguyen" in ents
    assert "Alice" not in ents and "Nguyen" not in ents


def test_norm_key_collapses_separator_variants():
    assert (
        mirror.norm_key("auth-service")
        == mirror.norm_key("auth_service")
        == mirror.norm_key("Auth Service")
        == "auth service"
    )


def test_mine_corpus_terms_finds_recurring_plain_words():
    """Plain lowercase words like "redis" are entities but are invisible to
    per-sentence rules; they separate from filler by document frequency."""
    descs = [
        "auth-service depends on redis for sessions",
        "Fixed the redis connection pool leak",
        "redis evicts keys under memory pressure",
    ] + [f"routine batch {i} handling ordinary traffic" for i in range(30)]
    terms, _phrases = mirror.mine_corpus_terms(descs)
    assert "redis" in terms
    # ubiquitous background vocabulary must stay out of the graph
    assert "routine" not in terms and "batch" not in terms


def test_build_entity_index_links_via_mined_term():
    class E:
        def __init__(self, i, d):
            self.id = i
            self.description = d
            self.data = {}
            self.causal_parents = []

    entries = [
        E("1", "auth-service depends on redis for sessions"),
        E("2", "Fixed the redis connection pool leak"),
        E("3", "redis evicts keys under memory pressure"),
        E("4", "totally unrelated widgets inventory note"),
    ]
    idx = mirror.build_entity_index(entries)
    assert sorted(e.id for e in idx["redis"]) == ["1", "2", "3"]


def test_mirror_expand_prefers_rare_shared_entity():
    """A neighbour linked through a rare entity outranks one linked through
    an entity that half the archive shares."""
    class E:
        def __init__(self, i, ents):
            self.id = i
            self.description = f"entry {i}"
            self.data = {"entities": ents}
            self.causal_parents = []

    seed = E("seed", ["shared-node", "rare-node"])
    via_rare = E("rare_hit", ["rare-node"])
    commons = [E(f"c{i}", ["shared-node"]) for i in range(6)]
    all_entries = [seed, via_rare, *commons]
    idx = mirror.build_entity_index(all_entries, mine=False)
    out = mirror.mirror_expand([(seed, 1.0)], all_entries, top_k=2, entity_index=idx)
    assert [e.id for e, _ in out] == ["seed", "rare_hit"]
