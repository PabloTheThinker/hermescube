"""Surface filter — what is allowed into prefetch / query / evidence.

Cuts friction: superseded junk, DOT spam, test handoffs, crystalized conflicts
should not clog the agent's working context.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from hermescube.journey import is_noise_text

_SURFACE_NOISE = re.compile(
    r"(?i)("
    r"^\[DOT\]|"
    r"^\[HANDOFF (OPEN|COMPLETED|ABANDONED)\]|"
    r"^\[ENTITY\]|"
    r"^\[HYGIENE\]|"
    r"^\[CONFLICT\]|"
    r"REAL-TEST-|HOLD-LINE-WHOLE|HOLD-LINE-WHOLE-CUBE|"
    r"Bench gates: durable hit|"
    r"numeric [0-9a-f]+↔|"
    r"PERSIST-PROOF|"
    r"superseded by "
    r")"
)

# Prefer these types when scores are close (doctrine over debris)
_TYPE_BOOST = {
    "resolve": 0.15,
    "belief": 0.10,
    "trait": 0.08,
    "focus": 0.05,
    "relationship": -0.05,  # often DOT noise
    "landmark": -0.02,
}


def should_surface_entry(entry: Any) -> bool:
    """False = hide from agent-facing recall."""
    if entry is None:
        return False
    outcome = (getattr(entry, "outcome", None) or "").lower()
    if outcome == "superseded":
        return False
    desc = (getattr(entry, "description", None) or "").strip()
    if not desc:
        return False
    if is_noise_text(desc):
        return False
    if _SURFACE_NOISE.search(desc):
        return False
    data = getattr(entry, "data", None) or {}
    if isinstance(data, dict):
        if data.get("supersedes") and outcome in ("superseded", "none"):
            # hygiene markers
            if desc.startswith("[HYGIENE]"):
                return False
        trust = data.get("trust")
        try:
            if trust is not None and float(trust) < 0.25:
                return False
        except (TypeError, ValueError):
            pass
        if data.get("source") in ("journey_hygiene", "dogfood", "test"):
            return False
    return True


def rank_key(item: tuple[Any, float]) -> float:
    entry, score = item
    et = (getattr(entry, "entry_type", None) or "").lower()
    return float(score) + float(_TYPE_BOOST.get(et, 0.0))


def filter_scored(
    results: Iterable[tuple[Any, float]],
    *,
    top_k: int | None = None,
    re_rank: bool = True,
) -> list[tuple[Any, float]]:
    kept: list[tuple[Any, float]] = []
    for entry, score in results:
        if not should_surface_entry(entry):
            continue
        kept.append((entry, score))
    if re_rank:
        kept.sort(key=rank_key, reverse=True)
    if top_k is not None:
        kept = kept[: max(0, int(top_k))]
    return kept
