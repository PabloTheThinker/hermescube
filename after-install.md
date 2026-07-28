# HermesCube installed

Local deep memory for **your** Hermes Agent profile.

**What it is:** [ABOUT.md](ABOUT.md) · **Docs:** [docs/README.md](docs/README.md)

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

## Everyday

- Prefetch + `sync_turn` automatic when provider is `hermescube`
- MEMORY.md stays the hot notebook; Cube is the warehouse
- Tools: search · manage · feedback · probe
- `hermescube info` · `dense` · `dream status` · doctor

## Docs

- [ABOUT.md](ABOUT.md) · [docs/DAY_TO_DAY.md](docs/DAY_TO_DAY.md) · [docs/CUBEDREAM.md](docs/CUBEDREAM.md) · [docs/ASSESSMENT.md](docs/ASSESSMENT.md)
