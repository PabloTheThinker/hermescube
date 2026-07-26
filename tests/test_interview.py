"""Peer interview protocol — interview-me adapted for hive dialogues."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.hive import (
    build_soul_card,
    init_hive,
    pilgrimage,
    publish_soul_card,
    write_offering,
)
from hermescube.interview import (
    answer_from_sources,
    close_interview,
    format_brief_markdown,
    inspect_subject,
    list_interviews,
    mint_skill_draft,
    next_question,
    peer_dialogue,
    produce_brief,
    record_turn,
    start_interview,
)
from hermescube.provider import CubeMemoryProvider


def _seed_peer(hive: str, home: str, agent_id: str, facts: list[str]) -> None:
    mem = Path(home) / "memories"
    mem.mkdir(parents=True, exist_ok=True)
    cube = CubeFile.create(str(mem / "memory.cube"))
    for fact in facts:
        cube.append(
            "belief",
            fact,
            data={"durable": True, "trust": 0.85, "crystal": True, "source": "manage"},
        )
    cube.append("focus", f"{agent_id} mission: master {facts[0][:40]}", data={})
    card = build_soul_card(list(cube.read_l1()), agent_id=agent_id, hermes_home=home)
    publish_soul_card(hive, card)
    from hermescube.hive import build_offering

    rows = build_offering(cube, agent_id=agent_id)
    if rows:
        write_offering(hive, rows, agent_id=agent_id)
    cube.close()


class TestInspectAndAsk:
    def test_inspect_reads_soul_and_offerings(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            home = os.path.join(td, "researcher")
            _seed_peer(
                hive, home, "researcher",
                ["Always verify sources before citing competitive analysis"],
            )
            d = inspect_subject(hive, "researcher", topic="sources")
            assert d["soul"].get("wisdom") or d["soul"].get("beliefs") or d["offerings"]

    def test_next_question_stops_on_coverage(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            r = start_interview(
                hive, interviewer="coder", subject="researcher",
                topic="source verification", mode="discover",
            )
            assert r["ok"]
            session = r["session"]
            # Cover everything → done
            session["coverage"] = {d: "covered" for d in session["coverage"]}
            nq = next_question(session)
            assert nq["done"]


class TestAnswerGrounding:
    def test_answers_from_dossier_not_invented(self):
        dossier = {
            "subject_id": "gza",
            "soul": {
                "wisdom": ["Always triangulate three independent sources"],
                "procedures": ["1. collect 2. verify 3. cite"],
            },
            "offerings": [
                {"type": "belief", "description": "Never cite a single unverified source"},
            ],
            "charter": {
                "lane": "deep research",
                "boundaries": ["no publishing credentials"],
            },
        }
        ans = answer_from_sources(
            "What crystallized lesson has gza earned about source verification?",
            dossier,
            topic="source",
        )
        assert ans["kind"] == "fact"
        assert "triangulate" in ans["answer"] or "unverified" in ans["answer"]

    def test_unknown_when_no_evidence(self):
        ans = answer_from_sources(
            "What is the capital of Atlantis?",
            {"soul": {}, "offerings": [], "charter": None},
        )
        assert ans["kind"] == "unknown"


class TestBriefAndMint:
    def test_brief_contract_headings(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            home_a = os.path.join(td, "a")
            home_b = os.path.join(td, "b")
            _seed_peer(hive, home_a, "coder", ["Deploy with daemon-reload before restart"])
            _seed_peer(
                hive, home_b, "researcher",
                ["Always verify sources before citing competitive analysis"],
            )
            r = peer_dialogue(
                hive,
                interviewer="coder",
                subject="researcher",
                topic="source verification",
                mode="discover",
                hermes_home=home_a,
                persist=True,
                mint=True,
            )
            assert r["ok"]
            assert r["turns"] >= 1
            assert r["outcome"] in (
                "READY TO PROCEED",
                "PROCEED WITH ASSUMPTIONS",
                "PAUSED",
                "STOPPED",
            )
            brief_md = Path(r["brief_path"]).read_text(encoding="utf-8")
            for heading in (
                "Interview Outcome", "Objective", "Confirmed Context",
                "Constraints", "Preferences", "Tradeoffs and Decisions",
                "Unknowns", "Recommended Next Step",
            ):
                assert f"## {heading}" in brief_md
            # mint creates pending draft, not installed skill
            mint = r.get("mint") or {}
            if r["outcome"] in ("READY TO PROCEED", "PROCEED WITH ASSUMPTIONS"):
                assert mint.get("ok")
                draft = Path(mint["draft"])
                assert draft.is_file()
                assert "origin: hermescube-peer-interview" in draft.read_text()
                assert not (Path(home_a) / "skills").exists() or not any(
                    (Path(home_a) / "skills").rglob("SKILL.md")
                )

    def test_mint_rejects_paused_brief(self):
        brief = {
            "Interview Outcome": "PAUSED",
            "meta": {"subject": "x", "interviewer": "y", "topic": "z"},
        }
        with tempfile.TemporaryDirectory() as td:
            r = mint_skill_draft(brief, hermes_home=td)
            assert not r["ok"]


class TestPersistenceConsent:
    def test_close_without_persist_keeps_session_only(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            r = start_interview(
                hive, interviewer="a", subject="b", topic="x", mode="brief"
            )
            sid = r["session"]["id"]
            record_turn(
                hive, sid, dimension="wisdom",
                question="lesson?", answer="always test", kind="fact",
            )
            closed = close_interview(hive, sid, persist=False)
            assert closed["ok"] and not closed["persisted"]
            # brief file exists (session artifact) but no hive offering from interview
            assert Path(closed["brief_path"]).is_file()


class TestPilgrimageInterview:
    def test_pilgrimage_with_interview_flag(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            home_a = os.path.join(td, "coder")
            home_b = os.path.join(td, "researcher")
            _seed_peer(
                hive, home_a, "coder",
                ["Deploy with systemd daemon-reload before restart"],
            )
            _seed_peer(
                hive, home_b, "researcher",
                ["Always verify sources before citing competitive analysis"],
            )
            # researcher pilgrimages with interview → interviews coder
            r = pilgrimage(
                hive,
                hermes_home=home_b,
                agent_id="researcher",
                focus="deploy",
                interview=True,
                interview_peers=1,
            )
            assert r["ok"]
            interviews = r.get("interviews") or []
            assert interviews and interviews[0].get("ok")
            assert list_interviews(hive)


class TestProviderTool:
    def test_manage_interview_dialogue(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            home = os.path.join(td, "home")
            peer = os.path.join(td, "peer")
            _seed_peer(
                hive, peer, "peer-agent",
                ["Prefer small PRs with focused review"],
            )
            p = CubeMemoryProvider()
            p.initialize(
                session_id="s1", hermes_home=home, agent_identity="commander"
            )
            p._hive_path = hive
            out = json.loads(
                p.handle_tool_call(
                    "hermescube_manage",
                    {
                        "action": "interview",
                        "interview_action": "dialogue",
                        "agent": "peer-agent",
                        "content": "code review preferences",
                        "mode": "profile",
                    },
                )
            )
            assert out.get("status") == "dialogue"
            assert out.get("ok")
            listed = json.loads(
                p.handle_tool_call(
                    "hermescube_manage",
                    {"action": "interview", "interview_action": "list"},
                )
            )
            assert listed.get("interviews")
            p.shutdown()
