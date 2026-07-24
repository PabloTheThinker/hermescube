#!/usr/bin/env bash
# Install HermesCube into the *user's* Hermes Agent home — ship-grade.
#
# Layout (Hermes-native):
#   $HERMES_HOME/plugins/hermescube/   ← plugin (prefers git checkout)
#   $HERMES_HOME/memories/memory.cube  ← USER data only
#   memory.provider: hermescube
#
# Flows:
#   A) hermes plugins install PabloTheThinker/hermescube && ./scripts/install_hermes.sh
#   B) git clone … && ./scripts/install_hermes.sh
#   C) curl | bash style: HERMESCUBE_GIT_URL=… ./scripts/install_hermes.sh --from-git
#
# Env: HERMES_HOME · HERMES_PYTHON · HERMESCUBE_GIT_URL
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
DEST="${HERMES_HOME}/plugins/hermescube"
MEM_DIR="${HERMES_HOME}/memories"
GIT_URL="${HERMESCUBE_GIT_URL:-https://github.com/PabloTheThinker/hermescube.git}"
FROM_GIT=0
for arg in "$@"; do
  [[ "$arg" == "--from-git" ]] && FROM_GIT=1
done

echo "=== HermesCube ship install → user Hermes home ==="
echo "  HERMES_HOME=$HERMES_HOME"
echo "  plugin → $DEST"
echo "  cube   → $MEM_DIR/memory.cube  (user data, never in git)"
echo "  source → $ROOT"
echo

resolve_python() {
  if [[ -n "${HERMES_PYTHON:-}" && -x "${HERMES_PYTHON}" ]]; then
    echo "$HERMES_PYTHON"; return
  fi
  local candidates=(
    "${HERMES_HOME}/hermes-agent/.venv/bin/python"
    "${HERMES_HOME}/.venv/bin/python"
    "${HOME}/hermes-agent/.venv/bin/python"
    "$(command -v python3 || true)"
  )
  if command -v hermes >/dev/null 2>&1; then
    local h; h="$(command -v hermes)"
    [[ -x "$(dirname "$h")/python" ]] && candidates=("$(dirname "$h")/python" "${candidates[@]}")
  fi
  for p in "${candidates[@]}"; do
    [[ -n "$p" && -x "$p" ]] && { echo "$p"; return; }
  done
  echo "python3"
}

PY="$(resolve_python)"
echo "  python → $PY"
"$PY" -c 'import sys; print("  version", sys.version.split()[0])'

mkdir -p "$DEST" "$MEM_DIR"

# ── Prefer a real git tree at DEST (so hermescube update + hermes plugins update work) ──
ensure_git_plugin() {
  if [[ -d "$DEST/.git" ]]; then
    echo "→ plugin already a git checkout — OK"
    # stamp origin for doctor/update
    git -C "$DEST" remote get-url origin >"$DEST/.hermescube-origin" 2>/dev/null || true
    return 0
  fi
  if [[ $FROM_GIT -eq 1 ]] || [[ ! -f "$DEST/plugin.yaml" ]]; then
    if command -v git >/dev/null 2>&1; then
      echo "→ git clone $GIT_URL → $DEST (ship layout with .git)"
      if [[ -z "$(ls -A "$DEST" 2>/dev/null || true)" ]]; then
        git clone --depth 1 "$GIT_URL" "$DEST"
      else
        # DEST has copy files — clone to temp and merge code, keep no user data here
        local tmp
        tmp="$(mktemp -d)"
        git clone --depth 1 "$GIT_URL" "$tmp/hermescube"
        # refresh code files only
        rsync -a --delete \
          --exclude '.hermescube-origin' \
          --exclude 'memories' \
          --exclude '*.cube' \
          "$tmp/hermescube/" "$DEST/" || {
            cp -a "$tmp/hermescube/." "$DEST/"
          }
        rm -rf "$tmp"
      fi
      echo "$GIT_URL" >"$DEST/.hermescube-origin"
      return 0
    fi
  fi
  # Fallback: copy entry from ROOT (dev machine with separate checkout)
  if [[ "$(cd "$ROOT" && pwd -P)" == "$(cd "$DEST" 2>/dev/null && pwd -P || true)" ]]; then
    echo "→ plugin dir is this checkout — OK"
    echo "$GIT_URL" >"$DEST/.hermescube-origin"
    return 0
  fi
  echo "→ copy plugin entry from $ROOT → $DEST (no .git — update will use origin stamp)"
  cp -f "$ROOT/plugin.yaml" "$DEST/plugin.yaml"
  cp -f "$ROOT/__init__.py" "$DEST/__init__.py" 2>/dev/null || true
  cp -f "$ROOT/cli.py" "$DEST/cli.py" 2>/dev/null || cp -f "$ROOT/plugin/cli.py" "$DEST/cli.py" 2>/dev/null || true
  cp -f "$ROOT/after-install.md" "$DEST/after-install.md" 2>/dev/null || true
  mkdir -p "$DEST/scripts"
  cp -f "$ROOT/scripts/install_hermes.sh" "$DEST/scripts/" 2>/dev/null || true
  cp -f "$ROOT/scripts/update.sh" "$DEST/scripts/" 2>/dev/null || true
  chmod +x "$DEST/scripts/"*.sh 2>/dev/null || true
  if [[ ! -f "$DEST/pyproject.toml" ]]; then
    cp -f "$ROOT/pyproject.toml" "$DEST/pyproject.toml"
  fi
  # Prefer symlink to live package when ROOT is a full checkout
  if [[ -d "$ROOT/hermescube" ]]; then
    if [[ -d "$ROOT/.git" ]]; then
      ln -sfn "$ROOT/hermescube" "$DEST/hermescube" 2>/dev/null \
        || { rm -rf "$DEST/hermescube"; cp -a "$ROOT/hermescube" "$DEST/hermescube"; }
      # SOURCE pin: update pulls from this checkout
      echo "$ROOT" >"$DEST/.hermescube-source-root"
    else
      rm -rf "$DEST/hermescube"
      cp -a "$ROOT/hermescube" "$DEST/hermescube"
    fi
  fi
  echo "$GIT_URL" >"$DEST/.hermescube-origin"
  echo "$ROOT" >"$DEST/.hermescube-source-root"
}

