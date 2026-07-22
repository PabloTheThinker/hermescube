"""Hermespace integration — Cube as Space's deep-memory module.

Problem Hermespace solves poorly alone under high load:
  large inject (world, fabric, episodes) → context bloat → monotropic collapse.

Cube role:
  Keep the long tail offline in .cube; on FOA turns inject only a **tiny**
  relevant strip from hyper-recall. Space stays the desk/FOA; Cube is the
  warehouse module Space opens when it needs facts without the bulk.

Optional dependency: Hermespace imports this; Cube never requires Space.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HIGH_LOAD_CHARS = 420
DEFAULT_NORMAL_CHARS = 900


def _hermes_home() -> str:
    return os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")


def is_available() -> bool:
    """True if hermescube package + user cube path can load."""
    try:
        import hermescube  # noqa: F401
        return True
    except Exception:
        return False


def cube_recall(
    query: str,
    *,
    top_k: int = 4,
    hermes_home: str | None = None,
    session_id: str = "hermespace",
) -> list[tuple[str, float]]:
    """Return (description, score) from the user's cube for a FOA query."""
    if not query or not str(query).strip():
        return []
    hh = hermes_home or _hermes_home()
    try:
        from hermescube.provider import CubeMemoryProvider

        p = CubeMemoryProvider()
        p.initialize(session_id=session_id, hermes_home=hh, platform="hermespace")
        if not p._engine:
            p.shutdown()
            return []
        hits = p._engine.query(query.strip(), top_k=top_k)
        out = [(e.description or "", float(s)) for e, s in hits if e.description]
        p.shutdown()
        return out
    except Exception as e:
        logger.debug("cube_recall failed: %s", e)
        return []


def build_space_inject(
    query: str,
    *,
    high_load: bool = False,
    max_chars: int | None = None,
    hermes_home: str | None = None,
    session_id: str = "hermespace",
) -> str:
    """Compact block for Hermespace pre_llm inject.

    High load → smaller strip (dense FOA support).
    Normal → slightly larger warehouse peek.
    """
    if not is_available():
        return ""
    cap = max_chars
    if cap is None:
        cap = DEFAULT_HIGH_LOAD_CHARS if high_load else DEFAULT_NORMAL_CHARS
    hits = cube_recall(
        query, top_k=3 if high_load else 5, hermes_home=hermes_home, session_id=session_id
    )
    if not hits:
        return ""
    lines = ["### HermesCube (deep memory module)"]
    if high_load:
        lines.append("_High load — cube strip only (warehouse, not full archive)._")
    used = sum(len(x) for x in lines)
    for desc, score in hits:
        line = f"- {desc.strip()[:180]}"
        if used + len(line) + 1 > cap:
            break
        lines.append(line)
        used += len(line) + 1
    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def seal_to_cube(
    content: str,
    *,
    entry_type: str = "belief",
    hermes_home: str | None = None,
    source: str = "hermespace",
    trust: float = 0.75,
) -> bool:
    """Write a Hermespace learning/decision into the user cube (durable)."""
    if not content or not content.strip():
        return False
    hh = hermes_home or _hermes_home()
    try:
        from hermescube.provider import CubeMemoryProvider

        p = CubeMemoryProvider()
        p.initialize(session_id="hermespace-seal", hermes_home=hh, platform="hermespace")
        if not p._cube:
            p.shutdown()
            return False
        p._cube.append(
            entry_type=entry_type,
            description=content.strip()[:500],
            data={
                "source": source,
                "durable": True,
                "trust": trust,
                "extension_of": "hermespace",
            },
        )
        if p._engine:
            p._engine.invalidate_cache()
        p.shutdown()
        return True
    except Exception as e:
        logger.debug("seal_to_cube failed: %s", e)
        return False


def module_status(hermes_home: str | None = None) -> dict[str, Any]:
    hh = hermes_home or _hermes_home()
    cube = Path(hh) / "memories" / "memory.cube"
    st: dict[str, Any] = {
        "available": is_available(),
        "hermes_home": hh,
        "cube_exists": cube.is_file(),
        "cube_path": str(cube),
    }
    if cube.is_file() and is_available():
        try:
            from hermescube.cube import CubeFile

            with CubeFile.open(str(cube)) as c:
                st["entries"] = c.entry_count
                st["density"] = c.density_stats()
        except Exception as e:
            st["error"] = str(e)
    return st
