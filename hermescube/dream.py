"""CubeDream L1 — soul dream scheduler + solo structure packaging.

Deterministic half of dreaming (OMH-style): due reasons + state.
Solo apply packages existing sleep_replay / crystalize as gated warehouse work.
Circle (L2) lives in ``dream_circle.py``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SCHEMA = "hermescube_dreaming_state/v1"
CLAIM_BOUNDARY = (
    "A dream handoff or diary entry is prepared context — not evidence that "
    "MEMORY.md or the hive changed unless that write was observed."
)

DREAM_MODES = frozenset({"off", "reminder", "auto-soul", "auto-circle"})
DEFAULT_TURN_INTERVAL = 8
_EVENT_REASONS = frozenset(
    {
        "turn_interval_reached",
        "session_ending_with_undreamed_turns",
        "context_compaction_observed",
        "manual",
    }
)


def dreams_dir(hermes_home: str | Path, **path_kw: Any) -> Path:
    from hermescube.framework.paths import resolve_cube_paths

    paths = resolve_cube_paths(hermes_home, **path_kw)
    d = paths.sidecar_dir / "dreams"
    d.mkdir(parents=True, exist_ok=True)
    return d


def dreaming_state_path(hermes_home: str | Path, **path_kw: Any) -> Path:
    return dreams_dir(hermes_home, **path_kw) / "dreaming.json"


def diary_path(hermes_home: str | Path, **path_kw: Any) -> Path:
    return dreams_dir(hermes_home, **path_kw) / "DREAMS.md"


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "turns_since_dream": 0,
        "compaction_pending": False,
        "last_dream_at": "",
        "last_reasons": [],
        "last_run_id": "",
        "mode": "reminder",
    }


def read_state(hermes_home: str | Path, **path_kw: Any) -> dict[str, Any]:
    path = dreaming_state_path(hermes_home, **path_kw)
    try:
        if not path.is_file():
            return empty_state()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA:
            return empty_state()
        state = empty_state()
        state["turns_since_dream"] = max(0, int(data.get("turns_since_dream") or 0))
        state["compaction_pending"] = bool(data.get("compaction_pending"))
        state["last_dream_at"] = str(data.get("last_dream_at") or "")
        state["last_reasons"] = [
            str(r) for r in (data.get("last_reasons") or []) if isinstance(r, str)
        ]
        state["last_run_id"] = str(data.get("last_run_id") or "")
        mode = str(data.get("mode") or "reminder").strip().lower()
        state["mode"] = mode if mode in DREAM_MODES else "reminder"
        return state
    except Exception:
        return empty_state()


def write_state(
    hermes_home: str | Path, state: dict[str, Any], **path_kw: Any
) -> Path:
    path = dreaming_state_path(hermes_home, **path_kw)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    return path


def record_turn(state: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["turns_since_dream"] = int(out.get("turns_since_dream") or 0) + 1
    return out


def record_compaction(state: dict[str, Any]) -> dict[str, Any]:
    out = dict(state)
    out["compaction_pending"] = True
    return out


def clear_after_dream(
    state: dict[str, Any], *, run_id: str, reasons: list[str]
) -> dict[str, Any]:
    out = dict(state)
    out["turns_since_dream"] = 0
    out["compaction_pending"] = False
    out["last_dream_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out["last_reasons"] = list(reasons)
    out["last_run_id"] = run_id
    return out


def normalize_mode(value: str | None) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in DREAM_MODES else "reminder"


def due_reasons(
    state: dict[str, Any],
    *,
    turn_interval: int = DEFAULT_TURN_INTERVAL,
    session_ending: bool = False,
    candidate_pending: int = 0,
    engram_stale: bool = False,
    hive_offerings_pending: int = 0,
    suppress: bool = True,
) -> list[str]:
    """Why a soul dream is due, or empty when not."""
    if normalize_mode(str(state.get("mode") or "")) == "off":
        return []
    reasons: list[str] = []
    interval = turn_interval if turn_interval > 0 else DEFAULT_TURN_INTERVAL
    turns = int(state.get("turns_since_dream") or 0)
    if turns >= interval:
        reasons.append(f"turn_interval_reached:{turns}/{interval}")
    elif session_ending and turns > 0:
        reasons.append(f"session_ending_with_undreamed_turns:{turns}")
    if state.get("compaction_pending"):
        reasons.append("context_compaction_observed")
    if candidate_pending > 0:
        reasons.append(f"candidate_backlog_high:{candidate_pending}")
    if engram_stale:
        reasons.append("engram_stale")
    if hive_offerings_pending > 0:
        reasons.append(f"hive_offerings_pending:{hive_offerings_pending}")
    if not suppress:
        return reasons
    already = {str(r) for r in (state.get("last_reasons") or [])}
    fresh = any(
        r.split(":", 1)[0] in _EVENT_REASONS or r not in already for r in reasons
    )
    return reasons if fresh else []


def append_diary(
    hermes_home: str | Path,
    text: str,
    **path_kw: Any,
) -> Path:
    path = diary_path(hermes_home, **path_kw)
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    header = ""
    if not path.is_file() or path.stat().st_size == 0:
        header = "# CubeDream diary (soul)\n\n"
    block = f"{header}## {stamp}\n\n{text.rstrip()}\n\n_{CLAIM_BOUNDARY}_\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(block)
    return path


def dream_status(
    hermes_home: str | Path,
    *,
    turn_interval: int = DEFAULT_TURN_INTERVAL,
    candidate_pending: int = 0,
    **path_kw: Any,
) -> dict[str, Any]:
    state = read_state(hermes_home, **path_kw)
    reasons = due_reasons(
        state,
        turn_interval=turn_interval,
        candidate_pending=candidate_pending,
    )
    ddir = dreams_dir(hermes_home, **path_kw)
    return {
        "ok": True,
        "layer": "L1_soul",
        "mode": state.get("mode"),
        "due": bool(reasons),
        "reasons": reasons,
        "state": state,
        "dreams_dir": str(ddir),
        "diary": str(diary_path(hermes_home, **path_kw)),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def run_solo_dream(
    cube: Any,
    hermes_home: str | Path,
    *,
    engram: Any = None,
    apply: bool = False,
    dry_crystalize: bool = True,
    reasons: list[str] | None = None,
    turn_interval: int = DEFAULT_TURN_INTERVAL,
    **path_kw: Any,
) -> dict[str, Any]:
    """L1 solo dream: diary + optional sleep_replay / crystalize.

    ``apply=False`` (default): stage report only — no warehouse mutate.
    ``apply=True``: run structure commits (still never touches MEMORY.md).
    """
    import uuid

    run_id = f"soul_{uuid.uuid4().hex[:10]}"
    state = read_state(hermes_home, **path_kw)
    why = list(reasons or due_reasons(state, turn_interval=turn_interval) or ["manual"])
    report: dict[str, Any] = {
        "ok": True,
        "layer": "L1_soul",
        "run_id": run_id,
        "reasons": why,
        "applied": False,
        "claim_boundary": CLAIM_BOUNDARY,
    }

    entries = []
    if cube is not None:
        try:
            entries = list(cube.read_l1() or [])
        except Exception:
            entries = []
    report["entries_scanned"] = len(entries)

    if apply and cube is not None:
        from hermescube.consolidate import snapshot_sidecars
        from hermescube.sleep_replay import sleep_replay
        from hermescube.wisdom import crystalize

        snap = snapshot_sidecars(hermes_home, label=f"dream_{run_id}")
        report["snapshot"] = snap.get("branch")
        if engram is not None:
            report["sleep_replay"] = sleep_replay(
                cube, engram, max_patterns=16, entries=entries
            )
            try:
                engram.save()
            except Exception:
                pass
        report["crystalize"] = crystalize(cube, dry_run=bool(dry_crystalize))
        report["applied"] = True
        report["crystalize_dry_run"] = bool(dry_crystalize)

    diary_text = (
        f"**Soul dream** `{run_id}`\n\n"
        f"- reasons: {', '.join(why)}\n"
        f"- entries scanned: {report['entries_scanned']}\n"
        f"- applied: {report['applied']}"
        + (
            f"\n- crystalize: {report.get('crystalize')}"
            if report.get("crystalize")
            else ""
        )
        + (
            f"\n- sleep_replay: {report.get('sleep_replay')}"
            if report.get("sleep_replay")
            else ""
        )
    )
    report["diary"] = str(append_diary(hermes_home, diary_text, **path_kw))
    write_state(
        hermes_home,
        clear_after_dream(state, run_id=run_id, reasons=why),
        **path_kw,
    )
    return report


def reminder_strip(
    hermes_home: str | Path,
    *,
    turn_interval: int = DEFAULT_TURN_INTERVAL,
    candidate_pending: int = 0,
    **path_kw: Any,
) -> str:
    """Short system-prompt strip when a dream is due (reminder mode)."""
    st = dream_status(
        hermes_home,
        turn_interval=turn_interval,
        candidate_pending=candidate_pending,
        **path_kw,
    )
    if not st.get("due"):
        return ""
    reasons = ", ".join(st.get("reasons") or [])
    return (
        f"## CubeDream due\n"
        f"Soul dream is due ({reasons}). "
        f"Run `hermescube_manage action=dream mode=solo` "
        f"(or `mode=solo:apply` for warehouse structure commits). "
        f"For fleet togetherness: open/join a hive dream circle.\n"
        f"_{CLAIM_BOUNDARY}_\n"
    )
