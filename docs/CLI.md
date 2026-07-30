# HermesCube CLI (terminal) — any Hermes user → their own library

Each **Hermes Agent** (any profile / user home) attaches to **one book**:

```text
$HERMES_HOME/memories/memory.cube
```

Agents do not share cubes unless they share `HERMES_HOME` (or later opt into Hive).

## Day one (terminal)

```bash
# Wire this Hermes home to HermesCube
export HERMES_HOME=~/.hermes          # or your profile home
hermescube setup                      # install/wire + connect
# or idempotent:
hermescube connect

hermescube status                     # human library status
hermes memory status                  # provider should show hermescube active

# Use the library
hermescube query "what do we know about…"
hermescube doctor
hermescube blackbox capture --latest
hermescube blackbox prove --claim "tests pass" --latest
hermescube checkpoint create --name first-lock
```

After `connect` / `setup`, **restart** the Hermes gateway, Desktop, or agent session so `memory.provider` loads.

## Commands that attach users

| Command | Job |
|---------|-----|
| `hermescube setup` | Run install script (if present) + connect |
| `hermescube connect` | Ensure dirs, plugin link, create empty book, set `memory.provider=hermescube` |
| `hermescube status` | Terminal-friendly library status for this `HERMES_HOME` |
| `hermescube doctor` | Deep health (integrity, density, growth) |

## How Hermes Agent uses it

1. Config: `memory.provider: hermescube` in `$HERMES_HOME/config.yaml`  
2. Plugin: `$HERMES_HOME/plugins/hermescube/`  
3. Data: `$HERMES_HOME/memories/memory.cube` (never in git)  
4. Tools in-session: `hermescube_search`, `hermescube_manage`, `hermescube_feedback`, `hermescube_probe`

Any Hermes agent process that loads that home **is dialed into that user’s cube**.

### Profiles / multi-agent

```bash
HERMES_HOME=~/.hermes/profiles/client-a hermescube connect
HERMES_HOME=~/.hermes/profiles/client-a hermescube status
```

Each profile = its own library book.

## Install paths

```bash
# A — plugin installer
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
hermescube connect

# B — from clone
git clone https://github.com/PabloTheThinker/hermescube.git
cd hermescube && ./scripts/install_hermes.sh
hermescube connect
```

## Library language

| Terminal | Meaning |
|----------|---------|
| setup / connect | Get a library card + open your book |
| status / doctor | Is the library healthy? |
| query | Find a passage |
| blackbox | Prove a run |
| checkpoint | Safe-lock the book + identity |

See [ABOUT.md](../ABOUT.md) · [CHECKPOINT.md](CHECKPOINT.md) · [BLACKBOX.md](BLACKBOX.md).
