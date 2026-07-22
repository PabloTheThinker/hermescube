"""HermesCube framework — how memory is housed and operates inside the cube.

Layers (all Cube-native; Hermes only provides MemoryProvider socket + HERMES_HOME):

  PATHS      resolve user-home cube/colony/board locations
  CONFIG     plugins.hermescube / memory.hermescube
  VOID       infinite-void recall: HAR + bio + mirror + colony stigmergy
  LEXINDEX   inverted token index for fast candidate generation (holo-class speed path)

Provider stays the Hermes adapter; framework is the operating system of the cube.
"""

from __future__ import annotations

from hermescube.framework.paths import CubePaths, resolve_cube_paths
from hermescube.framework.config import load_plugin_config, coerce_bool, query_rewrite_enabled
from hermescube.framework.void import CubeVoid
from hermescube.framework.lexindex import LexIndex

__all__ = [
    "CubePaths",
    "resolve_cube_paths",
    "load_plugin_config",
    "coerce_bool",
    "query_rewrite_enabled",
    "CubeVoid",
    "LexIndex",
]
