"""HermesCube memory plugin entry — works when installed via:

  hermes plugins install PabloTheThinker/hermescube

into ``$HERMES_HOME/plugins/hermescube/`` (full repo clone), **or** when
only this file is copied by ``scripts/install_hermes.sh``.

User data always lives under the **user's** Hermes home::

  $HERMES_HOME/memories/memory.cube

Never under the git checkout / project folder.
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


def _ensure_package_installed() -> None:
    """If hermescube isn't importable, pip-install this tree into the active env."""
    _ensure_import_path()
    try:
        import hermescube  # noqa: F401
        return
    except ImportError:
        pass
    import subprocess

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-e",
        f"{_ROOT}[numpy]",
        "-q",
    ]
    logger.info("HermesCube: installing package into active Python: %s", sys.executable)
    try:
        subprocess.check_call(cmd)
    except Exception:
        # numpy optional — try bare editable
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-e", str(_ROOT), "-q"]
        )
    _ensure_import_path()
    import hermescube  # noqa: F401


def register(ctx) -> None:
    """Register HermesCube as a MemoryProvider (Hermes plugin contract)."""
    _ensure_package_installed()
    from hermescube.provider import CubeMemoryProvider, _load_plugin_config, _coerce_bool

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
        "(tools: hermescube_search, hermescube_manage, hermescube_feedback)"
    )
