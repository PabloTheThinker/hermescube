"""Growth merge — compound when multiple Cube surfaces fire in one session.

Adapted from AgentDrive's multi-axis growth merge (experience + patterns +
skills + memory → one artifact), but Cube-native:

  durable writes · procedure drafts · association (engram/colony) ·
  yield feedback · wisdom crystals

When ≥2 axes are present, append one high-trust ``evolution`` entry with
``data.growth_merge=True`` and evidence ids — instead of leaving the session
as scattered landmarks. No LLM. No AgentDrive imports.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_AXES = ("durable", "procedure", "association", "yield", "wisdom")


@dataclass
class GrowthAxes:
    durable: bool = False
    procedure: bool = False
    association: bool = False
    yield_: bool = False  # "yield" is reserved in some contexts; expose as yield_
    wisdom: bool = False

    def present(self) -> list[str]:
        out: list[str] = []
        if self.durable:
            out.append("durable")
        if self.procedure:
            out.append("procedure")
        if self.association:
            out.append("association")
        if self.yield_:
            out.append("yield")
        if self.wisdom:
            out.append("wisdom")
        return out

    def merge_ready(self) -> bool:
        return len(self.present()) >= 2

    def to_dict(self) -> dict[str, bool]:
        return {
            "durable": self.durable,
            "procedure": self.procedure,
            "association": self.association,
            "yield": self.yield_,
            "wisdom": self.wisdom,
        }


@dataclass
class GrowthMergeResult:
    merged: bool
    axes: GrowthAxes
    entry_id: str = ""
    description: str = ""
    evidence_ids: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "merged": self.merged,
            "axes": self.axes.to_dict(),
            "present": self.axes.present(),
            "entry_id": self.entry_id,
            "description": self.description,
            "evidence_ids": self.evidence_ids,
            "reason": self.reason,
        }


def detect_axes(
    cube: Any,
    *,
    hermes_home: str | Path | None = None,
    engram: Any = None,
    session_stats: dict[str, Any] | None = None,
    entries: list[Any] | None = None,
) -> GrowthAxes:
    """Inspect the archive + session deltas for compounding surfaces."""
    stats = dict(session_stats or {})
    axes = GrowthAxes()

    durable_delta = int(stats.get("durable_writes") or 0)
    if durable_delta >= 1:
        axes.durable = True

    if entries is None:
        try:
            entries = list(cube.read_l1() or []) if cube is not None else []
        except Exception:
            entries = []
    else:
        entries = list(entries)

    # Recent session digest / sync_turn counts as durable even without delta
    if not axes.durable:
        for e in entries[-24:]:
            data = getattr(e, "data", None) or {}
            src = str(data.get("source") or "")
            if src in ("session_digest", "sync_turn", "hermescube_manage", "extract"):
                if (getattr(e, "outcome", "") or "") != "superseded":
                    axes.durable = True
                    break

    # Procedure axis: pending drafts or procedure-tagged entries
    try:
        from hermescube.consent import list_pending

        if list_pending(hermes_home):
            axes.procedure = True
    except Exception:
        pass
    if not axes.procedure:
        for e in entries[-40:]:
            desc = getattr(e, "description", "") or ""
            data = getattr(e, "data", None) or {}
            if (
                data.get("procedure")
                or desc.startswith("[PROCEDURE]")
                or desc.startswith("[TRAJECTORY]")
                or desc.startswith("[PROMOTED]")
            ):
                axes.procedure = True
                break

    # Association: engram edges/patterns or recent DOT links
    if engram is not None:
        try:
            st = engram.stats() if hasattr(engram, "stats") else {}
            if int(st.get("edges") or 0) >= 2 or int(st.get("patterns") or 0) >= 1:
                axes.association = True
        except Exception:
            pass
    if not axes.association:
        for e in entries[-30:]:
            data = getattr(e, "data", None) or {}
            if data.get("dot_link") or (getattr(e, "description", "") or "").startswith("[DOT]"):
                axes.association = True
                break

    # Yield: helpful feedback recorded this session or overall payoff signal
    if bool(stats.get("helpful_feedback")) or int(stats.get("yield_hits") or 0) > 0:
        axes.yield_ = True
    else:
        yg = stats.get("yield_gradient")
        if yg is not None and hasattr(yg, "stats"):
            try:
                yst = yg.stats()
                if int(yst.get("helpful") or yst.get("edges") or 0) > 0:
                    axes.yield_ = True
            except Exception:
                pass

    # Wisdom: active crystals
    for e in entries:
        data = getattr(e, "data", None) or {}
        if data.get("crystal") and (getattr(e, "outcome", "") or "") != "superseded":
            axes.wisdom = True
            break
    if bool(stats.get("crystalized")):
        axes.wisdom = True

    return axes


def _evidence_ids(entries: list[Any], *, limit: int = 8) -> list[str]:
    ids: list[str] = []
    for e in reversed(entries):
        if len(ids) >= limit:
            break
        et = (getattr(e, "entry_type", "") or "").lower()
        data = getattr(e, "data", None) or {}
        desc = getattr(e, "description", "") or ""
        if data.get("growth_merge"):
            continue
        if (getattr(e, "outcome", "") or "") == "superseded":
            continue
        keep = (
            et in ("belief", "resolve", "trait", "relationship", "evolution", "landmark")
            or data.get("crystal")
            or data.get("procedure")
            or data.get("dot_link")
            or desc.startswith("[SESSION]")
            or desc.startswith("[PROCEDURE]")
        )
        if keep and getattr(e, "id", None):
            ids.append(str(e.id))
    return list(reversed(ids))


def _already_merged_recently(entries: list[Any], *, window: int = 12) -> bool:
    for e in entries[-window:]:
        data = getattr(e, "data", None) or {}
        if data.get("growth_merge"):
            return True
    return False


def merge_session_growth(
    cube: Any,
    *,
    hermes_home: str | Path | None = None,
    engram: Any = None,
    session_stats: dict[str, Any] | None = None,
    dry_run: bool = False,
    agent_identity: str = "",
    agent_workspace: str = "",
    nest_profiles: bool = False,
    entries: list[Any] | None = None,
) -> GrowthMergeResult:
    """Emit one growth-merge crystal when ≥2 axes fired.

    Returns a result dict-friendly object. Mutates the cube unless dry_run.
    """
    if entries is None:
        try:
            entries = list(cube.read_l1() or []) if cube is not None else []
        except Exception as e:
            return GrowthMergeResult(
                merged=False,
                axes=GrowthAxes(),
                reason=f"read_l1: {e}",
            )
    else:
        entries = list(entries)

    axes = detect_axes(
        cube,
        hermes_home=hermes_home,
        engram=engram,
        session_stats=session_stats,
        entries=entries,
    )
    if not axes.merge_ready():
        return GrowthMergeResult(
            merged=False,
            axes=axes,
            reason=f"need ≥2 axes, have {axes.present() or ['none']}",
        )

    if _already_merged_recently(entries):
        return GrowthMergeResult(
            merged=False, axes=axes, reason="recent growth_merge already present"
        )

    evidence = _evidence_ids(entries)
    present = axes.present()
    desc = (
        f"[GROWTH-MERGE] axes={','.join(present)} "
        f"compounded across {len(evidence)} evidence entries"
    )[:240]

    if dry_run:
        return GrowthMergeResult(
            merged=True,
            axes=axes,
            description=desc,
            evidence_ids=evidence,
            reason="dry_run",
        )

    try:
        entry = cube.append(
            entry_type="evolution",
            description=desc,
            data={
                "growth_merge": True,
                "axes": present,
                "evidence_ids": evidence,
                "source": "growth_merge",
                "trust": 0.82,
                "durable": True,
                "crystal": True,
                "formed_at": time.time(),
            },
            outcome="success",
        )
        eid = str(getattr(entry, "id", "") or "")
    except Exception as e:
        logger.debug("growth_merge append failed: %s", e)
        return GrowthMergeResult(merged=False, axes=axes, reason=str(e))

    # Strengthen coactivation among evidence members when engram is present
    if engram is not None and len(evidence) >= 2:
        try:
            engram.learn_coactivation(evidence[:8], strength=1.0)
            if hasattr(engram, "save"):
                engram.save()
        except Exception:
            pass

    # SPO relations: trigger —compounds→ each axis
    if hermes_home:
        try:
            from hermescube.relations import RelationStore

            store = RelationStore(
                hermes_home,
                agent_identity=agent_identity,
                agent_workspace=agent_workspace,
                nest_profiles=nest_profiles,
            )
            for axis in present:
                store.record("session", "compounds", axis, memory_id=eid or None)
            for mid in evidence[:6]:
                store.record("session", "evidenced_by", mid, memory_id=eid or None)
        except Exception:
            pass

    # Genealogy: treat as a crystal-class lived event
    if hermes_home:
        try:
            from hermescube.genealogy import record_growth

            record_growth(
                hermes_home,
                "crystal",
                detail=f"growth_merge axes={','.join(present)}",
                cube=cube,
            )
        except Exception:
            pass

    return GrowthMergeResult(
        merged=True,
        axes=axes,
        entry_id=eid,
        description=desc,
        evidence_ids=evidence,
        reason="ok",
    )
