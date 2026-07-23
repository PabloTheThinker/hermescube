"""Wisdom Crystalizer — episodic noise → active beliefs (original Cube loop).

Research gap (live ILO cube 2026-07-23 + Hermes learning-loop principles):
  - Archive grows landmarks faster than *beliefs* (wisdom)
  - Near-duplicate manages/feedback/firsthand runs dilute rank
  - Hermespace world showed Beliefs: (none) while landmarks spam "session ended"
  - True functional memory needs episodic → semantic consolidation without LLM

This is NOT:
  - L2 k-means evolve (vector topics)
  - Yield Gradient (query payoff)
  - Colony trails (entity graph)

It IS a **lexical consensus crystalizer**:
  1. Tokenize descriptions
  2. Greedy cluster by Jaccard ≥ threshold among wisdom-bearing types
  3. For clusters size ≥ min_n: emit one `belief` crystal with evidence_ids
  4. Soft-supersede weaker members (append outcome=superseded pointers)

Hot path: never. Run on session_end / explicit manage action / doctor --crystalize.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from hermescube.cube import CubeEntry, CubeFile

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "and", "or", "but", "with", "as", "at", "by", "from", "that", "this",
    "it", "its", "we", "you", "they", "i", "me", "my", "our", "your", "do", "does",
    "did", "can", "could", "should", "would", "will", "just", "about", "into",
})

# Types that can crystallize into active wisdom
WISDOM_TYPES = frozenset({
    "belief", "landmark", "trait", "resolve", "relationship", "evolution",
})

# Chitchat / non-durable turn patterns (sync_turn gate)
_CHITCHAT_RE = re.compile(
    r"(?i)^("
    r"ok(ay)?|thanks|thank you|cool|nice|got it|sounds good|yes|no|yep|nah|"
    r"proceed|let'?s go|boom|perfect|good|hi|hey|hello|continue|go ahead|"
    r"confirm(ed)?\.?|sure|alright|all right"
    r")[\s!.]*$"
)
_DURABLE_HINT = re.compile(
    r"(?i)\b("
    r"prefer|always|never|must|path|provider|version|decision|decided|"
    r"remember|use |uses |don'?t|policy|gate|benchmark|client|mission|"
    r"warehouse|memory\.md|hermescube|soT|source of truth|password|token"
    r")\b"
)


def tokens(text: str) -> frozenset[str]:
    out: set[str] = set()
    for t in _TOKEN_RE.findall(text or ""):
        tl = t.lower()
        if len(tl) < 2 or tl in _STOP:
            continue
        out.add(tl)
    return frozenset(out)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    return inter / float(len(a | b))


def is_durable_turn(user: str, assistant: str) -> bool:
    """Gate: skip pure chitchat acks; keep substantive turns (incl. tests/episodes)."""
    u = (user or "").strip()
    a = (assistant or "").strip()
    if not u and not a:
        return False
    # Both sides pure ack → drop
    if u and a and _CHITCHAT_RE.match(u) and _CHITCHAT_RE.match(a):
        return False
    # User ack with empty/near-empty assistant → drop
    if u and _CHITCHAT_RE.match(u) and len(a) < 8:
        return False
    # Lone ultra-short both sides
    if len(u) <= 2 and len(a) <= 2:
        return False
    return True


def _trust(entry: Any) -> float:
    d = entry.data if isinstance(getattr(entry, "data", None), dict) else {}
    t = d.get("trust") if d else None
    if isinstance(t, (int, float)):
        return float(t)
    # source priors
    src = str((d or {}).get("source") or "").lower()
    if src in ("seed", "hermescube_manage", "manage", "extract"):
        return 0.7
    if src in ("sync_turn", "turn"):
        return 0.45
    if getattr(entry, "outcome", "") == "superseded":
        return 0.2
    return 0.5


def _already_crystal(entry: Any) -> bool:
    d = entry.data if isinstance(getattr(entry, "data", None), dict) else {}
    return bool(d and d.get("crystal") is True)


def crystalize(
    cube: "CubeFile",
    *,
    min_cluster: int = 2,
    jaccard_threshold: float = 0.42,
    max_crystals: int = 12,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Consolidate near-duplicate wisdom entries into belief crystals.

    Returns stats. Mutates cube unless dry_run=True.
    """
    entries = list(cube.read_l1() or [])
    candidates: list[Any] = []
    for e in entries:
        et = (e.entry_type or "").lower()
        if et not in WISDOM_TYPES:
            continue
        if (e.outcome or "") == "superseded":
            continue
        if _already_crystal(e):
            continue
        desc = (e.description or "").strip()
        if len(desc) < 12:
            continue
        # skip raw question shells
        if desc.endswith("?"):
            continue
        tok = tokens(desc)
        if len(tok) < 2:
            continue
        candidates.append(e)

    # Greedy clustering
    used: set[str] = set()
    clusters: list[list[Any]] = []
    # sort by trust desc so seeds are strong
    candidates.sort(key=lambda e: -_trust(e))
    for e in candidates:
        if e.id in used:
            continue
        etoks = tokens(e.description or "")
        cluster = [e]
        used.add(e.id)
        for o in candidates:
            if o.id in used:
                continue
            ot = tokens(o.description or "")
            if jaccard(etoks, ot) >= jaccard_threshold:
                cluster.append(o)
                used.add(o.id)
                # expand centroid lightly
                etoks = etoks | ot
        if len(cluster) >= min_cluster:
            clusters.append(cluster)

    clusters.sort(key=lambda c: -len(c))
    crystals_made = 0
    superseded = 0
    crystal_ids: list[str] = []

    for cluster in clusters[:max_crystals]:
        # pick canonical description: highest trust, then longest informative
        cluster.sort(key=lambda e: (-_trust(e), -len(e.description or "")))
        head = cluster[0]
        evidence = [e.id for e in cluster]
        # merge unique token coverage for description
        desc = (head.description or "").strip()[:240]
        # if head is landmark-ish and another is belief, prefer belief text if similar trust
        for e in cluster:
            if e.entry_type == "belief" and _trust(e) >= _trust(head) - 0.05:
                desc = (e.description or desc).strip()[:240]
                break

        avg_trust = sum(_trust(e) for e in cluster) / len(cluster)
        crystal_trust = min(0.95, max(0.72, avg_trust + 0.08 * (len(cluster) - 1)))
        data = {
            "crystal": True,
            "evidence_ids": evidence,
            "cluster_size": len(cluster),
            "source": "wisdom_crystalizer",
            "trust": round(crystal_trust, 3),
            "formed_at": time.time(),
            "member_types": sorted({(e.entry_type or "") for e in cluster}),
        }
        if dry_run:
            crystals_made += 1
            superseded += max(0, len(cluster) - 1)
            continue

        try:
            added = cube.append(
                entry_type="belief",
                description=desc,
                data=data,
                outcome="success",
            )
            crystal_ids.append(added.id)
            crystals_made += 1
            # supersede weaker members (not the chosen head text twin if same id)
            for e in cluster:
                if e.id == head.id:
                    # still mark head as absorbed into crystal
                    pass
                try:
                    cube.append(
                        entry_type=e.entry_type or "belief",
                        description=f"[CRYSTALIZED] {(e.description or '')[:150]}",
                        data={
                            "supersedes": e.id,
                            "crystal_id": added.id,
                            "source": "wisdom_crystalizer",
                            "trust": 0.15,
                        },
                        outcome="superseded",
                    )
                    superseded += 1
                except Exception as ex:
                    logger.debug("supersede failed %s: %s", e.id, ex)
        except Exception as ex:
            logger.warning("crystal append failed: %s", ex)

    return {
        "candidates": len(candidates),
        "clusters": len(clusters),
        "crystals": crystals_made,
        "superseded": superseded,
        "crystal_ids": crystal_ids,
        "dry_run": dry_run,
    }


