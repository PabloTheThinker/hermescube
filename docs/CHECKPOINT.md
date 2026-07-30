# Checkpoints — safe locks / identity ark

**HermesCube is the library.** A **checkpoint** is a **safe lock** on the shelf: a flash clone of the **book** plus the agent’s **core identity** at a moment in the arc.

## Why

If Hermes restarts fresh, the gateway dies, or the live cube is damaged, you should not lose:

- long memory (`memory.cube`)
- who the agent is (`SOUL.md`, `MEMORY.md`, `USER.md`)
- optional light config (`config.yaml` — **never** `.env` secrets by default)

Mental model (story, not cosplay): a **Weapon-like** offline copy of the mind’s core *before* a bad branch of the timeline — identity + library, ready to restore.

## What is saved

| Included | Path under `$HERMES_HOME` |
|----------|---------------------------|
| Soul | `SOUL.md` |
| Hot memory | `memories/MEMORY.md`, `memories/USER.md` |
| Living diary | `memories/CUBE.md` (if present) |
| Book | `memories/memory.cube` (+ wal/cubelog if present) |
| Config (optional) | `config.yaml` |
| Relations / triage | if present |

**Never included:** `.env`, `auth.json`, API keys, PEM files.

## CLI

```bash
# Create a named arc mark
hermescube checkpoint create --name "pre-update" --label "Before hermes update"

# List
hermescube checkpoint list

# Dry-run restore
hermescube checkpoint restore --name pre-update --dry-run

# Restore book + identity (backs up live files as *.pre-restore-*)
hermescube checkpoint restore --name pre-update

# Identity only / cube only
hermescube checkpoint restore --name pre-update --identity-only
hermescube checkpoint restore --name pre-update --cube-only
```

Default location: `$HERMES_HOME/memories/checkpoints/<slug>/`  
Optional: `--dense` adds portable text export; default also packs `<slug>.tar.gz` unless `--no-tar`.

## After restore

Restart Hermes gateway / Desktop so SOUL + memory provider reload.

## Library language

| Idea | Checkpoint |
|------|------------|
| Arc mark / shelf flag | Named checkpoint slug |
| Flash clone of the volume | Copied `memory.cube` |
| Who the librarian is | SOUL + hot MEMORY/USER |
| Safe lock | Offline, user-chosen, restorable |

## Not this

- Not continuous real-time RAID (use OS backups too for disk death)
- Not a cloud sync product
- Not a substitute for `hermescube update` (code) — this is **data + identity**
