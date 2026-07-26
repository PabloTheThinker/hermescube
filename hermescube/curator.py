"""Growth curator — Hermes-style closed learning loop for the Cube.

Hermes Agent has a curator that grades, prunes, and consolidates the skill
library. HermesCube's curator does the same for *lived memory*:

1. Match freshly drawn hive lessons to installed skills → refine them
2. On era milestones (major bumps), forge procedure drafts + garden dormant
3. Keep the living pulse honest — compose existing chambers, never invent

Nothing is silently installed. Forge writes pending drafts; gardener writes
proposals; skill refine only appends lessons. Consent stays at the top.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{2,}")
_STOP = frozenset(
    "the and for with that this from into your our are was were been have has "
    "not but you they them then than also just about when what who how why "
    "use used using via will can may always never must hive interview "
    "lesson lessons carefully".split()
)


def _tokens(text: str) -> set[str]:
    out = set()
    for t in _TOKEN.findall((text or "").lower()):
        if t not in _STOP and len(t) >= 3:
            out.add(t)
    return out


def list_installed_skills(hermes_home: str | Path) -> list[dict[str, Any]]:
    """Return installed Hermes skills with name + body tokens for matching."""
    root = Path(hermes_home) / "skills"
    if not root.is_dir():
        return []
    out = []
    for skill_md in root.rglob("SKILL.md"):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except Exception:
            continue
        name = skill_md.parent.name
        out.append(
            {
                "name": name,
                "path": str(skill_md),
                "tokens": _tokens(name + " " + text[:2000]),
                "text": text[:400],
            }
        )
    return out


def match_lesson_to_skills(
    lesson: str,
    skills: list[dict[str, Any]],
    *,
    min_overlap: int = 2,
) -> list[tuple[str, int]]:
    """Rank installed skills by topical overlap with a drawn lesson."""
    lt = _tokens(lesson)
    if not lt:
        return []
    scored = []
    for sk in skills:
        overlap = len(lt & (sk.get("tokens") or set()))
        # name tokens count double
        name_toks = _tokens(sk.get("name") or "")
        overlap += len(lt & name_toks)
        if overlap >= min_overlap:
            scored.append((str(sk["name"]), overlap))
    scored.sort(key=lambda x: -x[1])
    return scored


def refine_skills_from_lessons(
    hermes_home: str | Path,
    lessons: list[str],
    *,
    cube: Any = None,
    max_refines: int = 3,
) -> list[dict[str, Any]]:
    """Refine installed skills that overlap with drawn / interviewed lessons.

    This is how drawn experience *strengthens* skills — the Hermes closed
    learning loop applied to Cube→skill evolution.
    """
    from hermescube.genealogy import refine_skill

    skills = list_installed_skills(hermes_home)
    if not skills or not lessons:
        return []

    results = []
    refined_names: set[str] = set()
    for lesson in lessons:
        if len(results) >= max_refines:
            break
        clean = (lesson or "").strip()
        # strip hive/interview prefixes for matching and lesson text
        for prefix in ("[HIVE:", "[INTERVIEW:"):
            if clean.startswith(prefix) and "]" in clean:
                clean = clean.split("]", 1)[1].strip()
        if len(clean) < 24:
            continue
        matches = match_lesson_to_skills(clean, skills)
        for name, score in matches[:1]:
            if name in refined_names:
                continue
            r = refine_skill(
                hermes_home,
                name,
                lesson=f"from collective experience (overlap={score}): {clean[:200]}",
                cube=cube,
            )
            if r.get("ok"):
                refined_names.add(name)
                results.append(r)
            break
    return results


def run_curator(
    hermes_home: str | Path,
    *,
    cube: Any = None,
    lessons: list[str] | None = None,
    era_milestone: bool = False,
    do_garden: bool = True,
    do_forge: bool = True,
    max_refines: int = 3,
) -> dict[str, Any]:
    """One curator pass — refine skills, optionally forge + garden on milestones.

    ``era_milestone`` should be True when genealogy just major-bumped
    (awakening / formed / seasoned / elder). That is when the cube has
    earned a deeper consolidation pass.
    """
    home = Path(hermes_home)
    report: dict[str, Any] = {
        "ok": True,
        "refines": [],
        "forge": None,
        "garden": None,
        "era_milestone": era_milestone,
    }

    # 1. Always: drawn/interviewed lessons → skill refinements
    if lessons:
        try:
            report["refines"] = refine_skills_from_lessons(
                home, lessons, cube=cube, max_refines=max_refines
            )
        except Exception as e:
            report["refines_error"] = str(e)

    # 2. Era milestones: forge procedure drafts + garden dormant memories
    if era_milestone:
        if do_forge and cube is not None:
            try:
                from hermescube.procedure import forge

                report["forge"] = forge(
                    cube, hermes_home=home, limit=4, write_drafts=True
                )
            except Exception as e:
                report["forge_error"] = str(e)
        if do_garden and cube is not None:
            try:
                from hermescube.self_evolution import run_gardener

                report["garden"] = run_gardener(cube, home)
            except Exception as e:
                report["garden_error"] = str(e)

    return report
