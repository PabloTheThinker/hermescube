"""Grounded self-evolution harness — witness-anchored offline improvement.

Adapted from the hermes-self-evolution harness pattern
(Evolution + Critic + Verifier + Gardener) into HermesCube's own
offline cycle. Constitution-style rules, enforced in code:

1. **Witness log is ground truth** — an append-only ledger of *real*
   friction (failures, user corrections, retries). Structural evolution
   must cite a witness; without one the cycle is an honest no-op.
2. **No silent cycles** — every evolution cycle writes a report to an
   append-only ledger, even (especially) no-ops. Silent failure modes
   are the dominant harness bug.
3. **Falsifiable predictions** — when the cube promotes a procedure or
   crystallizes wisdom, it may commit a prediction with an expiry; the
   verifier later records a verdict (confirmed / refuted / expired).
4. **Anti-collusion critic** — a mechanical (non-LLM) critic reviews
   recent cycles and flags bookkeeping theatre: action cycles without
   witness anchors, overdue predictions, unaddressed critiques.
5. **Gardener surfaces, never deletes** — dormant durable memories are
   reported for consent-gated archival (supersession), not removed.

All ledgers are JSONL sidecars under ``$HERMES_HOME/memories/harness/``.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from hermescube.threats import sanitize_for_storage

WITNESS_LOG = "witness_log.jsonl"
CYCLE_LOG = "evolution_cycles.jsonl"
PREDICTIONS = "predictions.jsonl"
CRITIQUES = "critiques.jsonl"
GARDENER_REPORT = "gardener_report.json"

_THEATRE_STREAK = 3  # action cycles without witness before critic flags
_DEFAULT_HORIZON_DAYS = 7.0
_DORMANT_DAYS = 45.0


def harness_dir(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "memories" / "harness"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _rewrite_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    tmp.replace(path)


# ── 1. Witness ledger ────────────────────────────────────────────────

_CORRECTION_PATTERNS = [
    r"\bthat'?s (?:wrong|not right|incorrect|not what)\b",
    r"\bno[,.]? (?:that|this) (?:is|was)n'?t\b",
    r"\bnot what i (?:asked|meant|wanted)\b",
    r"\byou (?:already|just) (?:did|said|told)\b",
    r"\bstop (?:doing|saying|repeating)\b",
    r"\bwhy (?:did|do) you keep\b",
    r"\bi (?:already )?told you\b",
    r"\btry again\b",
    r"\bstill (?:broken|wrong|failing|not working)\b",
]
_ERROR_PATTERNS = [
    r"\btraceback \(most recent call last\)",
    r"\bfatal(?:\s+error)?:",
    r"\bexception\b.{0,40}\braised\b",
    r"\bcommand (?:failed|not found)\b",
    r"\bpermission denied\b",
]
_CORRECTION_RE = [re.compile(p, re.IGNORECASE) for p in _CORRECTION_PATTERNS]
_ERROR_RE = [re.compile(p, re.IGNORECASE) for p in _ERROR_PATTERNS]


def detect_friction(
    user_content: str, assistant_content: str
) -> dict[str, Any] | None:
    """Heuristic friction detector — user corrections and hard errors.

    Returns ``{"severity", "kind", "quote"}`` or None. Deliberately
    conservative: witnesses must be real friction, not noise.
    """
    u = (user_content or "").strip()
    a = (assistant_content or "").strip()
    for rx in _CORRECTION_RE:
        m = rx.search(u)
        if m:
            return {
                "severity": "medium",
                "kind": "user_correction",
                "quote": u[max(0, m.start() - 40) : m.end() + 80][:200],
            }
    for rx in _ERROR_RE:
        m = rx.search(a)
        if m:
            return {
                "severity": "low",
                "kind": "hard_error",
                "quote": a[max(0, m.start() - 40) : m.end() + 80][:200],
            }
    return None


def record_witness(
    hermes_home: str | Path,
    description: str,
    *,
    severity: str = "low",
    kind: str = "manual",
    session_id: str = "",
    source: str = "",
) -> dict[str, Any]:
    """Append real friction to the witness ledger (append-only ground truth)."""
    rec = {
        "ts": time.time(),
        "severity": severity if severity in ("low", "medium", "high") else "low",
        "kind": kind,
        "description": sanitize_for_storage(description, 400),
        "session_id": session_id,
        "source": source,
        "addressed": False,
    }
    _append_jsonl(harness_dir(hermes_home) / WITNESS_LOG, rec)
    return rec


def open_witnesses(hermes_home: str | Path) -> list[dict[str, Any]]:
    return [
        w
        for w in _read_jsonl(harness_dir(hermes_home) / WITNESS_LOG)
        if not w.get("addressed")
    ]


def mark_witnesses_addressed(
    hermes_home: str | Path, *, before_ts: float, cycle_id: str
) -> int:
    """Mark open witnesses (up to ``before_ts``) as addressed by a cycle."""
    path = harness_dir(hermes_home) / WITNESS_LOG
    records = _read_jsonl(path)
    n = 0
    for r in records:
        if not r.get("addressed") and float(r.get("ts") or 0) <= before_ts:
            r["addressed"] = True
            r["addressed_by"] = cycle_id
            n += 1
    if n:
        _rewrite_jsonl(path, records)
    return n


# ── 2. Grounded evolution cycles (no silent cycles) ─────────────────


def record_cycle(
    hermes_home: str | Path,
    *,
    kind: str,
    outcome: str,
    witness_ts: list[float] | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append a cycle report. Every cycle MUST land here — no-ops included."""
    rec = {
        "cycle_id": f"c{int(time.time())}_{kind[:16]}",
        "ts": time.time(),
        "kind": kind,
        "outcome": outcome,  # "action" | "noop" | "failed"
        "witnesses": [float(t) for t in (witness_ts or [])],
        "detail": detail or {},
    }
    _append_jsonl(harness_dir(hermes_home) / CYCLE_LOG, rec)
    return rec


