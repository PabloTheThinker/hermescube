#!/usr/bin/env bash
# Install HermesCube into the *user's* Hermes Agent home.
#
# Layout (Hermes-native):
#   $HERMES_HOME/plugins/hermescube/   ← plugin entry (this repo or copy)
#   $HERMES_HOME/memories/memory.cube  ← USER data (never the git tree)
#   memory.provider: hermescube        ← config.yaml
#
# Preferred user flows:
#   A) hermes plugins install PabloTheThinker/hermescube
#      then:  ./scripts/install_hermes.sh   # wire package + config
#   B) git clone … && ./scripts/install_hermes.sh
#
# Env:
#   HERMES_HOME   default ~/.hermes
#   HERMES_PYTHON optional path to Hermes venv python
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
DEST="${HERMES_HOME}/plugins/hermescube"
MEM_DIR="${HERMES_HOME}/memories"

echo "=== HermesCube → user Hermes home ==="
echo "  HERMES_HOME=$HERMES_HOME"
echo "  plugin → $DEST"
echo "  cube   → $MEM_DIR/memory.cube  (created on first use)"
echo "  source → $ROOT"
echo

# Resolve Python: prefer Hermes-managed venv, then HERMES_PYTHON, then current
resolve_python() {
  if [[ -n "${HERMES_PYTHON:-}" && -x "${HERMES_PYTHON}" ]]; then
    echo "$HERMES_PYTHON"
    return
  fi
  local candidates=(
    "${HERMES_HOME}/hermes-agent/.venv/bin/python"
    "${HERMES_HOME}/.venv/bin/python"
    "${HOME}/hermes-agent/.venv/bin/python"
    "$(command -v python3 || true)"
  )
  # If `hermes` is a script, try sibling venv
  if command -v hermes >/dev/null 2>&1; then
    local h
    h="$(command -v hermes)"
    if [[ -x "$(dirname "$h")/python" ]]; then
      candidates=("$(dirname "$h")/python" "${candidates[@]}")
    fi
  fi
  for p in "${candidates[@]}"; do
    if [[ -n "$p" && -x "$p" ]]; then
      echo "$p"
      return
    fi
  done
  echo "python3"
}

PY="$(resolve_python)"
echo "  python → $PY"
"$PY" -c 'import sys; print("  version", sys.version.split()[0])'

# 1) Install package into that interpreter (user env — not a random project folder)
echo
echo "→ pip install -e (package hermescube)"
"$PY" -m pip install -e "${ROOT}[numpy]" -q 2>/dev/null \
  || "$PY" -m pip install -e "${ROOT}" -q

# 2) Materialize plugin dir under USER hermes home
#    If DEST is already this git checkout (user cloned into plugins/), keep it.
#    Else copy entry files + leave package on PYTHONPATH via pip.
mkdir -p "$DEST" "$MEM_DIR"
if [[ "$(cd "$ROOT" && pwd -P)" == "$(cd "$DEST" 2>/dev/null && pwd -P || true)" ]]; then
  echo "→ plugin dir is this checkout (hermes plugins install layout) — OK"
else
  echo "→ install plugin entry → $DEST"
  # Full checkout copy for hermes plugins discover + cli.py
  # Prefer rsync of entry + package if DEST empty-ish
  cp -f "$ROOT/plugin.yaml" "$DEST/plugin.yaml"
  cp -f "$ROOT/__init__.py" "$DEST/__init__.py"
  cp -f "$ROOT/cli.py" "$DEST/cli.py" 2>/dev/null || cp -f "$ROOT/plugin/cli.py" "$DEST/cli.py"
  # Ensure package importable if user runs without pip path: ship thin path bootstrap already in __init__
  if [[ ! -d "$DEST/hermescube" ]]; then
    # symlink package into plugin dir for zero-pip fallback (dev only)
    ln -sfn "$ROOT/hermescube" "$DEST/hermescube" 2>/dev/null || true
  fi
  if [[ -f "$ROOT/after-install.md" ]]; then
    cp -f "$ROOT/after-install.md" "$DEST/after-install.md"
  fi
  # update/install scripts for hermescube update
  mkdir -p "$DEST/scripts"
  cp -f "$ROOT/scripts/install_hermes.sh" "$DEST/scripts/install_hermes.sh" 2>/dev/null || true
  cp -f "$ROOT/scripts/update.sh" "$DEST/scripts/update.sh" 2>/dev/null || true
  chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true
  # full tree pieces needed for pip -e from plugin dir
  if [[ ! -f "$DEST/pyproject.toml" ]]; then
    cp -f "$ROOT/pyproject.toml" "$DEST/pyproject.toml"
    # copy package source if not symlink
    if [[ ! -e "$DEST/hermescube" ]]; then
      cp -a "$ROOT/hermescube" "$DEST/hermescube"
    fi
  fi
