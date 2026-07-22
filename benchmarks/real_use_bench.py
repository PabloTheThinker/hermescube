#!/usr/bin/env python3
"""Real-use benchmark suite for HermesCube (public benefit).

Writes results under HERMESCUBE_BENCH_DIR (default ~/.hermes/hermescube-lab/results)
— never pollutes the git project tree with cubes or large outputs.

Scenarios mirror everyday agent memory:
  A) Fresh user install + seed durable prefs
  B) Noisy Q&A turns should not bury durable facts
  C) Prefetch latency under realistic N
  D) Multi-session persistence
  E) Labeled IR on agent-like corpus

Usage:
  PYTHONPATH=. python3 benchmarks/real_use_bench.py
  HERMESCUBE_BENCH_DIR=/tmp/hc-bench python3 benchmarks/real_use_bench.py
"""

from __future__ import annotations

import json
import os
import statistics as st
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# lab dir outside project
def _lab() -> Path:
    env = os.environ.get("HERMESCUBE_BENCH_DIR")
    if env:
        p = Path(env)
    else:
        home = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")
        p = home / "hermescube-lab" / "results"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _provider(home: str):
    from hermescube.provider import CubeMemoryProvider

    p = CubeMemoryProvider(auto_extract=False)
    p.initialize(session_id="real-use-bench", hermes_home=home, platform="bench")
    return p


def scenario_a_fresh_seed(lab: Path) -> dict:
    with tempfile.TemporaryDirectory(dir=str(lab.parent / "cubes")) as td:
        p = _provider(td)
        seeds = [
            ("trait", "User prefers concise bullet answers under high load"),
            ("relationship", "Alex Chen = primary human operator"),
            ("landmark", "Deploy path is $HERMES_HOME/memories/memory.cube"),
            ("resolve", "Ship gate requires secret scrub before public push"),
            ("belief", "Query rewrite must stay off on hot path"),
        ]
        t0 = time.perf_counter()
        for et, d in seeds:
            p._cube.append(et, d, data={"source": "seed", "trust": 0.9, "durable": True})
        seed_ms = (time.perf_counter() - t0) * 1000
        # noisy turns
        for i in range(12):
            p.sync_turn(
                f"What is random noise question {i}?",
                f"Noise answer {i} about unrelated topic widgets.",
                session_id="noise",
            )
        p._sync_queue.flush()
        time.sleep(0.08)
        p.evolve_consolidated()
        checks = {
            "high load talk": "concise",
            "who is Alex": "Alex Chen",
            "where is cube": "memory.cube",
            "ship gate": "secret",
            "query rewrite": "rewrite",
        }
        hits = {}
        times = []
        for q, needle in checks.items():
            t0 = time.perf_counter()
            text = p.prefetch(q) or ""
            times.append((time.perf_counter() - t0) * 1000)
            hits[q] = needle.lower() in text.lower()
        p.shutdown()
        return {
            "name": "A_fresh_seed_vs_noise",
            "seed_ms": round(seed_ms, 2),
            "prefetch_avg_ms": round(st.mean(times), 3),
            "prefetch_p50_ms": round(st.median(times), 3),
            "hit_rate": sum(hits.values()) / len(hits),
            "hits": hits,
            "entries": len(seeds) + 12,  # approx lower bound
        }


def scenario_b_question_index(lab: Path) -> dict:
    """Q turns must surface answer/durable not question text."""
    with tempfile.TemporaryDirectory(dir=str(lab.parent / "cubes")) as td:
        p = _provider(td)
        p._cube.append(
            "relationship",
            "Sam Rivera = team lead for memory systems",
            data={"source": "seed", "trust": 0.95, "durable": True},
        )
        p.sync_turn(
            "Who is Sam Rivera?",
            "Sam Rivera = team lead for memory systems.",
            session_id="q",
        )
        p._sync_queue.flush()
        time.sleep(0.05)
        text = p.prefetch("who is Sam") or ""
        top = next((ln for ln in text.splitlines() if ln.startswith("- [")), "")
        ok = "Sam Rivera = team lead" in text and not top.rstrip().endswith("?")
        p.shutdown()
        return {
            "name": "B_question_vs_fact",
            "ok": ok,
            "top": top[:120],
        }


