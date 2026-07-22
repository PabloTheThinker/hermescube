"""Mirror layer — interconnected cube memory (holographic RE + bio).

Inspiration
-----------
Hermes **holographic** (upstream): FTS5 candidates → Jaccard → HRR → trust;
entity tables; probe/related/reason via bind/unbind on memory banks.

Comparative cognition: elephant social graphs, dolphin cultural skills,
"mirror neuron" style co-activation — when one memory fires, linked ones
resonate.

Cube mapping
------------
- Extract lightweight entities from entry text (no SQLite required).
- Index entity → entry_ids (built per query from L1, or cached on evolve).
- After primary HAR hits, **mirror-expand**: pull co-entity + causal_parent
  neighbors into the result set (infinite-void reflection inside the cube).
- Jaccard token overlap boost (ported idea from holographic FactRetriever).

Hot path stays local — no LLM. Expand only around top seeds.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from hermescube import bio_rank

# Proper-name-ish + quoted + $PATH tokens
_RE_MULTI_CAP = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_RE_SINGLE_CAP = re.compile(r"\b([A-Z][a-z]{2,})\b")
_RE_DOLLAR = re.compile(r"\$[A-Z_][A-Z0-9_]*")
_RE_QUOTE = re.compile(r"[\"']([^\"']{2,40})[\"']")

_STOP_ENT = frozenset({
    "The", "This", "That", "With", "From", "When", "What", "Where", "User",
    "Hermes", "True", "False", "None", "Path", "Prefers", "Short", "Under",
})


def extract_entities(text: str, *, max_entities: int = 12) -> list[str]:
    """Pull entity-like tokens from free text."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        s = raw.strip()
        if len(s) < 2 or s in _STOP_ENT:
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(s)

    for m in _RE_MULTI_CAP.finditer(text):
        _add(m.group(1))
    for m in _RE_DOLLAR.finditer(text):
        _add(m.group(0))
    for m in _RE_QUOTE.finditer(text):
        _add(m.group(1))
    # single caps only if few multi already
    if len(found) < 4:
        for m in _RE_SINGLE_CAP.finditer(text):
            _add(m.group(1))
            if len(found) >= max_entities:
                break
    # lowercase multiword from bio tokens that look like names/ids
    for tok in bio_rank.tokenize(text):
        if tok in ("hermes_home", "memory_cube", "mission_zero", "founding_five"):
            _add(tok)
    return found[:max_entities]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return inter / len(a | b)


def build_entity_index(entries: Iterable[Any]) -> dict[str, list[Any]]:
    """entity_lower → list of entries mentioning it."""
    idx: dict[str, list[Any]] = defaultdict(list)
    for e in entries:
        desc = getattr(e, "description", "") or ""
        ents = extract_entities(desc)
        # also from data.entities if present
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict):
            extra = data.get("entities") or []
            if isinstance(extra, list):
                ents = list(ents) + [str(x) for x in extra]
        for ent in ents:
            idx[ent.lower()].append(e)
        # stash for later expand
        try:
            if isinstance(data, dict):
                data = dict(data)
                data.setdefault("entities", ents)
                e.data = data  # type: ignore[attr-defined]
        except Exception:
            pass
    return idx


def entry_id(e: Any) -> str:
    return str(getattr(e, "id", "") or id(e))


def mirror_expand(
    seeds: list[tuple[Any, float]],
    all_entries: list[Any],
    *,
    top_k: int = 5,
    entity_index: dict[str, list[Any]] | None = None,
) -> list[tuple[Any, float]]:
    """Given primary hits, pull mirrored neighbors (shared entities / parents).

    Returns up to top_k (entry, score) with seeds first, then resonated.
    Resonated scores are discounted (mirror echo, not primary).
    """
    if not seeds:
        return []
    if entity_index is None:
        entity_index = build_entity_index(all_entries)

    by_id = {entry_id(e): e for e in all_entries}
    picked: list[tuple[Any, float]] = []
    seen: set[str] = set()

    def _take(e: Any, score: float) -> None:
        eid = entry_id(e)
        if not eid or eid in seen:
            return
        seen.add(eid)
        picked.append((e, score))

    for e, sc in seeds:
        _take(e, sc)
        if len(picked) >= top_k:
            return picked[:top_k]

    # Mirror pass: co-entity + causal parents
    for e, sc in list(seeds):
        data = getattr(e, "data", None) or {}
        ents = []
        if isinstance(data, dict):
            ents = list(data.get("entities") or [])
        if not ents:
            ents = extract_entities(getattr(e, "description", "") or "")
        for ent in ents:
            for neigh in entity_index.get(str(ent).lower(), []):
                if entry_id(neigh) in seen:
                    continue
                # resonance score
                echo = float(sc) * 0.72 * (1.0 + 0.1 * min(3, len(ents)))
                _take(neigh, echo)
                if len(picked) >= top_k:
                    return picked[:top_k]
        for pid in getattr(e, "causal_parents", None) or []:
            parent = by_id.get(str(pid))
            if parent is not None:
                _take(parent, float(sc) * 0.8)
                if len(picked) >= top_k:
                    return picked[:top_k]

    # Fill remaining from unused high-score seeds already handled
    return picked[:top_k]


def annotate_entities_on_append(description: str, data: dict | None) -> dict:
    """Attach entities list into entry data at write time."""
    d = dict(data or {})
    ents = extract_entities(description)
    if ents:
        d["entities"] = ents
    return d
