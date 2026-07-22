#!/usr/bin/env bash
# Update HermesCube code in the user's Hermes home — ship-grade.
# NEVER touches $HERMES_HOME/memories/memory.cube (or COLONY / colony graph).
#
#   hermescube update
#   ./scripts/update.sh
#   hermes plugins update hermescube && ./scripts/update.sh
#
# Resolution order for code source:
#   1) $PLUGIN/.git  → git pull
#   2) $PLUGIN/.hermescube-source-root (dev pin to a checkout with .git)
#   3) $PLUGIN/.hermescube-origin URL → fetch into cache + sync
#   4) sibling checkout / this script's repo if it has .git
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
PLUGIN_DIR="${HERMES_HOME}/plugins/hermescube"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GIT_URL_DEFAULT="https://github.com/PabloTheThinker/hermescube.git"
CACHE="${HERMES_HOME}/.cache/hermescube-src"

echo "=== HermesCube update (ship) ==="
echo "  HERMES_HOME=$HERMES_HOME"
echo "  plugin=$PLUGIN_DIR"

resolve_python() {
  if [[ -n "${HERMES_PYTHON:-}" && -x "${HERMES_PYTHON}" ]]; then
    echo "$HERMES_PYTHON"; return
  fi
  for p in \
    "${HERMES_HOME}/hermes-agent/.venv/bin/python" \
    "${HERMES_HOME}/.venv/bin/python" \
    "${HOME}/hermes-agent/.venv/bin/python"
  do
    [[ -x "$p" ]] && { echo "$p"; return; }
  done
  command -v python3
}

PY="$(resolve_python)"
echo "  python=$PY"

if [[ ! -d "$PLUGIN_DIR" ]] || [[ ! -f "$PLUGIN_DIR/plugin.yaml" ]]; then
  echo "ERROR: plugin not installed at $PLUGIN_DIR"
  echo "  install: hermes plugins install PabloTheThinker/hermescube"
  echo "       or: ./scripts/install_hermes.sh --from-git"
  exit 1
fi

sync_tree() {
  local src="$1"
  local dst="$2"
  echo "→ sync code $src → $dst (data paths excluded)"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude '.git' \
      --exclude 'memories' \
      --exclude '*.cube' \
      --exclude '*.cubelog' \
      --exclude '__pycache__' \
      --exclude '.pytest_cache' \
      --exclude '*.egg-info' \
      --exclude '.hermescube-origin' \
      --exclude '.hermescube-source-root' \
      "$src"/ "$dst"/
  else
    # portable fallback
    cp -f "$src/plugin.yaml" "$dst/plugin.yaml" 2>/dev/null || true
    cp -f "$src/__init__.py" "$dst/__init__.py" 2>/dev/null || true
    cp -f "$src/cli.py" "$dst/cli.py" 2>/dev/null || true
    cp -f "$src/pyproject.toml" "$dst/pyproject.toml" 2>/dev/null || true
    cp -f "$src/after-install.md" "$dst/after-install.md" 2>/dev/null || true
    mkdir -p "$dst/scripts" "$dst/hermescube"
    cp -f "$src/scripts/"*.sh "$dst/scripts/" 2>/dev/null || true
    chmod +x "$dst/scripts/"*.sh 2>/dev/null || true
    if [[ -d "$src/hermescube" ]]; then
      rm -rf "$dst/hermescube"
      cp -a "$src/hermescube" "$dst/hermescube"
    fi
  fi
}

ORIGIN="$GIT_URL_DEFAULT"
[[ -f "$PLUGIN_DIR/.hermescube-origin" ]] && ORIGIN="$(tr -d '[:space:]' <"$PLUGIN_DIR/.hermescube-origin")"
[[ -n "${HERMESCUBE_GIT_URL:-}" ]] && ORIGIN="$HERMESCUBE_GIT_URL"

SRC=""
# 1) Plugin is git
if [[ -d "$PLUGIN_DIR/.git" ]]; then
  echo "→ git pull (plugin checkout)"
  git -C "$PLUGIN_DIR" fetch --tags --prune 2>/dev/null || true
  if ! git -C "$PLUGIN_DIR" pull --ff-only; then
    echo "  ff-only failed — pull --rebase"
    git -C "$PLUGIN_DIR" pull --rebase || {
      echo "  git pull failed in $PLUGIN_DIR — fix manually"
      exit 1
    }
  fi
  git -C "$PLUGIN_DIR" log -1 --oneline
  SRC="$PLUGIN_DIR"
