"""Engram Net — software neural substrate for HermesCube (original).

Research spine (principles, not clones):
  - Hermes/Nous learning loop: closed loop, memory that *pays off*, grow with use
  - Complementary Learning Systems: fast episodes + slow structure
  - Hopfield / modern dense associative memory: pattern completion from partial cue
  - Hebbian co-activation: "fire together → wire together" among retrieved engrams
  - Yield Gradient (sibling): query→entry value; Engram Net: entry↔entry + cue→pattern

This is NOT torch/transformers. It IS a compact local network:
  1) PatternBank — last K multi-entry patterns (vectors + member ids)
  2) CoGraph — sparse Hebbian weights between entry_ids
  3) complete() — one-step association boost map for ranking

Hot path: O(K·d + E_edges) with K small (≤256), d=256.
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

_LOCK = threading.Lock()
_MAX_PATTERNS = 256
_MAX_EDGES = 8000
_MAX_DEGREE = 32


def _cos(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = s1 = s2 = 0.0
    for i in range(len(a)):
        x = float(a[i])
        y = float(b[i])
        dot += x * y
        s1 += x * x
        s2 += y * y
    if s1 <= 1e-12 or s2 <= 1e-12:
        return 0.0
    return dot / math.sqrt(s1 * s2)


def _mean_vec(vecs: list[list[float]]) -> list[float] | None:
    if not vecs:
        return None
    d = len(vecs[0])
    out = [0.0] * d
    n = 0
    for v in vecs:
        if len(v) != d:
            continue
        n += 1
        for i in range(d):
            out[i] += float(v[i])
    if n <= 0:
        return None
    inv = 1.0 / n
    for i in range(d):
        out[i] *= inv
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


def default_path(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "engram_net.json"


class EngramNet:
    """Associative neural field over cube entry ids."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._patterns: list[dict[str, Any]] = []  # {v: list[float], ids: [str], ts}
        self._edges: dict[str, dict[str, float]] = {}  # id -> {id: weight}
        self._dirty = False
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self._patterns = []
            self._edges = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._patterns = list(raw.get("patterns") or [])[-_MAX_PATTERNS:]
            edges = raw.get("edges") or {}
            self._edges = {
                str(k): {str(kk): float(vv) for kk, vv in (v or {}).items()}
                for k, v in edges.items()
                if isinstance(v, dict)
            }
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self._patterns = []
            self._edges = {}

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "v": 1,
            "patterns": self._patterns[-_MAX_PATTERNS:],
            "edges": self._edges,
            "ts": time.time(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False

    # ── learning ──────────────────────────────────────────────────

    def learn_coactivation(
        self,
        entry_ids: Iterable[str],
        vectors: list[list[float]] | None = None,
        *,
        strength: float = 1.0,
    ) -> None:
        """Hebbian: members of one retrieval set wire together; optional pattern."""
        ids = [str(x) for x in entry_ids if x]
        # unique preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        if len(uniq) < 2 and not (vectors and len(vectors) >= 1 and uniq):
            return
        with _LOCK:
            if len(uniq) >= 2:
                w = 0.15 * float(strength)
                for i, a in enumerate(uniq):
                    bucket = self._edges.setdefault(a, {})
                    for b in uniq:
                        if a == b:
                            continue
                        bucket[b] = min(8.0, float(bucket.get(b, 0.0)) + w)
                    # cap degree
                    if len(bucket) > _MAX_DEGREE:
                        top = sorted(bucket.items(), key=lambda kv: -kv[1])[:_MAX_DEGREE]
                        self._edges[a] = dict(top)
                self._prune_edges()
            if vectors:
                mv = _mean_vec(vectors)
                if mv is not None and uniq:
                    self._patterns.append({"v": mv, "ids": uniq[:12], "ts": time.time()})
                    if len(self._patterns) > _MAX_PATTERNS:
                        self._patterns = self._patterns[-_MAX_PATTERNS:]
            self._dirty = True

    def learn_feedback(self, entry_ids: Iterable[str], helpful: bool) -> None:
        """Strengthen or weaken co-edges among a judged set."""
        ids = [str(x) for x in entry_ids if x]
        if len(ids) < 1:
            return
        delta = 0.35 if helpful else -0.25
        with _LOCK:
            if len(ids) == 1:
                # self-trace: mild isolation weight stored as loop skipped; no-op
                self._dirty = True
                return
            for a in ids:
                bucket = self._edges.setdefault(a, {})
                for b in ids:
                    if a == b:
                        continue
                    nw = float(bucket.get(b, 0.0)) + delta
                    if nw <= 0.05:
                        bucket.pop(b, None)
                    else:
                        bucket[b] = min(8.0, nw)
            self._prune_edges()
            self._dirty = True

    def _prune_edges(self) -> None:
        # global edge budget
        total = sum(len(v) for v in self._edges.values())
        if total <= _MAX_EDGES:
            return
        flat: list[tuple[float, str, str]] = []
        for a, bucket in self._edges.items():
            for b, w in bucket.items():
                flat.append((float(w), a, b))
        flat.sort(reverse=True)
        keep = flat[:_MAX_EDGES]
        new_e: dict[str, dict[str, float]] = defaultdict(dict)
        for w, a, b in keep:
            new_e[a][b] = w
        self._edges = dict(new_e)

    # ── retrieval boost ───────────────────────────────────────────

    def association_boosts(
        self,
        query_vec: list[float] | None,
        candidate_ids: list[str],
        *,
        beta: float = 12.0,
    ) -> dict[str, float]:
        """Return multiplicative boosts ~[0.88, 1.42] for candidate ids.

        Fast path: empty net → {} so HAR skips re-rank work.
        """
        if not candidate_ids:
            return {}
        if not self._patterns and not self._edges:
            return {}
        boosts = {str(i): 1.0 for i in candidate_ids}
        idset = set(boosts)

        # 1) Pattern completion — Hopfield-like attention over pattern bank
        if query_vec and self._patterns:
            # pre-norm query once
            qn = math.sqrt(sum(float(x) * float(x) for x in query_vec)) or 1.0
            scores: list[tuple[float, list[str]]] = []
            for pat in self._patterns:
                v = pat.get("v")
                ids = pat.get("ids") or []
                if not isinstance(v, list) or not ids or len(v) != len(query_vec):
                    continue
                # fused cos without extra allocs
                dot = s2 = 0.0
                for i in range(len(query_vec)):
                    y = float(v[i])
                    dot += float(query_vec[i]) * y
                    s2 += y * y
                if s2 <= 1e-12:
                    continue
                c = dot / (qn * math.sqrt(s2))
                if c <= 0.05:
                    continue
                scores.append((c, [str(x) for x in ids]))
            if scores:
                m = max(s for s, _ in scores)
                weights = []
                for s, ids in scores:
                    weights.append((math.exp(beta * (s - m)), ids))
                z = sum(w for w, _ in weights) or 1.0
                mass: dict[str, float] = defaultdict(float)
                for w, ids in weights:
                    p = w / z
                    for i in ids:
                        if i in idset:
                            mass[i] += p
                for i, mval in mass.items():
                    boosts[i] = boosts.get(i, 1.0) * (1.0 + 0.38 * min(1.0, mval * 2.5))

        # 2) Co-graph: if several candidates are mutually wired, raise them
        for i in list(idset):
            bucket = self._edges.get(i) or {}
            if not bucket:
                continue
            link = 0.0
            for j, w in bucket.items():
                if j in idset:
                    link += min(2.0, float(w))
            if link > 0:
                boosts[i] = boosts.get(i, 1.0) * (1.0 + 0.12 * min(3.0, link))

        # clamp
        for i in boosts:
            boosts[i] = max(0.88, min(1.42, float(boosts[i])))
        return boosts

    def stats(self) -> dict[str, Any]:
        return {
            "patterns": len(self._patterns),
            "nodes": len(self._edges),
            "edges": sum(len(v) for v in self._edges.values()),
            "path": str(self.path),
        }

    def hub_ids(self, *, limit: int = 8) -> list[str]:
        """Top associative hubs by weighted degree (Animus FOA under load)."""
        if not self._edges:
            return []
        scored: list[tuple[float, str]] = []
        for nid, bucket in self._edges.items():
            if not bucket:
                continue
            wsum = sum(min(2.0, float(w)) for w in bucket.values())
            scored.append((wsum + 0.15 * len(bucket), str(nid)))
        scored.sort(key=lambda x: -x[0])
        return [i for _, i in scored[: max(1, limit)]]
