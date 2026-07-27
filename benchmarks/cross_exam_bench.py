#!/usr/bin/env python3
"""Cross-exam: Hermes builtin memory vs holographic vs HermesCube.

Arms
----
A. Builtin MemoryStore (MEMORY.md / USER.md) — Hermes default when
   ``memory.provider`` is empty. No retrieval; recall = frozen system-prompt dump.
B. Bundled holographic MemoryProvider — local SQLite + FTS/HRR.
C. HermesCube CubeMemoryProvider — local cube + HAR.

Same seed facts and probe needles across arms. Reports add latency, recall
latency, hit rate, and capacity behaviour.

Requires HERMES_AGENT_ROOT (default /tmp/hermes-agent-research) on PYTHONPATH
for arms A/B. Arm C uses this repo.
"""

from __future__ import annotations

import json
import os
import statistics as st
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERMES_ROOT = Path(os.environ.get("HERMES_AGENT_ROOT", "/tmp/hermes-agent-research"))
sys.path.insert(0, str(ROOT))
if HERMES_ROOT.is_dir():
    sys.path.insert(0, str(HERMES_ROOT))


def _lab() -> Path:
    env = os.environ.get("HERMESCUBE_BENCH_DIR")
    p = Path(env) if env else Path("/tmp/hc-bench/results")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 3)


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    k = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return round(s[k], 3)


def _facts(n: int) -> list[str]:
    # Keep needle early — Cube prefetch quotes ~220 chars; builtin has 2200 budget.
    # Use space-separated tokens so holographic FTS5 can match (hyphens tokenize poorly).
    return [
        f"Needle {i:04d} vault token {i:04d} unlocks project auth for service {i % 17}"
        for i in range(n)
    ]


