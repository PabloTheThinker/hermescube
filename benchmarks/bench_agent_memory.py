"""Agent memory benchmark — realistic HermesCube stress test.

Generates synthetic agent memories (conversations, decisions, events,
beliefs, traits) and benchmarks HAR query performance, recall, and
scalability against brute-force linear scan.
"""

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

# ── Memory generation ────────────────────────────────────────────────

TOPICS = [
    "memory system", "authentication flow", "database schema",
    "deployment pipeline", "API design", "frontend components",
    "monitoring alerts", "cache invalidation", "rate limiting",
    "user onboarding", "payment processing", "email notifications",
    "file storage", "search indexing", "background jobs",
    "webhook handling", "data validation", "logging framework",
    "test coverage", "dependency management", "security audit",
    "performance profiling", "error handling", "configuration management",
    "feature flags", "A/B testing", "analytics dashboard",
    "user feedback", "documentation", "code review",
]

ACTIONS = [
    "Fixed bug in", "Refactored", "Designed new", "Optimized",
    "Deployed", "Documented", "Removed deprecated", "Added tests for",
    "Reviewed", "Migrated", "Debugged", "Implemented", "Configured",
    "Monitored", "Upgraded", "Reverted", "Simplified", "Extended",
]

SUBJECTS = [
    "the user asked about", "the team discussed", "we decided on",
    "the client requested", "the system detected", "the audit found",
    "the benchmark showed", "the logs revealed", "the user reported",
    "the tests caught", "the monitoring flagged", "the review found",
]

OUTCOMES = ["none", "success", "failure", "pending", "superseded"]

DATA_TEMPLATES = [
    {"confidence": 0.95, "source": "conversation"},
    {"confidence": 0.80, "source": "code_review", "pr": "1234"},
    {"confidence": 0.70, "source": "monitoring", "alert_id": "5678"},
    {"confidence": 0.60, "source": "user_feedback", "rating": 4},
    {"confidence": 0.85, "source": "automated_test", "suite": "integration"},
    {"confidence": 0.90, "source": "deployment_log", "env": "production"},
    {"confidence": 0.75, "source": "security_scan", "severity": "medium"},
    {"confidence": 0.65, "source": "performance_profile", "p99_ms": 450},
]


class _LCG:
    """Deterministic PRNG for reproducible benchmarks."""
    def __init__(self, seed: int = 42):
        self.state = seed

    def next(self) -> int:
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state

    def choice(self, seq: list) -> Any:
        return seq[self.next() % len(seq)]


def generate_memories(n: int, seed: int = 42) -> list[tuple[str, str, dict, str]]:
    """Generate n realistic agent memories."""
    rng = _LCG(seed)
    memories = []

    for i in range(n):
        topic = rng.choice(TOPICS)
        action = rng.choice(ACTIONS)
        subject = rng.choice(SUBJECTS)
        outcome = rng.choice(OUTCOMES)
        data = dict(rng.choice(DATA_TEMPLATES))

        # Vary entry types realistically
        roll = rng.next() % 100
        if roll < 30:
            etype = "landmark"
            desc = f"{action} {topic} — {subject} production issue #{i}"
        elif roll < 50:
            etype = "belief"
            desc = f"{subject} {topic} needs attention — lesson learned from iteration {i}"
        elif roll < 65:
            etype = "trait"
            desc = f"The user consistently asks about {topic} and prefers {rng.choice(['detailed', 'concise', 'visual', 'step-by-step'])} explanations"
        elif roll < 80:
            etype = "resolve"
            desc = f"Resolved {topic} issue — {action.lower()} the affected module after {subject} the root cause"
        elif roll < 90:
            etype = "focus"
            desc = f"Currently prioritizing {topic} improvements — sprint goal for week {i % 12}"
        else:
            etype = "evolution"
            desc = f"System understanding evolved — {topic} architecture changed from monolith to microservices"

        memories.append((etype, desc, data, outcome))

    return memories


