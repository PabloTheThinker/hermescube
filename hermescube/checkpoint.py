"""Identity ark / safe-lock checkpoints for HermesCube.

The cube is the library book. A **checkpoint** (safe lock) is a flash clone of:
  - the bound volume (memory.cube + optional dense)
  - core identity on the desk (SOUL.md, MEMORY.md, USER.md)
  - light Hermes config (config.yaml — no .env secrets by default)

If the live library is lost or the agent restarts "fresh," the user can restore
from a named arc checkpoint — a copy of who the agent was at that shelf mark.

Halo-style mental model (functional, not cosplay): a Weapon-like **pre-story
snapshot** of the mind's core — identity + long memory — portable and offline.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_NAME = "ark-manifest.json"
DEFAULT_INCLUDE_IDENTITY = (
    "SOUL.md",
    "memories/MEMORY.md",
    "memories/USER.md",
    "memories/CUBE.md",
)
DEFAULT_INCLUDE_CUBE = (
    "memories/memory.cube",
    "memories/memory.cube.wal",
    "memories/memory.cubelog",
)
# Optional extras when present (never .env)
OPTIONAL_FILES = (
    "config.yaml",
    "memories/relations.sqlite3",
    "memories/triage_plan.json",
    "memories/candidates.jsonl",
)


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _hermes_home(home: str | Path | None = None) -> Path:
    if home:
        return Path(home)
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def checkpoints_root(hermes_home: str | Path | None = None) -> Path:
    return _hermes_home(hermes_home) / "memories" / "checkpoints"


def _sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _copy_if_exists(src: Path, dest: Path) -> dict[str, Any] | None:
    if not src.is_file():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        "path": str(src.name if src.parent.name != "memories" else f"memories/{src.name}"),
        "rel": str(dest.relative_to(dest.parents[len(dest.parts) - len(src.parts) + 1]))
        if False
        else None,
        "bytes": dest.stat().st_size,
        "sha256": _sha256_file(dest),
    }


def create_checkpoint(
    name: str | None = None,
    *,
    hermes_home: str | Path | None = None,
    label: str = "",
    include_config: bool = True,
    include_dense: bool = False,
    pack_tar: bool = True,
) -> dict[str, Any]:
    """Create a safe-lock checkpoint (identity arc + cube book)."""
    from hermescube.security import (
        SecurityError,
        assert_under_home,
        harden_home_permissions,
        is_forbidden_rel,
        resolve_hermes_home,
        scan_file_for_secrets,
        validate_checkpoint_sources,
    )

    home = resolve_hermes_home(hermes_home)
    stamp = _utc_stamp()
    slug = (name or f"ark-{stamp}").strip().replace(" ", "-")
    # slug must be a single path segment
    if "/" in slug or "\\" in slug or slug in (".", "..") or ".." in slug:
        return {"ok": False, "error": "invalid checkpoint name"}
    root = checkpoints_root(home)
    assert_under_home(root, home, label="checkpoints_root")
    dest = root / slug
    if dest.exists():
        dest = root / f"{slug}-{stamp}"
        slug = dest.name
    dest.mkdir(parents=True, exist_ok=False)
    assert_under_home(dest, home, label="checkpoint_dest")
    files_meta: list[dict[str, Any]] = []

    candidates: list[str] = [str(x) for x in (*DEFAULT_INCLUDE_IDENTITY, *DEFAULT_INCLUDE_CUBE)]
    if include_config:
        candidates.append("config.yaml")
    for rel in OPTIONAL_FILES:
        if rel == "config.yaml":
            continue
        candidates.append(rel)

    rejected = validate_checkpoint_sources(home, candidates)
    # only hard-fail forbidden; secret-in-config.yaml → skip that file
    hard = [r for r in rejected if r.startswith("forbidden") or "escapes" in r]
    if hard:
        return {"ok": False, "error": "security rejected sources", "reasons": hard}

    skip_rels = set()
    for r in rejected:
        if "secret-pattern in " in r:
            skip_rels.add(r.split("secret-pattern in ", 1)[1].split(":", 1)[0].strip())

    def take(rel: str) -> None:
        if is_forbidden_rel(rel) or rel in skip_rels:
            return
        src = home / rel
        if not src.is_file():
            return
        try:
            assert_under_home(src, home, label=rel)
        except SecurityError:
            return
        # extra scan
        if scan_file_for_secrets(src):
            return
        out = dest / rel
        assert_under_home(out, home, label=f"ckpt:{rel}")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        try:
            out.chmod(0o600)
        except OSError:
            pass
        files_meta.append(
            {
                "rel": rel,
                "bytes": out.stat().st_size,
                "sha256": _sha256_file(out),
            }
        )

    for rel in candidates:
        take(rel)

    if include_dense:
        try:
            from hermescube.dense import export_dense

            cube = home / "memories" / "memory.cube"
            if cube.is_file():
                dense_out = dest / "memories" / "memory.dense.jsonl.gz"
                dense_out.parent.mkdir(parents=True, exist_ok=True)
                export_dense(cube, dense_out)
                try:
                    dense_out.chmod(0o600)
                except OSError:
                    pass
                files_meta.append(
                    {
                        "rel": "memories/memory.dense.jsonl.gz",
                        "bytes": dense_out.stat().st_size,
                        "sha256": _sha256_file(dense_out),
                    }
                )
        except Exception as e:
            files_meta.append({"rel": "memories/memory.dense.jsonl.gz", "error": str(e)})

    manifest = {
        "schema": "hermescube.ark.v1",
        "kind": "identity_arc_checkpoint",
        "slug": slug,
        "label": label or slug,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "hermes_home": str(home),
        "security": {
            "no_env": True,
            "path_contained": True,
            "secret_scan": True,
            "skipped": sorted(skip_rels),
        },
        "note": (
            "Safe lock: flash clone of cube book + core identity. "
            "Does not include .env secrets. Restore only onto the same logical home."
        ),
        "files": files_meta,
        "excludes": [".env", "auth.json", "*.pem", "credentials"],
    }
    man_path = dest / MANIFEST_NAME
    man_path.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        man_path.chmod(0o600)
    except OSError:
        pass
    manifest["manifest_sha256"] = _sha256_file(man_path)

    tar_path = None
    if pack_tar:
        tar_path = root / f"{slug}.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(dest, arcname=slug)
        try:
            tar_path.chmod(0o600)
        except OSError:
            pass
        manifest["archive"] = {
            "path": str(tar_path),
            "bytes": tar_path.stat().st_size,
            "sha256": _sha256_file(tar_path),
        }
        man_path.write_text(json.dumps(manifest, indent=2) + "\n")

    harden_home_permissions(home)

    # Hold the line — ark exists even if cube later breaks
    try:
        from hermescube.blackbox.hold_line import record as hold_record

        bb = hold_record(
            hermes_home=home,
            organ="checkpoint",
            event="create",
            summary=f"ark {slug}: {manifest.get('label') or slug}",
            payload={
                "slug": slug,
                "path": str(dest),
                "files": len(files_meta),
                "archive": str(tar_path) if tar_path else None,
                "label": manifest.get("label"),
            },
            ref_id=slug,
            severity="high",
        )
    except Exception as e:
        bb = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "slug": slug,
        "path": str(dest),
        "archive": str(tar_path) if tar_path else None,
        "files": len(files_meta),
        "label": manifest["label"],
        "created_at": manifest["created_at"],
        "skipped_sensitive": sorted(skip_rels),
        "blackbox": bb,
    }


def list_checkpoints(hermes_home: str | Path | None = None) -> list[dict[str, Any]]:
    root = checkpoints_root(hermes_home)
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / MANIFEST_NAME).is_file():
            try:
                man = json.loads((p / MANIFEST_NAME).read_text())
            except Exception:
                man = {}
            out.append(
                {
                    "slug": p.name,
                    "path": str(p),
                    "label": man.get("label") or p.name,
                    "created_at": man.get("created_at"),
                    "files": len(man.get("files") or []),
                    "archive": (man.get("archive") or {}).get("path"),
                }
            )
        elif p.suffixes[-2:] == [".tar", ".gz"] or p.name.endswith(".tar.gz"):
            out.append({"slug": p.name, "path": str(p), "label": p.name, "kind": "tarball"})
    return out


def restore_checkpoint(
    slug: str,
    *,
    hermes_home: str | Path | None = None,
    restore_identity: bool = True,
    restore_cube: bool = True,
    restore_config: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore a safe-lock onto HERMES_HOME (destructive to live book/identity)."""
    from hermescube.security import (
        SecurityError,
        assert_under_home,
        harden_home_permissions,
        is_forbidden_rel,
        resolve_hermes_home,
        scan_file_for_secrets,
    )

    home = resolve_hermes_home(hermes_home)
    root = checkpoints_root(home)
    assert_under_home(root, home, label="checkpoints_root")
    if "/" in slug or "\\" in slug or ".." in slug:
        return {"ok": False, "error": "invalid slug"}
    src = root / slug
    if not src.is_dir():
        candidates = [p for p in root.glob("*") if p.is_dir() and (p.name == slug or p.name.startswith(slug))]
        if not candidates:
            return {"ok": False, "error": f"checkpoint not found: {slug}"}
        src = candidates[0]
    try:
        assert_under_home(src, home, label="checkpoint_src")
    except SecurityError as e:
        return {"ok": False, "error": str(e)}

    man_path = src / MANIFEST_NAME
    if not man_path.is_file():
        return {"ok": False, "error": "missing ark-manifest.json"}

    man = json.loads(man_path.read_text())
    # refuse restore if manifest claims a different home host path *and* cube missing? 
    # Allow restore onto current home always (user intent) but never read files outside src.
    planned: list[str] = []
    restored: list[str] = []
    blocked: list[str] = []

    for f in man.get("files") or []:
        rel = f.get("rel") or ""
        if not rel or is_forbidden_rel(rel):
            if rel:
                blocked.append(rel)
            continue
        if ".." in Path(rel).parts:
            blocked.append(rel)
            continue
        is_id = rel in DEFAULT_INCLUDE_IDENTITY or rel.endswith("SOUL.md")
        is_cube = "memory.cube" in rel or rel.endswith(".cubelog") or rel.endswith(".wal")
        is_cfg = rel == "config.yaml"
        if is_id and not restore_identity:
            continue
        if is_cube and not restore_cube:
            continue
        if is_cfg and not restore_config:
            continue
        if not is_id and not is_cube and not is_cfg and "relations" not in rel:
            if not restore_config:
                continue

        s = src / rel
        d = home / rel
        try:
            assert_under_home(s, home, label=f"src:{rel}")
            assert_under_home(d, home, label=f"dst:{rel}")
        except SecurityError:
            blocked.append(rel)
            continue
        if scan_file_for_secrets(s):
            blocked.append(f"{rel}:secret")
            continue
        planned.append(rel)
        if dry_run:
            continue
        if not s.is_file():
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.is_file():
            bak = d.with_suffix(d.suffix + f".pre-restore-{_utc_stamp()}")
            shutil.copy2(d, bak)
            try:
                bak.chmod(0o600)
            except OSError:
                pass
        shutil.copy2(s, d)
        try:
            d.chmod(0o600)
        except OSError:
            pass
        restored.append(rel)

    if not dry_run:
        harden_home_permissions(home)

    return {
        "ok": True,
        "slug": slug,
        "dry_run": dry_run,
        "planned": planned,
        "restored": restored,
        "blocked": blocked,
        "warning": "Restart Hermes gateway/desktop after restore so identity + provider reload.",
    }
