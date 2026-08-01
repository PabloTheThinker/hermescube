"""Fleet HQ — charters, routing, claims, handoffs, verification, baseline."""

from __future__ import annotations

import json
import os
import tempfile
import time

from hermescube.cube import CubeFile
from hermescube.hive import init_hive
from hermescube.hq import (
    build_handoff_packet,
    claim_task,
    freeze_baseline,
    get_charter,
    lane_strip,
    list_charters,
    list_handoffs,
    record_handoff,
    register_charter,
    release_claim,
    retire_charter,
    route_task,
    set_route_override,
    verify_baseline,
    verify_fleet,
)
from hermescube.provider import CubeMemoryProvider


def _fleet(hq: str) -> None:
    register_charter(
        hq, "rza", role="command",
        lane="orchestration, routing, approvals, final synthesis",
        keywords=["routing", "approval", "synthesis"],
        boundaries=["owns external credentials", "owns publishing"],
    )
    register_charter(
        hq, "gza", role="specialist",
        lane="deep research and source verification",
        keywords=["research", "sources", "analysis", "verification"],
    )
    register_charter(
        hq, "masta-killa", role="specialist",
        lane="coding, debugging, testing, releases",
        keywords=["coding", "debugging", "testing", "release", "refactor"],
    )


class TestCharters:
    def test_register_and_list(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            cs = list_charters(td)
            assert len(cs) == 3
            assert get_charter(td, "rza")["role"] == "command"

    def test_charter_requires_lane_and_keywords(self):
        with tempfile.TemporaryDirectory() as td:
            r = register_charter(td, "x", role="specialist", lane="", keywords=[])
            assert not r["ok"]

    def test_retire_keeps_history_stops_routing(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            retire_charter(td, "gza")
            assert len(list_charters(td)) == 2
            assert len(list_charters(td, include_retired=True)) == 3
            r = route_task(td, "deep research on competitor sources")
            assert r["owner"] != "gza"  # command fallback, not the ghost


class TestRouting:
    def test_lane_keywords_route_to_specialist(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            r = route_task(td, "debugging the release pipeline tests")
            assert r["ok"]
            assert r["owner"] == "masta-killa"
            assert r["via"].startswith("lane:")

    def test_unmatched_falls_back_to_command(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            r = route_task(td, "rename this file please")
            assert r["owner"] == "rza"
            assert r["via"] == "command_fallback"

    def test_override_wins(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            set_route_override(td, "wordpress", "gza")
            r = route_task(td, "publish the wordpress draft")
            assert r["owner"] == "gza"
            assert r["via"] == "override:wordpress"


class TestClaims:
    def test_claim_conflict_and_release(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            a = claim_task(td, "gza", "audit repo licenses")
            assert a["ok"]
            b = claim_task(td, "masta-killa", "audit repo licenses")
            assert not b["ok"] and b["conflict"] and b["owner"] == "gza"
            assert release_claim(td, "gza", "audit repo licenses")
            c = claim_task(td, "masta-killa", "audit repo licenses")
            assert c["ok"]

    def test_same_agent_can_reclaim(self):
        with tempfile.TemporaryDirectory() as td:
            claim_task(td, "gza", "task x")
            r = claim_task(td, "gza", "task x")
            assert r["ok"]


class TestHandoffsAndPackets:
    def test_handoff_packet_distills_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            cube = CubeFile.create(os.path.join(td, "c.cube"))
            cube.append(
                "belief", "Northstar deploy requires systemd daemon-reload first",
                data={"durable": True, "trust": 0.9},
            )
            p = build_handoff_packet(
                cube, "fix the Northstar deploy failure",
                from_agent="rza", to_agent="masta-killa",
            )
            assert "Northstar" in p["context"]
            assert p["sha"]
            cube.close()

    def test_handoff_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            record_handoff(td, from_agent="rza", to_agent="gza",
                           task="research X", status="pending")
            hs = list_handoffs(td)
            assert len(hs) == 1 and hs[0]["status"] == "pending"


class TestVerification:
    def test_ghost_route_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            set_route_override(td, "editorial", "ghostface")  # never chartered
            r = verify_fleet(td)
            assert r["verdict"] == "flagged"
            assert any(f["flag"] == "ghost_route" for f in r["findings"])

    def test_lane_conflict_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            register_charter(
                td, "dupe", role="specialist", lane="also coding",
                keywords=["coding"],
            )
            r = verify_fleet(td)
            assert any(f["flag"] == "lane_conflict" for f in r["findings"])

    def test_no_command_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            register_charter(td, "solo", role="specialist", lane="x",
                             keywords=["x-lane"])
            r = verify_fleet(td)
            assert any(f["flag"] == "no_command" for f in r["findings"])

    def test_healthy_fleet(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            r = verify_fleet(td)
            assert r["verdict"] == "healthy"


class TestBaseline:
    def test_freeze_then_drift(self):
        with tempfile.TemporaryDirectory() as td:
            init_hive(td)
            _fleet(td)
            freeze_baseline(td)
            r = verify_baseline(td)
            assert r["clean"]
            register_charter(td, "new-agent", role="specialist",
                             lane="new lane", keywords=["newkw"])
            retire_charter(td, "gza")
            r2 = verify_baseline(td)
            assert not r2["clean"]
            assert any("added" in d for d in r2["drift"])
            assert any("changed" in d for d in r2["drift"])


class TestLaneStrip:
    def test_strip_shows_lane_and_others(self):
        with tempfile.TemporaryDirectory() as td:
            _fleet(td)
            s = lane_strip(td, "gza")
            assert "deep research" in s
            assert "masta-killa" in s
        # no charter → empty
        with tempfile.TemporaryDirectory() as td2:
            assert lane_strip(td2, "nobody") == ""


class TestProviderBoundaries:
    def test_subagent_gets_readonly_tools(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="c1", hermes_home=td, agent_context="subagent")
            names = {s["name"] for s in p.get_tool_schemas()}
            assert names == {
                "hermescube_search",
                "hermescube_probe",
                "hermescube_feedback",
                "hermescube_handoff",  # continuity packets are read/take safe for subagents
            }
            out = json.loads(p.handle_tool_call(
                "hermescube_manage", {"action": "add", "content": "sneaky write"}
            ))
            assert "boundary" in out.get("error", "")
            p.shutdown()

    def test_primary_keeps_full_tools(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="p1", hermes_home=td)
            names = {s["name"] for s in p.get_tool_schemas()}
            assert "hermescube_manage" in names
            p.shutdown()

    def test_manage_hq_route_and_verify(self):
        with tempfile.TemporaryDirectory() as td:
            hq = os.path.join(td, "hive")
            init_hive(hq)
            _fleet(hq)
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=os.path.join(td, "home"),
                         agent_identity="rza")
            p._hive_path = hq
            out = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "hq", "hq_action": "route",
                "content": "debugging the failing tests",
            }))
            assert out.get("owner") == "masta-killa"
            v = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "hq", "hq_action": "verify",
            }))
            assert v.get("verdict") == "healthy"
            p.shutdown()

    def test_lane_strip_in_system_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            hq = os.path.join(td, "hive")
            init_hive(hq)
            _fleet(hq)
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=os.path.join(td, "home"),
                         agent_identity="gza")
            p._hive_path = hq
            block = p.system_prompt_block()
            assert "HQ lane" in block
            assert "deep research" in block
            p.shutdown()

    def test_delegation_records_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            hq = os.path.join(td, "hive")
            init_hive(hq)
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=os.path.join(td, "home"),
                         agent_identity="rza")
            p._hive_path = hq
            p.on_delegation("research the docs", "found three relevant guides",
                            child_session_id="child-1")
            p._sync_queue.flush(timeout=5)
            hs = list_handoffs(hq)
            assert hs and hs[-1]["from_agent"] == "rza"
            assert hs[-1]["status"] == "completed"
            p.shutdown()
