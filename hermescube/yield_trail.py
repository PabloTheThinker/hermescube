"""Yield Gradient — query-conditioned payoff memory (original Cube mechanism).

Research spine (Nous / Teknium Hermes learning loop — principles, not code):
  - Agent grows by *using* what it stored (closed loop, not dump-only memory)
  - Nudges + feedback train what is worth keeping
  - Hot path stays cheap; learning is incremental

This module is NOT:
  - colony pheromone (entity↔entity stigmergy)
  - global trust alone
  - LLM re-rank / mem0-style cloud

It IS a local **value-of-information** surface:
  For similar *queries*, which entry_ids historically paid off
  (helpful feedback, success outcomes)? Rank boost is query-local.

Storage: tiny JSON under $HERMES_HOME/memories/yield_gradient.json
  buckets: hash(query_tokens) → {entry_id: {y, n, last_ts}}
  y = helpful/success count, n = unhelpful count
  score = (y - 0.5*n) / (1 + y + n) with mild time fade

Thread-safe enough for single-agent host (fcntl lock optional light).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.I)
_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on",
    "for", "and", "or", "but", "with", "as", "at", "by", "from", "that", "this",
    "it", "its", "we", "you", "they", "i", "me", "my", "our", "your", "what",
    "who", "how", "when", "where", "why", "do", "does", "did", "can", "could",
    "should", "would", "will", "just", "about", "into", "over", "also",
})

_LOCK = threading.Lock()
_MAX_BUCKETS = 4000
_MAX_IDS_PER_BUCKET = 48


def _tokens(text: str) -> list[str]:
    out: list[str] = []
    for t in _TOKEN_RE.findall(text or ""):
        tl = t.lower()
        if len(tl) < 2 or tl in _STOP:
            continue
        out.append(tl)
    return out[:24]


def query_buckets(query: str) -> list[str]:
    """One or more bucket ids — full set + cores of longest tokens for soft match."""
    toks = sorted(set(_tokens(query)))
    if not toks:
        return ["empty"]
    out: list[str] = []
    seen: set[str] = set()

    def add(parts: list[str]) -> None:
        if not parts:
            return
        raw = "|".join(sorted(set(parts)))
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        if h not in seen:
            seen.add(h)
            out.append(h)

    add(toks)
    longest = sorted(toks, key=len, reverse=True)
    if len(longest) >= 2:
        add(longest[:2])
    if len(longest) >= 3:
        add(longest[:3])
    return out


def query_bucket(query: str) -> str:
    """Primary bucket (full token set)."""
    return query_buckets(query)[0]


def yield_multiplier(y: float, n: float) -> float:
    """Map counts → multiplicative rank boost in ~[0.85, 1.35]."""
    # Softmax-ish confidence; cold start → 1.0
    total = y + n
    if total <= 0:
        return 1.0
    net = (y - 0.55 * n) / (1.0 + total)
    # clamp net to [-0.6, 0.8]
    net = max(-0.6, min(0.8, net))
    return 1.0 + 0.45 * net


class YieldGradient:
    """On-disk query→entry payoff map."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._data: dict[str, Any] = {"v": 1, "buckets": {}}
        self._dirty = False
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            self._data = {"v": 1, "buckets": {}}
            return
        try:
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self._data.get("buckets"), dict):
                self._data = {"v": 1, "buckets": {}}
        except (OSError, json.JSONDecodeError):
            self._data = {"v": 1, "buckets": {}}

    def save(self) -> None:
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        payload = json.dumps(self._data, separators=(",", ":"), ensure_ascii=False)
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self.path)
        self._dirty = False

    def _prune(self) -> None:
        buckets: dict = self._data.setdefault("buckets", {})
        if len(buckets) <= _MAX_BUCKETS:
            return
        # Drop coldest buckets by sum activity
        ranked = sorted(
            buckets.items(),
            key=lambda kv: sum(
                (v.get("y", 0) + v.get("n", 0)) for v in kv[1].values() if isinstance(v, dict)
            ),
        )
        for k, _ in ranked[: max(0, len(buckets) - _MAX_BUCKETS)]:
            buckets.pop(k, None)
        self._dirty = True

    def record(
        self,
        query: str,
        entry_id: str,
        *,
        helpful: bool | None = None,
        success: bool | None = None,
    ) -> None:
        if not entry_id or not (query or "").strip():
            return
        bids = query_buckets(query)
        with _LOCK:
            buckets = self._data.setdefault("buckets", {})
            for bid in bids:
                b = buckets.setdefault(bid, {})
                cell = b.setdefault(entry_id, {"y": 0.0, "n": 0.0, "t": 0.0})
                if helpful is True:
                    cell["y"] = float(cell.get("y", 0)) + 1.0
                elif helpful is False:
                    cell["n"] = float(cell.get("n", 0)) + 1.0
                if success is True:
                    cell["y"] = float(cell.get("y", 0)) + 0.6
                elif success is False:
                    cell["n"] = float(cell.get("n", 0)) + 0.35
                cell["t"] = time.time()
                if len(b) > _MAX_IDS_PER_BUCKET:
                    cold = sorted(b.items(), key=lambda kv: float(kv[1].get("t", 0)))[
                        : len(b) - _MAX_IDS_PER_BUCKET
                    ]
                    for eid, _ in cold:
                        b.pop(eid, None)
            self._dirty = True
            self._prune()
            self.save()

    def boost_map(self, query: str) -> dict[str, float]:
        """entry_id → multiplicative boost for this query (merges soft buckets)."""
        bids = query_buckets(query)
        with _LOCK:
            buckets = self._data.get("buckets", {})
            merged: dict[str, dict[str, float]] = {}
            now = time.time()
            for bid in bids:
                b = buckets.get(bid) or {}
                for eid, cell in b.items():
                    if not isinstance(cell, dict):
                        continue
                    acc = merged.setdefault(str(eid), {"y": 0.0, "n": 0.0, "t": 0.0})
                    acc["y"] += float(cell.get("y", 0))
                    acc["n"] += float(cell.get("n", 0))
                    acc["t"] = max(acc["t"], float(cell.get("t", 0)))
            out: dict[str, float] = {}
            for eid, cell in merged.items():
                y = float(cell.get("y", 0))
                n = float(cell.get("n", 0))
                # avoid double-count inflation from multi-bucket write: geometric mean scale
                scale = 1.0 / max(1.0, len(bids) * 0.85)
                y *= scale
                n *= scale
                age_days = max(0.0, (now - float(cell.get("t", now))) / 86400.0)
                fade = 0.97 ** min(age_days, 90.0)
                m = yield_multiplier(y * fade, n * fade)
                if abs(m - 1.0) > 0.01:
                    out[str(eid)] = m
            return out

    def stats(self) -> dict[str, Any]:
        buckets = self._data.get("buckets") or {}
        n_edges = sum(len(v) for v in buckets.values() if isinstance(v, dict))
        return {
            "buckets": len(buckets),
            "edges": n_edges,
            "path": str(self.path),
        }


def default_path(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "yield_gradient.json"
