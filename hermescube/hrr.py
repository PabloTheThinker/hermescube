"""HRR algebra primitives — bind, unbind, superpose, embed.

Holographic Reduced Representations (Plate 1995):
- bind(a, b) ≈ circular convolution
- unbind(c, b) ≈ circular correlation (approximate inverse)
- superpose(list) = sum + normalize

Numpy auto-detect with pure-Python fallback for all ops.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any

DEFAULT_DIM = 256

# ── Backend detection ─────────────────────────────────────────────────

_HAS_NUMPY = False
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _np = None  # type: ignore[assignment]


def has_numpy() -> bool:
    return _HAS_NUMPY


Array = list[float] | Any  # Any = np.ndarray at runtime


def _to_list(v: Array) -> list[float]:
    return list(v) if isinstance(v, (list, tuple)) else v.tolist()


# ── NumPy ops ─────────────────────────────────────────────────────────


def _numpy_dot(a: "_np.ndarray", b: "_np.ndarray") -> float:
    return float(_np.dot(a, b))


def _numpy_norm(v: "_np.ndarray") -> float:
    return float(_np.linalg.norm(v))


def _numpy_normalize(v: "_np.ndarray") -> "_np.ndarray":
    n = _np.linalg.norm(v)
    if n < 1e-12:
        return v
    return v / n


def _numpy_cosine_sim(a: "_np.ndarray", b: "_np.ndarray") -> float:
    na = _np.linalg.norm(a)
    nb = _np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(_np.dot(a, b) / (na * nb))


def _numpy_bind(a: "_np.ndarray", b: "_np.ndarray") -> "_np.ndarray":
    fa = _np.fft.fft(a)
    fb = _np.fft.fft(b)
    return _np.real(_np.fft.ifft(fa * fb))


def _numpy_unbind(c: "_np.ndarray", b: "_np.ndarray") -> "_np.ndarray":
    fc = _np.fft.fft(c)
    fb = _np.fft.fft(b)
    return _np.real(_np.fft.ifft(fc * _np.conj(fb)))


def _numpy_superpose(vectors: list["_np.ndarray"]) -> "_np.ndarray":
    if not vectors:
        return _np.zeros(DEFAULT_DIM, dtype=_np.float64)
    return _numpy_normalize(sum(vectors))


# ── Pure-Python ops ───────────────────────────────────────────────────


def _pure_dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _pure_norm(v: list[float]) -> float:
    return math.sqrt(_pure_dot(v, v))


def _pure_normalize(v: list[float]) -> list[float]:
    n = _pure_norm(v)
    if n < 1e-12:
        return v
    return [x / n for x in v]


def _pure_cosine_sim(a: list[float], b: list[float]) -> float:
    na = _pure_norm(a)
    nb = _pure_norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return _pure_dot(a, b) / (na * nb)


def _pure_bind(a: list[float], b: list[float]) -> list[float]:
    dim = len(a)
    result = [0.0] * dim
    for i in range(dim):
        s = 0.0
        for j in range(dim):
            k = (i - j) % dim
            s += a[j] * b[k]
        result[i] = s
    return _pure_normalize(result)


def _pure_unbind(c: list[float], b: list[float]) -> list[float]:
    dim = len(c)
    result = [0.0] * dim
    for i in range(dim):
        s = 0.0
        for j in range(dim):
            k = (j - i) % dim
            s += c[j] * b[k]
        result[i] = s
    return _pure_normalize(result)


def _pure_superpose(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.0] * DEFAULT_DIM
    dim = len(vectors[0])
    s = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            s[i] += v[i]
    return _pure_normalize(s)


# ── Public API (auto-selects backend) ─────────────────────────────────


def zero_vector(dim: int = DEFAULT_DIM) -> Array:
    if _HAS_NUMPY:
        return _np.zeros(dim, dtype=_np.float64)
    return [0.0] * dim


def dot(a: Array, b: Array) -> float:
    if _HAS_NUMPY:
        return _numpy_dot(_np.asarray(a, dtype=_np.float64), _np.asarray(b, dtype=_np.float64))
    return _pure_dot(_to_list(a), _to_list(b))


def norm(v: Array) -> float:
    if _HAS_NUMPY:
        return _numpy_norm(_np.asarray(v, dtype=_np.float64))
    return _pure_norm(_to_list(v))


def normalize(v: Array) -> Array:
    if _HAS_NUMPY:
        return _numpy_normalize(_np.asarray(v, dtype=_np.float64))
    return _pure_normalize(_to_list(v))


def cosine_sim(a: Array, b: Array) -> float:
    if _HAS_NUMPY:
        return _numpy_cosine_sim(_np.asarray(a, dtype=_np.float64), _np.asarray(b, dtype=_np.float64))
    return _pure_cosine_sim(_to_list(a), _to_list(b))


def bind(a: Array, b: Array) -> Array:
    if _HAS_NUMPY:
        return _numpy_bind(_np.asarray(a, dtype=_np.float64), _np.asarray(b, dtype=_np.float64))
    return _pure_bind(_to_list(a), _to_list(b))


def unbind(c: Array, b: Array) -> Array:
    if _HAS_NUMPY:
        return _numpy_unbind(_np.asarray(c, dtype=_np.float64), _np.asarray(b, dtype=_np.float64))
    return _pure_unbind(_to_list(c), _to_list(b))


def superpose(vectors: list[Array]) -> Array:
    if _HAS_NUMPY:
        np_vectors = [_np.asarray(v, dtype=_np.float64) for v in vectors]
        return _numpy_superpose(np_vectors)
    return _pure_superpose([_to_list(v) for v in vectors])


# ── Embedding ─────────────────────────────────────────────────────────


def embed_text(text: str, dim: int = DEFAULT_DIM) -> Array:
    """Deterministic hash embedding (Hermespace-compatible).

    Maps text → unit vector in dim-space using SHA-256 hashing.
    Identical to hermespace.neural_field.embed_text().
    """
    if _HAS_NUMPY:
        v = _np.zeros(dim, dtype=_np.float64)
    else:
        v = [0.0] * dim

    toks = re.findall(r"[a-z0-9_]+", (text or "").lower())
    if not toks:
        toks = ["_empty"]

    for tok in toks:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        for i in range(0, min(32, len(h) - 1), 2):
            idx = int.from_bytes(h[i : i + 2], "little") % dim
            sign = 1.0 if h[(i + 2) % len(h)] % 2 == 0 else -1.0
            v[idx] += sign

    for a, b in zip(toks, toks[1:]):
        h = hashlib.sha256(f"{a}#{b}".encode()).digest()
        idx = int.from_bytes(h[:2], "little") % dim
        v[idx] += 1.0

    return normalize(v)
