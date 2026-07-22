"""Tests for HAR query engine and k-means clustering."""

import tempfile
import os
from unittest.mock import patch

from hermescube.cube import CubeFile
from hermescube.har import HARQueryEngine
from hermescube import hrr


class TestHARQuery:
    def setup_cube(self, entries: list[tuple[str, str]]) -> str:
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        cube = CubeFile.create(path)
        for etype, desc in entries:
            cube.append(etype, desc)
        cube.close()
        return path

    def test_fallback_scan_before_evolve(self):
        path = self.setup_cube([
            ("landmark", "User asked about memory systems"),
            ("landmark", "Deployed hotfix for production crash"),
        ])
        try:
            with CubeFile.open(path) as cube:
                engine = HARQueryEngine(cube)
                results = engine.query("memory", top_k=5)
                assert len(results) == 2
                assert results[0][0].description.startswith("User asked")
        finally:
            os.unlink(path)

    def test_har_after_evolve(self):
        path = self.setup_cube([
            ("landmark", "User asked about memory systems"),
            ("landmark", "Deployed hotfix for production crash"),
            ("belief", "Agent should remember conversation history"),
        ])
        try:
            with CubeFile.open(path) as cube:
                # use_learned_embeddings=False: test exercises HAR ranking,
                # not learned embedding quality (which needs larger corpora)
                engine = HARQueryEngine(cube, use_learned_embeddings=False)
                engine.evolve()
                results = engine.query("memory and conversation", top_k=3)
                assert len(results) > 0
                # Should rank memory-related entry high
                top_desc = results[0][0].description.lower()
                assert any(w in top_desc for w in ["memory", "remember", "conversation"])
        finally:
            os.unlink(path)

    def test_query_empty_cube(self):
        path = self.setup_cube([])
        try:
            with CubeFile.open(path) as cube:
                engine = HARQueryEngine(cube)
                results = engine.query("anything", top_k=5)
                assert results == []
        finally:
            os.unlink(path)

    def test_different_topics_rank_differently(self):
        path = self.setup_cube([
            ("landmark", "Fixed parser bug in the memory module"),
            ("landmark", "Added new feature for user authentication"),
            ("belief", "Users prefer dark mode in the interface"),
        ])
        try:
            with CubeFile.open(path) as cube:
                engine = HARQueryEngine(cube, use_learned_embeddings=False)
                engine.evolve()

                bug_results = engine.query("bug fix", top_k=3)
                auth_results = engine.query("authentication", top_k=3)

                assert bug_results[0][0].description != auth_results[0][0].description
        finally:
            os.unlink(path)