def _probes(n_facts: int, m: int) -> list[tuple[str, str]]:
    # Spread probes across the corpus (not just the head).
    idxs = sorted({(i * max(1, n_facts // m)) % n_facts for i in range(m)})
    while len(idxs) < m:
        idxs.append(len(idxs) % n_facts)
    # Query + needle both use the unique token sequence.
    return [
        (f"vault token {i:04d}", f"vault token {i:04d}")
        for i in idxs[:m]
    ]


# ── Arm A: Hermes builtin MemoryStore ────────────────────────────────


def run_builtin(facts: list[str], probes: list[tuple[str, str]]) -> dict:
    os.environ["HERMES_HOME"] = str(Path(tempfile.mkdtemp(prefix="builtin-")))
    (Path(os.environ["HERMES_HOME"]) / "memories").mkdir(parents=True)

    from tools.memory_tool import MemoryStore, ENTRY_DELIMITER

    store = MemoryStore(memory_char_limit=2200, user_char_limit=1375)
    store.load_from_disk()

    add_ms: list[float] = []
    seeded = 0
    rejected = 0
    reject_reason = ""
    for f in facts:
        t0 = time.perf_counter()
        r = store.add("memory", f)
        add_ms.append(_ms(t0))
        if r.get("success"):
            seeded += 1
        else:
            rejected += 1
            if not reject_reason:
                reject_reason = str(r.get("error") or r)[:200]

    t0 = time.perf_counter()
    store.load_from_disk()
    block = store.format_for_system_prompt("memory") or ""
    snapshot_ms = _ms(t0)
    live = ENTRY_DELIMITER.join(store.memory_entries)
    chars = len(live)

    recall_ms: list[float] = []
    hits: list[bool] = []
    for _q, needle in probes:
        t0 = time.perf_counter()
        text = block  # no query API — presence in frozen dump
        recall_ms.append(_ms(t0))
        hits.append(needle.lower() in text.lower())

    return {
        "arm": "builtin_memory_store",
        "contract": "frozen MEMORY.md dump (no retrieval)",
        "capacity_chars": 2200,
        "seeded": seeded,
        "rejected": rejected,
        "reject_reason": reject_reason,
        "chars_used": chars,
        "add_p50_ms": _pct(add_ms, 50),
        "add_p95_ms": _pct(add_ms, 95),
        "snapshot_ms": snapshot_ms,
        "recall_p50_ms": _pct(recall_ms, 50),
        "recall_p95_ms": _pct(recall_ms, 95),
        "hit_rate": round(sum(hits) / len(hits), 3) if hits else 0.0,
        "hits": sum(hits),
        "probes": len(hits),
        "notes": "Hit = needle present in full system-prompt snapshot after reload.",
    }


# ── Arm B: holographic MemoryProvider ────────────────────────────────


def run_holographic(facts: list[str], probes: list[tuple[str, str]]) -> dict:
    home = Path(tempfile.mkdtemp(prefix="holo-"))
    os.environ["HERMES_HOME"] = str(home)
    (home / "memories").mkdir(parents=True)

    from plugins.memory.holographic import HolographicMemoryProvider

    p = HolographicMemoryProvider(
        config={
            "db_path": str(home / "memory_store.db"),
            "auto_extract": False,
            "default_trust": 0.5,
            "min_trust_threshold": 0.3,
            "hrr_dim": 1024,
        }
    )
    p.initialize(
        session_id="bench",
        hermes_home=str(home),
        platform="cli",
        agent_context="primary",
    )

    add_ms: list[float] = []
    seeded = 0
    for f in facts:
        t0 = time.perf_counter()
        raw = p.handle_tool_call(
            "fact_store",
            {"action": "add", "content": f, "category": "general"},
        )
        add_ms.append(_ms(t0))
        r = json.loads(raw)
        if r.get("status") == "added" or r.get("fact_id") is not None:
            seeded += 1

    # Prefetch path (what Hermes injects as <memory-context>, top-5)
    pref_ms: list[float] = []
    pref_hits: list[bool] = []
    for q, needle in probes:
        t0 = time.perf_counter()
        text = p.prefetch(q, session_id="bench") or ""
        pref_ms.append(_ms(t0))
        pref_hits.append(needle.lower() in text.lower())

    # Explicit tool search (limit 10) — fairer retrieval surface
    search_ms: list[float] = []
    search_hits: list[bool] = []
    for q, needle in probes:
        t0 = time.perf_counter()
        raw = p.handle_tool_call(
            "fact_store",
            {"action": "search", "query": q, "limit": 10, "min_trust": 0.0},
        )
        search_ms.append(_ms(t0))
        try:
            results = json.loads(raw).get("results") or []
            blob = " ".join(str(r.get("content") or "") for r in results)
        except Exception:
            blob = raw if isinstance(raw, str) else ""
        search_hits.append(needle.lower() in blob.lower())

    p.shutdown()
    return {
        "arm": "holographic",
        "contract": "MemoryProvider (fact_store + prefetch top-5)",
        "seeded": seeded,
        "rejected": len(facts) - seeded,
        "add_p50_ms": _pct(add_ms, 50),
        "add_p95_ms": _pct(add_ms, 95),
        "prefetch_p50_ms": _pct(pref_ms, 50),
        "prefetch_p95_ms": _pct(pref_ms, 95),
        "prefetch_hit_rate": round(sum(pref_hits) / len(pref_hits), 3) if pref_hits else 0.0,
        "search_p50_ms": _pct(search_ms, 50),
        "search_p95_ms": _pct(search_ms, 95),
        "search_hit_rate": round(sum(search_hits) / len(search_hits), 3) if search_hits else 0.0,
        "notes": "Prefetch capped at top-5; search uses limit=10.",
    }


# ── Arm C: HermesCube CubeMemoryProvider ─────────────────────────────


def run_cube(facts: list[str], probes: list[tuple[str, str]]) -> dict:
    home = Path(tempfile.mkdtemp(prefix="cube-"))
    (home / "memories").mkdir(parents=True)

    from hermescube.provider import CubeMemoryProvider

    p = CubeMemoryProvider(auto_extract=False)
    p.initialize(
        session_id="bench",
        hermes_home=str(home),
        platform="cli",
        agent_context="primary",
        agent_identity="bench",
    )

    add_ms: list[float] = []
    seeded = 0
    for f in facts:
        t0 = time.perf_counter()
        raw = p.handle_tool_call(
            "hermescube_manage",
            {"action": "add", "entry_type": "belief", "content": f},
        )
        add_ms.append(_ms(t0))
        r = json.loads(raw)
        if r.get("status") == "added" or r.get("id"):
            seeded += 1

    pref_ms: list[float] = []
    pref_hits: list[bool] = []
    for q, needle in probes:
        t0 = time.perf_counter()
        text = p.prefetch(q, session_id="bench") or ""
        pref_ms.append(_ms(t0))
        pref_hits.append(needle.lower() in text.lower())

    search_ms: list[float] = []
    search_hits: list[bool] = []
    for q, needle in probes:
        t0 = time.perf_counter()
        raw = p.handle_tool_call(
            "hermescube_search",
            {"query": q, "top_k": 10},
        )
        search_ms.append(_ms(t0))
        try:
            payload = json.loads(raw)
            results = payload.get("results") or []
            blob = " ".join(str(r.get("description") or r.get("content") or "") for r in results)
        except Exception:
            blob = raw if isinstance(raw, str) else ""
        search_hits.append(needle.lower() in blob.lower())

    # Growth / Eden strip (HermesCube-only surface)
    from hermescube.genealogy import growth_status

    g = growth_status(str(home), cube=p._cube)
    prompt = p.system_prompt_block()
    p.shutdown()

    return {
        "arm": "hermescube",
        "contract": "MemoryProvider (hermescube_manage/search + prefetch)",
        "seeded": seeded,
        "rejected": len(facts) - seeded,
        "add_p50_ms": _pct(add_ms, 50),
        "add_p95_ms": _pct(add_ms, 95),
        "prefetch_p50_ms": _pct(pref_ms, 50),
        "prefetch_p95_ms": _pct(pref_ms, 95),
        "prefetch_hit_rate": round(sum(pref_hits) / len(pref_hits), 3) if pref_hits else 0.0,
        "search_p50_ms": _pct(search_ms, 50),
        "search_p95_ms": _pct(search_ms, 95),
        "search_hit_rate": round(sum(search_hits) / len(search_hits), 3) if search_hits else 0.0,
        "era": g.get("era"),
        "era_label": g.get("era_label"),
        "living_version": g.get("version"),
        "eden_in_prompt": "Cube of Eden" in prompt,
        "notes": "Prefetch evidence packet; search top_k=10.",
    }


def run() -> dict:
    from hermescube import __version__

    lab = _lab()
    # Two regimes: capacity-fair (fits builtin 2200) and scale (retrieval arms only)
    regimes = {
        "capacity_fair": {"n_facts": 12, "n_probes": 8},   # ~12×~70 chars < 2200
        "scale_500": {"n_facts": 500, "n_probes": 25},
        "scale_1000": {"n_facts": 1000, "n_probes": 40},
    }

    report: dict = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "hermescube": __version__,
        "hermes_agent_root": str(HERMES_ROOT),
        "regimes": {},
        "gates": {},
    }

    for name, cfg in regimes.items():
        facts = _facts(cfg["n_facts"])
        probes = _probes(cfg["n_facts"], cfg["n_probes"])
        arms: dict = {}

        # Builtin only meaningful in capacity_fair (hard 2200 reject otherwise)
        if name == "capacity_fair":
            arms["builtin"] = run_builtin(facts, probes)
        else:
            # Document capacity wall without pretending it's a retrieval contest
            arms["builtin"] = {
                "arm": "builtin_memory_store",
                "skipped": True,
                "reason": f"N={cfg['n_facts']} exceeds 2200-char MEMORY.md budget",
                "capacity_chars": 2200,
            }

        if HERMES_ROOT.is_dir():
            arms["holographic"] = run_holographic(facts, probes)
        else:
            arms["holographic"] = {
                "arm": "holographic",
                "skipped": True,
                "reason": f"HERMES_AGENT_ROOT missing: {HERMES_ROOT}",
            }

        arms["hermescube"] = run_cube(facts, probes)
        report["regimes"][name] = {
            "n_facts": cfg["n_facts"],
            "n_probes": cfg["n_probes"],
            "arms": arms,
        }

    # Gates — fair capacity regime + scale retrieval (cold path, no evolve)
    fair = report["regimes"]["capacity_fair"]["arms"]
    s500 = report["regimes"]["scale_500"]["arms"]
    s1k = report["regimes"]["scale_1000"]["arms"]
    gates = {
        # Capacity-fair: builtin fits; cube recalls; Eden visible
        "fair_builtin_seeded_all": fair["builtin"].get("seeded") == 12,
        "fair_builtin_hit_1": fair["builtin"].get("hit_rate", 0) >= 1.0,
        "fair_cube_prefetch_hit_ge_0.8": fair["hermescube"].get("prefetch_hit_rate", 0) >= 0.8,
        "fair_eden_in_cube_prompt": bool(fair["hermescube"].get("eden_in_prompt")),
        # Scale: cube keeps high search hit; builtin cannot participate
        "scale500_cube_search_hit_ge_0.8": s500["hermescube"].get("search_hit_rate", 0) >= 0.8,
        "scale500_cube_prefetch_p50_lt_100ms": s500["hermescube"].get("prefetch_p50_ms", 999) < 100,
        "scale1000_cube_search_hit_ge_0.7": s1k["hermescube"].get("search_hit_rate", 0) >= 0.7,
        "scale1000_cube_prefetch_p50_lt_150ms": s1k["hermescube"].get("prefetch_p50_ms", 999) < 150,
        # Builtin capacity wall is the point of the scale regimes
        "scale500_builtin_skipped": bool(s500["builtin"].get("skipped")),
        "scale1000_builtin_skipped": bool(s1k["builtin"].get("skipped")),
    }
    if not fair["holographic"].get("skipped"):
        gates["fair_holo_seeded_all"] = fair["holographic"].get("seeded") == 12
        gates["fair_holo_search_hit_ge_0.8"] = fair["holographic"].get("search_hit_rate", 0) >= 0.8
        gates["scale500_holo_search_hit_ge_0.5"] = s500["holographic"].get("search_hit_rate", 0) >= 0.5
        # Head-to-head: at scale, cube search hit should meet or beat holo
        gates["scale500_cube_search_ge_holo"] = (
            s500["hermescube"].get("search_hit_rate", 0)
            >= s500["holographic"].get("search_hit_rate", 0)
        )

    report["gates"] = gates
    report["pass"] = all(gates.values())

    out = lab / f"cross-exam-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (lab / "cross-exam-latest.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    report["path"] = str(out)
    return report


def _print_arm(label: str, arm: dict) -> None:
    if arm.get("skipped"):
        print(f"  {label:12} SKIP — {arm.get('reason')}")
        return
    if arm.get("arm") == "builtin_memory_store":
        print(
            f"  {label:12} seeded={arm['seeded']}/{arm['seeded']+arm['rejected']} "
            f"chars={arm['chars_used']}/2200  "
            f"add_p50={arm['add_p50_ms']}ms  recall_p50={arm['recall_p50_ms']}ms  "
            f"hit={arm['hit_rate']}"
        )
        return
    print(
        f"  {label:12} seeded={arm['seeded']}  "
        f"add_p50={arm['add_p50_ms']}ms  "
        f"prefetch_p50={arm['prefetch_p50_ms']}ms hit={arm['prefetch_hit_rate']}  "
        f"search_p50={arm['search_p50_ms']}ms hit={arm['search_hit_rate']}"
    )


def main() -> int:
    r = run()
    print(f"Cross-exam: Hermes builtin vs holographic vs HermesCube v{r['hermescube']}")
    print(f"pass={r['pass']}")
    print("gates:")
    for k, v in r["gates"].items():
        print(f"  {'OK' if v else 'FAIL':4} {k}")
    for name, regime in r["regimes"].items():
        print(f"\n{name} (N={regime['n_facts']}, probes={regime['n_probes']}):")
        arms = regime["arms"]
        _print_arm("builtin", arms["builtin"])
        _print_arm("holographic", arms["holographic"])
        _print_arm("hermescube", arms["hermescube"])
        cube = arms["hermescube"]
        if cube.get("era_label"):
            print(f"             era={cube['era_label']} v{cube.get('living_version')}")
    print(f"\n→ {r['path']}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
