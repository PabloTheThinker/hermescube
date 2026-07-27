"""HermesCube — binary columnar archive with holographic associative retrieval."""

__version__ = "0.34.0"

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
from hermescube.events import MemoryEvent, make_event
from hermescube.claims import Claim, make_claim
from hermescube import bio_rank
from hermescube import space_bridge
from hermescube import hive
from hermescube import self_evolution
from hermescube import hq
from hermescube import interview
from hermescube import genealogy
from hermescube import curator

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
    "MemoryEvent",
    "make_event",
    "Claim",
    "make_claim",
    "bio_rank",
    "space_bridge",
    "hive",
    "self_evolution",
    "hq",
    "interview",
    "genealogy",
    "curator",
    "__version__",
]