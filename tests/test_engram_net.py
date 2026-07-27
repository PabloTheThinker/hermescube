"""Engram Net unit tests."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import pytest

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
    v1 = [1.0] + [0.0] * 255
    v2 = [0.9, 0.1] + [0.0] * 254
    v3 = [0.0, 1.0] + [0.0] * 254
    net.learn_coactivation(["a", "b", "c"], [v1, v2, v3], strength=1.0)
    boosts = net.association_boosts(v1, ["a", "b", "c", "z"])
    assert boosts["a"] >= 1.0
    assert boosts["b"] >= 1.0
    net.save()
    net2 = EngramNet(tmp_path / "engram_net.json")
    assert net2.stats()["patterns"] >= 1
    assert net2.stats()["edges"] >= 2


def test_unhelpful_weakens(tmp_path: Path):
    net = EngramNet(tmp_path / "engram_net.json")
    net.learn_coactivation(["x", "y"], strength=2.0)
    before = (net._edges.get("x") or {}).get("y", 0)
    net.learn_feedback(["x", "y"], helpful=False)
    after = (net._edges.get("x") or {}).get("y", 0)
    assert after < before or "y" not in (net._edges.get("x") or {})


def test_save_survives_concurrent_learning(tmp_path):
    """save() serialised _edges outside the lock, so a concurrent
    learn_coactivation() raised "dictionary changed size during iteration".
    Callers swallow exceptions, so learning was silently lost."""
    import threading

    net = EngramNet(tmp_path / "engram_net.json")
    errors: list[str] = []
    stop = threading.Event()

    def writer() -> None:
        i = 0
        while not stop.is_set():
            i += 1
            net.learn_coactivation(
                [f"id{i % 400}", f"id{(i * 7) % 400}", f"id{(i * 13) % 400}"],
                strength=0.4,
            )

    def saver() -> None:
        while not stop.is_set():
            try:
                net._dirty = True
                net.save()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=writer) for _ in range(2)]
    threads += [threading.Thread(target=saver) for _ in range(2)]
    for t in threads:
        t.start()
    time.sleep(1.0)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    assert errors == [], f"{len(errors)} save failures, e.g. {errors[:2]}"
    assert net.path.is_file()
    json.loads(net.path.read_text())
    assert not list(net.path.parent.glob("*.tmp"))


def test_decay_edges_prunes_weak_and_scales_strong(tmp_path):
    net = EngramNet(tmp_path / "engram_net.json")
    net.learn_coactivation(["a", "b"], strength=1.0)  # 0.15
    strong_before = net._edges["a"]["b"]
    pruned = net.decay_edges(0.5, floor=0.08)
    assert pruned == 2  # a->b and b->a fall to 0.075, below floor
    assert not net._edges.get("a")
    net.learn_coactivation(["c", "d"], strength=4.0)  # 0.60
    net.decay_edges(0.9, floor=0.08)
    assert net._edges["c"]["d"] == pytest.approx(0.54)
    assert strong_before > 0
