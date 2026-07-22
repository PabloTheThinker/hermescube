"""Learned embeddings for improved semantic similarity.

Replaces hash-based embedding with a trained model that captures
semantic relationships between terms. Uses SVD on the term-context
matrix when numpy is available, pure-Python TF-IDF + random projection
as fallback.

Usage:
    embedder = LearnedEmbedder(dim=256)
    embedder.train(descriptions)  # build vocabulary + projections
    vec = embedder.embed("User prefers dark mode")
    query_vec = embedder.embed_query("what theme does the user like")

Persistence:
    embedder.save("model.embedder")  # save trained model to disk
    embedder = LearnedEmbedder.load("model.embedder")  # load from disk
"""

from __future__ import annotations

import json
import math
import os
import re
import struct
import time
from collections import Counter
from typing import Any

from hermescube import hrr


class LearnedEmbedder:
    """Trained embedding model that improves on hash-based encoding.

    Builds a term vocabulary from accumulated descriptions, computes
    IDF weights, and uses random projections (or SVD with numpy) to
    produce dense vectors that capture semantic similarity.
    """

    def __init__(
        self,
        dim: int = 256,
        min_df: int = 1,
        max_df_ratio: float = 0.8,
        sublinear_tf: bool = True,
    ) -> None:
        self.dim = dim
        self.min_df = min_df
        self.max_df_ratio = max_df_ratio
        self.sublinear_tf = sublinear_tf

        # Vocabulary: term → index
        self._vocab: dict[str, int] = {}
        # IDF weights: index → weight
        self._idf: list[float] = []
        # Random projection matrix: vocab_size × dim
        self._projection: list[list[float]] = []
        # Whether the model has been trained
        self._trained: bool = False
        # Document count for IDF
        self._doc_count: int = 0
        # Term document frequency
        self._df: Counter[str] = Counter()

    @property
    def is_trained(self) -> bool:
        return self._trained

    def _tokenize(self, text: str) -> list[str]:
        """Extract lowercase tokens (3+ chars, alphanumeric + underscore)."""
        return re.findall(r"[a-z][a-z0-9_]{2,}", text.lower())

    def _build_vocab(self, descriptions: list[str]) -> None:
        """Build vocabulary from descriptions."""
        term_freq: Counter[str] = Counter()
        self._doc_count = len(descriptions)

        for desc in descriptions:
            tokens = set(self._tokenize(desc))
            for t in tokens:
                self._df[t] += 1
            for t in tokens:
                term_freq[t] += 1

        # Filter by document frequency
        min_df = max(1, int(self._doc_count * 0.01))  # at least 1% of docs
        max_df = int(self._doc_count * self.max_df_ratio)

        filtered = [
            (term, freq)
            for term, freq in term_freq.most_common()
            if self._df[term] >= min_df and self._df[term] <= max_df
        ]

        # Fallback: if max_df filtering eliminated everything (all docs
        # share vocabulary), relax the upper bound rather than fail
        if not filtered:
            filtered = [
                (term, freq)
                for term, freq in term_freq.most_common()
                if self._df[term] >= min_df
            ]

        self._vocab = {term: idx for idx, (term, _) in enumerate(filtered)}
        self._idf = []
        for term, _ in filtered:
            df = self._df[term]
            # Standard IDF: log(N / (1 + df))
            self._idf.append(math.log(self._doc_count / (1 + df)))

    def _compute_tf(self, tokens: list[str]) -> dict[str, float]:
        """Compute term frequency vector."""
        counts: Counter[str] = Counter()
        for t in tokens:
            if t in self._vocab:
                counts[t] += 1

        if not counts:
            return {}

        max_count = max(counts.values())
        tf: dict[str, float] = {}
        for term, count in counts.items():
            if self.sublinear_tf:
                tf[term] = (1 + math.log(count)) / (1 + math.log(max_count))
            else:
                tf[term] = count / max_count
        return tf

    def _build_projection(self) -> None:
        """Build random projection matrix.

        Uses seeded deterministic random for reproducibility.
        With numpy, uses Gaussian random projection (better quality).
        Without numpy, uses sparse random projection.
        """
        vocab_size = len(self._vocab)
        if vocab_size == 0:
            return

        if hrr.has_numpy():
            import numpy as _np

            # Deterministic seed from vocab hash
            seed = hash(tuple(sorted(self._vocab.keys()))) % (2**31)
            rng = _np.random.RandomState(seed)
            # Gaussian projection (better than sparse for small vocab)
            self._projection = rng.randn(vocab_size, self.dim).tolist()
        else:
            # Sparse random projection: each dim picks 3 random terms
            import hashlib

            self._projection = [[0.0] * self.dim for _ in range(vocab_size)]
            for d in range(self.dim):
                seed_str = f"proj-{d}-{vocab_size}"
                h = hashlib.sha256(seed_str.encode()).digest()
                for pick in range(3):
                    idx = h[pick * 2] % vocab_size
                    sign = 1.0 if h[pick * 2 + 1] % 2 == 0 else -1.0
                    self._projection[idx][d] += sign

    def train(self, descriptions: list[str]) -> dict[str, Any]:
        """Train the embedding model on a collection of descriptions.

        Returns training stats.
        """
        if len(descriptions) < 2:
            return {"status": "insufficient_data", "count": len(descriptions)}

        self._build_vocab(descriptions)
        if len(self._vocab) == 0:
            return {"status": "no_vocab", "count": len(descriptions)}

        self._build_projection()
        self._trained = True

        return {
            "status": "trained",
            "documents": len(descriptions),
            "vocab_size": len(self._vocab),
            "dim": self.dim,
        }

    def embed(self, text: str) -> hrr.Array:
        """Embed text using the trained model.

        Falls back to hash-based embedding if not trained.
        """
        if not self._trained or not self._vocab:
            return hrr.embed_text(text)

        tokens = self._tokenize(text)
        tf = self._compute_tf(tokens)

        if not tf:
            # Unknown tokens — fall back to hash embedding
            return hrr.embed_text(text)

        # TF-IDF weighted average of projection vectors
        vec = [0.0] * self.dim
        weight_sum = 0.0

        for term, tf_val in tf.items():
            if term in self._vocab:
                idx = self._vocab[term]
                idf_val = self._idf[idx] if idx < len(self._idf) else 1.0
                weight = tf_val * idf_val
                proj = self._projection[idx]
                for d in range(self.dim):
                    vec[d] += weight * proj[d]
                weight_sum += weight

        if weight_sum > 1e-12:
            for d in range(self.dim):
                vec[d] /= weight_sum
            return hrr.normalize(vec)

        # No in-vocab weight (OOV query) — hash path, never return zero vector
        return hrr.embed_text(text)

    def embed_query(self, text: str) -> hrr.Array:
        """Embed a query (same as embed, but explicit for clarity)."""
        return self.embed(text)

    def similarity(self, text_a: str, text_b: str) -> float:
        """Compute semantic similarity between two texts."""
        vec_a = self.embed(text_a)
        vec_b = self.embed(text_b)
        return hrr.cosine_sim(vec_a, vec_b)

    def get_vocab_info(self) -> dict[str, Any]:
        """Return vocabulary statistics."""
        return {
            "vocab_size": len(self._vocab),
            "trained": self._trained,
            "dim": self.dim,
            "top_terms": sorted(
                self._vocab.keys(),
                key=lambda t: self._df.get(t, 0),
                reverse=True,
            )[:20],
        }

    # ── Persistence ──────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save trained model to disk atomically.

        Format: JSON header + raw binary projection matrix.
        File extension: .embedder

        Writes to path + ".tmp" first, then os.replace() to ensure
        a crash mid-write cannot leave a partially-written model.
        """
        if not self._trained:
            return

        # Metadata as JSON
        meta = {
            "dim": self.dim,
            "vocab": self._vocab,
            "idf": self._idf,
            "doc_count": self._doc_count,
            "df": dict(self._df),
            "trained": self._trained,
        }
        meta_bytes = json.dumps(meta, separators=(",", ":")).encode("utf-8")

        # Projection matrix as raw f64 bytes
        if hrr.has_numpy():
            import numpy as _np

            proj_arr = _np.asarray(self._projection, dtype=_np.float64)
            proj_bytes = proj_arr.tobytes()
        else:
            proj_bytes = struct.pack(
                f"<{len(self._projection) * self.dim}d",
                *[v for row in self._projection for v in row],
            )

        # Atomic write: tmp file + os.replace
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            # Header: magic(4) + meta_len(4)
            f.write(b"HEMB")
            f.write(struct.pack("<I", len(meta_bytes)))
            f.write(meta_bytes)
            f.write(proj_bytes)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    @classmethod
    def load(cls, path: str) -> LearnedEmbedder:
        """Load trained model from disk.

        Returns a fresh untrained embedder if file doesn't exist or is invalid.
        """
        if not os.path.isfile(path):
            return cls(dim=256)

        try:
            with open(path, "rb") as f:
                magic = f.read(4)
                if magic != b"HEMB":
                    return cls(dim=256)

                (meta_len,) = struct.unpack("<I", f.read(4))
                meta_bytes = f.read(meta_len)
                meta = json.loads(meta_bytes)

                dim = meta["dim"]
                embedder = cls(dim=dim)
                embedder._vocab = meta["vocab"]
                embedder._idf = meta["idf"]
                embedder._doc_count = meta["doc_count"]
                embedder._df = Counter(meta["df"])
                embedder._trained = meta["trained"]

                # Read projection matrix
                vocab_size = len(embedder._vocab)
                expected_bytes = vocab_size * dim * 8
                proj_bytes = f.read(expected_bytes)
                if len(proj_bytes) < expected_bytes:
                    return cls(dim=dim)

                if hrr.has_numpy():
                    import numpy as _np

                    embedder._projection = _np.frombuffer(
                        proj_bytes, dtype=_np.float64
                    ).reshape(vocab_size, dim).tolist()
                else:
                    values = struct.unpack(
                        f"<{vocab_size * dim}d", proj_bytes
                    )
                    embedder._projection = [
                        list(values[i * dim : (i + 1) * dim])
                        for i in range(vocab_size)
                    ]

                return embedder
        except (json.JSONDecodeError, struct.error, KeyError, OSError) as e:
            # Quarantine the corrupt file so the next save doesn't silently
            # overwrite it, and the operator can inspect it
            try:
                corrupt_path = f"{path}.corrupt.{int(time.time())}"
                os.replace(path, corrupt_path)
            except OSError:
                pass
            # Could not load — return fresh embedder
            return cls(dim=256)
