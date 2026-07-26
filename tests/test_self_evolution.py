"""Grounded self-evolution harness — witness, cycles, predictions, critic, gardener."""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.provider import CubeMemoryProvider
from hermescube.self_evolution import (
    detect_friction,
    harness_status,
    make_prediction,
    mark_witnesses_addressed,
    open_predictions,
    open_witnesses,
    record_cycle,
    record_witness,
    run_critic,
    run_gardener,
    verify_predictions,
)


class TestWitness:
    def test_record_and_open(self):
        with tempfile.TemporaryDirectory() as td:
            record_witness(td, "search returned stale results", severity="medium")
            ws = open_witnesses(td)
            assert len(ws) == 1
            assert ws[0]["severity"] == "medium"
            assert not ws[0]["addressed"]

    def test_mark_addressed(self):
        with tempfile.TemporaryDirectory() as td:
            record_witness(td, "friction one")
            n = mark_witnesses_addressed(td, before_ts=time.time() + 1, cycle_id="c1")
            assert n == 1
            assert open_witnesses(td) == []

    def test_detect_user_correction(self):
        f = detect_friction("No, that's wrong — I asked for the prod config", "ok")
        assert f is not None
        assert f["kind"] == "user_correction"
        assert f["severity"] == "medium"

    def test_detect_hard_error(self):
        f = detect_friction(
            "run it", "Traceback (most recent call last):\n  ValueError"
        )
        assert f is not None
        assert f["kind"] == "hard_error"

    def test_no_false_positive_on_normal_turn(self):
        assert detect_friction("please deploy the app", "Deployed successfully.") is None


class TestCyclesAndCritic:
    def test_every_cycle_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            record_cycle(td, kind="session_end", outcome="noop")
            record_cycle(td, kind="session_end", outcome="action", witness_ts=[1.0])
            s = harness_status(td)
            assert len(s["recent_cycles"]) == 2

    def test_critic_flags_bookkeeping_theatre(self):
        with tempfile.TemporaryDirectory() as td:
            record_witness(td, "real unaddressed friction")
            for _ in range(3):
                record_cycle(td, kind="session_end", outcome="noop")
            r = run_critic(td)
            assert r["verdict"] == "flagged"
            assert any(f["flag"] == "bookkeeping_theatre" for f in r["findings"])

    def test_critic_healthy_when_grounded(self):
        with tempfile.TemporaryDirectory() as td:
            record_cycle(td, kind="session_end", outcome="action", witness_ts=[1.0])
            r = run_critic(td)
            assert r["verdict"] == "healthy"

    def test_critic_flags_failing_streak(self):
        with tempfile.TemporaryDirectory() as td:
            record_cycle(td, kind="session_end", outcome="failed")
            record_cycle(td, kind="session_end", outcome="failed")
            r = run_critic(td)
            assert any(f["flag"] == "failing_cycles" for f in r["findings"])


class TestPredictions:
    def test_witness_absence_confirmed_after_horizon(self):
        with tempfile.TemporaryDirectory() as td:
            p = make_prediction(
                td,
                "the stale-search friction will not recur",
                check={"type": "witness_absence", "pattern": "stale search"},
                horizon_days=0.0,  # already expired → verdict now
            )
            assert p["status"] == "open"
            stats = verify_predictions(td)
            assert stats["confirmed"] == 1
            assert open_predictions(td) == []

    def test_witness_absence_refuted_on_recurrence(self):
        with tempfile.TemporaryDirectory() as td:
            make_prediction(
                td,
                "the stale-search friction will not recur",
                check={"type": "witness_absence", "pattern": "stale search"},
                horizon_days=7.0,
            )
            record_witness(td, "stale search results again", severity="medium")
            stats = verify_predictions(td)
            assert stats["refuted"] == 1

    def test_entry_feedback_confirmed_on_trust(self):
        with tempfile.TemporaryDirectory() as td:
            cube = CubeFile.create(os.path.join(td, "c.cube"))
            e = cube.append("resolve", "promoted procedure", data={"trust": 0.9})
            make_prediction(
                td,
                "procedure earns trust",
                check={"type": "entry_feedback", "entry_id": e.id, "min_trust": 0.6},
            )
            stats = verify_predictions(td, cube=cube)
            assert stats["confirmed"] == 1
            cube.close()

    def test_entry_feedback_stays_open_until_horizon(self):
        with tempfile.TemporaryDirectory() as td:
            cube = CubeFile.create(os.path.join(td, "c.cube"))
            e = cube.append("resolve", "promoted procedure", data={"trust": 0.3})
            make_prediction(
                td,
                "procedure earns trust",
                check={"type": "entry_feedback", "entry_id": e.id, "min_trust": 0.6},
                horizon_days=7.0,
            )
            stats = verify_predictions(td, cube=cube)
            assert stats["open"] == 1
            cube.close()


class TestGardener:
    def test_dormant_surfaced_not_deleted(self):
        with tempfile.TemporaryDirectory() as td:
            cube = CubeFile.create(os.path.join(td, "c.cube"))
            old_ts = time.time() - 90 * 86400
            cube.append(
                "belief", "old dormant low-trust durable fact",
                data={"durable": True, "trust": 0.3, "timestamp": old_ts},
            )
            cube.append(
                "belief", "fresh durable fact",
                data={"durable": True, "trust": 0.8, "timestamp": time.time()},
            )
            r = run_gardener(cube, td, dormant_days=45)
            assert r["durable_scanned"] == 2
            assert len(r["dormant_candidates"]) == 1
            assert "dormant low-trust" in r["dormant_candidates"][0]["description"]
            # nothing deleted
            assert cube.entry_count == 2
            report = Path(td) / "memories" / "harness" / "gardener_report.json"
            assert report.is_file()
            cube.close()


class TestProviderIntegration:
    def test_sync_turn_records_friction_witness(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            p.sync_turn(
                "No, that's wrong — you deployed to the wrong host again",
                "Sorry, retrying with the correct host.",
                session_id="s1",
            )
            p._sync_queue.flush(timeout=5)
            ws = open_witnesses(td)
            assert ws and ws[0]["kind"] == "user_correction"
            p.shutdown()

    def test_manage_witness_and_harness_status(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            out = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "witness",
                "content": "cube search missed an obvious past session",
                "severity": "high",
            }))
            assert out.get("status") == "witness"
            s = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "harness", "harness_action": "status",
            }))
            assert s.get("status") == "harness"
            assert s.get("open_witnesses") == 1
            c = json.loads(p.handle_tool_call("hermescube_manage", {
                "action": "harness", "harness_action": "critic",
            }))
            assert c.get("status") == "critic"
            p.shutdown()

    def test_session_end_writes_grounded_cycle_report(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            p._cube.append(
                "belief", "durable fact for evolve",
                data={"durable": True, "trust": 0.7},
            )
            record_witness(td, "real friction to anchor this cycle")
            p.on_session_end([])
            p._sync_queue.flush(timeout=10)
            s = harness_status(td)
            assert s["recent_cycles"], "cycle report must exist (no silent cycles)"
            assert s["recent_cycles"][-1]["outcome"] == "action"
            assert s["open_witnesses"] == 0  # addressed by the cycle
            p.shutdown()
