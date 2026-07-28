"""CubeDream L2 — shared dream circles (agents dreaming together).

Chorus mode MVP: multi-writer signals → together-aware scoring → locked close
into the hive cube. Dialogue-in-circle can reuse interview later.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from hermescube.cube import CubeFile
from hermescube.threats import sanitize_for_storage, scan_text

CLAIM_BOUNDARY = (
    "Circle signals and diary lines are prepared context — not hive proof "
    "until close promotes them, and never MEMORY.md proof."
)
META_SCHEMA = "hermescube_dream_circle/v1"
SIGNAL_SCHEMA = "hermescube_dream_signal/v1"
CAND_SCHEMA = "hermescube_dream_candidate/v1"
TOGETHER_BONUS = 0.20
DEFAULT_TTL_S = 3600
_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)
_STOP = frozenset(
    "the and for with that this from into your our are was were been have has "
    "had not but you they them then than also just about when what who how why "
    "prefers likes using".split()
)


def circles_root(hive_root: str | Path) -> Path:
    return Path(hive_root) / "dreams" / "circles"


def circle_paths(hive_root: str | Path, circle_id: str) -> dict[str, Path]:
    root = circles_root(hive_root) / circle_id
    return {
        "root": root,
        "meta": root / "meta.json",
        "signals": root / "signals.jsonl",
        "candidates": root / "candidates.jsonl",
        "diary": root / "DREAMS.md",
        "dialogues": root / "dialogues",
        "lock": root / "lock",
    }


def hive_dream_lock_path(hive_root: str | Path) -> Path:
    return Path(hive_root) / ".locks" / "dream.lock"


def acquire_lock(
    lock_path: Path,
    *,
    holder: str,
    ttl_s: int = 300,
) -> dict[str, Any]:
    """Exclusive lock with TTL. Returns ok=False when held by another live holder."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if lock_path.is_file():
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            exp = float(data.get("expires_at") or 0)
            prev = str(data.get("holder") or "")
            if exp > now and prev and prev != holder:
                return {
                    "ok": False,
                    "error": "lock_held",
                    "holder": prev,
                    "expires_at": exp,
                }
        except Exception:
            pass
    payload = {
        "holder": holder,
        "acquired_at": now,
        "expires_at": now + max(30, int(ttl_s)),
    }
    tmp = lock_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp, lock_path)
    return {"ok": True, **payload}


def release_lock(lock_path: Path, *, holder: str) -> dict[str, Any]:
    if not lock_path.is_file():
        return {"ok": True, "released": False}
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        if str(data.get("holder") or "") not in ("", holder):
            return {"ok": False, "error": "not_holder", "holder": data.get("holder")}
    except Exception:
        pass
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass
    return {"ok": True, "released": True}