def scenario_c_scale_prefetch(lab: Path) -> dict:
    from hermescube.cube import CubeFile
    from hermescube.har import HARQueryEngine
    from hermescube.provider import CubeMemoryProvider

    results = []
    for n in (50, 200, 500, 1000):
        with tempfile.TemporaryDirectory(dir=str(lab.parent / "cubes")) as td:
            path = Path(td) / "memories"
            path.mkdir()
            cube_path = path / "memory.cube"
            cube = CubeFile.create(str(cube_path))
            for i in range(n):
                et = ["belief", "trait", "landmark", "resolve", "focus"][i % 5]
                cube.append(
                    et,
                    f"Memory item {i}: topic-{i % 17} fact about system component {i % 9}",
                    data={"source": "seed" if i % 7 == 0 else "sync_turn", "trust": 0.8 if i % 7 == 0 else 0.45},
                )
            cube.close()
            p = CubeMemoryProvider()
            p.initialize(session_id="scale", hermes_home=td, platform="bench")
            times = []
            for q in ("system component", "topic-3 fact", "user trait preferences", "deployment landmark"):
                t0 = time.perf_counter()
                p.prefetch(q)
                times.append((time.perf_counter() - t0) * 1000)
            p.shutdown()
            results.append({
                "n": n,
                "avg_ms": round(st.mean(times), 3),
                "p50_ms": round(st.median(times), 3),
                "max_ms": round(max(times), 3),
            })
    return {"name": "C_scale_prefetch", "rows": results}


def scenario_d_persistence(lab: Path) -> dict:
    with tempfile.TemporaryDirectory(dir=str(lab.parent / "cubes")) as td:
        p1 = _provider(td)
        p1._cube.append(
            "trait",
            "User timezone is America/New_York",
            data={"source": "manage", "trust": 0.95, "durable": True},
        )
        p1.shutdown()
        p2 = _provider(td)
        text = p2.prefetch("what timezone") or ""
        ok = "America/New_York" in text
        n = p2._cube.entry_count if p2._cube else 0
        p2.shutdown()
        return {"name": "D_cross_session", "ok": ok, "entries": n}


def scenario_e_labeled_ir() -> dict:
    try:
        from benchmarks.bench_agent_memory import bench_recall
    except ImportError:
        from bench_agent_memory import bench_recall  # type: ignore
    r = bench_recall(500, 10)
    return {
        "name": "E_labeled_ir",
        "entries": r.get("entries"),
        "avg_recall": r.get("avg_recall"),
        "avg_precision": r.get("avg_precision"),
        "metric": r.get("metric"),
    }


def main() -> int:
    lab = _lab()
    (lab.parent / "cubes").mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = {
        "stamp": stamp,
        "version": __import__("hermescube").__version__,
        "scenarios": [],
    }
    print(f"HermesCube real-use bench v{out['version']}")
    print(f"lab → {lab}")
    for fn in (
        scenario_a_fresh_seed,
        scenario_b_question_index,
        scenario_c_scale_prefetch,
        scenario_d_persistence,
    ):
        t0 = time.perf_counter()
        try:
            row = fn(lab)
            row["wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            out["scenarios"].append(row)
            print(f"  OK {row['name']} ({row['wall_ms']} ms)")
        except Exception as e:
            out["scenarios"].append({"name": getattr(fn, "__name__", "?"), "error": str(e)})
            print(f"  FAIL {fn.__name__}: {e}")
    try:
        t0 = time.perf_counter()
        row = scenario_e_labeled_ir()
        row["wall_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        out["scenarios"].append(row)
        print(f"  OK {row['name']} recall={row.get('avg_recall')}")
    except Exception as e:
        out["scenarios"].append({"name": "E_labeled_ir", "error": str(e)})
        print(f"  FAIL E: {e}")

    # Pass gates for public benefit narrative
    a = next((s for s in out["scenarios"] if s.get("name") == "A_fresh_seed_vs_noise"), {})
    b = next((s for s in out["scenarios"] if s.get("name") == "B_question_vs_fact"), {})
    d = next((s for s in out["scenarios"] if s.get("name") == "D_cross_session"), {})
    e = next((s for s in out["scenarios"] if s.get("name") == "E_labeled_ir"), {})
    gates = {
        "durable_hit_rate_ge_0.8": (a.get("hit_rate") or 0) >= 0.8,
        "prefetch_p50_lt_25ms": (a.get("prefetch_p50_ms") or 999) < 25,
        "question_index_ok": bool(b.get("ok")),
        "cross_session_ok": bool(d.get("ok")),
        "labeled_recall_ge_0.7": (e.get("avg_recall") or 0) >= 0.7,
    }
    out["gates"] = gates
    out["pass"] = all(gates.values())
    path = lab / f"real-use-{stamp}.json"
    path.write_text(json.dumps(out, indent=2))
    latest = lab / "real-use-latest.json"
    latest.write_text(json.dumps(out, indent=2))
    print(json.dumps({"pass": out["pass"], "gates": gates, "path": str(path)}, indent=2))
    return 0 if out["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
