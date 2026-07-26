"""Versioned temporal claims derived from MemoryEvents.

Claims are disposable projections: they can be superseded, but never erase
the supporting events. Bi-temporal fields track when a fact was true in the
world (valid_*) and when HermesCube learned it (transaction_*).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Claim:
    claim_id: str
    text: str
    claim_type: str = "belief"  # belief | trait | resolve | preference | relation
    status: str = "active"  # active | superseded | retracted
    confidence: float = 0.55
    verification: str = "unverified"
    evidence_event_ids: list[str] = field(default_factory=list)
    contradicts: list[str] = field(default_factory=list)
    superseded_by: str = ""
    valid_from: float | None = None
    valid_to: float | None = None
    transaction_from: float | None = None
    transaction_to: float | None = None
    branch_id: str = "main"
    origin: str = "model_inference"  # user | tool | model_inference | summary
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def make_claim(
    text: str,
    *,
    claim_type: str = "belief",
    evidence_event_ids: list[str] | None = None,
    confidence: float = 0.55,
    verification: str = "unverified",
    origin: str = "model_inference",
    branch_id: str = "main",
    valid_from: float | None = None,
    meta: dict[str, Any] | None = None,
) -> Claim:
    now = time.time()
    return Claim(
        claim_id=uuid.uuid4().hex[:12],
        text=(text or "").strip(),
        claim_type=claim_type,
        confidence=float(confidence),
        verification=verification,
        evidence_event_ids=list(evidence_event_ids or []),
        valid_from=valid_from if valid_from is not None else now,
        transaction_from=now,
        branch_id=branch_id or "main",
        origin=origin,
        meta=dict(meta or {}),
    )


def supersede_claim(old: Claim, new: Claim, *, reason: str = "") -> Claim:
    """Close validity of ``old`` and point it at ``new`` (in-memory)."""
    now = time.time()
    old.status = "superseded"
    old.valid_to = now
    old.transaction_to = now
    old.superseded_by = new.claim_id
    if reason:
        old.meta = dict(old.meta or {})
        old.meta["supersede_reason"] = reason[:300]
    new.meta = dict(new.meta or {})
    new.meta["supersedes"] = old.claim_id
    return old


def claim_to_entry_data(claim: Claim, **extra: Any) -> dict[str, Any]:
    data = dict(extra)
    data["claim"] = claim.to_dict()
    data.setdefault("source", "claim")
    data.setdefault("trust", claim.confidence)
    data.setdefault("durable", True)
    data.setdefault("branch_id", claim.branch_id)
    data.setdefault("verification", claim.verification)
    if claim.status == "superseded":
        data["superseded"] = True
    return data
