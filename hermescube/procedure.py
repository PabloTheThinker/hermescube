"""Procedure Forge — promote durable success into reusable procedures.

Research spine (Nous Hermes — principles, not code copy):
  - Closed learning loop: experience → skills the agent can reuse
  - skill_manage after complex wins; skills are procedural memory
  - MEMORY.md = doctrine; skills = how-to; Cube = long-tail warehouse
  - /journey makes learning visible; skills make it *actionable*

This is NOT:
  - Auto-writing into ~/.hermes/skills (operator must install)
  - LLM skill authoring
  - Replacing skill_manage

It IS:
  - Detect high-trust success resolves / procedures in the cube
  - Emit evolution entries tagged procedure=True
  - Write draft SKILL stubs under $HERMES_HOME/memories/procedures/
  - Surface candidates via manage action=forge

Drafts are reviewable artifacts — stand up to Nous by closing
store → consolidate → procedure, without silent skill thrash.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hermescube.cube import CubeFile

logger = logging.getLogger(__name__)

_PROC_HINT = re.compile(
    r"(?i)\b("
    r"how to|steps?|run |use |install|configure|deploy|wire|enable|"
    r"never |always |must |path|command|script|workflow|procedure|"
    r"update |doctor|prefetch|benchmark|gate|provider|plugin"
    r")\b"
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str, *, max_len: int = 48) -> str:
    s = _SLUG_RE.sub("-", (text or "").lower()).strip("-")
    return (s[:max_len] or "procedure").strip("-")


def procedures_dir(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "procedures"


def is_procedure_candidate(entry: Any) -> bool:
    """Heuristic: durable successful how-to / resolve worth promoting."""
    if (getattr(entry, "outcome", "") or "") == "superseded":
        return False
    desc = (getattr(entry, "description", "") or "").strip()
    if len(desc) < 24:
        return False
    # skip noise via journey filter if available
    try:
        from hermescube.journey import is_noise_text

        if is_noise_text(desc):
            return False
    except Exception:
        pass
    et = (getattr(entry, "entry_type", "") or "").lower()
    data = getattr(entry, "data", None) or {}
    if not isinstance(data, dict):
        data = {}
    if data.get("procedure") is True:
        return False  # already forged
    trust = data.get("trust")
    try:
        trust_f = float(trust) if trust is not None else 0.55
    except (TypeError, ValueError):
        trust_f = 0.55
    outcome = (getattr(entry, "outcome", "") or "none").lower()
    if et in ("resolve", "evolution") and outcome in ("success", "none"):
        if trust_f >= 0.55 or _PROC_HINT.search(desc):
            return True
    if data.get("crystal") and et in ("belief", "resolve") and _PROC_HINT.search(desc):
        return True
    if et == "resolve" and outcome == "success":
        return True
    if trust_f >= 0.8 and _PROC_HINT.search(desc) and et in ("belief", "landmark", "resolve"):
        return True
    return False


def list_candidates(entries: list[Any], *, limit: int = 20) -> list[Any]:
    out = [e for e in entries if is_procedure_candidate(e)]
    # prefer success + trust
    def score(e: Any) -> float:
        d = e.data if isinstance(e.data, dict) else {}
        t = float(d.get("trust") or 0.5)
        bonus = 0.2 if (e.outcome or "") == "success" else 0.0
        bonus += 0.15 if d.get("crystal") else 0.0
        return t + bonus

    out.sort(key=score, reverse=True)
    return out[:limit]


def _draft_markdown(entry: Any, *, source_id: str) -> str:
    desc = (entry.description or "").strip()
    title = desc[:80].rstrip(".")
    name = _slug(title)
    et = entry.entry_type or "resolve"
    outcome = entry.outcome or "none"
    trust = (entry.data or {}).get("trust") if isinstance(entry.data, dict) else None
    return f"""---
