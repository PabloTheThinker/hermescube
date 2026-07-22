<p align="center">
  <h1 align="center">HermesCube</h1>
</p>

<p align="center">
  <em>Binary columnar archive with holographic associative retrieval — persistent agent memory that grows forever.</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/hermescube"><img src="https://img.shields.io/pypi/v/hermescube?color=%2334D058&label=pypi" alt="PyPI"></a>
  <a href="https://pypi.org/project/hermescube"><img src="https://img.shields.io/pypi/pyversions/hermescube.svg?color=%2334D058" alt="Python 3.11+"></a>
  <a href="https://github.com/PabloTheThinker/hermescube/actions/workflows/ci.yml"><img src="https://github.com/PabloTheThinker/hermescube/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="https://github.com/PabloTheThinker/hermescube"><img src="https://img.shields.io/github/stars/PabloTheThinker/hermescube?style=social" alt="Stars"></a>
</p>

---

## Install into Hermes Agent (per-user)

Your cube lives under **your** Hermes home — not the git tree.

```bash
# Option A — Hermes plugin installer (recommended)
hermes plugins install PabloTheThinker/hermescube
cd "$HERMES_HOME/plugins/hermescube"   # usually ~/.hermes/plugins/hermescube
./scripts/install_hermes.sh            # pip into Hermes Python + wire config
hermes config set memory.provider hermescube

# Option B — clone then install
git clone https://github.com/PabloTheThinker/hermescube.git
cd hermescube
./scripts/install_hermes.sh
hermes config set memory.provider hermescube
```

Verify:

```bash
hermescube doctor
hermescube info          # defaults to $HERMES_HOME/memories/memory.cube
hermes memory status
```

| Path | Who owns it |
|------|-------------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin code (from install) |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory data |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` |

### Update

```bash
# Full update (recommended): pull plugin + reinstall package
hermescube update
# or
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube" && ./scripts/update.sh

# Hermes-native git-only pull (same as other plugins)
hermes plugins update hermescube
# then reinstall package if needed:
hermescube update
```

`hermes update` updates the **Hermes Agent** core only. Cube is a plugin —
use `hermes plugins update hermescube` and/or `hermescube update`.

User memory at `$HERMES_HOME/memories/memory.cube` is **never** overwritten by update.

---

## Why

LLM agents forget. Context windows are finite. Cloud memory APIs cost money,
add latency, and leak data. Flat files work at first but degrade with scale.

HermesCube gives your agent **persistent, semantic, local memory** — no network
calls, no API keys, no pruning. It uses holographic vectors to understand what
your conversations *mean*, not just what words they contain.

```python
from hermescube import CubeFile, HARQueryEngine

cube = CubeFile.create("memory.cube")

# Store memories like an agent would
cube.append("belief", "User prefers dark mode in all editors")
cube.append("trait",  "User values concise replies over verbosity")
cube.append("resolve", "Deployed auth module v2.1", outcome="success")

# Ask semantic questions — understands meaning, not just keywords
engine = HARQueryEngine(cube)
engine.evolve()  # build topic clusters
results = engine.query("what theme does the user like?")

for entry, score in results:
    print(f"[{entry.entry_type}] {entry.description}  score={score:.4f}")
```

---

See **[Framework housing](docs/FRAMEWORK.md · docs/DAY_TO_DAY.md)** for the full in-cube OS.

## Colony communication (Cube-native)

Memories **talk to each other** via stigmergy (inspired by ants/bees + mammal social maps — not a copy of any other plugin):

- **Ant trails** — entity–entity pheromone edges strengthen when memories are used together
- **Bee dances** — each entry encodes *what* (kind) + *where* (entities)
- **Markdown board** — `$HERMES_HOME/memories/COLONY.md` (readable colony song sheet)

## How It Works

A `.cube` file stores three layers:

<table>
<tr>
  <td width="80"><b>L1</b></td>
  <td width="200">Entry log</td>
  <td>Append-only. Every memory is a timestamped record with a type, outcome, and 256-dimensional HRR vector.</td>
</tr>
<tr>
  <td><b>L2</b></td>
  <td>Topic index</td>
  <td>64 k-means centroids, rebuilt on <code>evolve()</code>. Maps queries to relevant buckets in O(log n).</td>
</tr>
<tr>
  <td><b>L3</b></td>
  <td>&beta; vector</td>
  <td>The agent's attention state. Bind it with your query to bias retrieval toward what the agent cares about.</td>
</tr>
</table>

**HAR queries** bind your question with the β attention vector, match against
topic centroids, retrieve the best entries, and rank by semantic similarity ×
recency. If confidence is low, it falls back to a linear scan. You get
logarithmic search with the safety of exhaustive fallback.

```
query("what theme?")
  → embed("what theme?")                  → q
  → bind(q, β)                            → qβ
  → match qβ against L2 centroids         → top 3 buckets
  → retrieve entries from those buckets   → candidates
  → rank by cosine_sim × e^(-age/48h)     → results
