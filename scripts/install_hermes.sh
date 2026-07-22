#!/usr/bin/env bash
# Install HermesCube into a Hermes Agent home (memory provider).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DEST="$HERMES_HOME/plugins/hermescube"

echo "HermesCube install → $HERMES_HOME"
python3 -m pip install -e "$ROOT" -q
mkdir -p "$DEST"
cp -f "$ROOT/plugin/__init__.py" "$DEST/__init__.py"
cp -f "$ROOT/plugin/plugin.yaml" "$DEST/plugin.yaml"
cp -f "$ROOT/plugin/cli.py" "$DEST/cli.py" 2>/dev/null || true

python3 - <<PY
from pathlib import Path
import yaml
p = Path("$HERMES_HOME") / "config.yaml"
if not p.exists():
    print("No config.yaml — create one and set memory.provider: hermescube")
    raise SystemExit(0)
cfg = yaml.safe_load(p.read_text()) or {}
mem = cfg.setdefault("memory", {})
if not mem.get("provider"):
    mem["provider"] = "hermescube"
    print("Set memory.provider: hermescube")
else:
    print(f"memory.provider already: {mem.get('provider')}")
pl = cfg.setdefault("plugins", {})
hc = pl.setdefault("hermescube", {})
hc.setdefault("auto_extract", False)
hc.setdefault("evolve_interval", 50)
bak = p.with_suffix(".yaml.bak-hermescube-install")
if not bak.exists():
    bak.write_text(p.read_text())
p.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False, allow_unicode=True))
print("OK plugin dir $DEST")
print("Activate: memory.provider: hermescube (set)")
print("Verify:  hermes plugins list | rg hermescube  OR load_memory_provider('hermescube')")
PY

echo "Done."
