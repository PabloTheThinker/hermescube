"""HiveCube — a shared nexus where Hermes Agents pool distilled experience.

Concept
-------
Each Hermes Agent keeps its own private cube (its soul-record). A Hive is a
shared directory containing a collective cube plus per-agent soul cards.
Agents perform a **pilgrimage** (typically nightly, via cron):

  1. OFFER    — distill durable experience (wisdom, approved procedures,
                session digests, durable beliefs) into a signed offering.
                Raw conversation turns are never offered by default.
  2. ASSIMILATE — the hive merges offerings: threat-scanned, deduplicated by
                content hash, branch-tagged ``hive:<agent>``, provenance kept.
  3. DRAW     — the agent pulls collective wisdom relevant to its focus into
                its own cube under branch ``hive:collective`` with
                verification ``hive_shared`` (never trusted as user truth).

Hard rules
----------
- Local-first: a hive is a filesystem path (shared disk / synced folder).
  No network protocol here; sync transport is the operator's choice.
- Privacy: offerings contain distilled entries only; ``private: true``
  entries and raw turn payloads are excluded.
- No silent skill install: shared procedures arrive as drafts, consent-gated.
- Provenance survives: every assimilated entry cites source agent + hashes.
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from hermescube.cube import CubeFile
from hermescube.events import content_hash, event_to_entry_data, make_event
from hermescube.threats import sanitize_for_storage, scan_text

logger = logging.getLogger(__name__)

HIVE_MARKER = "hive.json"
OFFER_TYPES = {"belief", "trait", "resolve", "evolution", "landmark", "relationship"}
_OFFER_SOURCES_SKIP = {"sync_turn"}  # raw turns stay private
DRAW_VERIFICATION = "hive_shared"


# ── Hive layout ──────────────────────────────────────────────────────


def hive_paths(hive_root: str | Path) -> dict[str, Path]:
    root = Path(hive_root)
    return {
        "root": root,
        "marker": root / HIVE_MARKER,
        "cube": root / "hive.cube",
        "agents": root / "agents",
        "offerings": root / "offerings",
        "ledger": root / "ledger.jsonl",
    }


def init_hive(hive_root: str | Path, *, name: str = "hermes-hive") -> dict[str, Any]:
    """Create a hive directory with collective cube + ledgers."""
    p = hive_paths(hive_root)
    p["root"].mkdir(parents=True, exist_ok=True)
    p["agents"].mkdir(exist_ok=True)
    p["offerings"].mkdir(exist_ok=True)
    if not p["cube"].is_file():
        CubeFile.create(str(p["cube"]))
    meta = {
        "name": name,
        "created_at": time.time(),
        "version": 1,
        "note": "HermesCube hive — collective distilled experience. Local-first.",
    }
    if not p["marker"].is_file():
        p["marker"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    else:
        meta = json.loads(p["marker"].read_text(encoding="utf-8"))
    return {"ok": True, "root": str(p["root"]), "meta": meta}


def is_hive(hive_root: str | Path) -> bool:
    return hive_paths(hive_root)["marker"].is_file()


def _ledger_write(hive_root: str | Path, record: dict[str, Any]) -> None:
    p = hive_paths(hive_root)
    record = dict(record)
    record.setdefault("ts", time.time())
    with open(p["ledger"], "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# ── Soul cards ───────────────────────────────────────────────────────


def build_soul_card(
    entries: list[Any],
    *,
    agent_id: str,
    hermes_home: str | Path | None = None,
) -> dict[str, Any]:
    """Distill an agent's identity: who it is, what it knows, what it pursues."""
    ents = sorted(
        entries, key=lambda e: getattr(e, "timestamp", "") or "", reverse=True
    )

    def pick(types: set[str], limit: int, *, require_durable: bool = False) -> list[str]:
        out: list[str] = []
        for e in ents:
            et = (getattr(e, "entry_type", "") or "").lower()
            if et not in types:
                continue
            if (getattr(e, "outcome", "") or "") == "superseded":
                continue
            d = e.data if isinstance(getattr(e, "data", None), dict) else {}
            if d.get("private"):
                continue
            if require_durable and not d.get("durable"):
                continue
            desc = (getattr(e, "description", "") or "").strip()
            if not desc:
                continue
            out.append(desc[:200])
            if len(out) >= limit:
                break
        return out

    wisdom = []
    for e in ents:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        if d.get("crystal") and not d.get("private"):
            wisdom.append((e.description or "")[:200])
        if len(wisdom) >= 6:
            break

    procedures = []
    for e in ents:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        if d.get("procedure") and not d.get("private"):
            procedures.append((e.description or "")[:200])
        if len(procedures) >= 6:
            break

    card = {
        "agent_id": agent_id,
        "updated_at": time.time(),
        "entry_count": len(entries),
        "soul": {
            "wisdom": wisdom,
            "missions": pick({"focus"}, 5),
            "resolves": pick({"resolve"}, 5),
            "beliefs": pick({"belief"}, 6, require_durable=True),
            "procedures": procedures,
        },
    }
    # Living growth — peers see how mature this soul's cube is
    if hermes_home:
        try:
            from hermescube.genealogy import load_genealogy

            g = load_genealogy(hermes_home)
            card["growth"] = {
                "version": g.get("version") or "0.0.0",
                "era": g.get("era") or "genesis",
                "strength": g.get("strength") or 0,
                "epochs": g.get("epochs") or 0,
                "skills": list((g.get("skills") or {}).keys())[:12],
            }
        except Exception:
            pass
    # merge peer knowledge if present
    try:
        from hermescube.peer_card import load_card

        pc = load_card(hermes_home) if hermes_home else None
        if pc:
            card["peer"] = {
                k: v for k, v in pc.items() if k in ("name", "traits", "focuses")
            }
    except Exception:
        pass
    return card


