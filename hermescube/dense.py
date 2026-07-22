#!/usr/bin/env python3
"""Dense export/import — zip-class text archive without replacing live .cube.

Live cube keeps fast vectors for recall. This packs **descriptions + metadata**
into a compact portable file agents can ship/backup (gzip JSONL).
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any, Iterable

from hermescube.cube import CubeFile


def export_dense(cube_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    """Write entries as gzip JSONL (no float vectors) — small portable archive."""
    cube_path = Path(cube_path)
    out_path = Path(out_path)
    with CubeFile.open(str(cube_path)) as cube:
        entries = cube.read_l1() or []
        dens = cube.density_stats()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for e in entries:
            row = {
                "id": e.id,
                "ts": e.timestamp,
                "type": e.entry_type,
                "outcome": e.outcome,
                "description": e.description,
                "data": e.data or {},
                "parents": e.causal_parents or [],
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    out_sz = out_path.stat().st_size
    return {
        "entries": n,
        "out_bytes": out_sz,
        "live_total_bytes": dens.get("total_bytes"),
        "compression_ratio": (dens.get("total_bytes") or 0) / out_sz if out_sz else 0,
        "path": str(out_path),
    }


def iter_dense(path: str | Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def import_dense_into_cube(
    dense_path: str | Path,
    cube_path: str | Path,
    *,
    create: bool = True,
) -> int:
    """Rehydrate a dense archive into a live cube (re-embeds vectors)."""
    cube_path = Path(cube_path)
    if create and not cube_path.exists():
        CubeFile.create(str(cube_path))
    n = 0
    with CubeFile.open(str(cube_path)) as cube:
        for row in iter_dense(dense_path):
            cube.append(
                entry_type=row.get("type") or "belief",
                description=row.get("description") or "",
                data=row.get("data") or {},
                causal_parents=row.get("parents") or [],
                outcome=row.get("outcome") or "none",
            )
            n += 1
    return n
