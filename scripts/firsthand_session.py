#!/usr/bin/env python3
"""First-hand ILO experience session: store real ops facts, recall, train yield, integrity."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("HERMES_HOME", str(Path.home() / ".hermes"))
import sys

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from hermescube.provider import CubeMemoryProvider


def main() -> int:
    hh = os.environ["HERMES_HOME"]
    stamp = time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime())
    p = CubeMemoryProvider()
    p.initialize(
        session_id=f"ilo-firsthand-{stamp}",
        hermes_home=hh,
        platform="cli",
        agent_context="primary",
    )
    print("FIRSTHAND version", __import__("hermescube").__version__)
    print("cube", p._cube_path, "entries_before", p._cube.entry_count)

    facts = [
        (
            "landmark",
            f"ILO firsthand Cube session {stamp}: provider hermescube 0.8.1 live on Parallax",
            "success",
        ),
        (
            "resolve",
            "HermesCube GH main is SoT; hermescube update never wipes memory.cube",
            "success",
        ),
        (
            "belief",
            "Hot MEMORY.md stays doctrine; Cube is deep warehouse with Yield Gradient",
            "none",
        ),
        (
            "trait",
            "Under high load Pablo wants short monotropic reports with real numbers",
            "none",
        ),
        (
            "landmark",
            "Bench gates: durable hit, prefetch p50 under 25ms, labeled recall ge 0.7",
            "success",
        ),
    ]
    ids = []
    for et, content, outcome in facts:
        args = {"action": "add", "entry_type": et, "content": content}
        if outcome != "none":
            args["outcome"] = outcome
        r = json.loads(p.handle_tool_call("hermescube_manage", args))
        print("store", r.get("status"), r.get("id"), et)
        if r.get("id"):
            ids.append(r["id"])

    p.sync_turn(
        "Confirm Cube is wired and saving real data on ILO.",
        "Confirmed. memory.provider=hermescube, integrity ok, WAL+cube durable.",
        session_id=f"ilo-firsthand-{stamp}",
    )

    queries = [
        "firsthand Cube session Parallax",
        "hermescube update never wipes cube",
        "Yield Gradient warehouse MEMORY",
        "high load monotropic short reports",
        "prefetch p50 labeled recall gates",
    ]
    print("\nRECALL")
    hits = 0
    for q in queries:
        t0 = time.perf_counter()
        pref = p.prefetch(q, session_id=f"ilo-firsthand-{stamp}") or ""
        ms = (time.perf_counter() - t0) * 1000
        ok = len(pref) > 40
        hits += int(ok)
        line = pref.splitlines()[1][:90] if len(pref.splitlines()) > 1 else "(empty)"
        print(f"  {ms:5.2f}ms hit={ok} | {q[:36]!r}")
        print(f"         {line}")

    if ids:
        p.prefetch(queries[0], session_id=f"ilo-firsthand-{stamp}")
        fr = json.loads(
            p.handle_tool_call(
                "hermescube_feedback", {"action": "helpful", "entry_id": ids[0]}
            )
        )
        print("feedback", fr)

    sr = json.loads(
        p.handle_tool_call(
            "hermescube_search",
            {"query": "ILO firsthand hermescube durable warehouse", "top_k": 5},
        )
    )
    print("\nSEARCH top")
    for h in (sr.get("results") or [])[:5]:
        print(
            f"  {h.get('score', 0):.3f} [{h.get('type')}] {(h.get('description') or '')[:70]}"
        )

    # integrity after writes — reuse open handle (exclusive flock)
    assert p._cube is not None
    integ = p._cube.integrity_check()
    print("\nINTEGRITY", json.dumps(integ, indent=2)[:500])
    print("entries_after", p._cube.entry_count)
    if p._yield:
        print("yield", p._yield.stats())
    entries_final = p._cube.entry_count
    p.shutdown()

    out = {
        "stamp": stamp,
        "prefetch_hits": hits,
        "prefetch_total": len(queries),
        "integrity_ok": integ.get("ok"),
        "entries": integ.get("entries_read"),
    }
    lab = Path(hh) / "hermescube-lab" / "results"
    lab.mkdir(parents=True, exist_ok=True)
    path = lab / f"firsthand-{stamp}.json"
    path.write_text(json.dumps(out, indent=2))
    (lab / "firsthand-latest.json").write_text(json.dumps(out, indent=2))
    print("WROTE", path)
    print("FIRSTHAND_OK" if hits == len(queries) and integ.get("ok") else "FIRSTHAND_PARTIAL")
    return 0 if hits == len(queries) and integ.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
