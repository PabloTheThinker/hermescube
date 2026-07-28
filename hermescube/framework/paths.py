"""Path housing — all durable cube state under the user's Hermes home.

Hermes Agent often passes an already profile-scoped ``hermes_home``. Nesting
again by identity/workspace would double-scope. Default: use
``$HERMES_HOME/memories/``.

When both ``agent_identity`` and ``agent_workspace`` are set *and*
``nest_profiles=True`` (provider enables this for multi-workspace homes),
compounding **sidecars** live under
``memories/profiles/<identity>/<workspace>/`` so two workspaces sharing one
unscoped ``HERMES_HOME`` do not bleed engram/yield/relations/journey state.

The ``.cube`` warehouse stays at ``memories/memory.cube`` (shared) so vault
tags can soft-filter across workspaces without losing unlabeled legacy recall.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CubePaths:
    hermes_home: Path
    memories_dir: Path
    sidecar_dir: Path
    cube: Path
    cubelog: Path
    embedder: Path
    colony_graph: Path
    colony_board: Path
    branches_dir: Path
    consolidate_dir: Path
    ingest_cursor: Path
    engram: Path
    yield_gradient: Path
    relations: Path
    triage_plan: Path
    journey_events: Path
    journey_md: Path
    living_state: Path
    catalog: Path
    progress_ledger: Path
    candidates_ledger: Path
    cuboasis_state: Path
    cubewave: Path
    peer_card: Path
    # Legacy alias kept for callers that still read nexus_state
    nexus_state: Path

    def ensure(self) -> None:
        self.memories_dir.mkdir(parents=True, exist_ok=True)
        if self.sidecar_dir.resolve() != self.memories_dir.resolve():
            self.sidecar_dir.mkdir(parents=True, exist_ok=True)


def sidecar_dir(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    """Directory that holds compounding sidecars (engram, relations, …)."""
    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).sidecar_dir


def resolve_cube_paths(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> CubePaths:
    """Resolve durable cube + sidecar paths under Hermes home.

    Default: ``$HERMES_HOME/memories/memory.cube`` with sidecars alongside.
    When ``nest_profiles=True``, sidecars nest under
    ``memories/profiles/<identity>/<workspace>/``; the cube stays shared.
    """
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    mem = home / "memories"
    side = mem
    if nest_profiles:
        if agent_identity:
            side = side / "profiles" / _safe_seg(agent_identity)
        if agent_workspace:
            side = side / _safe_seg(agent_workspace)
    return CubePaths(
        hermes_home=home,
        memories_dir=mem,
        sidecar_dir=side,
        cube=mem / "memory.cube",
        cubelog=mem / "memory.cube.cubelog",
        embedder=mem / "memory.embedder",
        colony_graph=mem / "colony_graph.json",
        colony_board=mem / "COLONY.md",
        branches_dir=mem / "branches",
        consolidate_dir=mem / "consolidate",
        ingest_cursor=mem / "ingest_cursor.json",
        engram=side / "engram_net.json",
        yield_gradient=side / "yield_gradient.json",
        relations=side / "relations.sqlite3",
        triage_plan=side / "triage_plan.json",
        journey_events=side / "journey.jsonl",
        journey_md=side / "journey.md",
        living_state=side / "living_state.json",
        catalog=side / "catalog.json",
        progress_ledger=side / "progress.jsonl",
        candidates_ledger=side / "candidates.jsonl",
        cuboasis_state=side / "cuboasis_state.json",
        cubewave=side / "cubewave.json",
        peer_card=side / "peer_card.json",
        nexus_state=side / "nexus_state.json",
    )


def _safe_seg(name: str) -> str:
    s = "".join(c if c.isalnum() or c in "-_." else "_" for c in (name or "").strip())
    return s[:80] or "default"


def should_nest_profiles(agent_identity: str = "", agent_workspace: str = "") -> bool:
    """Nest when both identity and workspace are present (multi-ws under one home)."""
    return bool((agent_identity or "").strip() and (agent_workspace or "").strip())


_LEGACY_SIDE_CARS = (
    ("engram_net.json", "engram"),
    ("yield_gradient.json", "yield_gradient"),
    ("relations.sqlite3", "relations"),
    ("triage_plan.json", "triage_plan"),
    ("journey.jsonl", "journey_events"),
    ("journey.md", "journey_md"),
    ("living_state.json", "living_state"),
    ("catalog.json", "catalog"),
    ("progress.jsonl", "progress_ledger"),
    ("candidates.jsonl", "candidates_ledger"),
    ("cuboasis_state.json", "cuboasis_state"),
    ("cubewave.json", "cubewave"),
    ("peer_card.json", "peer_card"),
    ("nexus_state.json", "nexus_state"),
)


def migrate_legacy_sidecars(paths: CubePaths) -> list[str]:
    """Copy legacy ``memories/*`` sidecars into a nested profile dir once.

    Never deletes the legacy files. Returns list of copied basenames.
    """
    legacy_root = paths.memories_dir
    if paths.sidecar_dir.resolve() == legacy_root.resolve():
        return []
    paths.ensure()
    copied: list[str] = []
    for name, attr in _LEGACY_SIDE_CARS:
        src = legacy_root / name
        dst = getattr(paths, attr)
        if src.is_file() and not Path(dst).exists():
            try:
                Path(dst).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(name)
                logger.info("migrated sidecar %s → %s", src, dst)
            except OSError as e:
                logger.debug("sidecar migrate skip %s: %s", name, e)
    return copied