# ── Queries ──────────────────────────────────────────────────────────

QUERIES = [
    ("what bugs were fixed?", "landmark"),
    ("user preferences and habits", "trait"),
    ("authentication and security", None),
    ("deployment and production issues", None),
    ("what did the team decide on?", None),
    ("performance problems", None),
    ("what needs attention?", "focus"),
    ("completed tasks", "resolve"),
    ("how has the system evolved?", "evolution"),
    ("database and storage", None),
    ("monitoring and alerts", None),
    ("what lessons were learned?", "belief"),
]


# ── Benchmarks ───────────────────────────────────────────────────────

def build_cube(memories: list[tuple[str, str, dict, str]]) -> str:
    with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
        path = f.name
    cube = CubeFile.create(path)
    for etype, desc, data, outcome in memories:
        cube.append(etype, desc, data=data, outcome=outcome)
    cube.close()
    return path


def bench_query_latency(
    n_entries: int = 1000,
    n_queries: int = 12,
) -> dict[str, Any]:
    """Measure HAR vs brute-force query latency."""
    memories = generate_memories(n_entries)
    path = build_cube(memories)

    cube = CubeFile.open(path)
    engine = HARQueryEngine(cube)
    engine.evolve()

    # Force fallback scan on same handle (exclusive flock)
    scan_engine = HARQueryEngine(cube)
    scan_engine._l2_centroids = []

    har_times: list[float] = []
    scan_times: list[float] = []

    for q_text, _ in QUERIES[:n_queries]:
        t0 = time.perf_counter()
        engine.query(q_text, top_k=10)
        t1 = time.perf_counter()
        har_times.append((t1 - t0) * 1000)

        t0 = time.perf_counter()
        scan_engine.query(q_text, top_k=10)
        t1 = time.perf_counter()
        scan_times.append((t1 - t0) * 1000)

    har_avg = sum(har_times) / len(har_times)
    scan_avg = sum(scan_times) / len(scan_times)

    cube.close()
    for suffix in ("", ".cubelog"):
        p = path + suffix if suffix else path
        if os.path.isfile(p):
            os.unlink(p)

    return {
        "entries": n_entries,
        "har_avg_ms": round(har_avg, 3),
        "scan_avg_ms": round(scan_avg, 3),
        "speedup": round(scan_avg / har_avg, 2) if har_avg > 0 else 0,
        "har_p95_ms": round(sorted(har_times)[int(len(har_times) * 0.95)], 3),
        "scan_p95_ms": round(sorted(scan_times)[int(len(scan_times) * 0.95)], 3),
    }


def _is_relevant(query: str, entry_type: str, description: str, expected_type: str | None) -> bool:
    """Labeled relevance for IR: synonym/token cover + optional type prior."""
    try:
        from hermescube import bio_rank
    except ImportError:
        bio_rank = None  # type: ignore
    if bio_rank is not None:
        lx = bio_rank.lexical_score(query, description)
        if lx >= 0.18:
            return True
        # type-backed soft relevance when lexical weak but type matches intent
        if expected_type and entry_type == expected_type and lx >= 0.08:
            return True
        return False
    # fallback keyword
    q = set(query.lower().split())
    d = set(description.lower().split())
    return len(q & d) >= 2