fi

# 3) Wire config.yaml — only set provider if unset (don't clobber user's choice)
echo
echo "→ config.yaml"
"$PY" - <<PY
from pathlib import Path
import os, sys
try:
    import yaml
except ImportError:
    print("  PyYAML missing — set memory.provider: hermescube manually")
    sys.exit(0)

home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
p = home / "config.yaml"
if not p.exists():
    print(f"  No {p} — create Hermes config first (hermes setup), then re-run.")
    print("  Then set:  memory.provider: hermescube")
    raise SystemExit(0)

raw = p.read_text(encoding="utf-8")
cfg = yaml.safe_load(raw) or {}
mem = cfg.setdefault("memory", {})
prev = mem.get("provider")
if not prev or prev in ("", "none", "off"):
    mem["provider"] = "hermescube"
    print("  Set memory.provider: hermescube")
else:
    print(f"  memory.provider already: {prev}  (left unchanged)")

pl = cfg.setdefault("plugins", {})
hc = pl.setdefault("hermescube", {})
hc.setdefault("auto_extract", False)
hc.setdefault("evolve_interval", 50)
hc.setdefault("query_rewrite", False)

bak = p.with_suffix(".yaml.bak-hermescube-install")
if not bak.exists():
    bak.write_text(raw, encoding="utf-8")
    print(f"  Backup: {bak.name}")

p.write_text(
    yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False, allow_unicode=True),
    encoding="utf-8",
)
print("  OK config written")
print(f"  User cube path (on first use): {home / 'memories' / 'memory.cube'}")
PY

# 4) Verify load via Hermes discovery contract
echo
echo "→ verify"
"$PY" - <<PY
import os, sys
from pathlib import Path
os.environ.setdefault("HERMES_HOME", str(Path("${HERMES_HOME}").expanduser()))
sys.path.insert(0, str(Path("${HERMES_HOME}") / "hermes-agent"))
# also allow checkout hermes
for extra in (
    Path.home() / "hermes-agent",
    Path("/home/ilo/hermes-agent"),
):
    if extra.is_dir():
        sys.path.insert(0, str(extra))
ok = False
try:
    from plugins.memory import load_memory_provider
    p = load_memory_provider("hermescube")
    if p is None:
        print("  FAIL: load_memory_provider('hermescube') → None")
        print("  Check: $HERMES_HOME/plugins/hermescube/__init__.py exists")
        sys.exit(1)
    hh = os.environ["HERMES_HOME"]
    p.initialize(session_id="_install_verify", hermes_home=hh, platform="cli")
    path = getattr(p, "_cube_path", "")
    print(f"  provider: {p.name}")
    print(f"  cube_path: {path}")
    assert "memories" in path.replace("\\\\", "/"), path
    assert str(Path(hh).resolve()) in str(Path(path).resolve()) or path.startswith(hh), (
        f"cube must live under HERMES_HOME, got {path}"
    )
    print("  entries:", p._cube.entry_count if p._cube else 0)
    p.shutdown()
    ok = True
except Exception as e:
    print(f"  WARN verify via plugins.memory: {e}")
    # fallback: direct package
    try:
        from hermescube.provider import CubeMemoryProvider
        p = CubeMemoryProvider()
        p.initialize(session_id="_v", hermes_home=os.environ["HERMES_HOME"], platform="cli")
        print("  direct CubeMemoryProvider OK", p._cube_path)
        p.shutdown()
        ok = True
    except Exception as e2:
        print(f"  FAIL: {e2}")
        sys.exit(1)
print("  VERIFY OK" if ok else "  VERIFY partial")
PY

echo
echo "Done. Activate if needed:"
echo "  hermes config set memory.provider hermescube"
echo "  # or ensure config already has memory.provider: hermescube"
echo "Status:"
echo "  hermes memory status"
echo "CLI:"
echo "  hermescube --help"
echo "  hermescube info   # defaults to \$HERMES_HOME/memories/memory.cube"
