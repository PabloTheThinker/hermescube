"""First-run bootstrap — import hot memories + install skills."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hermescube.bootstrap import (
    bootstrap_status,
    install_bundled_skills,
    parse_memory_markdown,
    run_bootstrap,
)
from hermescube.provider import CubeMemoryProvider


def test_parse_memory_markdown_bullets_and_types():
    md = """# Preferences
- Prefers dark mode in all editors
- Likes concise replies

## People
- Alice = billing owner

## Notes
Some longer paragraph about Redis cluster topology that should import.
"""
    facts = parse_memory_markdown(md, source="MEMORY.md")
    descs = [f["description"] for f in facts]
    assert any("dark mode" in d.lower() for d in descs)
    assert any("Alice" in d for d in descs)
    assert any(f["entry_type"] == "trait" for f in facts if "dark mode" in f["description"].lower())


def test_bootstrap_import_and_skills(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    (home / "MEMORY.md").write_text(
        "# User\n- Prefers dark mode always\n- Uses postgres and redis\n",
        encoding="utf-8",
    )
    (home / "USER.md").write_text(
        "- Name = Pablo\n- Speaks English\n",
        encoding="utf-8",
    )

    p = CubeMemoryProvider(auto_extract=False)
    # Disable auto so we test explicit manage path
    p._auto_bootstrap = False
    p.initialize(session_id="b1", hermes_home=str(home), platform="cli")
    assert p._cube.entry_count == 0

    out = json.loads(
        p.handle_tool_call(
            "hermescube_manage",
            {"action": "bootstrap", "mode": "all"},
        )
    )
    assert out.get("ok") is True
    assert (out.get("import") or {}).get("imported", 0) >= 2
    assert p._cube.entry_count >= 2

    st = bootstrap_status(p._cube, str(home))
    assert st["needs_import"] is False
    assert "hermescube-operate" in (st.get("skills_installed") or [])

    prompt = p.system_prompt_block()
    assert "Mental model" in prompt
    assert "hermescube_search" in prompt
    # After import, Start here should be gone
    assert "Start here" not in prompt

    # Idempotent second run
    out2 = json.loads(
        p.handle_tool_call(
            "hermescube_manage",
            {"action": "bootstrap", "mode": "import"},
        )
    )
    assert (out2.get("import") or {}).get("imported", 0) == 0
    p.shutdown()


def test_auto_bootstrap_on_initialize(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    (home / "MEMORY.md").write_text(
        "- Project Alpha uses vault tokens\n- Deploy path = /opt/alpha\n",
        encoding="utf-8",
    )
    p = CubeMemoryProvider(auto_extract=False)
    p.initialize(session_id="auto", hermes_home=str(home), platform="cli")
    assert p._cube.entry_count >= 1
    assert p._last_bootstrap is not None
    prompt = p.system_prompt_block()
    assert "Mental model" in prompt
    assert "Bootstrap (this session)" in prompt or "Warehouse" in prompt
    p.shutdown()


def test_empty_prompt_shows_start_here(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    # No MEMORY.md — still show start here when empty + skills missing
    p = CubeMemoryProvider(auto_extract=False)
    p._auto_bootstrap = False
    p.initialize(session_id="e1", hermes_home=str(home), platform="cli")
    prompt = p.system_prompt_block()
    assert "Start here" in prompt
    assert "bootstrap mode=all" in prompt
    p.shutdown()


def test_install_bundled_skills_copies_operate():
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        r = install_bundled_skills(home)
        assert r["ok"]
        assert (home / "skills" / "hermescube-operate" / "SKILL.md").is_file()
        assert (home / "skills" / "hermescube-import" / "SKILL.md").is_file()


def test_run_bootstrap_status_only(tmp_path: Path):
    home = tmp_path / "hh"
    (home / "memories").mkdir(parents=True)
    p = CubeMemoryProvider(auto_extract=False)
    p._auto_bootstrap = False
    p.initialize(session_id="s", hermes_home=str(home), platform="cli")
    st = run_bootstrap(p._cube, str(home), mode="status")
    assert st.get("status") == "bootstrap"
    assert "needs_import" in st
    p.shutdown()
