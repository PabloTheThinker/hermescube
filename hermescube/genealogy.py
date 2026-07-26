"""Living Cube genealogy — the cube grows like Hermes Agent grows.

Hermes Agent's story is visible growth: skills appear, MEMORY.md deepens,
the agent gets stronger over weeks. HermesCube needed the same for *memory
itself* — a fresh cube starts at living version ``0.0.0`` and every lived
experience, drawn peer lesson, forged procedure, and refined skill pushes
that version forward and strengthens the archive.

This is NOT the package version (``hermescube.__version__``) and NOT the
binary format version (``CubeFile.VERSION``). It is the *soul-age* of one
agent's cube: measurable, append-only, and human-readable in ``CUBE.md``.

Version scheme (semver for a life):
  - **patch** — a session left durable knowledge, a draw landed, feedback
    reinforced something, an interview taught a lesson
  - **minor** — a procedure was forged/promoted, a skill installed, a
    prediction confirmed, a crystal formed
  - **major** — strength crossed a threshold (25 / 50 / 75 / 90) — the
    cube entered a new era of capability
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GENESIS = "0.0.0"

# Strength thresholds that earn a major bump (eras of the cube's life)
_ERA_THRESHOLDS = (25, 50, 75, 90)

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_VERSION_LINE = re.compile(r"(?m)^(version:\s*)(.+)$")


def growth_dir(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "growth"


def genealogy_path(hermes_home: str | Path | None = None) -> Path:
    return growth_dir(hermes_home) / "genealogy.json"


def epochs_path(hermes_home: str | Path | None = None) -> Path:
    return growth_dir(hermes_home) / "epochs.jsonl"


def cube_md_path(hermes_home: str | Path | None = None) -> Path:
    """Human-readable growth diary — the cube's equivalent of Hermes' MEMORY.md story."""
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "CUBE.md"


# ── Version arithmetic ───────────────────────────────────────────────


def parse_version(v: str) -> tuple[int, int, int]:
    parts = (v or GENESIS).strip().lstrip("v").split(".")
    nums = []
    for p in parts[:3]:
        m = re.match(r"(\d+)", p)
        nums.append(int(m.group(1)) if m else 0)
    while len(nums) < 3:
        nums.append(0)
    return nums[0], nums[1], nums[2]


def format_version(major: int, minor: int, patch: int) -> str:
    return f"{max(0, major)}.{max(0, minor)}.{max(0, patch)}"


def bump_version(v: str, kind: str) -> str:
    major, minor, patch = parse_version(v)
    if kind == "major":
        return format_version(major + 1, 0, 0)
    if kind == "minor":
        return format_version(major, minor + 1, 0)
    return format_version(major, minor, patch + 1)


# ── Strength ─────────────────────────────────────────────────────────


def measure_strength(
    cube: Any = None,
    *,
    hermes_home: str | Path | None = None,
) -> dict[str, Any]:
    """Compute a 0–100 strength score from what the cube has lived.

    Components are capped so no single pile of raw turns can fake maturity —
    procedures, crystals, confirmed predictions, and installed skills weigh
    more than entry count alone.
    """
    home = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    counts = {
        "entries": 0,
        "durable": 0,
        "crystals": 0,
        "procedures": 0,
        "hive_draws": 0,
        "interviews": 0,
        "skills_installed": 0,
        "predictions_confirmed": 0,
        "mean_trust": 0.0,
    }
    trusts: list[float] = []
    if cube is not None:
        try:
            entries = list(cube.read_l1() or [])
        except Exception:
            entries = []
        counts["entries"] = len(entries)
        for e in entries:
            d = e.data if isinstance(getattr(e, "data", None), dict) else {}
            if d.get("durable") or d.get("crystal") or d.get("procedure"):
                counts["durable"] += 1
            if d.get("crystal"):
                counts["crystals"] += 1
            if d.get("procedure") or (e.description or "").startswith(
                ("[PROCEDURE]", "[PROMOTED]", "[SKILL INSTALLED]")
            ):
                counts["procedures"] += 1
            if d.get("hive_shared") or (e.description or "").startswith("[HIVE:"):
                counts["hive_draws"] += 1
            if (e.description or "").startswith("[INTERVIEW:"):
                counts["interviews"] += 1
            t = d.get("trust")
            if isinstance(t, (int, float)):
                trusts.append(float(t))
        if trusts:
            counts["mean_trust"] = sum(trusts) / len(trusts)

    skills_root = home / "skills"
    if skills_root.is_dir():
        counts["skills_installed"] = sum(
            1 for p in skills_root.rglob("SKILL.md") if p.is_file()
        )

    preds = home / "memories" / "harness" / "predictions.jsonl"
    if preds.is_file():
        try:
            for line in preds.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("verdict") == "confirmed":
                    counts["predictions_confirmed"] += 1
        except Exception:
            pass

    # Weighted composite → 0..100
    score = 0.0
    score += min(20.0, counts["durable"] * 0.4)
    score += min(15.0, counts["crystals"] * 3.0)
    score += min(20.0, counts["procedures"] * 4.0)
    score += min(10.0, counts["skills_installed"] * 5.0)
    score += min(10.0, counts["hive_draws"] * 1.5)
    score += min(8.0, counts["interviews"] * 2.0)
    score += min(10.0, counts["predictions_confirmed"] * 5.0)
    score += min(7.0, counts["mean_trust"] * 7.0)
    score = round(min(100.0, score), 1)

    era = "genesis"
    for thr in _ERA_THRESHOLDS:
        if score >= thr:
            era = {25: "awakening", 50: "formed", 75: "seasoned", 90: "elder"}[thr]

    return {
        "score": score,
        "era": era,
        "counts": counts,
    }


# ── State I/O ────────────────────────────────────────────────────────


def _default_state() -> dict[str, Any]:
    return {
        "version": GENESIS,
        "born_at": time.time(),
        "updated_at": time.time(),
        "strength": 0.0,
        "era": "genesis",
        "epochs": 0,
        "events": {
            "sessions": 0,
            "draws": 0,
            "interviews": 0,
            "promotions": 0,
            "skill_installs": 0,
            "skill_refines": 0,
            "predictions_confirmed": 0,
            "crystals": 0,
        },
        "skills": {},  # name → {version, refined, path}
        "eras_crossed": [],
        "package_version": "",
    }


def load_genealogy(hermes_home: str | Path | None = None) -> dict[str, Any]:
    p = genealogy_path(hermes_home)
    if not p.is_file():
        return _default_state()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_state()
        base = _default_state()
        base.update(data)
        base.setdefault("events", _default_state()["events"])
        base.setdefault("skills", {})
        base.setdefault("eras_crossed", [])
        return base
    except Exception:
        return _default_state()


def save_genealogy(state: dict[str, Any], hermes_home: str | Path | None = None) -> Path:
    d = growth_dir(hermes_home)
    d.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.time()
    p = genealogy_path(hermes_home)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, p)
    return p


def ensure_genesis(
    hermes_home: str | Path | None = None,
    *,
    agent_id: str = "",
    package_version: str = "",
) -> dict[str, Any]:
    """Birth the living cube at 0.0.0 if it has never lived before."""
    p = genealogy_path(hermes_home)
    if p.is_file():
        state = load_genealogy(hermes_home)
        # Backfill package_version if missing
        if package_version and not state.get("package_version"):
            state["package_version"] = package_version
            save_genealogy(state, hermes_home)
        return state

    try:
        from hermescube import __version__ as pkg_v
    except Exception:
        pkg_v = package_version or ""
    state = _default_state()
    state["agent_id"] = agent_id or "hermes"
    state["package_version"] = package_version or pkg_v
    save_genealogy(state, hermes_home)
    _append_epoch(
        hermes_home,
        {
            "kind": "genesis",
            "from": None,
            "to": GENESIS,
            "reason": "cube born — empty archive, ready to live",
            "strength": 0.0,
            "era": "genesis",
        },
    )
    _rewrite_cube_md(state, hermes_home)
    return state


def _append_epoch(hermes_home: str | Path | None, event: dict[str, Any]) -> None:
    d = growth_dir(hermes_home)
    d.mkdir(parents=True, exist_ok=True)
    rec = {"ts": time.time(), **event}
    with open(epochs_path(hermes_home), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


# ── Growth events ────────────────────────────────────────────────────


# Event kinds → bump weight
_PATCH_KINDS = frozenset(
    {
        "session",
        "draw",
        "interview",
        "feedback_up",
        "evolve",
        "offering",
    }
)
_MINOR_KINDS = frozenset(
    {
        "promote",
        "skill_install",
        "skill_refine",
        "crystal",
        "prediction_confirmed",
        "forge",
    }
)


def record_growth(
    hermes_home: str | Path | None,
    kind: str,
    *,
    detail: str = "",
    cube: Any = None,
    skill: str = "",
    skill_version: str = "",
    force_bump: str = "",
) -> dict[str, Any]:
    """Record a lived experience and advance the living version if earned.

    Returns the updated genealogy state plus bump metadata.
    """
    state = ensure_genesis(hermes_home)
    before = state.get("version") or GENESIS
    strength = measure_strength(cube, hermes_home=hermes_home)
    state["strength"] = strength["score"]
    state["era"] = strength["era"]
    state["counts"] = strength["counts"]

    # Event counters
    ev = state.setdefault("events", {})
    counter_key = {
        "session": "sessions",
        "draw": "draws",
        "interview": "interviews",
        "promote": "promotions",
        "skill_install": "skill_installs",
        "skill_refine": "skill_refines",
        "prediction_confirmed": "predictions_confirmed",
        "crystal": "crystals",
    }.get(kind)
    if counter_key:
        ev[counter_key] = int(ev.get(counter_key) or 0) + 1

    if skill:
        sk = state.setdefault("skills", {})
        entry = sk.setdefault(skill, {"version": "0.1.0", "refined": 0})
        if skill_version:
            entry["version"] = skill_version
        if kind == "skill_refine":
            entry["refined"] = int(entry.get("refined") or 0) + 1
        entry["updated_at"] = time.time()

    # Decide bump
    bump = force_bump
    if not bump:
        if kind in _MINOR_KINDS:
            bump = "minor"
        elif kind in _PATCH_KINDS:
            bump = "patch"

    # Era crossings → major (once per threshold)
    crossed = list(state.get("eras_crossed") or [])
    for thr in _ERA_THRESHOLDS:
        if strength["score"] >= thr and thr not in crossed:
            crossed.append(thr)
            bump = "major"
            detail = (
                f"era threshold {thr} crossed → {strength['era']}"
                + (f"; {detail}" if detail else "")
            )
            break
    state["eras_crossed"] = crossed

    after = before
    if bump:
        after = bump_version(before, bump)
        state["version"] = after
        state["epochs"] = int(state.get("epochs") or 0) + 1
        _append_epoch(
            hermes_home,
            {
                "kind": kind,
                "bump": bump,
                "from": before,
                "to": after,
                "reason": detail or kind,
                "strength": strength["score"],
                "era": strength["era"],
                "skill": skill or None,
            },
        )
    else:
        # Still refresh strength snapshot even without a bump
        state["version"] = before

    save_genealogy(state, hermes_home)
    _rewrite_cube_md(state, hermes_home)

    # Landmark in the cube itself so HAR can recall growth
    if bump and cube is not None:
        try:
            cube.append(
                entry_type="epoch_transition",
                description=(
                    f"[GROWTH] cube {before} → {after} ({bump}) — "
                    f"{detail or kind} · strength {strength['score']} · era {strength['era']}"
                )[:1200],
                data={
                    "source": "genealogy",
                    "durable": True,
                    "living_version": after,
                    "bump": bump,
                    "strength": strength["score"],
                    "era": strength["era"],
                    "trust": 0.8,
                },
                outcome="success",
            )
        except Exception as e:
            logger.debug("growth landmark skipped: %s", e)

    return {
        "ok": True,
        "bumped": bool(bump),
        "bump": bump or None,
        "from": before,
        "to": after,
        "strength": strength["score"],
        "era": strength["era"],
        "version": after,
        "kind": kind,
    }


def tick_session(
    hermes_home: str | Path | None,
    *,
    cube: Any = None,
    durable_writes: int = 0,
    drew: int = 0,
    interviewed: int = 0,
    promoted: int = 0,
    skills_installed: int = 0,
    crystals: int = 0,
    predictions_confirmed: int = 0,
) -> dict[str, Any]:
    """End-of-session growth tick — one bump at the highest earned weight.

    Call once per session_end / pilgrimage. Prefer the strongest signal
    (skill install > promote > crystal > interview > draw > session).
    """
    ensure_genesis(hermes_home)
    if skills_installed:
        return record_growth(
            hermes_home, "skill_install",
            detail=f"{skills_installed} skill(s) installed this cycle",
            cube=cube,
        )
    if promoted:
        return record_growth(
            hermes_home, "promote",
            detail=f"{promoted} procedure(s) promoted",
            cube=cube,
        )
    if predictions_confirmed:
        return record_growth(
            hermes_home, "prediction_confirmed",
            detail=f"{predictions_confirmed} prediction(s) confirmed",
            cube=cube,
        )
    if crystals:
        return record_growth(
            hermes_home, "crystal",
            detail=f"{crystals} wisdom crystal(s) formed",
            cube=cube,
        )
    if interviewed:
        return record_growth(
            hermes_home, "interview",
            detail=f"interviewed {interviewed} peer(s)",
            cube=cube,
        )
    if drew:
        return record_growth(
            hermes_home, "draw",
            detail=f"drew {drew} collective lesson(s)",
            cube=cube,
        )
    if durable_writes > 0:
        return record_growth(
            hermes_home, "session",
            detail=f"session left {durable_writes} durable memor(ies)",
            cube=cube,
        )
    # Quiet session — refresh strength snapshot, no bump
    state = load_genealogy(hermes_home)
    strength = measure_strength(cube, hermes_home=hermes_home)
    state["strength"] = strength["score"]
    state["era"] = strength["era"]
    state["counts"] = strength["counts"]
    save_genealogy(state, hermes_home)
    return {
        "ok": True,
        "bumped": False,
        "bump": None,
        "from": state.get("version"),
        "to": state.get("version"),
        "strength": strength["score"],
        "era": strength["era"],
        "version": state.get("version"),
        "kind": "noop",
    }


# ── Skill refinement (skills evolve from experience) ─────────────────


def _bump_semver_patch(v: str) -> str:
    major, minor, patch = parse_version(v)
    return format_version(major, minor, patch + 1)


def refine_skill(
    hermes_home: str | Path,
    skill_name: str,
    *,
    lesson: str,
    cube: Any = None,
) -> dict[str, Any]:
    """Append a lived lesson to an installed skill and bump its patch version.

    This is how skills strengthen over time — the same skill folder Hermes
    Agent uses, but the Cube owns the evolution ledger. Never rewrites the
    core procedure body; only appends under ``## Lessons from the cube``.
    """
    home = Path(hermes_home)
    safe = re.sub(r"[^a-z0-9._-]+", "-", (skill_name or "").lower()).strip("-")
    if not safe:
        return {"ok": False, "error": "skill_name required"}
    skill_md = home / "skills" / safe / "SKILL.md"
    if not skill_md.is_file():
        # try fuzzy match
        matches = list((home / "skills").glob(f"*{safe}*/SKILL.md")) if (home / "skills").is_dir() else []
        if len(matches) == 1:
            skill_md = matches[0]
            safe = skill_md.parent.name
        else:
            return {"ok": False, "error": f"skill not found: {skill_name}"}

    text = skill_md.read_text(encoding="utf-8")
    # Extract / bump version in frontmatter
    cur_ver = "0.1.0"
    m = _FRONT_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if line.strip().startswith("version:"):
                cur_ver = line.split(":", 1)[1].strip().strip("\"'")
                break
    new_ver = _bump_semver_patch(cur_ver)

    if _VERSION_LINE.search(text):
        text = _VERSION_LINE.sub(rf"\g<1>{new_ver}", text, count=1)
    elif text.startswith("---"):
        text = text.replace("---\n", f"---\nversion: {new_ver}\n", 1)
    else:
        text = f"---\nname: {safe}\nversion: {new_ver}\n---\n\n" + text

    lesson_clean = (lesson or "").strip()[:500]
    if not lesson_clean:
        return {"ok": False, "error": "lesson required"}
    stamp = time.strftime("%Y-%m-%d")
    block = f"\n- ({stamp}, v{new_ver}) {lesson_clean}"
    marker = "## Lessons from the cube"
    if marker in text:
        text = text.rstrip() + block + "\n"
    else:
        text = text.rstrip() + f"\n\n{marker}\n{block}\n"

    skill_md.write_text(text, encoding="utf-8")

    growth = record_growth(
        hermes_home,
        "skill_refine",
        detail=f"skill '{safe}' {cur_ver} → {new_ver}: {lesson_clean[:80]}",
        cube=cube,
        skill=safe,
        skill_version=new_ver,
    )
    return {
        "ok": True,
        "skill": safe,
        "from_version": cur_ver,
        "to_version": new_ver,
        "path": str(skill_md),
        "growth": growth,
    }


# ── CUBE.md (readable growth diary) ──────────────────────────────────


def _rewrite_cube_md(state: dict[str, Any], hermes_home: str | Path | None) -> None:
    """Rewrite the human-readable growth diary (like Hermes' visible learning story)."""
    p = cube_md_path(hermes_home)
    p.parent.mkdir(parents=True, exist_ok=True)
    ver = state.get("version") or GENESIS
    strength = state.get("strength") or 0
    era = state.get("era") or "genesis"
    ev = state.get("events") or {}
    counts = state.get("counts") or {}
    born = state.get("born_at") or time.time()
    age_days = max(0, (time.time() - float(born)) / 86400)

    skills = state.get("skills") or {}
    skill_lines = []
    for name, meta in sorted(skills.items())[:20]:
        skill_lines.append(
            f"- `{name}` v{meta.get('version', '?')} "
            f"(refined {meta.get('refined', 0)}×)"
        )
    if not skill_lines:
        skill_lines = ["- *(none yet — promote a procedure to begin)*"]

    # Recent epochs
    recent: list[str] = []
    ep = epochs_path(hermes_home)
    if ep.is_file():
        try:
            lines = [ln for ln in ep.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines[-12:]:
                rec = json.loads(ln)
                if rec.get("kind") == "genesis":
                    recent.append(f"- genesis — cube born at {GENESIS}")
                else:
                    recent.append(
                        f"- `{rec.get('from')} → {rec.get('to')}` "
                        f"[{rec.get('bump')}] {rec.get('reason', '')[:90]}"
                    )
        except Exception:
            pass
    if not recent:
        recent = ["- *(awaiting first lived experience)*"]

    body = f"""# CUBE.md — living genealogy

> This cube's soul-age. Not the HermesCube package version —
> the life this archive has lived with its Hermes Agent.

| | |
|---|---|
| **Living version** | `{ver}` |
| **Era** | {era} |
| **Strength** | {strength}/100 |
| **Age** | {age_days:.1f} days |
| **Epochs lived** | {state.get('epochs', 0)} |
| **Package** | hermescube {state.get('package_version') or '?'} |

## What it has become

- Durable memories: {counts.get('durable', 0)}
- Wisdom crystals: {counts.get('crystals', 0)}
- Procedures forged: {counts.get('procedures', 0)}
- Skills installed: {counts.get('skills_installed', 0)}
- Hive lessons drawn: {counts.get('hive_draws', 0)}
- Peer interviews held: {counts.get('interviews', 0)}
- Predictions confirmed: {counts.get('predictions_confirmed', 0)}
- Mean trust: {float(counts.get('mean_trust') or 0):.2f}

## Lifecycle counters

- Sessions with growth: {ev.get('sessions', 0)}
- Collective draws: {ev.get('draws', 0)}
- Promotions: {ev.get('promotions', 0)}
- Skill installs: {ev.get('skill_installs', 0)}
- Skill refinements: {ev.get('skill_refines', 0)}

## Skills evolving with this cube

{chr(10).join(skill_lines)}

## Recent epochs

{chr(10).join(recent)}

---
*Rewritten by hermescube.genealogy — append-only truth lives in*
*`memories/growth/epochs.jsonl`.*
"""
    p.write_text(body, encoding="utf-8")


def growth_status(
    hermes_home: str | Path | None = None,
    *,
    cube: Any = None,
) -> dict[str, Any]:
    """Snapshot for CLI / manage tool / system prompt."""
    state = ensure_genesis(hermes_home)
    strength = measure_strength(cube, hermes_home=hermes_home)
    state["strength"] = strength["score"]
    state["era"] = strength["era"]
    state["counts"] = strength["counts"]
    # Don't bump on status — just refresh snapshot
    save_genealogy(state, hermes_home)
    _rewrite_cube_md(state, hermes_home)
    return {
        "ok": True,
        "version": state.get("version"),
        "era": strength["era"],
        "strength": strength["score"],
        "epochs": state.get("epochs", 0),
        "born_at": state.get("born_at"),
        "events": state.get("events"),
        "counts": strength["counts"],
        "skills": state.get("skills"),
        "eras_crossed": state.get("eras_crossed"),
        "cube_md": str(cube_md_path(hermes_home)),
        "genealogy": str(genealogy_path(hermes_home)),
    }


def prompt_strip(hermes_home: str | Path | None = None) -> str:
    """One-line strip for the system prompt — the cube's age at a glance."""
    state = load_genealogy(hermes_home)
    if not genealogy_path(hermes_home).is_file():
        return ""
    ver = state.get("version") or GENESIS
    era = state.get("era") or "genesis"
    strength = state.get("strength") or 0
    return (
        f"Living Cube v{ver} ({era}, strength {strength}/100) — "
        f"grows with every session; see memories/CUBE.md"
    )


def list_epochs(hermes_home: str | Path | None = None, *, limit: int = 30) -> list[dict[str, Any]]:
    ep = epochs_path(hermes_home)
    if not ep.is_file():
        return []
    out = []
    try:
        lines = [ln for ln in ep.read_text(encoding="utf-8").splitlines() if ln.strip()]
        for ln in lines[-limit:]:
            out.append(json.loads(ln))
    except Exception:
        return []
    return out
