#!/usr/bin/env python3
"""Cross-exam: Hermes builtin memory vs holographic vs HermesCube.

Arms
----
A. Builtin MemoryStore (MEMORY.md / USER.md) — Hermes default when
   ``memory.provider`` is empty. No retrieval; recall = frozen system-prompt dump.
B. Bundled holographic MemoryProvider — local SQLite + FTS/HRR.
C. HermesCube CubeMemoryProvider — local cube + HAR.

Stress regimes (loophole-closed)
--------------------------------
- Exact-token probes (FTS-friendly baseline)
- Paraphrase probes (natural language — no exact needle in query)
- Noise flood (durable needles buried under chat noise)
- Capacity overflow (prove builtin hard-rejects past 2200 chars)
- Cross-session reopen (shutdown → new provider → same home)
- Scale 500 / 1000 / 2000
- Hermes MemoryManager wiring smoke (Cube through ABC orchestrator)

Requires HERMES_AGENT_ROOT (default /tmp/hermes-agent-research) on PYTHONPATH
for arms A/B. Arm C uses this repo.
"""

from __future__ import annotations

import json
import os
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


_PROJECTS = (
    "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
    "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
)


def _facts(n: int) -> list[str]:
    """Distinctive durable facts — near-duplicate numeric corpora are unfair
    to lex rankers and unrealistically easy for FTS OR matching.

    Project ids use spaces (not hyphens) so holographic FTS5 and Cube lex
    both tokenize the id consistently.
    """
    out = []
    for i in range(n):
        proj = _PROJECTS[i % len(_PROJECTS)]
        out.append(
            f"Operator vault credential for project {proj} {i:04d} "
            f"is tok {i:04d} secret unlocked via service {i % 17}"
        )
    return out


def _noise(n: int) -> list[str]:
    return [
        f"Side chatter {i}: widgets look fine today, nothing durable about tokens."
        for i in range(n)
    ]


