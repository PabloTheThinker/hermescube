"""Prospective memory — focus intents that stay hot until resolve (original).

Research spine (from TG IDEAS_FROM_OPS + cognitive prospective memory):
  - Open goals bias attention until completed
  - Cube already has focus + resolve types; this wires the *loop*
  - Not a second todo app: warehouse-native, rank + prompt surface

Mechanics:
  1) Open focuses = entry_type focus, not superseded, outcome not success
  2) On successful resolve (or manage resolve), match open focus by token overlap
  3) Close match: append supersede marker + link causal_parents
  4) Open focuses get rank boost + strip in system_prompt / prefetch

Hot path: open_focuses() is cheap (L1 scan + filter). Matching is lexical.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)
_STOP = frozenset(
    "the and for with that this from into your our are was were been have has had "
    "not but you they them then than also just about when what who how why will "
    "need needs should must want wants please".split()
)


def _toks(text: str) -> set[str]:
    out: set[str] = set()
    for t in _TOKEN.findall(text or ""):
        tl = t.lower()
        if tl not in _STOP and len(tl) >= 3:
            out.add(tl)
    return out


def is_open_focus(entry: Any) -> bool:
    if (getattr(entry, "entry_type", "") or "").lower() != "focus":
        return False
    if (getattr(entry, "outcome", "") or "").lower() == "superseded":
        return False
    if (getattr(entry, "outcome", "") or "").lower() == "success":
        return False
    data = getattr(entry, "data", None) or {}
    if isinstance(data, dict) and data.get("prospective_closed"):
        return False
    try:
        from hermescube.journey import is_noise_text

        if is_noise_text(getattr(entry, "description", "") or ""):
            return False
    except Exception:
        pass
    return True


def open_focuses(entries: list[Any], *, limit: int = 12) -> list[Any]:
    """Active prospective intents, newest / highest trust first."""
    closed_ids: set[str] = set()
    for e in entries:
        d = getattr(e, "data", None) or {}
        if isinstance(d, dict) and d.get("prospective_closed"):
            fid = d.get("closes_focus_id")
            if fid:
                closed_ids.add(str(fid))
        # [CLOSED] markers also mark themselves
        desc = (getattr(e, "description", "") or "")
        if desc.startswith("[CLOSED]"):
            closed_ids.add(str(getattr(e, "id", "") or ""))

    open_ = [
        e
        for e in entries
        if is_open_focus(e) and str(getattr(e, "id", "")) not in closed_ids
    ]

    def score(e: Any) -> float:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        trust = float(d.get("trust") or 0.55)
        return trust

    open_.sort(key=score, reverse=True)
    open_.sort(key=lambda e: getattr(e, "timestamp", "") or "", reverse=True)
    return open_[:limit]


def match_score(focus_desc: str, resolve_desc: str) -> float:
    """Jaccard on content tokens; 0..1."""
    a, b = _toks(focus_desc), _toks(resolve_desc)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def best_focus_for_resolve(
    focuses: list[Any],
    resolve_desc: str,
    *,
    min_score: float = 0.18,
) -> tuple[Any | None, float]:
    best = None
    best_s = 0.0
    for f in focuses:
        s = match_score(getattr(f, "description", "") or "", resolve_desc)
        if s > best_s:
            best_s = s
            best = f
    if best is None or best_s < min_score:
        return None, best_s
    return best, best_s


def close_focus(
    cube: Any,
    focus: Any,
    *,
    resolve_id: str = "",
    resolve_desc: str = "",
    match: float = 0.0,
) -> Any | None:
    """Append closed marker (append-only cube) linked to resolve."""
    if cube is None or focus is None:
        return None
    desc = (getattr(focus, "description", "") or "").strip()
    try:
        return cube.append(
            entry_type="focus",
            description=f"[CLOSED] {desc[:200]}",
            data={
                "prospective_closed": True,
                "closes_focus_id": getattr(focus, "id", ""),
                "resolve_id": resolve_id,
                "resolve_desc": (resolve_desc or "")[:200],
                "match_score": round(float(match), 4),
                "source": "prospective",
                "trust": 0.7,
            },
            outcome="success",
            causal_parents=[getattr(focus, "id", "")] if getattr(focus, "id", None) else None,
        )
    except TypeError:
        # older cube.append without causal_parents
        return cube.append(
            entry_type="focus",
            description=f"[CLOSED] {desc[:200]}",
            data={
                "prospective_closed": True,
                "closes_focus_id": getattr(focus, "id", ""),
                "resolve_id": resolve_id,
                "resolve_desc": (resolve_desc or "")[:200],
                "match_score": round(float(match), 4),
                "source": "prospective",
                "trust": 0.7,
            },
            outcome="success",
        )
    except Exception as e:
        logger.debug("close_focus failed: %s", e)
        return None


def try_close_on_resolve(
    cube: Any,
    resolve_entry: Any,
    *,
    min_score: float = 0.18,
) -> dict[str, Any]:
    """If resolve looks successful, close best matching open focus."""
    out: dict[str, Any] = {"closed": False, "match": 0.0, "focus_id": None}
    if cube is None or resolve_entry is None:
        return out
    et = (getattr(resolve_entry, "entry_type", "") or "").lower()
    outcome = (getattr(resolve_entry, "outcome", "") or "none").lower()
    desc = (getattr(resolve_entry, "description", "") or "").strip()
    if et not in ("resolve", "evolution", "landmark") and outcome != "success":
        # still allow if description looks like completion
        if not any(
            w in desc.lower()
            for w in ("done", "shipped", "fixed", "completed", "resolved", "deployed")
        ):
            return out
    if outcome not in ("success", "none", ""):
        if outcome not in ("success",):
            # failure resolves don't close focuses
            if outcome in ("failure", "pending"):
                return out
    try:
        entries = list(cube.read_l1() or [])
    except Exception:
        return out
    focuses = open_focuses(entries, limit=24)
    # exclude the resolve itself if typed focus
    focuses = [f for f in focuses if getattr(f, "id", None) != getattr(resolve_entry, "id", None)]
    focus, score = best_focus_for_resolve(focuses, desc, min_score=min_score)
    out["match"] = score
    if focus is None:
        return out
    closed = close_focus(
        cube,
        focus,
        resolve_id=str(getattr(resolve_entry, "id", "") or ""),
        resolve_desc=desc,
        match=score,
    )
    if closed is not None:
        out["closed"] = True
        out["focus_id"] = getattr(focus, "id", None)
        out["closed_id"] = getattr(closed, "id", None)
        try:
            from hermescube.journey import log_event

            log_event(
                "prospective_close",
                f"Closed focus via resolve: {(getattr(focus, 'description') or '')[:100]}",
                entry_id=out.get("closed_id") or "",
                meta={"focus_id": out["focus_id"], "match": score},
            )
        except Exception:
            pass
    return out


def prompt_strip(entries: list[Any], *, limit: int = 4, high_load: bool = False) -> str:
    """Compact open-intent strip for system prompt / inject."""
    n = 2 if high_load else limit
    focuses = open_focuses(entries, limit=n)
    if not focuses:
        return ""
    lines = ["### Open intents (prospective — close with resolve)"]
    for f in focuses:
        d = (getattr(f, "description", "") or "").strip()[:140]
        if d:
            lines.append(f"- {d}")
    return "\n".join(lines)


def rank_boost_for_entry(entry: Any, open_ids: set[str] | None = None) -> float:
    """Multiplier contribution for bio_rank / HAR."""
    if is_open_focus(entry):
        return 1.35
    data = getattr(entry, "data", None) or {}
    if isinstance(data, dict) and data.get("prospective_closed"):
        return 0.92
    if open_ids and getattr(entry, "id", None) in open_ids:
        return 1.35
    return 1.0


def status(entries: list[Any]) -> dict[str, Any]:
    opens = open_focuses(entries, limit=50)
    closed_n = sum(
        1
        for e in entries
        if isinstance(getattr(e, "data", None), dict)
        and e.data.get("prospective_closed")
    )
    return {
        "open": len(opens),
        "closed_markers": closed_n,
        "open_preview": [
            {"id": e.id, "description": (e.description or "")[:100]} for e in opens[:5]
        ],
        "ts": time.time(),
    }
