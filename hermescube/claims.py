"""Versioned temporal claims derived from MemoryEvents.

Claims are disposable projections: they can be superseded, but never erase
the supporting events. Bi-temporal fields track when a fact was true in the
world (valid_*) and when HermesCube learned it (transaction_*).

First-class optional SPO fields let Cuboasis bridge claims into RelationStore
without re-parsing prose on every durable write.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

# Lightweight SPO patterns for agent memory prose
_RE_OWNS = re.compile(
    r"\b([A-Z][A-Za-z0-9_.\-]+(?:\s+[A-Z][A-Za-z0-9_.\-]+){0,3})\s+"
    r"(owns|own|owned|uses|used|runs|ran|manages|managed|depends on|belongs to|"
    r"prefers|preferred|is)\s+"
    r"([A-Za-z0-9_.\-/$][A-Za-z0-9_.\-/$ ]{1,60})",
    re.I,
)
_RE_EQ = re.compile(
    r"\b([A-Z][A-Za-z0-9_.\-]+(?:\s+[A-Z][A-Za-z0-9_.\-]+){0,3})\s*=\s*"
    r"([A-Za-z0-9_.\-/$][A-Za-z0-9_.\-/$ ]{1,60})"
)


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
    # Optional first-class SPO (Cuboasis → RelationStore bridge)
    subject: str = ""
    predicate: str = ""
    object: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


def infer_spo_from_text(text: str) -> tuple[str, str, str] | None:
    """Best-effort subject/predicate/object from a claim sentence.

    Returns None when no confident pattern matches — callers fall back to
    generic ``memory / asserts / text``.
    """
    raw = (text or "").strip()
    if not raw or len(raw) < 4:
        return None
    # Prefer "Name = Role" style
    m = _RE_EQ.search(raw)
    if m:
        return (m.group(1).strip()[:80], "is", m.group(2).strip()[:120])
    m = _RE_OWNS.search(raw)
    if m:
        pred = m.group(2).strip().lower().replace(" ", "_")
        # normalize tense
        pred_map = {
            "owns": "owns",
            "own": "owns",
            "owned": "owns",
            "uses": "uses",
            "used": "uses",
            "runs": "runs",
            "ran": "runs",
            "manages": "manages",
            "managed": "manages",
            "depends_on": "depends_on",
            "belongs_to": "belongs_to",
            "prefers": "prefers",
            "preferred": "prefers",
            "is": "is",
        }
        pred = pred_map.get(pred, pred)
        return (m.group(1).strip()[:80], pred, m.group(3).strip()[:120])
    # Entity pair fallback via extract_entities
    try:
        from hermescube.mirror import extract_entities

        ents = extract_entities(raw, max_entities=4)
        if len(ents) >= 2:
            return (ents[0][:80], "related_to", ents[1][:120])
    except Exception:
        pass
    return None


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
    subject: str = "",
    predicate: str = "",
    object: str = "",
    meta: dict[str, Any] | None = None,
    infer_spo: bool = True,
) -> Claim:
    now = time.time()
    text_s = (text or "").strip()
    subj, pred, obj = subject, predicate, object
    if infer_spo and (not subj or not obj):
        inferred = infer_spo_from_text(text_s)
        if inferred:
            subj = subj or inferred[0]
            pred = pred or inferred[1]
            obj = obj or inferred[2]
    return Claim(
        claim_id=uuid.uuid4().hex[:12],
        text=text_s,
        claim_type=claim_type,
        confidence=float(confidence),
        verification=verification,
        evidence_event_ids=list(evidence_event_ids or []),
        valid_from=valid_from if valid_from is not None else now,
        transaction_from=now,
        branch_id=branch_id or "main",
        origin=origin,
        subject=subj or "",
        predicate=pred or "",
        object=obj or "",
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
    try:
        from hermescube.memory_gate import normalize_evidence_state

        data.setdefault(
            "evidence_state",
            normalize_evidence_state(claim.verification, default="observed"),
        )
    except Exception:
        pass
    if claim.subject:
        data.setdefault("subject", claim.subject)
    if claim.predicate:
        data.setdefault("predicate", claim.predicate)
    if claim.object:
        data.setdefault("object", claim.object)
    if claim.status == "superseded":
        data["superseded"] = True
        data["evidence_state"] = "superseded"
    return data
