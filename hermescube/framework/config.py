"""Config loading for HermesCube (Hermes config.yaml plugin block)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def coerce_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "yes", "on")
    return default


def load_plugin_config(hermes_home: str | None = None) -> dict[str, Any]:
    """Read hermescube block from config.yaml. Empty dict on failure."""
    try:
        if hermes_home:
            config_path = Path(hermes_home) / "config.yaml"
        else:
            try:
                from hermes_constants import get_hermes_home as _get_home

                config_path = Path(str(_get_home())) / "config.yaml"
            except Exception:
                config_path = Path.home() / ".hermes" / "config.yaml"
        if not config_path.exists():
            return {}
        import yaml

        with open(config_path, encoding="utf-8-sig") as f:
            all_config = yaml.safe_load(f) or {}
        memory = all_config.get("memory", {})
        if isinstance(memory, dict) and "hermescube" in memory:
            return dict(memory["hermescube"])
        plugins = all_config.get("plugins", {})
        if isinstance(plugins, dict) and "hermescube" in plugins:
            return dict(plugins["hermescube"])
        return {}
    except Exception:
        return {}


def query_rewrite_enabled(config: dict[str, Any] | None = None) -> bool:
    """Default OFF (Quicksilver). Env HERMESCUBE_QUERY_REWRITE=1 forces on."""
    env = os.environ.get("HERMESCUBE_QUERY_REWRITE", "").strip().lower()
    if env in ("1", "true", "yes", "on"):
        return True
    if env in ("0", "false", "no", "off"):
        return False
    if config is None:
        return False
    return coerce_bool(config.get("query_rewrite"), False)
