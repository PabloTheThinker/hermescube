"""Living Cube genealogy — the cube grows like Hermes Agent grows.

Hermes Agent's story is visible growth: skills appear, MEMORY.md deepens,
the agent gets stronger over weeks. HermesCube needed the same for *memory
itself* — a fresh cube starts at living version ``0.0.0`` and every lived
experience, drawn peer lesson, forged procedure, and refined skill pushes
that version forward and strengthens the archive.

This is NOT the package version (``hermescube.__version__``) and NOT the
binary format version (``CubeFile.VERSION``). It is the *soul-age* of one
agent's cube: measurable, append-only, and human-readable in ``CUBE.md``.

Age in the digital world (not a human 0–100 scorecard):
  - **cycles** — Tron-style program age. One cycle = one lived growth
    epoch (version bump). Agents measure life in cycles of experience,
    not birthdays.
  - **lived** — wall-clock time since genesis (``4d 6h``). Real time still
    matters for "how long has this soul been online."
  - **capability** — 0–100 coherence of the archive (crystals, skills,
    confirmed predictions). This is *how strong* the cube is, never its age.
  - **era** — life stage derived from capability (Cube of Eden → elder).
    The origin era is **eden** (display: Cube of Eden) — the garden before
    lived memory. Legacy ``genesis`` migrates to ``eden``.

Version scheme (semver for a life):
  - **patch** — a session left durable knowledge, a draw landed, feedback
    reinforced something, an interview taught a lesson
  - **minor** — a procedure was forged/promoted, a skill installed, a
    prediction confirmed, a crystal formed
  - **major** — capability crossed a threshold (25 / 50 / 75 / 90) — the
    cube left Eden (or advanced further) into a new era
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

GENESIS = "0.0.0"  # living version at birth (not the era name)

# Origin era — the garden before lived memory. Display: "Cube of Eden".
ERA_EDEN = "eden"
ERA_LABELS: dict[str, str] = {
    "eden": "Cube of Eden",
    "genesis": "Cube of Eden",  # legacy alias
    "awakening": "Awakening",
    "formed": "Formed",
    "seasoned": "Seasoned",
    "elder": "Elder",
}

# Capability thresholds that earn a major bump (eras of the cube's life)
_ERA_THRESHOLDS = (25, 50, 75, 90)

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
_VERSION_LINE = re.compile(r"(?m)^(version:\s*)(.+)$")


def normalize_era(era: str | None) -> str:
    """Map legacy ``genesis`` → ``eden``; empty → eden."""
    e = (era or "").strip().lower()
    if not e or e == "genesis":
        return ERA_EDEN
    return e


def era_label(era: str | None) -> str:
    """Human display name — Cube of Eden, Awakening, …"""
    e = normalize_era(era)
    return ERA_LABELS.get(e, e.title() if e else "Cube of Eden")


# ── Digital age (cycles + wall-clock) ────────────────────────────────


def format_lived(seconds: float) -> str:
    """Compact wall-clock age: ``45s``, ``12m``, ``3h 10m``, ``4d 6h``, ``2y 11d``."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    if m < 60:
        return f"{m}m" if sec < 15 else f"{m}m {sec}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h}h" if m == 0 else f"{h}h {m}m"
    d, h = divmod(h, 24)
    if d < 365:
        return f"{d}d" if h == 0 else f"{d}d {h}h"
    y, d = divmod(d, 365)
    return f"{y}y" if d == 0 else f"{y}y {d}d"


