"""Path housing — all durable cube state under the user's Hermes home.

Hermes Agent passes an already profile-scoped ``hermes_home`` (see
``agent/agent_init.py``). Nesting again by ``agent_identity`` /
``agent_workspace`` double-scopes paths and desyncs CLI/docs from the
runtime cube. Treat ``hermes_home`` as the complete storage root.

Optional ``nest_profiles=True`` remains for explicit multi-identity
sandboxes that share one unscoped home (tests / advanced ops only).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CubePaths:
    hermes_home: Path
    memories_dir: Path
    cube: Path
    cubelog: Path
    embedder: Path
    colony_graph: Path
    colony_board: Path
    branches_dir: Path
    consolidate_dir: Path
    ingest_cursor: Path

    def ensure(self) -> None:
        self.memories_dir.mkdir(parents=True, exist_ok=True)


def resolve_cube_paths(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> CubePaths:
    """Resolve durable cube paths under Hermes home.

    Default: ``$HERMES_HOME/memories/memory.cube`` (Hermes already scopes home).
    When ``nest_profiles=True``, optionally nest
    ``memories/profiles/<identity>/<workspace>/`` for explicit isolation.
    """
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    mem = home / "memories"
    if nest_profiles:
        if agent_identity:
            mem = mem / "profiles" / agent_identity
        if agent_workspace:
            mem = mem / agent_workspace
    return CubePaths(
        hermes_home=home,
        memories_dir=mem,
        cube=mem / "memory.cube",
        cubelog=mem / "memory.cube.cubelog",
        embedder=mem / "memory.embedder",
        colony_graph=mem / "colony_graph.json",
        colony_board=mem / "COLONY.md",
        branches_dir=mem / "branches",
        consolidate_dir=mem / "consolidate",
        ingest_cursor=mem / "ingest_cursor.json",
    )
