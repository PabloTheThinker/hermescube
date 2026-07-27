#!/usr/bin/env python3
"""Live Hermes Agent × HermesCube integration bench.

Exercises the *real* Hermes MemoryManager orchestrator with CubeMemoryProvider
as the single external memory plugin — the production wiring path Hermes uses
when ``memory.provider: hermescube``.

Scenarios
---------
1. MemoryManager lifecycle (init → sync → prefetch → tools → session_end)
2. Cross-session reopen through MemoryManager
3. Cuboasis governance via manage tools (capture/review/approve/doctor)
4. Builtin MEMORY.md mirror via on_memory_write
5. Optional holographic peer arm (same Hermes ABC) for timing contrast
6. Gate rollup for CI-style pass/fail

Requires HERMES_AGENT_ROOT (default /tmp/hermes-agent-research) on PYTHONPATH.
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


def _gate(report: dict, name: str, ok: bool) -> None:
    report.setdefault("gates", {})[name] = bool(ok)


FACTS = [
    ("trait", "Operator prefers concise bullet answers under load"),
    ("belief", "Always triangulate three independent sources before citing"),
    ("landmark", "HermesCube cube path is HERMES_HOME memories memory.cube"),
    ("resolve", "Ship gate scrub secrets before public push"),
    ("belief", "Living cube starts in the Cube of Eden at version 0.0.0"),
    ("belief", "Cuboasis review-first candidates are not execution evidence"),
    ("belief", "Project Alpha uses vault tokens for service auth"),
    ("relationship", "Alice owns billing service on Redis cluster"),
]


def run_hermes_manager_lifecycle() -> dict:
    from agent.memory_manager import MemoryManager, build_memory_context_block
    from hermescube import __version__
    from hermescube.genealogy import growth_status
    from hermescube.provider import CubeMemoryProvider

    home = Path(tempfile.mkdtemp(prefix="live-hermes-cube-"))
    (home / "memories").mkdir(parents=True)

    cube = CubeMemoryProvider(auto_extract=False)
    mm = MemoryManager()
    mm.add_provider(cube)

    t0 = time.perf_counter()
    mm.initialize_all(
        session_id="live-sess-1",
        hermes_home=str(home),
        platform="cli",
        agent_context="primary",
        agent_identity="coder",
        agent_workspace="bench",
    )
    init_ms = _ms(t0)

    prompt = cube.system_prompt_block() or ""
    schemas = cube.get_tool_schemas() or []
    schema_names = []
    for s in schemas:
        if isinstance(s, dict):
            schema_names.append(str(s.get("name") or (s.get("function") or {}).get("name") or ""))

    # Seed via MemoryManager tool router (production Hermes dispatch path)
    add_ms: list[float] = []
    ids: list[str] = []
    for et, content in FACTS:
        t1 = time.perf_counter()
        raw = mm.handle_tool_call(
            "hermescube_manage",
            {"action": "add", "entry_type": et, "content": content},
        )
        add_ms.append(_ms(t1))
        rec = json.loads(raw)
        if rec.get("id"):
            ids.append(str(rec["id"]))

    # Hermes turn loop: sync_turn + prefetch_all
    sync_ms: list[float] = []
    for i, (et, content) in enumerate(FACTS[:5]):
        t1 = time.perf_counter()
        mm.sync_all(
            f"Please remember: {content}",
            f"Noted [{et}]. Stored for later recall.",
            session_id="live-sess-1",
        )
        sync_ms.append(_ms(t1))

    probes = [
        "concise bullet answers",
        "triangulate three sources",
        "memory.cube path",
        "Cube of Eden",
        "Alice owns billing",
        "vault tokens Alpha",
        "Cuboasis candidates not evidence",
    ]
    pref_ms: list[float] = []
    pref_hits: list[bool] = []
    fenced_ok = 0
    for q in probes:
        t1 = time.perf_counter()
        ctx = mm.prefetch_all(q, session_id="live-sess-1") or ""
        pref_ms.append(_ms(t1))
        fenced = build_memory_context_block(ctx) if ctx else ""
        if "<memory-context>" in fenced or ctx:
            fenced_ok += 1
        # hit: any distinctive token from the probe family
        blob = ctx.lower()
        hit = any(
            tok in blob
            for tok in (
                "concise",
                "bullet",
                "triangulate",
                "memory.cube",
                "eden",
                "alice",
                "billing",
                "vault",
                "alpha",
                "cuboasis",
                "candidate",
            )
        )
        pref_hits.append(hit)
        mm.queue_prefetch_all(q)

    # Builtin MEMORY.md mirror
    cube.on_memory_write(
        "add",
        "memory",
        "User prefers dark mode in the IDE",
        {"write_origin": "builtin", "session_id": "live-sess-1"},
    )
    t1 = time.perf_counter()
    mirror_ctx = mm.prefetch_all("dark mode IDE", session_id="live-sess-1") or ""
    mirror_ms = _ms(t1)
    mirror_hit = "dark" in mirror_ctx.lower() and "mode" in mirror_ctx.lower()

    # Cuboasis governance through MemoryManager-routed manage tool
    cap = json.loads(
        mm.handle_tool_call(
            "hermescube_manage",
            {
                "action": "cuboasis",
                "mode": "capture",
                "content": "Fleet HQ charters must stay review-first before durable write",
            },
        )
    )
    rev = json.loads(
        mm.handle_tool_call(
            "hermescube_manage",
            {"action": "cuboasis", "mode": "review"},
        )
    )
    cid = cap.get("candidate_id") or ""
    ap = {"ok": False}
    if cid:
        ap = json.loads(
            mm.handle_tool_call(
                "hermescube_manage",
                {"action": "cuboasis", "mode": f"approve:{cid}"},
            )
        )
    doc = json.loads(
        mm.handle_tool_call(
            "hermescube_manage",
            {"action": "cuboasis", "mode": "doctor"},
        )
    )
    oasis = json.loads(
        mm.handle_tool_call(
            "hermescube_manage",
            {"action": "cuboasis"},
        )
    )

    # Feedback loop
    fb_ok = False
    if ids:
        fb = json.loads(
            mm.handle_tool_call(
                "hermescube_feedback",
                {"action": "helpful", "entry_id": ids[0]},
            )
        )
        fb_ok = fb.get("status") in ("ok", "updated", "feedback", "rated") or (
            "error" not in fb and fb.get("id")
        )

    # Search tool
    sr = json.loads(
        mm.handle_tool_call(
            "hermescube_search",
            {"query": "Alice billing Redis", "top_k": 5},
        )
    )
    search_hit = any(
        "alice" in str(h.get("description") or "").lower()
        or "billing" in str(h.get("description") or "").lower()
        for h in (sr.get("results") or [])
    )

    g_before = growth_status(str(home), cube=cube._cube)
    t1 = time.perf_counter()
    mm.on_session_end([])
    # drain background work
    try:
        cube._sync_queue.flush(timeout=20)
    except Exception:
        pass
    end_ms = _ms(t1)
    g_after = growth_status(str(home), cube=cube._cube)

    entries = int(getattr(cube._cube, "entry_count", 0) or 0)
    mm.shutdown_all()

    hit_rate = round(sum(pref_hits) / len(pref_hits), 3) if pref_hits else 0.0
    return {
        "arm": "hermes_memory_manager+hermescube",
        "hermescube": __version__,
        "hermes_agent_root": str(HERMES_ROOT),
        "home": str(home),
        "init_ms": init_ms,
        "entries": entries,
        "seeded_ids": len(ids),
        "add_p50_ms": _pct(add_ms, 50),
        "sync_p50_ms": _pct(sync_ms, 50),
        "prefetch_p50_ms": _pct(pref_ms, 50),
        "prefetch_p95_ms": _pct(pref_ms, 95),
        "prefetch_hit_rate": hit_rate,
        "fenced_turns": fenced_ok,
        "fenced_total": len(probes),
        "mirror_hit": mirror_hit,
        "mirror_ms": mirror_ms,
        "search_hit": search_hit,
        "feedback_ok": fb_ok,
        "tool_schemas": len(schemas),
        "tool_names": [n for n in schema_names if n],
        "prompt_has_hermescube": "HermesCube" in prompt or "Cuboasis" in prompt,
        "prompt_has_eden": "Cube of Eden" in prompt or "eden" in prompt.lower(),
        "prompt_has_cuboasis": "Cuboasis" in prompt,
        "governance": {
            "capture_ok": bool(cap.get("ok") or cap.get("status") == "capture"),
            "pending": rev.get("count", 0),
            "approve_ok": bool(ap.get("ok")),
            "doctor_health": doc.get("health"),
            "oasis_framework": oasis.get("framework") or oasis.get("status"),
        },
        "session_end_ms": end_ms,
        "growth_before": {
            "version": g_before.get("version"),
            "era": g_before.get("era"),
            "era_label": g_before.get("era_label"),
        },
        "growth_after": {
            "version": g_after.get("version"),
            "era": g_after.get("era"),
            "era_label": g_after.get("era_label"),
        },
    }


def run_cross_session_reopen(home: str) -> dict:
    """Re-open the same HERMES_HOME through a fresh MemoryManager."""
    from agent.memory_manager import MemoryManager
    from hermescube.provider import CubeMemoryProvider
    from hermescube.genealogy import growth_status

    cube = CubeMemoryProvider(auto_extract=False)
    mm = MemoryManager()
    mm.add_provider(cube)
    t0 = time.perf_counter()
    mm.initialize_all(
        session_id="live-sess-2",
        hermes_home=home,
        platform="cli",
        agent_context="primary",
        agent_identity="coder",
        agent_workspace="bench",
    )
    reopen_ms = _ms(t0)
    ctx = mm.prefetch_all("Alice owns billing", session_id="live-sess-2") or ""
    hit = "alice" in ctx.lower() or "billing" in ctx.lower()
    g = growth_status(home, cube=cube._cube)
    entries = int(getattr(cube._cube, "entry_count", 0) or 0)
    # Cuboasis status persists
    oasis = json.loads(
        cube.handle_tool_call("hermescube_manage", {"action": "cuboasis"})
    )
    mm.shutdown_all()
    return {
        "reopen_ms": reopen_ms,
        "hit": hit,
        "entries": entries,
        "era": g.get("era"),
        "era_label": g.get("era_label"),
        "version": g.get("version"),
        "oasis_ok": oasis.get("ok") or oasis.get("status") == "cuboasis",
        "pending_candidates": (oasis.get("governance") or {}).get("pending_candidates"),
    }


def run_holographic_contrast() -> dict:
    """Optional peer arm — same MemoryManager, bundled holographic provider."""
    try:
        from plugins.memory.holographic import HolographicMemoryProvider  # type: ignore
    except Exception as e:
        return {"skipped": True, "reason": f"import: {e}"}

    from agent.memory_manager import MemoryManager

    home = Path(tempfile.mkdtemp(prefix="live-holo-"))
    (home / "memories").mkdir(parents=True)
    try:
        prov = HolographicMemoryProvider(
            config={
                "db_path": str(home / "memory_store.db"),
                "auto_extract": False,
                "default_trust": 0.5,
                "min_trust_threshold": 0.3,
                "hrr_dim": 1024,
            }
        )
    except Exception as e:
        return {"skipped": True, "reason": f"construct: {e}"}

    mm = MemoryManager()
    try:
        mm.add_provider(prov)
        mm.initialize_all(
            session_id="holo-1",
            hermes_home=str(home),
            platform="cli",
        )
    except Exception as e:
        return {"skipped": True, "reason": f"init: {e}"}

    seeded = 0
    add_ms: list[float] = []
    for content in [
        "Operator prefers concise bullet answers under load",
        "Alice owns billing service on Redis cluster",
        "Living cube starts in the Cube of Eden",
    ]:
        t1 = time.perf_counter()
        raw = prov.handle_tool_call(
            "fact_store",
            {"action": "add", "content": content, "category": "general"},
        )
        add_ms.append(_ms(t1))
        try:
            rec = json.loads(raw)
            if rec.get("status") == "added" or rec.get("fact_id") is not None:
                seeded += 1
        except Exception:
            pass

    t0 = time.perf_counter()
    ctx = mm.prefetch_all("concise bullet answers", session_id="holo-1") or ""
    pref_ms = _ms(t0)
    hit = any(tok in ctx.lower() for tok in ("concise", "bullet", "alice", "billing", "eden"))
    search_hit = False
    try:
        sr = json.loads(
            prov.handle_tool_call(
                "fact_store",
                {"action": "search", "query": "Alice billing", "limit": 5, "min_trust": 0.0},
            )
        )
        blob = " ".join(str(r.get("content") or "") for r in (sr.get("results") or []))
        search_hit = "alice" in blob.lower() or "billing" in blob.lower()
    except Exception:
        pass
    try:
        mm.shutdown_all()
    except Exception:
        pass
    return {
        "arm": "holographic",
        "seeded": seeded,
        "add_p50_ms": _pct(add_ms, 50),
        "prefetch_ms": pref_ms,
        "prefetch_hit": hit,
        "search_hit": search_hit,
        "ctx_chars": len(ctx),
    }


def run() -> dict:
    from hermescube import __version__

    lab = _lab()
    report: dict = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "hermescube": __version__,
        "hermes_agent_root": str(HERMES_ROOT),
        "hermes_present": HERMES_ROOT.is_dir(),
        "scenarios": {},
        "gates": {},
        "pass": False,
    }

    if not HERMES_ROOT.is_dir():
        report["error"] = f"HERMES_AGENT_ROOT missing: {HERMES_ROOT}"
        out = lab / f"live-hermes-cube-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        out.write_text(json.dumps(report, indent=2, default=str))
        report["path"] = str(out)
        return report

    print("… MemoryManager lifecycle", flush=True)
    life = run_hermes_manager_lifecycle()
    report["scenarios"]["lifecycle"] = life

    print("… cross-session reopen", flush=True)
    reopen = run_cross_session_reopen(life["home"])
    report["scenarios"]["reopen"] = reopen

    print("… holographic contrast (best-effort)", flush=True)
    holo = run_holographic_contrast()
    report["scenarios"]["holographic_contrast"] = holo

    # Gates
    _gate(report, "hermes_root_present", True)
    _gate(report, "init_lt_1000ms", life["init_ms"] < 1000)
    _gate(report, "seeded_ge_6", life["seeded_ids"] >= 6)
    _gate(report, "prefetch_hit_ge_0.7", life["prefetch_hit_rate"] >= 0.7)
    _gate(report, "prefetch_p50_lt_50ms", life["prefetch_p50_ms"] < 50)
    _gate(report, "fenced_context", life["fenced_turns"] >= max(1, life["fenced_total"] // 2))
    _gate(report, "prompt_cuboasis_or_hermescube", life["prompt_has_hermescube"] or life["prompt_has_cuboasis"])
    _gate(report, "prompt_eden", life["prompt_has_eden"])
    _gate(report, "tool_schemas_ge_3", life["tool_schemas"] >= 3)
    _gate(report, "mirror_builtin_hit", life["mirror_hit"])
    _gate(report, "search_hit", life["search_hit"])
    _gate(report, "governance_capture", life["governance"]["capture_ok"])
    _gate(report, "governance_approve", life["governance"]["approve_ok"])
    _gate(report, "doctor_present", life["governance"]["doctor_health"] in ("ok", "warning", "error", "missing"))
    _gate(report, "session_end_lt_10000ms", life["session_end_ms"] < 10000)
    _gate(report, "reopen_lt_1000ms", reopen["reopen_ms"] < 1000)
    _gate(report, "reopen_hit", reopen["hit"])
    _gate(report, "reopen_entries_persist", reopen["entries"] >= life["entries"] - 2)

    report["pass"] = all(report["gates"].values())

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = lab / f"live-hermes-cube-{stamp}.json"
    latest = lab / "live-hermes-cube-latest.json"
    blob = json.dumps(report, indent=2, default=str)
    out.write_text(blob)
    latest.write_text(blob)
    report["path"] = str(out)
    return report


def main() -> int:
    r = run()
    print(f"\nLive Hermes × HermesCube bench v{r.get('hermescube')}")
    print(f"pass={r.get('pass')}")
    print("gates:")
    for k, v in (r.get("gates") or {}).items():
        print(f"  {'OK  ' if v else 'FAIL'} {k}")
    life = (r.get("scenarios") or {}).get("lifecycle") or {}
    if life:
        print("\nlifecycle:")
        print(
            f"  init={life.get('init_ms')}ms seeded={life.get('seeded_ids')} "
            f"prefetch_p50={life.get('prefetch_p50_ms')}ms hit={life.get('prefetch_hit_rate')} "
            f"end={life.get('session_end_ms')}ms entries={life.get('entries')}"
        )
        print(
            f"  tools={life.get('tool_schemas')} "
            f"cuboasis={life.get('governance')} "
            f"growth {life.get('growth_before')} → {life.get('growth_after')}"
        )
    reopen = (r.get("scenarios") or {}).get("reopen") or {}
    if reopen:
        print(
            f"\nreopen: {reopen.get('reopen_ms')}ms hit={reopen.get('hit')} "
            f"entries={reopen.get('entries')} v{reopen.get('version')} {reopen.get('era_label')}"
        )
    holo = (r.get("scenarios") or {}).get("holographic_contrast") or {}
    if holo:
        print(f"\nholographic_contrast: {holo}")
    print(f"\n→ {r.get('path')}")
    return 0 if r.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
