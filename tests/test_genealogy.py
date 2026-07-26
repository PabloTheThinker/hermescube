"""Living cube genealogy — starts at 0.0.0, grows with experience."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hermescube.cube import CubeFile
from hermescube.genealogy import (
    GENESIS,
    bump_version,
    ensure_genesis,
    growth_status,
    list_epochs,
    load_genealogy,
    measure_strength,
    parse_version,
    record_growth,
    refine_skill,
    tick_session,
)
from hermescube.provider import CubeMemoryProvider


class TestVersionMath:
    def test_genesis_parse(self):
        assert parse_version(GENESIS) == (0, 0, 0)
        assert bump_version("0.0.0", "patch") == "0.0.1"
        assert bump_version("0.0.9", "minor") == "0.1.0"
        assert bump_version("0.3.5", "major") == "1.0.0"


class TestGenesisAndGrowth:
    def test_fresh_cube_starts_at_zero(self):
        with tempfile.TemporaryDirectory() as td:
            state = ensure_genesis(td, agent_id="coder")
            assert state["version"] == "0.0.0"
            assert state["era"] == "genesis"
            assert (Path(td) / "memories" / "CUBE.md").is_file()
            epochs = list_epochs(td)
            assert epochs and epochs[0]["kind"] == "genesis"

    def test_session_with_durable_writes_bumps_patch(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            cube = CubeFile.create(str(Path(td) / "memories" / "memory.cube"))
            cube.append(
                "belief", "Always reload units after editing systemd files",
                data={"durable": True, "trust": 0.8},
            )
            r = tick_session(td, cube=cube, durable_writes=1)
            assert r["bumped"] and r["bump"] == "patch"
            assert r["to"] == "0.0.1"
            cube.close()

    def test_promote_bumps_minor(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            r = record_growth(td, "promote", detail="approved deploy checklist")
            assert r["bump"] == "minor"
            assert r["to"] == "0.1.0"

    def test_quiet_session_no_bump(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            r = tick_session(td, durable_writes=0)
            assert not r["bumped"]
            assert r["version"] == "0.0.0"


class TestSkillRefine:
    def test_refine_appends_lesson_and_bumps_skill_and_cube(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            skill_dir = Path(td) / "skills" / "deploy-safely"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: deploy-safely\nversion: 0.1.0\n"
                "origin: hermescube-procedure-forge\n---\n\n"
                "# Deploy safely\n\n1. Run tests\n2. Reload units\n",
                encoding="utf-8",
            )
            r = refine_skill(
                td, "deploy-safely",
                lesson="daemon-reload must precede restart after unit edits",
            )
            assert r["ok"]
            assert r["from_version"] == "0.1.0"
            assert r["to_version"] == "0.1.1"
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            assert "version: 0.1.1" in text
            assert "Lessons from the cube" in text
            assert "daemon-reload" in text
            # cube living version got a minor bump from skill_refine
            assert load_genealogy(td)["version"] == "0.1.0"


class TestStrengthAndEras:
    def test_strength_grows_with_content(self):
        with tempfile.TemporaryDirectory() as td:
            cube = CubeFile.create(str(Path(td) / "m.cube"))
            for i in range(5):
                cube.append(
                    "belief", f"Crystal wisdom number {i} about careful deploys",
                    data={"durable": True, "crystal": True, "trust": 0.9},
                )
            for i in range(3):
                cube.append(
                    "evolution", f"[PROCEDURE] how to ship release {i}",
                    data={"durable": True, "procedure": True, "trust": 0.85},
                )
            s = measure_strength(cube, hermes_home=td)
            assert s["score"] > 15
            assert s["counts"]["crystals"] == 5
            assert s["counts"]["procedures"] == 3
            cube.close()

    def test_era_threshold_earns_major(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            # Seed enough content that strength ≥ 25, then tick
            cube = CubeFile.create(str(Path(td) / "memories" / "memory.cube"))
            for i in range(12):
                cube.append(
                    "belief", f"Hard-won lesson {i}: always verify before cite",
                    data={"durable": True, "crystal": True, "trust": 0.95},
                )
            for i in range(6):
                cube.append(
                    "evolution", f"[PROCEDURE] procedure {i} for careful work",
                    data={"durable": True, "procedure": True, "trust": 0.9},
                )
            # Force a growth event; era crossing should major-bump
            r = record_growth(td, "session", detail="dense archive", cube=cube)
            state = load_genealogy(td)
            assert state["strength"] >= 25
            assert 25 in (state.get("eras_crossed") or [])
            assert r["bump"] == "major"
            assert r["to"] == "1.0.0"
            cube.close()


class TestProviderIntegration:
    def test_initialize_births_genealogy(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td, agent_identity="coder")
            g = growth_status(td, cube=p._cube)
            assert g["version"] == "0.0.0"
            strip = p.system_prompt_block()
            assert "Living Cube v0.0.0" in strip
            p.shutdown()

    def test_manage_growth_status(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            out = json.loads(p.handle_tool_call(
                "hermescube_manage", {"action": "growth", "content": "status"}
            ))
            assert out.get("status") == "growth"
            assert out.get("version") == "0.0.0"
            p.shutdown()

    def test_helpful_feedback_refines_installed_skill(self):
        with tempfile.TemporaryDirectory() as td:
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            skill_dir = Path(td) / "skills" / "careful-deploy"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: careful-deploy\nversion: 0.1.0\n---\n\n# Deploy\n",
                encoding="utf-8",
            )
            e = p._cube.append(
                "evolution", "[SKILL INSTALLED] careful-deploy",
                data={
                    "procedure": True,
                    "skill_path": str(skill_dir / "SKILL.md"),
                    "trust": 0.7,
                    "durable": True,
                },
            )
            out = json.loads(p.handle_tool_call(
                "hermescube_feedback",
                {"action": "helpful", "entry_id": e.id},
            ))
            assert out.get("status") == "rated"
            assert out.get("skill_refined", {}).get("skill") == "careful-deploy"
            assert out["skill_refined"]["version"] == "0.1.1"
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            assert "Lessons from the cube" in text
            p.shutdown()
