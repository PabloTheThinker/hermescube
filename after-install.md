# HermesCube installed

Local holographic memory for **your** Hermes Agent profile.

## Layout (important)

| Path | Purpose |
|------|---------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin code (this folder after install) |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory file (created on first use) |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` |
| Python package `hermescube` | Library + `hermescube` CLI |

**Data never lives in a random project folder** — only under your `$HERMES_HOME`.

## Finish wiring

```bash
# 1) Install package into the Hermes Python env + wire config
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
# or:  python -m pip install -e ".[numpy]"

# 2) Select provider (if install did not already set it)
hermes config set memory.provider hermescube
# or: hermes memory setup

# 3) Verify
hermescube doctor
hermescube info
hermes memory status
```

## Everyday

- Hermes auto-calls `prefetch` / `sync_turn` when `memory.provider: hermescube`
- Tools: `hermescube_search` · `hermescube_manage` · `hermescube_feedback`
- Sleep consolidate runs on session end — not on the hot path
- Keep `query_rewrite` **off** (default) for fast recall
- CLI defaults to `$HERMES_HOME/memories/memory.cube` (omit path args)

## Docs

- [README](https://github.com/PabloTheThinker/hermescube#readme)
- [User Guide](https://github.com/PabloTheThinker/hermescube/blob/main/docs/USER_GUIDE.md)
- [Changelog](https://github.com/PabloTheThinker/hermescube/blob/main/CHANGELOG.md)
