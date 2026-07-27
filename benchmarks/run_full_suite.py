#!/usr/bin/env python3
"""Run the full HermesCube × Hermes Agent bench suite and write a combined report.

Arms:
  - unit/integration pytest (optional)
  - hermes_usage_bench
  - cross_exam_bench (Cube vs builtin vs holographic)
  - real_use_bench
  - assoc_recall_bench
  - bench_agent_memory / bench_har (timing rollups)
  - live_hermes_cube_bench (MemoryManager + Cuboasis governance)

Env:
  HERMES_AGENT_ROOT   default /tmp/hermes-agent-research
  HERMESCUBE_BENCH_DIR default /tmp/hc-bench/results
  SKIP_PYTEST=1       skip the pytest arm
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = Path(os.environ.get("HERMESCUBE_BENCH_DIR", "/tmp/hc-bench/results"))
ART = Path("/opt/cursor/artifacts")
HERMES = Path(os.environ.get("HERMES_AGENT_ROOT", "/tmp/hermes-agent-research"))


def _run(cmd: list[str], *, timeout: int | None = None) -> dict:
    t0 = time.perf_counter()
    env = os.environ.copy()
    env["HERMES_AGENT_ROOT"] = str(HERMES)
    env["HERMESCUBE_BENCH_DIR"] = str(LAB)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(HERMES), env.get("PYTHONPATH", "")]
    )
    try:
        cp = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "cmd": cmd,
            "returncode": cp.returncode,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "stdout_tail": (cp.stdout or "")[-4000:],
            "stderr_tail": (cp.stderr or "")[-2000:],
            "ok": cp.returncode == 0,
        }
    except subprocess.TimeoutExpired as e:
        return {
            "cmd": cmd,
            "returncode": -1,
            "elapsed_s": round(time.perf_counter() - t0, 3),
            "stdout_tail": (e.stdout or "")[-2000:] if isinstance(e.stdout, str) else "",
            "stderr_tail": f"TIMEOUT after {timeout}s",
            "ok": False,
        }


def _load_latest(glob_pat: str) -> dict | None:
    files = sorted(LAB.glob(glob_pat), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    try:
        return json.loads(files[0].read_text())
    except Exception:
        return None


def main() -> int:
    LAB.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)

    from hermescube import __version__

    report: dict = {
        "stamp": datetime.now(timezone.utc).isoformat(),
        "hermescube": __version__,
        "hermes_agent_root": str(HERMES),
        "hermes_tip": None,
        "arms": {},
        "pass": False,
    }

    if HERMES.is_dir():
        tip = _run(["git", "-C", str(HERMES), "rev-parse", "--short", "HEAD"])
        report["hermes_tip"] = (tip.get("stdout_tail") or "").strip() or None

    # ── pytest ────────────────────────────────────────────────────────
    if os.environ.get("SKIP_PYTEST") != "1":
        print("… pytest", flush=True)
        py = _run(
            [sys.executable, "-m", "pytest", "tests", "-q", "--tb=no"],
            timeout=600,
        )
        # parse "N passed"
        passed = failed = 0
        for line in (py.get("stdout_tail") or "").splitlines()[::-1]:
            if "passed" in line:
                # e.g. "428 passed in 12.3s"
                parts = line.replace(",", "").split()
                for i, tok in enumerate(parts):
                    if tok == "passed" and i > 0 and parts[i - 1].isdigit():
                        passed = int(parts[i - 1])
                    if tok == "failed" and i > 0 and parts[i - 1].isdigit():
                        failed = int(parts[i - 1])
                break
        report["arms"]["pytest"] = {
            "ok": py["ok"],
            "elapsed_s": py["elapsed_s"],
            "passed": passed,
            "failed": failed,
            "summary": (py.get("stdout_tail") or "").strip().splitlines()[-1:] or [],
        }
    else:
        report["arms"]["pytest"] = {"ok": True, "skipped": True}

    benches = [
        ("hermes_usage", "benchmarks/hermes_usage_bench.py", 180),
        ("cross_exam", "benchmarks/cross_exam_bench.py", 900),
        ("real_use", "benchmarks/real_use_bench.py", 300),
        ("assoc_recall", "benchmarks/assoc_recall_bench.py", 180),
        ("agent_memory", "benchmarks/bench_agent_memory.py", 300),
        ("har", "benchmarks/bench_har.py", 180),
        ("live_hermes_cube", "benchmarks/live_hermes_cube_bench.py", 180),
    ]

    for name, rel, timeout in benches:
        print(f"… {name}", flush=True)
        run = _run([sys.executable, str(ROOT / rel)], timeout=timeout)
        report["arms"][name] = {
            "ok": run["ok"],
            "elapsed_s": run["elapsed_s"],
            "returncode": run["returncode"],
            "stdout_tail": run["stdout_tail"][-1500:],
            "stderr_tail": run["stderr_tail"][-800:],
        }

    # Attach latest JSON payloads (compact)
    usage = _load_latest("hermes-usage-*.json")
    cross = _load_latest("cross-exam-*.json")
    real = _load_latest("real-use-*.json")
    assoc = _load_latest("assoc-recall*.json")
    live = _load_latest("live-hermes-cube-*.json")

    report["summaries"] = {
        "hermes_usage": {
            "pass": (usage or {}).get("pass"),
            "gates": (usage or {}).get("gates"),
            "lifecycle": {
                k: (((usage or {}).get("scenarios") or {}).get("lifecycle") or {}).get(k)
                for k in (
                    "init_ms",
                    "prefetch_p50_ms",
                    "hit_rate",
                    "session_end_ms",
                    "era",
                    "era_label",
                    "living_version",
                    "entries",
                )
            }
            if usage
            else None,
            "cross_session": ((usage or {}).get("scenarios") or {}).get("cross_session"),
            "hive": ((usage or {}).get("scenarios") or {}).get("hive_pilgrimage"),
        },
        "cross_exam": {
            "pass": (cross or {}).get("pass"),
            "gates_ok": sum(1 for v in ((cross or {}).get("gates") or {}).values() if v),
            "gates_total": len((cross or {}).get("gates") or {}),
            "gates_failed": [
                k for k, v in ((cross or {}).get("gates") or {}).items() if not v
            ],
            "memory_manager": ((cross or {}).get("stress") or {}).get("memory_manager"),
            "capacity_fair": ((cross or {}).get("regimes") or {}).get("capacity_fair"),
            "scale_500": ((cross or {}).get("regimes") or {}).get("scale_500"),
            "scale_1000": ((cross or {}).get("regimes") or {}).get("scale_1000"),
            "scale_2000": ((cross or {}).get("regimes") or {}).get("scale_2000"),
        },
        "real_use": {
            "pass": (real or {}).get("pass"),
            "gates": (real or {}).get("gates"),
        },
        "assoc_recall": {
            "entity_recall": ((assoc or {}).get("entities") or {}).get("entity_recall"),
            "version": (assoc or {}).get("version"),
        },
        "live_hermes_cube": {
            "pass": (live or {}).get("pass"),
            "gates": (live or {}).get("gates"),
            "lifecycle": ((live or {}).get("scenarios") or {}).get("lifecycle"),
            "reopen": ((live or {}).get("scenarios") or {}).get("reopen"),
            "holographic_contrast": ((live or {}).get("scenarios") or {}).get(
                "holographic_contrast"
            ),
        },
    }

    arm_ok = all(a.get("ok") for a in report["arms"].values())
    sum_ok = all(
        bool(report["summaries"][k].get("pass"))
        for k in ("hermes_usage", "cross_exam", "real_use", "live_hermes_cube")
        if report["summaries"].get(k) and report["summaries"][k].get("pass") is not None
    )
    report["pass"] = bool(arm_ok and sum_ok)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = LAB / f"combined-full-bench-{stamp}.json"
    latest = LAB / "combined-full-bench-latest.json"
    art_out = ART / "combined-full-bench-latest.json"
    summary = ART / "bench-summary-full.json"
    blob = json.dumps(report, indent=2, default=str)
    out.write_text(blob)
    latest.write_text(blob)
    art_out.write_text(blob)

    compact = {
        "stamp": report["stamp"],
        "hermescube": report["hermescube"],
        "hermes_tip": report["hermes_tip"],
        "pass": report["pass"],
        "arms_ok": {k: v.get("ok") for k, v in report["arms"].items()},
        "arms_elapsed_s": {k: v.get("elapsed_s") for k, v in report["arms"].items()},
        "summaries": report["summaries"],
    }
    summary.write_text(json.dumps(compact, indent=2, default=str))

    print(json.dumps(compact, indent=2, default=str))
    print(f"\n→ {out}")
    print(f"→ {art_out}")
    print(f"→ {summary}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
