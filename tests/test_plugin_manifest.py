"""The installer ships root plugin.yaml; plugin/plugin.yaml is a legacy-path
copy. They had drifted to 0.13.0 vs 0.20.0 with six config keys missing from
the one that actually gets installed."""

from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def test_manifests_are_identical():
    a = (ROOT / "plugin.yaml").read_text(encoding="utf-8")
    b = (ROOT / "plugin" / "plugin.yaml").read_text(encoding="utf-8")
    assert a == b, "root plugin.yaml and plugin/plugin.yaml have drifted"


def test_manifest_version_matches_package():
    from hermescube import __version__

    assert _load("plugin.yaml")["version"] == __version__


def test_manifest_declares_every_documented_config_key():
    cfg = _load("plugin.yaml")["config"]
    required = {
        "auto_extract",
        "memory_policy",
        "char_limit",
        "conflict_detect",
        "dim",
        "evolve_interval",
        "l2_buckets",
        "living_pulse_on_session_end",
        "memory_nudge_interval",
        "observe_on_session_end",
        "peer_card_cadence_s",
        "query_rewrite",
        "replay_on_session_end",
        "session_digest",
    }
    assert required <= set(cfg), f"missing: {sorted(required - set(cfg))}"
    for key, spec in cfg.items():
        assert "type" in spec and "default" in spec, f"{key} lacks type/default"
