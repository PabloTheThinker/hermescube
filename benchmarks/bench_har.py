"""Benchmark HAR query speed and accuracy vs brute-force linear scan."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from typing import Any

try:
    from hermescube.cube import CubeFile
    from hermescube.har import HARQueryEngine
    from hermescube import hrr
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from hermescube.cube import CubeFile
    from hermescube.har import HARQueryEngine
    from hermescube import hrr

QUERIES = [
    "memory storage and retrieval system",
    "user authentication and login flow",
    "performance optimization and caching",
    "error handling and debugging",
    "database schema and migration",
]


def _scenario_entries(n: int, seed: int = 42) -> list[tuple[str, str]]:
    """Generate n diverse entries."""
    rng = _SimpleRNG(seed)
    topics = [
        "memory module", "authentication", "database", "cache layer",
        "API design", "frontend components", "deployment pipeline",
        "monitoring system", "search index", "notification service",
        "file storage", "rate limiting", "data validation",
        "background jobs", "webhook handler", "serialization format",
        "configuration management", "logging framework", "test harness",
        "dependency injection",
    ]
    actions = [
        "Fixed bug in", "Refactored", "Designed new", "Optimized",
        "Deployed", "Documented", "Removed deprecated", "Added tests for",
        "Reviewed", "Migrated",
    ]
    outcomes = ["success", "failure", "pending", "none"]

    entries: list[tuple[str, str]] = []
    for i in range(n):
        topic = topics[rng.next() % len(topics)]
        action = actions[rng.next() % len(actions)]
        outcome = outcomes[rng.next() % len(outcomes)]
        etype = "landmark" if rng.next() % 2 == 0 else "belief"
        desc = f"{action} {topic} (item {i})"
        entries.append((etype, desc))
    return entries


class _SimpleRNG:
    def __init__(self, seed: int):
        self.state = seed

    def next(self) -> int:
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state


def build_cube(entries: list[tuple[str, str]]) -> str:
    with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
        path = f.name
    cube = CubeFile.create(path)
    for etype, desc in entries:
        cube.append(etype, desc)
    cube.close()
    return path


def bench_speed(
    sizes: list[int] = [10, 100, 500, 1000],
    target_queries: int = 5,
) -> dict[str, Any]:
    """Measure HAR vs brute-force query latency at different archive sizes."""
    print(f"{'Entries':>8} {'HAR avg (ms)':>15} {'Scan avg (ms)':>15} {'Speedup':>10}")
    print("-" * 50)

    results: dict[str, Any] = {"by_size": {}}

    for n in sizes:
        entries = _scenario_entries(n)
        path = build_cube(entries)

        # Open + evolve to populate L2 (single handle — flock is exclusive)
        cube = CubeFile.open(path)
        engine = HARQueryEngine(cube)
        engine.evolve()

        # Force fallback scan on same handle (second open races flock)
        scan_engine = HARQueryEngine(cube)
        scan_engine._l2_centroids = []  # trigger fallback

        har_times: list[float] = []
        scan_times: list[float] = []

        for q in QUERIES[:target_queries]:
            t0 = time.perf_counter()
            engine.query(q, top_k=10)
            t1 = time.perf_counter()
            har_times.append((t1 - t0) * 1000)

            t0 = time.perf_counter()
            scan_engine.query(q, top_k=10)
            t1 = time.perf_counter()
            scan_times.append((t1 - t0) * 1000)

        har_avg = sum(har_times) / len(har_times)
        scan_avg = sum(scan_times) / len(scan_times)
        speedup = scan_avg / har_avg if har_avg > 0 else 0

        print(f"{n:>8} {har_avg:>15.3f} {scan_avg:>15.3f} {speedup:>10.2f}x")

        results["by_size"][n] = {
            "har_avg_ms": round(har_avg, 3),
            "scan_avg_ms": round(scan_avg, 3),
            "speedup": round(speedup, 2),
        }

        cube.close()
        # drop WAL sidecar if present
        for suffix in ("", ".cubelog"):
            p = path + suffix if suffix else path
            if os.path.isfile(p):
                os.unlink(p)

    return results


def bench_recall(
    n: int = 500,
    target_queries: int = 5,
) -> dict[str, Any]:
    """Measure HAR recall@K compared to brute-force as ground truth."""
    entries = _scenario_entries(n)
    path = build_cube(entries)

    cube = CubeFile.open(path)
    engine_har = HARQueryEngine(cube)
    engine_scan = HARQueryEngine(cube)
    engine_har.evolve()

    # Force scan engine to use fallback (same handle — exclusive flock)
    engine_scan._l2_centroids = []

    total_recall = 0.0
    total_precision = 0.0

    print(f"\nRecall@K ({n} entries):")
    print(f"{'Query':<35} {'Recall@10':>10} {'Precision@10':>12}")
    print("-" * 60)

    for q in QUERIES[:target_queries]:
        har_results = engine_har.query(q, top_k=10)
        scan_results = engine_scan.query(q, top_k=10)

        har_ids = {e.id for e, s in har_results}
        scan_ids = {e.id for e, s in scan_results}

        if not scan_ids:
            continue

        relevant = len(har_ids & scan_ids)
        recall = relevant / len(scan_ids)
        precision = relevant / len(har_ids) if har_ids else 0.0

        total_recall += recall
        total_precision += precision

        q_short = q[:33] + ".." if len(q) > 35 else q
        print(f"{q_short:<35} {recall:>10.3f} {precision:>12.3f}")

    avg_recall = total_recall / target_queries
    avg_precision = total_precision / target_queries
    print("-" * 60)
    print(f"{'Average':<35} {avg_recall:>10.3f} {avg_precision:>12.3f}")

    cube.close()
    for suffix in ("", ".cubelog"):
        p = path + suffix if suffix else path
        if os.path.isfile(p):
            os.unlink(p)

    return {"recall": round(avg_recall, 3), "precision": round(avg_precision, 3)}


def bench_append_speed(sizes: list[int] = [10, 100, 500]) -> None:
    """Measure append latency at different batch sizes."""
    print(f"\nAppend latency:")
    print(f"{'Batch':>8} {'Total (ms)':>12} {'Per entry (µs)':>15}")
    print("-" * 38)

    for n in sizes:
        entries = _scenario_entries(n)
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        cube = CubeFile.create(path)

        t0 = time.perf_counter()
        for etype, desc in entries:
            cube.append(etype, desc)
        dt = (time.perf_counter() - t0) * 1000

        per_entry = (dt / n) * 1000  # µs
        print(f"{n:>8} {dt:>12.3f} {per_entry:>15.1f}")
        cube.close()
        os.unlink(path)


if __name__ == "__main__":
    print("HermesCube Benchmark\n")
    print(f"Backend: {'numpy' if hrr.has_numpy() else 'pure-python'}")
    print()

    speed = bench_speed([10, 100, 500, 1000])
    recall = bench_recall(500)
    bench_append_speed([10, 100, 500])

    print(f"\nSummary:")
    print(f"  HAR query vs linear scan speedup: {speed['by_size'][500]['speedup']}x at 500 entries")
    print(f"  Recall@10: {recall['recall']}, Precision@10: {recall['precision']}")
