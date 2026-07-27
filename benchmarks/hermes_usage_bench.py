#!/usr/bin/env python3
"""Hermes Agent × HermesCube usage benchmark.

Simulates the MemoryProvider lifecycle Hermes Agent actually drives:
  initialize → sync_turn × N → prefetch → manage tools → session_end
  → growth/Eden → optional hive pilgrimage → cross-session reopen.

Writes JSON under HERMESCUBE_BENCH_DIR (default /tmp/hc-bench/results).
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
sys.path.insert(0, str(ROOT))


def _lab() -> Path:
    env = os.environ.get("HERMESCUBE_BENCH_DIR")
    p = Path(env) if env else Path("/tmp/hc-bench/results")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 3)


def run() -> dict:
    from hermescube import __version__
    from hermescube.genealogy import growth_status, era_label
    from hermescube.hive import init_hive
    from hermescube.provider import CubeMemoryProvider

    lab = _lab()
    report: dict = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "hermescube": __version__,
        "scenarios": {},
        "gates": {},
    }

    with tempfile.TemporaryDirectory(prefix="hermes-usage-") as td:
        home = Path(td) / "hermes-home"
        hive = Path(td) / "hive"
        (home / "memories").mkdir(parents=True)
        init_hive(str(hive))

        # ── 1. Hermes-like provider lifecycle ─────────────────────
        p = CubeMemoryProvider(auto_extract=False)
        t0 = time.perf_counter()
        p.initialize(
            session_id="sess-1",
            hermes_home=str(home),
            platform="cli",
            agent_context="primary",
            agent_identity="coder",
        )
        init_ms = _ms(t0)
        p._hive_path = str(hive)
        p._hive_on_session_end = False  # we'll call pilgrimage explicitly

        # Seed durable operator facts the way Hermes would via manage
        seeds = [
            ("trait", "Operator prefers concise bullet answers under load"),
            ("belief", "Always triangulate three independent sources before citing"),
            ("landmark", "HermesCube cube path is $HERMES_HOME/memories/memory.cube"),
            ("resolve", "Ship gate: scrub secrets before public push"),
            ("belief", "Living cube starts in the Cube of Eden at version 0.0.0"),
        ]
        add_ms = []
        for et, content in seeds:
            t0 = time.perf_counter()
            raw = p.handle_tool_call(
                "hermescube_manage",
                {"action": "add", "entry_type": et, "content": content},
            )
            r = json.loads(raw) if isinstance(raw, str) else raw
            add_ms.append(_ms(t0))
            assert "error" not in r, r
            assert r.get("status") in ("added", "ok", "add") or r.get("id")

        # Noisy conversation turns (Hermes sync_turn path)
        sync_ms = []
        for i in range(20):
            t0 = time.perf_counter()
            p.sync_turn(
                f"Side question {i} about unrelated widgets?",
                f"Noise reply {i}: widgets are fine, nothing durable.",
                session_id="sess-1",
            )
            sync_ms.append(_ms(t0))
        p._sync_queue.flush()
        time.sleep(0.05)

        # Prefetch under conversational load (what Hermes injects as <memory-context>)
        probes = {
            "concise answers under load": "concise",
            "triangulate sources citing": "triangulate",
            "where is the cube stored": "memory.cube",
            "ship gate secrets": "secret",
            "Cube of Eden version": "Eden",
        }
        pref_ms = []
        hits = {}
        for q, needle in probes.items():
            t0 = time.perf_counter()
            text = p.prefetch(q, session_id="sess-1") or ""
            pref_ms.append(_ms(t0))
            hits[q] = needle.lower() in text.lower()

        # Search tool (agent-initiated)
        t0 = time.perf_counter()
        search = json.loads(
            p.handle_tool_call(
                "hermescube_search",
                {"query": "triangulate three independent sources", "top_k": 5},
            )
        )
        search_ms = _ms(t0)

        # Growth / Eden status (soul age)
        t0 = time.perf_counter()
        growth = json.loads(
            p.handle_tool_call(
                "hermescube_manage",
                {"action": "growth", "content": "status"},
            )
        )
        growth_ms = _ms(t0)

        # Session end (Hermes MemoryManager end hook)
        t0 = time.perf_counter()
        p.on_session_end([])
        p._sync_queue.flush()
        end_ms = _ms(t0)

        g = growth_status(str(home), cube=p._cube)
        prompt = p.system_prompt_block()
        era_ok = (
            g.get("era") == "eden"
            and g.get("era_label") == "Cube of Eden"
            and "Cube of Eden" in prompt
        )

        report["scenarios"]["lifecycle"] = {
            "init_ms": init_ms,
            "add_p50_ms": round(st.median(add_ms), 3),
            "sync_turn_p50_ms": round(st.median(sync_ms), 3),
            "prefetch_p50_ms": round(st.median(pref_ms), 3),
            "prefetch_avg_ms": round(st.mean(pref_ms), 3),
            "search_ms": search_ms,
            "growth_status_ms": growth_ms,
            "session_end_ms": end_ms,
            "hit_rate": sum(hits.values()) / len(hits),
            "hits": hits,
            "search_count": search.get("count", len(search.get("results") or [])),
            "era": g.get("era"),
            "era_label": g.get("era_label"),
            "age": g.get("age"),
            "living_version": g.get("version"),
            "capability": g.get("capability"),
            "entries": p._cube.entry_count if p._cube else 0,
            "eden_in_prompt": "Cube of Eden" in prompt,
            "era_ok": era_ok,
        }

        # ── 2. Hive pilgrimage (multi-agent night cycle) ──────────
        # Seed a peer agent offering via a second home
        peer = Path(td) / "peer-home"
        (peer / "memories").mkdir(parents=True)
        peer_p = CubeMemoryProvider(auto_extract=False)
        peer_p.initialize(
            session_id="peer",
            hermes_home=str(peer),
            agent_identity="researcher",
            platform="cli",
        )
        peer_p._cube.append(
            "belief",
            "Wayback Machine snapshots beat live pages for citation stability",
            data={"durable": True, "crystal": True, "trust": 0.9},
        )
        peer_p._hive_path = str(hive)
        # Close before pilgrimage opens the same cube file exclusively
        peer_p.shutdown()
        from hermescube import hive as hive_mod

        t0 = time.perf_counter()
        r_peer = hive_mod.pilgrimage(
            str(hive), hermes_home=str(peer), agent_id="researcher", focus="sources"
        )
        peer_pilgrim_ms = _ms(t0)

        # Close coder cube before pilgrimage rewrite
        p.shutdown()

        t0 = time.perf_counter()
        r_coder = hive_mod.pilgrimage(
            str(hive), hermes_home=str(home), agent_id="coder", focus="sources"
        )
        coder_pilgrim_ms = _ms(t0)

        drew = int((r_coder.get("draw") or {}).get("drawn") or 0)
        growth2 = r_coder.get("growth") or {}
        report["scenarios"]["hive_pilgrimage"] = {
            "peer_pilgrim_ms": peer_pilgrim_ms,
            "coder_pilgrim_ms": coder_pilgrim_ms,
            "peer_offered": (r_peer.get("offer") or {}).get("rows", 0),
            "coder_drew": drew,
            "coder_growth": {
                "bumped": growth2.get("bumped"),
                "version": growth2.get("to") or growth2.get("version"),
                "age": growth2.get("age"),
                "era_label": growth2.get("era_label") or era_label(growth2.get("era")),
            },
            "ok": bool(r_peer.get("ok") and r_coder.get("ok") and drew >= 1),
        }

        # ── 3. Cross-session reopen (Hermes restart) ──────────────
        # Reopen after pilgrimage so drawn peer wisdom is visible (fresh CubeFile).
        p2 = CubeMemoryProvider(auto_extract=False)
        t0 = time.perf_counter()
        p2.initialize(
            session_id="sess-2",
            hermes_home=str(home),
            agent_identity="coder",
            platform="cli",
        )
        reopen_ms = _ms(t0)

        t0 = time.perf_counter()
        after = p2.prefetch("Wayback citation snapshots", session_id="sess-2") or ""
        after_ms = _ms(t0)
        report["scenarios"]["post_draw_prefetch"] = {
            "ms": after_ms,
            "hit_wayback": "wayback" in after.lower() or "snapshot" in after.lower(),
            "drawn": drew,
        }

        text = p2.prefetch("Cube of Eden") or ""
        g2 = growth_status(str(home), cube=p2._cube)
        known_eras = {"eden", "awakening", "formed", "seasoned", "elder"}
        report["scenarios"]["cross_session"] = {
            "reopen_ms": reopen_ms,
            "entries": p2._cube.entry_count if p2._cube else 0,
            "era": g2.get("era"),
            "era_label": g2.get("era_label"),
            "era_known": g2.get("era") in known_eras,
            "hit_eden_or_growth": (
                "eden" in text.lower()
                or "0.0.0" in text
                or "awakening" in text.lower()
                or "growth" in text.lower()
                or bool(g2.get("version"))
            ),
            "living_version": g2.get("version"),
            "cycles": (g2.get("age") or {}).get("cycles"),
            "grew_past_genesis": (g2.get("version") or "0.0.0") != "0.0.0",
        }
        p2.shutdown()

    # Gates (Hermes-useful thresholds)
    life = report["scenarios"]["lifecycle"]
    hive_s = report["scenarios"]["hive_pilgrimage"]
    cross = report["scenarios"]["cross_session"]
    post = report["scenarios"]["post_draw_prefetch"]
    gates = {
        "init_lt_500ms": life["init_ms"] < 500,
        "prefetch_p50_lt_25ms": life["prefetch_p50_ms"] < 25,
        "durable_hit_rate_ge_0.8": life["hit_rate"] >= 0.8,
        "eden_era_ok": life["era_ok"],  # starts in Cube of Eden
        "session_end_lt_5000ms": life["session_end_ms"] < 5000,
        "hive_pilgrimage_ok": hive_s["ok"],
        "post_draw_hit": post["hit_wayback"],
        # After pilgrimage the cube may leave Eden (Awakening+) — persist growth
        "cross_session_growth_persists": (
            cross["era_known"]
            and cross["grew_past_genesis"]
            and int(cross.get("cycles") or 0) >= 1
        ),
        "cross_session_reopen_lt_500ms": cross["reopen_ms"] < 500,
    }
    report["gates"] = gates
    report["pass"] = all(gates.values())

    out = lab / f"hermes-usage-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["path"] = str(out)
    return report


def main() -> int:
    r = run()
    print(f"Hermes Agent × HermesCube usage bench v{r['hermescube']}")
    print(f"pass={r['pass']}")
    print("gates:")
    for k, v in r["gates"].items():
        print(f"  {'OK' if v else 'FAIL':4} {k}")
    life = r["scenarios"]["lifecycle"]
    print("\nlifecycle:")
    print(f"  init={life['init_ms']}ms  sync_p50={life['sync_turn_p50_ms']}ms  "
          f"prefetch_p50={life['prefetch_p50_ms']}ms  end={life['session_end_ms']}ms")
    print(f"  hit_rate={life['hit_rate']:.2f}  era={life['era_label']}  "
          f"v{life['living_version']}  entries={life['entries']}")
    hive_s = r["scenarios"]["hive_pilgrimage"]
    print("\nhive:")
    print(f"  drew={hive_s['coder_drew']}  pilgrim_ms={hive_s['coder_pilgrim_ms']}  "
          f"growth={hive_s['coder_growth']}")
    cross = r["scenarios"]["cross_session"]
    print("\ncross-session:")
    print(f"  reopen={cross['reopen_ms']}ms  entries={cross['entries']}  "
          f"cycles={cross['cycles']}  v{cross['living_version']}  "
          f"era={cross.get('era_label')}")
    print(f"\n→ {r['path']}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