def bench_recall(
    n_entries: int = 1000,
    top_k: int = 10,
) -> dict[str, Any]:
    """True IR recall@k against labeled relevance (not HAR↔scan agreement)."""
    memories = generate_memories(n_entries)
    path = build_cube(memories)

    cube = CubeFile.open(path)
    engine = HARQueryEngine(cube)
    engine.evolve()

    # Precompute relevant ID sets per query from full L1
    all_entries = cube.read_l1()
    total_recall = 0.0
    total_precision = 0.0
    per_query: list[dict] = []

    for q_text, expected_type in QUERIES:
        relevant_ids = {
            e.id
            for e in all_entries
            if _is_relevant(q_text, e.entry_type, e.description, expected_type)
        }
        results = engine.query(q_text, top_k=top_k)
        hit_ids = [e.id for e, _ in results]
        if not relevant_ids:
            # no gold labels — skip query
            per_query.append({
                "query": q_text[:40],
                "recall": None,
                "precision": None,
                "har_results": len(results),
                "gold": 0,
            })
            continue
        hits = sum(1 for i in hit_ids if i in relevant_ids)
        recall = hits / min(top_k, len(relevant_ids))
        # standard recall@k: |retrieved ∩ relevant| / |relevant| clipped usefully
        recall = hits / len(relevant_ids) if relevant_ids else 0.0
        # also report hit-rate@k against gold pool
        recall_at_k = hits / min(top_k, len(relevant_ids))
        precision = hits / len(hit_ids) if hit_ids else 0.0
        total_recall += recall_at_k
        total_precision += precision
        per_query.append({
            "query": q_text[:40],
            "recall": round(recall_at_k, 3),
            "precision": round(precision, 3),
            "har_results": len(results),
            "gold": len(relevant_ids),
            "hits": hits,
        })

    n = sum(1 for p in per_query if p.get("recall") is not None)
    cube.close()
    for suffix in ("", ".cubelog"):
        p = path + suffix if suffix else path
        if os.path.isfile(p):
            os.unlink(p)

    return {
        "entries": n_entries,
        "top_k": top_k,
        "avg_recall": round(total_recall / n, 3) if n else 0,
        "avg_precision": round(total_precision / n, 3) if n else 0,
        "metric": "labeled_relevance@k",
        "per_query": per_query,
    }


def bench_append_latency(sizes: list[int] = [100, 500, 1000]) -> list[dict]:
    """Measure append throughput at different batch sizes."""
    results = []
    for n in sizes:
        memories = generate_memories(n)
        with tempfile.NamedTemporaryFile(suffix=".cube", delete=False) as f:
            path = f.name
        cube = CubeFile.create(path)

        t0 = time.perf_counter()
        for etype, desc, data, outcome in memories:
            cube.append(etype, desc, data=data, outcome=outcome)
        dt = (time.perf_counter() - t0) * 1000

        per_entry_us = (dt / n) * 1000
        cube.close()
        os.unlink(path)

        results.append({
            "entries": n,
            "total_ms": round(dt, 1),
            "per_entry_us": round(per_entry_us, 1),
        })
    return results


def bench_evolve_latency(sizes: list[int] = [100, 500, 1000]) -> list[dict]:
    """Measure evolve (k-means) latency at different archive sizes."""
    results = []
    for n in sizes:
        memories = generate_memories(n)
        path = build_cube(memories)
        cube = CubeFile.open(path)
        engine = HARQueryEngine(cube)

        t0 = time.perf_counter()
        stats = engine.evolve()
        dt = (time.perf_counter() - t0) * 1000

        results.append({
            "entries": n,
            "evolve_ms": round(dt, 1),
            "non_empty_buckets": stats["non_empty_buckets"],
        })
        cube.close()
        os.unlink(path)
    return results