def publish_soul_card(hive_root: str | Path, card: dict[str, Any]) -> Path:
    p = hive_paths(hive_root)
    p["agents"].mkdir(parents=True, exist_ok=True)
    safe = "".join(
        c if c.isalnum() or c in "-_." else "_" for c in str(card.get("agent_id") or "agent")
    )[:64]
    path = p["agents"] / f"{safe}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(card, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)
    return path


def list_souls(hive_root: str | Path) -> list[dict[str, Any]]:
    p = hive_paths(hive_root)
    if not p["agents"].is_dir():
        return []
    out = []
    for f in sorted(p["agents"].glob("*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


# ── Offer (agent → hive) ─────────────────────────────────────────────


def _offerable(entry: Any) -> bool:
    et = (getattr(entry, "entry_type", "") or "").lower()
    if et not in OFFER_TYPES:
        return False
    if (getattr(entry, "outcome", "") or "") == "superseded":
        return False
    d = entry.data if isinstance(getattr(entry, "data", None), dict) else {}
    if d.get("private"):
        return False
    if (d.get("source") or "") in _OFFER_SOURCES_SKIP:
        return False
    # No wisdom laundering: knowledge that arrived FROM the hive (drawn
    # entries, hive_shared verification) must never be re-offered under
    # this agent's name — the collective already holds it with the true
    # author's provenance.
    if d.get("hive_shared") or d.get("from_agent") or d.get("offer_hash"):
        return False
    if str(d.get("verification") or "") == "hive_shared":
        return False
    desc = (getattr(entry, "description", "") or "").strip()
    if len(desc) < 12:
        return False
    if desc.startswith("[HIVE:") or "[INTERVIEW:" in desc:
        return False
    # only share durable / distilled knowledge
    if not (
        d.get("durable")
        or d.get("crystal")
        or d.get("procedure")
        or d.get("mirror")
        or et in ("evolution", "resolve")
    ):
        return False
    return True


def build_offering(
    cube: CubeFile,
    *,
    agent_id: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Distill offerable entries into portable rows with content hashes."""
    entries = list(cube.read_l1() or [])
    rows: list[dict[str, Any]] = []
    for e in entries:
        if not _offerable(e):
            continue
        desc = (e.description or "").strip()
        d = dict(e.data or {})
        # strip bulky / private payload fields
        for k in ("user", "assistant", "tools", "event", "provenance"):
            d.pop(k, None)
        ch = content_hash("offer", e.entry_type, desc)
        rows.append(
            {
                "offer_hash": ch,
                "agent_id": agent_id,
                "src_entry_id": e.id,
                "ts": e.timestamp,
                "type": e.entry_type,
                "outcome": e.outcome,
                "description": desc[:1200],
                "data": {
                    k: v
                    for k, v in d.items()
                    if k
                    in (
                        "trust",
                        "durable",
                        "crystal",
                        "procedure",
                        "source",
                        "entities",
                        "verification",
                        "extension_of",
                    )
                },
            }
        )
        if len(rows) >= limit:
            break
    return rows


def write_offering(
    hive_root: str | Path,
    rows: list[dict[str, Any]],
    *,
    agent_id: str,
) -> dict[str, Any]:
    p = hive_paths(hive_root)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in agent_id)[:64]
    agent_dir = p["offerings"] / safe
    agent_dir.mkdir(parents=True, exist_ok=True)
    # Nanosecond stamp + entropy: several offerings can land in the same
    # second during a single pilgrimage (offer, then interview facts) and
    # must never overwrite each other
    fname = f"offering_{time.time_ns()}_{os.urandom(3).hex()}.jsonl.gz"
    path = agent_dir / fname
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    manifest = {
        "agent_id": agent_id,
        "rows": len(rows),
        "path": str(path),
        "sha": content_hash("offering", agent_id, [r["offer_hash"] for r in rows]),
        "ts": time.time(),
    }
    (agent_dir / (fname + ".manifest.json")).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    _ledger_write(hive_root, {"action": "offer", **manifest})
    return manifest


# ── Assimilate (hive-side merge) ─────────────────────────────────────


def _hive_seen_hashes(hive_cube: CubeFile) -> set[str]:
    seen: set[str] = set()
    for e in hive_cube.read_l1() or []:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        h = d.get("offer_hash") or d.get("content_hash")
        if h:
            seen.add(str(h))
    return seen


def assimilate_offerings(hive_root: str | Path) -> dict[str, Any]:
    """Merge pending offerings into the hive cube (dedup + threat scan)."""
    p = hive_paths(hive_root)
    if not p["cube"].is_file():
        init_hive(hive_root)
    stats = {"files": 0, "rows": 0, "merged": 0, "dupes": 0, "blocked": 0}
    with CubeFile.open(str(p["cube"])) as hive_cube:
        seen = _hive_seen_hashes(hive_cube)
        for agent_dir in sorted(p["offerings"].iterdir()) if p["offerings"].is_dir() else []:
            if not agent_dir.is_dir():
                continue
            for f in sorted(agent_dir.glob("offering_*.jsonl.gz")):
                stats["files"] += 1
                try:
                    with gzip.open(f, "rt", encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if not line:
                                continue
                            stats["rows"] += 1
                            row = json.loads(line)
                            ch = str(row.get("offer_hash") or "")
                            if not ch or ch in seen:
                                stats["dupes"] += 1
                                continue
                            desc = sanitize_for_storage(
                                str(row.get("description") or ""), 1200
                            )
                            if any(
                                t.severity == "block" for t in scan_text(desc)
                            ):
                                stats["blocked"] += 1
                                continue
                            agent = str(row.get("agent_id") or "unknown")
                            ev = make_event(
                                "hive_offer",
                                session_id="",
                                platform="hive",
                                agent_identity=agent,
                                actor="agent",
                                source="hive_assimilate",
                                branch_id=f"hive:{agent}",
                                confidence=float(
                                    (row.get("data") or {}).get("trust") or 0.6
                                ),
                                verification=DRAW_VERIFICATION,
                                payload={
                                    "src_entry_id": row.get("src_entry_id"),
                                    "src_ts": row.get("ts"),
                                },
                            )
                            data = event_to_entry_data(
                                ev,
                                offer_hash=ch,
                                from_agent=agent,
                                durable=True,
                                **{
                                    k: v
                                    for k, v in (row.get("data") or {}).items()
                                    if k in ("crystal", "procedure", "entities")
                                },
                            )
                            hive_cube.append(
                                entry_type=str(row.get("type") or "belief"),
                                description=desc,
                                data=data,
                                outcome=str(row.get("outcome") or "none"),
                            )
                            seen.add(ch)
                            stats["merged"] += 1
                    # archive processed offering
                    done = f.with_suffix(f.suffix + ".done")
                    os.replace(f, done)
                except Exception as e:
                    logger.warning("assimilate failed for %s: %s", f, e)
    _ledger_write(hive_root, {"action": "assimilate", **stats})
    return stats


# ── Draw (hive → agent) ──────────────────────────────────────────────


def draw_wisdom(
    hive_root: str | Path,
    agent_cube: CubeFile,
    *,
    agent_id: str,
    focus: str = "",
    limit: int = 12,
) -> dict[str, Any]:
    """Pull relevant collective entries into the agent's cube (quarantined).

    Drawn entries carry branch ``hive:collective`` + verification
    ``hive_shared`` — evidence packets rank user_authored/tool_verified above
    them, and they never overwrite local claims.
    """
    p = hive_paths(hive_root)
    if not p["cube"].is_file():
        return {"ok": False, "error": "hive cube missing"}

    # local dedup set
    local_seen: set[str] = set()
    for e in agent_cube.read_l1() or []:
        d = e.data if isinstance(getattr(e, "data", None), dict) else {}
        h = d.get("offer_hash")
        if h:
            local_seen.add(str(h))

    drawn = 0
    skipped_own = 0
    drawn_lessons: list[str] = []
    with CubeFile.open(str(p["cube"])) as hive_cube:
        candidates: list[tuple[Any, float]]
        if focus.strip():
            from hermescube.har import HARQueryEngine

            engine = HARQueryEngine(hive_cube)
            candidates = engine.query(focus, top_k=limit * 3)
        else:
            ents = list(hive_cube.read_l1() or [])
            ents.sort(key=lambda e: getattr(e, "timestamp", "") or "", reverse=True)
            candidates = [(e, 0.0) for e in ents[: limit * 3]]

        for entry, _score in candidates:
            if drawn >= limit:
                break
            d = entry.data if isinstance(getattr(entry, "data", None), dict) else {}
            ch = str(d.get("offer_hash") or "")
            if not ch or ch in local_seen:
                continue
            if str(d.get("from_agent") or "") == agent_id:
                skipped_own += 1
                continue
            desc = (entry.description or "").strip()
            if not desc:
                continue
            # Echo guard: never re-absorb your own interviewed knowledge
            if f"[INTERVIEW:{agent_id}]" in desc:
                skipped_own += 1
                continue
            ev = make_event(
                "hive_draw",
                session_id="",
                platform="hive",
                agent_identity=agent_id,
                actor="agent",
                source="hive_draw",
                branch_id="hive:collective",
                confidence=min(0.6, float(d.get("trust") or 0.5)),
                verification=DRAW_VERIFICATION,
                payload={"from_agent": d.get("from_agent"), "offer_hash": ch},
            )
            # Preserve distillation flags so maturity ranking + skill
            # matching can see crystals/procedures after the draw.
            tagged = f"[HIVE:{d.get('from_agent', '?')}] {desc[:400]}"
            agent_cube.append(
                entry_type=entry.entry_type or "belief",
                description=tagged,
                data=event_to_entry_data(
                    ev,
                    offer_hash=ch,
                    from_agent=d.get("from_agent"),
                    hive_shared=True,
                    durable=True,
                    crystal=bool(d.get("crystal")),
                    procedure=bool(d.get("procedure")),
                    entities=d.get("entities") or [],
                ),
                outcome=entry.outcome or "none",
            )
            local_seen.add(ch)
            drawn += 1
            drawn_lessons.append(tagged)

    _ledger_write(
        hive_root,
        {"action": "draw", "agent_id": agent_id, "drawn": drawn, "focus": focus[:120]},
    )
    return {
        "ok": True,
        "drawn": drawn,
        "skipped_own": skipped_own,
        "lessons": drawn_lessons,
    }


# ── Pilgrimage (full nightly cycle) ─────────────────────────────────


def pilgrimage(
    hive_root: str | Path,
    *,
    hermes_home: str | Path,
    agent_id: str,
    focus: str = "",
    offer_limit: int = 200,
    draw_limit: int = 12,
    interview: bool = False,
    interview_peers: int = 1,
) -> dict[str, Any]:
    """Full cycle: offer → assimilate → draw → optional peer interview.

    Intended to run at a quiet hour (Hermes cron or hive host cron):
    every agent goes to the hive at the end of the night and uploads what
    it learned, then returns with what the collective knows. When
    ``interview=True``, the agent also interviews peer souls (interview-me
    protocol) and may mint consent-gated skill drafts from the briefs.
    """
    if not is_hive(hive_root):
        init_hive(hive_root)
    home = Path(hermes_home)
    cube_path = home / "memories" / "memory.cube"
    if not cube_path.is_file():
        return {"ok": False, "error": f"agent cube missing: {cube_path}"}

    report: dict[str, Any] = {"ok": True, "agent_id": agent_id, "hive": str(hive_root)}
    with CubeFile.open(str(cube_path)) as cube:
        # 1. OFFER
        rows = build_offering(cube, agent_id=agent_id, limit=offer_limit)
        if rows:
            report["offer"] = write_offering(hive_root, rows, agent_id=agent_id)
        else:
            report["offer"] = {"rows": 0}

        # 2. PEER INTERVIEW (optional — interview-me at the hive).
        # Runs BEFORE assimilate so interview-distilled facts (persisted
        # as offerings) join the collective in this same visit.
        if interview:
            try:
                report["interviews"] = _pilgrimage_interviews(
                    hive_root,
                    interviewer=agent_id,
                    hermes_home=home,
                    focus=focus,
                    peers=interview_peers,
                )
            except Exception as e:
                report["interviews"] = {"error": str(e)}

        # 3. ASSIMILATE (all pending offerings — including interview facts)
        report["assimilate"] = assimilate_offerings(hive_root)

        # 4. DRAW
        report["draw"] = draw_wisdom(
            hive_root, cube, agent_id=agent_id, focus=focus, limit=draw_limit
        )

        # 5. GROWTH — pilgrimage experience advances the living cube version
        try:
            from hermescube.genealogy import tick_session

            drew = int((report.get("draw") or {}).get("drawn") or 0)
            ivs = report.get("interviews") or []
            interviewed = (
                sum(1 for x in ivs if isinstance(x, dict) and x.get("ok"))
                if isinstance(ivs, list)
                else 0
            )
            offered = int((report.get("offer") or {}).get("rows") or 0)
            report["growth"] = tick_session(
                home,
                cube=cube,
                durable_writes=offered,
                drew=drew,
                interviewed=interviewed,
            )
        except Exception as e:
            report["growth"] = {"error": str(e)}

        # 6. CURATOR — drawn lessons refine skills; era milestones forge/garden
        try:
            from hermescube.curator import run_curator

            lessons = list((report.get("draw") or {}).get("lessons") or [])
            # Interview briefs also leave distillable facts as lessons
            for ivr in report.get("interviews") or []:
                if isinstance(ivr, dict) and ivr.get("ok"):
                    topic = ivr.get("outcome") or ""
                    if ivr.get("session_id"):
                        lessons.append(
                            f"peer interview on craft: {topic} "
                            f"session {ivr.get('session_id')}"
                        )
            growth = report.get("growth") or {}
            report["curator"] = run_curator(
                home,
                cube=cube,
                lessons=lessons,
                era_milestone=bool(
                    growth.get("bumped") and growth.get("bump") == "major"
                ),
            )
        except Exception as e:
            report["curator"] = {"error": str(e)}

        # 7. SOUL CARD — published LAST so peers see post-growth living
        # version, strength, and skills refined during this visit.
        try:
            card = build_soul_card(
                list(cube.read_l1() or []), agent_id=agent_id, hermes_home=home
            )
            publish_soul_card(hive_root, card)
            report["soul_card"] = True
            report["soul_growth"] = card.get("growth")
        except Exception as e:
            report["soul_card"] = f"failed: {e}"

    _ledger_write(hive_root, {"action": "pilgrimage", "agent_id": agent_id})
    return report


def _pilgrimage_interviews(
    hive_root: str | Path,
    *,
    interviewer: str,
    hermes_home: Path,
    focus: str,
    peers: int,
) -> list[dict[str, Any]]:
    """Interview up to ``peers`` other souls present in the hive."""
    from hermescube.interview import peer_dialogue

    souls = [
        s for s in list_souls(hive_root)
        if s.get("agent_id") and s.get("agent_id") != interviewer
    ]
    # Prefer souls whose missions/wisdom overlap the focus
    focus_l = (focus or "").lower()

    def score(s: dict[str, Any]) -> int:
        soul = s.get("soul") or {}
        blob = " ".join(
            str(x)
            for k in ("wisdom", "missions", "procedures", "beliefs")
            for x in (soul.get(k) or [])
        ).lower()
        return sum(1 for t in focus_l.split() if t and t in blob) if focus_l else 1

    souls.sort(key=score, reverse=True)
    results = []
    topic = focus.strip() or "shared craft and lessons learned"
    for s in souls[: max(0, peers)]:
        results.append(
            peer_dialogue(
                hive_root,
                interviewer=interviewer,
                subject=str(s["agent_id"]),
                topic=topic,
                mode="discover",
                hermes_home=hermes_home,
                persist=True,
                mint=True,
            )
        )
    return results


def hive_status(hive_root: str | Path) -> dict[str, Any]:
    p = hive_paths(hive_root)
    if not is_hive(hive_root):
        return {"ok": False, "error": "not a hive (missing hive.json)"}
    meta = json.loads(p["marker"].read_text(encoding="utf-8"))
    n_entries = 0
    if p["cube"].is_file():
        try:
            with CubeFile.open(str(p["cube"])) as c:
                n_entries = c.entry_count
        except Exception:
            n_entries = -1
    souls = list_souls(hive_root)
    pending = 0
    if p["offerings"].is_dir():
        pending = sum(
            1
            for d in p["offerings"].iterdir()
            if d.is_dir()
            for _ in d.glob("offering_*.jsonl.gz")
        )
    status: dict[str, Any] = {
        "ok": True,
        "name": meta.get("name"),
        "root": str(p["root"]),
        "collective_entries": n_entries,
        "agents": [s.get("agent_id") for s in souls],
        "souls": len(souls),
        "pending_offerings": pending,
    }
    # One nexus, one status: fold in HQ + interview surfaces when present
    try:
        from hermescube.hq import list_charters, list_handoffs

        charters = list_charters(hive_root)
        status["charters"] = len(charters)
        status["command"] = next(
            (c["agent_id"] for c in charters if c.get("role") == "command"), None
        )
        status["pending_handoffs"] = len(list_handoffs(hive_root, status="pending"))
    except Exception:
        pass
    try:
        from hermescube.interview import list_interviews

        status["interviews"] = len(list_interviews(hive_root, limit=1000))
    except Exception:
        pass
    return status
