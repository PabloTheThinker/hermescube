"""HermesCube memory plugin entry — works when installed via:

  hermes plugins install PabloTheThinker/hermescube

into ``$HERMES_HOME/plugins/hermescube/`` (full repo clone), **or** when
only this file is copied by ``scripts/install_hermes.sh``.

User data always lives under the **user's** Hermes home::

  $HERMES_HOME/memories/memory.cube

Never under the git checkout / project folder.

Package installation belongs to the plugin installer / ``install_hermes.sh``.
``register()`` only ensures importability from the plugin tree.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent


def _ensure_import_path() -> None:
    """Make the hermescube package importable from a full-repo plugin clone."""
    root = str(_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def register(ctx) -> None:
    """Register HermesCube as a MemoryProvider (Hermes plugin contract)."""
    _ensure_import_path()
    try:
        from hermescube.provider import CubeMemoryProvider, _load_plugin_config
    except ImportError as e:
        logger.error(
            "HermesCube package not importable (%s). "
            "Run ./scripts/install_hermes.sh or: pip install -e \"%s[numpy]\"",
            e,
            _ROOT,
        )
        raise

    config = _load_plugin_config()
    auto = config.get("auto_extract", False)
    if isinstance(auto, str):
        auto = auto.lower() in ("true", "1", "yes", "on")
    else:
        auto = bool(auto)

    provider = CubeMemoryProvider(auto_extract=auto)
    ctx.register_memory_provider(provider)
    logger.info(
        "HermesCube memory provider registered "
        "(tools: hermescube_search, hermescube_manage, hermescube_feedback, hermescube_probe)"
    )
