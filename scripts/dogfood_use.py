#!/usr/bin/env python3
"""Live dogfood: use HermesCube the way an agent does — store, prefetch, search, feedback, yield."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HERMES_HOME", str(Path.home() / ".hermes"))
# prefer installed package
sys.path.insert(0, "/home/ilo/projects/hermescube")

from hermescube.provider import CubeMemoryProvider  # noqa: E402


def main() -> int:
    hh = os.environ["HERMES_HOME"]
    p = CubeMemoryProvider()
    p.initialize(
        session_id="dogfood-bench-2026-07-23",
        hermes_home=hh,
        platform="cli",
        agent_context="primary",
    )
    print("version_provider_ok path=", p._cube_path)
    print("entries_before", p._cube.entry_count if p._cube else 0)

    facts = [
        ("belief", "HermesCube 0.8 Yield Gradient trains query-local payoff without LLM calls"),
        ("resolve", "2026-07-23: monotropic focus is everyday Cube usefulness not feature sprawl", "success"),
        ("landmark", "Dogfood session stores ops facts then benchmarks retrieval quality"),
        ("trait", "Pablo prefers first-person direct partner voice under high load"),
        ("belief", "Mission Zero north star is client collect plus Founding Five cash"),
    ]
    ids = []
    for item in facts:
        et, content = item[0], item[1]
        outcome = item[2] if len(item) > 2 else "none"
        args = {"action": "add", "entry_type": et, "content": content}
        if outcome != "none":
            args["outcome"] = outcome
        r = json.loads(p.handle_tool_call("hermescube_manage", args))
        print("add", r.get("status"), r.get("id"), et)
        if r.get("id"):
            ids.append(r["id"])

    # simulate turns
    p.sync_turn(
        "Remember we use Cube as deep warehouse with MEMORY.md",
        "Locked. Hot doctrine stays in MEMORY; long tail in cube.",
        session_id="dogfood-bench-2026-07-23",
    )

    queries = [
        "Yield Gradient query-local payoff",
        "monotropic everyday usefulness Cube",
        "Mission Zero cash Founding Five",
        "partner voice high load",
        "warehouse MEMORY.md extension",
    ]
    print("\n--- prefetch ---")
    for q in queries:
        t0 = time.perf_counter()
        pref = p.prefetch(q, session_id="dogfood-bench-2026-07-23")
        ms = (time.perf_counter() - t0) * 1000
        head = (pref or "").splitlines()[:3]
        print(f"{ms:6.2f}ms | {q[:40]!r}")
        for line in head:
            print("   ", line[:100])

    print("\n--- search + feedback (train yield) ---")
    if ids:
        p.prefetch("Yield Gradient payoff learning", session_id="dogfood-bench-2026-07-23")
        fr = json.loads(
            p.handle_tool_call(
                "hermescube_feedback",
                {"action": "helpful", "entry_id": ids[0]},
            )
        )
        print("feedback", fr)

    sr = json.loads(
        p.handle_tool_call(
            "hermescube_search",
            {"query": "Yield Gradient monotropic usefulness", "top_k": 5},
        )
    )
    for hit in (sr.get("results") or [])[:5]:
        print(
            f"  score={hit.get('score'):.3f} trust={hit.get('trust')} "
            f"{(hit.get('description') or '')[:70]}"
        )

    print("\nentries_after", p._cube.entry_count if p._cube else 0)
    if p._yield:
        print("yield", p._yield.stats())
    print("prompt_chars", len(p.system_prompt_block() or ""))
    p.shutdown()
    print("DOGFOOD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
