"""Path housing — all durable cube state under the user's Hermes home."""

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

    def ensure(self) -> None:
        self.memories_dir.mkdir(parents=True, exist_ok=True)


def resolve_cube_paths(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
) -> CubePaths:
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    mem = home / "memories"
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
    )