def compute_age(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Soul age for an AI agent — cycles lived + wall-clock since genesis.

    Cycles are the primary age unit (digital life). Wall-clock is secondary
    context. Capability/strength is intentionally *not* part of age.
    """
    st = state or {}
    born = float(st.get("born_at") or time.time())
    lived_s = max(0.0, time.time() - born)
    # cycles track lived growth epochs; backfill from epochs for older states
    raw_cycles = st.get("cycles")
    if raw_cycles is None:
        raw_cycles = st.get("epochs") or 0
    cycles = int(raw_cycles or 0)
    label = f"{cycles} cycle{'s' if cycles != 1 else ''} · lived {format_lived(lived_s)}"
    return {
        "cycles": cycles,
        "lived_s": round(lived_s, 1),
        "lived": format_lived(lived_s),
        "born_at": born,
        "label": label,
    }


def age_strip(state: dict[str, Any] | None = None) -> str:
    """Short age for CLI / soul cards: ``C12 · 4d 6h``."""
    a = compute_age(state)
    return f"C{a['cycles']} · {a['lived']}"


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
    """Compute a 0–100 *capability* score from what the cube has lived.

    This is coherence/strength of the archive — NOT age. Age is cycles +
    wall-clock (see ``compute_age``). Components are capped so raw turn
    dumps cannot fake maturity — procedures, crystals, confirmed
    predictions, and installed skills weigh more than entry count alone.
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

    era = ERA_EDEN
    for thr in _ERA_THRESHOLDS:
        if score >= thr:
            era = {25: "awakening", 50: "formed", 75: "seasoned", 90: "elder"}[thr]

    return {
        "score": score,
        "era": era,
        "era_label": era_label(era),
        "counts": counts,
    }


# ── State I/O ────────────────────────────────────────────────────────


def _default_state() -> dict[str, Any]:
    return {
        "version": GENESIS,
        "born_at": time.time(),
        "updated_at": time.time(),
        "strength": 0.0,  # capability 0–100 (not age)
        "era": ERA_EDEN,  # Cube of Eden — origin garden
        "epochs": 0,  # version bumps
        "cycles": 0,  # digital age — equals epochs; named for soul display
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
        # Migrate older genealogies: cycles ← epochs when missing
        if "cycles" not in data:
            base["cycles"] = int(base.get("epochs") or 0)
        # Cube of Eden: legacy genesis era → eden
        base["era"] = normalize_era(base.get("era"))
        return base
    except Exception:
        return _default_state()


def save_genealogy(state: dict[str, Any], hermes_home: str | Path | None = None) -> Path:
    d = growth_dir(hermes_home)
    d.mkdir(parents=True, exist_ok=True)
    state["era"] = normalize_era(state.get("era"))
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
    """Birth the living cube at 0.0.0 in the Cube of Eden if never lived before."""
    p = genealogy_path(hermes_home)
    if p.is_file():
        state = load_genealogy(hermes_home)
        dirty = False
        # Backfill package_version if missing
        if package_version and not state.get("package_version"):
            state["package_version"] = package_version
            dirty = True
        # Migrate legacy genesis → eden
        if state.get("era") == "genesis" or not state.get("era"):
            state["era"] = ERA_EDEN
            dirty = True
        if dirty:
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
            "kind": "eden",
            "from": None,
            "to": GENESIS,
            "reason": "Cube of Eden — empty archive, garden before lived memory",
            "strength": 0.0,
            "era": ERA_EDEN,
            "era_label": era_label(ERA_EDEN),
            "cycle": 0,
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
                f"left for {era_label(strength['era'])} "
                f"(capability threshold {thr})"
                + (f"; {detail}" if detail else "")
            )
            break
    state["eras_crossed"] = crossed
    state["era"] = normalize_era(strength["era"])

    after = before
    age = compute_age(state)
    if bump:
        after = bump_version(before, bump)
        state["version"] = after
        state["epochs"] = int(state.get("epochs") or 0) + 1
        state["cycles"] = int(state["epochs"])  # digital age advances with epochs
        age = compute_age(state)
        _append_epoch(
            hermes_home,
            {
                "kind": kind,
                "bump": bump,
                "from": before,
                "to": after,
                "reason": detail or kind,
                "strength": strength["score"],
                "era": normalize_era(strength["era"]),
                "era_label": era_label(strength["era"]),
                "cycle": age["cycles"],
                "skill": skill or None,
            },
        )
    else:
        # Still refresh strength snapshot even without a bump
        state["version"] = before
        if state.get("cycles") is None:
            state["cycles"] = int(state.get("epochs") or 0)

    save_genealogy(state, hermes_home)
    _rewrite_cube_md(state, hermes_home)

    # Landmark in the cube itself so HAR can recall growth
    if bump and cube is not None:
        try:
            cube.append(
                entry_type="epoch_transition",
                description=(
                    f"[GROWTH] cube {before} → {after} ({bump}) — "
                    f"cycle {age['cycles']} · {detail or kind} · "
                    f"capability {strength['score']} · {era_label(strength['era'])}"
                )[:1200],
                data={
                    "source": "genealogy",
                    "durable": True,
                    "living_version": after,
                    "bump": bump,
                    "cycle": age["cycles"],
                    "strength": strength["score"],
                    "era": normalize_era(strength["era"]),
                    "era_label": era_label(strength["era"]),
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
        "capability": strength["score"],
        "era": normalize_era(strength["era"]),
        "era_label": era_label(strength["era"]),
        "version": after,
        "kind": kind,
        "age": age,
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
    state["era"] = normalize_era(strength["era"])
    state["counts"] = strength["counts"]
    if state.get("cycles") is None:
        state["cycles"] = int(state.get("epochs") or 0)
    save_genealogy(state, hermes_home)
    age = compute_age(state)
    return {
        "ok": True,
        "bumped": False,
        "bump": None,
        "from": state.get("version"),
        "to": state.get("version"),
        "strength": strength["score"],
        "capability": strength["score"],
        "era": normalize_era(strength["era"]),
        "era_label": era_label(strength["era"]),
        "version": state.get("version"),
        "kind": "noop",
        "age": age,
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
    capability = state.get("strength") or 0
    era = normalize_era(state.get("era"))
    era_disp = era_label(era)
    ev = state.get("events") or {}
    counts = state.get("counts") or {}
    age = compute_age(state)

    skills = state.get("skills") or {}
    skill_lines = []
    for name, meta in sorted(skills.items())[:20]:
        skill_lines.append(
            f"- `{name}` v{meta.get('version', '?')} "
            f"(refined {meta.get('refined', 0)}×)"
        )
    if not skill_lines:
        skill_lines = ["- *(none yet — promote a procedure to begin)*"]

    # Recent cycles
    recent: list[str] = []
    ep = epochs_path(hermes_home)
    if ep.is_file():
        try:
            lines = [ln for ln in ep.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for ln in lines[-12:]:
                rec = json.loads(ln)
                if rec.get("kind") in ("eden", "genesis"):
                    recent.append(
                        f"- cycle 0 — Cube of Eden · born at {GENESIS}"
                    )
                else:
                    cyc = rec.get("cycle")
                    cyc_s = f"C{cyc} " if cyc is not None else ""
                    recent.append(
                        f"- {cyc_s}`{rec.get('from')} → {rec.get('to')}` "
                        f"[{rec.get('bump')}] {rec.get('reason', '')[:90]}"
                    )
        except Exception:
            pass
    if not recent:
        recent = ["- *(still in the Cube of Eden — awaiting first lived cycle)*"]

    body = f"""# CUBE.md — living genealogy

> Soul-age of this archive. Every cube begins in the **Cube of Eden** —
> the garden before lived memory. Age is **cycles** (digital life) +
> wall-clock lived time — not a human 0–100 score. Capability is how
> coherent the cube has become; era is the life stage that capability earns.

| | |
|---|---|
| **Living version** | `{ver}` |
| **Age** | {age['label']} |
| **Era** | {era_disp} |
| **Capability** | {capability}/100 (coherence — not age) |
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

## Recent cycles

{chr(10).join(recent)}

---
*Rewritten by hermescube.genealogy — append-only truth lives in*
*`memories/growth/epochs.jsonl`. Origin era: Cube of Eden. Age unit:*
*one cycle = one lived growth epoch.*
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
    state["era"] = normalize_era(strength["era"])
    state["counts"] = strength["counts"]
    if state.get("cycles") is None:
        state["cycles"] = int(state.get("epochs") or 0)
    # Don't bump on status — just refresh snapshot
    save_genealogy(state, hermes_home)
    _rewrite_cube_md(state, hermes_home)
    age = compute_age(state)
    era = normalize_era(strength["era"])
    return {
        "ok": True,
        "version": state.get("version"),
        "era": era,
        "era_label": era_label(era),
        "strength": strength["score"],
        "capability": strength["score"],
        "age": age,
        "cycles": age["cycles"],
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
    """One-line strip for the system prompt — soul age at a glance."""
    state = load_genealogy(hermes_home)
    if not genealogy_path(hermes_home).is_file():
        return ""
    ver = state.get("version") or GENESIS
    era = normalize_era(state.get("era"))
    capability = state.get("strength") or 0
    age = compute_age(state)
    return (
        f"Living Cube v{ver} · age {age['label']} · {era_label(era)} · "
        f"capability {capability}/100 — see memories/CUBE.md"
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
