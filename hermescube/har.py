"""HAR — Holographic Associative Retrieval engine.

Query protocol:
1. Embed query text → 256-dim vector q
2. Bind q with β (attention state) → qβ
3. Cosine-match qβ against L2 topic centroids
4. Retrieve L1 entries for matched buckets
5. Rank by combined centroid score + recency
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from hermescube import hrr
from hermescube.cube import CubeFile, CubeEntry, L2Bucket
from hermescube.embed import LearnedEmbedder
from hermescube import bio_rank
from hermescube import mirror as mirror_mod


# Below this entry count, linear scan beats HAR on current hardware
# (numpy baseline 2026-07-22: HAR still <1× at N=1000).
LINEAR_SCAN_MAX_N = 1200


class HARQueryEngine:
    """HAR query engine wrapping a .cube file."""

    def __init__(self, cube: CubeFile, use_learned_embeddings: bool = True) -> None:
        self.cube = cube
        self._beta: hrr.Array | None = None
        self._l2_centroids: list[L2Bucket] | None = None
        self._embedder: LearnedEmbedder | None = (
            LearnedEmbedder(dim=cube.dim) if use_learned_embeddings else None
        )
        # Hyper resident cache (lex + matrix) — surpass holo latency class
        self._cache_n: int = -1
        self._entries: list[CubeEntry] = []
        self._by_id: dict[str, CubeEntry] = {}
        self._mat = None
        self._lex = None
        self._colony = None
        self._entity_index = None
        # Yield Gradient (query-conditioned payoff) — set by provider
        self._yield_gradient = None
        self._yield_map: dict[str, float] = {}
        # Engram Net (Hebbian + Hopfield-style field) — set by provider
        self._engram_net = None

    # ── β vector management ───────────────────────────────────────

    @property
    def beta(self) -> hrr.Array:
        if self._beta is None:
            self._beta = self.cube.read_l3()
        return self._beta

    def update_beta(self, new_beta: hrr.Array) -> None:
        self._beta = new_beta
        self.cube.write_l3(new_beta)

    def apply_beta_decay(self, factor: float = 0.995) -> None:
        b = self.beta
        if hrr.has_numpy():
            import numpy as _np
            decayed = _np.asarray(b, dtype=_np.float64) * factor
            self._beta = hrr.normalize(decayed)
        else:
            decayed = [float(x) * factor for x in b]
            self._beta = hrr.normalize(decayed)
        self.cube.write_l3(self._beta)

    def update_beta_on_append(self, entry_vector: hrr.Array) -> None:
        """Light online β update (weight=0.1)."""
        b = self.beta
        if hrr.has_numpy():
            import numpy as _np
            b_arr = _np.asarray(b, dtype=_np.float64)
            ev_arr = _np.asarray(entry_vector, dtype=_np.float64)
            self._beta = hrr.normalize(b_arr + 0.1 * ev_arr)
        else:
            b_list = list(b)
            ev_list = list(entry_vector)
            summed = [b_list[i] + 0.1 * ev_list[i] for i in range(len(b_list))]
            self._beta = hrr.normalize(summed)
        self.cube.write_l3(self._beta)

    # ── L2 centroid cache ─────────────────────────────────────────

    def _load_centroids(self) -> list[L2Bucket]:
        if self._l2_centroids is None:
            self._l2_centroids = self.cube.read_l2()
        return self._l2_centroids

    def _invalidate_centroids(self) -> None:
        self._l2_centroids = None


    def invalidate_cache(self) -> None:
        self._cache_n = -1
        self._entries = []
        self._by_id = {}
        self._mat = None
        self._entity_index = None

    def refresh_cache(self, force: bool = False) -> None:
        n = int(getattr(self.cube, "entry_count", 0) or 0)
        if not force and n == self._cache_n and self._entries:
            return
        entries = self.cube.read_l1() or []
        self._entries = entries
        self._by_id = {e.id: e for e in entries}
        self._cache_n = len(entries)
        try:
            from hermescube.framework.lexindex import LexIndex
            self._lex = LexIndex()
            self._lex.build(entries)
        except Exception:
            self._lex = None
        if hrr.has_numpy() and entries:
            import numpy as _np
            try:
                self._mat = _np.asarray([e.vector for e in entries], dtype=_np.float64)
            except Exception:
                self._mat = None
        else:
            self._mat = None

    # ── Query ─────────────────────────────────────────────────────

    def query(
        self,
        text: str,
        top_k: int = 10,
        min_score: float = 0.0,
        fallback_threshold: float = 0.3,
        beta: hrr.Array | None = None,
        centroids: list[L2Bucket] | None = None,
    ) -> list[tuple[CubeEntry, float]]:
        """HAR query: return (entry, score) pairs ranked by relevance.

        Steps:
        1. Embed query, bind with β
        2. Match against L2 centroids
        3. Retrieve entries for top buckets
        4. Rank by (centroid_score * recency_weight)

        If max centroid score < fallback_threshold, falls back to
        brute-force linear scan against all entry vectors.

        beta / centroids: optional overrides for session-stable prefetch.
        When provided, the engine's live state is not modified (avoids
        races with concurrent background updates).
        """
        # ── Hyper path (default): lex candidates + batch score ──
        return self._hyper_query(text, top_k=top_k, min_score=min_score)

        # legacy HAR path retained below (unreachable) for reference/tests of internals
        # Use learned embedder if trained, otherwise hash-based
        if self._embedder and self._embedder.is_trained:
            q = self._embedder.embed_query(text)
        else:
            q = hrr.embed_text(text)
        # Use provided beta (snapshot) or engine's live beta
        effective_beta = beta if beta is not None else self.beta
        q_beta = hrr.bind(q, effective_beta)

        # Use provided centroids (snapshot) or load from cube
        effective_centroids = centroids if centroids is not None else self._load_centroids()

        # Score each centroid
        scored_buckets: list[tuple[float, L2Bucket, int]] = []
        for idx, bucket in enumerate(effective_centroids):
            score = hrr.cosine_sim(q_beta, bucket.centroid)
            if score > min_score:
                scored_buckets.append((score, bucket, idx))

        scored_buckets.sort(key=lambda x: -x[0])

        # Fallback if confidence too low or archive is empty
        max_score = scored_buckets[0][0] if scored_buckets else 0.0
        if max_score < fallback_threshold or not scored_buckets:
            return self._fallback_scan(text, top_k)

        # Quicksilver: don't pay L1 full-read + bucket walk when scan is faster.
        # bench (numpy, 2026-07-22): scan still wins through N≈1000;
        # use cheap entry_count and linear path below LINEAR_SCAN_MAX_N.
        n_entries = int(getattr(self.cube, "entry_count", 0) or 0)
        if n_entries > 0 and n_entries < LINEAR_SCAN_MAX_N:
            return self._fallback_scan(text, top_k)

        # Collect entries from top buckets
        entry_scores: dict[str, tuple[CubeEntry, float]] = {}
        n_buckets = max(3, top_k // 2)
        all_entries = self.cube.read_l1()
        now_ts = all_entries[-1].timestamp if all_entries else ""
        for centroid_score, bucket, _ in scored_buckets[:n_buckets]:
            for eid in bucket.entry_ids:
                if eid not in entry_scores:
                    entry = self.cube.read_entry(eid)
                    if entry:
                        final = self._rank_entry(
                            entry, float(centroid_score), now=now_ts, query=text
                        )
                        entry_scores[eid] = (entry, final)

        # Sort by score then diversify by cortical layer, then mirror-expand
        ranked = sorted(entry_scores.values(), key=lambda x: -x[1])
        primary = bio_rank.diversify_by_layer(ranked, max(top_k, 3))
        return self._mirror_finish(primary, all_entries, top_k)

    def _mirror_finish(
        self,
        primary: list[tuple[CubeEntry, float]],
        all_entries: list[CubeEntry],
        top_k: int,
    ) -> list[tuple[CubeEntry, float]]:
        """Reflect related memories (entity/parent graph) into the hit set."""
        if not primary:
            return []
        idx = mirror_mod.build_entity_index(all_entries)
        colony = getattr(self, "_colony", None)
        return mirror_mod.mirror_expand(
            primary, all_entries, top_k=top_k, entity_index=idx, colony=colony
        )

    def _fallback_scan(
        self, text: str, top_k: int
    ) -> list[tuple[CubeEntry, float]]:
        """Brute-force linear scan when HAR confidence is low.

        Quicksilver: batch cosine via numpy matmul when available (N×d · d),
        instead of N separate norm/dot loops.
        """
        if self._embedder and self._embedder.is_trained:
            q = self._embedder.embed(text)
        else:
            q = hrr.embed_text(text)
        entries = self.cube.read_l1()
        if not entries:
            return []
        # Lexindex candidate shrink (framework) when large
        lex = getattr(self, "_lexindex", None)
        if lex is not None and len(entries) > 64:
            try:
                ids = lex.candidate_ids(text, limit=min(120, max(48, len(entries) // 4)))
                if ids:
                    by_id = {e.id: e for e in entries}
                    narrowed = [by_id[i] for i in ids if i in by_id]
                    if narrowed:
                        entries = narrowed
            except Exception:
                pass
        now_ts = entries[-1].timestamp if entries else ""

        if hrr.has_numpy():
            import numpy as _np

            mat = _np.asarray(
                [e.vector for e in entries],
                dtype=_np.float64,
            )
            if mat.ndim != 2 or mat.shape[0] == 0:
                return []
            qv = _np.asarray(q, dtype=_np.float64).reshape(-1)
            norms = _np.linalg.norm(mat, axis=1)
            norms = _np.where(norms < 1e-12, 1.0, norms)
            qn = float(_np.linalg.norm(qv))
            if qn < 1e-12:
                # Degenerate query embed — retry hash
                qv = _np.asarray(hrr.embed_text(text), dtype=_np.float64).reshape(-1)
                qn = float(_np.linalg.norm(qv))
                if qn < 1e-12:
                    return []
            sims = (mat @ qv) / (norms * qn)
            # NaN-safe
            sims = _np.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)
            scored: list[tuple[CubeEntry, float]] = []
            for i, entry in enumerate(entries):
                scored.append(
                    (entry, self._rank_entry(entry, float(sims[i]), now=now_ts, query=text))
                )
            scored.sort(key=lambda x: -x[1])
            primary = bio_rank.diversify_by_layer(scored, max(top_k, 3))
            return self._mirror_finish(primary, entries, top_k)

        scored = []
        for entry in entries:
            score = hrr.cosine_sim(q, entry.vector)
            scored.append(
                (entry, self._rank_entry(entry, float(score), now=now_ts, query=text))
            )
        scored.sort(key=lambda x: -x[1])
        primary = bio_rank.diversify_by_layer(scored, max(top_k, 3))
        return self._mirror_finish(primary, entries, top_k)

    @staticmethod
    def _delta_hours(entry: CubeEntry, now: str = "") -> float:
        try:
            ts = entry.timestamp
            if now and len(ts) >= 19 and len(now) >= 19:
                from datetime import datetime

                t_entry = datetime.fromisoformat(ts[:19])
                t_now = datetime.fromisoformat(now[:19])
                return max(0.0, (t_now - t_entry).total_seconds() / 3600.0)
        except (ValueError, IndexError, TypeError):
            pass
        return 0.0

    @staticmethod
    def _recency_weight(entry: CubeEntry, now: str = "") -> float:
        """Type-aware bio decay (elephant social/spatial lasts longer than focus)."""
        try:
            delta = HARQueryEngine._delta_hours(entry, now=now)
            if delta > 0 or (now and entry.timestamp):
                return bio_rank.recency_weight(delta, entry.entry_type or "")
            # Fallback: mild hour-of-day jitter when timestamps incomplete
            ts = entry.timestamp or ""
            hour = int(ts[11:13]) if len(ts) >= 13 else 12
            return 1.0 + (hour % 24) / 100.0
        except (ValueError, IndexError, TypeError):
            return 1.0

    def _prime_yield(self, query: str) -> None:
        """Load query-local yield boosts (closed learning loop)."""
        self._yield_map = {}
        yg = getattr(self, "_yield_gradient", None)
        if yg is None or not query:
            return
        try:
            self._yield_map = yg.boost_map(query) or {}
        except Exception:
            self._yield_map = {}

    def _rank_entry(
        self,
        entry: CubeEntry,
        semantic: float,
        *,
        now: str = "",
        query: str = "",
        yield_boost: float | None = None,
    ) -> float:
        trust = None
        if entry.data and isinstance(entry.data, dict):
            trust = entry.data.get("trust")
        lex = bio_rank.lexical_score(query, entry.description or "") if query else 0.0
        data = entry.data if isinstance(entry.data, dict) else None
        yb = yield_boost
        if yb is None:
            eid = getattr(entry, "id", None) or ""
            yb = float(self._yield_map.get(str(eid), 1.0)) if self._yield_map else 1.0
        return bio_rank.composite_score(
            semantic,
            entry_type=entry.entry_type or "",
            outcome=entry.outcome or "none",
            trust=trust if isinstance(trust, (int, float)) else None,
            delta_hours=self._delta_hours(entry, now=now),
            lexical=lex,
            description=entry.description or "",
            data=data,
            yield_boost=float(yb),
        )

    def _hyper_query(
        self,
        text: str,
        *,
        top_k: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[CubeEntry, float]]:
        """Lex-first two-stage retrieval — holo-class speed, Cube store."""
        if not text or not str(text).strip():
            return []
        self._prime_yield(text)
        self.refresh_cache()
        if not self._entries:
            return []
        n = len(self._entries)
        limit = min(160, max(48, top_k * 12))
        if n <= 48:
            cands = list(self._entries)
        else:
            ids = self._lex.candidate_ids(text, limit=limit) if self._lex else None
            if ids:
                cands = [self._by_id[i] for i in ids if i in self._by_id]
            else:
                cands = list(self._entries[-limit:])
            if not cands:
                cands = list(self._entries)
        now_ts = self._entries[-1].timestamp if self._entries else ""
        if self._embedder and self._embedder.is_trained:
            q = self._embedder.embed_query(text)
        else:
            q = hrr.embed_text(text)
        scored: list[tuple[CubeEntry, float]] = []
        if hrr.has_numpy():
            import numpy as _np
            mat = _np.asarray([e.vector for e in cands], dtype=_np.float64)
            qv = _np.asarray(q, dtype=_np.float64).reshape(-1)
            norms = _np.linalg.norm(mat, axis=1)
            norms = _np.where(norms < 1e-12, 1.0, norms)
            qn = float(_np.linalg.norm(qv))
            if qn < 1e-12:
                qv = _np.asarray(hrr.embed_text(text), dtype=_np.float64).reshape(-1)
                qn = float(_np.linalg.norm(qv))
            if qn >= 1e-12 and mat.size:
                sims = _np.nan_to_num((mat @ qv) / (norms * qn), nan=0.0)
                for i, entry in enumerate(cands):
                    scored.append(
                        (entry, self._rank_entry(entry, float(sims[i]), now=now_ts, query=text))
                    )
        if not scored:
            for entry in cands:
                s = hrr.cosine_sim(q, entry.vector)
                scored.append(
                    (entry, self._rank_entry(entry, float(s), now=now_ts, query=text))
                )
        if min_score > 0:
            scored = [(e, s) for e, s in scored if s >= min_score]
        scored.sort(key=lambda x: -x[1])
        # Engram Net re-rank: association completion + co-activation (neural field)
        scored = self._apply_engram(scored, q if isinstance(q, list) else list(q) if q is not None else None)
        primary = bio_rank.diversify_by_layer(scored, max(top_k, 3))
        # light expand only — entity index cached; skip if tiny result already full
        idx = self._entity_index
        if idx is None:
            out = primary[:top_k]
        else:
            out = mirror_mod.mirror_expand(
                primary,
                self._entries,
                top_k=top_k,
                entity_index=idx,
                colony=getattr(self, "_colony", None),
            )
        # weak Hebbian co-activation on retrieved set (shadow learn)
        try:
            net = getattr(self, "_engram_net", None)
            if net is not None and out:
                ids = [str(getattr(e, "id", "") or "") for e, _ in out if getattr(e, "id", None)]
                vecs = []
                for e, _ in out[:8]:
                    v = getattr(e, "vector", None)
                    if v is not None:
                        try:
                            vecs.append([float(x) for x in list(v)[:512]])
                        except Exception:
                            pass
                if len(ids) >= 2:
                    net.learn_coactivation(ids, vecs if vecs else None, strength=0.35)
        except Exception:
            pass
        return out

    def _apply_engram(
        self,
        scored: list[tuple[CubeEntry, float]],
        query_vec: list[float] | None,
    ) -> list[tuple[CubeEntry, float]]:
        net = getattr(self, "_engram_net", None)
        if net is None or not scored:
            return scored
        try:
            # pool: top slice for association context
            pool = scored[: min(48, len(scored))]
            ids = [str(getattr(e, "id", "") or "") for e, _ in pool]
            qv = None
            if query_vec is not None:
                try:
                    qv = [float(x) for x in list(query_vec)[:512]]
                except Exception:
                    qv = None
            boosts = net.association_boosts(qv, ids)
            if not boosts:
                return scored
            rescored = [
                (e, float(s) * float(boosts.get(str(getattr(e, "id", "") or ""), 1.0)))
                for e, s in scored
            ]
            rescored.sort(key=lambda x: -x[1])
            return rescored
        except Exception:
            return scored

    def probe_entity(self, entity: str, top_k: int = 10) -> list[tuple[CubeEntry, float]]:
        return self.query(entity, top_k=top_k)

    def related(self, entity: str, top_k: int = 10) -> list[tuple[CubeEntry, float]]:
        self.refresh_cache()
        key = entity.strip().lower()
        if not key:
            return []
        idx = mirror_mod.build_entity_index(self._entries)
        seeds = list(idx.get(key) or [])
        if not seeds:
            for k, ents in idx.items():
                if key in k or k in key:
                    seeds.extend(ents)
        if not seeds:
            return self.query(entity, top_k=top_k)
        seen = set()
        uniq = []
        for e in seeds:
            if e.id not in seen:
                seen.add(e.id)
                uniq.append((e, 1.0))
        return mirror_mod.mirror_expand(
            uniq[:top_k],
            self._entries,
            top_k=top_k,
            entity_index=idx,
            colony=getattr(self, "_colony", None),
        )


    def contradict(
        self,
        text: str,
        top_k: int = 5,
        min_opposition: float = -0.1,
    ) -> list[tuple[CubeEntry, float]]:
        """Find entries semantically distant from the query.

        Uses ``unbind`` (circular correlation) to decompose the entry
        vector against the query, then measures how dissimilar the
        residue is. Entries with the most negative cosine similarity
        to the query are ranked first — these are semantically most
        distant, potentially contradictory.

        This gives ``unbind()`` a real use case: finding *conflicting*
        or *superseded* memories alongside matching ones.
        """
        if self._embedder and self._embedder.is_trained:
            q = self._embedder.embed_query(text)
        else:
            q = hrr.embed_text(text)

        entries = self.cube.read_l1()
        scored: list[tuple[CubeEntry, float]] = []
        for entry in entries:
            # unbind decomposes entry vector w.r.t query
            residue = hrr.unbind(entry.vector, q)
            # How well does the residue point back to q?
            # Negative = entry vector points away from q → contradict
            opposition = hrr.cosine_sim(residue, q)
            if opposition <= min_opposition:
                scored.append((entry, opposition))

        scored.sort(key=lambda x: x[1])  # most negative first
        return scored[:top_k]

    # ── Evolution ─────────────────────────────────────────────────

    def evolve(self, k: int | None = None) -> dict[str, Any]:
        self.invalidate_cache()
        """Recluster L2 centroids, update β, return stats.

        Steps:
        1. Read all entries with vectors
        2. Run k-means on entry vectors (k = l2_bucket_count)
        3. Assign each entry to nearest centroid
        4. Compute new β: normalize(old β + topic means)
        5. Apply β decay
        6. Write updated L2 + L3
        """
        num_clusters = k or self.cube.l2_bucket_count
        entries = self.cube.read_l1()

        if not entries:
            return {"clusters": 0, "entries": 0, "note": "no entries"}

        # Collect entry vectors
        vecs = []
        for e in entries:
            v = e.vector
            if hrr.has_numpy():
                import numpy as _np
                vecs.append(_np.asarray(v, dtype=_np.float64))
            else:
                vecs.append(list(v))

        # k-means: use existing centroids if available (incremental),
        # otherwise k-means++ init from scratch.
        # Incremental requires buckets that were previously populated —
        # a fresh cube has 64 empty buckets with zero centroids, which
        # are degenerate as k-means initialization.
        existing_centroids = self._load_centroids()
        has_populated = any(b.entry_ids for b in existing_centroids)
        if has_populated and len(existing_centroids) == num_clusters:
            # Incremental: use existing centroids, single refinement pass
            centroids = [b.centroid for b in existing_centroids]
            centroids = self._kmeans_iteration(vecs, centroids, num_clusters)
        else:
            # Full: k-means++ init, up to 10 iterations (early stop on convergence)
            centroids = self._kmeans_init(vecs, num_clusters)
            for _iter in range(10):
                new_centroids = self._kmeans_iteration(vecs, centroids, num_clusters)
                # Convergence check: max centroid movement
                max_delta = max(
                    1.0 - hrr.cosine_sim(c, nc)
                    for c, nc in zip(centroids, new_centroids)
                )
                centroids = new_centroids
                if max_delta < 0.001:  # converged
                    break

        # Assign entries to nearest centroid
        assignments: list[list[int]] = [[] for _ in range(num_clusters)]
        for idx, vec in enumerate(vecs):
            best_c = -1
            best_d = -1.0
            for c_idx, cent in enumerate(centroids):
                d = hrr.cosine_sim(vec, cent)
                if d > best_d:
                    best_d = d
                    best_c = c_idx
            assignments[best_c].append(idx)

        # Build L2 buckets
        buckets: list[L2Bucket] = []
        topic_vectors: list[hrr.Array] = []
        for c_idx in range(num_clusters):
            member_ids = [entries[i].id for i in assignments[c_idx]]
            centroid = centroids[c_idx]

            # Extract top terms from member descriptions
            terms = self._extract_terms(
                [entries[i].description for i in assignments[c_idx]]
            )

            bucket = L2Bucket(
                centroid=centroid,
                entry_ids=member_ids,
                terms=terms[:8],
            )
            buckets.append(bucket)

            if member_ids:
                topic_vectors.append(centroid)

        # Update β: blend old β with topic mean, then decay
        old_beta = self.beta
        if topic_vectors:
            topic_mean = hrr.superpose(topic_vectors)
            if hrr.has_numpy():
                import numpy as _np
                old = _np.asarray(old_beta, dtype=_np.float64)
                mean = _np.asarray(topic_mean, dtype=_np.float64)
                new_beta = hrr.normalize(0.7 * old + 0.3 * mean)
            else:
                old = list(old_beta)
                mean = list(topic_mean)
                blended = [
                    0.7 * old[i] + 0.3 * mean[i] for i in range(len(old))
                ]
                new_beta = hrr.normalize(blended)
        else:
            new_beta = old_beta

        # Decay
        if hrr.has_numpy():
            import numpy as _np
            new_beta = hrr.normalize(_np.asarray(new_beta, dtype=_np.float64) * 0.995)
        else:
            new_beta = hrr.normalize([float(x) * 0.995 for x in new_beta])

        # Write
        self.cube.write_l2(buckets)
        self.update_beta(new_beta)
        self._invalidate_centroids()

        # Train learned embedder on all descriptions
        embedder_stats: dict[str, Any] = {}
        if self._embedder:
            descriptions = [e.description for e in entries]
            embedder_stats = self._embedder.train(descriptions)

        return {
            "clusters": num_clusters,
            "entries": len(entries),
            "non_empty_buckets": sum(1 for b in buckets if b.entry_ids),
            "beta_norm": round(float(hrr.norm(new_beta)), 6),
            "embedder": embedder_stats,
        }

    # ── k-means helpers ───────────────────────────────────────────

    def _kmeans_init(
        self, vectors: list[Any], k: int
    ) -> list[hrr.Array]:
        """k-means++ initialization."""
        if k <= 0:
            return []
        if len(vectors) <= k:
            # Pad with copies + noise to reach k.
            # Seed the noise deterministically from the input vectors so
            # initialization is reproducible per-input (not at the mercy
            # of the process-global RNG).
            seed_material = "|".join(
                str(round(sum(v), 6)) for v in vectors
            ).encode()
            seed = int.from_bytes(
                hashlib.sha256(seed_material).digest()[:4], "big"
            )
            if hrr.has_numpy():
                import numpy as _np_np
                rng = _np_np.random.RandomState(seed)
                result = list(vectors)
                while len(result) < k:
                    src = result[len(result) % len(vectors)]
                    noise = rng.randn(len(src)) * 0.01
                    padded = hrr.normalize(_np_np.asarray(src, dtype=_np_np.float64) + noise)
                    result.append(padded)
                return result
            else:
                import random as _random
                rng = _random.Random(seed)
                result = [list(v) for v in vectors]
                while len(result) < k:
                    src = result[len(result) % len(vectors)]
                    noise = [rng.gauss(0, 0.01) for _ in src]
                    padded = hrr.normalize([src[i] + noise[i] for i in range(len(src))])
                    result.append(padded)
                return result

        centroids: list[hrr.Array] = []
        if hrr.has_numpy():
            import numpy as _np
            centroids.append(_np.asarray(vectors[0], dtype=_np.float64).copy())
        else:
            centroids.append(list(vectors[0]))

        for _ in range(1, k):
            dists = []
            for vec in vectors:
                v_arr = _np.asarray(vec) if hrr.has_numpy() else vec
                min_d = min(hrr.cosine_sim(v_arr, c) for c in centroids)
                dists.append(1.0 - min_d + 1e-12)
            total = sum(dists)
            r = (hashlib.sha256(str(total).encode()).digest()[0] / 255.0) * total
            cumulative = 0.0
            chosen = vectors[-1]
            for i, d in enumerate(dists):
                cumulative += d
                if cumulative >= r:
                    chosen = vectors[i]
                    break
            if hrr.has_numpy():
                centroids.append(_np.asarray(chosen, dtype=_np.float64).copy())
            else:
                centroids.append(list(chosen))
        return centroids

    def _kmeans_iteration(
        self, vectors: list[Any], centroids: list[hrr.Array], k: int
    ) -> list[hrr.Array]:
        """One k-means iteration: assign → recompute means."""
        assignments: list[list[int]] = [[] for _ in range(k)]
        for idx, vec in enumerate(vectors):
            best_c = -1
            best_d = -1.0
            for c_idx in range(k):
                d = hrr.cosine_sim(vec, centroids[c_idx])
                if d > best_d:
                    best_d = d
                    best_c = c_idx
            assignments[best_c].append(idx)

        if hrr.has_numpy():
            import numpy as _np
            new_centroids = []
            for c_idx in range(k):
                if not assignments[c_idx]:
                    new_centroids.append(_np.asarray(centroids[c_idx], dtype=_np.float64).copy())
                else:
                    cluster_vecs = [_np.asarray(vectors[i], dtype=_np.float64) for i in assignments[c_idx]]
                    mean = _np.mean(cluster_vecs, axis=0)
                    new_centroids.append(hrr.normalize(mean))
            return new_centroids
        else:
            new_centroids = []
            for c_idx in range(k):
                if not assignments[c_idx]:
                    new_centroids.append(list(centroids[c_idx]))
                else:
                    cluster_vecs = [vectors[i] for i in assignments[c_idx]]
                    dim = len(cluster_vecs[0])
                    mean = [0.0] * dim
                    for vec in cluster_vecs:
                        for i in range(dim):
                            mean[i] += vec[i]
                    mean = [x / len(cluster_vecs) for x in mean]
                    new_centroids.append(hrr.normalize(mean))
            return new_centroids

    # ── Term extraction ───────────────────────────────────────────

    @staticmethod
    def _extract_terms(descriptions: list[str], max_terms: int = 8) -> list[str]:
        stopwords = frozenset(
            "the a an and or to of for in on at is was with from that this "
            "into via set goal enter sealed none".split()
        )
        counter: Counter = Counter()
        for desc in descriptions:
            toks = re.findall(r"[a-z][a-z0-9_\-]{2,}", desc.lower())
            for t in toks:
                if t not in stopwords:
                    counter[t] += 1
        return [t for t, _ in counter.most_common(max_terms)]
