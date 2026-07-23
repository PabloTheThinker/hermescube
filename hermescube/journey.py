"""Journey Ledger — playable learning timeline (original Cube mechanism).

Research spine (Nous Hermes patterns — principles, not code copy):
  - /journey + memory graph: agent memory must not be a black box
  - Closed learning loop: show what was learned, allow prune/edit surface
  - Skills + memories accumulate; operator can see growth
  - Hermespace World currently shows Beliefs:(none) while Cube has crystals

This module is NOT:
  - Hermespace world model (that lives in Space)
  - FTS5 session_search
  - Yield / crystalize internals

It IS:
  - Append-only JSONL of *material learn events* (add, crystal, feedback, mirror)
  - Renderable journey.md for humans + agents
  - Export of active wisdom → Hermespace WorldModel.add_belief (bridge)

Path: $HERMES_HOME/memories/journey.jsonl
       $HERMES_HOME/memories/journey.md  (generated)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def default_paths(hermes_home: str | Path | None = None) -> tuple[Path, Path]:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    mem = hh / "memories"
    return mem / "journey.jsonl", mem / "journey.md"


def log_event(
    kind: str,
    summary: str,
    *,
    hermes_home: str | Path | None = None,
    entry_id: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one journey milestone (best-effort, never raises to callers)."""
    summary = (summary or "").strip()
    if not summary or not kind:
        return
    # skip pure noise
    if summary.lower() in ("session ended", "ok", "sure"):
        return
    try:
        if is_noise_text(summary):
            return
    except Exception:
        pass
    jsonl, _md = default_paths(hermes_home)
    try:
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "t": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": kind[:40],
            "summary": summary[:300],
            "entry_id": (entry_id or "")[:24],
            "meta": meta or {},
        }
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        return


def read_events(
    hermes_home: str | Path | None = None,
    *,
    limit: int = 200,
) -> list[dict[str, Any]]:
    jsonl, _ = default_paths(hermes_home)
    if not jsonl.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        lines = jsonl.read_text(encoding="utf-8").splitlines()
        for line in lines[-max(1, limit) :]:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def render_markdown(
    hermes_home: str | Path | None = None,
    *,
    limit: int = 40,
    cube_wisdom: list[tuple[str, float]] | None = None,
) -> str:
    """Human/agent readable journey (Nous /journey spirit)."""
    events = read_events(hermes_home, limit=limit)
    lines = [
        "# HermesCube Journey",
        "",
        "_Playable learning timeline — what the agent actually kept._",
        "",
    ]
    if cube_wisdom:
        lines.append("## Active wisdom (from cube crystals/beliefs)")
        for text, conf in cube_wisdom[:12]:
            stars = "*" * max(1, min(5, int(float(conf) * 5)))
            lines.append(f"- {text[:200]} [{stars}]")
        lines.append("")
    lines.append("## Recent learn events")
    if not events:
        lines.append("- (no journey events yet)")
    else:
        for e in reversed(events[-limit:]):
            iso = e.get("iso") or "?"
            kind = e.get("kind") or "event"
            summary = e.get("summary") or ""
            lines.append(f"- `{iso}` **{kind}** — {summary[:180]}")
    lines.append("")
    lines.append(f"_Events file: `{default_paths(hermes_home)[0]}`_")
    return "\n".join(lines)


def write_markdown(
    hermes_home: str | Path | None = None,
    *,
    cube_wisdom: list[tuple[str, float]] | None = None,
) -> Path:
    _jsonl, md = default_paths(hermes_home)
    text = render_markdown(hermes_home, cube_wisdom=cube_wisdom)
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text(text, encoding="utf-8")
    return md


_NOISE_RE = __import__("re").compile(
    r"(?i)("
    r"PERSIST-PROOF|ADHOC-|DURABILITY-MARKER|SUBPROCESS-|hermes-verify|"
    r"\[CRYSTALIZED\]|\[SUPERSEDED\]|"
    r"^session ended$|"
    r"firsthand Cube session|"
    r"test_token|dogfood-bench|Isolated journey"
    r")"
)


def is_noise_text(text: str) -> bool:
    """True if text should not surface as active wisdom / world belief."""
    t = (text or "").strip()
    if not t:
        return True
    if t.lower() in ("ok", "sure", "session ended", "thanks", "proceed"):
        return True
    if _NOISE_RE.search(t):
        return True
    # conversational shells / dogfood remember prompts
    if t.startswith("User said remember:"):
        return True
    if t.startswith("Confirm Cube") or t.startswith("Confirm cube"):
        return True
    if t.startswith("[HYGIENE]"):
        return True
    return False