ensure_git_plugin

# ── pip install into Hermes interpreter ──
echo
echo "→ pip install -e (package hermescube)"
SRC="$DEST"
if [[ ! -f "$SRC/pyproject.toml" && -f "$ROOT/pyproject.toml" ]]; then
  SRC="$ROOT"
fi
if [[ -f "$SRC/pyproject.toml" ]]; then
  "$PY" -m pip install -e "${SRC}[numpy]" -q 2>/dev/null \
    || "$PY" -m pip install -e "$SRC" -q
else
  echo "ERROR: no pyproject.toml at $SRC"
  exit 1
fi

# ── config.yaml ──
echo
echo "→ config.yaml"
HERMES_HOME="$HERMES_HOME" "$PY" - <<'PY'
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
    print(f"  No {p} — run hermes setup, then re-run install.")
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
print(f"  User cube path: {home / 'memories' / 'memory.cube'}")
PY

# ── verify ──
echo
echo "→ verify"
HERMES_HOME="$HERMES_HOME" "$PY" - <<'PY'
import os, sys
from pathlib import Path
os.environ.setdefault("HERMES_HOME", str(Path.home() / ".hermes"))
hh = Path(os.environ["HERMES_HOME"])
sys.path.insert(0, str(hh / "hermes-agent"))
for extra in (
    Path.home() / "hermes-agent",
    Path(os.environ["HERMES_HOME"]) / "hermes-agent" if os.environ.get("HERMES_HOME") else None,
    Path(os.environ["HERMES_AGENT_HOME"]) if os.environ.get("HERMES_AGENT_HOME") else None,
):
    if extra is not None and extra.is_dir():
        sys.path.insert(0, str(extra))
ok = False
try:
    from plugins.memory import load_memory_provider
    p = load_memory_provider("hermescube")
    if p is None:
        print("  FAIL: load_memory_provider('hermescube') → None")
        sys.exit(1)
    p.initialize(session_id="_install_verify", hermes_home=str(hh), platform="cli")
    path = getattr(p, "_cube_path", "")
    print(f"  provider: {getattr(p, 'name', 'hermescube')}")
    print(f"  cube_path: {path}")
    assert "memories" in path.replace("\\", "/")
    print("  entries:", p._cube.entry_count if p._cube else 0)
    p.shutdown()
    ok = True
except Exception as e:
    print(f"  WARN plugins.memory: {e}")
    try:
        from hermescube.provider import CubeMemoryProvider
        p = CubeMemoryProvider()
        p.initialize(session_id="_v", hermes_home=str(hh), platform="cli")
        print("  direct CubeMemoryProvider OK", p._cube_path)
        p.shutdown()
        ok = True
    except Exception as e2:
        print(f"  FAIL: {e2}")
        sys.exit(1)
print("  VERIFY OK" if ok else "  VERIFY partial")
PY

echo
echo "Done (ship install)."
echo "  hermescube doctor"
echo "  hermescube update   # later — pulls code, never wipes cube"
echo "  memory.provider: hermescube"
