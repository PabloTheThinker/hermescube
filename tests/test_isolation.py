"""Multi-workspace sidecar isolation + vault soft filter."""

from __future__ import annotations

from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.engram_net import EngramNet, default_path as engram_path
from hermescube.framework.paths import (
    migrate_legacy_sidecars,
    resolve_cube_paths,
    should_nest_profiles,
)
from hermescube.har import HARQueryEngine
from hermescube.relations import RelationStore
from hermescube.triage import plan_path


def test_should_nest_requires_identity_and_workspace():
    assert should_nest_profiles("a", "b") is True
    assert should_nest_profiles("a", "") is False
    assert should_nest_profiles("", "b") is False


def test_two_workspaces_distinct_sidecars(tmp_path: Path):
    hh = tmp_path / "hh"
    a = resolve_cube_paths(
        hh, agent_identity="agent", agent_workspace="ws-a", nest_profiles=True
    )
    b = resolve_cube_paths(
        hh, agent_identity="agent", agent_workspace="ws-b", nest_profiles=True
    )
    assert a.cube == b.cube
    assert a.engram != b.engram
    assert a.relations != b.relations
    assert a.triage_plan != b.triage_plan

    a.engram.parent.mkdir(parents=True, exist_ok=True)
    a.engram.write_text('{"v":1,"patterns":[],"edges":{"x":{"y":0.5}}}', encoding="utf-8")
    RelationStore(path=a.relations).record("Alice", "owns", "AuthA")
    RelationStore(path=b.relations).record("Bob", "owns", "AuthB")

    assert a.engram.is_file()
    assert a.engram != b.engram
    assert not b.engram.is_file()
    assert RelationStore(path=a.relations).stats()["relations"] >= 1
    sa = {r.subject for r in RelationStore(path=a.relations).query("Alice")}
    sb = {r.subject for r in RelationStore(path=b.relations).query("Bob")}
    assert "Alice" in sa
    assert "Bob" in sb
    assert not RelationStore(path=a.relations).query("Bob")


def test_migrate_legacy_sidecars_copies_once(tmp_path: Path):
    hh = tmp_path / "hh"
    legacy = hh / "memories"
    legacy.mkdir(parents=True)
    (legacy / "engram_net.json").write_text('{"patterns":[],"edges":{}}', encoding="utf-8")
    (legacy / "triage_plan.json").write_text('{"counts":{}}', encoding="utf-8")

    nested = resolve_cube_paths(
        hh, agent_identity="agent", agent_workspace="ws", nest_profiles=True
    )
    copied = migrate_legacy_sidecars(nested)
    assert "engram_net.json" in copied
    assert nested.engram.is_file()
    # legacy preserved
    assert (legacy / "engram_net.json").is_file()
    # second pass no-op
    assert migrate_legacy_sidecars(nested) == []


def test_unlabeled_legacy_still_recalls(tmp_path: Path):
    """Vault soft boost must never hard-drop unlabeled entries."""
    cube_path = tmp_path / "memory.cube"
    cube = CubeFile.create(str(cube_path))
    cube.append(
        "belief",
        "Legacy Redis caches AuthService for sessions",
        data={"trust": 0.9, "durable": True},
    )
    cube.append(
        "belief",
        "Workspace Postgres stores AuthService users",
        data={"trust": 0.9, "durable": True, "vault": "ws-a"},
    )
    eng = HARQueryEngine(cube)
    eng._active_vault = "ws-a"
    hits = eng.query("AuthService", top_k=5)
    descs = [e.description for e, _score in hits]
    assert any("Legacy Redis" in d for d in descs)
    assert any("Postgres" in d for d in descs)
    cube.close()


def test_default_path_helpers_respect_nest(tmp_path: Path):
    hh = tmp_path / "hh"
    ep = engram_path(
        hh, agent_identity="a", agent_workspace="w", nest_profiles=True
    )
    tp = plan_path(
        hh, agent_identity="a", agent_workspace="w", nest_profiles=True
    )
    assert "profiles" in str(ep)
    assert "profiles" in str(tp)
    assert ep.parent == tp.parent
