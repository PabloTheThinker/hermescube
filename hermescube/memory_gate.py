"""Cuboasis memory gate — safety, evidence states, candidate governance.

Cube-native recreation of oh-my-hermes memory discipline (not a port):
  - Safety gate before durable writes (creds / logs / temp noise)
  - Explicit evidence_state: prepared_not_observed | observed | verified | …
  - Candidate → review → approve / reject (review-first oasis)
  - Rejected-decision recall (negative memory, never current instruction)
  - Curation sync report (duplicates / stale / risky — proposals only)

Policy modes: review-first | auto-safe | off
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

SCHEMA = "cube_memory_candidate/v1"
SAFETY_SCHEMA = "cube_memory_safety/v1"
POLICY_MODES = frozenset({"review-first", "auto-safe", "off"})

EVIDENCE_STATES = frozenset(
    {
        "prepared_not_observed",
        "observed",
        "verified",
        "superseded",
        "refuted",
        "rejected",
    }
)

CLAIM_BOUNDARY = (
    "Cuboasis candidates and prepared context are not execution evidence, "
    "not MEMORY.md proof, and not Hive assimilation proof unless that write "
    "was observed."
)

_RE_SENSITIVE = re.compile(
    r"(?i)\b(?:secret|password|passwd|private[_-]?key|api[_-]?key|apikey|"
    r"access[_-]?token|auth[_-]?token|bearer\s+[a-z0-9._\-]{16,}|sk-[a-z0-9]{16,})\b"
)
_RE_PR = re.compile(r"(?i)\b(?:PR|pull request)\s*#?\d+\b")
_RE_COMMIT = re.compile(r"\b[0-9a-f]{7,40}\b", re.I)
_RE_TEMP = re.compile(
    r"(?i)\b(?:temporary|for this session|wip|in progress|pending ci|"
    r"currently running|todo later|fixme)\b"
)
_RE_LOG_TS = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}", re.M)
_RE_SPEAKER = re.compile(
    r"^(user|assistant|system|developer|human|agent):", re.I | re.M
)


def normalize_evidence_state(value: str | None, *, default: str = "observed") -> str:
    s = (value or "").strip().lower()
    if s in EVIDENCE_STATES:
        return s
    # Map legacy verification labels
    legacy = {
        "unverified": "prepared_not_observed",
        "user_authored": "verified",
        "tool_verified": "verified",
        "hive_shared": "observed",
    }
    return legacy.get(s, default if default in EVIDENCE_STATES else "observed")


def normalize_policy(value: str | None, *, default: str = "auto-safe") -> str:
    s = (value or default).strip().lower().replace("_", "-")
    return s if s in POLICY_MODES else default


def memory_safety(summary: str, content: str = "", *, tags: Iterable[str] | None = None) -> dict[str, Any]:
    """Score whether text is safe to auto-approve as durable memory."""
    tag_s = " ".join(str(t) for t in (tags or []))
    text = "\n".join([summary or "", content or "", tag_s])
    reasons: list[str] = []
    blocked = False

    if _RE_SENSITIVE.search(text):
        blocked = True
        reasons.append("sensitive_credential_like_text")
    if _looks_like_raw_log(text):
        blocked = True
        reasons.append("raw_log_or_traceback")
    if _looks_like_full_transcript(text):
        blocked = True
        reasons.append("full_transcript_like_text")
    if _RE_PR.search(text):
        reasons.append("short_lived_pr_reference")
    if _RE_COMMIT.search(text) and not _looks_like_machine_id_only(text):
        # Avoid flagging every auth-service hex; require commit-ish context
        if re.search(r"(?i)\b(commit|sha|revision|git)\b", text) or len(
            _RE_COMMIT.findall(text)
        ) >= 2:
            reasons.append("short_lived_commit_reference")
    if _RE_TEMP.search(text):
        reasons.append("temporary_task_progress")
    if len(content or summary or "") > 2400:
        reasons.append("long_content_requires_review")

    status = "blocked" if blocked else ("needs_review" if reasons else "safe")
    return {
        "schema_version": SAFETY_SCHEMA,
        "status": status,
        "safe_to_auto_approve": status == "safe",
        "review_reasons": reasons,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _looks_like_raw_log(value: str) -> bool:
    lowered = value.lower()
    markers = (
        "traceback (most recent call last)",
        "\nstderr",
        "\nstdout",
        "[error]",
        "exception:",
        "raw log",
        "full log",
    )
    return any(m in lowered for m in markers) or len(_RE_LOG_TS.findall(value)) >= 3


def _looks_like_full_transcript(value: str) -> bool:
    lowered = value.lower()
    return (
        "full transcript" in lowered
        or "chat transcript" in lowered
        or len(_RE_SPEAKER.findall(value)) >= 4
    )


def _looks_like_machine_id_only(text: str) -> bool:
    # Single short hex in an otherwise normal sentence → not a commit dump
    return len(_RE_COMMIT.findall(text)) == 1 and len(text) < 120


def decide_write_path(
    safety: dict[str, Any],
    *,
    policy: str = "auto-safe",
    explicit: bool = False,
) -> str:
    """Return durable | candidate | block | skip.

    explicit=True means operator/manage add (prefer durable unless blocked).
    """
    mode = normalize_policy(policy)
    status = str(safety.get("status") or "needs_review")
    if mode == "off" and not explicit:
        return "skip"
    if status == "blocked":
        return "block" if explicit else "candidate"
    if explicit:
        return "durable"
    if mode == "review-first":
        return "candidate"
    # auto-safe
    if status == "safe":
        return "durable"
    return "candidate"


# ── Candidate store ───────────────────────────────────────────────────


def candidates_path(
    hermes_home: str | Path | None = None,
    *,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    return resolve_cube_paths(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).candidates_ledger


def _load_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        for ln in path.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                rec = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(rec, dict):
                out.append(rec)
    except OSError:
        return []
    return out


def _rewrite_candidates(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for rec in rows:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    tmp.replace(path)


def capture_candidate(
    hermes_home: str | Path | None,
    text: str,
    *,
    record_type: str = "fact",
    source: str = "capture",
    evidence_state: str = "prepared_not_observed",
    tags: list[str] | None = None,
    session_id: str = "",
    entry_type: str = "belief",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Append a review candidate. Does not write the cube."""
    summary = (text or "").strip()
    if not summary:
        return {"ok": False, "error": "text required"}
    safety = memory_safety(summary, summary, tags=tags or [])
    status = (
        "blocked_review_required"
        if safety["status"] == "blocked"
        else "pending_review"
    )
    cid = "cand_" + hashlib.sha256(
        f"{summary}|{record_type}|{source}".encode()
    ).hexdigest()[:16]
    # Dedupe pending identical candidate_id
    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    path = candidates_path(hermes_home, **pkw)
    rows = _load_candidates(path)
    for existing in rows:
        if existing.get("candidate_id") == cid and existing.get("status") in (
            "pending_review",
            "blocked_review_required",
        ):
            return {"ok": True, "duplicate": True, **existing}
    rec = {
        "schema_version": SCHEMA,
        "candidate_id": cid,
        "status": status,
        "record_type": (record_type or "fact").strip()[:32],
        "entry_type": entry_type or "belief",
        "summary": summary[:500],
        "content": summary[:4000],
        "tags": list(tags or [])[:12],
        "source": (source or "capture")[:64],
        "session_id": session_id or "",
        "evidence_state": normalize_evidence_state(evidence_state, default="prepared_not_observed"),
        "created_at": time.time(),
        "safety": safety,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return {"ok": True, **rec, "path": str(path)}


def list_candidates(
    hermes_home: str | Path | None,
    *,
    status: str = "pending",
    limit: int = 40,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    path = candidates_path(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    rows = _load_candidates(path)
    want = (status or "pending").strip().lower()
    if want in ("pending", "review", "queue"):
        filtered = [
            r
            for r in rows
            if r.get("status") in ("pending_review", "blocked_review_required")
        ]
    elif want == "rejected":
        filtered = [r for r in rows if r.get("status") == "rejected"]
    elif want == "approved":
        filtered = [r for r in rows if r.get("status") == "approved"]
    elif want in ("all", "*"):
        filtered = rows
    else:
        filtered = [r for r in rows if r.get("status") == want]
    # newest last → show recent first
    filtered = list(reversed(filtered[-limit:]))
    return {
        "ok": True,
        "path": str(path),
        "count": len(filtered),
        "candidates": filtered,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _update_candidate_status(
    hermes_home: str | Path | None,
    candidate_id: str,
    *,
    status: str,
    reason: str = "",
    reviewer: str = "operator",
    entry_id: str = "",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any] | None:
    path = candidates_path(
        hermes_home,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    rows = _load_candidates(path)
    found = None
    for rec in rows:
        if rec.get("candidate_id") == candidate_id:
            rec["status"] = status
            rec["reviewed_at"] = time.time()
            rec["reviewer"] = reviewer
            if reason:
                rec["review_reason"] = reason[:300]
            if entry_id:
                rec["entry_id"] = entry_id
            found = rec
            break
    if found is None:
        return None
    _rewrite_candidates(path, rows)
    return found


def approve_candidate(
    hermes_home: str | Path | None,
    candidate_id: str,
    *,
    cube: Any = None,
    reviewer: str = "operator",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Promote a candidate into durable cube memory."""
    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    queue = list_candidates(hermes_home, status="all", limit=500, **pkw)
    cand = None
    for c in queue.get("candidates") or []:
        if c.get("candidate_id") == candidate_id:
            cand = c
            break
    if cand is None:
        return {"ok": False, "error": f"candidate not found: {candidate_id}"}
    if cand.get("status") == "approved":
        return {"ok": True, "already": True, **cand}
    if cand.get("status") == "blocked_review_required" or (
        (cand.get("safety") or {}).get("status") == "blocked"
    ):
        return {
            "ok": False,
            "error": "blocked candidates must be rejected or recaptured",
            "safety": cand.get("safety"),
        }
    if cube is None:
        return {"ok": False, "error": "cube required to approve"}

    text = str(cand.get("content") or cand.get("summary") or "").strip()
    entry_type = str(cand.get("entry_type") or "belief")
    entry = cube.append(
        entry_type=entry_type,
        description=text[:2000],
        data={
            "durable": True,
            "source": "cuboasis_approve",
            "candidate_id": candidate_id,
            "record_type": cand.get("record_type") or "fact",
            "evidence_state": "verified",
            "verification": "user_authored",
            "trust": 0.78,
            "claim_boundary": CLAIM_BOUNDARY,
            "tags": list(cand.get("tags") or []),
        },
    )
    updated = _update_candidate_status(
        hermes_home,
        candidate_id,
        status="approved",
        reviewer=reviewer,
        entry_id=str(getattr(entry, "id", "") or ""),
        **pkw,
    )
    return {
        "ok": True,
        "entry_id": str(getattr(entry, "id", "") or ""),
        "candidate": updated or cand,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def reject_candidate(
    hermes_home: str | Path | None,
    candidate_id: str,
    *,
    reason: str = "",
    reviewer: str = "operator",
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    updated = _update_candidate_status(
        hermes_home,
        candidate_id,
        status="rejected",
        reason=reason or "rejected",
        reviewer=reviewer,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    if updated is None:
        return {"ok": False, "error": f"candidate not found: {candidate_id}"}
    updated["evidence_state"] = "rejected"
    return {
        "ok": True,
        "candidate": updated,
        "claim_boundary": (
            "Rejected decisions are negative memory — do not treat as current instruction."
        ),
    }


def recall_rejected(
    hermes_home: str | Path | None,
    query: str = "",
    *,
    limit: int = 12,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Search rejected candidates — labeled not-approved."""
    q = (query or "").strip().lower()
    rows = list_candidates(
        hermes_home,
        status="rejected",
        limit=200,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    ).get("candidates") or []
    hits = []
    for r in rows:
        blob = f"{r.get('summary', '')} {r.get('content', '')} {r.get('review_reason', '')}".lower()
        if q and q not in blob:
            continue
        hits.append(
            {
                "candidate_id": r.get("candidate_id"),
                "summary": r.get("summary"),
                "reason": r.get("review_reason") or "",
                "evidence_state": "rejected",
                "not_approved": True,
                "claim_boundary": (
                    "Rejected decision — do not treat as current instruction."
                ),
            }
        )
        if len(hits) >= limit:
            break
    return {
        "ok": True,
        "count": len(hits),
        "rejected": hits,
        "claim_boundary": "Negative memory only; not approved durable truth.",
    }


# ── Curation sync report ──────────────────────────────────────────────


def curation_sync_report(
    cube: Any,
    hermes_home: str | Path | None = None,
    *,
    limit: int = 24,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Proposals only — duplicates, low-trust, stale-ish, risky text. No deletes."""
    entries = list(cube.read_l1() or []) if cube is not None else []
    by_desc: dict[str, list[str]] = {}
    risky: list[dict[str, Any]] = []
    low_trust: list[dict[str, Any]] = []
    for e in entries:
        desc = (getattr(e, "description", "") or "").strip()
        if not desc or desc.startswith("["):
            continue
        key = " ".join(desc.lower().split())[:160]
        by_desc.setdefault(key, []).append(str(e.id))
        data = e.data if isinstance(getattr(e, "data", None), dict) else {}
        safety = memory_safety(desc, desc)
        if safety["status"] in ("blocked", "needs_review") and safety["review_reasons"]:
            risky.append(
                {
                    "entry_id": str(e.id),
                    "summary": desc[:160],
                    "reasons": safety["review_reasons"],
                    "proposal": "review_or_supersede",
                }
            )
        trust = data.get("trust")
        if isinstance(trust, (int, float)) and float(trust) < 0.35 and data.get("durable"):
            low_trust.append(
                {
                    "entry_id": str(e.id),
                    "summary": desc[:160],
                    "trust": float(trust),
                    "proposal": "feedback_or_supersede",
                }
            )

    duplicates = [
        {"summary": k[:120], "ids": ids, "count": len(ids), "proposal": "merge_or_supersede"}
        for k, ids in by_desc.items()
        if len(ids) >= 2
    ]
    duplicates.sort(key=lambda x: -x["count"])

    pending = list_candidates(
        hermes_home,
        status="pending",
        limit=20,
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )

    report = {
        "ok": True,
        "schema_version": "cuboasis_curation_report/v1",
        "scanned": len(entries),
        "duplicates": duplicates[:limit],
        "risky": risky[:limit],
        "low_trust": low_trust[:limit],
        "pending_candidates": pending.get("count", 0),
        "proposals_only": True,
        "claim_boundary": (
            "Curation report is prepared guidance — not deletion evidence."
        ),
    }
    if hermes_home:
        try:
            from hermescube.cuboasis import record_progress

            record_progress(
                hermes_home,
                "curation_sync",
                detail=(
                    f"dups={len(duplicates)} risky={len(risky)} "
                    f"low_trust={len(low_trust)} pending={pending.get('count', 0)}"
                ),
                metrics={
                    "duplicates": len(duplicates),
                    "risky": len(risky),
                    "low_trust": len(low_trust),
                    "pending_candidates": int(pending.get("count") or 0),
                },
                agent_identity=agent_identity,
                agent_workspace=agent_workspace,
                nest_profiles=nest_profiles,
            )
        except Exception as e:
            logger.debug("curation progress skip: %s", e)
    return report


# ── Doctor card ───────────────────────────────────────────────────────


def oasis_doctor_card(
    cube: Any,
    hermes_home: str | Path | None,
    *,
    engram: Any = None,
    cubewave: Any = None,
    relation_store: Any = None,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
) -> dict[str, Any]:
    """Structured Cuboasis readiness — not execution evidence."""
    from hermescube.framework.paths import resolve_cube_paths

    pkw = dict(
        agent_identity=agent_identity,
        agent_workspace=agent_workspace,
        nest_profiles=nest_profiles,
    )
    paths = resolve_cube_paths(hermes_home, **pkw) if hermes_home else None
    checks: list[dict[str, Any]] = []

    def _add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if paths is None:
        _add("paths", "missing", "hermes_home unset")
    else:
        _add(
            "cube",
            "ok" if paths.cube.is_file() else "missing",
            str(paths.cube),
        )
        _add(
            "progress",
            "ok" if paths.progress_ledger.is_file() else "empty",
            str(paths.progress_ledger),
        )
        _add(
            "candidates",
            "ok" if paths.candidates_ledger.is_file() else "empty",
            str(paths.candidates_ledger),
        )
        _add(
            "cubewave",
            "ok" if paths.cubewave.is_file() else "empty",
            str(paths.cubewave),
        )
        _add(
            "engram",
            "ok" if paths.engram.is_file() else "empty",
            str(paths.engram),
        )

    n_entries = 0
    if cube is not None:
        try:
            n_entries = int(getattr(cube, "entry_count", 0) or len(list(cube.read_l1() or [])))
            _add("cube_readable", "ok", f"entries={n_entries}")
        except Exception as e:
            _add("cube_readable", "error", str(e))

    pending = 0
    if hermes_home:
        pending = int(
            list_candidates(hermes_home, status="pending", limit=500, **pkw).get("count")
            or 0
        )
    _add(
        "candidate_backlog",
        "warning" if pending > 0 else "ok",
        f"pending={pending}",
    )

    if engram is not None:
        try:
            st = engram.stats() if hasattr(engram, "stats") else {}
            _add("engram_net", "ok", f"edges={st.get('edges', 0)}")
        except Exception as e:
            _add("engram_net", "error", str(e))
    if cubewave is not None:
        try:
            st = cubewave.stats() if hasattr(cubewave, "stats") else {}
            _add("cubewave_field", "ok", f"readouts={st.get('readouts', 0)}")
        except Exception as e:
            _add("cubewave_field", "error", str(e))
    if relation_store is not None:
        try:
            st = relation_store.stats()
            _add("relations", "ok", f"open={st.get('open', st.get('relations', 0))}")
        except Exception as e:
            _add("relations", "error", str(e))

    usefulness = None
    if hermes_home:
        try:
            from hermescube.cuboasis import progress_usefulness

            usefulness = progress_usefulness(hermes_home, **pkw).get("usefulness")
        except Exception:
            pass

    worst = "ok"
    for c in checks:
        if c["status"] == "error":
            worst = "error"
            break
        if c["status"] in ("missing", "warning") and worst == "ok":
            worst = "warning"

    return {
        "ok": True,
        "schema_version": "cuboasis_doctor_card/v1",
        "health": worst,
        "entries": n_entries,
        "pending_candidates": pending,
        "usefulness": usefulness,
        "checks": checks,
        "claim_boundary": (
            "Doctor card is readiness evidence only — not proof a workflow ran."
        ),
    }


def enrich_entry_data(
    data: dict[str, Any] | None,
    *,
    evidence_state: str | None = None,
    safety: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach evidence_state (+ optional safety) onto entry data."""
    out = dict(data or {})
    if evidence_state:
        out["evidence_state"] = normalize_evidence_state(evidence_state)
    elif "evidence_state" not in out and out.get("verification"):
        out["evidence_state"] = normalize_evidence_state(str(out.get("verification")))
    if safety:
        out["safety"] = safety
    out.setdefault("claim_boundary", CLAIM_BOUNDARY)
    return out
