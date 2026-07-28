"""First-run bootstrap — import hot Hermes memories + install Cube skills.

When an agent connects to an empty (or never-bootstrapped) warehouse, this
module seeds the cube from MEMORY.md / USER.md / SOUL.md and installs the
bundled HermesCube skills so the agent instantly knows how to operate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Any

from hermescube.threats import has_blockable_threat, sanitize_for_storage

logger = logging.getLogger(__name__)

BOOTSTRAP_STATE = "bootstrap_state.json"
MAX_IMPORT_LINES = 240
MAX_LINE_CHARS = 400

# Packaged skills shipped with the plugin (repo skills/ → HERMES_HOME/skills/)
BUNDLED_SKILLS = (
    "hermescube-operate",
    "hermescube-import",
    "interview-me",
)

_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$")
_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s+")


def bootstrap_state_path(hermes_home: str | Path | None) -> Path:
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    return home / "memories" / BOOTSTRAP_STATE


def load_bootstrap_state(hermes_home: str | Path | None) -> dict[str, Any]:
    path = bootstrap_state_path(hermes_home)
    if not path.is_file():
        return {"imported_hashes": [], "skills_installed": [], "runs": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"imported_hashes": [], "skills_installed": [], "runs": []}
        data.setdefault("imported_hashes", [])
        data.setdefault("skills_installed", [])
        data.setdefault("runs", [])
        return data
    except Exception:
        return {"imported_hashes": [], "skills_installed": [], "runs": []}


def save_bootstrap_state(hermes_home: str | Path | None, state: dict[str, Any]) -> None:
    path = bootstrap_state_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    hashes = list(state.get("imported_hashes") or [])
    if len(hashes) > 8000:
        hashes = hashes[-8000:]
    state = dict(state)
    state["imported_hashes"] = hashes
    state["updated_at"] = time.time()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def _line_hash(source: str, text: str) -> str:
    return hashlib.sha256(f"{source}|{text.strip().lower()}".encode()).hexdigest()[:24]


def parse_memory_markdown(text: str, *, source: str = "MEMORY.md") -> list[dict[str, str]]:
    """Extract durable fact lines from Hermes markdown memory files.

    Prefer bullets; also keep short non-header paragraphs (1–2 sentences).
    """
    if not text or not text.strip():
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    section = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if _HEADER_RE.match(line):
            section = _HEADER_RE.sub("", line).strip()[:80]
            continue
        m = _BULLET_RE.match(line)
        if m:
            body = m.group(1).strip()
        else:
            # Short standalone fact lines (not code fences / tables)
            body = line.strip()
            if body.startswith(("```", "|", ">", "<!--")):
                continue
            if len(body) < 12 or len(body) > MAX_LINE_CHARS:
                continue
            # Skip pure links / navigation fluff
            if body.startswith(("http://", "https://", "[")) and len(body) < 40:
                continue
        body = sanitize_for_storage(body, MAX_LINE_CHARS)
        if not body or len(body) < 8:
            continue
        if has_blockable_threat(body):
            continue
        key = body.lower()
        if key in seen:
            continue
        seen.add(key)
        entry_type = "trait" if "USER" in source.upper() else "belief"
        if section and section.lower() in ("preferences", "traits", "style"):
            entry_type = "trait"
        elif section and section.lower() in ("people", "relationships", "contacts"):
            entry_type = "relationship"
        elif section and section.lower() in ("paths", "locations", "landmarks"):
            entry_type = "landmark"
        desc = body
        if section and not body.lower().startswith(section.lower()[:20].lower()):
            # Keep section as soft context without drowning the fact
            pass
        out.append(
            {
                "entry_type": entry_type,
                "description": desc,
                "source": source,
                "section": section,
            }
        )
        if len(out) >= MAX_IMPORT_LINES:
            break
    return out


def discover_hot_memory_files(hermes_home: str | Path | None) -> list[Path]:
    """Find Hermes hot-memory markdown files worth importing."""
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    names = ("MEMORY.md", "USER.md", "SOUL.md", "AGENTS.md")
    found: list[Path] = []
    for name in names:
        # Common Hermes layouts
        for candidate in (
            home / name,
            home / "memories" / name,
            home / "agent" / name,
        ):
            if candidate.is_file() and candidate not in found:
                found.append(candidate)
                break
    return found


def package_skills_root() -> Path | None:
    """Locate bundled skills/ next to the installed package or repo root."""
    here = Path(__file__).resolve()
    # hermescube/hermescube/bootstrap.py → repo skills/
    repo = here.parents[1] / "skills"
    if repo.is_dir():
        return repo
    # plugin tree: plugins/hermescube/skills
    plugin = here.parents[1]
    alt = plugin / "skills"
    if alt.is_dir():
        return alt
    return None


def install_bundled_skills(
    hermes_home: str | Path | None,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy packaged Cube skills into ``$HERMES_HOME/skills/``."""
    home = Path(hermes_home) if hermes_home else Path.home() / ".hermes"
    src_root = package_skills_root()
    dest_root = home / "skills"
    report: dict[str, Any] = {
        "ok": True,
        "dest": str(dest_root),
        "installed": [],
        "skipped": [],
        "missing": [],
    }
    if src_root is None:
        report["ok"] = False
        report["error"] = "bundled skills/ not found beside package"
        return report
    dest_root.mkdir(parents=True, exist_ok=True)
    for name in BUNDLED_SKILLS:
        src = src_root / name / "SKILL.md"
        if not src.is_file():
            report["missing"].append(name)
            continue
        dest_dir = dest_root / name
        dest = dest_dir / "SKILL.md"
        if dest.is_file() and not overwrite:
            # Refresh if packaged skill is newer / different version tag
            try:
                if dest.read_text(encoding="utf-8") == src.read_text(encoding="utf-8"):
                    report["skipped"].append(name)
                    continue
            except OSError:
                pass
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        report["installed"].append(name)
    return report


