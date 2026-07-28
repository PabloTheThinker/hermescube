"""CLI coverage for hive / HQ / interview (fleet path)."""

from __future__ import annotations

from pathlib import Path

from hermescube.cli import main
from hermescube.cube import CubeFile


def test_hive_init_status_souls(tmp_path: Path, capsys):
    hive = tmp_path / "hive"
    rc = main(["hive", "init", "--hive", str(hive)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Hive ready" in out

    rc = main(["hive", "status", "--hive", str(hive)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "collective entries" in out.lower() or "souls" in out.lower() or "Hive:" in out

    rc = main(["hive", "souls", "--hive", str(hive)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "No souls" in out or "—" in out or "agent" in out.lower()


def test_hq_charter_route_verify(tmp_path: Path, capsys):
    hive = tmp_path / "hq"
    assert main(["hive", "init", "--hive", str(hive)]) == 0
    capsys.readouterr()

    rc = main(
        [
            "hq",
            "charter",
            "--hive",
            str(hive),
            "--agent",
            "coder",
            "--role",
            "specialist",
            "--lane",
            "coding and tests",
            "--keywords",
            "coding,tests,debug",
        ]
    )
    assert rc == 0
    assert "Chartered" in capsys.readouterr().out

    rc = main(
        [
            "hq",
            "charter",
            "--hive",
            str(hive),
            "--agent",
            "chief",
            "--role",
            "command",
            "--lane",
            "orchestration",
            "--keywords",
            "route,approve",
        ]
    )
    assert rc == 0
    capsys.readouterr()

    rc = main(["hq", "list", "--hive", str(hive)])
    assert rc == 0
    listed = capsys.readouterr().out
    assert "coder" in listed and "chief" in listed

    rc = main(
        ["hq", "route", "--hive", str(hive), "--task", "debug failing unit tests"]
    )
    assert rc == 0
    routed = capsys.readouterr().out
    assert "Owner:" in routed
    assert "coder" in routed

    rc = main(["hq", "verify", "--hive", str(hive)])
    # healthy → 0, findings → 2; both are valid CLI outcomes
    assert rc in (0, 2)
    assert "Fleet verdict" in capsys.readouterr().out


def test_hive_missing_path_errors(capsys):
    rc = main(["hive", "status"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "hive path required" in err.lower()


def test_manage_dispatch_covers_fleet_actions():
    from hermescube.manage import known_actions

    acts = set(known_actions())
    for a in ("hive", "hq", "interview", "cuboasis", "bootstrap", "add", "nexus"):
        assert a in acts
