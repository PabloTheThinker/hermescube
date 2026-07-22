"""HermesCube memory plugin — register with HermesAgent via register(ctx).

Usage:
    The plugin is discovered by HermesAgent from either:
    - Bundled: ``plugins/memory/hermescube/`` (in hermes-agent source tree)
    - User-installed: ``$HERMES_HOME/plugins/memory/hermescube/``

Activation:
    Set ``memory.provider: hermescube`` in ``$HERMES_HOME/config.yaml``.
    The MemoryManager will load, initialize, and wire this provider.

Config is read from ``config.yaml`` under ``plugins.hermescube``
(or ``memory.hermescube``), following the Holographic provider's pattern.

Tool names:
    hermescube_search   — HAR-powered semantic search
    hermescube_manage   — add/remove memories
    hermescube_feedback — rate entries (trains trust scores)
"""

import logging

logger = logging.getLogger(__name__)


def register(ctx) -> None:
    """Register HermesCube as a MemoryProvider with the plugin system.

    Called automatically by HermesAgent's plugin loader when this
    plugin is activated via ``memory.provider: hermescube``.

    Loads config from ``plugins.hermescube`` in config.yaml and
    passes it to the provider constructor — same pattern as the
    Holographic provider.
    """
    from hermescube.provider import CubeMemoryProvider, _load_plugin_config

    config = _load_plugin_config()
    provider = CubeMemoryProvider(
        auto_extract=config.get("auto_extract", "false").lower() in ("true", "1", "yes") if isinstance(config.get("auto_extract"), str) else bool(config.get("auto_extract", False)),
    )
    ctx.register_memory_provider(provider)

    logger.info(
        "HermesCube memory provider registered (3 tools: hermescube_search, "
        "hermescube_manage, hermescube_feedback)"
    )
