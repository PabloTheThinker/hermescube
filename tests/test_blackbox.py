"""Blackbox flight recorder — center organ tests."""
from __future__ import annotations

import json
from pathlib import Path

from hermescube.blackbox.flight import FlightRecord, integrity_hash, verify_integrity
from hermescube.blackbox.prove import prove_claim
from hermescube.blackbox.redact import redact_text
from hermescube import center


def test_redact_jwt_like():
    # three base64url segments (pattern requires length ≥10 each)
    s = (
        "auth eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
        "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )
    out, n = redact_text(s)
    assert n >= 1
    assert "eyJhbGci" not in (out or "")


def test_integrity_roundtrip():
    events = [{"ts": "1", "kind": "user", "summary": "hi", "detail": None, "name": None, "refs": {}}]
    rec = FlightRecord(
        id="bb_test",
        created_at="2026-01-01T00:00:00Z",
        schema_version="1.0",
        source={"type": "test"},
        session={"id": "s1"},
        events=events,
        integrity=integrity_hash(events),
    )
    assert verify_integrity(rec)
    rec.events.append({"kind": "tamper"})
    assert not verify_integrity(rec)


def test_prove_tests_pass_evidence():
    events = [
        {
            "ts": "1",
            "kind": "tool_result",
            "name": "terminal",
            "summary": "pytest -q ... 12 passed",
            "detail": "12 passed in 0.1s",
            "refs": {},
        }
    ]
    rec = {
        "events": events,
        "integrity": integrity_hash(events),
    }
    r = prove_claim(rec, "tests pass")
    assert r.verdict == "pass"
    assert r.evidence


def test_center_api_has_blackbox_organ():
    st = center.center_status()
    assert st["api_version"] >= "1.2" or st["api_version"].startswith("1.")
    assert "blackbox" in st["organs"]
    assert "flight" in (st["organs"]["blackbox"].get("api") or "")


def test_flight_capture_live_optional():
    """Soft: skip if no HERMES state.db or empty session history."""
    home = Path.home() / ".hermes"
    if not (home / "state.db").exists():
        return
    out = center.flight_capture(latest=True, hermes_home=str(home))
    # Empty homes (no sessions yet) are not a product failure — skip soft.
    if not out.get("ok"):
        err = str(out.get("error") or "")
        if "No sessions" in err or "no sessions" in err.lower():
            return
    assert out.get("ok") is True
    assert out.get("events", 0) >= 1
    assert out.get("integrity_ok") is True
    p = Path(out["path"])
    assert p.is_file()
    data = json.loads(p.read_text())
    assert data["meta"]["engine"] == "hermescube.blackbox"
