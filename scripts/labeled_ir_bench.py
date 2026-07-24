#!/usr/bin/env python3
"""Labeled IR bench — stem queries against live cube (user home only).

  HERMES_HOME=~/.hermes python scripts/labeled_ir_bench.py
"""
from __future__ import annotations

import os
import random
import re
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

os.environ.setdefault("HERMES_HOME", str(Path.home() / ".hermes"))


def _stems(text: str, n: int = 5) -> str:
    toks = re.findall(r"[a-zA-Z]{4,}", text or "")
    stop = {"that", "this", "with", "from", "have", "been", "were", "their", "about"}
    toks = [t.lower() for t in toks if t.lower() not in stop]
    if len(toks) < 2:
        return (text or "")[:80]
    random.shuffle(toks)
    return " ".join(toks[:n])


def main() -> int:
    from hermescube.provider import CubeMemoryProvider

    home = Path(os.environ["HERMES_HOME"])
    cube_path = home / "memories" / "memory.cube"
    if not cube_path.is_file():
        print("SKIP no cube at", cube_path)
        return 0

    p = CubeMemoryProvider()
    p.initialize(
        session_id="_ir_bench",
        hermes_home=str(home),
        platform="cli",
        agent_context="primary",
    )
    eng = p._engine
    if eng is None:
        print("FAIL no engine")
        return 1
    eng.refresh_cache()
    entries = list(getattr(eng, "_entries", []) or [])
    if len(entries) < 5:
        print("SKIP too few entries", len(entries))
        p.shutdown()
        return 0

    pairs = []
    for e in entries:
        desc = (e.description or "").strip()
        if len(desc) < 24:
            continue
        pairs.append((_stems(desc), str(e.id)))
    random.seed(42)
    random.shuffle(pairs)
    pairs = pairs[: min(40, len(pairs))]

    hit1 = hit3 = hit5 = 0
    mrr = 0.0
    t0 = time.perf_counter()
    for q, eid in pairs:
        res = eng.query(q, top_k=5)
        ids = [str(getattr(r, "id", "") or "") for r, _ in res]
        if eid in ids[:1]:
            hit1 += 1
        if eid in ids[:3]:
            hit3 += 1
        if eid in ids[:5]:
            hit5 += 1
        if eid in ids:
            mrr += 1.0 / (ids.index(eid) + 1)
    dt = (time.perf_counter() - t0) * 1000
    n = max(1, len(pairs))
    engram_stats = {}
    try:
        engram_stats = p._engram.stats() if p._engram else {}
    except Exception:
        pass
    report = {
        "n": len(pairs),
        "hit@1": round(hit1 / n, 3),
        "hit@3": round(hit3 / n, 3),
        "hit@5": round(hit5 / n, 3),
        "mrr": round(mrr / n, 3),
        "total_ms": round(dt, 2),
        "per_query_ms": round(dt / n, 3),
        "entries": len(entries),
        "engram": engram_stats,
    }
    print(report)
    p.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