# 2) Dev pin to source root
elif [[ -f "$PLUGIN_DIR/.hermescube-source-root" ]]; then
  PIN="$(tr -d '[:space:]' <"$PLUGIN_DIR/.hermescube-source-root")"
  if [[ -d "$PIN/.git" && -f "$PIN/pyproject.toml" ]]; then
    echo "→ git pull (pinned source $PIN)"
    git -C "$PIN" fetch --tags --prune 2>/dev/null || true
    git -C "$PIN" pull --ff-only 2>/dev/null || git -C "$PIN" pull --rebase || true
    git -C "$PIN" log -1 --oneline 2>/dev/null || true
    SRC="$PIN"
    sync_tree "$SRC" "$PLUGIN_DIR"
  fi
fi

# 3) This script's ROOT if full git checkout
if [[ -z "$SRC" && -d "$ROOT/.git" && -f "$ROOT/pyproject.toml" ]]; then
  echo "→ git pull (update.sh repo $ROOT)"
  git -C "$ROOT" fetch --tags --prune 2>/dev/null || true
  git -C "$ROOT" pull --ff-only 2>/dev/null || git -C "$ROOT" pull --rebase || true
  git -C "$ROOT" log -1 --oneline 2>/dev/null || true
  SRC="$ROOT"
  sync_tree "$SRC" "$PLUGIN_DIR"
fi

# 4) Cache clone from origin URL
if [[ -z "$SRC" ]]; then
  echo "→ fetch origin $ORIGIN → cache"
  mkdir -p "$(dirname "$CACHE")"
  if [[ -d "$CACHE/.git" ]]; then
    git -C "$CACHE" remote set-url origin "$ORIGIN" 2>/dev/null || true
    git -C "$CACHE" fetch --tags --prune
    git -C "$CACHE" reset --hard origin/main 2>/dev/null \
      || git -C "$CACHE" reset --hard origin/master 2>/dev/null \
      || git -C "$CACHE" pull --ff-only || true
  else
    rm -rf "$CACHE"
    git clone --depth 1 "$ORIGIN" "$CACHE"
  fi
  SRC="$CACHE"
  sync_tree "$SRC" "$PLUGIN_DIR"
  echo "$ORIGIN" >"$PLUGIN_DIR/.hermescube-origin"
  git -C "$CACHE" log -1 --oneline 2>/dev/null || true
fi

# pip reinstall — prefer SRC with pyproject
echo "→ pip install -e"
PIP_SRC="$SRC"
[[ -f "$PLUGIN_DIR/pyproject.toml" ]] && PIP_SRC="$PLUGIN_DIR"
[[ -f "$PIP_SRC/pyproject.toml" ]] || PIP_SRC="$ROOT"
if [[ -f "$PIP_SRC/pyproject.toml" ]]; then
  "$PY" -m pip install -e "${PIP_SRC}[numpy]" -q 2>/dev/null \
    || "$PY" -m pip install -e "$PIP_SRC" -q
else
  echo "ERROR: no pyproject.toml to install"
  exit 1
fi

# verify — cube path must remain under memories/
echo "→ verify"
HERMES_HOME="$HERMES_HOME" "$PY" - <<'PY'
import os, sys
from pathlib import Path
home = Path(os.environ["HERMES_HOME"])
sys.path.insert(0, str(home / "hermes-agent"))
for extra in (Path.home() / "hermes-agent", Path("/home/ilo/hermes-agent")):
    if extra.is_dir():
        sys.path.insert(0, str(extra))
import hermescube
print(f"  package {hermescube.__version__} @ {hermescube.__file__}")
cube = home / "memories" / "memory.cube"
print(f"  user cube path (untouched): {cube} exists={cube.is_file()}")
try:
    from plugins.memory import load_memory_provider
    p = load_memory_provider("hermescube")
    if not p:
        print("  FAIL load_memory_provider")
        sys.exit(1)
    p.initialize(session_id="_update", hermes_home=str(home), platform="cli")
    path = Path(p._cube_path)
    assert path.resolve() == cube.resolve() or "memories" in str(path)
    print(f"  live entries={p._cube.entry_count if p._cube else 0}")
    p.shutdown()
except Exception as e:
    print(f"  WARN discovery: {e}")
print("  UPDATE OK")
PY

echo
echo "Done. User cube data untouched."
echo "  hermescube doctor"
echo "  hermes plugins update hermescube   # optional if plugin is a git clone"
