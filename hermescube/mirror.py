"""Mirror layer — interconnected cube memory (infinite void co-activation).

Cube-native interconnect (not a port of upstream holographic):
- Entity extract (hygiene-first)
- Entity → entry index
- mirror_expand: co-entity + causal parents + optional colony trail boost

Hot path stays local — no LLM.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

from hermescube import bio_rank

_RE_MULTI_CAP = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
_RE_DOLLAR = re.compile(r"\$[A-Z_][A-Z0-9_]*(?:/[A-Za-z0-9_./-]+)?")
_RE_QUOTE = re.compile(r"[\"']([^\"']{2,40})[\"']")
_RE_EQUALS_NAME = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3})\s*="
)

# Never promote these as entities (noise that broke colony trails)
_STOP_ENT = frozenset({
    "the", "this", "that", "with", "from", "when", "what", "where", "who",
    "user", "hermes", "true", "false", "none", "path", "prefers", "short",
    "under", "after", "before", "until", "client", "cash", "primary",
    "human", "for", "and", "mission", "zero", "collect", "board", "exit",
    "pay", "verified", "offers", "dollars", "packages", "general", "memory",
    "system", "agent", "entry", "type", "file", "home", "open", "done",
    "fixed", "error", "failed", "using", "into", "over", "only", "also",
})

# Known multiword concepts (bee landmarks)
_CANON_PHRASES = (
    ("mission zero", "Mission Zero"),
    ("founding five", "Founding Five"),
    ("hermes home", "HERMES_HOME"),
    ("memory cube", "memory.cube"),
    ("ship gate", "ship gate"),
    ("query rewrite", "query rewrite"),
)


def extract_entities(text: str, *, max_entities: int = 8) -> list[str]:
    """High-precision entity tokens — multiword / $-vars preferred.

    Drops bare single-word caps that polluted trails (Zero, Mission, Halsted-alone
    only if multi already present is OK for real surnames when part of multi).
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        s = " ".join(raw.strip().split())
        if len(s) < 2:
            return
        key = s.lower()
        if key in _STOP_ENT or key in seen:
            return
        # reject single-token stop-ish or too short generic
        parts = key.split()
        if len(parts) == 1:
            if key in _STOP_ENT or len(key) < 4:
                return
            # single token only if looks like proper name or $ENV or known phrase id
            if not (s[:1].isupper() or s.startswith("$") or "_" in s or "." in s):
                return
        seen.add(key)
        found.append(s)

    low = text.lower()
    for phrase, label in _CANON_PHRASES:
        if phrase in low or phrase.replace(" ", "_") in low:
            _add(label)

    for m in _RE_EQUALS_NAME.finditer(text):
        _add(m.group(1))
    for m in _RE_MULTI_CAP.finditer(text):
        _add(m.group(1))
    for m in _RE_DOLLAR.finditer(text):
        _add(m.group(0).split("/")[0])  # $HERMES_HOME from longer path
    for m in _RE_QUOTE.finditer(text):
        _add(m.group(1))

    # bio tokens
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
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict):
            extra = data.get("entities") or []
            if isinstance(extra, list):
                # re-filter stored entities through hygiene
                for x in extra:
                    for cleaned in extract_entities(str(x)):
                        if cleaned not in ents:
                            ents.append(cleaned)
        for ent in ents:
            idx[ent.lower()].append(e)
        try:
            if isinstance(data, dict):
                data = dict(data)
                data["entities"] = ents
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
    colony: Any = None,
) -> list[tuple[Any, float]]:
    """Primary hits + co-entity / parent / trail-boosted neighbors."""
    if not seeds:
        return []
    if entity_index is None:
        entity_index = build_entity_index(all_entries)

    by_id = {entry_id(e): e for e in all_entries}
    picked: list[tuple[Any, float]] = []
    seen: set[str] = set()

    def _ents(e: Any) -> list[str]:
        data = getattr(e, "data", None) or {}
        if isinstance(data, dict) and data.get("entities"):
            return [str(x) for x in data["entities"]]
        return extract_entities(getattr(e, "description", "") or "")

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

    for e, sc in list(seeds):
        ents = _ents(e)
        for ent in ents:
            for neigh in entity_index.get(str(ent).lower(), []):
                if entry_id(neigh) in seen:
                    continue
                echo = float(sc) * 0.72
                if colony is not None:
                    try:
                        echo *= float(colony.trail_boost(ents, _ents(neigh)))
                    except Exception:
                        pass
                _take(neigh, echo)
                if len(picked) >= top_k:
                    return picked[:top_k]
        for pid in getattr(e, "causal_parents", None) or []:
            parent = by_id.get(str(pid))
            if parent is not None:
                _take(parent, float(sc) * 0.8)
                if len(picked) >= top_k:
                    return picked[:top_k]

    return picked[:top_k]


def annotate_entities_on_append(description: str, data: dict | None) -> dict:
    """Attach cleaned entities list into entry data at write time."""
    d = dict(data or {})
    ents = extract_entities(description)
    if ents:
        d["entities"] = ents
    elif "entities" in d:
        # re-clean legacy
        d["entities"] = extract_entities(" ".join(str(x) for x in d.get("entities") or []))
    return d
