"""HermesCube Blackbox — flight recorder core (inner center).

Inspired by asimons81/hermes-blackbox (Apache-2.0): capture Hermes runs,
redact secrets, integrity-hash trajectories, prove claims against evidence.

Integrated as Cube's anatomical *blackbox* organ — not a separate product
dependency. Agents saying "done" must show the work.
"""
from __future__ import annotations

from hermescube.blackbox.capture import capture_session, load_record, save_record
from hermescube.blackbox.flight import (
    ClaimResult,
    FlightRecord,
    integrity_hash,
    verify_integrity,
)
from hermescube.blackbox.prove import prove_claim, prove_many
from hermescube.blackbox.redact import redact_obj, redact_text

__all__ = [
    "ClaimResult",
    "FlightRecord",
    "capture_session",
    "integrity_hash",
    "load_record",
    "prove_claim",
    "prove_many",
    "redact_obj",
    "redact_text",
    "save_record",
    "verify_integrity",
]
