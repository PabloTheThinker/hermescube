# HermesCube installed

Local holographic memory for **your** Hermes Agent profile.

## What was installed

| Path | Purpose |
|------|---------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin entry (this folder) |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory file (created on first use) |
| Python package `hermescube` | Library + `hermescube` CLI |

Data never lives in the git checkout — only under **your** `$HERMES_HOME`.

## Finish wiring

```bash
# 1) Install package into the Hermes Python env (if not already)
cd "$HERMES_HOME/plugins/hermescube"
./scripts/install_hermes.sh
# or:  python -m pip install -e ".[numpy]"

# 2) Select provider
hermes config set memory.provider hermescube
# or: hermes memory setup   → choose hermescube when listed

# 3) Verify
hermes memory status
hermescube info
```

## Everyday

- Hermes auto-calls `prefetch` / `sync_turn` when `memory.provider: hermescube`
- Tools: `hermescube_search` · `hermescube_manage` · `hermescube_feedback`
- Sleep consolidate runs on session end — not on the hot path
- Keep `query_rewrite` **off** (default) for fast recall

## Docs

https://github.com/PabloTheThinker/hermescube