def import_hot_memories(
    cube: Any,
    hermes_home: str | Path | None,
    *,
    force: bool = False,
    max_lines: int = MAX_IMPORT_LINES,
    vault: str = "",
    session_id: str = "",
) -> dict[str, Any]:
    """Import MEMORY.md / USER.md / SOUL.md facts into the cube (idempotent)."""
    if cube is None:
        return {"ok": False, "error": "cube not open"}
    state = load_bootstrap_state(hermes_home)
    seen = set(state.get("imported_hashes") or [])
    files = discover_hot_memory_files(hermes_home)
    imported = 0
    skipped = 0
    blocked = 0
    per_file: dict[str, int] = {}
    samples: list[str] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.debug("bootstrap read skip %s: %s", path, e)
            continue
        facts = parse_memory_markdown(text, source=path.name)
        count = 0
        for fact in facts:
            if imported >= max_lines:
                break
            h = _line_hash(fact["source"], fact["description"])
            if h in seen and not force:
                skipped += 1
                continue
            desc = fact["description"]
            if has_blockable_threat(desc):
                blocked += 1
                continue
            data: dict[str, Any] = {
                "source": "bootstrap_import",
                "mirror": True,
                "durable": True,
                "trust": 0.88,
                "verification": "user_authored",
                "extension_of": fact["source"],
                "bootstrap": True,
                "evidence_state": "verified",
            }
            if fact.get("section"):
                data["section"] = fact["section"]
            if vault:
                data["vault"] = vault
            if session_id:
                data["session_id"] = session_id
            try:
                cube.append(
                    entry_type=fact["entry_type"],
                    description=desc,
                    data=data,
                    outcome="none",
                )
            except Exception as e:
                logger.debug("bootstrap append failed: %s", e)
                continue
            seen.add(h)
            imported += 1
            count += 1
            if len(samples) < 5:
                samples.append(desc[:120])
        per_file[path.name] = per_file.get(path.name, 0) + count

    state["imported_hashes"] = list(seen)
    runs = list(state.get("runs") or [])
    runs.append(
        {
            "ts": time.time(),
            "imported": imported,
            "skipped": skipped,
            "blocked": blocked,
            "files": list(per_file.keys()),
        }
    )
    state["runs"] = runs[-20:]
    state["last_import_at"] = time.time()
    state["last_imported"] = imported
    save_bootstrap_state(hermes_home, state)

    return {
        "ok": True,
        "imported": imported,
        "skipped_dupes": skipped,
        "blocked": blocked,
        "files": per_file,
        "sources_found": [str(p) for p in files],
        "samples": samples,
        "cube_entries": int(getattr(cube, "entry_count", 0) or 0),
    }


