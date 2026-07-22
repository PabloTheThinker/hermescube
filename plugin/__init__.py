"""HermesCube plugin shim under plugin/ (legacy install path).

Prefer repo-root ``__init__.py`` + ``plugin.yaml`` for
``hermes plugins install PabloTheThinker/hermescube``.
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


def _ensure_package_installed() -> None:
    _ensure_import_path()
    try:
        import hermescube  # noqa: F401
        return
    except ImportError:
        pass
    import subprocess

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", f"{_ROOT}[numpy]", "-q"]
        )
    except Exception:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", str(_ROOT), "-q"]
        )
    _ensure_import_path()
    import hermescube  # noqa: F401


def register(ctx) -> None:
    _ensure_package_installed()
    from hermescube.provider import CubeMemoryProvider, _load_plugin_config

    config = _load_plugin_config()
    auto = config.get("auto_extract", False)
    if isinstance(auto, str):
        auto = auto.lower() in ("true", "1", "yes", "on")
    else:
        auto = bool(auto)

    provider = CubeMemoryProvider(auto_extract=auto)
    ctx.register_memory_provider(provider)
    logger.info("HermesCube memory provider registered (plugin/ shim)")
