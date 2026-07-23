"""Persistence + integrity: real data survives close/reopen/evolve."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from hermescube import CubeFile, HARQueryEngine


def test_append_survives_close_reopen(tmp_path: Path):
    path = str(tmp_path / "p.cube")
    marker = "DURABILITY-MARKER-ALPHA-REAL-DATA"
    c = CubeFile.create(path)
    e = c.append("landmark", marker, data={"source": "test"}, outcome="success")
    eid = e.id
    c.close()

    c2 = CubeFile.open(path)
    found = [x for x in c2.read_l1() if marker in (x.description or "")]
    assert len(found) == 1
    assert found[0].id == eid
    assert found[0].outcome == "success"
    assert found[0].data.get("source") == "test"
    assert found[0].vector is not None
    integ = c2.integrity_check()
    assert integ["ok"] is True
    assert integ["entries_read"] == 1
    assert integ["bad_vectors"] == 0
    c2.close()


def test_cubelog_then_evolve_keeps_data(tmp_path: Path):
    path = str(tmp_path / "e.cube")
    c = CubeFile.create(path)
    markers = []
    for i in range(5):
        m = f"EVOLVE-KEEP-{i}-REAL"
        e = c.append("belief", m, data={"i": i})
        markers.append((e.id, m))
    assert Path(path + ".cubelog").is_file()
    eng = HARQueryEngine(c)
    eng.evolve()
    c.close()

    c2 = CubeFile.open(path)
    texts = {e.description for e in c2.read_l1()}
    for _eid, m in markers:
        assert m in texts
    integ = c2.integrity_check()
    assert integ["ok"] is True
    hits = HARQueryEngine(c2).query("EVOLVE-KEEP-3-REAL", top_k=3)
    assert hits and "EVOLVE-KEEP-3" in (hits[0][0].description or "")
    c2.close()


def test_subprocess_cold_open(tmp_path: Path):
    path = str(tmp_path / "s.cube")
    marker = "SUBPROCESS-COLD-OPEN-MARKER"
    c = CubeFile.create(path)
    c.append("trait", marker)
    c.close()
    code = (
        "import sys; sys.path.insert(0, %r); from hermescube import CubeFile; "
        "c=CubeFile.open(%r); "
        "ok=any(%r in (e.description or '') for e in c.read_l1()); "
        "print('OK' if ok else 'FAIL'); c.close(); raise SystemExit(0 if ok else 1)"
        % (str(Path(__file__).resolve().parents[1]), path, marker)
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "OK" in r.stdout
