"""Engram Net unit tests."""

from __future__ import annotations

import math
from pathlib import Path

from hermescube.engram_net import EngramNet, _cos, _mean_vec


def test_mean_and_cos():
    a = [1.0, 0.0, 0.0]
    b = [1.0, 0.0, 0.0]
    assert _cos(a, b) > 0.99
    m = _mean_vec([a, [0.0, 1.0, 0.0]])
    assert m is not None
    assert abs(math.sqrt(sum(x * x for x in m)) - 1.0) < 1e-6


def test_hebbian_and_boost(tmp_path: Path):
    net = EngramNet(tmp_path / "engram_net.json")
    net.learn_coactivation(
        ["a", "b", "c"],
        vectors=[[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
        strength=1.0,
    )
    boosts = net.association_boosts([1.0, 0.0], ["a", "b", "z"])
    assert boosts["a"] >= 1.0
    assert boosts["b"] >= 1.0
    assert boosts["z"] == 1.0
    net.learn_feedback(["a", "b"], helpful=True)
    net.save()
    net2 = EngramNet(tmp_path / "engram_net.json")
    st = net2.stats()
    assert st["patterns"] >= 1
    assert st["edges"] >= 1


def test_unhelpful_weakens(tmp_path: Path):
    net = EngramNet(tmp_path / "e.json")
    net.learn_coactivation(["x", "y"], strength=2.0)
    before = (net._edges.get("x") or {}).get("y", 0)
    net.learn_feedback(["x", "y"], helpful=False)
    after = (net._edges.get("x") or {}).get("y", 0)
    assert after < before or "y" not in (net._edges.get("x") or {})
