"""Soft contradiction detection (Holo-inspired, original, no LLM).

When a new belief/resolve lexically opposes an existing high-trust belief
(negation cues + shared content tokens), mark both with conflict_with ids.

Also: numeric / count contradiction pass (AgentDrive witness idea, Cube-native)
— same subject tokens with disagreeing integers soft-flag before crystalize.
Does not delete — operator resolves via feedback/hygiene.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

_NEG = re.compile(
    r"(?i)\b(not|never|no longer|don't|dont|isn't|isnt|won't|wont|instead of|rather than)\b"
)
_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)
_NUM = re.compile(r"(?<![A-Za-z0-9./])(\d{1,7})(?![A-Za-z0-9./])")
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


def extract_numeric_claims(text: str) -> list[tuple[frozenset[str], int]]:
    """Pull (subject-token-set, count) pairs from a memory description.

    Years and lone tiny indices are skipped. Subject keys are content tokens
    with digit-only tokens removed — enough to pair "AuthService has 3 replicas"
    against "AuthService has 5 replicas".
    """
    t = (text or "").strip()
    if len(t) < 8:
        return []
    toks = _toks(t)
    subject = frozenset(x for x in toks if not x.isdigit())
    if len(subject) < 2:
        return []
    out: list[tuple[frozenset[str], int]] = []
    seen_n: set[int] = set()
    for m in _NUM.finditer(t):
        n = int(m.group(1))
        if n in seen_n:
            continue
        # skip year-like and zero
        if n == 0 or 1900 <= n <= 2100:
            continue
        # skip very large IDs / timestamps
        if n >= 10_000_000:
            continue
        seen_n.add(n)
        out.append((subject, n))
    return out


def find_numeric_conflicts(
    entries: list[Any],
    *,
    min_key_overlap: float = 0.55,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Find pairs of memories that share a subject but disagree on a count.

    Returns soft conflict dicts compatible with ``annotate_conflicts``
    (each item is one side; callers pair via ``conflict_with``).
    Prefer using ``scan_numeric_conflict_pairs`` for structured pairs.
    """
    pairs = scan_numeric_conflict_pairs(
        entries, min_key_overlap=min_key_overlap, limit=limit
    )
    # Flatten to "conflicts against first of each pair" style for annotate
    out: list[dict[str, Any]] = []
    for p in pairs:
        out.append(
            {
                "id": p["b_id"],
                "description": p["b_description"],
                "score": p["score"],
                "kind": "numeric",
                "counts": [p["a_count"], p["b_count"]],
                "a_id": p["a_id"],
            }
        )
    return out


def scan_numeric_conflict_pairs(
    entries: list[Any],
    *,
    min_key_overlap: float = 0.55,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Return up to ``limit`` numeric contradiction pairs before crystalize."""
    claims: list[tuple[Any, frozenset[str], int, str]] = []
    for e in entries:
        et = (getattr(e, "entry_type", "") or "").lower()
        if et not in ("belief", "trait", "resolve", "relationship", "landmark"):
            continue
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        d = (getattr(e, "description", "") or "").strip()
        if not d or d.startswith("["):
            continue
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict) and data.get("conflict"):
            continue
        for subject, n in extract_numeric_claims(d):
            claims.append((e, subject, n, d))

    # Bucket by a coarse stem (sorted token prefix) to avoid O(n²) on huge L1
    buckets: dict[str, list[tuple[Any, frozenset[str], int, str]]] = defaultdict(list)
    for row in claims:
        stem = "|".join(sorted(row[1])[:4])
        buckets[stem].append(row)

    pairs: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for bucket in buckets.values():
        if len(bucket) < 2:
            # also cross-check near stems via pairwise within expanded set
            pass
        for i in range(len(bucket)):
            e1, s1, n1, d1 = bucket[i]
            for j in range(i + 1, len(bucket)):
                e2, s2, n2, d2 = bucket[j]
                if n1 == n2:
                    continue
                ov = jaccard(set(s1), set(s2))
                if ov < min_key_overlap:
                    continue
                id1 = str(getattr(e1, "id", "") or "")
                id2 = str(getattr(e2, "id", "") or "")
                if not id1 or not id2 or id1 == id2:
                    continue
                key = tuple(sorted((id1, id2)))
                if key in seen:
                    continue
                seen.add(key)
                pairs.append(
                    {
                        "a_id": id1,
                        "b_id": id2,
                        "a_count": n1,
                        "b_count": n2,
                        "a_description": d1[:120],
                        "b_description": d2[:120],
                        "score": round(ov + 0.2, 3),
                        "kind": "numeric",
                    }
                )
                if len(pairs) >= limit:
                    return pairs

    # Cross-bucket pass for near-keys (smaller claim sets only)
    if len(pairs) < limit and len(claims) <= 400:
        for i in range(len(claims)):
            e1, s1, n1, d1 = claims[i]
            for j in range(i + 1, len(claims)):
                e2, s2, n2, d2 = claims[j]
                if n1 == n2:
                    continue
                ov = jaccard(set(s1), set(s2))
                if ov < min_key_overlap:
                    continue
                id1 = str(getattr(e1, "id", "") or "")
                id2 = str(getattr(e2, "id", "") or "")
                key = tuple(sorted((id1, id2)))
                if not id1 or not id2 or id1 == id2 or key in seen:
                    continue
                seen.add(key)
                pairs.append(
                    {
                        "a_id": id1,
                        "b_id": id2,
                        "a_count": n1,
                        "b_count": n2,
                        "a_description": d1[:120],
                        "b_description": d2[:120],
                        "score": round(ov + 0.2, 3),
                        "kind": "numeric",
                    }
                )
                if len(pairs) >= limit:
                    return pairs
    return pairs


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
        kind = str(c.get("kind") or "lexical")
        counts = c.get("counts")
        count_bit = ""
        if isinstance(counts, (list, tuple)) and len(counts) >= 2:
            count_bit = f" counts={counts[0]}≠{counts[1]}"
        try:
            cube.append(
                entry_type="belief",
                description=(
                    f"[CONFLICT] {nid[:8]}↔{cid[:8]}{count_bit}: "
                    f"{(c.get('description') or '')[:100]}"
                ),
                data={
                    "conflict": True,
                    "conflict_kind": kind,
                    "conflict_with": [nid, cid],
                    "source": "conflict_detect",
                    "trust": 0.4,
                    **({"counts": list(counts)} if counts else {}),
                },
                outcome="pending",
            )
            n += 1
        except Exception:
            pass
    return n


def annotate_numeric_pairs(cube: Any, pairs: list[dict[str, Any]]) -> int:
    """Append soft markers for numeric conflict pairs (no single 'new' entry)."""
    if not pairs or cube is None:
        return 0
    n = 0
    for p in pairs:
        a = str(p.get("a_id") or "")
        b = str(p.get("b_id") or "")
        if not a or not b:
            continue
        try:
            cube.append(
                entry_type="belief",
                description=(
                    f"[CONFLICT] numeric {a[:8]}↔{b[:8]} "
                    f"counts={p.get('a_count')}≠{p.get('b_count')}: "
                    f"{(p.get('a_description') or '')[:80]}"
                ),
                data={
                    "conflict": True,
                    "conflict_kind": "numeric",
                    "conflict_with": [a, b],
                    "counts": [p.get("a_count"), p.get("b_count")],
                    "source": "numeric_conflict",
                    "trust": 0.4,
                },
                outcome="pending",
            )
            n += 1
        except Exception:
            pass
    return n
