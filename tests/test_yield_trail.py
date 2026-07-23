"""Tests for Yield Gradient — query-conditioned payoff learning."""

from __future__ import annotations

import tempfile
from pathlib import Path

from hermescube.yield_trail import YieldGradient, query_bucket, yield_multiplier
from hermescube.bio_rank import composite_score
from hermescube import CubeFile, HARQueryEngine


def test_query_bucket_order_invariant():
    a = query_bucket("HermesCube warehouse MEMORY")
    b = query_bucket("MEMORY warehouse HermesCube")
    assert a == b
    assert a != query_bucket("totally different topic zp3 roofing")


def test_yield_multiplier_bounds():
    assert abs(yield_multiplier(0, 0) - 1.0) < 1e-9
    assert yield_multiplier(5, 0) > 1.0
    assert yield_multiplier(0, 5) < 1.0
    assert 0.75 <= yield_multiplier(100, 0) <= 1.40
    assert 0.75 <= yield_multiplier(0, 100) <= 1.40


def test_record_and_boost_roundtrip(tmp_path: Path):
    yg = YieldGradient(tmp_path / "yield_gradient.json")
    q = "what is monotropic HermesCube focus"
    eid = "abc123"
    yg.record(q, eid, helpful=True)
    yg.record(q, eid, helpful=True)
    yg.record(q, "other", helpful=False)
    m = yg.boost_map(q)
    assert eid in m
    assert m[eid] > 1.0
    # similar query same bucket
    m2 = yg.boost_map("HermesCube monotropic focus usefulness")
    assert eid in m2
    # persist
    yg2 = YieldGradient(tmp_path / "yield_gradient.json")
    assert eid in yg2.boost_map(q)


def test_composite_score_yield_changes_rank():
    base = composite_score(0.5, entry_type="belief", lexical=0.4, yield_boost=1.0)
    up = composite_score(0.5, entry_type="belief", lexical=0.4, yield_boost=1.3)
    down = composite_score(0.5, entry_type="belief", lexical=0.4, yield_boost=0.8)
    assert up > base > down


def test_engine_primes_yield(tmp_path: Path):
    cube_path = tmp_path / "t.cube"
    c = CubeFile.create(str(cube_path))
    e1 = c.append("belief", "HermesCube is the deep warehouse extension of MEMORY.md")
    e2 = c.append("belief", "ZP3 client uses Hostinger VPS for agent home")
    c.close()
    c = CubeFile.open(str(cube_path))
    eng = HARQueryEngine(c)
    from hermescube.yield_trail import YieldGradient

    yg = YieldGradient(tmp_path / "yg.json")
    q = "what is HermesCube warehouse for"
    yg.record(q, e1.id, helpful=True)
    yg.record(q, e1.id, helpful=True)
    eng._yield_gradient = yg
    res = eng.query(q, top_k=5)
    assert res
    # rewarded entry should rank at or near top
    assert res[0][0].id == e1.id or any(e.id == e1.id for e, _ in res[:2])
    c.close()
