"""HermesCube — binary columnar archive with holographic associative retrieval."""

__version__ = "0.6.0"

from hermescube.hrr import (
    Array,
    bind,
    cosine_sim,
    dot,
    embed_text,
    has_numpy,
    norm,
    normalize,
    superpose,
    unbind,
    zero_vector,
)
from hermescube.cube import CubeEntry, CubeFile
from hermescube.har import HARQueryEngine
from hermescube.embed import LearnedEmbedder
from hermescube.provider import CubeMemoryProvider
from hermescube.threats import scan_text, has_blockable_threat, sanitize_for_storage
from hermescube import bio_rank

__all__ = [
    "Array",
    "bind",
    "cosine_sim",
    "dot",
    "embed_text",
    "has_numpy",
    "norm",
    "normalize",
    "superpose",
    "unbind",
    "zero_vector",
    "CubeEntry",
    "CubeFile",
    "HARQueryEngine",
    "LearnedEmbedder",
    "CubeMemoryProvider",
    "scan_text",
    "has_blockable_threat",
    "sanitize_for_storage",
    "bio_rank",
    "__version__",
]