name: {name}
description: "Draft procedure promoted from HermesCube ({et}). Review before skill_manage install."
version: 0.1.0-draft
origin: hermescube-procedure-forge
source_entry_id: {source_id}
---

# {title}

> **Draft** — forged from cube memory. Not installed into Hermes skills until you promote it.

## When to use
- When the situation matches: {desc[:200]}

## Procedure
1. Recall context from HermesCube (`hermescube_search` / prefetch).
2. Apply the durable decision/fact below.
3. If the workflow drifts, patch this draft or run `hermescube_manage action=forge` again.

### Source memory
- **Type:** {et}
- **Outcome:** {outcome}
- **Trust:** {trust}
- **Entry ID:** `{source_id}`
- **Text:** {desc}

## Verification
- [ ] Still true on this host
- [ ] No secrets in the draft
- [ ] Ready for `skill_manage` create (optional)

## Notes
Forged at {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} by HermesCube Procedure Forge.
Nous alignment: experience → reusable procedure (operator-gated install).
"""


def forge(
    cube: "CubeFile",
    *,
    hermes_home: str | Path | None = None,
    limit: int = 8,
    write_drafts: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Promote candidates → evolution procedure entries + optional draft SKILL.md files."""
    entries = list(cube.read_l1() or [])
    cands = list_candidates(entries, limit=limit)
    out_dir = procedures_dir(hermes_home)
    forged: list[dict[str, Any]] = []
    drafts: list[str] = []

    # already forged source ids
    already = set()
    for e in entries:
        d = e.data if isinstance(e.data, dict) else {}
        if d.get("procedure") and d.get("source_entry_id"):
            already.add(str(d.get("source_entry_id")))
        if d.get("forged_from"):
            already.add(str(d.get("forged_from")))

    for e in cands:
        if e.id in already:
            continue
        desc = (e.description or "").strip()
        if dry_run:
            forged.append({"id": e.id, "description": desc[:120], "dry_run": True})
            continue
        try:
            data = {
                "procedure": True,
                "forged_from": e.id,
                "source_entry_id": e.id,
                "source": "procedure_forge",
                "trust": max(
                    0.75,
                    float((e.data or {}).get("trust") or 0.7)
                    if isinstance(e.data, dict)
                    else 0.7,
                ),
                "durable": True,
            }
            added = cube.append(
                entry_type="evolution",
                description=f"[PROCEDURE] {desc[:220]}",
                data=data,
                outcome="success",
            )
            rec = {
                "id": added.id,
                "from": e.id,
                "description": desc[:160],
            }
            if write_drafts:
                out_dir.mkdir(parents=True, exist_ok=True)
                slug = _slug(desc)
                # stable filename from source id
                h = hashlib.sha256(e.id.encode()).hexdigest()[:8]
                path = out_dir / f"{slug}-{h}.md"
                path.write_text(_draft_markdown(e, source_id=e.id), encoding="utf-8")
                rec["draft"] = str(path)
                drafts.append(str(path))
            forged.append(rec)
            try:
                from hermescube.journey import log_event

                log_event(
                    "procedure_forge",
                    f"Forged procedure from {e.id}: {desc[:120]}",
                    hermes_home=hermes_home,
                    entry_id=added.id,
                    meta={"from": e.id, "draft": rec.get("draft")},
                )
            except Exception:
                pass
        except Exception as ex:
            logger.warning("forge failed for %s: %s", e.id, ex)

    return {
        "candidates": len(cands),
        "forged": len(forged),
        "items": forged,
        "drafts": drafts,
        "procedures_dir": str(out_dir),
        "dry_run": dry_run,
    }


def list_drafts(hermes_home: str | Path | None = None) -> list[dict[str, Any]]:
    d = procedures_dir(hermes_home)
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob("*.md")):
        out.append(
            {
                "path": str(p),
                "name": p.stem,
                "bytes": p.stat().st_size,
                "mtime": p.stat().st_mtime,
            }
        )
    return out