def _probe_idxs(n_facts: int, m: int) -> list[int]:
    idxs = sorted({(i * max(1, n_facts // m)) % n_facts for i in range(m)})
    while len(idxs) < m:
        idxs.append(len(idxs) % n_facts)
    return idxs[:m]


def _exact_probes(n_facts: int, m: int) -> list[tuple[str, str]]:
    return [
        (f"tok {i:04d} secret", f"tok {i:04d} secret")
        for i in _probe_idxs(n_facts, m)
    ]


def _paraphrase_probes(n_facts: int, m: int) -> list[tuple[str, str]]:
    """Natural-language queries that do NOT contain the secret needle.

    Includes the distinctive project id so retrieval has a real handle —
    matching how operators actually ask ('what's the vault for project X').
    """
    out = []
    for i in _probe_idxs(n_facts, m):
        proj = _PROJECTS[i % len(_PROJECTS)]
        q = f"which vault credential does project {proj} {i:04d} use"
        needle = f"tok {i:04d} secret"
        assert needle.lower() not in q.lower(), (q, needle)
        out.append((q, needle))
    return out


# ── Arm A: Hermes builtin MemoryStore ────────────────────────────────


def run_builtin(
    facts: list[str],
    probes: list[tuple[str, str]],
    *,
    overflow_extra: int = 0,
) -> dict:
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
                reject_reason = str(r.get("error") or r)[:240]

    # Mid-session freeze loophole: live entries updated, snapshot frozen until reload
    mid_block = store.format_for_system_prompt("memory") or ""
    mid_sees_seeds = sum(
        1 for _q, needle in probes if needle.lower() in mid_block.lower()
    )

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
        text = block
        recall_ms.append(_ms(t0))
        hits.append(needle.lower() in text.lower())

    overflow_rejected = 0
    if overflow_extra > 0:
        # Force the 2200-char wall — pad until reject (or safety cap).
        for j in range(max(overflow_extra, 40)):
            r = store.add(
                "memory",
                f"Overflow filler {j:04d} " + ("x" * 400),
            )
            if not r.get("success"):
                overflow_rejected += 1
                if not reject_reason:
                    reject_reason = str(r.get("error") or r)[:240]
                break

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
        "mid_session_snapshot_hits": mid_sees_seeds,
        "mid_session_frozen": mid_sees_seeds == 0 and seeded > 0,
        "overflow_attempted": overflow_extra,
        "overflow_rejected": overflow_rejected,
        "notes": (
            "Hit = needle in frozen system-prompt after reload. "
            "Mid-session adds do not update the snapshot until load_from_disk()."
        ),
    }


# ── Arm B: holographic MemoryProvider ────────────────────────────────


def run_holographic(
    facts: list[str],
    probes: list[tuple[str, str]],
    *,
    noise: list[str] | None = None,
    reopen: bool = False,
) -> dict:
    home = Path(tempfile.mkdtemp(prefix="holo-"))
    os.environ["HERMES_HOME"] = str(home)
    (home / "memories").mkdir(parents=True)

    from plugins.memory.holographic import HolographicMemoryProvider

    def _make() -> HolographicMemoryProvider:
        # Default dim=1024. Raising dim made N=2000 adds pathologically slow —
        # that is itself a scale finding (documented in scale_2000 skip).
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
        return p

    p = _make()

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

    noise_n = 0
    for n in noise or []:
        p.handle_tool_call(
            "fact_store",
            {"action": "add", "content": n, "category": "general"},
        )
        noise_n += 1

    def _measure(provider) -> tuple[list[float], list[bool], list[float], list[bool]]:
        pref_ms, pref_hits, search_ms, search_hits = [], [], [], []
        for q, needle in probes:
            t0 = time.perf_counter()
            text = provider.prefetch(q, session_id="bench") or ""
            pref_ms.append(_ms(t0))
            pref_hits.append(needle.lower() in text.lower())

            t0 = time.perf_counter()
            raw = provider.handle_tool_call(
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
        return pref_ms, pref_hits, search_ms, search_hits

    pref_ms, pref_hits, search_ms, search_hits = _measure(p)

    reopen_hit = None
    reopen_ms = None
    if reopen:
        p.shutdown()
        t0 = time.perf_counter()
        p2 = _make()
        reopen_ms = _ms(t0)
        _pm, ph, _sm, sh = _measure(p2)
        reopen_hit = round(sum(sh) / len(sh), 3) if sh else 0.0
        p2.shutdown()
    else:
        p.shutdown()

    return {
        "arm": "holographic",
        "contract": "MemoryProvider (fact_store + prefetch top-5)",
        "seeded": seeded,
        "noise": noise_n,
        "rejected": len(facts) - seeded,
        "add_p50_ms": _pct(add_ms, 50),
        "add_p95_ms": _pct(add_ms, 95),
        "prefetch_p50_ms": _pct(pref_ms, 50),
        "prefetch_p95_ms": _pct(pref_ms, 95),
        "prefetch_hit_rate": round(sum(pref_hits) / len(pref_hits), 3) if pref_hits else 0.0,
        "search_p50_ms": _pct(search_ms, 50),
        "search_p95_ms": _pct(search_ms, 95),
        "search_hit_rate": round(sum(search_hits) / len(search_hits), 3) if search_hits else 0.0,
        "reopen_ms": reopen_ms,
        "reopen_search_hit": reopen_hit,
        "notes": "Prefetch capped at top-5; search uses limit=10.",
    }


# ── Arm C: HermesCube CubeMemoryProvider ─────────────────────────────


def run_cube(
    facts: list[str],
    probes: list[tuple[str, str]],
    *,
    noise: list[str] | None = None,
    reopen: bool = False,
    evolve: bool = False,
) -> dict:
    home = Path(tempfile.mkdtemp(prefix="cube-"))
    (home / "memories").mkdir(parents=True)

    from hermescube.provider import CubeMemoryProvider

    def _make(session_id: str = "bench") -> CubeMemoryProvider:
        p = CubeMemoryProvider(auto_extract=False)
        p.initialize(
            session_id=session_id,
            hermes_home=str(home),
            platform="cli",
            agent_context="primary",
            agent_identity="bench",
        )
        return p

    p = _make("bench")

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

    noise_n = 0
    for n in noise or []:
        # Noise as low-trust manage facts (same store surface as durable seeds)
        p.handle_tool_call(
            "hermescube_manage",
            {"action": "add", "entry_type": "belief", "content": n},
        )
        noise_n += 1
    # Also exercise Hermes sync path once (not N times — avoid flush stalls)
    if noise_n:
        p.sync_turn(
            "Side chatter batch: widgets look fine, nothing durable.",
            "ok noted.",
            session_id="bench",
        )
        if hasattr(p, "_sync_queue"):
            p._sync_queue.flush(timeout=10.0)

    evolve_ms = None
    if evolve and p._engine is not None:
        t0 = time.perf_counter()
        try:
            p._engine.evolve()
            if p._void is not None:
                p._void.rebuild_lex()
                setattr(p._engine, "_lexindex", p._void.lex)
        except Exception:
            pass
        evolve_ms = _ms(t0)

    def _measure(provider) -> tuple[list[float], list[bool], list[float], list[bool]]:
        pref_ms, pref_hits, search_ms, search_hits = [], [], [], []
        for q, needle in probes:
            t0 = time.perf_counter()
            text = provider.prefetch(q, session_id="bench") or ""
            pref_ms.append(_ms(t0))
            pref_hits.append(needle.lower() in text.lower())

            t0 = time.perf_counter()
            raw = provider.handle_tool_call(
                "hermescube_search",
                {"query": q, "top_k": 10},
            )
            search_ms.append(_ms(t0))
            try:
                payload = json.loads(raw)
                results = payload.get("results") or []
                blob = " ".join(
                    str(r.get("description") or r.get("content") or "") for r in results
                )
            except Exception:
                blob = raw if isinstance(raw, str) else ""
            search_hits.append(needle.lower() in blob.lower())
        return pref_ms, pref_hits, search_ms, search_hits

    pref_ms, pref_hits, search_ms, search_hits = _measure(p)

    from hermescube.genealogy import growth_status

    g = growth_status(str(home), cube=p._cube)
    prompt = p.system_prompt_block()

    reopen_hit = None
    reopen_ms = None
    reopen_eden = None
    if reopen:
        p.shutdown()
        t0 = time.perf_counter()
        p2 = _make("bench-reopen")
        reopen_ms = _ms(t0)
        _pm, _ph, _sm, sh = _measure(p2)
        reopen_hit = round(sum(sh) / len(sh), 3) if sh else 0.0
        reopen_eden = "Cube of Eden" in (p2.system_prompt_block() or "") or (
            growth_status(str(home), cube=p2._cube).get("era") in ("eden", "awakening", "formed")
        )
        p2.shutdown()
    else:
        p.shutdown()

    return {
        "arm": "hermescube",
        "contract": "MemoryProvider (hermescube_manage/search + prefetch)",
        "seeded": seeded,
        "noise": noise_n,
        "rejected": len(facts) - seeded,
        "add_p50_ms": _pct(add_ms, 50),
        "add_p95_ms": _pct(add_ms, 95),
        "prefetch_p50_ms": _pct(pref_ms, 50),
        "prefetch_p95_ms": _pct(pref_ms, 95),
        "prefetch_hit_rate": round(sum(pref_hits) / len(pref_hits), 3) if pref_hits else 0.0,
        "search_p50_ms": _pct(search_ms, 50),
        "search_p95_ms": _pct(search_ms, 95),
        "search_hit_rate": round(sum(search_hits) / len(search_hits), 3) if search_hits else 0.0,
        "evolve_ms": evolve_ms,
        "reopen_ms": reopen_ms,
        "reopen_search_hit": reopen_hit,
        "reopen_era_ok": reopen_eden,
        "era": g.get("era"),
        "era_label": g.get("era_label"),
        "living_version": g.get("version"),
        "eden_in_prompt": "Cube of Eden" in prompt,
        "notes": "Prefetch evidence packet; search top_k=10; noise via sync_turn.",
    }


def run_memory_manager_smoke() -> dict:
    """Wire Cube through Hermes MemoryManager (production orchestrator)."""
    if not HERMES_ROOT.is_dir():
        return {"ok": False, "skipped": True, "reason": "no hermes root"}

    from agent.memory_manager import MemoryManager, build_memory_context_block
    from hermescube.provider import CubeMemoryProvider
    from hermescube.genealogy import growth_status

    home = Path(tempfile.mkdtemp(prefix="mm-"))
    (home / "memories").mkdir(parents=True)
    cube = CubeMemoryProvider(auto_extract=False)
    mm = MemoryManager()
    mm.add_provider(cube)
    mm.initialize_all(
        session_id="mm-bench",
        hermes_home=str(home),
        platform="cli",
        agent_context="primary",
        agent_identity="bench",
    )

    raw = cube.handle_tool_call(
        "hermescube_manage",
        {
            "action": "add",
            "entry_type": "belief",
            "content": "Operator prefers concise bullet answers under load",
        },
    )
    assert "error" not in json.loads(raw)

    prompt = cube.system_prompt_block() or ""
    t0 = time.perf_counter()
    ctx = mm.prefetch_all("concise bullet answers", session_id="mm-bench") or ""
    pref_ms = _ms(t0)
    fenced = build_memory_context_block(ctx) if ctx else ""
    hit = "concise" in ctx.lower() or "bullet" in ctx.lower()
    schemas = cube.get_tool_schemas()
    g = growth_status(str(home), cube=cube._cube)
    mm.shutdown_all()

    return {
        "ok": bool(hit and len(schemas) >= 3 and "HermesCube" in prompt),
        "prefetch_ms": pref_ms,
        "hit": hit,
        "fenced": "<memory-context>" in fenced or bool(ctx),
        "tool_schemas": len(schemas),
        "eden_in_prompt": "Cube of Eden" in prompt,
        "era": g.get("era"),
        "living_version": g.get("version"),
    }


def run() -> dict:
    from hermescube import __version__

    lab = _lab()
    report: dict = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "hermescube": __version__,
        "hermes_agent_root": str(HERMES_ROOT),
        "regimes": {},
        "stress": {},
        "gates": {},
    }

    def _prog(msg: str) -> None:
        print(f"… {msg}", flush=True)

    # Stress first (fast failure signal), then scale.
    _prog("stress memory_manager")
    report["stress"]["memory_manager"] = run_memory_manager_smoke()

    _prog("regime capacity_fair N=12")
    facts = _facts(12)
    probes = _exact_probes(12, 8)
    report["regimes"]["capacity_fair"] = {
        "n_facts": 12,
        "n_probes": 8,
        "mode": "exact",
        "arms": {
            "builtin": run_builtin(facts, probes, overflow_extra=5),
            "holographic": run_holographic(facts, probes)
            if HERMES_ROOT.is_dir()
            else {"skipped": True, "reason": "no hermes"},
            "hermescube": run_cube(facts, probes),
        },
    }

    _prog("stress paraphrase_200")
    facts_p = _facts(200)
    probes_p = _paraphrase_probes(200, 20)
    report["stress"]["paraphrase_200"] = {
        "n_facts": 200,
        "n_probes": 20,
        "arms": {
            "holographic": run_holographic(facts_p, probes_p)
            if HERMES_ROOT.is_dir()
            else {"skipped": True},
            "hermescube": run_cube(facts_p, probes_p),
        },
    }

    _prog("stress noise_flood (20+80)")
    durable = _facts(20)
    probes_n = _exact_probes(20, 10)
    noise = _noise(80)
    report["stress"]["noise_flood"] = {
        "durable": 20,
        "noise": 80,
        "n_probes": 10,
        "arms": {
            "holographic": run_holographic(durable, probes_n, noise=noise)
            if HERMES_ROOT.is_dir()
            else {"skipped": True},
            "hermescube": run_cube(durable, probes_n, noise=noise),
        },
    }

    _prog("stress cross_session_300")
    facts_r = _facts(300)
    probes_r = _exact_probes(300, 20)
    report["stress"]["cross_session_300"] = {
        "n_facts": 300,
        "n_probes": 20,
        "arms": {
            "holographic": run_holographic(facts_r, probes_r, reopen=True)
            if HERMES_ROOT.is_dir()
            else {"skipped": True},
            "hermescube": run_cube(facts_r, probes_r, reopen=True),
        },
    }

    for name, n_facts, n_probes, holo in (
        ("scale_500", 500, 25, True),
        ("scale_1000", 1000, 40, True),
        ("scale_2000", 2000, 50, False),  # cube only — holo HRR wall
    ):
        _prog(f"regime {name} N={n_facts}")
        facts = _facts(n_facts)
        probes = _exact_probes(n_facts, n_probes)
        arms: dict = {
            "builtin": {
                "arm": "builtin_memory_store",
                "skipped": True,
                "reason": f"N={n_facts} exceeds 2200-char MEMORY.md budget",
                "capacity_chars": 2200,
            }
        }
        if holo and HERMES_ROOT.is_dir():
            arms["holographic"] = run_holographic(facts, probes)
        else:
            arms["holographic"] = {
                "arm": "holographic",
                "skipped": True,
                "reason": (
                    f"N={n_facts}: holographic HRR add path too slow at this scale"
                    if not holo
                    else "no hermes"
                ),
            }
        arms["hermescube"] = run_cube(facts, probes)
        report["regimes"][name] = {
            "n_facts": n_facts,
            "n_probes": n_probes,
            "mode": "exact",
            "arms": arms,
        }

    # ── Gates ─────────────────────────────────────────────────────
    fair = report["regimes"]["capacity_fair"]["arms"]
    s500 = report["regimes"]["scale_500"]["arms"]
    s1k = report["regimes"]["scale_1000"]["arms"]
    s2k = report["regimes"]["scale_2000"]["arms"]
    para = report["stress"]["paraphrase_200"]["arms"]
    noise_s = report["stress"]["noise_flood"]["arms"]
    cross = report["stress"]["cross_session_300"]["arms"]
    mm = report["stress"]["memory_manager"]

    gates = {
        # Builtin contract
        "fair_builtin_seeded_all": fair["builtin"].get("seeded") == 12,
        "fair_builtin_hit_1": fair["builtin"].get("hit_rate", 0) >= 1.0,
        "fair_builtin_overflow_rejects": fair["builtin"].get("overflow_rejected", 0) >= 1,
        "fair_builtin_mid_session_frozen": bool(fair["builtin"].get("mid_session_frozen")),
        # Cube baseline
        "fair_cube_prefetch_hit_ge_0.8": fair["hermescube"].get("prefetch_hit_rate", 0) >= 0.8,
        "fair_eden_in_cube_prompt": bool(fair["hermescube"].get("eden_in_prompt")),
        "scale500_cube_search_hit_ge_0.8": s500["hermescube"].get("search_hit_rate", 0) >= 0.8,
        "scale500_cube_prefetch_p50_lt_100ms": s500["hermescube"].get("prefetch_p50_ms", 999) < 100,
        "scale1000_cube_search_hit_ge_0.7": s1k["hermescube"].get("search_hit_rate", 0) >= 0.7,
        "scale1000_cube_prefetch_p50_lt_150ms": s1k["hermescube"].get("prefetch_p50_ms", 999) < 150,
        "scale2000_cube_search_hit_ge_0.6": s2k["hermescube"].get("search_hit_rate", 0) >= 0.6,
        "scale2000_cube_prefetch_p50_lt_250ms": s2k["hermescube"].get("prefetch_p50_ms", 999) < 250,
        "scale500_builtin_skipped": bool(s500["builtin"].get("skipped")),
        "scale1000_builtin_skipped": bool(s1k["builtin"].get("skipped")),
        "scale2000_builtin_skipped": bool(s2k["builtin"].get("skipped")),
        # Stress
        "paraphrase_cube_search_ge_0.6": para["hermescube"].get("search_hit_rate", 0) >= 0.6,
        "noise_cube_search_ge_0.8": noise_s["hermescube"].get("search_hit_rate", 0) >= 0.8,
        "cross_cube_reopen_hit_ge_0.7": (cross["hermescube"].get("reopen_search_hit") or 0) >= 0.7,
        "cross_cube_reopen_lt_1000ms": (cross["hermescube"].get("reopen_ms") or 9999) < 1000,
        "memory_manager_ok": bool(mm.get("ok")),
    }
    if not fair["holographic"].get("skipped"):
        gates["fair_holo_seeded_all"] = fair["holographic"].get("seeded") == 12
        gates["fair_holo_search_hit_ge_0.8"] = fair["holographic"].get("search_hit_rate", 0) >= 0.8
        gates["scale500_holo_search_hit_ge_0.5"] = s500["holographic"].get("search_hit_rate", 0) >= 0.5
        gates["scale500_cube_search_ge_holo"] = (
            s500["hermescube"].get("search_hit_rate", 0)
            >= s500["holographic"].get("search_hit_rate", 0)
        )
        gates["paraphrase_holo_search_ge_0.4"] = para["holographic"].get("search_hit_rate", 0) >= 0.4
        gates["noise_holo_search_ge_0.5"] = noise_s["holographic"].get("search_hit_rate", 0) >= 0.5
        gates["cross_holo_reopen_hit_ge_0.5"] = (
            (cross["holographic"].get("reopen_search_hit") or 0) >= 0.5
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
            f"hit={arm['hit_rate']}  "
            f"overflow_rej={arm.get('overflow_rejected')}  "
            f"mid_frozen={arm.get('mid_session_frozen')}"
        )
        return
    extra = ""
    if arm.get("reopen_search_hit") is not None:
        extra = f"  reopen_hit={arm['reopen_search_hit']} ({arm.get('reopen_ms')}ms)"
    if arm.get("noise"):
        extra += f"  noise={arm['noise']}"
    print(
        f"  {label:12} seeded={arm['seeded']}  "
        f"add_p50={arm['add_p50_ms']}ms  "
        f"prefetch_p50={arm['prefetch_p50_ms']}ms hit={arm['prefetch_hit_rate']}  "
        f"search_p50={arm['search_p50_ms']}ms hit={arm['search_hit_rate']}"
        f"{extra}"
    )


def main() -> int:
    r = run()
    print(f"Cross-exam STRESS: Hermes builtin vs holographic vs HermesCube v{r['hermescube']}")
    print(f"pass={r['pass']}")
    print("gates:")
    for k, v in r["gates"].items():
        print(f"  {'OK' if v else 'FAIL':4} {k}")
    for name, regime in r["regimes"].items():
        print(f"\n{name} (N={regime['n_facts']}, probes={regime['n_probes']}, mode={regime['mode']}):")
        arms = regime["arms"]
        _print_arm("builtin", arms["builtin"])
        _print_arm("holographic", arms["holographic"])
        _print_arm("hermescube", arms["hermescube"])
        cube = arms["hermescube"]
        if cube.get("era_label"):
            print(f"             era={cube['era_label']} v{cube.get('living_version')}")
    print("\nstress:")
    for name, block in r["stress"].items():
        if name == "memory_manager":
            print(f"  {name}: ok={block.get('ok')} hit={block.get('hit')} "
                  f"prefetch_ms={block.get('prefetch_ms')} schemas={block.get('tool_schemas')}")
            continue
        print(f"  {name}:")
        for arm_name, arm in (block.get("arms") or {}).items():
            _print_arm(arm_name, arm)
    print(f"\n→ {r['path']}")
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
