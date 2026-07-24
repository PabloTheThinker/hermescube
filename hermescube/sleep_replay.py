"""Sleep replay — offline consolidation for Engram Net + cube (original).

CLS-inspired: fast episodes land all day; slow structure is taught offline
without LLM cost. Principles from mammalian sleep replay + our Care/day-to-day
continuity work (memories that must not die after week one).

What it does:
  1) Pull recent high-value entries (success resolves, beliefs, landmarks)
  2) Form multi-member patterns (co-topic bundles) → Engram pattern bank
  3) Mild edge decay on stale weak links (forgetting as feature)
  4) Optional: return stats for doctor / cron

Hot path never calls this. Wire via:
  hermescube_manage action=replay
  or cron: hermescube replay
"""

from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)
_STOP = frozenset(
    "the and for with that this from into your our are was were been have has had "
    "not but you they them then than also just about when what who how why".split()
)


def _toks(text: str) -> set[str]:
    out = set()
    for t in _TOKEN.findall(text or ""):
        tl = t.lower()
        if tl not in _STOP:
            out.add(tl)
    return out


def _entry_vec(entry: Any) -> list[float] | None:
    v = getattr(entry, "vector", None)
    if v is None:
        return None
    try:
        return [float(x) for x in list(v)]
    except Exception:
        return None


def sleep_replay(
    cube: Any,
    engram: Any,
    *,
    max_patterns: int = 24,
    edge_decay: float = 0.97,
    min_bundle: int = 2,
) -> dict[str, Any]:
    """Offline consolidation pass. Mutates engram; caller saves."""
    stats: dict[str, Any] = {
        "entries_scanned": 0,
        "bundles": 0,
        "patterns_added": 0,
        "edges_decayed": 0,
        "skipped": False,
    }
    if cube is None or engram is None:
        stats["skipped"] = True
        return stats

    # Collect candidates
    try:
        entries = list(cube.read_l1()) if hasattr(cube, "read_l1") else []
    except Exception:
        entries = []
    if not entries and hasattr(cube, "iter_entries"):
        try:
            entries = list(cube.iter_entries())
        except Exception:
            entries = []

    # Fallback: engine cache style
    if not entries:
        stats["skipped"] = True
        stats["reason"] = "no_entries"
        return stats

    stats["entries_scanned"] = len(entries)
    # Prefer durable / high-signal types (Care continuity bias)
    prefer = {
        "belief": 3.0,
        "resolve": 2.5,
        "landmark": 2.0,
        "trait": 2.5,
        "relationship": 2.0,
        "evolution": 2.2,
        "focus": 1.2,
    }
    scored: list[tuple[float, Any]] = []
    now = time.time()
    for e in entries:
        et = (getattr(e, "entry_type", None) or "").lower()
        if et in ("enter", "leave", "epoch_transition"):
            continue
        oc = (getattr(e, "outcome", None) or "none").lower()
        if oc == "superseded":
            continue
        base = prefer.get(et, 1.0)
        if oc == "success":
            base *= 1.15
        if oc == "failure":
            base *= 1.1  # lessons stick
        desc = getattr(e, "description", "") or ""
        if len(desc) < 12:
            continue
        # recency mild
        ts = getattr(e, "timestamp", "") or ""
        # keep simple — no parse fail
        scored.append((base, e))

    scored.sort(key=lambda x: -x[0])
    top = [e for _, e in scored[: min(200, len(scored))]]

    # Bundle by shared tokens (schema formation)
    buckets: dict[str, list[Any]] = defaultdict(list)
    for e in top:
        toks = sorted(_toks(getattr(e, "description", "") or ""))[:6]
        if not toks:
            continue
        # key = top 2 tokens
        key = "|".join(toks[:2])
        buckets[key].append(e)

    added = 0
    for key, group in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        if len(group) < min_bundle:
            continue
        if added >= max_patterns:
            break
        ids = []
        vecs = []
        for e in group[:8]:
            eid = str(getattr(e, "id", "") or "")
            if not eid:
                continue
            ids.append(eid)
            v = _entry_vec(e)
            if v:
                vecs.append(v)
        if len(ids) < min_bundle:
            continue
        engram.learn_coactivation(ids, vecs if len(vecs) >= 2 else None, strength=1.1)
        added += 1
        stats["bundles"] += 1
    stats["patterns_added"] = added

    # Edge decay (forgetting weak noise)
    decayed = 0
    try:
        edges = getattr(engram, "_edges", None) or {}
        for a, bucket in list(edges.items()):
            for b, w in list(bucket.items()):
                nw = float(w) * float(edge_decay)
                if nw < 0.08:
                    bucket.pop(b, None)
                    decayed += 1
                else:
                    bucket[b] = nw
        if decayed:
            engram._dirty = True
    except Exception:
        pass
    stats["edges_decayed"] = decayed
    stats["engram"] = engram.stats() if hasattr(engram, "stats") else {}
    return stats
