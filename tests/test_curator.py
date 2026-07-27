"""Growth curator + maturity ranking — experience strengthens the system."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hermescube.bio_rank import composite_score, maturity_multiplier
from hermescube.cube import CubeFile
from hermescube.curator import (
    list_installed_skills,
    match_lesson_to_skills,
    refine_skills_from_lessons,
    run_curator,
)
from hermescube.genealogy import ensure_genesis, record_growth
from hermescube.hive import build_soul_card, init_hive, pilgrimage, write_offering
from hermescube.provider import CubeMemoryProvider


class TestMaturityRanking:
    def test_elder_boosts_crystals_demotes_ephemeral(self):
        crystal = {"crystal": True, "durable": True, "trust": 0.9}
        ephemeral = {"trust": 0.4}
        assert maturity_multiplier(crystal, era="elder", strength=92) > 1.0
        assert maturity_multiplier(ephemeral, era="elder", strength=92) < 1.0
        assert maturity_multiplier(crystal, era="eden", strength=0) == 1.0
        assert maturity_multiplier(crystal, era="genesis", strength=0) == 1.0  # legacy

    def test_composite_uses_maturity(self):
        data = {"crystal": True, "durable": True, "trust": 0.9}
        base = composite_score(
            0.8, entry_type="belief", trust=0.9, data=data,
            maturity_era="eden", maturity_strength=0,
        )
        elder = composite_score(
            0.8, entry_type="belief", trust=0.9, data=data,
            maturity_era="elder", maturity_strength=92,
        )
        assert elder > base


class TestCuratorMatching:
    def test_match_lesson_to_skill_by_overlap(self):
        with tempfile.TemporaryDirectory() as td:
            skill_dir = Path(td) / "skills" / "cite-carefully"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: cite-carefully\nversion: 0.1.0\n---\n\n"
                "# Cite carefully\n\nTriangulate three independent sources "
                "before citing any claim. Prefer Wayback snapshots.\n",
                encoding="utf-8",
            )
            skills = list_installed_skills(td)
            hits = match_lesson_to_skills(
                "Always triangulate three independent sources before citing",
                skills,
            )
            assert hits and hits[0][0] == "cite-carefully"

    def test_refine_skills_from_drawn_lessons(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            skill_dir = Path(td) / "skills" / "cite-carefully"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: cite-carefully\nversion: 0.1.0\n---\n\n"
                "# Cite carefully\n\nTriangulate three independent sources.\n",
                encoding="utf-8",
            )
            results = refine_skills_from_lessons(
                td,
                [
                    "[HIVE:gza] Always triangulate three independent sources "
                    "before citing a claim"
                ],
            )
            assert results and results[0]["ok"]
            assert results[0]["to_version"] == "0.1.1"
            text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            assert "Lessons from the cube" in text
            assert "triangulate" in text.lower()


class TestSoulCardGrowth:
    def test_soul_card_publishes_living_version(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td, agent_id="coder")
            record_growth(td, "draw", detail="first lessons")
            cube = CubeFile.create(str(Path(td) / "m.cube"))
            cube.append(
                "belief", "Always triangulate three sources",
                data={"durable": True, "crystal": True, "trust": 0.9},
            )
            card = build_soul_card(
                list(cube.read_l1()), agent_id="coder", hermes_home=td
            )
            assert card["growth"]["version"] == "0.0.1"
            assert card["growth"]["cycles"] == 1
            assert card["growth"]["age"]["cycles"] == 1
            assert "era" in card["growth"]
            cube.close()


class TestDrawPreservesDistillation:
    def test_drawn_entries_keep_crystal_flag(self):
        with tempfile.TemporaryDirectory() as td:
            hive = os.path.join(td, "hive")
            init_hive(hive)
            # Seed collective via offering from researcher
            home_r = Path(td) / "researcher"
            (home_r / "memories").mkdir(parents=True)
            cr = CubeFile.create(str(home_r / "memories" / "memory.cube"))
            cr.append(
                "belief",
                "Always triangulate three independent sources before citing",
                data={"durable": True, "crystal": True, "trust": 0.9},
            )
            from hermescube.hive import build_offering, publish_soul_card, build_soul_card

            rows = build_offering(cr, agent_id="researcher")
            # ensure crystal flag survived offering whitelist
            assert any(r.get("data", {}).get("crystal") for r in rows)
            write_offering(hive, rows, agent_id="researcher")
            publish_soul_card(
                hive,
                build_soul_card(list(cr.read_l1()), agent_id="researcher", hermes_home=home_r),
            )
            cr.close()

            home_c = Path(td) / "coder"
            (home_c / "memories").mkdir(parents=True)
            ensure_genesis(home_c, agent_id="coder")
            # Install a matching skill so curator can refine
            skill_dir = home_c / "skills" / "cite-carefully"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: cite-carefully\nversion: 0.1.0\n---\n\n"
                "# Cite carefully\n\nTriangulate three independent sources.\n",
                encoding="utf-8",
            )
            cc = CubeFile.create(str(home_c / "memories" / "memory.cube"))
            cc.append(
                "belief", "Deploy with daemon-reload first always",
                data={"durable": True, "trust": 0.8},
            )
            cc.close()

            r = pilgrimage(
                hive, hermes_home=home_c, agent_id="coder", focus="sources"
            )
            assert r["ok"]
            assert (r.get("draw") or {}).get("drawn", 0) >= 1
            # crystal preserved on local draw
            with CubeFile.open(str(home_c / "memories" / "memory.cube")) as c:
                hive_ents = [
                    e for e in c.read_l1()
                    if (e.description or "").startswith("[HIVE:")
                ]
                assert hive_ents
                assert any(
                    (e.data or {}).get("crystal") for e in hive_ents
                )
            # curator refined the overlapping skill
            cur = r.get("curator") or {}
            refines = cur.get("refines") or []
            assert any(x.get("skill") == "cite-carefully" for x in refines)


class TestProviderMaturity:
    def test_engine_gets_maturity_on_init(self):
        with tempfile.TemporaryDirectory() as td:
            ensure_genesis(td)
            record_growth(td, "promote", detail="first procedure")
            # Force era/strength into genealogy for ranking context
            from hermescube.genealogy import load_genealogy, save_genealogy

            g = load_genealogy(td)
            g["era"] = "formed"
            g["strength"] = 55
            save_genealogy(g, td)
            p = CubeMemoryProvider()
            p.initialize(session_id="s1", hermes_home=td)
            mat = getattr(p._engine, "_maturity", {})
            assert mat.get("era") == "formed"
            assert mat.get("strength") == 55
            out = json.loads(p.handle_tool_call(
                "hermescube_manage", {"action": "curate", "mode": "milestone"}
            ))
            assert out.get("status") == "curate"
            assert out.get("era_milestone") is True
            p.shutdown()
