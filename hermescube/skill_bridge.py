"""Bridge approved Cube procedure drafts into Hermes-native skills.

Cube never silently writes into ~/.hermes/skills. Installation requires an
explicit install_to_skills=True consent path and still leaves a Cube record.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def skills_dir(hermes_home: str | Path) -> Path:
    return Path(hermes_home) / "skills"


def _parse_name(markdown: str, fallback: str) -> str:
    m = _FRONT_RE.match(markdown or "")
    if m:
        for line in m.group(1).splitlines():
            if line.strip().startswith("name:"):
                return line.split(":", 1)[1].strip().strip("\"'")
    return fallback


def install_approved_draft(
    name: str,
    *,
    hermes_home: str | Path,
    cube: Any = None,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Copy an approved procedure draft into Hermes skills/ as SKILL.md."""
    home = Path(hermes_home)
    approved = home / "memories" / "procedures" / "approved"
    src = approved / Path(name).name
    if not src.name.endswith(".md"):
        src = approved / f"{Path(name).name}.md"
    if not src.is_file():
        matches = list(approved.glob(f"*{name}*")) if name else []
        matches = [m for m in matches if m.is_file() and m.suffix == ".md"]
        if len(matches) == 1:
            src = matches[0]
        else:
            return {"ok": False, "error": f"approved draft not found: {name}"}

    text = src.read_text(encoding="utf-8")
    skill_name = _parse_name(text, src.stem)
    # sanitize skill folder name
    safe = re.sub(r"[^a-z0-9._-]+", "-", skill_name.lower()).strip("-") or "hermescube-skill"
    dest_dir = skills_dir(home) / safe
    dest = dest_dir / "SKILL.md"
    if dest.is_file() and not overwrite:
        return {
            "ok": False,
            "error": f"skill already exists: {dest}",
            "hint": "pass overwrite=true to replace",
        }
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Ensure origin tag in frontmatter
    if "origin: hermescube-procedure-forge" not in text:
        if text.startswith("---"):
            text = text.replace("---\n", "---\norigin: hermescube-skill-bridge\n", 1)
        else:
            text = (
                "---\n"
                f"name: {safe}\n"
                "origin: hermescube-skill-bridge\n"
                "---\n\n"
                + text
            )
    dest.write_text(text, encoding="utf-8")

    rec: dict[str, Any] = {
        "ok": True,
        "action": "installed_skill",
        "skill_dir": str(dest_dir),
        "skill_path": str(dest),
        "from_draft": str(src),
        "name": safe,
    }
    # ledger
    ledger = home / "memories" / "procedures" / "skill_install_log.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "action": "install_skill",
                    "name": safe,
                    "path": str(dest),
                    "from": str(src),
                }
            )
            + "\n"
        )

    if cube is not None:
        try:
            e = cube.append(
                entry_type="evolution",
                description=f"[SKILL INSTALLED] {safe}",
                data={
                    "source": "skill_bridge",
                    "procedure": True,
                    "skill_path": str(dest),
                    "from_draft": src.name,
                    "trust": 0.9,
                    "durable": True,
                    "verification": "user_authored",
                },
                outcome="success",
            )
            rec["entry_id"] = getattr(e, "id", None)
        except Exception as ex:
            rec["cube_error"] = str(ex)
    return rec


def promote_and_optionally_install(
    name: str,
    *,
    hermes_home: str | Path,
    cube: Any = None,
    install_to_skills: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Promote draft to approved/, optionally install into Hermes skills/."""
    from hermescube.consent import promote

    result = promote(name, hermes_home=hermes_home, cube=cube)
    if not result.get("ok"):
        return result
    if not install_to_skills:
        result["installed"] = False
        return result
    # After promote, draft lives under approved/
    approved_name = Path(result.get("path") or name).name
    inst = install_approved_draft(
        approved_name,
        hermes_home=hermes_home,
        cube=cube,
        overwrite=overwrite,
    )
    result["installed"] = bool(inst.get("ok"))
    result["install"] = inst
    return result
