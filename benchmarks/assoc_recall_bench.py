#!/usr/bin/env python3
"""Associative-recall bench — guards the entity graph against silent decay.

`real_use_bench.py` labels relevance purely by lexical overlap, so it cannot
see whether the entity graph works: any result reached by association counts
as a miss there, and a completely inert graph still scores 1.0. This bench
covers the gap.

It measures four things:
  1. Entity extraction recall on realistic memory prose
  2. Entity annotation rate across a populated archive
  3. Two-hop associative recall — probe A must surface B, where B shares no
     query token with A and is reachable only through a shared entity
  4. Direct IR (hit@1/@3/@5, MRR, p50 latency), so a gain in (3) that costs
     direct retrieval is visible immediately

Usage:
  PYTHONPATH=. python3 benchmarks/assoc_recall_bench.py [label]
  GUARD_DISTRACTORS=1000 PYTHONPATH=. python3 benchmarks/assoc_recall_bench.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

# ── Corpus: realistic agent memories with known entity links ──────────
# Each tuple: (entry_type, text, [entities that SHOULD be extracted])
CORPUS = [
    ("relationship", "Alice Nguyen is the primary operator for the billing service", ["Alice Nguyen", "billing service"]),
    ("landmark", "Deployed auth-service v2.1 to production on the eu-west cluster", ["auth-service", "eu-west"]),
    ("belief", "auth-service depends on redis for session storage", ["auth-service", "redis"]),
    ("resolve", "Fixed the redis connection pool leak in auth-service", ["redis", "auth-service"]),
    ("trait", "User prefers dark mode and concise replies", []),
    ("belief", "The billing service uses postgres with a read replica", ["billing service", "postgres"]),
    ("landmark", "Migrated postgres from version 14 to 16", ["postgres"]),
    ("relationship", "Bob Carter reviews all auth-service pull requests", ["Bob Carter", "auth-service"]),
    ("resolve", "Rolled back the eu-west deploy after latency spike", ["eu-west"]),
    ("belief", "kubernetes ingress terminates TLS for auth-service", ["kubernetes", "auth-service"]),
    ("focus", "Working on the payment reconciliation pipeline this sprint", ["payment reconciliation"]),
    ("belief", "The payment reconciliation pipeline reads from postgres nightly", ["payment reconciliation", "postgres"]),
    ("landmark", "Config lives at $HERMES_HOME/memories/memory.cube", ["$HERMES_HOME"]),
    ("relationship", "Alice Nguyen owns the payment reconciliation pipeline", ["Alice Nguyen", "payment reconciliation"]),
    ("evolution", "Refactored billing service from flask to fastapi", ["billing service", "flask", "fastapi"]),
    ("belief", "fastapi gives better async throughput than flask", ["fastapi", "flask"]),
    ("resolve", "Bob Carter approved the fastapi migration", ["Bob Carter", "fastapi"]),
    ("landmark", "Grafana dashboard tracks auth-service p99 latency", ["Grafana", "auth-service"]),
    ("belief", "redis evicts keys under memory pressure in eu-west", ["redis", "eu-west"]),
    ("trait", "User wants alerts only for p99 regressions", []),
]

# TRUE 2-hop associative probes.
# probe -> target text that shares NO query token with the probe.
# The only path from probe to target is a shared entity in a bridging entry.
#   e.g. "Alice Nguyen" --owns--> "payment reconciliation" --reads--> "postgres nightly"
# A pure lexical matcher cannot make this hop; an entity graph can.
ASSOC_PROBES = [
    ("Alice Nguyen", "reads from postgres nightly"),
    ("Bob Carter", "better async throughput"),
    ("Grafana", "terminates TLS"),
    ("flask", "read replica"),
    ("kubernetes", "connection pool leak"),
]

# Direct IR probes: natural question -> substring that must appear in a hit
IR_PROBES = [
    ("who operates billing", "Alice Nguyen"),
    ("what does auth-service depend on", "redis"),
    ("where is the config stored", "memory.cube"),
    ("which database does billing use", "postgres"),
    ("who reviews auth pull requests", "Bob Carter"),
    ("what happened to the eu-west deploy", "eu-west"),
    ("why did we move to fastapi", "fastapi"),
    ("what is the user's reply style", "concise"),
    ("what tracks latency", "Grafana"),
    ("what is being worked on this sprint", "reconciliation"),
]


def measure_entity_recall() -> dict:
    from hermescube.mirror import extract_entities

    total = hit = 0
    misses = []
    for _et, text, expected in CORPUS:
        for want in expected:
            total += 1
            got = [g.lower() for g in extract_entities(text)]
            if any(want.lower() in g or g in want.lower() for g in got):
                hit += 1
            else:
                misses.append((want, text[:55]))
    return {
        "expected_entities": total,
        "extracted": hit,
        "entity_recall": round(hit / max(total, 1), 3),
        "sample_misses": misses[:8],
    }


DISTRACTOR_N = int(os.environ.get("GUARD_DISTRACTORS", "400"))


def _distractors(n: int):
    """Unrelated memories so lexical candidate generation gets diluted."""
    topics = ["invoice", "webhook", "cron", "gateway", "queue", "shard", "cdn",
              "lambda", "bucket", "tracing", "quota", "backup", "cert", "dns"]
    verbs = ["updated", "checked", "reviewed", "documented", "tested", "profiled"]
    out = []
    for i in range(n):
        t = topics[i % len(topics)]
        v = verbs[i % len(verbs)]
        out.append((
            ["belief", "landmark", "resolve", "focus"][i % 4],
            f"{v.capitalize()} the {t} subsystem for batch {i} handling routine {t} traffic",
        ))
    return out


def _build(tmp: str):
    from hermescube.provider import CubeMemoryProvider

    p = CubeMemoryProvider()
    p.initialize(session_id="guard", hermes_home=tmp, platform="bench")
    for et, text in _distractors(DISTRACTOR_N):
        p._cube.append(et, text, data={"source": "sync_turn", "trust": 0.45})
    for et, text, _ in CORPUS:
        p._cube.append(et, text, data={"source": "seed", "trust": 0.8, "durable": True})
    p._engine.invalidate_cache()
    p.evolve_consolidated()
    p._refresh_snapshot()
    return p


def measure_retrieval(p) -> dict:
    eng = p._engine
    eng.refresh_cache()

    # Direct IR
    ir_hits = 0
    ir_detail = []
    for q, needle in IR_PROBES:
        res = eng.query(q, top_k=5)
        texts = [r.description for r, _ in res]
        ok = any(needle.lower() in t.lower() for t in texts)
        ir_hits += ok
        ir_detail.append({"q": q, "want": needle, "ok": ok, "top": texts[0][:50] if texts else ""})

    # Associative recall
    assoc_hits = 0
    assoc_detail = []
    for probe, want in ASSOC_PROBES:
        res = eng.query(probe, top_k=5)
        texts = [r.description for r, _ in res]
        ok = any(want.lower() in t.lower() for t in texts)
        assoc_hits += ok
        assoc_detail.append({"probe": probe, "want": want, "ok": ok})

    # Self-retrieval hit@k / MRR over the SIGNAL entries only (distractors
    # stay in the archive as noise but are not themselves probed).
    entries = [e for e in eng._entries if (e.data or {}).get("source") == "seed"]
    h1 = h3 = h5 = 0
    mrr = 0.0
    lat = []
    for e in entries:
        words = (e.description or "").split()
        if len(words) < 5:
            continue
        q = " ".join(words[1:6])  # partial phrase, not identical
        t0 = time.perf_counter()
        res = eng.query(q, top_k=5)
        lat.append((time.perf_counter() - t0) * 1000)
        ids = [r.id for r, _ in res]
        if e.id in ids[:1]:
            h1 += 1
        if e.id in ids[:3]:
            h3 += 1
        if e.id in ids[:5]:
            h5 += 1
        if e.id in ids:
            mrr += 1.0 / (ids.index(e.id) + 1)
    n = max(1, len([e for e in entries if len((e.description or "").split()) >= 5]))

    return {
        "ir_probe_hits": f"{ir_hits}/{len(IR_PROBES)}",
        "ir_probe_rate": round(ir_hits / len(IR_PROBES), 3),
        "assoc_hits": f"{assoc_hits}/{len(ASSOC_PROBES)}",
        "assoc_rate": round(assoc_hits / len(ASSOC_PROBES), 3),
        "hit@1": round(h1 / n, 3),
        "hit@3": round(h3 / n, 3),
        "hit@5": round(h5 / n, 3),
        "mrr": round(mrr / n, 3),
        "query_p50_ms": round(sorted(lat)[len(lat) // 2], 3) if lat else 0,
        "ir_detail": ir_detail,
        "assoc_detail": assoc_detail,
    }


def measure_colony(p) -> dict:
    """Is the stigmergy graph actually accumulating edges?"""
    col = getattr(p, "_colony", None)
    if col is None:
        return {"colony": "absent"}
    # simulate real usage: recall then reinforce
    for q, _ in IR_PROBES:
        p.prefetch(q)
    ents_with = 0
    for e in p._cube.read_l1() or []:
        if (e.data or {}).get("entities"):
            ents_with += 1
    nodes = len(col.edges or {})
    undirected = len({col._ekey(a, b) for a, bs in col.edges.items() for b in bs})
    return {
        "entries_with_entities": ents_with,
        "entries_total": p._cube.entry_count,
        "entity_annotation_rate": round(ents_with / max(p._cube.entry_count, 1), 3),
        "colony_nodes": nodes,
        "colony_edges": undirected,
        "colony_dances": len(col.dances or {}),
    }


def main() -> int:
    out = {"version": __import__("hermescube").__version__}
    out["entities"] = measure_entity_recall()
    tmp = tempfile.mkdtemp(prefix="hcguard-")
    try:
        p = _build(tmp)
        out["retrieval"] = measure_retrieval(p)
        out["colony"] = measure_colony(p)
        p.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(json.dumps(out, indent=2))
    # Results land outside the git tree, same convention as real_use_bench.
    label = sys.argv[1] if len(sys.argv) > 1 else "latest"
    lab = os.environ.get("HERMESCUBE_BENCH_DIR")
    lab_dir = (
        os.path.join(lab) if lab
        else os.path.join(
            os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes")),
            "hermescube-lab", "results",
        )
    )
    os.makedirs(lab_dir, exist_ok=True)
    with open(os.path.join(lab_dir, f"assoc-recall-{label}.json"), "w") as f:
        json.dump(out, f, indent=2)

    e, r, c = out["entities"], out["retrieval"], out["colony"]
    print("\n─── SUMMARY ─────────────────────────────")
    print(f"entity_recall        {e['entity_recall']}")
    print(f"entity_annotation    {c.get('entity_annotation_rate')}")
    print(f"colony_nodes/edges   {c.get('colony_nodes')} / {c.get('colony_edges')}")
    print(f"assoc_recall         {r['assoc_rate']}  ({r['assoc_hits']})")
    print(f"ir_probe_rate        {r['ir_probe_rate']}  ({r['ir_probe_hits']})")
    print(f"hit@1 / @3 / @5      {r['hit@1']} / {r['hit@3']} / {r['hit@5']}")
    print(f"mrr                  {r['mrr']}")
    print(f"query_p50_ms         {r['query_p50_ms']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