def bench_type_filter() -> dict[str, Any]:
    """Benchmark type-filtered queries."""
    memories = generate_memories(500)
    path = build_cube(memories)
    cube = CubeFile.open(path)
    engine = HARQueryEngine(cube)
    engine.evolve()

    results = {}
    for etype in ["landmark", "belief", "trait", "resolve", "focus", "evolution"]:
        t0 = time.perf_counter()
        found = cube.search("", entry_type=etype, limit=100)
        dt = (time.perf_counter() - t0) * 1000
        results[etype] = {"count": len(found), "scan_ms": round(dt, 3)}

    cube.close()
    os.unlink(path)
    return results


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("HermesCube Agent Memory Benchmark")
    print("=" * 70)
    print(f"Backend: {'numpy' if hrr.has_numpy() else 'pure-python'}")
    print()

    # 1. Append latency
    print("─" * 70)
    print("1. APPEND LATENCY")
    print("─" * 70)
    append_results = bench_append_latency([100, 500, 1000])
    print(f"{'Entries':>8} {'Total (ms)':>12} {'Per entry (µs)':>15}")
    print("-" * 40)
    for r in append_results:
        print(f"{r['entries']:>8} {r['total_ms']:>12.1f} {r['per_entry_us']:>15.1f}")
    print()

    # 2. Evolve latency
    print("─" * 70)
    print("2. EVOLVE (K-MEANS) LATENCY")
    print("─" * 70)
    evolve_results = bench_evolve_latency([100, 500, 1000])
    print(f"{'Entries':>8} {'Evolve (ms)':>12} {'Buckets':>10}")
    print("-" * 35)
    for r in evolve_results:
        print(f"{r['entries']:>8} {r['evolve_ms']:>12.1f} {r['non_empty_buckets']:>10}")
    print()

    # 3. Query latency
    print("─" * 70)
    print("3. QUERY LATENCY (HAR vs brute-force)")
    print("─" * 70)
    latency_results = []
    for n in [100, 500, 1000]:
        r = bench_query_latency(n)
        latency_results.append(r)
    print(f"{'Entries':>8} {'HAR avg':>10} {'HAR p95':>10} {'Scan avg':>10} {'Scan p95':>10} {'Speedup':>8}")
    print("-" * 60)
    for r in latency_results:
        print(f"{r['entries']:>8} {r['har_avg_ms']:>9.2f}ms {r['har_p95_ms']:>9.2f}ms "
              f"{r['scan_avg_ms']:>9.2f}ms {r['scan_p95_ms']:>9.2f}ms {r['speedup']:>7.2f}x")
    print()

    # 4. Recall
    print("─" * 70)
    print("4. RECALL@10 (HAR vs brute-force ground truth)")
    print("─" * 70)
    recall_result = bench_recall(1000)
    print(f"Entries: {recall_result['entries']}, Top-K: {recall_result['top_k']}")
    print(f"Average Recall@10:    {recall_result['avg_recall']:.3f}")
    print(f"Average Precision@10: {recall_result['avg_precision']:.3f}")
    print()
    print(f"{'Query':<42} {'Recall':>8} {'Precision':>10} {'HAR':>5} {'Scan':>5}")
    print("-" * 75)
    for pq in recall_result["per_query"]:
        print(f"{pq['query']:<42} {pq['recall']:>8.3f} {pq['precision']:>10.3f} "
              f"{pq['har_results']:>5} {pq['scan_results']:>5}")
    print()

    # 5. Type filter
    print("─" * 70)
    print("5. TYPE FILTER (500 entries)")
    print("─" * 70)
    type_results = bench_type_filter()
    print(f"{'Type':<18} {'Count':>8} {'Scan (ms)':>12}")
    print("-" * 40)
    for etype, r in type_results.items():
        print(f"{etype:<18} {r['count']:>8} {r['scan_ms']:>12.3f}")
    print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    r500 = next(r for r in latency_results if r["entries"] == 500)
    r1000 = next(r for r in latency_results if r["entries"] == 1000)
    a500 = next(r for r in append_results if r["entries"] == 500)
    e500 = next(r for r in evolve_results if r["entries"] == 500)
    print(f"  Append: {a500['per_entry_us']:.0f} µs/entry ({a500['entries']} batch)")
    print(f"  Evolve: {e500['evolve_ms']:.0f} ms ({e500['entries']} entries)")
    print(f"  Query @500:  {r500['har_avg_ms']:.2f} ms HAR, {r500['speedup']:.1f}x vs scan")
    print(f"  Query @1000: {r1000['har_avg_ms']:.2f} ms HAR, {r1000['speedup']:.1f}x vs scan")
    print(f"  Recall@10:   {recall_result['avg_recall']:.1%}")
    print(f"  Precision@10: {recall_result['avg_precision']:.1%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
