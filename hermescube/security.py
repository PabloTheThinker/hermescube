"""Home security suite — isolation, no leakage, no cross-profile population.

Generator discipline:
  Each HERMES_HOME is a sealed library building.
  Paths never escape that home.
  Checkpoints never ship secrets.
  Profiles never share a book unless they share HERMES_HOME.

This module is the lock on the library doors.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any, Iterable

# Paths that must never leave a home / enter a checkpoint
FORBIDDEN_NAME_FRAGMENTS = (
    ".env",
    "auth.json",
    "credentials",
    "id_rsa",
    "id_ed25519",
    ".pem",
    "secret",
    "token.json",
    "oauth",
)

# High-signal secret shapes (aligned with blackbox redaction)
_SECRET_RES: list[re.Pattern[str]] = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-proj-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bxai-[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    re.compile(r"(?i)password\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


class SecurityError(RuntimeError):
    """Hard boundary violation — refuse the operation."""


def resolve_hermes_home(override: str | Path | None = None) -> Path:
    """Canonical absolute HERMES_HOME (no relative escape)."""
    if override is not None:
        raw = Path(override).expanduser()
    else:
        raw = Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()
    home = raw.resolve()
    if not home.is_absolute():
        raise SecurityError(f"HERMES_HOME must be absolute after resolve: {home}")
    return home


def assert_under_home(path: str | Path, home: str | Path, *, label: str = "path") -> Path:
    """Ensure path resolves inside home. Blocks ../ and symlink escape."""
    h = Path(home).resolve()
    p = Path(path).expanduser()
    # resolve with strict=False so missing targets still normalize
    try:
        resolved = p.resolve(strict=False)
    except TypeError:
        resolved = p.resolve()
    try:
        resolved.relative_to(h)
    except ValueError as e:
        raise SecurityError(
            f"{label} escapes HERMES_HOME boundary: {resolved} not under {h}"
        ) from e
    return resolved


def is_forbidden_rel(rel: str) -> bool:
    r = rel.replace("\\", "/").lower()
    while r.startswith("./"):
        r = r[2:]
    base = Path(r).name.lower()
    if base in {".env", "auth.json"} or base.endswith(".env"):
        return True
    if base.endswith(".pem") or base in {"id_rsa", "id_ed25519", "id_ecdsa"}:
        return True
    if base in {"credentials", "credentials.json", "token.json"}:
        return True
    parts = r.split("/")
    if ".env" in parts or "credentials" in parts:
        return True
    return False


def scan_text_for_secrets(text: str) -> list[str]:
    hits: list[str] = []
    for pat in _SECRET_RES:
        if pat.search(text or ""):
            hits.append(pat.pattern[:40])
    return hits


def scan_file_for_secrets(path: Path, *, max_bytes: int = 2_000_000) -> list[str]:
    if not path.is_file():
        return []
    # skip pure binary cube
    if path.suffix in {".cube", ".sqlite3", ".db", ".gz", ".wal"} or path.name.endswith(".cubelog"):
        return []
    try:
        data = path.read_bytes()[:max_bytes]
    except OSError:
        return ["unreadable"]
    # binary sniff
    if b"\x00" in data[:1024]:
        return []
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return []
    return scan_text_for_secrets(text)


def harden_home_permissions(home: str | Path) -> dict[str, Any]:
    """Tighten modes on the library vault (best-effort, no sudo)."""
    h = resolve_hermes_home(home)
    changed: list[str] = []
    notes: list[str] = []

    def chmod(path: Path, mode: int) -> None:
        if not path.exists():
            return
        try:
            path.chmod(mode)
            changed.append(f"{oct(mode)} {path}")
        except OSError as e:
            notes.append(f"chmod fail {path}: {e}")

    # directory vaults
    for rel, mode in (
        ("", 0o700),  # HERMES_HOME itself if we own it — careful: may be 755 shared
        ("memories", 0o700),
        ("memories/checkpoints", 0o700),
        ("memories/blackbox", 0o700),
        ("memories/harness", 0o700),
        ("plugins", 0o755),
    ):
        p = h / rel if rel else h
        if rel == "" and p.exists():
            # only tighten home if owned by us
            try:
                if p.stat().st_uid == os.getuid():
                    chmod(p, mode)
            except OSError:
                pass
        else:
            chmod(p, mode)

    # sensitive files
    for rel, mode in (
        ("SOUL.md", 0o600),
        ("memories/MEMORY.md", 0o600),
        ("memories/USER.md", 0o600),
        ("memories/CUBE.md", 0o600),
        ("memories/memory.cube", 0o600),
        ("memories/relations.sqlite3", 0o600),
        ("config.yaml", 0o600),
        (".env", 0o600),
        ("auth.json", 0o600),
    ):
        chmod(h / rel, mode)

    # all checkpoint trees
    ck = h / "memories" / "checkpoints"
    if ck.is_dir():
        for root, dirs, files in os.walk(ck):
            try:
                Path(root).chmod(0o700)
            except OSError:
                pass
            for fn in files:
                fp = Path(root) / fn
                try:
                    fp.chmod(0o600)
                except OSError:
                    pass

    return {"ok": True, "changed": changed[:50], "changed_n": len(changed), "notes": notes}


def audit_home(home: str | Path | None = None) -> dict[str, Any]:
    """Full security audit for one HERMES_HOME (generator isolation)."""
    h = resolve_hermes_home(home)
    findings: list[dict[str, Any]] = []
    ok = True

    def find(sev: str, code: str, msg: str, **extra: Any) -> None:
        nonlocal ok
        if sev in ("high", "critical"):
            ok = False
        findings.append({"severity": sev, "code": code, "message": msg, **extra})

    # 1. home exists
    if not h.is_dir():
        find("critical", "home_missing", f"HERMES_HOME missing: {h}")
        return {"ok": False, "hermes_home": str(h), "findings": findings}

    # 2. cube only under memories/
    cube = h / "memories" / "memory.cube"
    if cube.is_file():
        try:
            assert_under_home(cube, h, label="memory.cube")
        except SecurityError as e:
            find("critical", "cube_escape", str(e))
        mode = stat.S_IMODE(cube.stat().st_mode)
        if mode & 0o077:
            find("high", "cube_world_readable", f"memory.cube mode {oct(mode)} allows group/other", path=str(cube))
    else:
        find("medium", "cube_missing", "memory.cube not created yet")

    # 3. .env must never be world-readable
    envp = h / ".env"
    if envp.is_file():
        mode = stat.S_IMODE(envp.stat().st_mode)
        if mode & 0o077:
            find("critical", "env_leaky", f".env mode {oct(mode)} — secrets exposure risk", path=str(envp))
        # never under checkpoints
        ck = h / "memories" / "checkpoints"
        if ck.is_dir():
            for hit in ck.rglob(".env"):
                find("critical", "env_in_checkpoint", f".env found inside checkpoint tree: {hit}")

    # 4. checkpoint hygiene
    ck_root = h / "memories" / "checkpoints"
    if ck_root.is_dir():
        for man in ck_root.rglob("ark-manifest.json"):
            try:
                import json

                data = json.loads(man.read_text(encoding="utf-8", errors="replace"))
            except Exception as e:
                find("medium", "ark_manifest_bad", f"{man}: {e}")
                continue
            for f in data.get("files") or []:
                rel = str(f.get("rel") or "")
                if is_forbidden_rel(rel):
                    find("critical", "ark_forbidden_file", f"checkpoint lists forbidden path {rel}", manifest=str(man))
            # scan text files in that checkpoint
            base = man.parent
            for fp in base.rglob("*"):
                if not fp.is_file():
                    continue
                rel = str(fp.relative_to(base))
                if is_forbidden_rel(rel):
                    find("critical", "ark_forbidden_on_disk", f"forbidden file in ark: {rel}")
                hits = scan_file_for_secrets(fp)
                if hits:
                    find(
                        "high",
                        "ark_secret_pattern",
                        f"secret-like pattern in checkpoint file {rel}",
                        patterns=hits[:3],
                    )

    # 5. provider isolation note
    cfg = h / "config.yaml"
    if cfg.is_file():
        text = cfg.read_text(encoding="utf-8", errors="replace")
        if "provider:" in text and "hermescube" not in text:
            find("low", "provider_other", "memory.provider is not hermescube (ok if intentional)")
        hits = scan_text_for_secrets(text)
        if hits:
            find("high", "config_secrets", "config.yaml matches secret-like patterns — move secrets to .env")

    # 6. no cube path pointing outside home via symlink
    mem = h / "memories"
    if mem.is_dir() and mem.is_symlink():
        try:
            assert_under_home(mem.resolve(), h, label="memories symlink")
        except SecurityError as e:
            find("critical", "memories_symlink_escape", str(e))

    # 7. profile collision warning — if home is a profile, parent profiles dir listing is fine
    if h.parent.name == "profiles":
        find("info", "profile_home", f"Profile-scoped home (good isolation): {h.name}")

    report = {
        "ok": ok,
        "hermes_home": str(h),
        "findings": findings,
        "summary": {
            "critical": sum(1 for f in findings if f["severity"] == "critical"),
            "high": sum(1 for f in findings if f["severity"] == "high"),
            "medium": sum(1 for f in findings if f["severity"] == "medium"),
            "low": sum(1 for f in findings if f["severity"] == "low"),
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
    }
    _seal_audit(h, report)
    return report


def _seal_audit(home: Path, report: dict[str, Any]) -> None:
    try:
        from hermescube.blackbox.hold_line import record as hold_record

        hold_record(
            hermes_home=home,
            organ="security",
            event="audit",
            summary=f"security audit ok={report.get('ok')} summary={report.get('summary')}",
            payload={
                "summary": report.get("summary"),
                "findings_n": len(report.get("findings") or []),
            },
            severity="critical" if not report.get("ok") else "normal",
        )
    except Exception:
        pass


def validate_checkpoint_sources(
    home: Path, rel_paths: Iterable[str]
) -> list[str]:
    """Return list of rejection reasons; empty means OK to pack."""
    reasons: list[str] = []
    h = resolve_hermes_home(home)
    for rel in rel_paths:
        if is_forbidden_rel(rel):
            reasons.append(f"forbidden: {rel}")
            continue
        src = h / rel
        try:
            assert_under_home(src, h, label=rel)
        except SecurityError as e:
            reasons.append(str(e))
            continue
        for hit in scan_file_for_secrets(src):
            reasons.append(f"secret-pattern in {rel}: {hit}")
    return reasons


def format_audit(report: dict[str, Any]) -> str:
    lines = [
        "HermesCube security audit",
        f"  HERMES_HOME: {report.get('hermes_home')}",
        f"  ok:          {report.get('ok')}",
        f"  summary:     {report.get('summary')}",
        "",
    ]
    for f in report.get("findings") or []:
        lines.append(f"  [{f.get('severity')}] {f.get('code')}: {f.get('message')}")
    if not report.get("findings"):
        lines.append("  (no findings)")
    lines.append("")
    lines.append("Generator rule: one HERMES_HOME → one book → no cross-profile bleed.")
    return "\n".join(lines)
