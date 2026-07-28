"""Hermespace heart / generator bridge — Cube powers Space.

HermesCube is the **heart** of Hermespace (the pocket workbench).
Hermespace owns FOA / dual decode / inject budget; Cube owns the durable
``.cube`` archive and generates dense power when Space asks.

Stable contract (``GENERATOR_API_VERSION``):

  - ``ensure_heart``         — create cube path if missing (bootstrap)
  - ``heart_status``         — readiness + growth + contract version
  - ``build_space_inject``   — FOA strip (wisdom → hubs → query hits)
  - ``seal_learning``        — desk decisions → durable archive (structured)
  - ``seal_to_cube``         — bool wrapper (back-compat with Space 0.18)
  - ``sync_world_beliefs``   — charge Hermespace WorldModel from Cube wisdom
  - ``pulse_charge``         — idle/pulse: refresh journey + world charge
  - ``module_status``        — alias of heart_status (back-compat)

Under high load, Space must not dump the world. It opens this heart and
takes a tiny relevant strip. Soft dependency: Hermespace imports us; Cube
never requires Space. See docs/HERMESPACE.md and PURPOSE.md.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Bump when Hermespace must adapt (additive fields are fine within a major).
GENERATOR_API_VERSION = "1.0"

DEFAULT_HIGH_LOAD_CHARS = 420
DEFAULT_NORMAL_CHARS = 900

# WorldModel-aligned entry types Hermespace can seal into the heart.
SEAL_ENTRY_TYPES = frozenset(
    {"belief", "landmark", "trait", "resolve", "relationship", "focus", "evolution"}
)


def _hermes_home() -> str:
    return os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")


def _cube_path(hermes_home: str | None = None) -> Path:
    return Path(hermes_home or _hermes_home()) / "memories" / "memory.cube"


def is_available() -> bool:
    """True if hermescube package can import."""
    try:
        import hermescube  # noqa: F401

        return True
    except Exception:
        return False


def ensure_heart(hermes_home: str | None = None) -> dict[str, Any]:
    """Ensure the durable cube exists so Space can treat Cube as its heart.

    Creates ``$HERMES_HOME/memories/memory.cube`` if missing. Does not wipe
    an existing archive. Safe to call from Hermespace install / enter / pulse.
    """
    hh = hermes_home or _hermes_home()
    mem = Path(hh) / "memories"
    cube = mem / "memory.cube"
    out: dict[str, Any] = {
        "ok": False,
        "hermes_home": hh,
        "cube_path": str(cube),
        "created": False,
        "api_version": GENERATOR_API_VERSION,
    }
    try:
        mem.mkdir(parents=True, exist_ok=True)
        if not cube.is_file():
            from hermescube.cube import CubeFile

            CubeFile.create(str(cube))
            out["created"] = True
        out["ok"] = cube.is_file()
        out["entries"] = 0
        if cube.is_file():
            from hermescube.cube import CubeFile

            with CubeFile.open(str(cube)) as c:
                out["entries"] = int(c.entry_count or 0)
    except Exception as e:
        out["error"] = str(e)
        logger.debug("ensure_heart failed: %s", e)
    return out


def heart_status(hermes_home: str | None = None) -> dict[str, Any]:
    """Generator readiness for Hermespace doctor / desktop / pulse."""
    hh = hermes_home or _hermes_home()
    cube = _cube_path(hh)
    st: dict[str, Any] = {
        "api_version": GENERATOR_API_VERSION,
        "role": "heart",
        "available": is_available(),
        "hermes_home": hh,
        "cube_exists": cube.is_file(),
        "cube_path": str(cube),
        "heart_ready": False,
        "hermescube_version": None,
    }
    try:
        import hermescube

        st["hermescube_version"] = getattr(hermescube, "__version__", None)
    except Exception:
        pass

    if cube.is_file() and is_available():
        try:
            from hermescube.cube import CubeFile

            with CubeFile.open(str(cube)) as c:
                st["entries"] = int(c.entry_count or 0)
                try:
                    st["density"] = c.density_stats()
                except Exception:
                    pass
            st["heart_ready"] = True
        except Exception as e:
            st["error"] = str(e)

        try:
            from hermescube.genealogy import growth_status

            g = growth_status(hh)
            st["growth"] = {
                "version": g.get("version"),
                "era": g.get("era"),
                "era_label": g.get("era_label"),
                "cycles": (g.get("age") or {}).get("cycles"),
            }
        except Exception:
            pass

    try:
        from hermescube.journey import default_paths, read_events

        jpath, md = default_paths(hh)
        st["journey_events"] = len(read_events(hh, limit=5000))
        st["journey_jsonl"] = str(jpath)
        st["journey_md"] = str(md)
    except Exception:
        pass

    st["surfaces"] = {
        "inject": "build_space_inject",
        "seal": "seal_learning",
        "seal_bool": "seal_to_cube",
        "charge": "sync_world_beliefs",
        "pulse": "pulse_charge",
        "ensure": "ensure_heart",
    }
    return st


def module_status(hermes_home: str | None = None) -> dict[str, Any]:
    """Back-compat alias — prefer ``heart_status``."""
    return heart_status(hermes_home=hermes_home)


def cube_recall(
    query: str,
    *,
    top_k: int = 4,
    hermes_home: str | None = None,
    session_id: str = "hermespace",
) -> list[tuple[str, float]]:
    """Return (description, score) from the user's cube for a FOA query.

    Filters dogfood/test noise so Hermespace inject stays doctrine-grade.
    """
    if not query or not str(query).strip():
        return []
    hh = hermes_home or _hermes_home()
    try:
        from hermescube.provider import CubeMemoryProvider
        from hermescube.journey import is_noise_text

        p = CubeMemoryProvider()
        p.initialize(session_id=session_id, hermes_home=hh, platform="hermespace")
        if not p._engine:
            p.shutdown()
            return []
        hits = p._engine.query(query.strip(), top_k=max(top_k * 3, 12))
        out: list[tuple[str, float]] = []
        for e, s in hits:
            desc = (e.description or "").strip()
            if not desc or is_noise_text(desc):
                continue
            if (e.outcome or "") == "superseded":
                continue
            out.append((desc, float(s)))
            if len(out) >= top_k:
                break
        p.shutdown()
        return out
    except Exception as e:
        logger.debug("cube_recall failed: %s", e)
        return []


def sync_world_beliefs(
    *,
    hermes_home: str | None = None,
    hermespace_home: str | None = None,
    agent_id: str = "hermes-agent",
) -> dict[str, Any]:
    """Push Cube crystals/beliefs into Hermespace World active wisdom."""
    try:
        from hermescube.journey import push_to_hermespace_world

        return push_to_hermespace_world(
            hermes_home=hermes_home,
            hermespace_home=hermespace_home,
            agent_id=agent_id,
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}


def pulse_charge(
    *,
    hermes_home: str | None = None,
    hermespace_home: str | None = None,
    agent_id: str = "hermes-agent",
    ensure: bool = True,
) -> dict[str, Any]:
    """Idle / pulse tick: ensure heart exists, then charge Space world from Cube.

    Hermespace can call this from ``idle_tick`` / pulse jobs so the desk's
    WorldModel Beliefs stay fed by the durable archive.
    """
    report: dict[str, Any] = {
        "api_version": GENERATOR_API_VERSION,
        "ok": False,
        "ensure": None,
        "charge": None,
    }
    if ensure:
        report["ensure"] = ensure_heart(hermes_home=hermes_home)
    report["charge"] = sync_world_beliefs(
        hermes_home=hermes_home,
        hermespace_home=hermespace_home,
        agent_id=agent_id,
    )
    report["ok"] = bool(
        (report["ensure"] or {}).get("ok", True)
        and ((report["charge"] or {}).get("ok") or (report["charge"] or {}).get("wisdom_n", 0) == 0)
    )
    # ok if ensure worked and charge didn't hard-fail
    if report["charge"] and report["charge"].get("error") and not report["charge"].get("ok"):
        # Hermespace missing is soft — still heart-ok
        report["ok"] = bool((report["ensure"] or {}).get("ok", True))
        report["soft"] = "hermespace_unavailable_or_empty"
    return report


def build_space_inject(
    query: str,
    *,
    high_load: bool = False,
    max_chars: int | None = None,
    hermes_home: str | None = None,
    session_id: str = "hermespace",
) -> str:
    """Compact block for Hermespace pre_llm inject (heart → FOA strip).

    High load → smaller strip (dense FOA support).
    Prefer crystal/journey wisdom when query is empty or generic.
    """
    if not is_available():
        return ""
    try:
        from hermescube.journey import is_noise_text
    except Exception:

        def is_noise_text(text: str) -> bool:  # fallback when journey unavailable
            return False

    cap = max_chars
    if cap is None:
        cap = DEFAULT_HIGH_LOAD_CHARS if high_load else DEFAULT_NORMAL_CHARS
    hh = hermes_home or _hermes_home()
    lines = ["### HermesCube (heart)"]
    if high_load:
        lines.append("_High load — heart strip only (warehouse, not full archive)._")
    used = sum(len(x) for x in lines)

    try:
        from hermescube.journey import wisdom_from_cube
        from hermescube.cube import CubeFile

        cube = _cube_path(hh)
        entries_cache = None
        if cube.is_file():
            try:
                with CubeFile.open(str(cube)) as c:
                    entries_cache = list(c.read_l1() or [])
                    w = wisdom_from_cube(entries=entries_cache)
            except Exception:
                w = []
                entries_cache = None
            for desc, conf in w[: 1 if high_load else 4]:
                if is_noise_text(desc):
                    continue
                line = f"- {desc.strip()[:160]}"
                if used + len(line) + 1 > cap:
                    break
                lines.append(line)
                used += len(line) + 1

            if high_load and entries_cache is not None and used < cap - 40:
                try:
                    from hermescube.engram_net import EngramNet, default_path

                    net = EngramNet(default_path(hh))
                    hubs = net.hub_ids(limit=4)
                    if hubs:
                        by_id = {
                            str(e.id): e
                            for e in entries_cache
                            if getattr(e, "id", None)
                        }
                        lines.append("_Animus hubs (engram)_")
                        used += len(lines[-1]) + 1
                        for hid in hubs:
                            e = by_id.get(str(hid))
                            if not e:
                                continue
                            desc = (e.description or "").strip()
                            if not desc or is_noise_text(desc):
                                continue
                            if desc.startswith("[CLOSED]") or desc.startswith(
                                "[PROCEDURE]"
                            ):
                                continue
                            line = f"- {desc[:140]}"
                            if used + len(line) + 1 > cap:
                                break
                            if any(desc[:40] in x for x in lines):
                                continue
                            lines.append(line)
                            used += len(line) + 1
                except Exception:
                    pass
    except Exception:
        pass

    q = (query or "").strip()
    if q and used < cap - 40 and not (high_load and used > cap * 0.55):
        hits = cube_recall(
            q,
            top_k=2 if high_load else 4,
            hermes_home=hermes_home,
            session_id=session_id,
        )
        for desc, score in hits:
            if is_noise_text(desc):
                continue
            line = f"- {desc.strip()[:160]}"
            if used + len(line) + 1 > cap:
                break
            if any(desc[:40] in x for x in lines):
                continue
            lines.append(line)
            used += len(line) + 1

    if len(lines) <= 2:
        return ""
    return "\n".join(lines)


def seal_learning(
    content: str,
    *,
    entry_type: str = "belief",
    hermes_home: str | None = None,
    source: str = "hermespace",
    trust: float = 0.75,
    agent_id: str = "",
    outcome: str = "none",
) -> dict[str, Any]:
    """Write a Hermespace learning/decision into the durable cube (structured).

    Preferred seal API for Space-as-heart. Returns ``{ok, id, entry_type, …}``.
    """
    result: dict[str, Any] = {
        "ok": False,
        "api_version": GENERATOR_API_VERSION,
        "id": None,
        "entry_type": entry_type,
    }
    if not content or not str(content).strip():
        result["error"] = "empty_content"
        return result

    et = (entry_type or "belief").strip().lower()
    if et not in SEAL_ENTRY_TYPES:
        et = "belief"
        result["entry_type"] = et

    hh = hermes_home or _hermes_home()
    ensure = ensure_heart(hermes_home=hh)
    if not ensure.get("ok"):
        result["error"] = ensure.get("error") or "ensure_heart_failed"
        return result

    try:
        from hermescube.cube import CubeFile
        from hermescube.threats import has_blockable_threat, sanitize_for_storage

        text = sanitize_for_storage(str(content).strip()[:500])
        if has_blockable_threat(text):
            result["error"] = "blocked_by_threat_scan"
            return result

        cube = _cube_path(hh)
        data: dict[str, Any] = {
            "source": source,
            "durable": True,
            "trust": float(trust),
            "extension_of": "hermespace",
            "evidence_state": "observed",
            "heart_seal": True,
        }
        if agent_id:
            data["agent_id"] = str(agent_id)[:128]

        with CubeFile.open(str(cube)) as c:
            entry = c.append(
                entry_type=et,
                description=text,
                outcome=outcome if outcome in ("none", "success", "failure", "partial") else "none",
                data=data,
            )
            eid = str(getattr(entry, "id", "") or "")
        result["ok"] = bool(eid)
        result["id"] = eid or None
        result["cube_path"] = str(cube)

        try:
            from hermescube.journey import log_event

            log_event(
                "hermespace_seal",
                text[:200],
                hermes_home=hh,
                meta={"id": eid, "entry_type": et, "source": source},
            )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.debug("seal_learning failed: %s", e)
        result["error"] = str(e)
        return result


def seal_to_cube(
    content: str,
    *,
    entry_type: str = "belief",
    hermes_home: str | None = None,
    source: str = "hermespace",
    trust: float = 0.75,
    **kwargs: Any,
) -> bool:
    """Bool wrapper for Hermespace 0.18 ``cube_seal`` back-compat."""
    rec = seal_learning(
        content,
        entry_type=entry_type,
        hermes_home=hermes_home,
        source=source,
        trust=trust,
        agent_id=str(kwargs.get("agent_id") or ""),
        outcome=str(kwargs.get("outcome") or "none"),
    )
    return bool(rec.get("ok"))
