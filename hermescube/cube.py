"""Binary .cube file I/O — L1 entries, L2 topic index, L3 β vector."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import struct
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from hermescube import hrr

logger = logging.getLogger(__name__)

MAGIC = b"CUBE"
VERSION = 1
HEADER_SIZE = 40
CUBELOG_MAGIC = b"CUBELOG\x01"  # 8 bytes: CUBELOG + version byte
DEFAULT_DIM = 256
DEFAULT_L2_BUCKETS = 64

# Entry type enum
ENTRY_TYPES = {
    "enter": 0,
    "leave": 1,
    "landmark": 2,
    "belief": 3,
    "trait": 4,
    "evolution": 5,
    "focus": 6,
    "epoch_transition": 7,
    "resolve": 8,
    "relationship": 9,
}
ENTRY_TYPE_NAMES = {v: k for k, v in ENTRY_TYPES.items()}

# Outcome enum
OUTCOMES = {"none": 0, "success": 1, "failure": 2, "pending": 3, "superseded": 4}
OUTCOME_NAMES = {v: k for k, v in OUTCOMES.items()}


# ── Data types ────────────────────────────────────────────────────────


@dataclass
class CubeEntry:
    id: str = ""
    timestamp: str = ""
    entry_type: str = ""
    outcome: str = "none"
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    causal_parents: list[str] = field(default_factory=list)

    @property
    def vector(self) -> hrr.Array:
        if not hasattr(self, "_vector") or self._vector is None:
            self._vector = hrr.embed_text(
                f"{self.entry_type}: {self.description}"
            )
        return self._vector

    @vector.setter
    def vector(self, v: hrr.Array) -> None:
        self._vector = v

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "entry_type": self.entry_type,
            "outcome": self.outcome,
            "description": self.description,
            "data": self.data,
            "causal_parents": self.causal_parents,
        }


@dataclass
class L2Bucket:
    centroid: hrr.Array
    entry_ids: list[str] = field(default_factory=list)
    terms: list[str] = field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _serialize_vec(v: hrr.Array) -> bytes:
    if hrr.has_numpy():
        import numpy as _np

        arr = _np.asarray(v, dtype=_np.float64)
        return arr.tobytes()
    return struct.pack(f"<{len(v)}d", *v)


def _deserialize_vec(data: bytes, dim: int) -> hrr.Array:
    if hrr.has_numpy():
        import numpy as _np

        return _np.frombuffer(data, dtype=_np.float64).copy()
    return list(struct.unpack(f"<{dim}d", data))


# ── CubeFile ──────────────────────────────────────────────────────────


class CubeFile:
    """Binary .cube file — open/create, append, read, write L3."""

    def __init__(self) -> None:
        import threading
        self.path: str = ""
        self._file: Any = None  # file handle
        self._flocked: bool = False  # set True after fcntl.flock acquired
        self.dim: int = DEFAULT_DIM
        self.l2_bucket_count: int = DEFAULT_L2_BUCKETS
        self.entry_count: int = 0
        self.l1_data_size: int = 0
        self.l3_offset: int = 0
        self._entries_cache: list[CubeEntry] | None = None
        # WAL: entries appended since last evolve live in .cubelog
        self._cubelog_path: str = ""
        self._cubelog_count: int = 0
        self._cubelog_entries: list[CubeEntry] | None = None
        # Internal RLock — guards all file I/O and in-memory state mutation
        self._lock = threading.RLock()

    # ── File-level locking (cross-process) ─────────────────────────

    def _acquire_flock(self) -> None:
        """Acquire exclusive flock on the open file descriptor.

        Non-blocking; raises RuntimeError if another process holds the lock.
        The lock is released automatically when the fd is closed or the
        process exits.
        """
        if self._flocked:
            return
        if not self._file or self._file.closed:
            raise RuntimeError("Cube file not open")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._flocked = True
        except OSError as e:
            raise RuntimeError(
                f"Cannot lock {self.path!r}: another process may have it open. "
                f"({e})"
            ) from None

    def _release_flock(self) -> None:
        """Release the exclusive flock (best-effort)."""
        if not self._flocked:
            return
        if self._file and not self._file.closed:
            try:
                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        self._flocked = False

    def _reopen_after_replace(self) -> None:
        """Reopen the file handle after os.replace() renamed the underlying file.

        The old fd still points to the unlinked temp inode; we must
        reopen on the canonical path and reacquire the flock.
        """
        if self._file and not self._file.closed:
            self._file.close()
        self._file = open(self.path, "r+b")
        self._acquire_flock()
        self._open_cubelog()

    # ── WAL: cubelog for O(1) appends ──────────────────────────────

    def _open_cubelog(self) -> None:
        """Open (or create) the cubelog WAL file.

        The cubelog stores entries appended since the last evolve.
        It lives alongside the .cube file and is truncated after
        each successful compaction (evolve).
        """
        self._cubelog_path = self.path + ".cubelog"
        cubelog_bytes = b""
        if os.path.isfile(self._cubelog_path):
            with open(self._cubelog_path, "rb") as cf:
                cubelog_bytes = cf.read()
            if cubelog_bytes.startswith(CUBELOG_MAGIC):
                self._cubelog_count = struct.unpack("<I", cubelog_bytes[8:12])[0]
            else:
                self._cubelog_count = 0
                cubelog_bytes = b""
        else:
            # Create empty cubelog
            with open(self._cubelog_path, "wb") as cf:
                cf.write(CUBELOG_MAGIC)
                cf.write(struct.pack("<I", 0))

        self._cubelog_entries = None  # force re-read on next read_l1
        if cubelog_bytes and self._cubelog_count > 0:
            self._cubelog_preload(cubelog_bytes)
        else:
            self._cubelog_entries = []

    def _cubelog_preload(self, existing_bytes: bytes) -> None:
        """Pre-load cubelog entries into cache for fast reads."""
        if self._cubelog_count == 0:
            self._cubelog_entries = []
            return
        entries: list[CubeEntry] = []
        offset = 12  # skip magic + count
        remaining = len(existing_bytes) - offset
        for _ in range(self._cubelog_count):
            if remaining <= 0:
                break
            entry, entry_size = self._read_entry_bytes(
                existing_bytes[offset:], self.dim
            )
            entries.append(entry)
            offset += entry_size
            remaining -= entry_size
        self._cubelog_entries = entries

    @staticmethod
    def _read_entry_bytes(data: bytes, dim: int) -> tuple[CubeEntry, int]:
        """Parse an entry from raw bytes — shared by cubelog and .cube reads."""
        off = 0
        entry_id = data[off:off+12].rstrip(b"\x00").decode("ascii"); off += 12
        timestamp = data[off:off+16].rstrip(b"\x00").decode("ascii"); off += 16
        (type_code,) = struct.unpack("<B", data[off:off+1]); off += 1
        (outcome_code,) = struct.unpack("<B", data[off:off+1]); off += 1
        (desc_len,) = struct.unpack("<I", data[off:off+4]); off += 4
        (data_len,) = struct.unpack("<I", data[off:off+4]); off += 4
        (causal_count,) = struct.unpack("<I", data[off:off+4]); off += 4

        desc = data[off:off+desc_len].decode("utf-8"); off += desc_len
        data_raw = data[off:off+data_len]; off += data_len
        entry_data: dict[str, Any] = {}
        if data_raw:
            try:
                entry_data = json.loads(data_raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                entry_data = {"_raw": data_raw.decode("utf-8", errors="replace")}

        causal_parents: list[str] = []
        for _ in range(causal_count):
            pid = data[off:off+12].rstrip(b"\x00").decode("ascii"); off += 12
            causal_parents.append(pid)

        vec_data = data[off:off+dim*8]; off += dim*8
        vec = _deserialize_vec(vec_data, dim)

        entry = CubeEntry(
            id=entry_id, timestamp=timestamp,
            entry_type=ENTRY_TYPE_NAMES.get(type_code, "unknown"),
            outcome=OUTCOME_NAMES.get(outcome_code, "none"),
            description=desc, data=entry_data, causal_parents=causal_parents,
        )
        entry.vector = vec

        total_size = off
        return entry, total_size

    def _append_to_cubelog(self, entry: CubeEntry) -> None:
        """Append a single entry to the cubelog WAL — O(1) write."""
        desc_bytes = entry.description.encode("utf-8")
        data_bytes = json.dumps(entry.data, default=str).encode("utf-8")
        vec = entry.vector if hasattr(entry, "_vector") and entry._vector is not None else hrr.embed_text(f"{entry.entry_type}: {entry.description}")
        if not hasattr(entry, "_vector") or entry._vector is None:
            entry._vector = vec
        entry_bytes = self._pack_entry_bytes(entry, desc_bytes, data_bytes, vec, self.dim)

        with open(self._cubelog_path, "r+b") as cf:
            cf.seek(8)  # after magic
            new_count = self._cubelog_count + 1
            cf.write(struct.pack("<I", new_count))
            cf.seek(0, 2)  # end of file
            cf.write(entry_bytes)
            cf.flush()
            try:
                os.fsync(cf.fileno())
            except OSError as e:
                logger.warning("fsync failed after cubelog append: %s", e)

        self._cubelog_count = new_count
        if self._cubelog_entries is not None:
            self._cubelog_entries.append(entry)
        self.entry_count += 1

    def _truncate_cubelog(self) -> None:
        """Reset the cubelog after a successful compaction (evolve)."""
        with open(self._cubelog_path, "wb") as cf:
            cf.write(CUBELOG_MAGIC)
            cf.write(struct.pack("<I", 0))
            cf.flush()
            try:
                os.fsync(cf.fileno())
            except OSError as e:
                logger.warning("fsync failed after cubelog truncate: %s", e)
        self._cubelog_count = 0
        self._cubelog_entries = []
        self._entries_cache = None

    # ── Creation / Open ───────────────────────────────────────────

    @classmethod
    def create(
        cls,
        path: str,
        dim: int = DEFAULT_DIM,
        l2_buckets: int = DEFAULT_L2_BUCKETS,
    ) -> CubeFile:
        self = cls()
        self.path = os.path.abspath(path)
        self.dim = dim
        self.l2_bucket_count = l2_buckets
        self.entry_count = 0
        self.l1_data_size = 0
        # l3_offset = HEADER_SIZE + L1_size + L2_size
        # at creation: L1_size=0, L2_size=4 + buckets*(dim*8 + 6)
        empty_l2_size = 4 + l2_buckets * (dim * 8 + 6)
        self.l3_offset = HEADER_SIZE + empty_l2_size

        self._file = open(self.path, "wb")
        self._acquire_flock()
        self._write_header(self._file)
        self._write_empty_l2()

        beta = hrr.zero_vector(dim)
        self._write_l3_raw(beta)
        self._file.flush()
        self.close()

        self._file = open(self.path, "r+b")
        self._acquire_flock()
        self._open_cubelog()
        # entry_count from header excludes cubelog entries — add them
        self.entry_count += self._cubelog_count
        return self

    @classmethod
    def open(cls, path: str) -> CubeFile:
        self = cls()
        self.path = os.path.abspath(path)

        if not os.path.isfile(self.path):
            raise FileNotFoundError(f"Cube file not found: {path}")

        with open(self.path, "rb") as f:
            self._read_header(f)

        self._file = open(self.path, "r+b")
        self._acquire_flock()
        self._open_cubelog()
        # entry_count from header excludes cubelog entries — add them
        self.entry_count += self._cubelog_count
        return self

    def density_stats(self) -> dict:
        """Archive density report (how much of the file is signal vs vectors)."""
        import os as _os
        n = int(self.entry_count or 0)
        path_size = _os.path.getsize(self.path) if self.path and _os.path.isfile(self.path) else 0
        log_size = 0
        if getattr(self, "_cubelog_path", None) and _os.path.isfile(self._cubelog_path):
            log_size = _os.path.getsize(self._cubelog_path)
        try:
            ents = self.read_l1() or []
            text_b = sum(len((e.description or "").encode()) for e in ents)
            data_b = sum(len(__import__("json").dumps(e.data or {}).encode()) for e in ents)
        except Exception:
            text_b = data_b = 0
        total = path_size + log_size
        vec_b = n * self.dim * 8
        return {
            "version": 1,
            "entries": n,
            "cube_bytes": path_size,
            "cubelog_bytes": log_size,
            "total_bytes": total,
            "bytes_per_entry": (total / n) if n else 0,
            "text_bytes": text_b,
            "data_bytes": data_b,
            "vec_bytes_estimate": vec_b,
            "text_plus_data_share": ((text_b + data_b) / total) if total else 0,
            "note": "v1 float64 vectors dominate; dense f16 migration tracked for 0.7",
        }

    def close(self) -> None:
        with self._lock:
            self._release_flock()
            if self._file and not self._file.closed:
                self._file.flush()
                self._file.close()

    def __enter__(self) -> CubeFile:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    # ── Header I/O ────────────────────────────────────────────────

    def _write_header(self, f: Any) -> None:
        f.write(MAGIC)
        f.write(struct.pack("<I", VERSION))
        f.write(struct.pack("<I", self.dim))
        f.write(struct.pack("<Q", self.entry_count))
        f.write(struct.pack("<I", self.l2_bucket_count))
        f.write(struct.pack("<Q", self.l1_data_size))
        f.write(struct.pack("<Q", self.l3_offset))
        # Total: 4 + 4 + 4 + 8 + 4 + 8 + 8 = 40

    def _read_header(self, f: Any) -> None:
        data = f.read(HEADER_SIZE)
        if len(data) < HEADER_SIZE:
            raise ValueError("File too small for header")

        off = 0
        magic = data[off : off + 4]
        off += 4
        if magic != MAGIC:
            raise ValueError(f"Not a cube file (magic={magic!r})")

        version = struct.unpack("<I", data[off : off + 4])[0]
        off += 4
        if version > VERSION:
            raise ValueError(f"Unsupported version: {version}")

        self.dim = struct.unpack("<I", data[off : off + 4])[0]
        off += 4
        self.entry_count = struct.unpack("<Q", data[off : off + 8])[0]
        off += 8
        self.l2_bucket_count = struct.unpack("<I", data[off : off + 4])[0]
        off += 4
        self.l1_data_size = struct.unpack("<Q", data[off : off + 8])[0]
        off += 8
        self.l3_offset = struct.unpack("<Q", data[off : off + 8])[0]

    # ── L1 — Entry I/O ────────────────────────────────────────────

    @staticmethod
    def _compute_entry_size(
        desc_len: int,
        data_len: int,
        causal_count: int,
        dim: int,
    ) -> int:
        """Single source of truth for entry byte size.

        Used by _entry_size and _read_entry_at so the two cannot drift
        apart on a future format change.
        """
        return (
            12  # id
            + 16  # timestamp
            + 1  # entry_type
            + 1  # outcome
            + 4  # desc_len
            + 4  # data_len
            + 4  # causal_count
            + desc_len
            + data_len
            + causal_count * 12
            + dim * 8  # vector
        )

    def _entry_size(self, entry: CubeEntry) -> int:
        desc_bytes = entry.description.encode("utf-8")
        data_bytes = json.dumps(entry.data, default=str).encode("utf-8")
        return self._compute_entry_size(
            desc_len=len(desc_bytes),
            data_len=len(data_bytes),
            causal_count=len(entry.causal_parents),
            dim=self.dim,
        )

    @staticmethod
    def _pack_entry_bytes(
        entry: CubeEntry,
        desc_bytes: bytes,
        data_bytes: bytes,
        vec: hrr.Array,
        dim: int,
    ) -> bytes:
        """Serialize an entry to bytes — single source of truth for the
        on-disk L1 entry layout. Used by both _append_unlocked (write)
        and tests. _read_entry_at is the dual (parse) side."""
        import io
        buf = io.BytesIO()
        entry_type_code = ENTRY_TYPES.get(entry.entry_type, 0)
        outcome_code = OUTCOMES.get(entry.outcome, 0)

        buf.write(entry.id.encode("ascii").ljust(12, b"\x00")[:12])
        buf.write(entry.timestamp.encode("ascii").ljust(16, b"\x00")[:16])
        buf.write(struct.pack("<B", entry_type_code))
        buf.write(struct.pack("<B", outcome_code))
        buf.write(struct.pack("<I", len(desc_bytes)))
        buf.write(struct.pack("<I", len(data_bytes)))
        buf.write(struct.pack("<I", len(entry.causal_parents)))
        buf.write(desc_bytes)
        buf.write(data_bytes)
        for pid in entry.causal_parents:
            buf.write(pid.encode("ascii").ljust(12, b"\x00")[:12])
        buf.write(_serialize_vec(vec))
        return buf.getvalue()

    def append(
        self,
        entry_type: str,
        description: str,
        data: dict[str, Any] | None = None,
        causal_parents: list[str] | None = None,
        outcome: str = "none",
    ) -> CubeEntry:
        from hermescube.mirror import annotate_entities_on_append

        data = annotate_entities_on_append(description, data)
        with self._lock:
            return self._append_unlocked(
                entry_type, description, data, causal_parents, outcome
            )

    def _append_unlocked(
        self,
        entry_type: str,
        description: str,
        data: dict[str, Any] | None = None,
        causal_parents: list[str] | None = None,
        outcome: str = "none",
    ) -> CubeEntry:
        entry = CubeEntry(
            id=_new_id(),
            timestamp=_utcnow(),
            entry_type=entry_type,
            outcome=outcome,
            description=description.strip(),
            data=data or {},
            causal_parents=causal_parents or [],
        )

        if not self._file or self._file.closed:
            raise RuntimeError("Cube file not open")

        # Pre-compute the entry vector (also caches on the entry)
        vec = hrr.embed_text(f"{entry.entry_type}: {entry.description}")
        entry._vector = vec

        # O(1) append to cubelog WAL — no .cube file rewrite
        self._append_to_cubelog(entry)

        # Invalidate the merged L1 cache so next read picks up the new entry
        self._entries_cache = None

        return entry

    def _read_entry_at(self, offset: int) -> tuple[CubeEntry, int]:
        f = self._file
        f.seek(offset)

        entry_id = f.read(12).rstrip(b"\x00").decode("ascii")
        timestamp = f.read(16).rstrip(b"\x00").decode("ascii")
        (type_code,) = struct.unpack("<B", f.read(1))
        (outcome_code,) = struct.unpack("<B", f.read(1))
        (desc_len,) = struct.unpack("<I", f.read(4))
        (data_len,) = struct.unpack("<I", f.read(4))
        (causal_count,) = struct.unpack("<I", f.read(4))

        desc = f.read(desc_len).decode("utf-8")
        data_raw = f.read(data_len)
        data: dict[str, Any] = {}
        if data_raw:
            try:
                data = json.loads(data_raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("entry data not valid JSON: %s", e)
                data = {"_raw": data_raw.decode("utf-8", errors="replace")}

        causal_parents = []
        for _ in range(causal_count):
            pid = f.read(12).rstrip(b"\x00").decode("ascii")
            causal_parents.append(pid)

        # Read vector
        vec_data = f.read(self.dim * 8)
        vec = _deserialize_vec(vec_data, self.dim)

        entry = CubeEntry(
            id=entry_id,
            timestamp=timestamp,
            entry_type=ENTRY_TYPE_NAMES.get(type_code, "unknown"),
            outcome=OUTCOME_NAMES.get(outcome_code, "none"),
            description=desc,
            data=data,
            causal_parents=causal_parents,
        )
        entry.vector = vec

        total_size = self._compute_entry_size(
            desc_len=desc_len,
            data_len=data_len,
            causal_count=causal_count,
            dim=self.dim,
        )
        return entry, total_size

    def read_l1(self) -> list[CubeEntry]:
        with self._lock:
            if self._entries_cache is not None:
                return self._entries_cache

            if not self._file or self._file.closed:
                raise RuntimeError("Cube file not open")

            entries: list[CubeEntry] = []

            # Read entries from .cube L1
            offset = HEADER_SIZE
            remaining = self.l1_data_size
            while remaining > 0:
                entry, entry_size = self._read_entry_at(offset)
                entries.append(entry)
                offset += entry_size
                remaining -= entry_size

            # Merge cubelog entries (appended since last evolve)
            if self._cubelog_count > 0:
                if self._cubelog_entries is None:
                    with open(self._cubelog_path, "rb") as cf:
                        raw = cf.read()
                    if raw.startswith(CUBELOG_MAGIC) and len(raw) > 12:
                        # Skip 8-byte magic + 4-byte count header
                        self._cubelog_preload(raw)
                if self._cubelog_entries:
                    entries.extend(self._cubelog_entries)

            self._entries_cache = entries
            return entries

    def read_entry(self, entry_id: str) -> CubeEntry | None:
        with self._lock:
            for entry in self.read_l1():
                if entry.id == entry_id:
                    return entry
            return None

    def replay(self) -> list[CubeEntry]:
        return self.read_l1()

    def count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.read_l1():
            t = entry.entry_type
            counts[t] = counts.get(t, 0) + 1
        return counts

    def search(
        self,
        term: str,
        entry_type: str | None = None,
        limit: int = 20,
    ) -> list[CubeEntry]:
        """Simple substring search across entry descriptions."""
        term_lower = term.lower()
        matches: list[CubeEntry] = []
        for entry in self.read_l1():
            if entry_type and entry.entry_type != entry_type:
                continue
            if term_lower in entry.description.lower():
                matches.append(entry)
                if limit > 0 and len(matches) >= limit:
                    break
        return matches

    def query_range(
        self,
        after: str | None = None,
        before: str | None = None,
        entry_type: str | None = None,
    ) -> list[CubeEntry]:
        """Filter entries by timestamp range and type."""
        results: list[CubeEntry] = []
        for entry in self.read_l1():
            if entry_type and entry.entry_type != entry_type:
                continue
            if after and entry.timestamp < after:
                continue
            if before and entry.timestamp > before:
                continue
            results.append(entry)
        return results

    # ── L2 — Topic index ──────────────────────────────────────────

    def _write_empty_l2(self) -> None:
        if not self._file or self._file.closed:
            raise RuntimeError("Cube file not open")

        l2_start = HEADER_SIZE + self.l1_data_size
        self._file.seek(l2_start)
        self._file.write(struct.pack("<I", self.l2_bucket_count))

        dim = self.dim
        for _ in range(self.l2_bucket_count):
            vec_data = _serialize_vec(hrr.zero_vector(dim))
            self._file.write(vec_data)  # centroid
            self._file.write(struct.pack("<I", 0))  # entry_count = 0
            self._file.write(struct.pack("<H", 0))  # terms_len = 0

    def read_l2(self) -> list[L2Bucket]:
        with self._lock:
            return self._read_l2_unlocked()

    def _read_l2_unlocked(self) -> list[L2Bucket]:
        if not self._file or self._file.closed:
            raise RuntimeError("Cube file not open")

        l2_start = HEADER_SIZE + self.l1_data_size
        self._file.seek(l2_start)

        (bucket_count,) = struct.unpack("<I", self._file.read(4))

        buckets: list[L2Bucket] = []
        for _ in range(bucket_count):
            centroid_data = self._file.read(self.dim * 8)
            centroid = _deserialize_vec(centroid_data, self.dim)
            (entry_count,) = struct.unpack("<I", self._file.read(4))

            entry_ids: list[str] = []
            for _ in range(entry_count):
                eid = self._file.read(12).rstrip(b"\x00").decode("ascii")
                entry_ids.append(eid)

            (terms_len,) = struct.unpack("<H", self._file.read(2))
            terms_raw = self._file.read(terms_len)
            terms = terms_raw.decode("utf-8").split(",") if terms_raw else []

            buckets.append(L2Bucket(centroid=centroid, entry_ids=entry_ids, terms=terms))

        return buckets

    def write_l2(self, buckets: list[L2Bucket]) -> None:
        with self._lock:
            self._write_l2_unlocked(buckets)

    def _write_l2_unlocked(self, buckets: list[L2Bucket]) -> None:
        if not self._file or self._file.closed:
            raise RuntimeError("Cube file not open")

        # Compact: merge cubelog entries into L1 before writing L2.
        # This ensures all entries are in the .cube after evolve, and
        # L2 centroids point to entries that exist in the .cube L1.
        if self._cubelog_count > 0:
            all_entries = self.read_l1()  # merges .cube + cubelog
            # Rebuild L1 with all entries (existing .cube entries + cubelog)
            new_l1_bytes = bytearray()
            for entry in all_entries[:self.entry_count - self._cubelog_count]:
                # These are already in .cube L1 — keep as-is via existing data
                pass
            # Append cubelog entries to .cube L1
            if self._cubelog_entries:
                for entry in self._cubelog_entries:
                    desc_bytes = entry.description.encode("utf-8")
                    data_bytes = json.dumps(entry.data, default=str).encode("utf-8")
                    eb = self._pack_entry_bytes(
                        entry, desc_bytes, data_bytes, entry.vector, self.dim,
                    )
                    new_l1_bytes.extend(eb)
                # Write cubelog entries to end of current L1
                self._file.seek(HEADER_SIZE + self.l1_data_size)
                self._file.write(bytes(new_l1_bytes))
                self.l1_data_size += len(new_l1_bytes)
                self._file.flush()
                os.fsync(self._file.fileno())
            # Truncate cubelog
            with open(self._cubelog_path, "wb") as cf:
                cf.write(CUBELOG_MAGIC)
                cf.write(struct.pack("<I", 0))
                cf.flush()
                os.fsync(cf.fileno())
            self._cubelog_count = 0
            self._cubelog_entries = []
            self._entries_cache = None

        l2_start = HEADER_SIZE + self.l1_data_size
        self._file.seek(l2_start)
        self._file.write(struct.pack("<I", len(buckets)))

        dim = self.dim
        for bucket in buckets:
            centroid_data = _serialize_vec(bucket.centroid)
            self._file.write(centroid_data)
            self._file.write(struct.pack("<I", len(bucket.entry_ids)))
            for eid in bucket.entry_ids:
                self._file.write(eid.encode("ascii").ljust(12, b"\x00")[:12])
            terms_str = ",".join(bucket.terms)
            terms_bytes = terms_str.encode("utf-8")
            self._file.write(struct.pack("<H", len(terms_bytes)))
            self._file.write(terms_bytes)

        # Capture L2 end position BEFORE writing header (seek will move us)
        l2_end = self._file.tell()

        # Update header BEFORE truncating so on-disk l3_offset is never
        # ahead of the file (avoids the truncate+header-update race window)
        self.l3_offset = 0  # invalidate so write_l3() appends fresh
        self._file.seek(0)
        self._write_header(self._file)
        self._file.flush()

        # Truncate at end of L2 — old L3 is discarded, write_l3() will re-append
        self._file.truncate(l2_end)
        self._file.flush()
        try:
            os.fsync(self._file.fileno())
        except OSError as e:
            logger.warning("fsync failed after write_l2: %s", e)

    # ── L3 — β vector ─────────────────────────────────────────────

    def _write_l3_raw(self, beta: hrr.Array) -> None:
        if not self._file or self._file.closed:
            return
        self._file.seek(self.l3_offset)
        self._file.write(_serialize_vec(beta))
        self._file.flush()

    def read_l3(self) -> hrr.Array:
        with self._lock:
            if not self._file or self._file.closed:
                raise RuntimeError("Cube file not open")

            if self.l3_offset <= 0:
                return hrr.zero_vector(self.dim)

            self._file.seek(self.l3_offset)
            data = self._file.read(self.dim * 8)
            if len(data) < self.dim * 8:
                return hrr.zero_vector(self.dim)
            return _deserialize_vec(data, self.dim)

    def write_l3(self, beta: hrr.Array) -> None:
        with self._lock:
            if self.l3_offset > 0:
                # L3 exists and wasn't invalidated — overwrite in place
                self._file.seek(self.l3_offset)
                self._write_l3_raw(beta)
                self._file.flush()
                try:
                    os.fsync(self._file.fileno())
                except OSError as e:
                    logger.warning("fsync failed after write_l3 (in-place): %s", e)
                return

            # Append L3 at file end (after L2), update header
            self._file.seek(0, 2)
            self.l3_offset = self._file.tell()
            self._write_l3_raw(beta)
            self._file.seek(0)
            self._write_header(self._file)
            self._file.flush()
            try:
                os.fsync(self._file.fileno())
            except OSError as e:
                logger.warning("fsync failed after write_l3: %s", e)

    # ── Utility ───────────────────────────────────────────────────

    def info(self) -> dict[str, Any]:
        try:
            buckets = self.read_l2()
            bucket_stats = {
                "count": len(buckets),
                "non_empty": sum(1 for b in buckets if b.entry_ids),
            }
        except Exception as e:
            logger.warning("read_l2 failed in info(): %s", e)
            bucket_stats = {"count": self.l2_bucket_count, "non_empty": 0}

        return {
            "path": self.path,
            "dim": self.dim,
            "entries": self.entry_count,
            "l1_data_size": self.l1_data_size,
            "l3_offset": self.l3_offset,
            "l2_buckets": bucket_stats,
            "file_size": os.path.getsize(self.path) if os.path.isfile(self.path) else 0,
            "has_numpy": hrr.has_numpy(),
        }