```

---

## Features

| | | |
|---|---|---|
| **HAR retrieval** | Semantic search without an embedding API | `engine.query("deployment issues")` |
| **Learned embeddings** | TF-IDF trains on your data, improves with use | Auto-trains during `evolve()` |
| **Atomic writes** | `.tmp` → `fsync` → `os.replace()` — crash-safe | No partial files survive |
| **Cross-process lock** | `fcntl.flock(LOCK_EX)` — two processes can't race | Clear error, no corruption |
| **10 entry types** | landmark, belief, trait, focus, resolve, evolution, relationship, enter, leave, epoch_transition | Rich memory modeling |
| **Threat scanning** | 6 injection/escape patterns blocked before storage | `scan_text()` with block/warn |
| **Circuit breaker** | 3 evolve failures → 5-min cooldown | Prevents cascading failures |
| **Auto-extract** | Regex-based fact extraction on session end | "I prefer X" → trait entry |
| **Zero dependencies** | Pure Python with numpy autodetect | `pip install hermescube` |
| **HermesAgent native** | Drop-in `MemoryProvider` plugin with 3 tools | `memory.provider: hermescube` |

---

## Quick Start (library / scratch cube)

For Hermes users, prefer **Install into Hermes Agent** above (user home paths).

```bash
pip install hermescube

# Scratch cube in cwd (explicit path)
hermescube init ./scratch.cube
hermescube append ./scratch.cube -t belief -d "User prefers dark mode"
hermescube evolve ./scratch.cube
hermescube query ./scratch.cube "what does the user prefer?"
hermescube info ./scratch.cube

# After Hermes install — defaults to $HERMES_HOME/memories/memory.cube
hermescube info
hermescube query "what does the user prefer?"
hermescube doctor
```

---

## HermesAgent Integration

Full install is at the top of this README. After `memory.provider: hermescube`:

| Tool | Purpose |
|------|---------|
| `hermescube_search` | Semantic search over past conversations |
| `hermescube_manage` | Add or remove persistent memories |
| `hermescube_feedback` | Rate entries helpful/unhelpful (trains trust scores) |

```python
from hermescube.provider import CubeMemoryProvider
import os

home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
provider = CubeMemoryProvider()
provider.initialize(session_id="abc123", hermes_home=home)
context = provider.prefetch("user's current question")
provider.sync_turn(user_msg, assistant_msg)
```

User data path is always `$HERMES_HOME/memories/memory.cube`.

---

## Real-use bench (for operators)

```bash
# Results land in ~/.hermes/hermescube-lab/results/ — not the repo
PYTHONPATH=. python3 benchmarks/real_use_bench.py
hermescube update   # after pull
```

Gates: durable facts beat noise, prefetch p50 &lt; 25ms, questions don't bury facts, cross-session OK.

## Benchmarks

HAR query latency scales logarithmically with archive size.

| Entries | HAR | Linear scan | Speedup |
|---------|-----|-------------|---------|
| 10 | 0.4 ms | 0.2 ms | 0.5× |
| 100 | 0.7 ms | 1.2 ms | 1.7× |
| 500 | 1.2 ms | 5.8 ms | 4.8× |
| 1,000 | 1.5 ms | 11.4 ms | **7.6×** |

---

## Entry Types

Choose the right type for each memory.

| Type | Use for | Example |
|------|---------|---------|
| `landmark` | Notable events, decisions | "Deployed v2 to production" |
| `belief` | Learned facts, conclusions | "Pyright catches type errors early" |
| `trait` | User characteristics | "Prefers dark mode editors" |
| `focus` | Current priorities | "Working on auth module" |
| `resolve` | Completed tasks | "Fixed login timeout bug" |
| `evolution` | Changes in understanding | "Migrated from flask to fastapi" |
| `relationship` | Entity connections | "auth-service depends on redis" |
| `enter` | Session start | "Started coding session" |
| `leave` | Session end | "Ended coding session" |
| `epoch_transition` | Phase shifts | "Completed project milestone" |

---

## Documentation

| | |
|---|---|
| **[User Guide](docs/USER_GUIDE.md)** | How-tos: install, store, search, evolve, integrate |
| **[API Reference](docs/API_REFERENCE.md)** | Every module, class, and function documented |
| **[Architecture](docs/ARCHITECTURE.md)** | Design rationale, algorithms, data flow |
| **[Binary Format Spec](docs/SPEC.md)** | `.cube` file layout, HRR algebra, HAR protocol |
| **[Contributing](CONTRIBUTING.md)** | Setup, testing, conventions, PR process |

---

## Project Structure

```
hermescube/
├── hermescube/          # Core library (7 modules, zero required deps)
│   ├── hrr.py            # HRR algebra — bind, unbind, superpose, embed
│   ├── cube.py           # .cube binary format — atomic read/write
│   ├── har.py            # HAR query engine — k-means, retrieval, ranking
│   ├── embed.py          # Learned embeddings — TF-IDF + projection
│   ├── provider.py       # CubeMemoryProvider — HermesAgent ABC
│   ├── threats.py        # Injection scanning — 6 patterns
│   ├── cli.py            # CLI — 7 commands
│   └── __init__.py       # Public API surface
├── plugin/               # HermesAgent plugin
│   ├── __init__.py        # register(ctx) entry point
│   ├── cli.py             # Plugin CLI (status, evolve, dump, compact)
│   └── plugin.yaml        # Plugin metadata
├── tests/                # 158 tests (pytest)
├── docs/                 # Full documentation suite
├── benchmarks/           # HAR vs linear scan
├── CONTRIBUTING.md
├── CHANGELOG.md
└── README.md
```

---

## License

MIT — see [LICENSE](LICENSE).
