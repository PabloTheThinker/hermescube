"""Dense archive packing tests."""

import gzip
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.dense import export_dense, import_dense_into_cube


def test_dense_export_much_smaller_than_live():
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "m.cube"
        CubeFile.create(str(cp))
        with CubeFile.open(str(cp)) as c:
            for i in range(30):
                c.append("belief", f"Fact number {i} about system component {i%5}")
            live = c.density_stats()["total_bytes"]
        out = Path(td) / "pack.jsonl.gz"
        rep = export_dense(cp, out)
        assert rep["entries"] == 30
        assert out.stat().st_size < live
        assert rep["compression_ratio"] > 2.0


def test_dense_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        cp = Path(td) / "a.cube"
        CubeFile.create(str(cp))
        with CubeFile.open(str(cp)) as c:
            c.append("trait", "User prefers teal accents")
        pack = Path(td) / "p.jsonl.gz"
        export_dense(cp, pack)
        cp2 = Path(td) / "b.cube"
        n = import_dense_into_cube(pack, cp2, create=True)
        assert n == 1
        with CubeFile.open(str(cp2)) as c:
            assert any("teal" in e.description for e in c.read_l1())
