"""CLI doctor / dense / bootstrap surface tests (lift CLI coverage)."""

from __future__ import annotations

import os
from pathlib import Path

from hermescube.cli import main
from hermescube.cube import CubeFile


def test_doctor_shows_bootstrap_and_density(tmp_path: Path, capsys):
    home = tmp_path / "hh"
    mem = home / "memories"
    mem.mkdir(parents=True)
    (home / "MEMORY.md").write_text("- Prefers dark mode\n", encoding="utf-8")
    cube = CubeFile.create(str(mem / "memory.cube"))
    cube.append("belief", "Prefers dark mode", data={"durable": True})
    for i in range(8):
        cube.append(
            "belief",
            f"Service uses redis and postgres cluster node {i}",
            data={"durable": True},
        )
    cube.close()

    # Minimal config for provider line
    (home / "config.yaml").write_text(
        "memory:\n  provider: hermescube\nplugins:\n  hermescube:\n    memory_policy: auto-safe\n",
        encoding="utf-8",
    )
    plugin = home / "plugins" / "hermescube"
    plugin.mkdir(parents=True)
    (plugin / "__init__.py").write_text("# stub\n", encoding="utf-8")
    (plugin / "plugin.yaml").write_text(
        'name: hermescube\nversion: "0.47.0"\n',
        encoding="utf-8",
    )

    rc = main(["doctor", "--hermes-home", str(home)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "HermesCube doctor" in out
    assert "bootstrap:" in out
    assert "density:" in out


def test_dense_export_import_roundtrip(tmp_path: Path, capsys):
    home = tmp_path / "hh"
    mem = home / "memories"
    mem.mkdir(parents=True)
    cube_path = mem / "memory.cube"
    c = CubeFile.create(str(cube_path))
    c.append("belief", "Alice owns billing", data={"durable": True})
    c.append("trait", "Prefers concise replies", data={"durable": True})
    c.close()

    dense = mem / "pack.dense.jsonl.gz"
    rc = main(
        [
            "dense",
            "export",
            "--hermes-home",
            str(home),
            "--cube",
            str(cube_path),
            "--out",
            str(dense),
        ]
    )
    assert rc == 0
    assert dense.is_file()
    out = capsys.readouterr().out
    assert "exported 2" in out

    rc = main(
        [
            "dense",
            "stats",
            "--hermes-home",
            str(home),
            "--cube",
            str(cube_path),
        ]
    )
    stats_out = capsys.readouterr().out.lower()
    assert rc == 0
    assert "entries" in stats_out
    assert "recommendation" in stats_out or "vector" in stats_out


def test_doctor_nested_identity_paths(tmp_path: Path, capsys):
    home = tmp_path / "hh"
    mem = home / "memories"
    nest = mem / "profiles" / "ilo" / "billing"
    nest.mkdir(parents=True)
    (nest / "candidates.jsonl").write_text(
        '{"candidate_id":"cand_x","status":"pending_review","summary":"fact"}\n',
        encoding="utf-8",
    )
    CubeFile.create(str(mem / "memory.cube")).close()
    (home / "config.yaml").write_text("memory:\n  provider: hermescube\n", encoding="utf-8")
    plugin = home / "plugins" / "hermescube"
    plugin.mkdir(parents=True)
    (plugin / "__init__.py").write_text("# stub\n", encoding="utf-8")

    rc = main(
        [
            "doctor",
            "--hermes-home",
            str(home),
            "--identity",
            "ilo",
            "--workspace",
            "billing",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "profile nest" in out
    assert "candidates:" in out
