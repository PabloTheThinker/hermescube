"""Inspire cycle — blackbox × heart × relations (not the same old append loop).

Coding idea: *evidence-oriented programming*.
  A run is not done until a FlightRecord exists and standing claims are proven.
  Proven evidence becomes Cube blood (landmarks/beliefs) + SPO relations.
  Empty relation graph is treated as hypoxia — backfill from the warehouse.

This module is the pulmonary circuit of the anatomical center:
  inhale  = capture trajectory + scan warehouse gaps
  gas exchange = prove claims + extract SPO
  exhale  = seal learnings + write relations + breath note
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from hermescube.blackbox.capture import capture_session, save_record
from hermescube.blackbox.flight import verify_integrity
from hermescube.blackbox.prove import prove_claim, prove_many
from hermescube.claims import infer_spo_from_text

# Standing claim pack — house-level "is the organism alive?" probes
DEFAULT_CLAIM_PACK: list[str] = [
    "hermescube",
    "memory",
    "skill",
]


def _hermes_home(home: str | None) -> Path:
    import os

    return Path(home or os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def inhale(
    *,
    hermes_home: str | None = None,
    session_id: str | None = None,
    latest: bool = True,
    redact: bool = True,
    max_events: int | None = 400,
) -> dict[str, Any]:
    """Inhale — pull a redacted flight record from Hermes lungs (state.db)."""
    home = _hermes_home(hermes_home)
    t0 = time.perf_counter()
    rec = capture_session(
        session_id=session_id,
        latest=latest if not session_id else False,
        db_path=home / "state.db",
        redact=redact,
        max_events=max_events,
    )
    path = home / "memories" / "blackbox" / f"{rec.id}.json"
    save_record(rec, path)
    return {
        "ok": True,
        "phase": "inhale",
        "record_id": rec.id,
        "path": str(path),
        "events": len(rec.events),
        "redactions": rec.redactions_count,
        "integrity_ok": verify_integrity(rec),
        "session_id": (rec.session or {}).get("id"),
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        "record": rec,
    }


def gas_exchange(
    record: Any,
    *,
    claims: list[str] | None = None,
) -> dict[str, Any]:
    """Gas exchange — prove standing claims against the inhaled trajectory."""
    pack = claims or list(DEFAULT_CLAIM_PACK)
    results = prove_many(record, pack)
    return {
        "ok": True,
        "phase": "gas_exchange",
        "claims": [r.to_dict() for r in results],
        "pass_n": sum(1 for r in results if r.verdict == "pass"),
        "fail_n": sum(1 for r in results if r.verdict == "fail"),
        "inconclusive_n": sum(1 for r in results if r.verdict == "inconclusive"),
    }


def _backfill_relations(hermes_home: Path, *, limit: int = 120) -> dict[str, Any]:
    """Hypoxia fix — relations store empty → seed from durable cube L1 entries."""
    from hermescube.cube import CubeFile
    from hermescube.relations import RelationStore, ingest_entry

    cube_path = hermes_home / "memories" / "memory.cube"
    if not cube_path.exists():
        return {"ok": False, "error": "no cube", "ingested": 0}

    store = RelationStore(str(hermes_home))
    before = store.stats()
    n = 0
    scanned = 0
    try:
        cube = CubeFile.open(str(cube_path))
        entries = cube.read_l1()
        # prefer relationship/belief/trait densest tail
        preferred = [
            e
            for e in entries
            if (getattr(e, "entry_type", "") or "").lower()
            in ("relationship", "belief", "resolve", "trait", "landmark")
        ]
        batch = preferred[-limit:] if preferred else entries[-limit:]
        scanned = len(batch)
        for e in batch:
            try:
                n += len(ingest_entry(e, store))
            except Exception:
                continue
    except Exception as e:
        return {"ok": False, "error": str(e), "ingested": 0}

    after = store.stats()
    return {
        "ok": True,
        "ingested_links": n,
        "before": before,
        "after": after,
        "scanned": scanned,
    }


def exhale(
    inhale_report: dict[str, Any],
    exchange_report: dict[str, Any],
    *,
    hermes_home: str | None = None,
    seal: bool = True,
    relations: bool = True,
) -> dict[str, Any]:
    """Exhale — seal evidence into the heart; grow the relation graph."""
    from hermescube import space_bridge

    home = _hermes_home(hermes_home)
    sealed: list[dict[str, Any]] = []
    rel_report: dict[str, Any] = {"ok": False, "skipped": True}

    if seal:
        rid = inhale_report.get("record_id")
        sid = inhale_report.get("session_id")
        path = inhale_report.get("path")
        lines = [
            f"Blackbox breath: flight {rid} session {sid} events={inhale_report.get('events')} "
            f"integrity={inhale_report.get('integrity_ok')} path={path}",
        ]
        for c in exchange_report.get("claims") or []:
            lines.append(
                f"Claim [{c.get('verdict')}] conf={c.get('confidence')}: {c.get('claim')}"
            )
        for text in lines:
            sealed.append(
                space_bridge.seal_learning(
                    text,
                    entry_type="landmark" if text.startswith("Blackbox") else "belief",
                    hermes_home=str(home),
                    source="blackbox_breathe",
                    trust=0.72,
                )
            )
        # SPO from pass claims into free-text seals
        for c in exchange_report.get("claims") or []:
            if c.get("verdict") != "pass":
                continue
            spo = infer_spo_from_text(str(c.get("claim") or ""))
            if spo:
                s, p, o = spo
                sealed.append(
                    space_bridge.seal_learning(
                        f"{s} {p} {o} (from flight claim)",
                        entry_type="relationship",
                        hermes_home=str(home),
                        source="blackbox_spo",
                        trust=0.65,
                    )
                )

    if relations:
        # Two-stage hypoxia fix: SPO ingest + living connect_dots graph weave
        rel_report = _backfill_relations(home)
        try:
            from hermescube import living
            from hermescube.cube import CubeFile

            cube = CubeFile.open(str(home / "memories" / "memory.cube"))
            entries = cube.read_l1()
            dots = living.connect_dots(
                cube, entries, hermes_home=str(home), max_links=25
            )
            rel_report["connect_dots"] = dots
            from hermescube.relations import RelationStore

            rel_report["after"] = RelationStore(str(home)).stats()
        except Exception as e:
            rel_report["connect_dots_error"] = str(e)

    breath_note = {
        "ts": time.time(),
        "record_id": inhale_report.get("record_id"),
        "pass_n": exchange_report.get("pass_n"),
        "fail_n": exchange_report.get("fail_n"),
        "relations_after": (rel_report.get("after") or {}),
    }
    note_path = home / "memories" / "blackbox" / "last_breath.json"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    note_path.write_text(json.dumps(breath_note, indent=2, default=str) + "\n")

    return {
        "ok": True,
        "phase": "exhale",
        "sealed": sealed,
        "sealed_ok": sum(1 for s in sealed if s.get("ok")),
        "relations": rel_report,
        "breath_note": str(note_path),
    }


def breathe(
    *,
    hermes_home: str | None = None,
    session_id: str | None = None,
    latest: bool = True,
    claims: list[str] | None = None,
    seal: bool = True,
    relations: bool = True,
    redact: bool = True,
) -> dict[str, Any]:
    """One full respiratory cycle for the Cube organism.

    Novel loop (not plain append):
      inhale → gas_exchange → exhale(+relation hypoxia fix)
    """
    t0 = time.perf_counter()
    out: dict[str, Any] = {
        "ok": False,
        "cycle": "breathe",
        "idea": "evidence-oriented programming / pulmonary center",
        "phases": {},
    }
    try:
        inn = inhale(
            hermes_home=hermes_home,
            session_id=session_id,
            latest=latest,
            redact=redact,
        )
        rec = inn.pop("record", None)
        out["phases"]["inhale"] = {k: v for k, v in inn.items()}
        if rec is None:
            out["error"] = "no record"
            return out
        ex = gas_exchange(rec, claims=claims)
        out["phases"]["gas_exchange"] = ex
        out["phases"]["exhale"] = exhale(
            inn, ex, hermes_home=hermes_home, seal=seal, relations=relations
        )
        out["ok"] = bool(inn.get("ok")) and bool(ex.get("ok"))
        # unified hold-the-line seal for whole Cube breath
        try:
            from hermescube.blackbox.hold_line import record as hold_record
            from hermescube.security import resolve_hermes_home

            home = resolve_hermes_home(hermes_home)
            out["hold_line"] = hold_record(
                hermes_home=home,
                organ="breathe",
                event="cycle",
                summary=f"breathe ok={out['ok']} claims_pass={(ex.get('passed') if isinstance(ex, dict) else None)}",
                payload={
                    "ok": out.get("ok"),
                    "inhale": {k: inn.get(k) for k in ("ok", "record_id", "events", "path") if k in inn},
                    "gas_exchange": {
                        k: ex.get(k)
                        for k in ("ok", "passed", "failed", "total")
                        if isinstance(ex, dict) and k in ex
                    },
                },
                session_id=session_id or "",
                severity="high",
            )
        except Exception as e:
            out["hold_line"] = {"ok": False, "error": str(e)}
    except Exception as e:
        out["error"] = str(e)
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return out
