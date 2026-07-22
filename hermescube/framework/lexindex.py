"""Lightweight inverted index for holo-class candidate generation (Cube-native)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from hermescube import bio_rank


class LexIndex:
    """token → entry ids. Built from L1; used to shrink scan candidate sets."""

    def __init__(self) -> None:
        self._inv: dict[str, set[str]] = defaultdict(set)
        self._n = 0

    def clear(self) -> None:
        self._inv.clear()
        self._n = 0

    def build(self, entries: Iterable[Any]) -> None:
        self.clear()
        for e in entries:
            eid = str(getattr(e, "id", "") or "")
            if not eid:
                continue
            text = f"{getattr(e, 'entry_type', '')} {getattr(e, 'description', '')}"
            data = getattr(e, "data", None) or {}
            if isinstance(data, dict):
                ents = data.get("entities") or []
                if isinstance(ents, list):
                    text += " " + " ".join(str(x) for x in ents)
            for tok in bio_rank.tokenize(text):
                self._inv[tok].add(eid)
            self._n += 1

    @property
    def entry_count(self) -> int:
        return self._n

    def candidate_ids(self, query: str, *, limit: int = 80) -> list[str] | None:
        """Return ranked candidate ids or None if query has no index tokens."""
        toks = bio_rank.tokenize(query)
        if not toks:
            return None
        scores: dict[str, int] = defaultdict(int)
        for t in toks:
            for eid in self._inv.get(t, ()):
                scores[eid] += 1
        if not scores:
            return []
        ranked = sorted(scores.keys(), key=lambda i: (-scores[i], i))
        return ranked[:limit]
