"""HermesCube — local deep-memory heart for Hermes Agent (+ Hermespace).

Binary `.cube` archive with holographic associative retrieval (HAR), Cuboasis
governance, living growth, optional Hive/HQ, CubeDream (solo + together),
``space_bridge`` (heart pump), and ``center`` (anatomical circulatory integration).

See ABOUT.md / PURPOSE.md / docs/HERMESPACE.md / docs/ANATOMY.md.
"""

__version__ = "0.49.0"

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
from hermescube import center
from hermescube import hive
from hermescube import self_evolution
from hermescube import hq
from hermescube import interview
from hermescube import genealogy
from hermescube import curator
from hermescube import cuboasis
from hermescube import cubewave
from hermescube import memory_gate
from hermescube import bootstrap
from hermescube import agent_manual
from hermescube import session_end
from hermescube import manage
from hermescube import manage_warehouse
from hermescube import manage_cuboasis
from hermescube import manage_growth
from hermescube import manage_fleet
from hermescube import manage_dream
from hermescube import dream
from hermescube import dream_circle
from hermescube import tools_recall
from hermescube import nexus  # backward-compat shim → cuboasis

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
    "center",
    "hive",
    "self_evolution",
    "hq",
    "interview",
    "genealogy",
    "curator",
    "cuboasis",
    "cubewave",
    "memory_gate",
    "bootstrap",
    "agent_manual",
    "session_end",
    "manage",
    "manage_warehouse",
    "manage_cuboasis",
    "manage_growth",
    "manage_fleet",
    "manage_dream",
    "dream",
    "dream_circle",
    "tools_recall",
    "nexus",
    "__version__",
]