def bootstrap_status(
    cube: Any,
    hermes_home: str | Path | None,
) -> dict[str, Any]:
    """Agent-readable readiness card for first-run / re-import."""
    state = load_bootstrap_state(hermes_home)
    files = discover_hot_memory_files(hermes_home)
    entries = int(getattr(cube, "entry_count", 0) or 0) if cube is not None else 0
    skills_root = Path(hermes_home or Path.home() / ".hermes") / "skills"
    skills_ok = [
        name
        for name in BUNDLED_SKILLS
        if (skills_root / name / "SKILL.md").is_file()
    ]
    needs_import = entries == 0 or (
        bool(files) and not state.get("last_import_at") and entries < 3
    )
    return {
        "ok": True,
        "cube_entries": entries,
        "hot_files": [p.name for p in files],
        "hot_paths": [str(p) for p in files],
        "last_import_at": state.get("last_import_at"),
        "last_imported": state.get("last_imported", 0),
        "skills_installed": skills_ok,
        "skills_missing": [n for n in BUNDLED_SKILLS if n not in skills_ok],
        "needs_import": needs_import,
        "needs_skills": len(skills_ok) < len(BUNDLED_SKILLS),
        "hint": (
            "Call hermescube_manage action=bootstrap mode=all"
            if needs_import or len(skills_ok) < len(BUNDLED_SKILLS)
            else "Warehouse ready — use hermescube_search / feedback / triage"
        ),
    }


def run_bootstrap(
    cube: Any,
    hermes_home: str | Path | None,
    *,
    mode: str = "all",
    force: bool = False,
    vault: str = "",
    session_id: str = "",
    overwrite_skills: bool = False,
) -> dict[str, Any]:
    """Run status / import / skills / all — single agent entrypoint."""
    mode_l = (mode or "all").strip().lower()
    if mode_l in ("status", "doctor", "check"):
        return {"status": "bootstrap", **bootstrap_status(cube, hermes_home)}

    report: dict[str, Any] = {"status": "bootstrap", "mode": mode_l, "ok": True}

    if mode_l in ("skills", "all"):
        report["skills"] = install_bundled_skills(
            hermes_home, overwrite=overwrite_skills
        )
        st = load_bootstrap_state(hermes_home)
        installed = list(st.get("skills_installed") or [])
        for name in report["skills"].get("installed") or []:
            if name not in installed:
                installed.append(name)
        st["skills_installed"] = installed
        save_bootstrap_state(hermes_home, st)

    if mode_l in ("import", "memories", "all"):
        report["import"] = import_hot_memories(
            cube,
            hermes_home,
            force=force,
            vault=vault,
            session_id=session_id,
        )
        if not report["import"].get("ok"):
            report["ok"] = False

    report["readiness"] = bootstrap_status(cube, hermes_home)
    return report


def needs_auto_bootstrap(cube: Any, hermes_home: str | Path | None) -> bool:
    """True when initialize should quietly seed the warehouse."""
    st = bootstrap_status(cube, hermes_home)
    return bool(st.get("needs_import") or st.get("needs_skills"))
