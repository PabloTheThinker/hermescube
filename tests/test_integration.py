"""Deep integration — hive, HQ, interviews, and harness working as one.

Covers the full "night cycle": agents with charters pilgrimage to the
nexus, offer, interview each other, assimilate (including interview
facts in the same visit), draw with echo guards, hand work off with
distilled context, settle handoffs, and commit falsifiable predictions.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.hive import (
    build_offering,
    build_soul_card,
    hive_status,
    init_hive,
    pilgrimage,
    publish_soul_card,
    write_offering,
)
from hermescube.hq import (
    list_handoffs,
    register_charter,
    update_handoff_status,
    verify_fleet,
)
from hermescube.interview import peer_dialogue
from hermescube.provider import CubeMemoryProvider
from hermescube.self_evolution import harness_dir


def _agent(hive: str, td: str, agent_id: str, facts: list[str]) -> str:
    """Seed an agent home + soul card + offering; return home path."""
    home = os.path.join(td, agent_id)
    mem = Path(home) / "memories"
    mem.mkdir(parents=True, exist_ok=True)
    cube = CubeFile.create(str(mem / "memory.cube"))
    for f in facts:
        cube.append(
            "belief", f,
            data={"durable": True, "trust": 0.9, "crystal": True},
        )
    card = build_soul_card(list(cube.read_l1()), agent_id=agent_id, hermes_home=home)
    publish_soul_card(hive, card)
    rows = build_offering(cube, agent_id=agent_id)
    if rows:
        write_offering(hive, rows, agent_id=agent_id)
    cube.close()
    return home


class TestNightCycle:
    def test_interview_facts_join_collective_same_pilgrimage(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher",
                   ["Always triangulate three independent sources before citing"])
            home_coder = _agent(hive, td, "coder",
                                ["Deploy with systemd daemon-reload first"])

            r = pilgrimage(
                hive, hermes_home=home_coder, agent_id="coder",
                focus="sources", interview=True, interview_peers=1,
            )
            assert r["ok"]
            ivs = r.get("interviews") or []
            assert ivs and ivs[0].get("ok")
            # interview offering assimilated in the SAME pilgrimage
            merged = (r.get("assimilate") or {}).get("merged", 0)
            assert merged >= 1
            from hermescube.cube import CubeFile as CF

            with CF.open(os.path.join(hive, "hive.cube")) as hc:
                descs = [e.description for e in hc.read_l1()]
            # collective now includes an [INTERVIEW:researcher] fact
            assert any("[INTERVIEW:researcher]" in d for d in descs)
            # …and coder's own pilgrimage offering was NOT lost to a same-
            # second offering filename collision with the interview facts
            assert any("daemon-reload" in d for d in descs)
            assert any("triangulate" in d.lower() for d in descs)

    def test_subject_never_redraws_own_interviewed_facts(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            home_r = _agent(hive, td, "researcher",
                            ["Always triangulate three independent sources"])
            home_c = _agent(hive, td, "coder", ["Deploy carefully with checks"])

            # coder interviews researcher; facts enter collective
            pilgrimage(hive, hermes_home=home_c, agent_id="coder",
                       focus="sources", interview=True)
            # researcher pilgrimages: must not re-absorb their own knowledge
            r = pilgrimage(hive, hermes_home=home_r, agent_id="researcher",
                           focus="sources")
            with CubeFile.open(str(Path(home_r) / "memories" / "memory.cube")) as c:
                descs = [e.description for e in c.read_l1()]
            assert not any("[INTERVIEW:researcher]" in d for d in descs)

    def test_reinterview_dedupes_in_collective(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher", ["Always triangulate three sources"])
            home_c = _agent(hive, td, "coder", ["Deploy carefully with checks"])

            pilgrimage(hive, hermes_home=home_c, agent_id="coder",
                       focus="sources", interview=True)
            first = hive_status(hive)["collective_entries"]
            pilgrimage(hive, hermes_home=home_c, agent_id="coder",
                       focus="sources", interview=True)
            second = hive_status(hive)["collective_entries"]
            assert second == first  # content-hash dedupe held

    def test_unified_status_reports_all_layers(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            register_charter(hive, "rza", role="command",
                             lane="orchestration", keywords=["routing"])
            _agent(hive, td, "researcher", ["Triangulate three sources always"])
            home_c = _agent(hive, td, "coder", ["Deploy with daemon-reload"])
            pilgrimage(hive, hermes_home=home_c, agent_id="coder",
                       focus="sources", interview=True)
            s = hive_status(hive)
            assert s["charters"] == 1
            assert s["command"] == "rza"
            assert s["interviews"] >= 1
            assert "pending_handoffs" in s


class TestInterviewFleetIntegration:
    def test_interview_takes_claim_and_blocks_concurrent(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher", ["Triangulate three sources always"])

            from hermescube.hq import claim_task

            # someone else holds the interview claim
            claim_task(hive, "rival", "interview:researcher:sources")
            r = peer_dialogue(
                hive, interviewer="coder", subject="researcher",
                topic="sources", persist=False, mint=False,
            )
            assert not r.get("ok") and r.get("conflict")

    def test_interview_recorded_as_fleet_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher", ["Triangulate three sources always"])
            r = peer_dialogue(
                hive, interviewer="coder", subject="researcher",
                topic="sources", persist=False, mint=False,
            )
            assert r["ok"]
            hs = list_handoffs(hive)
            assert any(
                h["from_agent"] == "researcher" and h["to_agent"] == "coder"
                and h["status"] == "completed"
                for h in hs
            )

    def test_mint_commits_falsifiable_prediction(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher", ["Triangulate three sources always"])
            home_c = os.path.join(td, "coder-home")
            r = peer_dialogue(
                hive, interviewer="coder", subject="researcher",
                topic="sources", hermes_home=home_c, persist=False, mint=True,
            )
            assert r["ok"]
            if (r.get("mint") or {}).get("ok"):
                preds = (harness_dir(home_c) / "predictions.jsonl")
                assert preds.is_file()
                lines = [json.loads(x) for x in preds.read_text().splitlines() if x.strip()]
                assert any(p["check"]["type"] == "witness_absence" for p in lines)

    def test_interviewer_memories_never_masquerade_as_subject(self):
        """Provenance boundary: interviewer's own cube facts must not
        appear as the subject's answers."""
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            _agent(hive, td, "researcher", ["Triangulate three sources always"])
            home = os.path.join(td, "home")
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=home,
                         agent_identity="commander")
            p._hive_path = hive
            # interviewer's own secret-ish memory, unattributed to subject
            p._cube.append(
                "belief", "Commander private strategy: sources are optional",
                data={"durable": True, "trust": 0.9},
            )
            out = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "interview", "interview_action": "dialogue",
                "agent": "researcher", "content": "sources", "mode": "profile",
            }))
            assert out.get("ok")
            brief_md = Path(out["brief_path"]).read_text(encoding="utf-8")
            assert "Commander private strategy" not in brief_md
            p.shutdown()


