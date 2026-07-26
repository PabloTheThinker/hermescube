"""Provenance-preserving MemoryEvent envelope for HermesCube.

Every durable experience is an append-only event with stable identity,
source hashes, actor/context metadata, and bi-temporal fields. Derived
claims and procedures must cite event ids — never replace raw evidence.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def _utcnow() -> float:
    return time.time()


def content_hash(*parts: Any) -> str:
    """Stable sha256 over canonical JSON fragments."""
    payload = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class MemoryEvent:
    """Immutable experience record (logical; stored inside CubeEntry.data)."""

    event_id: str
    kind: str  # turn | tool | memory_write | delegation | claim | procedure | reconcile
    observed_at: float
    ingested_at: float
    session_id: str = ""
    parent_session_id: str = ""
    platform: str = "cli"
    agent_context: str = "primary"
    agent_identity: str = ""
    actor: str = "agent"  # user | agent | tool | system
    source: str = ""
    content_hash: str = ""
    privacy: str = "local"
    confidence: float = 0.55
    verification: str = "unverified"  # unverified | observed | tool_verified | user_authored
    valid_from: float | None = None
    valid_to: float | None = None  # None = currently valid
    parent_event_ids: list[str] = field(default_factory=list)
    branch_id: str = "main"
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryEvent":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in data.items() if k in known}
        if "event_id" not in kwargs:
            kwargs["event_id"] = uuid.uuid4().hex[:16]
        if "ingested_at" not in kwargs:
            kwargs["ingested_at"] = _utcnow()
        if "observed_at" not in kwargs:
            kwargs["observed_at"] = kwargs["ingested_at"]
        return cls(**kwargs)


def make_event(
    kind: str,
    *,
    session_id: str = "",
    parent_session_id: str = "",
    platform: str = "cli",
    agent_context: str = "primary",
    agent_identity: str = "",
    actor: str = "agent",
    source: str = "",
    payload: dict[str, Any] | None = None,
    confidence: float = 0.55,
    verification: str = "unverified",
    parent_event_ids: list[str] | None = None,
    branch_id: str = "main",
    observed_at: float | None = None,
    valid_from: float | None = None,
    valid_to: float | None = None,
    event_id: str | None = None,
) -> MemoryEvent:
    now = _utcnow()
    body = payload or {}
    ch = content_hash(kind, session_id, source, body)
    return MemoryEvent(
        event_id=event_id or uuid.uuid4().hex[:16],
        kind=kind,
        observed_at=float(observed_at if observed_at is not None else now),
        ingested_at=now,
        session_id=session_id or "",
        parent_session_id=parent_session_id or "",
        platform=platform or "cli",
        agent_context=agent_context or "primary",
        agent_identity=agent_identity or "",
        actor=actor,
        source=source,
        content_hash=ch,
        confidence=float(confidence),
        verification=verification,
        valid_from=valid_from if valid_from is not None else now,
        valid_to=valid_to,
        parent_event_ids=list(parent_event_ids or []),
        branch_id=branch_id or "main",
        payload=body,
    )


def event_to_entry_data(event: MemoryEvent, **extra: Any) -> dict[str, Any]:
    """Embed a MemoryEvent into CubeEntry.data without losing provenance."""
    data = dict(extra)
    data["event"] = event.to_dict()
    data.setdefault("source", event.source or event.kind)
    data.setdefault("session_id", event.session_id)
    data.setdefault("trust", event.confidence)
    data.setdefault("branch_id", event.branch_id)
    data.setdefault("content_hash", event.content_hash)
    data.setdefault("verification", event.verification)
    return data
