"""Branchable consolidation — propose, measure, merge or rollback.

Offline 'dream' work should produce reviewable diffs, not silent rewrites.
This module snapshots sidecar state before evolve and can restore it.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any


def consolidate_root(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "consolidate"


def _copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def snapshot_sidecars(hermes_home: str | Path, *, label: str = "") -> dict[str, Any]:
    """Snapshot rebuildable projections before consolidation."""
    home = Path(hermes_home)
    mem = home / "memories"
    branch = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    if label:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)[:40]
        branch = f"{branch}_{safe}"
    root = consolidate_root(home) / branch
    root.mkdir(parents=True, exist_ok=True)

    names = [
        "engram_net.json",
        "yield_gradient.json",
        "colony_graph.json",
        "peer_card.json",
        "living_state.json",
        "catalog.json",
        "ingest_cursor.json",
        "memory.embedder",
    ]
    copied: list[str] = []
    for name in names:
        if _copy_if_exists(mem / name, root / name):
            copied.append(name)

    meta = {
        "branch": branch,
        "created_at": time.time(),
        "label": label,
        "copied": copied,
        "status": "open",
    }
    (root / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def list_branches(hermes_home: str | Path) -> list[dict[str, Any]]:
    root = consolidate_root(hermes_home)
    if not root.is_dir():
        return []
    out = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        except Exception:
            meta = {}
        meta.setdefault("branch", d.name)
        meta["path"] = str(d)
        out.append(meta)
    return out


def rollback_sidecars(hermes_home: str | Path, branch: str) -> dict[str, Any]:
    """Restore sidecar projections from a consolidation snapshot."""
    home = Path(hermes_home)
    root = consolidate_root(home) / branch
    if not root.is_dir():
        return {"ok": False, "error": f"branch not found: {branch}"}
    mem = home / "memories"
    restored: list[str] = []
    for src in root.iterdir():
        if src.name == "meta.json" or not src.is_file():
            continue
        dest = mem / src.name
        shutil.copy2(src, dest)
        restored.append(src.name)
    meta_path = root / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {}
    meta["status"] = "rolled_back"
    meta["rolled_back_at"] = time.time()
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "branch": branch, "restored": restored}


def mark_merged(hermes_home: str | Path, branch: str, *, note: str = "") -> dict[str, Any]:
    root = consolidate_root(hermes_home) / branch
    meta_path = root / "meta.json"
    if not meta_path.is_file():
        return {"ok": False, "error": f"branch not found: {branch}"}
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        meta = {"branch": branch}
    meta["status"] = "merged"
    meta["merged_at"] = float(time.time())  # type: ignore[assignment]
    if note:
        meta["note"] = note[:300]
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "branch": branch, "status": "merged"}


def run_branched_evolve(
    provider: Any,
    *,
    label: str = "evolve",
) -> dict[str, Any]:
    """Snapshot sidecars, run evolve_consolidated, mark merged on success."""
    home = getattr(provider, "_hermes_home", None) or os.environ.get("HERMES_HOME")
    if not home:
        return {"ok": False, "error": "hermes_home missing"}
    snap = snapshot_sidecars(home, label=label)
    branch = snap["branch"]
    try:
        provider.evolve_consolidated()
        if hasattr(provider, "_refresh_snapshot"):
            provider._refresh_snapshot()
        mark_merged(home, branch, note="evolve_consolidated ok")
        return {"ok": True, "branch": branch, "status": "merged", "snapshot": snap}
    except Exception as e:
        rb = rollback_sidecars(home, branch)
        return {
            "ok": False,
            "branch": branch,
            "error": str(e),
            "rollback": rb,
        }