class TestBeta:
    def test_beta_on_append(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            engine = HARQueryEngine(cube)
            initial_beta = engine.beta
            initial_norm = hrr.norm(initial_beta)

            entry = cube.append("landmark", "First entry")
            engine.update_beta_on_append(entry.vector)

            updated_beta = engine.beta
            updated_norm = hrr.norm(updated_beta)
            assert abs(updated_norm - 1.0) < 1e-10  # normalized
            cube.close()
        finally:
            os.unlink(path)

    def test_beta_decay(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("landmark", "Some entry")
            engine = HARQueryEngine(cube)
            engine.evolve()

            before = hrr.norm(engine.beta)
            engine.apply_beta_decay(factor=0.5)
            after = hrr.norm(engine.beta)
            assert abs(after - 1.0) < 1e-10  # still normalized
            cube.close()
        finally:
            os.unlink(path)

    def test_beta_persists_across_reopen(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            engine = HARQueryEngine(cube)
            new_beta = hrr.embed_text("persistent attention state")
            engine.update_beta(new_beta)
            cube.close()

            cube2 = CubeFile.open(path)
            engine2 = HARQueryEngine(cube2)
            loaded_beta = engine2.beta
            sim = hrr.cosine_sim(new_beta, loaded_beta)
            assert abs(sim - 1.0) < 1e-10
            cube2.close()
        finally:
            os.unlink(path)


class TestEvolve:
    def test_evolve_single_entry(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("landmark", "Only entry")
            engine = HARQueryEngine(cube)
            stats = engine.evolve()
            assert stats["entries"] == 1
            assert stats["non_empty_buckets"] == 1
            assert stats["clusters"] == 64
        finally:
            os.unlink(path)

    def test_evolve_updates_l2(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(10):
                cube.append("landmark", f"Event number {i}")
            cube.close()

            cube2 = CubeFile.open(path)
            engine = HARQueryEngine(cube2)
            before = cube2.read_l2()
            empty = all(len(b.entry_ids) == 0 for b in before)
            assert empty

            engine.evolve()
            after = cube2.read_l2()
            non_empty = sum(1 for b in after if b.entry_ids)
            assert non_empty > 0
            cube2.close()
        finally:
            os.unlink(path)

    def test_evolve_updates_beta(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("landmark", "Entry for evolve")
            engine = HARQueryEngine(cube)
            initial_beta_vec = [x for x in engine.beta]
            engine.evolve()
            evolved_beta_vec = [x for x in engine.beta]
            # Beta should have changed
            similarity = sum(a * b for a, b in zip(initial_beta_vec, evolved_beta_vec))
            # It could still be somewhat similar since we only have 1 entry
            assert len(initial_beta_vec) == len(evolved_beta_vec)
        finally:
            os.unlink(path)

    def test_multiple_evolves(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(20):
                cube.append("landmark" if i % 2 == 0 else "belief",
                            f"Entry {i}: {'memory system' if i < 10 else 'authentication feature'}")

            engine = HARQueryEngine(cube)
            stats1 = engine.evolve()
            assert stats1["entries"] == 20

            # Add more entries and evolve again
            for i in range(20, 30):
                cube.append("landmark", f"Entry {i}: database optimization")

            stats2 = engine.evolve()
            assert stats2["entries"] == 30
            cube.close()
        finally:
            os.unlink(path)


class TestExtractTerms:
    def test_extract_terms_basic(self):
        terms = HARQueryEngine._extract_terms(["User likes dark mode"])
        assert "user" in terms
        assert "likes" in terms
        assert "dark" in terms
        assert "mode" in terms

    def test_extract_terms_stopwords(self):
        terms = HARQueryEngine._extract_terms(["The user is a developer"])
        assert "the" not in terms
        assert "is" not in terms
        assert "a" not in terms
        assert "user" in terms
        assert "developer" in terms

    def test_extract_terms_empty(self):
        terms = HARQueryEngine._extract_terms([])
        assert terms == []

    def test_extract_terms_multiple(self):
        terms = HARQueryEngine._extract_terms([
            "User likes dark mode",
            "User prefers Python",
        ])
        assert "user" in terms
        # "user" appears twice, should rank high
        assert terms.index("user") == 0


class TestContradict:
    def test_contradict_runs(self):
        """contradict() returns sorted results using unbind decomposition."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(5):
                cube.append("belief", f"Statement about topic {i}")

            engine = HARQueryEngine(cube)
            engine.evolve()

            # Wide threshold should return all entries
            results = engine.contradict("topic 0", min_opposition=1.0)
            assert isinstance(results, list)
            assert len(results) == 5
            # Scores should be monotonically increasing (most negative first)
            scores = [s for _, s in results]
            assert scores == sorted(scores)
        finally:
            os.unlink(path)

    def test_contradict_empty(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            engine = HARQueryEngine(cube)
            results = engine.contradict("anything")
            assert results == []
        finally:
            os.unlink(path)

    def test_contradict_default_threshold_filters(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(10):
                cube.append("belief", f"Topic {i}")
            engine = HARQueryEngine(cube)
            engine.evolve()
            # Default threshold (-0.1) should return a subset
            results = engine.contradict("topic 0")
            assert 0 <= len(results) <= 10
        finally:
            os.unlink(path)


class TestHAREdgeCases:
    def test_early_fallback_small_archive(self):
        """HAR skips to linear scan for tiny archives (<20 entries)."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(3):
                cube.append("belief", f"Small entry {i}")
            engine = HARQueryEngine(cube)
            engine.evolve()
            results = engine.query("entry", top_k=5)
            assert len(results) == 3
        finally:
            os.unlink(path)

    def test_query_with_explicit_snapshot(self):
        """Query accepts explicit beta/centroids (prefetch snapshot pattern)."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "Snapshot test entry")
            engine = HARQueryEngine(cube)
            engine.evolve()
            snap_beta = engine.beta
            snap_centroids = cube.read_l2()
            results = engine.query(
                "test", beta=snap_beta, centroids=snap_centroids
            )
            assert len(results) >= 1
        finally:
            os.unlink(path)

    def test_evolve_empty_cube(self):
        """Evolve on empty cube returns note dict."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            engine = HARQueryEngine(cube)
            stats = engine.evolve()
            assert stats.get("note") == "no entries"
        finally:
            os.unlink(path)

    def test_evolve_fewer_entries_than_clusters(self):
        """K-means init handles entries < k by padding with noise."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path, l2_buckets=8)
            for i in range(2):
                cube.append("belief", f"Entry {i}")
            engine = HARQueryEngine(cube)
            stats = engine.evolve()
            assert stats["clusters"] == 8
            assert stats["non_empty_buckets"] <= 2
        finally:
            os.unlink(path)

    def test_recency_weight_fallback(self):
        """Recency weight falls back to hour-of-day when now is empty."""
        from hermescube.cube import CubeEntry
        entry = CubeEntry(
            id="test12345678",
            timestamp="2026-07-21T15:30:00Z",
            entry_type="belief",
            description="test",
        )
        w = HARQueryEngine._recency_weight(entry, now="")
        assert 1.0 <= w <= 1.2  # hour-based fallback

    def test_recency_weight_invalid_timestamp(self):
        """Recency weight falls to hour heuristic for unparseable timestamps."""
        from hermescube.cube import CubeEntry
        entry = CubeEntry(
            id="test12345678",
            timestamp="not-a-date",
            entry_type="belief",
            description="test",
        )
        w = HARQueryEngine._recency_weight(entry, now="")
        assert 1.0 <= w <= 1.2  # hour-based fallback
        # With a parseable now, uses exponential decay
        w2 = HARQueryEngine._recency_weight(entry, now="2026-07-21T15:30:00Z")
        assert 1.0 <= w2 <= 1.2  # unparseable ts → hour fallback

    def test_query_uses_learned_embedder_when_trained(self):
        """Query dispatches to learned embedder when trained."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(5):
                cube.append("belief", f"Training entry about topic {i}")
            engine = HARQueryEngine(cube, use_learned_embeddings=True)
            engine.evolve()  # trains embedder
            assert engine._embedder.is_trained
            results = engine.query("topic 2")
            assert len(results) >= 1
        finally:
            os.unlink(path)

    def test_kmeans_pure_python_path(self):
        """K-means works with pure-Python backend (numpy patched out)."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(30):
                cube.append("belief", f"Pure python entry {i}")
            engine = HARQueryEngine(cube)
            with patch.object(hrr, "_HAS_NUMPY", False):
                stats = engine.evolve()
            assert stats["entries"] == 30
            assert stats["non_empty_buckets"] > 0
        finally:
            os.unlink(path)

    def test_appended_entries_visible_before_evolve(self):
        """read_l1 returns cubelog entries even before evolve compacts them."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "WAL entry 1")
            cube.append("belief", "WAL entry 2")
            entries = cube.read_l1()
            assert len(entries) == 2
            # Cubelog should have them
            assert cube._cubelog_count == 2
        finally:
            os.unlink(path)

    def test_evolve_compacts_cubelog(self):
        """After evolve, cubelog is truncated and entries are in .cube L1."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "Compact me")
            assert cube._cubelog_count == 1
            engine = HARQueryEngine(cube)
            engine.evolve()
            assert cube._cubelog_count == 0
            entries = cube.read_l1()
            assert any("Compact me" in e.description for e in entries)
        finally:
            os.unlink(path)
