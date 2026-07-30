"""Security suite unit tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from hermescube import security as sec


def test_assert_under_home_blocks_escape(tmp_path: Path):
    home = tmp_path / "h"
    home.mkdir()
    outside = tmp_path / "other" / "x"
    outside.parent.mkdir()
    outside.write_text("nope")
    with pytest.raises(sec.SecurityError):
        sec.assert_under_home(outside, home, label="x")


def test_assert_under_home_allows_inside(tmp_path: Path):
    home = tmp_path / "h"
    mem = home / "memories"
    mem.mkdir(parents=True)
    f = mem / "memory.cube"
    f.write_bytes(b"x")
    got = sec.assert_under_home(f, home, label="cube")
    assert got == f.resolve()


def test_forbidden_env():
    assert sec.is_forbidden_rel(".env")
    assert sec.is_forbidden_rel("memories/.env")
    assert sec.is_forbidden_rel("auth.json")
    assert not sec.is_forbidden_rel("memories/MEMORY.md")


def test_scan_secrets():
    assert sec.scan_text_for_secrets("key sk-" + "a" * 24)
    assert not sec.scan_text_for_secrets("hello world library book")


def test_harden_and_audit(tmp_path: Path):
    home = tmp_path / "hermes"
    mem = home / "memories"
    mem.mkdir(parents=True)
    cube = mem / "memory.cube"
    cube.write_bytes(b"cube")
    soul = home / "SOUL.md"
    soul.write_text("I am a test soul")
    # leaky modes
    cube.chmod(0o666)
    r = sec.harden_home_permissions(home)
    assert r["ok"]
    assert stat_mode(cube) & 0o077 == 0
    rep = sec.audit_home(home)
    assert rep["hermes_home"] == str(home.resolve())
    # should not be critical on clean home
    assert rep["summary"]["critical"] == 0


def stat_mode(p: Path) -> int:
    return p.stat().st_mode & 0o777
