"""Claim auditor — prove natural-language claims against a flight record."""
from __future__ import annotations

import re
from typing import Any

from hermescube.blackbox.flight import ClaimResult, FlightRecord

_RULES: list[tuple[re.Pattern[str], list[str], float, str]] = [
    (
        re.compile(r"\btests?\s+pass", re.I),
        ["pytest", "test", "passed", "pass"],
        0.75,
        "Need test runner success evidence",
    ),
    (
        re.compile(r"\b(unit\s+)?tests?\s+(succeeded|successful|green|ok)\b", re.I),
        ["pytest", "passed", "pass"],
        0.75,
        "Need test success evidence",
    ),
    (
        re.compile(r"\bpip install", re.I),
        ["pip install", "successfully installed"],
        0.7,
        "Need pip install evidence",
    ),
    (
        re.compile(r"\b(commit|committed)\b", re.I),
        ["git commit", "committed"],
        0.7,
        "Need git commit evidence",
    ),
    (
        re.compile(r"\b(push(ed)?|pushed to)\b", re.I),
        ["git push", "pushed"],
        0.7,
        "Need git push evidence",
    ),
    (
        re.compile(r"\bpr\b|pull request", re.I),
        ["gh pr", "pull request", "github.com/.*/pull/"],
        0.7,
        "Need PR evidence",
    ),
    (
        re.compile(r"\bbuild succeeded|build passed|compiled successfully", re.I),
        ["build", "succeeded", "passed"],
        0.7,
        "Need build success evidence",
    ),
    (
        re.compile(r"\bserver\b.*(up|running|listening)", re.I),
        ["listening", "started", "uvicorn", "gunicorn"],
        0.65,
        "Need server listen evidence",
    ),
    (
        re.compile(r"\bmemory\.provider|hermescube\b", re.I),
        ["hermescube", "memory.provider", "provider"],
        0.7,
        "Need memory provider evidence",
    ),
]


def _event_blob(event: dict[str, Any]) -> str:
    parts = [
        str(event.get("kind") or ""),
        str(event.get("name") or ""),
        str(event.get("summary") or ""),
        str(event.get("detail") or ""),
    ]
    return "\n".join(parts).lower()


def _find_evidence(
    events: list[dict[str, Any]], needles: list[str], limit: int = 5
) -> list[dict[str, Any]]:
    hits = []
    for e in events:
        blob = _event_blob(e)
        score = sum(1 for n in needles if n.lower() in blob)
        if score:
            hits.append((score, e))
    hits.sort(key=lambda x: x[0], reverse=True)
    out = []
    for score, e in hits[:limit]:
        out.append(
            {
                "score": score,
                "ts": e.get("ts"),
                "kind": e.get("kind"),
                "name": e.get("name"),
                "summary": e.get("summary"),
                "message_id": (e.get("refs") or {}).get("message_id"),
            }
        )
    return out


def _has_failure_markers(events: list[dict[str, Any]], needles: list[str]) -> list[str]:
    fail_words = (
        "failed",
        "error",
        "traceback",
        "exception",
        'exit_code": 1',
        "exit code 1",
        "non-zero",
    )
    gaps = []
    for e in events:
        blob = _event_blob(e)
        if any(n.lower() in blob for n in needles) and any(f in blob for f in fail_words):
            gaps.append(e.get("summary") or "failure marker near relevant evidence")
    return gaps[:5]


def prove_claim(record: FlightRecord | dict[str, Any], claim: str) -> ClaimResult:
    data = record.to_dict() if isinstance(record, FlightRecord) else record
    events = data.get("events") or []
    claim_s = claim.strip()
    if not claim_s:
        return ClaimResult(
            claim=claim, verdict="fail", confidence=1.0, evidence=[], gaps=["empty claim"]
        )

    literal = re.findall(r"\"([^\"]+)\"|'([^']+)'", claim_s)
    literals = [a or b for a, b in literal]

    matched_rule = None
    for pat, needles, base, gap in _RULES:
        if pat.search(claim_s):
            matched_rule = (needles, base, gap)
            break

    if literals:
        needles = literals
        base = 0.8
        gap = "Quoted phrase not found in trajectory"
    elif matched_rule:
        needles, base, gap = matched_rule
    else:
        tokens = [t for t in re.split(r"[^a-zA-Z0-9_./+-]+", claim_s) if len(t) > 3]
        stop = {
            "that",
            "this",
            "with",
            "from",
            "have",
            "been",
            "were",
            "will",
            "should",
            "could",
            "about",
            "after",
            "before",
            "using",
            "into",
        }
        needles = [t for t in tokens if t.lower() not in stop][:8]
        base = 0.55
        gap = "No strong domain rule matched; fell back to keyword overlap"

    evidence = _find_evidence(events, needles)
    failures = _has_failure_markers(events, needles)

    if not evidence:
        return ClaimResult(
            claim=claim_s,
            verdict="fail",
            confidence=0.7,
            evidence=[],
            gaps=[gap, f"needles={needles}"],
        )

    success_claim = bool(
        re.search(r"pass|success|complete|done|green|ok|shipped|merged", claim_s, re.I)
    )
    if success_claim and failures and len(failures) >= max(1, len(evidence) // 2):
        return ClaimResult(
            claim=claim_s,
            verdict="fail",
            confidence=min(0.9, base + 0.1),
            evidence=evidence,
            gaps=failures + ["failure markers found near matching evidence"],
        )

    conf = min(0.95, base + 0.05 * min(4, len(evidence)))
    verdict = "pass" if conf >= 0.6 and evidence else "inconclusive"
    if verdict == "pass" and len(evidence) == 1 and base < 0.7:
        verdict = "inconclusive"
        conf = min(conf, 0.59)
    return ClaimResult(
        claim=claim_s,
        verdict=verdict,
        confidence=round(conf, 3),
        evidence=evidence,
        gaps=[] if verdict == "pass" else [gap],
    )


def prove_many(record: FlightRecord | dict[str, Any], claims: list[str]) -> list[ClaimResult]:
    return [prove_claim(record, c) for c in claims]