def active_wisdom(
    entries: list[Any],
    *,
    limit: int = 8,
) -> list[Any]:
    """Select active wisdom entries for prompt/prefetch (crystals first)."""
    scored: list[tuple[float, Any]] = []
    for e in entries:
        if (e.outcome or "") == "superseded":
            continue
        et = (e.entry_type or "").lower()
        if et not in WISDOM_TYPES and et != "belief":
            continue
        d = e.data if isinstance(e.data, dict) else {}
        score = _trust(e)
        if d.get("crystal"):
            score += 0.35 + 0.03 * float(d.get("cluster_size") or 1)
        if et == "belief":
            score += 0.08
        if et == "trait":
            score += 0.05
        scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:limit]]


def functional_loop_stats(entries: list[Any]) -> dict[str, Any]:
    """Metrics for true functional memory health."""
    n = len(entries)
    if n == 0:
        return {"entries": 0, "wisdom_ratio": 0.0, "crystal_count": 0, "dup_pressure": 0.0}
    crystals = sum(
        1
        for e in entries
        if isinstance(e.data, dict) and e.data.get("crystal") and (e.outcome or "") != "superseded"
    )
    beliefs = sum(1 for e in entries if e.entry_type == "belief" and (e.outcome or "") != "superseded")
    landmarks = sum(1 for e in entries if e.entry_type == "landmark" and (e.outcome or "") != "superseded")
    superseded = sum(1 for e in entries if (e.outcome or "") == "superseded")
    # near-dup pressure via identical prefix
    from collections import Counter

    pref = Counter((e.description or "")[:64] for e in entries if (e.outcome or "") != "superseded")
    dups = sum(1 for _, c in pref.items() if c > 1)
    active = max(1, n - superseded)
    return {
        "entries": n,
        "active": active,
        "crystal_count": crystals,
        "belief_count": beliefs,
        "landmark_count": landmarks,
        "superseded": superseded,
        "wisdom_ratio": round(beliefs / active, 3),
        "crystal_ratio": round(crystals / active, 3),
        "dup_pressure": round(dups / active, 3),
        "healthy": bool(
            (crystals > 0 and beliefs >= max(1.0, landmarks * 0.25)) or beliefs >= 5
        ),
    }