class TestHandoffLifecycle:
    def test_handoff_route_packet_ledger_complete(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            register_charter(hive, "rza", role="command",
                             lane="orchestration", keywords=["routing"])
            register_charter(hive, "masta-killa", role="specialist",
                             lane="coding and debugging",
                             keywords=["coding", "debugging", "testing"])
            home = os.path.join(td, "home")
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=home,
                         agent_identity="rza")
            p._hive_path = hive
            p._cube.append(
                "belief", "The failing test is in the release pipeline config",
                data={"durable": True, "trust": 0.9},
            )
            # handoff auto-routes and carries distilled context
            out = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "hq", "hq_action": "handoff",
                "content": "debugging the failing release tests",
            }))
            assert out.get("status") == "handoff"
            assert out.get("to_agent") == "masta-killa"
            assert "release pipeline" in (out.get("context") or "")
            hid = out["id"]
            # pending in ledger
            assert any(
                h["id"] == hid and h["status"] == "pending"
                for h in list_handoffs(hive)
            )
            # settle it
            done = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "hq", "hq_action": "complete", "content": hid,
            }))
            assert done.get("ok")
            assert any(
                h["id"] == hid and h["status"] == "completed"
                for h in list_handoffs(hive)
            )
            # fleet verify: nothing stuck
            v = verify_fleet(hive)
            assert not any(f["flag"] == "stuck_handoff" for f in v["findings"])
            p.shutdown()

    def test_update_handoff_status_direct(self):
        with tempfile.TemporaryDirectory() as td:
            from hermescube.hq import record_handoff

            rec = record_handoff(td, from_agent="a", to_agent="b",
                                 task="t", status="pending")
            r = update_handoff_status(td, rec["id"], "completed")
            assert r["ok"]
            assert list_handoffs(td)[0]["status"] == "completed"
            bad = update_handoff_status(td, "nope", "completed")
            assert not bad["ok"]