def recent_cycles(hermes_home: str | Path, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl(harness_dir(hermes_home) / CYCLE_LOG)[-limit:]


def run_grounded_evolve(
    provider: Any, *, label: str = "session_end"
) -> dict[str, Any]:
    """Witness-anchored wrapper around branched evolve.

    Index maintenance (re-clustering, β refresh) always runs — that is
    hygiene, not structural change. The cycle report records whether the
    cycle was anchored to real witnessed friction ("action") or was pure
    maintenance ("noop"). The critic watches the ratio.
    """
    home = getattr(provider, "_hermes_home", "") or ""
    if not home:
        from hermescube.consolidate import run_branched_evolve

        return run_branched_evolve(provider, label=label)

    witnesses = open_witnesses(home)
    started = time.time()
    from hermescube.consolidate import run_branched_evolve

    result = run_branched_evolve(provider, label=label)
    outcome = "failed" if not result.get("ok") else ("action" if witnesses else "noop")
    cycle = record_cycle(
        home,
        kind=label,
        outcome=outcome,
        witness_ts=[float(w.get("ts") or 0) for w in witnesses],
        detail={
            "branch": result.get("branch"),
            "error": result.get("error"),
            "open_witnesses": len(witnesses),
        },
    )
    if result.get("ok") and witnesses:
        mark_witnesses_addressed(
            home, before_ts=started, cycle_id=cycle["cycle_id"]
        )
    result["cycle"] = cycle
    return result


# ── 3. Falsifiable predictions + verifier ────────────────────────────


def make_prediction(
    hermes_home: str | Path,
    statement: str,
    *,
    check: dict[str, Any],
    horizon_days: float = _DEFAULT_HORIZON_DAYS,
    source: str = "",
) -> dict[str, Any]:
    """Commit a falsifiable prediction with an expiry.

    Supported checks:
    - ``{"type": "witness_absence", "pattern": "..."}`` — the friction
      pattern must NOT recur in the witness log before the horizon.
    - ``{"type": "entry_feedback", "entry_id": "...", "min_trust": 0.6}``
      — the promoted entry's trust must reach the bar by the horizon.
    """
    rec = {
        "id": f"p{int(time.time() * 1000)}",
        "ts": time.time(),
        "statement": sanitize_for_storage(statement, 300),
        "check": check,
        "expires_at": time.time() + horizon_days * 86400.0,
        "source": source,
        "status": "open",  # open | confirmed | refuted | expired
    }
    _append_jsonl(harness_dir(hermes_home) / PREDICTIONS, rec)
    return rec


def _verify_one(
    pred: dict[str, Any], *, hermes_home: str | Path, cube: Any
) -> str | None:
    """Return a verdict for one open prediction, or None if still pending."""
    check = pred.get("check") or {}
    ctype = check.get("type")
    now = time.time()
    expired = now >= float(pred.get("expires_at") or 0)

    if ctype == "witness_absence":
        pattern = str(check.get("pattern") or "").lower()
        if pattern:
            for w in _read_jsonl(harness_dir(hermes_home) / WITNESS_LOG):
                if float(w.get("ts") or 0) <= float(pred.get("ts") or 0):
                    continue
                if pattern in str(w.get("description") or "").lower():
                    return "refuted"  # friction recurred
        return "confirmed" if expired else None

    if ctype == "entry_feedback":
        entry_id = str(check.get("entry_id") or "")
        min_trust = float(check.get("min_trust") or 0.6)
        if cube is not None and entry_id:
            try:
                for e in cube.read_l1() or []:
                    if e.id != entry_id:
                        continue
                    d = e.data if isinstance(getattr(e, "data", None), dict) else {}
                    if float(d.get("trust") or 0) >= min_trust:
                        return "confirmed"
                    if (getattr(e, "outcome", "") or "") == "superseded":
                        return "refuted"
                    break
            except Exception:
                pass
        return "expired" if expired else None

    return "expired" if expired else None


def verify_predictions(
    hermes_home: str | Path, *, cube: Any = None
) -> dict[str, Any]:
    """Verifier pass: settle open predictions; verdicts are permanent."""
    path = harness_dir(hermes_home) / PREDICTIONS
    records = _read_jsonl(path)
    stats = {"open": 0, "confirmed": 0, "refuted": 0, "expired": 0}
    changed = False
    for r in records:
        if r.get("status") != "open":
            continue
        verdict = _verify_one(r, hermes_home=hermes_home, cube=cube)
        if verdict is None:
            stats["open"] += 1
            continue
        r["status"] = verdict
        r["settled_at"] = time.time()
        stats[verdict] = stats.get(verdict, 0) + 1
        changed = True
    if changed:
        _rewrite_jsonl(path, records)
    return stats


def open_predictions(hermes_home: str | Path) -> list[dict[str, Any]]:
    return [
        p
        for p in _read_jsonl(harness_dir(hermes_home) / PREDICTIONS)
        if p.get("status") == "open"
    ]


# ── 4. Critic (mechanical, anti-collusion) ──────────────────────────


def run_critic(hermes_home: str | Path) -> dict[str, Any]:
    """Heuristic critic over recent cycles — no LLM, no shared blind spots.

    Flags:
    - **bookkeeping theatre**: ≥N consecutive maintenance-only cycles
      while friction sits unaddressed in the witness log
    - **overdue predictions**: open predictions past their horizon
    - **failed cycle streaks**: repeated evolve failures
    """
    cycles = recent_cycles(hermes_home, limit=30)
    witnesses = open_witnesses(hermes_home)
    findings: list[dict[str, Any]] = []

    noop_streak = 0
    for c in reversed(cycles):
        if c.get("outcome") == "noop":
            noop_streak += 1
        else:
            break
    if noop_streak >= _THEATRE_STREAK and witnesses:
        findings.append(
            {
                "flag": "bookkeeping_theatre",
                "detail": (
                    f"{noop_streak} maintenance-only cycles while "
                    f"{len(witnesses)} witnesses sit unaddressed"
                ),
            }
        )

    overdue = [
        p
        for p in open_predictions(hermes_home)
        if time.time() >= float(p.get("expires_at") or 0)
    ]
    if overdue:
        findings.append(
            {
                "flag": "overdue_predictions",
                "detail": f"{len(overdue)} predictions past horizon without a verdict",
            }
        )

    fail_streak = 0
    for c in reversed(cycles):
        if c.get("outcome") == "failed":
            fail_streak += 1
        else:
            break
    if fail_streak >= 2:
        findings.append(
            {
                "flag": "failing_cycles",
                "detail": f"{fail_streak} consecutive failed evolve cycles",
            }
        )

    report = {
        "ts": time.time(),
        "verdict": "healthy" if not findings else "flagged",
        "findings": findings,
        "cycles_reviewed": len(cycles),
        "open_witnesses": len(witnesses),
    }
    _append_jsonl(harness_dir(hermes_home) / CRITIQUES, report)
    return report


# ── 5. Gardener (surface dormant, never delete) ─────────────────────


def run_gardener(
    cube: Any,
    hermes_home: str | Path,
    *,
    dormant_days: float = _DORMANT_DAYS,
) -> dict[str, Any]:
    """Scan durable memories for dormancy; surface for consent-gated archival.

    Anti-entropy without destruction: the report proposes candidates;
    a human (or an explicit manage call) decides on supersession.
    """
    cutoff = time.time() - dormant_days * 86400.0
    candidates: list[dict[str, Any]] = []
    scanned = 0
    for e in cube.read_l1() or []:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        if not (d.get("durable") or d.get("crystal") or d.get("procedure")):
            continue
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        scanned += 1
        ets = float(d.get("timestamp") or 0)
        if not ets:
            # ISO timestamp fallback
            try:
                import datetime as _dt

                ets = _dt.datetime.fromisoformat(
                    str(e.timestamp).replace("Z", "+00:00")
                ).timestamp()
            except Exception:
                continue
        trust = float(d.get("trust") or 0.5)
        if ets < cutoff and trust <= 0.5:
            candidates.append(
                {
                    "entry_id": e.id,
                    "type": e.entry_type,
                    "description": (e.description or "")[:140],
                    "trust": trust,
                    "age_days": round((time.time() - ets) / 86400.0, 1),
                }
            )
    report = {
        "ts": time.time(),
        "dormant_days": dormant_days,
        "durable_scanned": scanned,
        "dormant_candidates": candidates[:40],
        "note": "candidates are proposals only — archive via manage remove (supersession)",
    }
    out = harness_dir(hermes_home) / GARDENER_REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


# ── Status roll-up ───────────────────────────────────────────────────


def harness_status(hermes_home: str | Path) -> dict[str, Any]:
    cycles = recent_cycles(hermes_home, limit=10)
    critiques = _read_jsonl(harness_dir(hermes_home) / CRITIQUES)
    last_critique = critiques[-1] if critiques else None
    preds = _read_jsonl(harness_dir(hermes_home) / PREDICTIONS)
    return {
        "open_witnesses": len(open_witnesses(hermes_home)),
        "recent_cycles": [
            {"kind": c.get("kind"), "outcome": c.get("outcome"), "ts": c.get("ts")}
            for c in cycles
        ],
        "predictions": {
            "open": sum(1 for p in preds if p.get("status") == "open"),
            "confirmed": sum(1 for p in preds if p.get("status") == "confirmed"),
            "refuted": sum(1 for p in preds if p.get("status") == "refuted"),
            "expired": sum(1 for p in preds if p.get("status") == "expired"),
        },
        "last_critique": (
            {
                "verdict": last_critique.get("verdict"),
                "findings": last_critique.get("findings"),
            }
            if last_critique
            else None
        ),
    }
