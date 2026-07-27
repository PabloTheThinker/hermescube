"""Time-bounded SPO relations sidecar for HermesCube.

Adapted from AgentDrive's MemoryRelationGraph: subject–predicate–object
records with optional validity windows, stored under
``$HERMES_HOME/memories/relations.sqlite3``.

Claims already carry bi-temporal fields; this store makes them *queryable*
as a graph ("who owned X as of date D") without scanning every L1 entry.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_.\-]{2,}")


def default_path(hermes_home: str | Path | None = None) -> Path:
    hh = Path(hermes_home or os.environ.get("HERMES_HOME") or (Path.home() / ".hermes"))
    return hh / "memories" / "relations.sqlite3"


@dataclass
class RelationRecord:
    relation_id: str
    subject: str
    predicate: str
    object: str
    valid_from: str | None = None
    valid_to: str | None = None
    memory_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "memory_id": self.memory_id,
        }


class RelationStore:
    """Per-Hermes-home SQLite relation store."""

    def __init__(self, hermes_home: str | Path | None = None) -> None:
        self.path = default_path(hermes_home)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relations (
                    relation_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    memory_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_subject ON relations(subject)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_object ON relations(object)"
            )
            conn.commit()

    def record(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        valid_from: str | None = None,
        valid_to: str | None = None,
        memory_id: str | None = None,
    ) -> RelationRecord:
        subject = (subject or "").strip()
        predicate = (predicate or "").strip()
        obj = (obj or "").strip()
        if not subject or not predicate or not obj:
            raise ValueError("subject, predicate, and object are required")
        relation_id = f"rel-{uuid.uuid4().hex[:12]}"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO relations (
                    relation_id, subject, predicate, object,
                    valid_from, valid_to, memory_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    subject,
                    predicate,
                    obj,
                    valid_from,
                    valid_to,
                    memory_id,
                    now,
                ),
            )
            conn.commit()
        return RelationRecord(
            relation_id=relation_id,
            subject=subject,
            predicate=predicate,
            object=obj,
            valid_from=valid_from,
            valid_to=valid_to,
            memory_id=memory_id,
        )

    def expire(
        self,
        subject: str,
        predicate: str,
        obj: str,
        *,
        ended: str | None = None,
    ) -> int:
        end = ended or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE relations SET valid_to = ?
                WHERE subject = ? AND predicate = ? AND object = ?
                  AND (valid_to IS NULL OR valid_to = '')
                """,
                (end, subject.strip(), predicate.strip(), obj.strip()),
            )
            conn.commit()
            return int(cur.rowcount or 0)

    def query(
        self,
        entity: str,
        *,
        as_of: str | None = None,
        limit: int = 50,
    ) -> list[RelationRecord]:
        entity = (entity or "").strip()
        if not entity:
            return []
        sql = "SELECT * FROM relations WHERE (subject = ? OR object = ?)"
        params: list[Any] = [entity, entity]
        if as_of:
            sql += " AND (valid_from IS NULL OR valid_from <= ?)"
            sql += " AND (valid_to IS NULL OR valid_to = '' OR valid_to >= ?)"
            params.extend([as_of, as_of])
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        records: list[RelationRecord] = []
        with self._connect() as conn:
            for row in conn.execute(sql, params):
                records.append(
                    RelationRecord(
                        relation_id=row["relation_id"],
                        subject=row["subject"],
                        predicate=row["predicate"],
                        object=row["object"],
                        valid_from=row["valid_from"],
                        valid_to=row["valid_to"],
                        memory_id=row["memory_id"],
                    )
                )
        return records

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            n = conn.execute("SELECT COUNT(*) AS c FROM relations").fetchone()["c"]
            open_n = conn.execute(
                "SELECT COUNT(*) AS c FROM relations "
                "WHERE valid_to IS NULL OR valid_to = ''"
            ).fetchone()["c"]
        return {"path": str(self.path), "relations": int(n), "open": int(open_n)}


def _entity_tokens(text: str, *, limit: int = 6) -> list[str]:
    """Prefer mirror entities when available; fall back to capitalised tokens."""
    try:
        from hermescube.mirror import extract_entities

        ents = extract_entities(text, max_entities=limit)
        if ents:
            return ents[:limit]
    except Exception:
        pass
    found: list[str] = []
    seen: set[str] = set()
    for m in _TOKEN.finditer(text or ""):
        t = m.group(0)
        if t[:1].isupper() or "-" in t or "_" in t or "." in t:
            key = t.lower()
            if key not in seen and len(t) >= 3:
                seen.add(key)
                found.append(t)
        if len(found) >= limit:
            break
    return found


def ingest_entry(entry: Any, store: RelationStore) -> list[str]:
    """Derive lightweight SPO links from a relationship / belief entry."""
    et = (getattr(entry, "entry_type", "") or "").lower()
    desc = (getattr(entry, "description", "") or "").strip()
    data = getattr(entry, "data", None) or {}
    if not desc or desc.startswith("[GROWTH-MERGE]"):
        return []
    if et not in ("relationship", "belief", "resolve", "trait") and not data.get(
        "dot_link"
    ):
        return []

    mid = str(getattr(entry, "id", "") or "") or None
    ids: list[str] = []

    # Explicit links from living connect_dots
    links = data.get("links") if isinstance(data, dict) else None
    entity = data.get("entity") if isinstance(data, dict) else None
    if data.get("dot_link") and entity and isinstance(links, list) and len(links) >= 2:
        try:
            rel = store.record(
                str(links[0])[:40],
                "shares_entity",
                str(links[1])[:40],
                memory_id=mid,
            )
            ids.append(rel.relation_id)
            rel2 = store.record(
                str(entity)[:80],
                "bridges",
                str(links[0])[:40],
                memory_id=mid,
            )
            ids.append(rel2.relation_id)
        except Exception:
            pass
        return ids

    ents = _entity_tokens(desc, limit=4)
    if len(ents) >= 2:
        pred = "related_to"
        if et == "relationship":
            pred = "relates"
        elif et == "resolve":
            pred = "decided"
        try:
            rel = store.record(ents[0], pred, ents[1], memory_id=mid)
            ids.append(rel.relation_id)
        except Exception:
            pass
    return ids


def format_for_prompt(
    records: list[RelationRecord], *, limit: int = 6
) -> str:
    if not records:
        return ""
    lines = ["### Relations"]
    for r in records[:limit]:
        span = ""
        if r.valid_from or r.valid_to:
            span = f" ({r.valid_from or '?'}→{r.valid_to or 'open'})"
        lines.append(f"- {r.subject} —{r.predicate}→ {r.object}{span}")
    return "\n".join(lines)
