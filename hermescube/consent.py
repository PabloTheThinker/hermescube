"""Consent gate for procedure drafts — promote / reject (original).

Nous parallel: skills.write_approval pending queue.
Cube: drafts under memories/procedures/; promote copies to
memories/procedures/approved/ and records resolve; reject archives.
Never silent skill_manage into ~/.hermes/skills.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path
from typing import Any


def procedures_root(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "procedures"


def list_pending(hermes_home: str | Path | None = None) -> list[dict[str, Any]]:
    root = procedures_root(hermes_home)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("*.md")):
        if p.parent.name in ("approved", "rejected"):
            continue
        out.append(
            {
                "name": p.name,
                "path": str(p),
                "bytes": p.stat().st_size,
                "mtime": p.stat().st_mtime,
            }
        )
    return out


def _safe_name(name: str) -> str:
    n = Path(name).name
    if not n.endswith(".md"):
        n += ".md"
    return n


def promote(
    name: str,
    *,
    hermes_home: str | Path | None = None,
    cube: Any = None,
) -> dict[str, Any]:
    root = procedures_root(hermes_home)
    src = root / _safe_name(name)
    if not src.is_file():
        # allow basename match
        matches = list(root.glob(f"*{name}*")) if name else []
        matches = [m for m in matches if m.is_file() and m.suffix == ".md"]
        if len(matches) == 1:
            src = matches[0]
        else:
            return {"ok": False, "error": f"draft not found: {name}"}
    dest_dir = root / "approved"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    # leave original as pending until reject, or move
    src.unlink(missing_ok=True)
    rec: dict[str, Any] = {
        "ok": True,
        "action": "promoted",
        "path": str(dest),
        "note": "Approved draft only — not installed into Hermes skills. Use skill_manage if you want a live skill.",
    }
    if cube is not None:
        try:
            e = cube.append(
                entry_type="resolve",
                description=f"[PROMOTED] procedure draft {src.name}",
                data={
                    "source": "procedure_consent",
                    "draft": src.name,
                    "approved_path": str(dest),
                    "trust": 0.85,
                    "durable": True,
                },
                outcome="success",
            )
            rec["entry_id"] = getattr(e, "id", None)
        except Exception as ex:
            rec["cube_error"] = str(ex)
    # ledger
    ledger = root / "consent_log.jsonl"
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "action": "promote",
                    "name": src.name,
                    "path": str(dest),
                }
            )
            + "\n"
        )
    return rec


def reject(
    name: str,
    *,
    hermes_home: str | Path | None = None,
    reason: str = "",
) -> dict[str, Any]:
    root = procedures_root(hermes_home)
    src = root / _safe_name(name)
    if not src.is_file():
        matches = [m for m in root.glob(f"*{name}*") if m.is_file()]
        if len(matches) == 1:
            src = matches[0]
        else:
            return {"ok": False, "error": f"draft not found: {name}"}
    dest_dir = root / "rejected"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.move(str(src), str(dest))
    with open(root / "consent_log.jsonl", "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "action": "reject",
                    "name": src.name,
                    "reason": reason[:200],
                }
            )
            + "\n"
        )
    return {"ok": True, "action": "rejected", "path": str(dest)}
