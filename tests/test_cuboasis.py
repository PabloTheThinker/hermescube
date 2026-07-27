"""Tests for Cuboasis — pocket-dimension memory infrastructure + Cubewave."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hermescube.claims import infer_spo_from_text, make_claim
from hermescube.cube import CubeFile
from hermescube.cuboasis import (
    bridge_claim_to_relation,
    chamber_filter_ids,
    connect_entity,
    cuboasis_status,
    progress_status,
    record_progress,
    space_map,
)
from hermescube.cubewave import Cubewave
from hermescube.provider import CubeMemoryProvider
from hermescube.relations import RelationStore


def test_space_map_chambers_and_vaults():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        cube = CubeFile.create(str(home / "memories" / "memory.cube"))
        try:
            cube.append(
                "belief",
                "Operator prefers dark mode",
                data={"durable": True, "crystal": True, "vault": "desk"},
            )
            cube.append(
                "focus",
                "Ship the Cuboasis infrastructure",
                data={"vault": "desk"},
            )
            cube.append(
                "trait",
                "Agent identity is coder",
                data={"source": "hermescube_peer_card"},
            )
            sm = space_map(cube, hermes_home=str(home), active_vault="desk")
        finally:
            cube.close()
        assert sm["ok"]
        assert sm["entries"] == 3
        assert sm["labeled_vault"] >= 2
        chambers = {c["chamber"]: c["entries"] for c in sm["chambers"]}
        assert chambers.get("doctrine", 0) >= 1
        assert chambers.get("intent", 0) >= 1
        assert chambers.get("identity", 0) >= 1
        vault_names = {v["vault"] for v in sm["vaults"]}
        assert "desk" in vault_names


def test_progress_ledger_and_usefulness():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        record_progress(str(home), "session_end", detail="boot", metrics={"durable_delta": 2})
        record_progress(
            str(home), "feedback", detail="helpful", metrics={"helpful": 1, "unhelpful": 0}
        )
        record_progress(
            str(home), "feedback", detail="unhelpful", metrics={"helpful": 0, "unhelpful": 1}
        )
        st = progress_status(str(home), limit=10)
        assert st["events"] >= 3
        assert st["kinds"].get("feedback") == 2
        assert st["usefulness"] == 0.5
        assert (home / "memories" / "progress.jsonl").is_file()


def test_connect_unifies_spo():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        store = RelationStore(str(home))
        store.record("Alice", "owns", "billing")
        store.record("billing", "uses", "Redis")
        report = connect_entity("billing", hermes_home=str(home), relation_store=store)
        assert report["ok"]
        assert report["counts"]["spo"] >= 2
        preds = {r["predicate"] for r in report["spo"]}
        assert "owns" in preds or "uses" in preds


def test_cuboasis_status_writes_state():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        cube_path = home / "memories" / "memory.cube"
        cube_path.parent.mkdir()
        cube = CubeFile.create(str(cube_path))
        try:
            cube.append(
                "belief",
                "Cuboasis is the spine of the pocket dimension",
                data={"durable": True, "crystal": True},
            )
            st = cuboasis_status(cube, str(home), active_vault="")
        finally:
            cube.close()
        assert st["ok"]
        assert st["framework"] == "cuboasis"
        assert st["space"]["entries"] >= 1
        assert Path(st["state_path"]).is_file()
        assert "cuboasis_state.json" in st["state_path"]


def test_cubewave_learn_and_boost():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "cubewave.json"
        wave = Cubewave(path, hidden=32)
        ids = ["e1", "e2", "e3"]
        wave.learn_coactivation(ids, query_text="auth service redis", strength=1.0)
        wave.learn_feedback(
            ["e1", "e2"],
            helpful=True,
            query_text="who owns auth",
        )
        boosts = wave.association_boosts(None, ids, query_text="who owns auth")
        assert boosts
        assert boosts["e1"] >= 1.0 or boosts["e2"] >= 1.0
        wave.save()
        assert path.is_file()
        wave2 = Cubewave(path, hidden=32)
        assert wave2.stats()["readouts"] >= 2


def test_claim_spo_bridge():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        spo = infer_spo_from_text("Alice owns billing service")
        assert spo is not None
        assert spo[0].lower().startswith("alice")
        assert spo[1] == "owns"
        claim = make_claim("Alice owns billing service", origin="user")
        assert claim.subject
        assert claim.object
        store = RelationStore(str(home))
        r = bridge_claim_to_relation(claim, store)
        assert r["ok"]
        hits = store.query("Alice", limit=5)
        assert len(hits) >= 1


def test_chamber_filter_and_provider_tools():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        p = CubeMemoryProvider(auto_extract=False)
        p.initialize(
            session_id="n1",
            hermes_home=str(home),
            platform="cli",
            agent_identity="coder",
            agent_workspace="cuboasis",
        )
        p.handle_tool_call(
            "hermescube_manage",
            {
                "action": "add",
                "entry_type": "belief",
                "content": "Project Alpha uses vault token for auth",
            },
        )
        p.handle_tool_call(
            "hermescube_manage",
            {
                "action": "add",
                "entry_type": "relationship",
                "content": "Alice owns billing service on Redis",
            },
        )

        space = json.loads(
            p.handle_tool_call("hermescube_manage", {"action": "space"})
        )
        assert space["status"] == "space"
        assert space["entries"] >= 2

        ch = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "space", "mode": "chamber:doctrine"},
            )
        )
        assert ch["chamber"] == "doctrine"
        assert p._chamber == "doctrine"
        ids = chamber_filter_ids(p._cube, "doctrine", limit=20)
        assert isinstance(ids, list)

        conn = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "connect", "content": "Alice"},
            )
        )
        assert conn["status"] == "connect"
        assert conn["ok"]

        prog = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "progress", "mode": "record", "content": "smoke"},
            )
        )
        assert prog.get("ok") or prog.get("status") == "progress"

        oasis = json.loads(
            p.handle_tool_call("hermescube_manage", {"action": "cuboasis"})
        )
        assert oasis["status"] == "cuboasis"
        assert "space" in oasis and "connections" in oasis and "progress" in oasis
        assert "wave" in oasis

        # legacy alias
        legacy = json.loads(
            p.handle_tool_call("hermescube_manage", {"action": "nexus"})
        )
        assert legacy["status"] == "cuboasis"

        prompt = p.system_prompt_block()
        assert "Cuboasis" in prompt or "Living Cube" in prompt

        # cubewave should be wired
        assert getattr(p, "_cubewave", None) is not None

        tri = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "triage", "mode": "apply"},
            )
        )
        assert tri.get("status") == "triage_apply"
        p.shutdown()


def test_session_end_writes_progress():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        p = CubeMemoryProvider(auto_extract=False)
        p.initialize(session_id="s1", hermes_home=str(home), platform="cli")
        for i in range(6):
            p.handle_tool_call(
                "hermescube_manage",
                {
                    "action": "add",
                    "entry_type": "belief",
                    "content": f"Durable fact number {i} about project auth",
                },
            )
        p.on_session_end([])
        p._sync_queue.flush(timeout=15)
        ledger = home / "memories" / "progress.jsonl"
        state = home / "memories" / "cuboasis_state.json"
        assert ledger.is_file() or state.is_file()
        p.shutdown()


def test_usefulness_folds_into_strength():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        cube = CubeFile.create(str(home / "memories" / "memory.cube"))
        try:
            for i in range(8):
                cube.append(
                    "belief",
                    f"Crystal doctrine fact {i} about HermesCube auth",
                    data={"durable": True, "crystal": True, "trust": 0.9},
                )
            from hermescube.genealogy import measure_strength

            base = measure_strength(cube, hermes_home=str(home))
            for _ in range(6):
                record_progress(
                    str(home),
                    "feedback",
                    detail="helpful",
                    metrics={"helpful": 1, "unhelpful": 0},
                )
            boosted = measure_strength(cube, hermes_home=str(home))
        finally:
            cube.close()
        assert boosted["usefulness"] == 1.0
        assert boosted["score"] >= base["score"]


def test_extract_cuboasis_entities():
    from hermescube import mirror

    ents = {e.lower() for e in mirror.extract_entities(
        "Cubewave resonates inside Cuboasis near the Cube of Eden; Alice owns billing"
    )}
    assert "cuboasis" in ents or "cubewave" in ents or "cube of eden" in ents
    assert "alice" in ents or any("alice" in e for e in ents)
    assert "billing" in ents
