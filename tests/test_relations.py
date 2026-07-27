"""SPO relations sidecar."""

from __future__ import annotations

from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.relations import RelationStore, format_for_prompt, ingest_entry


def test_record_query_expire_as_of(tmp_path: Path):
    hh = tmp_path / "home"
    (hh / "memories").mkdir(parents=True)
    store = RelationStore(hh)
    store.record("alice", "owns", "auth-service", valid_from="2026-01-01")
    store.record("bob", "owns", "billing", valid_from="2026-01-01")
    hits = store.query("alice")
    assert len(hits) == 1
    assert hits[0].predicate == "owns"

    as_of = store.query("alice", as_of="2026-06-01")
    assert len(as_of) == 1

    n = store.expire("alice", "owns", "auth-service", ended="2026-03-01")
    assert n == 1
    assert store.query("alice", as_of="2026-06-01") == []
    assert len(store.query("alice", as_of="2026-02-01")) == 1

    st = store.stats()
    assert st["relations"] == 2
    assert st["open"] == 1


def test_ingest_dot_link_and_entities(tmp_path: Path):
    hh = tmp_path / "home"
    (hh / "memories").mkdir(parents=True)
    store = RelationStore(hh)
    cube = CubeFile.create(str(tmp_path / "m.cube"))
    entry = cube.append(
        entry_type="relationship",
        description="[DOT] Redis: auth uses cache ↔ billing uses cache",
        data={
            "dot_link": True,
            "entity": "Redis",
            "links": ["id-a", "id-b"],
            "source": "living_connect",
        },
        outcome="success",
    )
    ids = ingest_entry(entry, store)
    assert len(ids) >= 1
    assert store.query("Redis")

    belief = cube.append(
        entry_type="belief",
        description="AuthService depends on Redis for session tokens",
        data={"source": "hermescube_manage", "trust": 0.7},
        outcome="success",
    )
    ingest_entry(belief, store)
    # entity extract or capitalised tokens should create at least one link
    assert store.stats()["relations"] >= 2

    prompt = format_for_prompt(store.query("Redis"))
    assert "### Relations" in prompt
    assert "Redis" in prompt
