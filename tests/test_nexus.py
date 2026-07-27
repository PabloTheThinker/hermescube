"""Tests for Nexus — functional memory infrastructure."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.nexus import (
    connect_entity,
    nexus_status,
    progress_status,
    record_progress,
    space_map,
)
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
                "Ship the nexus infrastructure",
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


def test_nexus_status_writes_state():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        cube_path = home / "memories" / "memory.cube"
        cube_path.parent.mkdir()
        cube = CubeFile.create(str(cube_path))
        try:
            cube.append("belief", "Nexus is the spine", data={"durable": True, "crystal": True})
            st = nexus_status(cube, str(home), active_vault="")
        finally:
            cube.close()
        assert st["ok"]
        assert st["space"]["entries"] >= 1
        assert Path(st["state_path"]).is_file()


def test_provider_space_connect_progress_nexus_tools():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        p = CubeMemoryProvider(auto_extract=False)
        p.initialize(
            session_id="n1",
            hermes_home=str(home),
            platform="cli",
            agent_identity="coder",
            agent_workspace="nexus",
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

        nexus = json.loads(
            p.handle_tool_call("hermescube_manage", {"action": "nexus"})
        )
        assert nexus["status"] == "nexus"
        assert "space" in nexus and "connections" in nexus and "progress" in nexus

        prompt = p.system_prompt_block()
        assert "Nexus infra" in prompt or "Living Cube" in prompt

        # triage apply should not crash on empty-ish queues
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
        # May take a moment for background work
        assert ledger.is_file() or (home / "memories" / "nexus_state.json").is_file()
        p.shutdown()
