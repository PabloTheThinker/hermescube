"""Cubewave — brainwave association field inside the Cuboasis pocket dimension.

The cube is a memory oasis for Hermes agents. Cubewave is the neural-like
substrate that learns which memories *resonate* together — without torch.

Architecture (Cube-native ELM / soft reservoir — not a clone of EngramNet):
  1) Token bag → fixed random projection into H-dim "wave" (frozen feature map)
  2) Online LMS readout: wave → soft affinity over entry ids (feedback-trained)
  3) Soft Hebbian co-activation among co-retrieved entry ids
  4) association_boosts() → multiplicative HAR re-rank (sibling to EngramNet)

Hot path: O(H + |candidates|) with H small (≤96).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

_MAX_ENTRIES = 4000
_MAX_EDGES = 6000
_MAX_DEGREE = 28
_DEFAULT_H = 64
_SEED = 0xC0BEA5E  # cube-native seed — stable across process restarts


def _tokens(text: str) -> list[str]:
    try:
        from hermescube import bio_rank

        return sorted(bio_rank.tokenize(text or "") or set())[:48]
    except Exception:
        raw = (text or "").lower().replace("-", " ").replace("_", " ")
        return [t for t in raw.split() if len(t) >= 2][:48]


def _proj_row(token: str, h: int, seed: int) -> list[float]:
    """Deterministic ±1/√h random projection row for one token (no stored W_in)."""
    out = [0.0] * h
    scale = 1.0 / math.sqrt(float(h))
    for i in range(h):
        digest = hashlib.blake2b(
            f"{seed}:{token}:{i}".encode(),
            digest_size=8,
        ).digest()
        # map 64-bit → ±1
        v = int.from_bytes(digest, "little")
        out[i] = scale if (v & 1) else -scale
    return out


def _wave_from_tokens(tokens: Iterable[str], h: int, seed: int) -> list[float]:
    toks = [str(t).lower() for t in tokens if t]
    if not toks:
        return [0.0] * h
    acc = [0.0] * h
    for tok in toks:
        row = _proj_row(tok, h, seed)
        for i in range(h):
            acc[i] += row[i]
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in acc)) or 1.0
    return [x / norm for x in acc]


def _wave_from_vec(vec: list[float] | None, h: int) -> list[float]:
    """Fold an HRR/query vector into H dims via block-average (no learnable params)."""
    if not vec:
        return [0.0] * h
    d = len(vec)
    out = [0.0] * h
    for i, x in enumerate(vec):
        out[i % h] += float(x)
    # normalize by occupancy
    occ = [0] * h
    for i in range(d):
        occ[i % h] += 1
    for i in range(h):
        if occ[i]:
            out[i] /= float(occ[i])
    norm = math.sqrt(sum(x * x for x in out)) or 1.0
    return [x / norm for x in out]


def default_path(
    hermes_home: str | Path,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).cubewave


class Cubewave:
    """Pocket-dimension neural field over cube entry ids."""

    def __init__(self, path: str | Path, *, hidden: int = _DEFAULT_H) -> None:
        self.path = Path(path)
        self.h = max(16, min(96, int(hidden)))
        self.seed = _SEED
        # entry_id → readout weight vector (LMS)
        self._readout: dict[str, list[float]] = {}
        # soft Hebbian edges
        self._edges: dict[str, dict[str, float]] = {}
        self._dirty = False
        self._lock = threading.RLock()
        self.load()

    def load(self) -> None:
        readout: dict[str, list[float]] = {}
        edges: dict[str, dict[str, float]] = {}
        h = self.h
        seed = self.seed
        if self.path.is_file():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                h = int(raw.get("h") or h)
                seed = int(raw.get("seed") or seed)
                for k, v in (raw.get("readout") or {}).items():
                    if isinstance(v, list) and len(v) == h:
                        readout[str(k)] = [float(x) for x in v]
                edges = {
                    str(a): {str(b): float(w) for b, w in (bucket or {}).items()}
                    for a, bucket in (raw.get("edges") or {}).items()
                    if isinstance(bucket, dict)
                }
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                readout, edges = {}, {}
        with self._lock:
            self.h = max(16, min(96, h))
            self.seed = seed
            self._readout = readout
            self._edges = edges

    def save(self) -> None:
        with self._lock:
            if not self._dirty:
                return
            # Cap readout table size
            if len(self._readout) > _MAX_ENTRIES:
                # keep highest L2-norm readouts (most trained)
                ranked = sorted(
                    self._readout.items(),
                    key=lambda kv: -sum(x * x for x in kv[1]),
                )[:_MAX_ENTRIES]
                self._readout = dict(ranked)
            blob = json.dumps(
                {
                    "v": 1,
                    "kind": "cubewave",
                    "h": self.h,
                    "seed": self.seed,
                    "readout": self._readout,
                    "edges": self._edges,
                    "ts": time.time(),
                },
                separators=(",", ":"),
            )
            self._dirty = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(
            f"{self.path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            tmp.write_text(blob, encoding="utf-8")
            tmp.replace(self.path)
        except BaseException:
            with self._lock:
                self._dirty = True
            tmp.unlink(missing_ok=True)
            raise

    def _wave(
        self,
        *,
        query_text: str = "",
        query_vec: list[float] | None = None,
        tokens: Iterable[str] | None = None,
    ) -> list[float]:
        toks = list(tokens) if tokens is not None else _tokens(query_text)
        w_tok = _wave_from_tokens(toks, self.h, self.seed)
        if query_vec:
            w_vec = _wave_from_vec(query_vec, self.h)
            # blend: text tokens dominate when present
            alpha = 0.65 if toks else 0.0
            mixed = [
                alpha * w_tok[i] + (1.0 - alpha) * w_vec[i] for i in range(self.h)
            ]
            norm = math.sqrt(sum(x * x for x in mixed)) or 1.0
            return [x / norm for x in mixed]
        return w_tok

    # ── learning ──────────────────────────────────────────────────

    def learn_coactivation(
        self,
        entry_ids: Iterable[str],
        *,
        query_text: str = "",
        query_vec: list[float] | None = None,
        strength: float = 1.0,
    ) -> None:
        """Hebbian wiring + mild positive LMS nudge for co-retrieved set."""
        ids = []
        seen: set[str] = set()
        for x in entry_ids:
            s = str(x)
            if s and s not in seen:
                seen.add(s)
                ids.append(s)
        if len(ids) < 1:
            return
        wave = self._wave(query_text=query_text, query_vec=query_vec)
        with self._lock:
            if len(ids) >= 2:
                w = 0.12 * float(strength)
                for a in ids:
                    bucket = self._edges.setdefault(a, {})
                    for b in ids:
                        if a == b:
                            continue
                        bucket[b] = min(6.0, float(bucket.get(b, 0.0)) + w)
                    if len(bucket) > _MAX_DEGREE:
                        top = sorted(bucket.items(), key=lambda kv: -kv[1])[
                            :_MAX_DEGREE
                        ]
                        self._edges[a] = dict(top)
                self._prune_edges()
            # Mild positive LMS: move readout toward the query wave
            lr = 0.04 * float(strength)
            for eid in ids:
                row = self._readout.get(eid)
                if row is None or len(row) != self.h:
                    row = [0.0] * self.h
                for i in range(self.h):
                    row[i] += lr * (wave[i] - row[i])
                self._readout[eid] = row
            self._dirty = True

    def learn_feedback(
        self,
        entry_ids: Iterable[str],
        helpful: bool,
        *,
        query_text: str = "",
        query_vec: list[float] | None = None,
    ) -> None:
        """LMS + edge update from usefulness signal (the closed learning loop)."""
        ids = [str(x) for x in entry_ids if x]
        if not ids:
            return
        wave = self._wave(query_text=query_text, query_vec=query_vec)
        target = 1.0 if helpful else -0.6
        lr = 0.12 if helpful else 0.08
        edge_delta = 0.28 if helpful else -0.22
        with self._lock:
            for eid in ids:
                row = self._readout.get(eid)
                if row is None or len(row) != self.h:
                    row = [0.0] * self.h
                # pred = wave · readout
                pred = sum(wave[i] * row[i] for i in range(self.h))
                err = target - pred
                for i in range(self.h):
                    row[i] += lr * err * wave[i]
                    # soft clip
                    if row[i] > 4.0:
                        row[i] = 4.0
                    elif row[i] < -4.0:
                        row[i] = -4.0
                self._readout[eid] = row
            if len(ids) >= 2:
                for a in ids:
                    bucket = self._edges.setdefault(a, {})
                    for b in ids:
                        if a == b:
                            continue
                        nw = float(bucket.get(b, 0.0)) + edge_delta
                        if nw <= 0.05:
                            bucket.pop(b, None)
                        else:
                            bucket[b] = min(6.0, nw)
                self._prune_edges()
            self._dirty = True

    def _prune_edges(self) -> None:
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
        query_text: str = "",
    ) -> dict[str, float]:
        """Multiplicative boosts ~[0.86, 1.38] for candidate ids."""
        if not candidate_ids:
            return {}
        if not self._readout and not self._edges:
            return {}
        wave = self._wave(query_text=query_text, query_vec=query_vec)
        boosts = {str(i): 1.0 for i in candidate_ids}
        idset = set(boosts)

        # 1) Readout resonance — how well each entry's learned wave matches cue
        for eid in list(idset):
            row = self._readout.get(eid)
            if not row or len(row) != self.h:
                continue
            score = sum(wave[i] * row[i] for i in range(self.h))
            # map score roughly [-2,2] → multiplier
            boosts[eid] *= 1.0 + 0.22 * max(-1.0, min(1.5, score))

        # 2) Co-graph mutual wiring among candidates
        for eid in list(idset):
            bucket = self._edges.get(eid) or {}
            if not bucket:
                continue
            link = 0.0
            for j, w in bucket.items():
                if j in idset:
                    link += min(2.0, float(w))
            if link > 0:
                boosts[eid] *= 1.0 + 0.10 * min(3.0, link)

        for eid in boosts:
            boosts[eid] = max(0.86, min(1.38, float(boosts[eid])))
        return boosts

    def stats(self) -> dict[str, Any]:
        return {
            "kind": "cubewave",
            "h": self.h,
            "readouts": len(self._readout),
            "nodes": len(self._edges),
            "edges": sum(len(v) for v in self._edges.values()),
            "path": str(self.path),
        }

    def hub_ids(self, *, limit: int = 8) -> list[str]:
        scored: list[tuple[float, str]] = []
        for nid, bucket in self._edges.items():
            if not bucket:
                continue
            wsum = sum(min(2.0, float(w)) for w in bucket.values())
            scored.append((wsum + 0.12 * len(bucket), str(nid)))
        # also surface strong readout norms
        for eid, row in self._readout.items():
            n2 = sum(x * x for x in row)
            if n2 > 0.05:
                scored.append((math.sqrt(n2), str(eid)))
        scored.sort(key=lambda x: -x[0])
        seen: set[str] = set()
        out: list[str] = []
        for _, i in scored:
            if i in seen:
                continue
            seen.add(i)
            out.append(i)
            if len(out) >= max(1, limit):
                break
        return out
