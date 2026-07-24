"""Tests for sleep_replay consolidation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hermescube.engram_net import EngramNet
from hermescube.sleep_replay import sleep_replay


def test_sleep_replay_bundles(tmp_path: Path):
    net = EngramNet(tmp_path / "engram.json")

    def E(i, desc, et="landmark"):
        # unit vector-ish
        v = [0.0] * 8
        v[i % 8] = 1.0
        return SimpleNamespace(id=f"e{i}", description=desc, entry_type=et, outcome="success", vector=v, timestamp="")

    class FakeCube:
        def read_l1(self):
            return [
                E(0, "deploy production hotfix auth login security"),
                E(1, "deploy production release pipeline auth"),
                E(2, "user prefers dark mode editor style"),
                E(3, "user prefers concise style responses"),
                E(4, "random unrelated fishing boat weather"),
            ]

    stats = sleep_replay(FakeCube(), net, max_patterns=10, min_bundle=2)
    assert stats["entries_scanned"] == 5
    assert stats["bundles"] >= 1
    assert net.stats()["patterns"] >= 1
