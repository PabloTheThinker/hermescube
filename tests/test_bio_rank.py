"""Tests for bio-inspired ranking (comparative cognition → Cube)."""

from __future__ import annotations

import tempfile
import time

from hermescube import bio_rank
from hermescube.provider import CubeMemoryProvider
from hermescube.har import HARQueryEngine
from hermescube.cube import CubeFile


class TestBioRank:
    def test_layers_and_half_lives(self):
        assert bio_rank.cortical_layer("trait") == "associative"
        assert bio_rank.cortical_layer("focus") == "executive"
        assert bio_rank.cortical_layer("evolution") == "meta"
        assert bio_rank.half_life_hours("relationship") > bio_rank.half_life_hours("focus")
        assert bio_rank.half_life_hours("landmark") > bio_rank.half_life_hours("enter")

    def test_composite_trust_and_supersede(self):
        base = bio_rank.composite_score(1.0, entry_type="belief", trust=0.5)
        high = bio_rank.composite_score(1.0, entry_type="belief", trust=0.9)
        low = bio_rank.composite_score(1.0, entry_type="belief", trust=0.1)
        assert high > base > low
        super_s = bio_rank.composite_score(
            1.0, entry_type="belief", outcome="superseded", trust=0.5
        )
        assert super_s < base

    def test_elephant_recency(self):
        # Same age: relationship retains more than focus
        r_rel = bio_rank.recency_weight(200.0, "relationship")
        r_focus = bio_rank.recency_weight(200.0, "focus")
        assert r_rel > r_focus

    def test_diversify_layers(self):
        class E:
            def __init__(self, t, d):
                self.entry_type = t
                self.description = d

        # Score order must win everyday path
        scored = [
            (E("landmark", "a"), 0.9),
            (E("landmark", "b"), 0.8),
            (E("landmark", "c"), 0.7),
            (E("focus", "f1"), 0.6),
            (E("evolution", "e1"), 0.5),
            (E("trait", "t1"), 0.4),
        ]
        out = bio_rank.diversify_by_layer(scored, top_k=5)
        assert out[0][0].description == "a"
        assert len(out) == 5
        # weak executive must not jump above stronger landmarks
        assert out[0][1] >= out[1][1] >= out[2][1]

    def test_lexical_bridge_bugs(self):
        # paraphrase: query "bugs fixed" should match "Fixed bug in auth"
        assert bio_rank.lexical_score(
            "what bugs were fixed?", "Fixed bug in authentication flow"
        ) > 0.2
        assert bio_rank.hybrid_semantic(0.05, 0.4) > 0.2

    def test_composite_with_lexical(self):
        weak = bio_rank.composite_score(0.05, entry_type="landmark", lexical=0.0)
        strong = bio_rank.composite_score(0.05, entry_type="landmark", lexical=0.5)
        assert strong > weak


class TestBioProviderIntegration:
    def test_prefetch_layer_tags_and_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = CubeMemoryProvider()
            p.initialize(session_id="bio", hermes_home=tmp)
            p.sync_turn("I prefer dark mode", "Noted")
            p.sync_turn("Client Acme is on a dedicated VPS only", "Locked")
            p.sync_turn("Our focus this week is cash collection", "OK")
            p._sync_queue.flush()
            time.sleep(0.05)
            t0 = time.perf_counter()
            text = p.prefetch("what does the user prefer about editors?")
            ms = (time.perf_counter() - t0) * 1000
            assert ms < 50.0, f"prefetch too slow: {ms}ms"
            assert (
                "Relevant memories" in text
                or "evidence packet" in text.lower()
                or "CURRENT FACTS" in text
                or "PAST EPISODES" in text
            )
            assert "|associative]" in text or "|executive]" in text or "trait" in text
            block = p.system_prompt_block()
            assert "Hemispheres" in block
            assert "extension" in block.lower() or "durable" in block.lower()
            stats = p.evolve_consolidated()
            assert stats.get("phase") == "sleep_consolidate"
            assert "nrem" in stats
            assert "rem_hubs" in stats
            p.shutdown()

    def test_classify_relationship_and_spatial(self):
        p = CubeMemoryProvider()
        assert p._classify_turn("my partner likes X", "") == "relationship"
        assert p._classify_turn("deploy to the VPS path", "") == "landmark"

class TestDiversifyByLayer:
    """The soft-inject path was unreachable: the guard tested
    `len(head) >= top_k` (always true after the early return) and the
    replacement then required the candidate to outrank the tail it came
    from below. Both are fixed; these pin the behaviour."""

    class _E:
        def __init__(self, entry_type: str, description: str) -> None:
            self.entry_type = entry_type
            self.description = description

    def _run(self, tail_type: str, tail_score: float, top_k: int = 8):
        scored = [(self._E("landmark", f"L{i}"), 1.0 - 0.01 * i) for i in range(top_k)]
        scored.append((self._E(tail_type, "INJECT"), tail_score))
        return bio_rank.diversify_by_layer(scored, top_k)

    def test_injects_missing_executive_layer(self):
        out = self._run("resolve", 0.90)
        assert any(e.description == "INJECT" for e, _ in out)
        assert {bio_rank.cortical_layer(e.entry_type) for e, _ in out} >= {
            "associative",
            "executive",
        }

    def test_respects_relevance_floor(self):
        # 0.30 < 0.60 * 1.00 leader -> never trade a slot for a weak filler
        out = self._run("resolve", 0.30)
        assert not any(e.description == "INJECT" for e, _ in out)

    def test_never_displaces_protected_head(self):
        out = self._run("resolve", 0.90)
        assert [e.description for e, _ in out][:4] == ["L0", "L1", "L2", "L3"]
        assert len(out) == 8

    def test_returns_pure_order_when_layer_already_present(self):
        scored = [(self._E("landmark", "L0"), 1.0), (self._E("focus", "F"), 0.9)]
        scored += [(self._E("landmark", f"L{i}"), 0.5) for i in range(1, 8)]
        out = bio_rank.diversify_by_layer(scored, 3)
        assert [e.description for e, _ in out] == ["L0", "F", "L1"]


class TestHalfLifeSingleSource:
    def test_table_is_the_single_source_of_truth(self):
        # half_life_hours() used to duplicate (and contradict) this table
        for et, hours in bio_rank.HALF_LIFE_HOURS.items():
            assert bio_rank.half_life_hours(et) == hours
        assert bio_rank.half_life_hours("no_such_type") == bio_rank.DEFAULT_HALF_LIFE_HOURS


class TestLexicalScorePreTokenized:
    def test_pretokenized_query_matches_inline(self):
        q = "redis cache latency in the auth service"
        docs = [
            "redis cache reduced auth-service latency",
            "postgres migration finished",
            "the auth service uses a redis cache",
        ]
        toks = bio_rank.tokenize(q)
        for d in docs:
            assert bio_rank.lexical_score(q, d) == bio_rank.lexical_score(
                q, d, q_tokens=toks
            )
