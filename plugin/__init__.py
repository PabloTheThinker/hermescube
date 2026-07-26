"""HermesCube plugin shim under plugin/ (legacy install path).

Prefer repo-root ``__init__.py`` + ``plugin.yaml`` for
``hermes plugins install PabloTheThinker/hermescube``.

Package installation belongs to the installer; ``register()`` only
ensures the plugin tree is importable.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# plugin/ → repo root
_ROOT = Path(__file__).resolve().parent.parent


def _ensure_import_path() -> None:
    root = str(_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def register(ctx) -> None:
    _ensure_import_path()
    try:
        from hermescube.provider import CubeMemoryProvider, _load_plugin_config
    except ImportError as e:
        logger.error(
            "HermesCube package not importable (%s). Run ./scripts/install_hermes.sh",
            e,
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
    logger.info("HermesCube memory provider registered (plugin/ shim)")
