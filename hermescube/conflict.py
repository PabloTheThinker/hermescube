"""Soft contradiction detection (Holo-inspired, original, no LLM).

When a new belief/resolve lexically opposes an existing high-trust belief
(negation cues + shared content tokens), mark both with conflict_with ids.
Does not delete — operator resolves via feedback/hygiene.
"""

from __future__ import annotations

import re
from typing import Any

_NEG = re.compile(
    r"(?i)\b(not|never|no longer|don't|dont|isn't|isnt|won't|wont|instead of|rather than)\b"
)
_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)
_STOP = frozenset(
    "the and for with that this from into not never rather than instead".split()
)


def _toks(t: str) -> set[str]:
    return {
        x.lower()
        for x in _TOKEN.findall(t or "")
        if x.lower() not in _STOP and len(x) >= 3
    }


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def find_conflicts(
    new_text: str,
    entries: list[Any],
    *,
    min_overlap: float = 0.28,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return list of {id, description, score} that may contradict new_text."""
    nt = (new_text or "").strip()
    if len(nt) < 12:
        return []
    ntoks = _toks(nt)
    neg_new = bool(_NEG.search(nt))
    hits: list[tuple[float, Any]] = []
    for e in entries:
        et = (getattr(e, "entry_type", "") or "").lower()
        if et not in ("belief", "trait", "resolve", "relationship"):
            continue
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        d = (getattr(e, "description", "") or "").strip()
        if not d or d.startswith("["):
            continue
        otoks = _toks(d)
        ov = jaccard(ntoks, otoks)
        if ov < min_overlap:
            continue
        neg_old = bool(_NEG.search(d))
        # conflict if one side negated and content overlaps, or high overlap + opposite polarity words
        if neg_new != neg_old and ov >= min_overlap:
            hits.append((ov + 0.15, e))
        elif ov >= 0.55 and neg_new and neg_old:
            # both negative — not necessarily conflict
            continue
        elif ov >= 0.62:
            # near-duplicate — skip (hygiene handles)
            continue
    hits.sort(key=lambda x: -x[0])
    out = []
    for score, e in hits[:limit]:
        out.append(
            {
                "id": getattr(e, "id", None),
                "description": (getattr(e, "description", "") or "")[:120],
                "score": round(score, 3),
            }
        )
    return out


def annotate_conflicts(cube: Any, new_entry: Any, conflicts: list[dict[str, Any]]) -> int:
    """Append soft conflict markers (append-only). Returns markers written."""
    if not conflicts or cube is None or new_entry is None:
        return 0
    n = 0
    nid = str(getattr(new_entry, "id", "") or "")
    for c in conflicts:
        cid = str(c.get("id") or "")
        if not cid or cid == nid:
            continue
        try:
            cube.append(
                entry_type="belief",
                description=f"[CONFLICT] {nid[:8]}↔{cid[:8]}: {(c.get('description') or '')[:100]}",
                data={
                    "conflict": True,
                    "conflict_with": [nid, cid],
                    "source": "conflict_detect",
                    "trust": 0.4,
                },
                outcome="pending",
            )
            n += 1
        except Exception:
            pass
    return n
