#!/usr/bin/env bash
# Update HermesCube in the *user's* Hermes home (like hermes plugins update + reinstall).
#
# Primary (Hermes-native):
#   hermes plugins update hermescube && ./scripts/update.sh
# Or one-shot:
#   hermescube update
#   ./scripts/update.sh
#
# Does NOT touch user cube data ($HERMES_HOME/memories/memory.cube).
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-${HOME}/.hermes}"
PLUGIN_DIR="${HERMES_HOME}/plugins/hermescube"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== HermesCube update ==="
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

# Prefer updating the installed plugin tree (user copy)
TARGET=""
if [[ -d "$PLUGIN_DIR/.git" ]]; then
  TARGET="$PLUGIN_DIR"
elif [[ -d "$PLUGIN_DIR" && -f "$PLUGIN_DIR/plugin.yaml" ]]; then
  TARGET="$PLUGIN_DIR"
elif [[ -d "$ROOT/.git" ]]; then
  TARGET="$ROOT"
  echo "  note: no git plugin dir; updating checkout at $ROOT"
else
  echo "ERROR: no hermescube install found at $PLUGIN_DIR"
  echo "  install: hermes plugins install PabloTheThinker/hermescube"
  exit 1
fi

# 1) Git pull when possible
if [[ -d "$TARGET/.git" ]]; then
  echo "→ git pull ($TARGET)"
  git -C "$TARGET" fetch --tags --prune 2>/dev/null || true
  if git -C "$TARGET" pull --ff-only; then
    :
  else
    echo "  ff-only failed — trying pull --rebase"
    git -C "$TARGET" pull --rebase || {
      echo "  git pull failed; fix conflicts in $TARGET"
      exit 1
    }
  fi
  git -C "$TARGET" log -1 --oneline
else
  echo "→ no .git in $TARGET (copy install) — skip pull; reinstall package from tree"
fi

# 2) Reinstall package into Hermes Python (code only — not cube data)
echo "→ pip install -e"
SRC="$TARGET"
# If plugin dir is entry-only (symlinked package), prefer ROOT when it's a full checkout
if [[ ! -f "$TARGET/pyproject.toml" && -f "$ROOT/pyproject.toml" ]]; then
  SRC="$ROOT"
fi
if [[ -f "$SRC/pyproject.toml" ]]; then
  "$PY" -m pip install -e "${SRC}[numpy]" -q 2>/dev/null \
    || "$PY" -m pip install -e "$SRC" -q
else
  echo "  WARN: no pyproject at $SRC — package may be stale"
fi

# 3) Refresh plugin entry files if TARGET is copy-layout and SRC differs
if [[ "$(cd "$SRC" && pwd -P)" != "$(cd "$TARGET" && pwd -P)" ]]; then
  if [[ -f "$SRC/plugin.yaml" ]]; then
    echo "→ refresh plugin entry files → $TARGET"
    mkdir -p "$TARGET"
    cp -f "$SRC/plugin.yaml" "$TARGET/plugin.yaml"
    cp -f "$SRC/__init__.py" "$TARGET/__init__.py" 2>/dev/null || true
    cp -f "$SRC/cli.py" "$TARGET/cli.py" 2>/dev/null || cp -f "$SRC/plugin/cli.py" "$TARGET/cli.py" 2>/dev/null || true
    cp -f "$SRC/after-install.md" "$TARGET/after-install.md" 2>/dev/null || true
  fi
fi

# 4) Verify — do not rewrite config provider if already set
echo "→ verify"
HERMES_HOME="$HERMES_HOME" "$PY" - <<'PY'
import os, sys
from pathlib import Path
home = Path(os.environ["HERMES_HOME"])
sys.path.insert(0, str(home / "hermes-agent"))
for extra in (Path.home() / "hermes-agent", Path("/home/ilo/hermes-agent")):
    if extra.is_dir():
        sys.path.insert(0, str(extra))
try:
    import hermescube
    print(f"  package {hermescube.__version__} @ {hermescube.__file__}")
except Exception as e:
    print(f"  FAIL import hermescube: {e}")
    sys.exit(1)
try:
    from plugins.memory import load_memory_provider
    p = load_memory_provider("hermescube")
    if not p:
        print("  FAIL load_memory_provider('hermescube')")
        sys.exit(1)
    p.initialize(session_id="_update", hermes_home=str(home), platform="cli")
    print(f"  cube {p._cube_path} entries={p._cube.entry_count if p._cube else 0}")
    p.shutdown()
except Exception as e:
    print(f"  WARN discovery: {e}")
print("  UPDATE OK")
PY

echo
echo "Done. User cube data untouched."
echo "  hermes plugins update hermescube   # git-only (Hermes native)"
echo "  hermescube update                  # git + pip reinstall (this script)"
echo "  hermescube doctor"