def canonical_key(summary: str, entities: list[str] | None = None) -> str:
    """Stable chorus key: entities win when present so peers can agree across wording."""
    ents = sorted({(e or "").strip().lower() for e in (entities or []) if e})[:8]
    if len(ents) >= 2:
        material = "ent|" + "|".join(ents)
    else:
        toks = sorted(
            {
                t.lower()
                for t in _TOKEN.findall(summary or "")
                if t.lower() not in _STOP
            }
        )[:10]
        material = "tok|" + "|".join(ents + toks) or (summary or "").strip().lower()[:80]
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def open_circle(
    hive_root: str | Path,
    *,
    opened_by: str,
    topic: str = "",
    ttl_s: int = DEFAULT_TTL_S,
) -> dict[str, Any]:
    from hermescube.hive import init_hive, is_hive

    if not is_hive(hive_root):
        init_hive(hive_root)
    circle_id = f"c_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    paths = circle_paths(hive_root, circle_id)
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["dialogues"].mkdir(exist_ok=True)
    meta = {
        "schema_version": META_SCHEMA,
        "circle_id": circle_id,
        "opened_by": opened_by,
        "topic": (topic or "").strip()[:200],
        "status": "open",
        "opened_at": time.time(),
        "expires_at": time.time() + max(60, int(ttl_s)),
        "members": [opened_by],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    paths["signals"].touch()
    paths["diary"].write_text(
        f"# Dream circle `{circle_id}`\n\nTopic: {meta['topic'] or '(open)'}\n"
        f"Opened by: {opened_by}\n\n_{CLAIM_BOUNDARY}_\n",
        encoding="utf-8",
    )
    return {"ok": True, **meta, "path": str(paths["root"])}


def _load_meta(hive_root: str | Path, circle_id: str) -> dict[str, Any] | None:
    paths = circle_paths(hive_root, circle_id)
    if not paths["meta"].is_file():
        return None
    try:
        data = json.loads(paths["meta"].read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _save_meta(hive_root: str | Path, meta: dict[str, Any]) -> None:
    paths = circle_paths(hive_root, str(meta["circle_id"]))
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")


def join_circle(
    hive_root: str | Path, circle_id: str, *, agent_id: str
) -> dict[str, Any]:
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    if meta.get("status") != "open":
        return {"ok": False, "error": f"circle_{meta.get('status')}", "meta": meta}
    members = list(meta.get("members") or [])
    if agent_id not in members:
        members.append(agent_id)
        meta["members"] = members
        _save_meta(hive_root, meta)
    return {"ok": True, "circle_id": circle_id, "members": members}


def post_signal(
    hive_root: str | Path,
    circle_id: str,
    *,
    agent_id: str,
    summary: str,
    entities: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    kind: str = "chorus",
    trust: float = 0.5,
) -> dict[str, Any]:
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    if meta.get("status") != "open":
        return {"ok": False, "error": f"circle_{meta.get('status')}"}
    text = sanitize_for_storage((summary or "").strip(), 800)
    if len(text) < 12:
        return {"ok": False, "error": "summary_too_short"}
    if any(t.severity == "block" for t in scan_text(text)):
        return {"ok": False, "error": "blocked_by_threat_scan"}
    try:
        from hermescube.memory_gate import memory_safety

        if memory_safety(text, text).get("status") == "blocked":
            return {"ok": False, "error": "blocked_by_memory_safety"}
    except Exception:
        pass

    # Auto-join on signal
    members = list(meta.get("members") or [])
    if agent_id not in members:
        members.append(agent_id)
        meta["members"] = members
        _save_meta(hive_root, meta)

    key = canonical_key(text, entities)
    signal = {
        "schema_version": SIGNAL_SCHEMA,
        "signal_id": f"sig_{uuid.uuid4().hex[:10]}",
        "circle_id": circle_id,
        "agent_id": agent_id,
        "kind": kind,
        "summary": text,
        "entities": list(entities or [])[:12],
        "evidence_refs": list(evidence_refs or [])[:12],
        "canonical_key": key,
        "trust": float(trust),
        "ts": time.time(),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    paths = circle_paths(hive_root, circle_id)
    with open(paths["signals"], "a", encoding="utf-8") as f:
        f.write(json.dumps(signal, ensure_ascii=False) + "\n")
    return {"ok": True, **signal}


def signal_from_cube(
    hive_root: str | Path,
    circle_id: str,
    cube: Any,
    *,
    agent_id: str,
    limit: int = 24,
) -> dict[str, Any]:
    """Post Light signals from offerable cube entries (Chorus feed)."""
    from hermescube.hive import build_offering

    rows = build_offering(cube, agent_id=agent_id, limit=limit)
    posted = 0
    keys: list[str] = []
    errors = 0
    for row in rows:
        ents = []
        data = row.get("data") or {}
        if isinstance(data.get("entities"), list):
            ents = [str(x) for x in data["entities"][:8]]
        r = post_signal(
            hive_root,
            circle_id,
            agent_id=agent_id,
            summary=str(row.get("description") or ""),
            entities=ents,
            evidence_refs=[str(row.get("src_entry_id") or "")],
            kind="chorus",
            trust=float((data or {}).get("trust") or 0.5),
        )
        if r.get("ok"):
            posted += 1
            keys.append(str(r.get("canonical_key")))
        else:
            errors += 1
    return {
        "ok": True,
        "circle_id": circle_id,
        "agent_id": agent_id,
        "offered_rows": len(rows),
        "posted": posted,
        "errors": errors,
        "keys": keys[:20],
    }


def _read_signals(hive_root: str | Path, circle_id: str) -> list[dict[str, Any]]:
    paths = circle_paths(hive_root, circle_id)
    out: list[dict[str, Any]] = []
    if not paths["signals"].is_file():
        return out
    with open(paths["signals"], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
    return out


def score_circle(
    hive_root: str | Path,
    circle_id: str,
    *,
    scorer: str,
    min_agents_together: int = 2,
    lock_ttl_s: int = 300,
) -> dict[str, Any]:
    """Cluster signals by canonical_key; apply together bonus; write candidates."""
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    if meta.get("status") not in ("open", "scoring"):
        return {"ok": False, "error": f"circle_{meta.get('status')}"}

    paths = circle_paths(hive_root, circle_id)
    lock = acquire_lock(paths["lock"], holder=scorer, ttl_s=lock_ttl_s)
    if not lock.get("ok"):
        return lock

    try:
        meta["status"] = "scoring"
        _save_meta(hive_root, meta)
        signals = _read_signals(hive_root, circle_id)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in signals:
            groups[str(s.get("canonical_key") or "")].append(s)

        candidates: list[dict[str, Any]] = []
        for key, rows in groups.items():
            if not key:
                continue
            agents = sorted({str(r.get("agent_id") or "") for r in rows if r.get("agent_id")})
            together = len(agents) >= max(2, int(min_agents_together))
            freq = len(rows)
            trust_avg = sum(float(r.get("trust") or 0.5) for r in rows) / max(1, freq)
            together_score = TOGETHER_BONUS if together else 0.0
            score = min(
                1.0,
                0.22 * min(1.0, freq / 5.0)
                + together_score
                + 0.18 * trust_avg
                + 0.12,  # mild base
            )
            summary = str(rows[0].get("summary") or "")
            # Prefer longest summary as representative
            for r in rows:
                if len(str(r.get("summary") or "")) > len(summary):
                    summary = str(r.get("summary") or "")
            cand = {
                "schema_version": CAND_SCHEMA,
                "candidate_id": f"dream_{uuid.uuid4().hex[:10]}",
                "circle_id": circle_id,
                "canonical_key": key,
                "kind": "promote" if together or score >= 0.55 else "theme",
                "plane": "circle",
                "summary": summary[:800],
                "supporting_agents": agents,
                "occurrence_count": freq,
                "together": together,
                "score": round(score, 4),
                "score_components": {
                    "frequency": round(0.22 * min(1.0, freq / 5.0), 4),
                    "together": together_score,
                    "trust": round(0.18 * trust_avg, 4),
                },
                "evidence_refs": [
                    ref
                    for r in rows
                    for ref in (r.get("evidence_refs") or [])
                    if ref
                ][:16],
                "claim_boundary": CLAIM_BOUNDARY,
            }
            candidates.append(cand)

        candidates.sort(key=lambda c: (-float(c["score"]), -int(c["occurrence_count"])))
        with open(paths["candidates"], "w", encoding="utf-8") as f:
            for c in candidates:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")

        together_n = sum(1 for c in candidates if c.get("together"))
        diary = (
            f"\n## Score ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})\n\n"
            f"Scorer: {scorer}\n"
            f"Signals: {len(signals)} → candidates: {len(candidates)} "
            f"(together: {together_n})\n"
            f"_{CLAIM_BOUNDARY}_\n"
        )
        with open(paths["diary"], "a", encoding="utf-8") as f:
            f.write(diary)

        meta["status"] = "open"  # remain open until close
        meta["last_scored_at"] = time.time()
        meta["candidate_count"] = len(candidates)
        meta["together_count"] = together_n
        _save_meta(hive_root, meta)
        return {
            "ok": True,
            "circle_id": circle_id,
            "signals": len(signals),
            "candidates": len(candidates),
            "together_count": together_n,
            "top": candidates[:5],
        }
    finally:
        release_lock(paths["lock"], holder=scorer)


def close_circle(
    hive_root: str | Path,
    circle_id: str,
    *,
    closer: str,
    max_promotes: int = 5,
    min_score: float = 0.55,
    prefer_together: bool = True,
    lock_ttl_s: int = 300,
) -> dict[str, Any]:
    """Promote top circle candidates into hive.cube under hive dream lock."""
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    if meta.get("status") == "closed":
        return {"ok": False, "error": "already_closed", "meta": meta}

    paths = circle_paths(hive_root, circle_id)
    # Ensure scored
    if not paths["candidates"].is_file() or paths["candidates"].stat().st_size == 0:
        scored = score_circle(
            hive_root, circle_id, scorer=closer, lock_ttl_s=lock_ttl_s
        )
        if not scored.get("ok"):
            return scored

    hive_lock = hive_dream_lock_path(hive_root)
    lock = acquire_lock(hive_lock, holder=f"close:{closer}", ttl_s=lock_ttl_s)
    if not lock.get("ok"):
        return lock

    try:
        candidates: list[dict[str, Any]] = []
        with open(paths["candidates"], encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    candidates.append(json.loads(line))
                except Exception:
                    continue

        chosen: list[dict[str, Any]] = []
        for c in candidates:
            if prefer_together and not c.get("together"):
                if float(c.get("score") or 0) < min_score + 0.1:
                    continue
            elif float(c.get("score") or 0) < min_score and not c.get("together"):
                continue
            chosen.append(c)
            if len(chosen) >= max_promotes:
                break

        from hermescube.hive import hive_paths, init_hive, is_hive, _ledger_write

        if not is_hive(hive_root):
            init_hive(hive_root)
        hp = hive_paths(hive_root)
        promoted = 0
        with CubeFile.open(str(hp["cube"])) as hive_cube:
            for c in chosen:
                desc = sanitize_for_storage(str(c.get("summary") or ""), 1200)
                agents = ",".join(c.get("supporting_agents") or [])
                hive_cube.append(
                    entry_type="belief",
                    description=f"[CIRCLE:{circle_id}] {desc}",
                    data={
                        "durable": True,
                        "origin": "dream_circle",
                        "circle_id": circle_id,
                        "candidate_id": c.get("candidate_id"),
                        "canonical_key": c.get("canonical_key"),
                        "supporting_agents": c.get("supporting_agents") or [],
                        "together": bool(c.get("together")),
                        "dream_score": c.get("score"),
                        "verification": "hive_shared",
                        "trust": min(0.85, 0.5 + float(c.get("score") or 0) * 0.3),
                        "from_agents": agents,
                    },
                    outcome="success",
                )
                promoted += 1

        meta["status"] = "closed"
        meta["closed_at"] = time.time()
        meta["closed_by"] = closer
        meta["promoted"] = promoted
        _save_meta(hive_root, meta)
        _ledger_write(
            hive_root,
            {
                "action": "dream_circle_close",
                "circle_id": circle_id,
                "closer": closer,
                "promoted": promoted,
                "members": meta.get("members"),
            },
        )
        with open(paths["diary"], "a", encoding="utf-8") as f:
            f.write(
                f"\n## Closed\n\nCloser: {closer}\nPromoted to hive: {promoted}\n"
                f"Members: {', '.join(meta.get('members') or [])}\n"
                f"_{CLAIM_BOUNDARY}_\n"
            )
        return {
            "ok": True,
            "circle_id": circle_id,
            "promoted": promoted,
            "members": meta.get("members"),
            "status": "closed",
            "claim_boundary": CLAIM_BOUNDARY,
        }
    finally:
        release_lock(hive_lock, holder=f"close:{closer}")


def draw_circle(
    hive_root: str | Path,
    circle_id: str,
    cube: Any,
    *,
    agent_id: str,
    limit: int = 12,
) -> dict[str, Any]:
    """Draw circle-promoted hive entries into the agent's soul cube."""
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    from hermescube.hive import hive_paths

    hp = hive_paths(hive_root)
    if not hp["cube"].is_file():
        return {"ok": False, "error": "hive_cube_missing"}
    marker = f"[CIRCLE:{circle_id}]"
    drawn = 0
    with CubeFile.open(str(hp["cube"])) as hive_cube:
        for e in list(hive_cube.read_l1() or []):
            desc = e.description or ""
            if marker not in desc:
                continue
            d = dict(e.data or {})
            # skip if this agent already has this candidate
            already = False
            for local in list(cube.read_l1() or [])[-200:]:
                ld = local.data if isinstance(getattr(local, "data", None), dict) else {}
                if ld.get("candidate_id") == d.get("candidate_id"):
                    already = True
                    break
            if already:
                continue
            cube.append(
                entry_type=e.entry_type or "belief",
                description=desc,
                data={
                    **{
                        k: d[k]
                        for k in (
                            "origin",
                            "circle_id",
                            "candidate_id",
                            "canonical_key",
                            "supporting_agents",
                            "together",
                            "dream_score",
                        )
                        if k in d
                    },
                    "verification": "hive_shared",
                    "hive_shared": True,
                    "from_circle": circle_id,
                    "drawn_by": agent_id,
                    "durable": True,
                    "trust": float(d.get("trust") or 0.55),
                },
                outcome="success",
            )
            drawn += 1
            if drawn >= limit:
                break
    return {
        "ok": True,
        "circle_id": circle_id,
        "agent_id": agent_id,
        "drawn": drawn,
        "claim_boundary": CLAIM_BOUNDARY,
    }


def list_circles(hive_root: str | Path, *, limit: int = 20) -> list[dict[str, Any]]:
    root = circles_root(hive_root)
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted(root.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        meta = _load_meta(hive_root, d.name)
        if meta:
            out.append(
                {
                    "circle_id": meta.get("circle_id"),
                    "status": meta.get("status"),
                    "topic": meta.get("topic"),
                    "members": meta.get("members"),
                    "promoted": meta.get("promoted"),
                    "opened_at": meta.get("opened_at"),
                }
            )
        if len(out) >= limit:
            break
    return out


def circle_status(hive_root: str | Path, circle_id: str) -> dict[str, Any]:
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    signals = _read_signals(hive_root, circle_id)
    return {
        "ok": True,
        **meta,
        "signal_count": len(signals),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def dialogue_in_circle(
    hive_root: str | Path,
    circle_id: str,
    *,
    interviewer: str,
    subject: str,
    topic: str = "",
    hermes_home: str | Path | None = None,
    subject_cube: Any = None,
    mint: bool = False,
    max_turns: int = 6,
) -> dict[str, Any]:
    """Conversation mode: peer interview inside a circle; facts become signals."""
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    if meta.get("status") != "open":
        return {"ok": False, "error": f"circle_{meta.get('status')}"}

    join_circle(hive_root, circle_id, agent_id=interviewer)
    join_circle(hive_root, circle_id, agent_id=subject)

    from hermescube.interview import peer_dialogue

    focus = (topic or meta.get("topic") or "shared craft").strip()
    dialogue = peer_dialogue(
        hive_root,
        interviewer=interviewer,
        subject=subject,
        topic=focus,
        mode="discover",
        subject_cube=subject_cube,
        hermes_home=hermes_home,
        persist=True,
        mint=bool(mint),
        max_turns=max_turns,
    )
    if not dialogue.get("ok"):
        return dialogue

    paths = circle_paths(hive_root, circle_id)
    paths["dialogues"].mkdir(parents=True, exist_ok=True)
    sid = str(dialogue.get("session_id") or uuid.uuid4().hex[:10])
    rec_path = paths["dialogues"] / f"{sid}.json"
    rec_path.write_text(
        json.dumps(
            {
                "circle_id": circle_id,
                "session_id": sid,
                "interviewer": interviewer,
                "subject": subject,
                "topic": focus,
                "outcome": dialogue.get("outcome"),
                "turns": dialogue.get("turns"),
                "brief_path": dialogue.get("brief_path"),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    posted = 0
    # Distill brief / outcome into chorus signals attributed to both agents
    snippets: list[str] = []
    brief_path = dialogue.get("brief_path")
    if brief_path and Path(brief_path).is_file():
        try:
            text = Path(brief_path).read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip(" -*")
                if len(line) >= 24 and not line.startswith("#"):
                    snippets.append(line[:400])
                if len(snippets) >= 4:
                    break
        except Exception:
            pass
    if not snippets:
        snippets.append(
            f"Peer interview {interviewer}↔{subject} on {focus}: "
            f"{dialogue.get('outcome') or 'done'}"
        )

    for snip in snippets:
        for agent in (interviewer, subject):
            r = post_signal(
                hive_root,
                circle_id,
                agent_id=agent,
                summary=snip,
                entities=[interviewer, subject, focus.split()[0] if focus else "craft"],
                evidence_refs=[sid],
                kind="dialogue_fact",
                trust=0.62,
            )
            if r.get("ok"):
                posted += 1

    with open(paths["diary"], "a", encoding="utf-8") as f:
        f.write(
            f"\n## Dialogue\n\n{interviewer} interviewed {subject} on {focus!r}\n"
            f"session={sid} outcome={dialogue.get('outcome')} "
            f"signals_posted={posted}\n"
            f"_{CLAIM_BOUNDARY}_\n"
        )

    meta = _load_meta(hive_root, circle_id) or meta
    meta["dialogues"] = int(meta.get("dialogues") or 0) + 1
    _save_meta(hive_root, meta)

    return {
        "ok": True,
        "circle_id": circle_id,
        "dialogue": dialogue,
        "signals_posted": posted,
        "record": str(rec_path),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def adversarial_skim(
    hive_root: str | Path,
    circle_id: str,
    *,
    local_entries: list[Any] | None = None,
) -> dict[str, Any]:
    """Loom-lite: flag circle candidates that conflict with hive/local evidence.

    Report-only — adjusts candidate risk_flags / score in candidates.jsonl;
    does not delete signals.
    """
    meta = _load_meta(hive_root, circle_id)
    if not meta:
        return {"ok": False, "error": "circle_not_found"}
    paths = circle_paths(hive_root, circle_id)
    if not paths["candidates"].is_file() or paths["candidates"].stat().st_size == 0:
        scored = score_circle(hive_root, circle_id, scorer="adversary")
        if not scored.get("ok"):
            return scored

    from hermescube.conflict import find_conflicts
    from hermescube.hive import hive_paths

    corpus: list[Any] = list(local_entries or [])
    hp = hive_paths(hive_root)
    if hp["cube"].is_file():
        with CubeFile.open(str(hp["cube"])) as hive_cube:
            corpus.extend(list(hive_cube.read_l1() or [])[-400:])

    updated: list[dict[str, Any]] = []
    flagged = 0
    with open(paths["candidates"], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
            except Exception:
                continue
            summary = str(c.get("summary") or "")
            confs = find_conflicts(summary, corpus, limit=3) if summary else []
            if confs:
                flagged += 1
                flags = list(c.get("risk_flags") or [])
                flags.append("adversarial_conflict")
                c["risk_flags"] = flags
                c["adversary"] = {
                    "verdict": "harmful" if len(confs) >= 2 else "neutral",
                    "conflicts": confs[:3],
                }
                # Bounded penalty — report-influenced ranking
                c["score"] = round(max(0.0, float(c.get("score") or 0) - 0.12), 4)
                if c.get("kind") == "promote" and c["adversary"]["verdict"] == "harmful":
                    c["kind"] = "theme"
            else:
                c.setdefault("adversary", {"verdict": "helpful", "conflicts": []})
            updated.append(c)

    updated.sort(key=lambda c: (-float(c.get("score") or 0), -int(c.get("occurrence_count") or 0)))
    with open(paths["candidates"], "w", encoding="utf-8") as f:
        for c in updated:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    with open(paths["diary"], "a", encoding="utf-8") as f:
        f.write(
            f"\n## Adversarial skim\n\nFlagged {flagged}/{len(updated)} candidates\n"
            f"_{CLAIM_BOUNDARY}_\n"
        )
    return {
        "ok": True,
        "circle_id": circle_id,
        "candidates": len(updated),
        "flagged": flagged,
        "top": updated[:5],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def run_auto_circle(
    hive_root: str | Path,
    *,
    agent_homes: dict[str, str | Path],
    topic: str = "night chorus",
    opened_by: str = "night-watch",
    max_promotes: int = 5,
    interview_pairs: list[tuple[str, str]] | None = None,
    skim: bool = True,
) -> dict[str, Any]:
    """Quiet-hour Chorus: open circle, signal from each soul cube, score, close.

    ``agent_homes`` maps agent_id → hermes_home path. Offline agents still
    dream together via distilled cube offerings (no live chat required).
    """
    from hermescube.hive import init_hive, is_hive

    if not is_hive(hive_root):
        init_hive(hive_root)

    opened = open_circle(hive_root, opened_by=opened_by, topic=topic)
    if not opened.get("ok"):
        return opened
    cid = str(opened["circle_id"])
    feeds: list[dict[str, Any]] = []

    for agent_id, home in agent_homes.items():
        home_p = Path(home)
        cube_path = home_p / "memories" / "memory.cube"
        if not cube_path.is_file():
            feeds.append({"agent_id": agent_id, "ok": False, "error": "cube_missing"})
            continue
        join_circle(hive_root, cid, agent_id=agent_id)
        with CubeFile.open(str(cube_path)) as cube:
            feeds.append(
                signal_from_cube(hive_root, cid, cube, agent_id=agent_id, limit=20)
            )

    dialogues: list[dict[str, Any]] = []
    for pair in interview_pairs or []:
        if len(pair) != 2:
            continue
        a, b = pair
        home_b = agent_homes.get(b)
        cube_b = Path(home_b) / "memories" / "memory.cube" if home_b else None
        if cube_b and cube_b.is_file():
            with CubeFile.open(str(cube_b)) as sub_cube:
                dialogues.append(
                    dialogue_in_circle(
                        hive_root,
                        cid,
                        interviewer=a,
                        subject=b,
                        topic=topic,
                        hermes_home=agent_homes.get(a),
                        subject_cube=sub_cube,
                        mint=False,
                    )
                )
        else:
            dialogues.append(
                dialogue_in_circle(
                    hive_root,
                    cid,
                    interviewer=a,
                    subject=b,
                    topic=topic,
                    hermes_home=agent_homes.get(a),
                    mint=False,
                )
            )

    scored = score_circle(hive_root, cid, scorer=opened_by)
    skim_report: dict[str, Any] = {}
    if skim and scored.get("ok"):
        skim_report = adversarial_skim(hive_root, cid)
    closed = close_circle(
        hive_root, cid, closer=opened_by, max_promotes=max_promotes
    )

    return {
        "ok": bool(closed.get("ok")),
        "circle_id": cid,
        "topic": topic,
        "feeds": feeds,
        "dialogues": dialogues,
        "score": scored,
        "adversarial": skim_report,
        "close": closed,
        "claim_boundary": CLAIM_BOUNDARY,
    }
