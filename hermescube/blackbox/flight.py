"""FlightRecord schema + integrity (Cube blackbox core)."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class FlightEvent:
    ts: str | None
    kind: str
    name: str | None = None
    summary: str | None = None
    detail: Any = None
    refs: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "kind": self.kind,
            "name": self.name,
            "summary": self.summary,
            "detail": self.detail,
            "refs": self.refs or {},
        }


@dataclass
class ClaimResult:
    claim: str
    verdict: str  # pass | fail | inconclusive
    confidence: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim": self.claim,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "gaps": self.gaps,
        }


@dataclass
class FlightRecord:
    id: str
    created_at: str
    schema_version: str
    source: dict[str, Any]
    session: dict[str, Any]
    events: list[dict[str, Any]]
    redactions_count: int = 0
    integrity: dict[str, Any] = field(default_factory=dict)
    claims_tested: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "schema_version": self.schema_version,
            "source": self.source,
            "session": self.session,
            "events": self.events,
            "redactions_count": self.redactions_count,
            "integrity": self.integrity,
            "claims_tested": self.claims_tested,
            "artifacts": self.artifacts,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightRecord":
        return cls(
            id=data["id"],
            created_at=data["created_at"],
            schema_version=data.get("schema_version", "1.0"),
            source=data.get("source", {}),
            session=data.get("session", {}),
            events=data.get("events", []),
            redactions_count=int(data.get("redactions_count", 0)),
            integrity=data.get("integrity", {}),
            claims_tested=data.get("claims_tested", []),
            artifacts=data.get("artifacts", []),
            meta=data.get("meta", {}),
        )


def new_record_id() -> str:
    return f"bb_{uuid.uuid4().hex[:16]}"


def integrity_hash(events: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = json.dumps(
        events, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "alg": "sha256",
        "event_count": len(events),
        "sha256": digest,
        "canonicalization": "json-sort-keys-utf8",
    }


def verify_integrity(record: FlightRecord | dict[str, Any]) -> bool:
    data = record.to_dict() if isinstance(record, FlightRecord) else record
    expected = integrity_hash(data.get("events") or [])
    got = (data.get("integrity") or {}).get("sha256")
    return bool(got) and got == expected["sha256"]