def wisdom_from_cube(
    cube_path: str | Path | None = None,
    *,
    entries: list | None = None,
) -> list[tuple[str, float]]:
    """(statement, confidence) from crystals + high-trust beliefs.

    Prefer `entries` when caller already holds the cube lock (exclusive flock).
    Filters dogfood/test noise so world + inject stay doctrine-grade.
    """
    try:
        from hermescube.wisdom import active_wisdom

        ents = list(entries) if entries is not None else None
        if ents is None:
            if not cube_path:
                return []
            from hermescube.cube import CubeFile

            with CubeFile.open(str(cube_path)) as c:
                ents = c.read_l1() or []
        out: list[tuple[str, float]] = []
        for e in active_wisdom(ents, limit=16):
            d = e.data if isinstance(e.data, dict) else {}
            conf = float(d.get("trust") or 0.7)
            if d.get("crystal"):
                conf = max(conf, 0.85)
            desc = (e.description or "").strip()
            if not desc or is_noise_text(desc):
                continue
            out.append((desc, conf))
            if len(out) >= 12:
                break
        return out
    except Exception:
        return []


def prune_events(
    hermes_home: str | Path | None = None,
    *,
    drop_noise: bool = True,
    drop_kinds: list[str] | None = None,
    drop_entry_ids: list[str] | None = None,
    keep_last: int | None = None,
) -> dict[str, Any]:
    """Edit the journey timeline (Nous /journey prune principle).

    Rewrites journey.jsonl in place. Returns counts.
    """
    jsonl, _md = default_paths(hermes_home)
    if not jsonl.is_file():
        return {"kept": 0, "removed": 0, "path": str(jsonl)}
    kinds = set(drop_kinds or [])
    ids = set(drop_entry_ids or [])
    kept: list[dict[str, Any]] = []
    removed = 0
    for e in read_events(hermes_home, limit=50_000):
        summary = str(e.get("summary") or "")
        kind = str(e.get("kind") or "")
        eid = str(e.get("entry_id") or "")
        drop = False
        if drop_noise and is_noise_text(summary):
            drop = True
        if kind in kinds:
            drop = True
        if eid and eid in ids:
            drop = True
        if drop:
            removed += 1
            continue
        kept.append(e)
    if keep_last is not None and keep_last >= 0:
        if len(kept) > keep_last:
            removed += len(kept) - keep_last
            kept = kept[-keep_last:]
    tmp = jsonl.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for e in kept:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, jsonl)
    return {"kept": len(kept), "removed": removed, "path": str(jsonl)}


