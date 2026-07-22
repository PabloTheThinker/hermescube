"""Tests for hermescube CLI commands."""

import json
import os
import tempfile

from hermescube.cli import main


class TestCLI:
    def test_init(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            rc = main(["init", path])
            assert rc == 0
            assert os.path.isfile(path)

    def test_init_custom_dim(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            rc = main(["init", path, "--dim", "128", "--buckets", "32"])
            assert rc == 0
            from hermescube.cube import CubeFile
            with CubeFile.open(path) as cube:
                assert cube.dim == 128
                assert cube.l2_bucket_count == 32

    def test_info(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["info", path])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Entries: 0" in out
            assert "Dimension: 256" in out

    def test_append(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["append", path, "-t", "belief", "-d", "User likes dark mode"])
            assert rc == 0
            from hermescube.cube import CubeFile
            with CubeFile.open(path) as cube:
                entries = cube.read_l1()
                assert len(entries) == 1
                assert entries[0].description == "User likes dark mode"

    def test_append_with_data(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["append", path, "-t", "trait", "-d", "Prefers Python",
                        "--data", '{"lang": "python"}'])
            assert rc == 0
            from hermescube.cube import CubeFile
            with CubeFile.open(path) as cube:
                entries = cube.read_l1()
                assert entries[0].data == {"lang": "python"}

    def test_query_empty(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["query", path, "memory"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "No results" in out

    def test_query_with_entries(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            main(["append", path, "-t", "belief", "-d", "User prefers dark mode"])
            main(["append", path, "-t", "belief", "-d", "User likes Python"])
            main(["evolve", path])
            rc = main(["query", path, "programming language"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Results" in out

    def test_evolve(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            for i in range(5):
                main(["append", path, "-t", "belief", "-d", f"Fact {i}"])
            rc = main(["evolve", path])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Evolution complete" in out

    def test_dump(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            main(["append", path, "-t", "landmark", "-d", "Deployed v1.0"])
            rc = main(["dump", path])
            assert rc == 0
            out = capsys.readouterr().out
            assert "Total entries: 1" in out
            assert "Deployed v1.0" in out

    def test_dump_jsonl(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            main(["append", path, "-t", "belief", "-d", "Test fact"])
            capsys.readouterr()  # clear previous output
            rc = main(["dump", path, "--jsonl"])
            assert rc == 0
            out = capsys.readouterr().out.strip()
            data = json.loads(out)
            assert data["description"] == "Test fact"

    def test_beta(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["beta", path])
            assert rc == 0
            out = capsys.readouterr().out
            assert "β norm:" in out
            assert "β dim: 256" in out

    def test_beta_show(self, capsys):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            main(["init", path])
            rc = main(["beta", path, "--show"])
            assert rc == 0
            out = capsys.readouterr().out
            assert "β vector" in out

    def test_invalid_cube_path(self):
        rc = main(["info", "/nonexistent/path.cube"])
        assert rc == 1

    def test_full_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test.cube")
            # Init → append → evolve → query → dump → info → beta
            assert main(["init", path]) == 0
            assert main(["append", path, "-t", "belief", "-d", "User likes dark mode"]) == 0
            assert main(["append", path, "-t", "trait", "-d", "Prefers concise answers"]) == 0
            assert main(["evolve", path]) == 0
            assert main(["query", path, "preferences"]) == 0
            assert main(["dump", path]) == 0
            assert main(["info", path]) == 0
            assert main(["beta", path]) == 0
