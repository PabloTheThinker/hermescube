"""Anatomical center — circulatory integration of Cube (heart) + Hermespace (nervous FOA).

Research merged into this module (functional analogues, not biophysics):

**Nous Hermes Agent (coding methods)**
  - One external MemoryProvider + always-on MEMORY.md
  - Soft-fail hooks; profile-scoped ``hermes_home``
  - Prefetch caps (holographic top-5); asymmetric trust feedback
  - Lifecycle: initialize → sync_turn → prefetch → session_end → mirror writes

**Hermespace (pocket nervous system)**
  - Baddeley WM modalities + Cowan FOA ≤4 + GWT broadcast
  - Sweller load (I/E/G) → monotropic protect under high load
  - Pulse runtime = autonomic rhythm (idle_tick / world_evolve / dream)
  - Dual decode: short human report vs dense model context

**Comparative anatomy → Cube organs**
  - Heart / blood       → ``.cube`` SoT + inject strips (arterial supply)
  - Veins / return      → ``seal_learning`` (desk decisions → archive)
  - Autonomic pulse     → ``pulse_charge`` / ``autonomic_tick``
  - Hippocampus         → L1 encode + evolve / CubeDream consolidate
  - PFC / FOA           → Hermespace desk (Space owns; Cube supplies)
  - Immune              → threat scan + Cuboasis memory_gate
  - Lymph / collective  → Hive pilgrimage
  - Vascular beds       → Cuboasis chambers / vaults
  - Elephant maps       → bio_rank long half-lives (trait/relationship)
  - Dolphin USWS        → dream/idle while other systems stay online

``CENTER_API_VERSION`` extends the heart contract. Hermespace should soft-import
``hermescube.center`` (or ``space_bridge`` for 1.0 heart-only).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable

from hermescube import space_bridge
from hermescube.space_bridge import GENERATOR_API_VERSION

logger = logging.getLogger(__name__)

# Additive within 1.x — Space feature-detects via center_status()["api_version"].
CENTER_API_VERSION = "1.2"

# Sweller-style load → arterial strip budget (chars). Matches Hermespace cognition levels.
LOAD_STRIP_CHARS: dict[str, int] = {
    "low": space_bridge.DEFAULT_NORMAL_CHARS,  # 900
    "mid": 640,
    "high": space_bridge.DEFAULT_HIGH_LOAD_CHARS,  # 420
    "protect": 280,  # monotropic — densest blood only
}

# Organ map for doctor / desktop (stable keys).
ANATOMY: dict[str, dict[str, str]] = {
    "heart": {
        "organ": "HermesCube .cube archive",
        "job": "Durable pump / SoT — long-tail memory",
        "api": "ensure_heart · heart_status · seal_learning",
    },
    "arteries": {
        "organ": "Inject strip (diastole supply)",
        "job": "Dense FOA blood to Hermespace desk under load",
        "api": "build_space_inject · center.supply",
    },
    "veins": {
        "organ": "Seal return (systole intake)",
        "job": "Desk decisions / learnings → durable archive",
        "api": "seal_learning · center.return_flow",
    },
    "autonomic": {
        "organ": "Pulse / idle rhythm",
        "job": "Charge WorldModel + journey while Space idle",
        "api": "pulse_charge · center.autonomic_tick",
    },
    "nervous_foa": {
        "organ": "Hermespace desk (PFC analogue)",
        "job": "FOA ≤4, dual decode, GWT broadcast — owned by Space",
        "api": "hermespace Workbench / hermes_bridge",
    },
    "hippocampus": {
        "organ": "Encode + consolidate",
        "job": "L1 WAL append, evolve, CubeDream solo/circle",
        "api": "CubeMemoryProvider · dream",
    },
    "immune": {
        "organ": "Threat + governance",
        "job": "Injection block, Cuboasis candidates / evidence states",
        "api": "threats · memory_gate",
    },
    "lymph": {
        "organ": "Hive collective",
        "job": "Pilgrimage offer → assimilate → draw",
        "api": "hive",
    },
    "vascular_beds": {
        "organ": "Cuboasis chambers",
        "job": "Local tissue rooms without forking stores",
        "api": "cuboasis space/connect/progress",
    },
    "blackbox": {
        "organ": "Flight recorder (inner core)",
        "job": "Capture redacted trajectories · integrity hash · prove claims — agents show the work",
        "api": "blackbox.capture_session · prove_claim · center.flight_capture · center.flight_prove",
    },
    "ark": {
        "organ": "Safe-lock checkpoints (identity arc)",
        "job": "Flash clone of cube book + SOUL/MEMORY/USER — restore after fresh restart or corruption",
        "api": "checkpoint.create_checkpoint · restore_checkpoint · hermescube checkpoint",
    },
}


def _normalize_load(load: str | float | None, *, high_load: bool = False) -> str:
    if high_load:
        return "high"
    if load is None:
        return "mid"
    if isinstance(load, (int, float)):
        v = float(load)
        if v >= 0.85:
            return "protect"
        if v >= 0.65:
            return "high"
        if v >= 0.35:
            return "mid"
        return "low"
    s = str(load).strip().lower()
    if s in LOAD_STRIP_CHARS:
        return s
    if s in ("protected", "mono", "monotropic"):
        return "protect"
    return "mid"


def strip_budget(load: str | float | None = None, *, high_load: bool = False) -> int:
    """Arterial char budget from Sweller-style load (Hermespace cognition)."""
    return LOAD_STRIP_CHARS[_normalize_load(load, high_load=high_load)]


def center_status(hermes_home: str | None = None) -> dict[str, Any]:
    """Full center readiness — heart plus organ map for Space doctor."""
    heart = space_bridge.heart_status(hermes_home=hermes_home)
    organs: dict[str, Any] = {}
    for key, meta in ANATOMY.items():
        organs[key] = {
            **meta,
            "ready": bool(heart.get("heart_ready")) if key != "nervous_foa" else None,
        }
    # nervous_foa is Space-owned — report unknown from Cube side
    organs["nervous_foa"]["ready"] = None
    organs["nervous_foa"]["note"] = "owned_by_hermespace"

    return {
        "api_version": CENTER_API_VERSION,
        "heart_api_version": GENERATOR_API_VERSION,
        "role": "center",
        "heart": heart,
        "organs": organs,
        "load_strip_chars": dict(LOAD_STRIP_CHARS),
        "nous_methods": [
            "one_external_MemoryProvider",
            "soft_fail_hooks",
            "prefetch_caps",
            "asymmetric_trust_feedback",
            "builtin_MEMORY_md_coexistence",
        ],
        "space_methods": [
            "cowan_foa_cap",
            "baddeley_modalities",
            "gwt_broadcast",
            "sweller_load_protect",
            "pulse_autonomic_rhythm",
        ],
        "ok": bool(heart.get("heart_ready")),
    }


def supply(
    query: str,
    *,
    load: str | float | None = None,
    high_load: bool = False,
    max_chars: int | None = None,
    hermes_home: str | None = None,
    session_id: str = "hermespace",
) -> dict[str, Any]:
    """Diastole — arterial supply: Cube blood → Hermespace FOA strip."""
    level = _normalize_load(load, high_load=high_load)
    cap = max_chars if max_chars is not None else strip_budget(level)
    t0 = time.perf_counter()
    block = space_bridge.build_space_inject(
        query,
        high_load=level in ("high", "protect"),
        max_chars=cap,
        hermes_home=hermes_home,
        session_id=session_id,
    )
    return {
        "ok": bool(block),
        "phase": "diastole",
        "load_level": level,
        "max_chars": cap,
        "chars": len(block or ""),
        "block": block or "",
        "elapsed_ms": round((time.perf_counter() - t0) * 1000, 3),
        "api_version": CENTER_API_VERSION,
    }


def return_flow(
    content: str | Iterable[str],
    *,
    entry_type: str = "belief",
    hermes_home: str | None = None,
    source: str = "hermespace",
    trust: float = 0.75,
    agent_id: str = "",
) -> dict[str, Any]:
    """Systole — venous return: desk learnings → durable Cube."""
    items: list[str]
    if isinstance(content, str):
        items = [content]
    else:
        items = [str(x) for x in content if str(x).strip()]

    sealed: list[dict[str, Any]] = []
    for text in items:
        sealed.append(
            space_bridge.seal_learning(
                text,
                entry_type=entry_type,
                hermes_home=hermes_home,
                source=source,
                trust=trust,
                agent_id=agent_id,
            )
        )
    ok_n = sum(1 for r in sealed if r.get("ok"))
    return {
        "ok": ok_n == len(sealed) and len(sealed) > 0,
        "phase": "systole",
        "sealed": sealed,
        "count": ok_n,
        "api_version": CENTER_API_VERSION,
    }


def autonomic_tick(
    *,
    hermes_home: str | None = None,
    hermespace_home: str | None = None,
    agent_id: str = "hermes-agent",
    ensure: bool = True,
) -> dict[str, Any]:
    """Autonomic rhythm — Space idle/pulse should call this (Nous: soft, idempotent)."""
    report = space_bridge.pulse_charge(
        hermes_home=hermes_home,
        hermespace_home=hermespace_home,
        agent_id=agent_id,
        ensure=ensure,
    )
    report["phase"] = "autonomic"
    report["api_version"] = CENTER_API_VERSION
    report["anatomy"] = "dolphin_usws_style_idle_maintain"
    return report


def beat(
    query: str = "",
    *,
    seals: str | Iterable[str] | None = None,
    entry_type: str = "belief",
    load: str | float | None = None,
    high_load: bool = False,
    hermes_home: str | None = None,
    hermespace_home: str | None = None,
    agent_id: str = "hermes-agent",
    charge: bool = False,
    session_id: str = "hermespace",
) -> dict[str, Any]:
    """One cardiac cycle for a Hermespace turn.

    Order (Nous-safe, soft-fail per phase):
      1. ensure heart exists
      2. systole  — seal desk learnings (optional)
      3. diastole — supply FOA strip sized by Sweller load
      4. autonomic charge (optional — usually idle, not every turn)
    """
    t0 = time.perf_counter()
    out: dict[str, Any] = {
        "api_version": CENTER_API_VERSION,
        "ok": False,
        "phases": {},
    }
    try:
        out["phases"]["ensure"] = space_bridge.ensure_heart(hermes_home=hermes_home)
    except Exception as e:
        out["phases"]["ensure"] = {"ok": False, "error": str(e)}

    if seals is not None:
        try:
            out["phases"]["systole"] = return_flow(
                seals,
                entry_type=entry_type,
                hermes_home=hermes_home,
                agent_id=agent_id,
            )
        except Exception as e:
            out["phases"]["systole"] = {"ok": False, "error": str(e)}

    try:
        out["phases"]["diastole"] = supply(
            query or "",
            load=load,
            high_load=high_load,
            hermes_home=hermes_home,
            session_id=session_id,
        )
    except Exception as e:
        out["phases"]["diastole"] = {"ok": False, "error": str(e), "block": ""}

    if charge:
        try:
            out["phases"]["autonomic"] = autonomic_tick(
                hermes_home=hermes_home,
                hermespace_home=hermespace_home,
                agent_id=agent_id,
                ensure=False,
            )
        except Exception as e:
            out["phases"]["autonomic"] = {"ok": False, "error": str(e)}

    diastole = out["phases"].get("diastole") or {}
    ensure = out["phases"].get("ensure") or {}
    out["block"] = diastole.get("block") or ""
    out["load_level"] = diastole.get("load_level")
    out["ok"] = bool(ensure.get("ok")) and (
        "error" not in (diastole if isinstance(diastole, dict) else {})
        or bool(diastole.get("ok") or diastole.get("block") == "")
    )
    # Prefer: heart ready; empty strip is still a valid beat under cold start
    if ensure.get("ok"):
        out["ok"] = True
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 3)
    return out


def flight_capture(
    session_id: str | None = None,
    *,
    latest: bool = True,
    hermes_home: str | None = None,
    redact: bool = True,
    out_path: str | None = None,
) -> dict[str, Any]:
    """Blackbox organ — capture a Hermes session as a redacted flight record."""
    from pathlib import Path

    from hermescube.blackbox import capture_session, save_record, verify_integrity

    db = None
    if hermes_home:
        db = str(Path(hermes_home) / "state.db")
    try:
        rec = capture_session(
            session_id=session_id,
            latest=latest if not session_id else False,
            db_path=db,
            redact=redact,
        )
    except Exception as e:
        return {"ok": False, "error": str(e), "api_version": CENTER_API_VERSION}

    path = None
    if out_path:
        path = str(save_record(rec, out_path))
    else:
        # default under HERMES_HOME/memories/blackbox/
        home = Path(hermes_home or Path.home() / ".hermes")
        dest = home / "memories" / "blackbox" / f"{rec.id}.json"
        path = str(save_record(rec, dest))

    return {
        "ok": True,
        "organ": "blackbox",
        "record_id": rec.id,
        "session_id": (rec.session or {}).get("id"),
        "events": len(rec.events),
        "redactions": rec.redactions_count,
        "integrity_ok": verify_integrity(rec),
        "path": path,
        "api_version": CENTER_API_VERSION,
    }


def flight_prove(
    claim: str,
    *,
    record_path: str | None = None,
    record: dict | None = None,
    hermes_home: str | None = None,
    session_id: str | None = None,
    latest: bool = True,
) -> dict[str, Any]:
    """Blackbox organ — prove a natural-language claim against a flight record."""
    from hermescube.blackbox import capture_session, load_record, prove_claim, verify_integrity

    try:
        if record is not None:
            rec = record
        elif record_path:
            rec = load_record(record_path)
        else:
            db = None
            if hermes_home:
                from pathlib import Path

                db = str(Path(hermes_home) / "state.db")
            rec = capture_session(
                session_id=session_id,
                latest=latest if not session_id else False,
                db_path=db,
                redact=True,
            )
        result = prove_claim(rec, claim)
        ok_int = verify_integrity(rec)
    except Exception as e:
        return {"ok": False, "error": str(e), "api_version": CENTER_API_VERSION}

    d = result.to_dict()
    exit_hint = {"pass": 0, "fail": 2, "inconclusive": 3}.get(result.verdict, 1)
    return {
        "ok": result.verdict == "pass",
        "organ": "blackbox",
        "integrity_ok": ok_int,
        "exit_code_hint": exit_hint,
        "result": d,
        "api_version": CENTER_API_VERSION,
    }


def breathe(
    *,
    hermes_home: str | None = None,
    session_id: str | None = None,
    latest: bool = True,
    claims: list[str] | None = None,
    seal: bool = True,
    relations: bool = True,
) -> dict[str, Any]:
    """Pulmonary cycle — blackbox × heart × relations (evidence-oriented programming).

    Fills gaps the cardiac ``beat`` alone does not: empty relation graph,
    unproven "done" claims, flight evidence not sealed into the warehouse.
    """
    from hermescube.blackbox.inspire import breathe as _breathe

    report = _breathe(
        hermes_home=hermes_home,
        session_id=session_id,
        latest=latest,
        claims=claims,
        seal=seal,
        relations=relations,
    )
    report["api_version"] = CENTER_API_VERSION
    report["organ"] = "blackbox+heart+relations"
    return report


# Friendly aliases matching anatomy language Space docs can cite.
diastole = supply
systole = return_flow
