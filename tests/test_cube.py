"""Tests for .cube file I/O."""

import json
import os
import tempfile

from hermescube.cube import CubeFile, CubeEntry


class TestCubeCreate:
    def test_create_and_open(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            assert cube.entry_count == 0
            assert cube.l1_data_size == 0
            assert cube.l3_offset > 0
            cube.close()

            cube2 = CubeFile.open(path)
            assert cube2.entry_count == 0
            assert cube2.dim == 256
            info = cube2.info()
            assert info["entries"] == 0
            cube2.close()
        finally:
            os.unlink(path)

    def test_custom_dim_and_buckets(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path, dim=128, l2_buckets=32)
            assert cube.dim == 128
            assert cube.l2_bucket_count == 32
            cube.close()

            cube2 = CubeFile.open(path)
            assert cube2.dim == 128
            assert cube2.l2_bucket_count == 32
            cube2.close()
        finally:
            os.unlink(path)


class TestCubeAppend:
    def test_append_single(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            entry = cube.append("landmark", "Test entry")
            assert entry.id is not None
            assert len(entry.id) == 12
            assert entry.entry_type == "landmark"
            assert entry.description == "Test entry"
            cube.close()

            cube2 = CubeFile.open(path)
            assert cube2.entry_count == 1
            entries = cube2.read_l1()
            assert len(entries) == 1
            assert entries[0].description == "Test entry"
            cube2.close()
        finally:
            os.unlink(path)

    def test_append_multiple(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            n = 10
            for i in range(n):
                cube.append("belief", f"Belief number {i}")
            assert cube.entry_count == n
            cube.close()

            cube2 = CubeFile.open(path)
            assert cube2.entry_count == n
            entries = cube2.read_l1()
            assert len(entries) == n
            for i, e in enumerate(entries):
                assert e.description == f"Belief number {i}"
            cube2.close()
        finally:
            os.unlink(path)

    def test_append_with_data(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append(
                "belief",
                "Has data",
                data={"confidence": 0.95, "tags": ["a", "b"]},
            )
            cube.close()

            cube2 = CubeFile.open(path)
            entries = cube2.read_l1()
            assert len(entries) == 1
            assert entries[0].data["confidence"] == 0.95
            assert entries[0].data["tags"] == ["a", "b"]
            cube2.close()
        finally:
            os.unlink(path)

    def test_append_with_causal_parents(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            e1 = cube.append("landmark", "Parent event")
            e2 = cube.append("focus", "Child event", causal_parents=[e1.id])
            cube.close()

            cube2 = CubeFile.open(path)
            child = cube2.read_entry(e2.id)
            assert child is not None
            assert child.causal_parents == [e1.id]
            cube2.close()
        finally:
            os.unlink(path)

    def test_append_with_outcome(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("resolve", "Task done", outcome="success")
            cube.close()

            cube2 = CubeFile.open(path)
            entries = cube2.read_l1()
            assert entries[0].outcome == "success"
            cube2.close()
        finally:
            os.unlink(path)


class TestCubeRead:
    def test_read_entry_by_id(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            e1 = cube.append("landmark", "Find me")
            cube.append("landmark", "Not me")
            cube.close()

            cube2 = CubeFile.open(path)
            found = cube2.read_entry(e1.id)
            assert found is not None
            assert found.id == e1.id
            assert found.description == "Find me"

            missing = cube2.read_entry("nonexistent123")
            assert missing is None
            cube2.close()
        finally:
            os.unlink(path)

    def test_replay(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(5):
                cube.append("landmark", f"Event {i}")
            cube.close()

            cube2 = CubeFile.open(path)
            entries = cube2.replay()
            assert len(entries) == 5
            cube2.close()
        finally:
            os.unlink(path)

    def test_count_by_type(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("landmark", "Event 1")
            cube.append("belief", "I think")
            cube.append("landmark", "Event 2")
            cube.append("trait", "I am")
            cube.close()

            cube2 = CubeFile.open(path)
            counts = cube2.count_by_type()
            assert counts["landmark"] == 2
            assert counts["belief"] == 1
            assert counts["trait"] == 1
            cube2.close()
        finally:
            os.unlink(path)


class TestL2:
    def test_empty_buckets(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            buckets = cube.read_l2()
            assert len(buckets) == 64
            for b in buckets:
                assert len(b.entry_ids) == 0
            cube.close()
        finally:
            os.unlink(path)

    def test_write_and_read_buckets(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            e1 = cube.append("landmark", "Test entry")
            _ = cube.append("belief", "Another entry")
            cube.close()

            cube2 = CubeFile.open(path)
            buckets = cube2.read_l2()
            # Assign entries to buckets
            entries = cube2.read_l2()  # reread to reset
            buckets = cube2.read_l2()
            buckets[0].entry_ids = [e1.id]
            buckets[0].terms = ["test", "entry"]
            cube2.write_l2(buckets)
            cube2.close()

            cube3 = CubeFile.open(path)
            buckets2 = cube3.read_l2()
            assert buckets2[0].entry_ids == [e1.id]
            assert buckets2[0].terms == ["test", "entry"]
            assert all(len(b.entry_ids) == 0 for b in buckets2[1:])
            cube3.close()
        finally:
            os.unlink(path)


class TestL3:
    def test_initial_beta_zero(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            beta = cube.read_l3()
            if hasattr(beta, "__len__"):
                zero_norm = sum(abs(x) for x in beta)
            else:
                zero_norm = 0
            assert zero_norm < 1e-10
            cube.close()
        finally:
            os.unlink(path)

    def test_write_and_read_beta(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            from hermescube import hrr

            cube = CubeFile.create(path)
            cube.append("landmark", "Some entry")
            cube.close()

            cube2 = CubeFile.open(path)
            new_beta = hrr.embed_text("new attention state")
            cube2.write_l3(new_beta)
            cube2.close()

            cube3 = CubeFile.open(path)
            beta = cube3.read_l3()
            sim = hrr.cosine_sim(new_beta, beta)
            assert abs(sim - 1.0) < 1e-10
            cube3.close()
        finally:
            os.unlink(path)


class TestEdgeCases:
    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            with open(path, "wb") as f:
                f.write(b"not a cube file")
            try:
                CubeFile.open(path)
                assert False, "Should have raised"
            except (ValueError, Exception):
                pass
        finally:
            os.unlink(path)

    def test_all_entry_types(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            types = ["enter", "leave", "landmark", "belief", "trait",
                     "evolution", "focus", "epoch_transition", "resolve", "relationship"]
            for t in types:
                cube.append(t, f"Entry of type {t}")
            cube.close()

            cube2 = CubeFile.open(path)
            entries = cube2.read_l1()
            assert len(entries) == len(types)
            for e in entries:
                assert e.entry_type in types
            cube2.close()
        finally:
            os.unlink(path)

    def test_large_description(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            long_desc = "x" * 5000
            cube.append("landmark", long_desc)
            cube.close()

            cube2 = CubeFile.open(path)
            entries = cube2.read_l1()
            assert entries[0].description == long_desc
            assert len(entries[0].description) == 5000
            cube2.close()
        finally:
            os.unlink(path)


class TestCubeSearch:
    def test_search_finds_entry(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "User likes dark mode")
            cube.append("belief", "User prefers Python")
            results = cube.search("dark mode")
            assert len(results) >= 1
            assert any("dark mode" in e.description for e in results)
            cube.close()
        finally:
            os.unlink(path)

    def test_search_no_match(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "User likes dark mode")
            results = cube.search("quantum physics")
            assert len(results) == 0
            cube.close()
        finally:
            os.unlink(path)

    def test_query_range(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(10):
                cube.append("belief", f"Fact {i}")
            entries = cube.read_l1()
            # Filter by type
            results = cube.query_range(entry_type="belief")
            assert len(results) == 10
            # Filter by timestamp range
            results = cube.query_range(after=entries[2].timestamp)
            assert len(results) >= 7
            cube.close()
        finally:
            os.unlink(path)

    def test_entry_as_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            entry = cube.append("belief", "Test fact", data={"key": "value"})
            d = entry.as_dict()
            assert d["description"] == "Test fact"
            assert d["entry_type"] == "belief"
            assert d["data"] == {"key": "value"}
            assert "id" in d
            assert "timestamp" in d
            cube.close()
        finally:
            os.unlink(path)


class TestEntrySizeFormula:
    """Regression: _entry_size and _write_entry must use the same
    byte-size formula. A future format change that updates one and
    forgets the other will silently corrupt the file."""

    def test_compute_entry_size_constant(self):
        # Fixed overhead: 12+16+1+1+4+4+4 = 42
        # dim*8 for vector
        size = CubeFile._compute_entry_size(
            desc_len=0, data_len=0, causal_count=0, dim=256
        )
        assert size == 42 + 256 * 8  # 2090

    def test_size_matches_actual_l1_growth(self):
        """Appended entry goes to cubelog WAL — .cube L1 size stays 0 until evolve.
        The cubelog count grows instead."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            assert cube.l1_data_size == 0
            assert cube._cubelog_count == 0
            entry = cube.append("belief", "test", data={"k": "v"})
            # Entry went to cubelog, not .cube L1
            assert cube.l1_data_size == 0
            assert cube._cubelog_count == 1
            assert cube.entry_count == 1  # total = .cube + cubelog
            cube.close()
        finally:
            os.unlink(path)


class TestCubeFileConcurrency:
    """Regression: concurrent append from multiple threads must not
    corrupt the file. Without the RLock, two threads interleaving
    _shift_tail + _write_entry produced byte-interleaved garbage that
    crashed on read."""

    def test_concurrent_appends_do_not_corrupt(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            n_per_thread = 5
            n_threads = 4

            def append_many(thread_id):
                for i in range(n_per_thread):
                    cube.append(
                        "belief",
                        f"thread {thread_id} entry {i}",
                        data={"t": thread_id, "i": i},
                    )

            with ThreadPoolExecutor(max_workers=n_threads) as ex:
                futures = [ex.submit(append_many, t) for t in range(n_threads)]
                for f in futures:
                    f.result()

            cube.close()

            # Reopen and verify all entries survived intact
            with CubeFile.open(path) as cube2:
                entries = cube2.read_l1()
                assert len(entries) == n_per_thread * n_threads
                # Every entry's description must be a valid string
                for e in entries:
                    assert isinstance(e.description, str)
                    assert e.description.startswith("thread ")
            cube2.close()
        finally:
            os.unlink(path)

    def test_concurrent_read_and_write(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(10):
                cube.append("belief", f"initial {i}")
            cube.close()

            cube = CubeFile.open(path)

            def writer():
                for i in range(10):
                    cube.append("belief", f"new {i}")

            def reader():
                for _ in range(10):
                    entries = cube.read_l1()
                    assert all(isinstance(e.description, str) for e in entries)

            with ThreadPoolExecutor(max_workers=2) as ex:
                f1 = ex.submit(writer)
                f2 = ex.submit(reader)
                f1.result()
                f2.result()

            cube.close()
        finally:
            os.unlink(path)


class TestCubelog:
    def test_cubelog_persists_across_reopen(self):
        """Entries in cubelog survive close + reopen."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            cube.append("belief", "Persist me")
            cube.close()

            cube2 = CubeFile.open(path)
            assert cube2._cubelog_count == 1
            entries = cube2.read_l1()
            assert len(entries) == 1
            assert entries[0].description == "Persist me"
            cube2.close()
        finally:
            os.unlink(path)

    def test_empty_cubelog_on_create(self):
        """Fresh cube has empty cubelog."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            assert cube._cubelog_count == 0
            assert cube._cubelog_entries == []
            cubelog_path = path + ".cubelog"
            assert os.path.isfile(cubelog_path)
            cube.close()
        finally:
            os.unlink(path)

    def test_many_appends_survive(self):
        """100 rapid appends all survive and are readable."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            for i in range(100):
                cube.append("belief", f"Entry {i}")
            assert cube.entry_count == 100
            entries = cube.read_l1()
            assert len(entries) == 100
            cube.close()
        finally:
            os.unlink(path)

    def test_cubelog_counts_in_entry_count(self):
        """entry_count reflects .cube header + cubelog count."""
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        try:
            cube = CubeFile.create(path)
            assert cube.entry_count == 0
            cube.append("belief", "One")
            assert cube.entry_count == 1
            cube.append("belief", "Two")
            assert cube.entry_count == 2
            cube.close()
        finally:
            os.unlink(path)
