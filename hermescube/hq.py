"""Fleet HQ — clear ownership for 1, 100, or a million Hermes Agents.

The hive gave agents a place to pool experience. HQ makes that place the
command layer of a real fleet, following the hard-won rules of production
multi-agent systems:

- **Charters, not vibes** — a permanent agent exists because it owns a
  durable lane of work. A charter records role, lane, keywords, and
  boundaries. No charter, no routing.
- **One command surface** — routing falls back to the ``command`` role;
  the orchestrator owns the outcome, specialists own their lanes.
- **Work flows upward, privilege does not flow down** — subagents get
  read-only memory tools (enforced in the provider); durable writes and
  hive/HQ operations belong to the parent.
- **Ownership is explicit** — task claims with leases prevent two agents
  from both thinking a task belongs to them.
- **Context travels with the handoff** — a delegation carries a distilled
  handoff packet (evidence, not raw history), and the ledger records it.
- **Documentation is runtime** — ``verify_fleet`` catches ghost routes
  (rules pointing at retired agents), lane conflicts, and a missing
  command profile. History can mention ghosts; routing cannot.
- **Recoverable, not just running** — ``freeze_baseline`` snapshots
  charter/routing/collective hashes; ``verify_baseline`` reports drift.

HQ state lives inside the hive root: ``charters/``, ``routing.json``,
``handoffs.jsonl``, ``claims/``, ``baseline.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from hermescube.threats import sanitize_for_storage

ROLES = ("command", "specialist")
_CLAIM_TTL_S = 3600.0
_STUCK_HANDOFF_S = 48 * 3600.0


def hq_paths(hive_root: str | Path) -> dict[str, Path]:
    root = Path(hive_root)
    return {
        "root": root,
        "charters": root / "charters",
        "routing": root / "routing.json",
        "handoffs": root / "handoffs.jsonl",
        "claims": root / "claims",
        "baseline": root / "baseline.json",
    }


def _safe_id(agent_id: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in agent_id)[:64]


# ── Charters (ownership, not personality) ────────────────────────────


def register_charter(
    hive_root: str | Path,
    agent_id: str,
    *,
    role: str,
    lane: str,
    keywords: list[str],
    boundaries: list[str] | None = None,
    description: str = "",
) -> dict[str, Any]:
    """Charter a permanent agent: one durable lane, explicit boundaries.

    The bar for a charter is the article's bar for a permanent profile:
    real recurring work with clear routing — not "cool personality".
    """
    if role not in ROLES:
        return {"ok": False, "error": f"role must be one of {ROLES}"}
    if not lane.strip() or not keywords:
        return {"ok": False, "error": "lane and keywords required"}
    p = hq_paths(hive_root)
    p["charters"].mkdir(parents=True, exist_ok=True)
    charter = {
        "agent_id": agent_id,
        "role": role,
        "lane": sanitize_for_storage(lane, 200),
        "keywords": sorted({k.strip().lower() for k in keywords if k.strip()})[:24],
        "boundaries": [sanitize_for_storage(b, 160) for b in (boundaries or [])][:12],
        "description": sanitize_for_storage(description, 400),
        "status": "active",
        "updated_at": time.time(),
    }
    path = p["charters"] / f"{_safe_id(agent_id)}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(charter, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True, "charter": charter}


def retire_charter(hive_root: str | Path, agent_id: str) -> dict[str, Any]:
    """Retire an agent: history keeps the record, routing stops immediately."""
    p = hq_paths(hive_root)
    path = p["charters"] / f"{_safe_id(agent_id)}.json"
    if not path.is_file():
        return {"ok": False, "error": f"no charter for {agent_id}"}
    charter = json.loads(path.read_text(encoding="utf-8"))
    charter["status"] = "retired"
    charter["retired_at"] = time.time()
    path.write_text(json.dumps(charter, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "charter": charter}


def get_charter(hive_root: str | Path, agent_id: str) -> dict[str, Any] | None:
    path = hq_paths(hive_root)["charters"] / f"{_safe_id(agent_id)}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_charters(
    hive_root: str | Path, *, include_retired: bool = False
) -> list[dict[str, Any]]:
    d = hq_paths(hive_root)["charters"]
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("status") == "retired" and not include_retired:
            continue
        out.append(c)
    return out


# ── Routing (explicit lanes, command fallback) ──────────────────────


def _tokenize(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9][a-z0-9_\-]{2,}", text.lower())}


def route_task(hive_root: str | Path, task: str) -> dict[str, Any]:
    """Decide which charter owns this work.

    Scoring: keyword overlap against active charters, explicit overrides
    from ``routing.json`` first, command-role fallback when nothing
    matches — the orchestrator owns the outcome.
    """
    p = hq_paths(hive_root)
    charters = list_charters(hive_root)
    if not charters:
        return {"ok": False, "error": "no active charters — register the fleet first"}

    active = {c["agent_id"]: c for c in charters}
    tokens = _tokenize(task)

    # explicit overrides win (verify_fleet audits them for ghosts)
    overrides: dict[str, str] = {}
    if p["routing"].is_file():
        try:
            overrides = json.loads(p["routing"].read_text(encoding="utf-8")).get(
                "overrides", {}
            )
        except Exception:
            overrides = {}
    for kw, agent in overrides.items():
        if kw.lower() in tokens and agent in active:
            return {
                "ok": True,
                "owner": agent,
                "via": f"override:{kw}",
                "lane": active[agent].get("lane"),
                "confidence": 1.0,
            }

    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for c in charters:
        hits = [k for k in c.get("keywords") or [] if k in tokens]
        if hits:
            scored.append((float(len(hits)), c, hits))
    scored.sort(key=lambda x: -x[0])

    if scored:
        best_score, best, hits = scored[0]
        runner_up = scored[1] if len(scored) > 1 else None
        return {
            "ok": True,
            "owner": best["agent_id"],
            "via": "lane:" + ",".join(hits[:4]),
            "lane": best.get("lane"),
            "confidence": min(1.0, best_score / 3.0),
            "runner_up": runner_up[1]["agent_id"] if runner_up else None,
        }

    command = next((c for c in charters if c.get("role") == "command"), None)
    if command:
        return {
            "ok": True,
            "owner": command["agent_id"],
            "via": "command_fallback",
            "lane": command.get("lane"),
            "confidence": 0.3,
        }
    return {"ok": False, "error": "no lane match and no command charter"}


def set_route_override(
    hive_root: str | Path, keyword: str, agent_id: str
) -> dict[str, Any]:
    p = hq_paths(hive_root)
    data: dict[str, Any] = {"overrides": {}}
    if p["routing"].is_file():
        try:
            data = json.loads(p["routing"].read_text(encoding="utf-8"))
        except Exception:
            pass
    data.setdefault("overrides", {})[keyword.strip().lower()] = agent_id
    data["updated_at"] = time.time()
    p["routing"].write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "overrides": data["overrides"]}


# ── Task claims (one owner per task) ─────────────────────────────────


def claim_task(
    hive_root: str | Path,
    agent_id: str,
    task_key: str,
    *,
    ttl_s: float = _CLAIM_TTL_S,
) -> dict[str, Any]:
    """Claim a task with a lease. A live claim by another agent is a conflict."""
    p = hq_paths(hive_root)
    p["claims"].mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(task_key.strip().lower().encode()).hexdigest()[:24]
    path = p["claims"] / f"{key}.json"
    now = time.time()
    if path.is_file():
        try:
            cur = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
        if float(cur.get("expires_at") or 0) > now and cur.get("agent_id") != agent_id:
            return {
                "ok": False,
                "conflict": True,
                "owner": cur.get("agent_id"),
                "expires_at": cur.get("expires_at"),
            }
    rec = {
        "agent_id": agent_id,
        "task_key": sanitize_for_storage(task_key, 200),
        "claimed_at": now,
        "expires_at": now + ttl_s,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return {"ok": True, "claim": rec}


def release_claim(hive_root: str | Path, agent_id: str, task_key: str) -> bool:
    p = hq_paths(hive_root)
    key = hashlib.sha256(task_key.strip().lower().encode()).hexdigest()[:24]
    path = p["claims"] / f"{key}.json"
    if not path.is_file():
        return False
    try:
        cur = json.loads(path.read_text(encoding="utf-8"))
        if cur.get("agent_id") != agent_id:
            return False
    except Exception:
        pass
    path.unlink(missing_ok=True)
    return True


# ── Handoffs (context travels with the work) ─────────────────────────


def build_handoff_packet(
    cube: Any,
    task: str,
    *,
    from_agent: str = "",
    to_agent: str = "",
    limit: int = 8,
) -> dict[str, Any]:
    """Distill task-relevant context for a delegation.

    The orchestrator's job is "sending the right context" — not the whole
    history, not nothing. Reuses the evidence packet (quoted, typed,
    provenance-tagged) so the receiving agent gets facts, not habits.
    """
    text = ""
    try:
        from hermescube.evidence import build_evidence_packet
        from hermescube.har import HARQueryEngine

        engine = HARQueryEngine(cube)
        results = engine.query(task, top_k=limit)
        if results:
            text = build_evidence_packet(results, top_n=limit)
    except Exception:
        text = ""
    packet = {
        "task": sanitize_for_storage(task, 400),
        "from_agent": from_agent,
        "to_agent": to_agent,
        "context": text[:4000],
        "sha": hashlib.sha256(text.encode()).hexdigest()[:16] if text else "",
        "built_at": time.time(),
    }
    return packet


def record_handoff(
    hive_root: str | Path,
    *,
    from_agent: str,
    to_agent: str,
    task: str,
    status: str = "pending",
    packet_sha: str = "",
) -> dict[str, Any]:
    p = hq_paths(hive_root)
    rec = {
        "id": f"h{int(time.time() * 1000)}",
        "ts": time.time(),
        "from_agent": from_agent,
        "to_agent": to_agent,
        "task": sanitize_for_storage(task, 300),
        "status": status,  # pending | completed | failed
        "packet_sha": packet_sha,
    }
    p["handoffs"].parent.mkdir(parents=True, exist_ok=True)
    with open(p["handoffs"], "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    return rec


def update_handoff_status(
    hive_root: str | Path, handoff_id: str, status: str
) -> dict[str, Any]:
    """Settle a handoff (completed / failed). Pending handoffs that never
    settle are flagged by ``verify_fleet`` as stuck — this is the exit."""
    if status not in ("pending", "completed", "failed"):
        return {"ok": False, "error": f"bad status: {status}"}
    p = hq_paths(hive_root)
    if not p["handoffs"].is_file():
        return {"ok": False, "error": "no handoffs recorded"}
    records = []
    found = False
    for line in p["handoffs"].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("id") == handoff_id:
            rec["status"] = status
            rec["settled_at"] = time.time()
            found = True
        records.append(rec)
    if not found:
        return {"ok": False, "error": f"handoff not found: {handoff_id}"}
    tmp = p["handoffs"].with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    os.replace(tmp, p["handoffs"])
    return {"ok": True, "id": handoff_id, "status": status}


def list_handoffs(
    hive_root: str | Path, *, status: str = "", limit: int = 50
) -> list[dict[str, Any]]:
    p = hq_paths(hive_root)
    if not p["handoffs"].is_file():
        return []
    out = []
    for line in p["handoffs"].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if status and rec.get("status") != status:
            continue
        out.append(rec)
    return out[-limit:]


# ── Fleet verification (documentation is runtime) ───────────────────


def verify_fleet(hive_root: str | Path) -> dict[str, Any]:
    """Audit the fleet's control plane. Behavior-adjacent, not folder-adjacent.

    Findings:
    - ``ghost_route`` — routing override targets a retired/unknown agent
    - ``lane_conflict`` — the same keyword is owned by two active charters
    - ``no_command`` — no command-role charter (nobody owns outcomes)
    - ``uncharted_soul`` — an agent uploads to the hive but owns no lane
    - ``stuck_handoff`` — pending handoffs older than 48h
    """
    p = hq_paths(hive_root)
    findings: list[dict[str, Any]] = []
    charters = list_charters(hive_root)
    active_ids = {c["agent_id"] for c in charters}

    overrides: dict[str, str] = {}
    if p["routing"].is_file():
        try:
            overrides = json.loads(p["routing"].read_text(encoding="utf-8")).get(
                "overrides", {}
            )
        except Exception:
            overrides = {}
    for kw, agent in overrides.items():
        if agent not in active_ids:
            findings.append(
                {
                    "flag": "ghost_route",
                    "detail": f"override '{kw}' routes to '{agent}' which has no active charter",
                }
            )

    seen_kw: dict[str, str] = {}
    for c in charters:
        for kw in c.get("keywords") or []:
            if kw in seen_kw and seen_kw[kw] != c["agent_id"]:
                findings.append(
                    {
                        "flag": "lane_conflict",
                        "detail": f"keyword '{kw}' owned by both '{seen_kw[kw]}' and '{c['agent_id']}'",
                    }
                )
            else:
                seen_kw[kw] = c["agent_id"]

    if charters and not any(c.get("role") == "command" for c in charters):
        findings.append(
            {"flag": "no_command", "detail": "no command charter — nobody owns outcomes"}
        )

    try:
        from hermescube.hive import list_souls

        for soul in list_souls(hive_root):
            aid = str(soul.get("agent_id") or "")
            if aid and aid not in active_ids:
                findings.append(
                    {
                        "flag": "uncharted_soul",
                        "detail": f"agent '{aid}' uploads to the hive but owns no lane",
                    }
                )
    except Exception:
        pass

    cutoff = time.time() - _STUCK_HANDOFF_S
    for h in list_handoffs(hive_root, status="pending"):
        if float(h.get("ts") or 0) < cutoff:
            findings.append(
                {
                    "flag": "stuck_handoff",
                    "detail": f"handoff {h.get('id')} to '{h.get('to_agent')}' pending >48h",
                }
            )

    return {
        "ok": True,
        "verdict": "healthy" if not findings else "flagged",
        "charters": len(charters),
        "findings": findings,
    }


# ── Baseline (production ready means recoverable) ───────────────────


def _sha_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def freeze_baseline(hive_root: str | Path) -> dict[str, Any]:
    """Snapshot the control plane: charter hashes, routing hash, collective stats."""
    p = hq_paths(hive_root)
    charter_hashes = {}
    if p["charters"].is_dir():
        for f in sorted(p["charters"].glob("*.json")):
            charter_hashes[f.stem] = _sha_file(f)
    entries = -1
    cube_path = Path(hive_root) / "hive.cube"
    if cube_path.is_file():
        try:
            from hermescube.cube import CubeFile

            with CubeFile.open(str(cube_path)) as c:
                entries = c.entry_count
        except Exception:
            entries = -1
    baseline = {
        "frozen_at": time.time(),
        "charters": charter_hashes,
        "routing_sha": _sha_file(p["routing"]),
        "collective_entries": entries,
    }
    p["baseline"].write_text(
        json.dumps(baseline, indent=2, default=str), encoding="utf-8"
    )
    return {"ok": True, "baseline": baseline}


def verify_baseline(hive_root: str | Path) -> dict[str, Any]:
    """Report drift since the frozen baseline — prove what changed."""
    p = hq_paths(hive_root)
    if not p["baseline"].is_file():
        return {"ok": False, "error": "no baseline frozen"}
    try:
        base = json.loads(p["baseline"].read_text(encoding="utf-8"))
    except Exception as e:
        return {"ok": False, "error": f"baseline unreadable: {e}"}

    drift: list[str] = []
    current: dict[str, str] = {}
    if p["charters"].is_dir():
        for f in sorted(p["charters"].glob("*.json")):
            current[f.stem] = _sha_file(f)
    old = base.get("charters") or {}
    for name in sorted(set(old) | set(current)):
        if name not in current:
            drift.append(f"charter removed: {name}")
        elif name not in old:
            drift.append(f"charter added: {name}")
        elif old[name] != current[name]:
            drift.append(f"charter changed: {name}")
    if _sha_file(p["routing"]) != (base.get("routing_sha") or ""):
        drift.append("routing overrides changed")
    return {
        "ok": True,
        "frozen_at": base.get("frozen_at"),
        "drift": drift,
        "clean": not drift,
    }


# ── Prompt strip (lane awareness in every session) ──────────────────


def lane_strip(hive_root: str | Path, agent_id: str) -> str:
    """One compact block: your lane, your boundaries, where other work goes."""
    charter = get_charter(hive_root, agent_id)
    charters = list_charters(hive_root)
    if not charter or charter.get("status") != "active":
        return ""
    lines = [f"HQ lane [{charter.get('role')}]: {charter.get('lane')}"]
    if charter.get("boundaries"):
        lines.append("Boundaries: " + "; ".join(charter["boundaries"][:4]))
    others = [
        f"{c.get('lane', '?')[:40]} → {c['agent_id']}"
        for c in charters
        if c["agent_id"] != agent_id
    ][:6]
    if others:
        lines.append("Other lanes: " + " · ".join(others))
        lines.append("Not your lane → hand off (manage action=hq hq_action=route).")
    return "\n".join(lines)
