"""Lexical + numeric soft conflict detection."""

from __future__ import annotations

from pathlib import Path

from hermescube.conflict import (
    extract_numeric_claims,
    find_conflicts,
    scan_numeric_conflict_pairs,
    annotate_numeric_pairs,
)
from hermescube.cube import CubeFile
from hermescube.wisdom import active_wisdom


class _E:
    def __init__(self, eid, desc, et="belief", data=None, outcome="success"):
        self.id = eid
        self.description = desc
        self.entry_type = et
        self.data = data or {}
        self.outcome = outcome


def test_extract_numeric_claims_skips_years():
    claims = extract_numeric_claims("Deployed auth-service in 2026 with 3 replicas")
    nums = {n for _, n in claims}
    assert 3 in nums
    assert 2026 not in nums


def test_numeric_conflict_pairs():
    entries = [
        _E("a1", "AuthService runs 3 replicas in eu-west"),
        _E("a2", "AuthService runs 5 replicas in eu-west"),
        _E("b1", "billing service uses postgres read replica"),
    ]
    pairs = scan_numeric_conflict_pairs(entries, limit=4)
    assert pairs
    assert {pairs[0]["a_count"], pairs[0]["b_count"]} == {3, 5}


def test_annotate_numeric_pairs(tmp_path: Path):
    c = CubeFile.create(str(tmp_path / "c.cube"))
    a = c.append(
        "belief",
        "Redis pool size is 8 for auth-service",
        data={"trust": 0.8},
    )
    b = c.append(
        "belief",
        "Redis pool size is 16 for auth-service",
        data={"trust": 0.8},
    )
    pairs = scan_numeric_conflict_pairs(c.read_l1())
    assert pairs
    n = annotate_numeric_pairs(c, pairs)
    assert n >= 1
    markers = [
        e
        for e in c.read_l1()
        if (e.data or {}).get("conflict_kind") == "numeric"
    ]
    assert markers
    c.close()


def test_lexical_conflict_still_works():
    entries = [_E("x", "User prefers dark mode always")]
    hits = find_conflicts("User does not prefer dark mode", entries)
    assert hits


def test_active_wisdom_vault_soft_boost():
    entries = [
        _E("1", "Unlabeled Redis caches sessions", data={"trust": 0.8, "crystal": True}),
        _E(
            "2",
            "Workspace Postgres stores users",
            data={"trust": 0.75, "crystal": True, "vault": "ws-a"},
        ),
        _E(
            "3",
            "Other vault Redis note",
            data={"trust": 0.85, "crystal": True, "vault": "ws-b"},
        ),
    ]
    # With vault=ws-a, matching crystal should outrank higher-trust other-vault
    got = active_wisdom(entries, limit=3, vault="ws-a")
    ids = [e.id for e in got]
    assert "2" in ids
    assert "1" in ids  # unlabeled never hard-dropped from the pool
