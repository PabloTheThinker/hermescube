"""Tests for Cuboasis memory gate — safety, candidates, curation, doctor."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.memory_gate import (
    approve_candidate,
    capture_candidate,
    curation_sync_report,
    decide_write_path,
    list_candidates,
    memory_safety,
    oasis_doctor_card,
    recall_rejected,
    reject_candidate,
)
from hermescube.provider import CubeMemoryProvider


def test_memory_safety_blocks_credentials_and_logs():
    s = memory_safety("rotate api_key sk-abcdef", "password=hunter2")
    assert s["status"] == "blocked"
    assert "sensitive_credential_like_text" in s["review_reasons"]

    loggy = memory_safety(
        "build failed",
        "Traceback (most recent call last):\n  File x.py\nException: boom",
    )
    assert loggy["status"] == "blocked"

    temp = memory_safety("WIP for this session pending CI", "temporary note")
    assert temp["status"] == "needs_review"
    assert "temporary_task_progress" in temp["review_reasons"]

    clean = memory_safety("Alice owns billing", "Alice owns the billing service")
    assert clean["status"] == "safe"
    assert clean["safe_to_auto_approve"] is True


def test_decide_write_path_policies():
    safe = memory_safety("fact", "Project uses Redis")
    risky = memory_safety("wip", "temporary task progress for this session")
    blocked = memory_safety("secret", "api_key=abc")

    assert decide_write_path(safe, policy="auto-safe") == "durable"
    assert decide_write_path(risky, policy="auto-safe") == "candidate"
    assert decide_write_path(safe, policy="review-first") == "candidate"
    assert decide_write_path(blocked, policy="auto-safe") == "candidate"
    assert decide_write_path(blocked, policy="auto-safe", explicit=True) == "block"
    assert decide_write_path(safe, policy="off") == "skip"


def test_candidate_capture_approve_reject_flow():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        cube = CubeFile.create(str(home / "memories" / "memory.cube"))
        try:
            cap = capture_candidate(
                str(home),
                "Cuboasis should store reviewed project facts",
                source="test",
            )
            assert cap["ok"]
            cid = cap["candidate_id"]
            queue = list_candidates(str(home), status="pending")
            assert queue["count"] >= 1
            assert any(c["candidate_id"] == cid for c in queue["candidates"])

            approved = approve_candidate(str(home), cid, cube=cube)
            assert approved["ok"]
            assert approved["entry_id"]
            entries = list(cube.read_l1() or [])
            assert any("reviewed project facts" in (e.description or "") for e in entries)
            data = next(
                e.data for e in entries if "reviewed project facts" in (e.description or "")
            )
            assert data.get("evidence_state") == "verified"

            cap2 = capture_candidate(str(home), "Bad idea: store raw api_key forever", source="test")
            # may be blocked_review_required
            cid2 = cap2["candidate_id"]
            rejected = reject_candidate(str(home), cid2, reason="unsafe")
            assert rejected["ok"]
            neg = recall_rejected(str(home), "api_key")
            assert neg["count"] >= 1
            assert all(h.get("not_approved") for h in neg["rejected"])
        finally:
            cube.close()


def test_curation_and_doctor():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        cube = CubeFile.create(str(home / "memories" / "memory.cube"))
        try:
            cube.append("belief", "Duplicate fact about Redis", data={"durable": True, "trust": 0.2})
            cube.append("belief", "Duplicate fact about Redis", data={"durable": True, "trust": 0.2})
            cube.append(
                "belief",
                "Operator password is hunter2 forever",
                data={"durable": True},
            )
            capture_candidate(str(home), "pending oasis fact", source="test")
            report = curation_sync_report(cube, str(home))
            assert report["ok"]
            assert report["proposals_only"] is True
            assert report["duplicates"] or report["risky"] or report["low_trust"]
            card = oasis_doctor_card(cube, str(home))
            assert card["ok"]
            assert card["pending_candidates"] >= 1
            assert card["health"] in ("ok", "warning", "error", "missing")
        finally:
            cube.close()


def test_provider_cuboasis_governance_modes():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        (home / "memories").mkdir()
        p = CubeMemoryProvider(auto_extract=False)
        p.initialize(session_id="g1", hermes_home=str(home), platform="cli")
        p._memory_policy = "review-first"

        cap = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {
                    "action": "cuboasis",
                    "mode": "capture",
                    "content": "Project Alpha prefers vault tokens for auth",
                },
            )
        )
        assert cap["status"] == "capture"
        assert cap.get("ok")
        cid = cap["candidate_id"]

        rev = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "cuboasis", "mode": "review"},
            )
        )
        assert rev["status"] == "review"
        assert rev["count"] >= 1

        ap = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "cuboasis", "mode": f"approve:{cid}"},
            )
        )
        assert ap["status"] == "approve"
        assert ap.get("ok")

        sync = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "cuboasis", "mode": "sync"},
            )
        )
        assert sync["status"] == "sync"

        doc = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "cuboasis", "mode": "doctor"},
            )
        )
        assert doc["status"] == "doctor"
        assert "checks" in doc

        prompt = p.system_prompt_block()
        assert "Cuboasis" in prompt
        p.shutdown()
