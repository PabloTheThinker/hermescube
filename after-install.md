# HermesCube installed

Local deep memory for **your** Hermes Agent profile.

## Layout (ship contract)

| Path | Purpose |
|------|---------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin code |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory (never in the git repo) |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` |
| `.hermescube-origin` | Update URL stamp |
| Python package `hermescube` | Library + CLI |

## Finish wiring

```bash
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
# preferred clean ship (git at plugin path):
./scripts/install_hermes.sh --from-git

hermescube doctor
hermes memory status
```

## Update (code only — cube untouched)

```bash
hermescube update
```

Works for:
- git plugin checkout
- pinned dev source root
- copy install via origin cache clone

## Everyday

- Prefetch + sync_turn automatic when provider is hermescube
- MEMORY.md stays the hot notebook; Cube is the warehouse
- Tools: search · manage · feedback · probe
- `hermescube info` · density · dense export for backup

## Docs

- https://github.com/PabloTheThinker/hermescube
- docs/DAY_TO_DAY.md · docs/ASSESSMENT.md · docs/FRAMEWORK.md
