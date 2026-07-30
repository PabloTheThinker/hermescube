"""Terminal connect layer — any Hermes user ↔ their own HermesCube library.

This is the TLI/CLI surface for day-one:

  hermescube setup     # wire plugin + provider + empty book if needed
  hermescube connect   # ensure this HERMES_HOME is attached (idempotent)
  hermescube status    # human library status

Each Hermes home / profile owns **one** book under::

  $HERMES_HOME/memories/memory.cube

Agents never share cubes unless they share HERMES_HOME (or opt into Hive).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def hermes_home(override: str | None = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser().resolve()


def cube_path(home: Path | None = None) -> Path:
    h = home or hermes_home()
    return h / "memories" / "memory.cube"


def plugin_dir(home: Path | None = None) -> Path:
    h = home or hermes_home()
    return h / "plugins" / "hermescube"


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
            timeout=120,
        )
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode, out
    except FileNotFoundError:
        return 127, "command not found"
    except Exception as e:
        return 1, str(e)


def find_hermes_bin() -> str | None:
    candidates = [
        shutil.which("hermes"),
        str(Path.home() / "hermes-agent" / "venv" / "bin" / "hermes"),
        str(Path.home() / ".local" / "bin" / "hermes"),
    ]
    # optional: dirname(hermes)/python sibling installs
    for c in candidates:
        if c and Path(c).is_file() and os.access(c, os.X_OK):
            return c
    return None


def ensure_dirs(home: Path) -> None:
    (home / "memories").mkdir(parents=True, exist_ok=True)
    (home / "plugins").mkdir(parents=True, exist_ok=True)
    (home / "memories" / "blackbox").mkdir(parents=True, exist_ok=True)
    (home / "memories" / "checkpoints").mkdir(parents=True, exist_ok=True)


def ensure_cube(home: Path, *, dim: int = 256, buckets: int = 64) -> dict[str, Any]:
    from hermescube.cube import CubeFile

    path = cube_path(home)
    if path.is_file():
        return {"ok": True, "created": False, "path": str(path)}
    path.parent.mkdir(parents=True, exist_ok=True)
    CubeFile.create(str(path), dim=dim, l2_buckets=buckets)
    return {"ok": True, "created": True, "path": str(path), "dim": dim, "buckets": buckets}


def read_provider(home: Path) -> str:
    cfg = home / "config.yaml"
    if not cfg.is_file():
        return ""
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    # light parse — avoid requiring pyyaml always
    in_memory = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("memory:") and not s.startswith("memory_"):
            in_memory = True
            continue
        if in_memory:
            if s and not s.startswith("#") and not line.startswith(" ") and not line.startswith("\t"):
                # left memory block
                if not s.startswith("provider"):
                    in_memory = False
            if s.startswith("provider:"):
                return s.split(":", 1)[1].strip().strip("'\"")
    return ""


def set_provider_hermescube(home: Path) -> dict[str, Any]:
    """Set memory.provider=hermescube via hermes config or direct yaml patch."""
    hermes = find_hermes_bin()
    env = os.environ.copy()
    env["HERMES_HOME"] = str(home)
    if hermes:
        code, out = _run(
            [hermes, "config", "set", "memory.provider", "hermescube"],
            env=env,
        )
        if code == 0:
            return {"ok": True, "method": "hermes config set", "detail": out.strip()[:200]}
    # fallback: patch config.yaml
    cfg = home / "config.yaml"
    if not cfg.is_file():
        cfg.write_text("memory:\n  provider: hermescube\n  memory_enabled: true\n  user_profile_enabled: true\n")
        return {"ok": True, "method": "wrote config.yaml", "detail": "created minimal config"}
    text = cfg.read_text(encoding="utf-8", errors="replace")
    if "provider: hermescube" in text or 'provider: "hermescube"' in text:
        return {"ok": True, "method": "already", "detail": "provider already hermescube"}
    # inject under memory: block
    lines = text.splitlines()
    out_lines: list[str] = []
    injected = False
    i = 0
    while i < len(lines):
        line = lines[i]
        out_lines.append(line)
        if line.strip() == "memory:" or line.strip().startswith("memory:"):
            # next indented lines — replace provider or add
            j = i + 1
            block: list[str] = []
            while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t") or not lines[j].strip()):
                block.append(lines[j])
                j += 1
            new_block: list[str] = []
            saw_provider = False
            for b in block:
                if b.strip().startswith("provider:"):
                    new_block.append("  provider: hermescube")
                    saw_provider = True
                else:
                    new_block.append(b)
            if not saw_provider:
                new_block.insert(0, "  provider: hermescube")
            out_lines.extend(new_block)
            i = j
            injected = True
            continue
        i += 1
    if not injected:
        out_lines.append("")
        out_lines.append("memory:")
        out_lines.append("  provider: hermescube")
    cfg.write_text("\n".join(out_lines) + "\n")
    return {"ok": True, "method": "patched config.yaml", "detail": "memory.provider=hermescube"}


def ensure_plugin_link(home: Path, *, source: Path | None = None) -> dict[str, Any]:
    """Ensure $HERMES_HOME/plugins/hermescube points at an install."""
    dest = plugin_dir(home)
    if (dest / "plugin.yaml").is_file() or (dest / "hermescube" / "__init__.py").is_file():
        return {"ok": True, "path": str(dest), "linked": False, "note": "plugin present"}

    # prefer this checkout
    candidates = []
    if source:
        candidates.append(source)
    here = Path(__file__).resolve().parent.parent  # package root
    candidates.append(here)
    env_src = os.environ.get("HERMESCUBE_SOURCE")
    if env_src:
        candidates.insert(0, Path(env_src))

    for c in candidates:
        if (c / "plugin.yaml").is_file() and (c / "hermescube").is_dir():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                if dest.is_symlink() or dest.is_file():
                    dest.unlink()
                else:
                    return {
                        "ok": False,
                        "error": f"{dest} exists and is not empty plugin — remove or use install_hermes.sh",
                    }
            try:
                dest.symlink_to(c, target_is_directory=True)
                return {"ok": True, "path": str(dest), "linked": True, "source": str(c)}
            except OSError:
                # copy minimal
                shutil.copytree(
                    c,
                    dest,
                    ignore=shutil.ignore_patterns(
                        ".git", ".venv", "venv", "__pycache__", "*.pyc", "tests", ".pytest_cache"
                    ),
                    dirs_exist_ok=True,
                )
                return {"ok": True, "path": str(dest), "linked": False, "copied": True, "source": str(c)}
    return {
        "ok": False,
        "error": "No hermescube source found. git clone PabloTheThinker/hermescube or hermes plugins install",
    }


def connect(
    *,
    hermes_home_override: str | None = None,
    create_cube: bool = True,
    set_provider: bool = True,
    ensure_plugin: bool = True,
) -> dict[str, Any]:
    """Idempotent: attach this HERMES_HOME to its own Cube library."""
    home = hermes_home(hermes_home_override)
    report: dict[str, Any] = {
        "ok": False,
        "hermes_home": str(home),
        "cube": str(cube_path(home)),
        "steps": {},
    }
    ensure_dirs(home)
    report["steps"]["dirs"] = {"ok": True}

    if ensure_plugin:
        report["steps"]["plugin"] = ensure_plugin_link(home)
    else:
        report["steps"]["plugin"] = {"ok": True, "skipped": True}

    if create_cube:
        report["steps"]["cube"] = ensure_cube(home)
    else:
        report["steps"]["cube"] = {
            "ok": cube_path(home).is_file(),
            "path": str(cube_path(home)),
            "created": False,
        }

    if set_provider:
        report["steps"]["provider"] = set_provider_hermescube(home)
    else:
        report["steps"]["provider"] = {"ok": True, "skipped": True, "current": read_provider(home)}

    prov = read_provider(home)
    report["provider"] = prov or read_provider(home)
    report["hermes_bin"] = find_hermes_bin()
    report["ok"] = bool(
        report["steps"]["cube"].get("ok")
        and report["steps"]["provider"].get("ok")
        and (not ensure_plugin or report["steps"]["plugin"].get("ok"))
    )
    # seal the vault modes after connect
    try:
        from hermescube.security import harden_home_permissions

        report["steps"]["harden"] = harden_home_permissions(home)
    except Exception as e:
        report["steps"]["harden"] = {"ok": False, "error": str(e)}
    report["next"] = [
        "Restart Hermes gateway / Desktop / agent session so memory.provider loads",
        "hermescube status",
        "hermescube security audit",
        "hermescube query \"what should I remember?\"",
        "hermescube checkpoint create --name first-lock",
    ]
    return report


def setup(
    *,
    hermes_home_override: str | None = None,
    run_install_script: bool = True,
) -> dict[str, Any]:
    """Fuller setup: optional install_hermes.sh then connect."""
    home = hermes_home(hermes_home_override)
    out: dict[str, Any] = {"ok": False, "hermes_home": str(home), "install": None, "connect": None}
    ensure_dirs(home)

    if run_install_script:
        # find install script near package
        root = Path(__file__).resolve().parent.parent
        script = root / "scripts" / "install_hermes.sh"
        if script.is_file():
            env = os.environ.copy()
            env["HERMES_HOME"] = str(home)
            code, text = _run(["bash", str(script)], env=env)
            out["install"] = {"ok": code == 0, "exit": code, "log_tail": text[-1500:]}
        else:
            out["install"] = {"ok": True, "skipped": True, "note": "no install_hermes.sh"}

    out["connect"] = connect(
        hermes_home_override=str(home),
        create_cube=True,
        set_provider=True,
        ensure_plugin=True,
    )
    out["ok"] = bool(out["connect"].get("ok"))
    return out


def status_report(hermes_home_override: str | None = None) -> dict[str, Any]:
    """Friendly library status for terminal users."""
    from hermescube import center

    home = hermes_home(hermes_home_override)
    path = cube_path(home)
    st = center.center_status(hermes_home=str(home))
    heart = st.get("heart") or {}
    return {
        "ok": bool(st.get("ok") and path.is_file()),
        "hermes_home": str(home),
        "cube_path": str(path),
        "cube_exists": path.is_file(),
        "provider": read_provider(home) or "(unset)",
        "plugin_present": (plugin_dir(home) / "plugin.yaml").is_file()
        or plugin_dir(home).is_symlink(),
        "heart_ready": heart.get("heart_ready"),
        "entries": heart.get("entries"),
        "center_api": st.get("api_version"),
        "organs": list((st.get("organs") or {}).keys()),
        "hermes_bin": find_hermes_bin(),
        "library_line": (
            "HermesCube is the library under Hermes — "
            "your book lives at memories/memory.cube for this HERMES_HOME only."
        ),
    }


def format_status(s: dict[str, Any]) -> str:
    lines = [
        "HermesCube — your library",
        f"  HERMES_HOME:  {s.get('hermes_home')}",
        f"  Book:         {s.get('cube_path')}  ({'exists' if s.get('cube_exists') else 'MISSING'})",
        f"  Provider:     {s.get('provider')}",
        f"  Plugin:       {'yes' if s.get('plugin_present') else 'no'}",
        f"  Heart ready:  {s.get('heart_ready')}",
        f"  Entries:      {s.get('entries')}",
        f"  Center API:   {s.get('center_api')}",
        f"  Hermes CLI:   {s.get('hermes_bin') or 'not on PATH'}",
        "",
        s.get("library_line") or "",
    ]
    if s.get("provider") != "hermescube":
        lines.append("")
        lines.append("  → Run: hermescube connect")
    if not s.get("cube_exists"):
        lines.append("  → Run: hermescube connect   # creates empty book")
    return "\n".join(lines)


def format_connect(r: dict[str, Any]) -> str:
    lines = [
        "HermesCube connect",
        f"  HERMES_HOME: {r.get('hermes_home')}",
        f"  ok:          {r.get('ok')}",
    ]
    for name, step in (r.get("steps") or {}).items():
        lines.append(f"  [{name}] {step}")
    lines.append(f"  provider now: {r.get('provider')}")
    lines.append("")
    lines.append("Next:")
    for n in r.get("next") or []:
        lines.append(f"  · {n}")
    return "\n".join(lines)