def hygiene_cube_noise(
    cube,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Supersede dogfood/test noise entries still marked active in the cube."""
    ents = list(cube.read_l1() or [])
    targets = []
    for e in ents:
        if (e.outcome or "") == "superseded":
            continue
        desc = e.description or ""
        if is_noise_text(desc):
            targets.append(e)
    if dry_run:
        return {"would_supersede": len(targets), "ids": [e.id for e in targets[:20]]}
    n = 0
    for e in targets:
        try:
            cube.append(
                entry_type=e.entry_type or "landmark",
                description=f"[HYGIENE] {(desc := (e.description or ''))[:150]}",
                data={
                    "supersedes": e.id,
                    "source": "journey_hygiene",
                    "trust": 0.1,
                },
                outcome="superseded",
            )
            n += 1
        except Exception:
            continue
    return {"superseded": n, "scanned": len(ents)}


def hygiene_world_beliefs(
    *,
    hermespace_home: str | Path | None = None,
    agent_id: str = "hermes-agent",
) -> dict[str, Any]:
    """Drop noise beliefs from Hermespace world (edit surface)."""
    try:
        hs_home = Path(
            hermespace_home
            or os.environ.get("HERMESPACE_HOME")
            or (Path.home() / ".hermespace")
        )
        os.environ.setdefault("HERMESPACE_HOME", str(hs_home))
        for cand in (
            Path.home() / "projects" / "hermespace" / "src",
            Path("/home/ilo/projects/hermespace/src"),
        ):
            if cand.is_dir() and str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
        from hermespace.world import WorldModel  # type: ignore

        wm = WorldModel(agent_id=agent_id)
        before = list(wm.state.beliefs)
        kept = [b for b in before if not is_noise_text(getattr(b, "statement", "") or "")]
        removed = len(before) - len(kept)
        wm.state.beliefs = kept
        wm.save()
        try:
            if hasattr(wm, "render_markdown"):
                jp = Path(getattr(wm, "path", ""))
                if jp.suffix == ".json":
                    jp.with_name("world.md").write_text(wm.render_markdown(), encoding="utf-8")
        except Exception:
            pass
        return {"removed": removed, "kept": len(kept), "ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_hygiene(
    *,
    hermes_home: str | Path | None = None,
    hermespace_home: str | Path | None = None,
    agent_id: str = "hermes-agent",
    cube=None,
    entries: list | None = None,
    sync_world: bool = True,
) -> dict[str, Any]:
    """Full hygiene pass: journey prune + cube noise supersede + world clean + re-push."""
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    out: dict[str, Any] = {}
    out["journey"] = prune_events(hh, drop_noise=True)
    if cube is not None:
        out["cube"] = hygiene_cube_noise(cube, dry_run=False)
        ents = list(cube.read_l1() or [])
    else:
        ents = list(entries) if entries is not None else None
        out["cube"] = {"skipped": True}
    out["world_clean"] = hygiene_world_beliefs(
        hermespace_home=hermespace_home, agent_id=agent_id
    )
    wisdom = wisdom_from_cube(
        hh / "memories" / "memory.cube" if (hh / "memories" / "memory.cube").is_file() else None,
        entries=ents,
    )
    write_markdown(hh, cube_wisdom=wisdom)
    if sync_world:
        out["world_push"] = push_to_hermespace_world(
            hermes_home=hh,
            hermespace_home=hermespace_home,
            agent_id=agent_id,
            entries=ents,
        )
    out["wisdom_n"] = len(wisdom)
    out["ok"] = True
    log_event(
        "hygiene",
        f"Hygiene: journey_removed={out['journey'].get('removed')} "
        f"cube={out.get('cube')} wisdom={len(wisdom)}",
        hermes_home=hh,
        meta={"journey": out["journey"], "wisdom_n": len(wisdom)},
    )
    return out


def push_to_hermespace_world(
    *,
    hermes_home: str | Path | None = None,
    hermespace_home: str | Path | None = None,
    agent_id: str = "default",
    max_beliefs: int = 10,
    entries: list | None = None,
) -> dict[str, Any]:
    """Bridge Cube active wisdom → Hermespace WorldModel beliefs.

    Fixes empty 'Beliefs (Active Wisdom)' when Cube already has crystals.
    Best-effort: no-op if Hermespace not installed.
    Pass `entries` when cube flock already held by caller.
    """
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    cube_path = hh / "memories" / "memory.cube"
    wisdom = wisdom_from_cube(cube_path if cube_path.is_file() else None, entries=entries)
    write_markdown(hh, cube_wisdom=wisdom)

    result: dict[str, Any] = {
        "wisdom_n": len(wisdom),
        "journey_md": str(default_paths(hh)[1]),
        "world_pushed": 0,
        "ok": False,
    }
    if not wisdom:
        return result

    try:
        # Hermespace import path
        hs_home = Path(
            hermespace_home
            or os.environ.get("HERMESPACE_HOME")
            or (Path.home() / ".hermespace")
        )
        os.environ.setdefault("HERMESPACE_HOME", str(hs_home))
        # ensure src on path if present
        for cand in (
            Path.home() / "projects" / "hermespace" / "src",
            Path("/home/ilo/projects/hermespace/src"),
        ):
            if cand.is_dir() and str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
        from hermespace.world import WorldModel  # type: ignore

        wm = WorldModel(agent_id=agent_id)
        n = 0
        for statement, conf in wisdom[:max_beliefs]:
            if "session ended" in statement.lower():
                continue
            wm.add_belief(statement[:200], confidence=float(conf), source="hermescube_journey")
            n += 1
        # Persist world.json + world.md (Hermespace API varies by version)
        try:
            wm.save()
        except Exception:
            pass
        try:
            if hasattr(wm, "write_world_md"):
                wm.write_world_md()
            elif hasattr(wm, "render_markdown"):
                md_path = Path(getattr(wm, "path", Path("."))).with_suffix(".md")
                # world.json sibling world.md
                jp = Path(getattr(wm, "path", ""))
                if jp.suffix == ".json":
                    md_path = jp.with_name("world.md")
                md_path.write_text(wm.render_markdown(), encoding="utf-8")
        except Exception:
            pass
        result["world_pushed"] = n
        result["ok"] = n > 0
        log_event(
            "world_bridge",
            f"Pushed {n} cube wisdom beliefs into Hermespace world",
            hermes_home=hh,
            meta={"n": n},
        )
    except Exception as e:
        result["error"] = str(e)
    return result
