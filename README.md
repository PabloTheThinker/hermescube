<p align="center">
  <img src="docs/assets/hermescube-047-cubedream-graphic-novel.png" alt="HermesCube · CubeDream" width="100%">
</p>

# HermesCube

<p align="center">
  <em>Local deep-memory warehouse for Hermes Agent — durable, semantic, offline.</em>
</p>

<p align="center">
  <a href="ABOUT.md"><img src="https://img.shields.io/badge/About-what%20%26%20why-0A7A6A?style=for-the-badge" alt="About"></a>
  <a href="https://github.com/PabloTheThinker/hermescube/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/CI-passing-34D058?style=for-the-badge" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-blue?style=for-the-badge" alt="Python 3.11+">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/version-0.47.0-informational?style=for-the-badge" alt="0.47.0">
</p>

**HermesCube plugs into [Hermes Agent](https://github.com/NousResearch/hermes-agent) as the one external `MemoryProvider`.** Hermes keeps the hot notebook (`MEMORY.md`); Cube keeps the long tail — a crash-safe `.cube` archive with holographic associative retrieval, Cuboasis governance, living growth, and optional multi-agent Hive / CubeDream.

No cloud memory APIs. No pruning tax. Your data stays under `$HERMES_HOME/memories/`.

<table>
<tr><td><b>Works with Hermes, not instead of it</b></td><td>Hot MEMORY.md stays always-on. Cube mirrors writes, WAL-syncs turns, and injects a small deep strip when useful.</td></tr>
<tr><td><b>Semantic recall, local</b></td><td>HAR + learned embeddings + entity/colony graphs — meaning over keywords, no embedding SaaS.</td></tr>
<tr><td><b>Safe under load</b></td><td>Atomic writes, cross-process lock, threat scan, Cuboasis review-first candidates.</td></tr>
<tr><td><b>Grows with the agent</b></td><td>Cube of Eden → Elder living version, diary, curator skill refine, grounded self-evolution harness.</td></tr>
<tr><td><b>Dream alone or together</b></td><td><a href="docs/CUBEDREAM.md">CubeDream</a>: soul solo cycles, dream circles (chorus / conversation), hive commit, MEMORY.md proposals only — never auto-applied.</td></tr>
<tr><td><b>Powers Hermespace</b></td><td><a href="docs/HERMESPACE.md">Generator core</a> for the Hermespace FOA desk — dense inject strips, seals, world-belief charge. Space focuses the turn; Cube holds the floor.</td></tr>
<tr><td><b>Fleet when you need it</b></td><td>Optional Hive pilgrimage, Fleet HQ routing/handoffs, peer interviews. Solo path is enough for day one.</td></tr>
</table>

Read the product pitch in **[ABOUT.md](ABOUT.md)**. North star for maintainers: **[PURPOSE.md](PURPOSE.md)**.

---

## Install into Hermes Agent

Your cube lives under **your** Hermes home — never inside the git tree.

```bash
# Option A — Hermes plugin installer (recommended)
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
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
| `$HERMES_HOME/plugins/hermescube/` | Plugin code |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory data |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` |

### Update

```bash
hermescube update
# or: hermes plugins update hermescube   then   hermescube update
```

`hermes update` updates Hermes Agent core only. Cube is a plugin — use `hermescube update`.  
User memory is **never** overwritten by update.

---

## Getting started

```bash
hermescube doctor              # wiring + density / bootstrap hints
hermescube info                # warehouse stats
hermescube query "…"           # semantic search
hermescube dream status        # CubeDream due reasons
hermescube dream solo          # private night cycle (add --apply to commit)
hermescube dense               # dense export for backup / density view
```

After `memory.provider: hermescube`, the agent gets four tools:

| Tool | Purpose |
|------|---------|
| `hermescube_search` | Semantic search over the warehouse |
| `hermescube_manage` | Hub: warehouse · Cuboasis · growth · fleet · dream |
| `hermescube_feedback` | Rate memories helpful / unhelpful (yield gradient) |
| `hermescube_probe` | Diagnostic probe / density peeks |

First connect on an empty warehouse auto-imports MEMORY.md / USER.md (when enabled) and installs operate/import skills. Manual: `hermescube_manage action=bootstrap mode=all`.

---

## How the `.cube` works

Three layers inside the file:

| | | |
|---|---|---|
| **L1** | Entry log | Append-only records + 256-d HRR vectors |
| **L2** | Topic index | Centroids rebuilt on `evolve()` — O(log n) buckets |
| **L3** | β attention | Bind with the query to bias toward what matters now |

```
query("what theme?")
  → embed → bind(q, β) → match L2 centroids → rank sim × recency
  → low confidence falls back to linear scan
```

Full algebra and on-disk layout: [docs/SPEC.md](docs/SPEC.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Library quick start

Prefer Hermes install above for real agent use. For a scratch cube:

```bash
pip install -e .                 # from a clone; optional: numpy
hermescube init ./scratch.cube
hermescube append ./scratch.cube -t belief -d "User prefers dark mode"
hermescube evolve ./scratch.cube
hermescube query ./scratch.cube "what does the user prefer?"
```

```python
from hermescube import CubeFile, HARQueryEngine

cube = CubeFile.create("memory.cube")
cube.append("belief", "User prefers dark mode in all editors")
engine = HARQueryEngine(cube)
engine.evolve()
for entry, score in engine.query("what theme does the user like?"):
    print(entry.entry_type, entry.description, f"{score:.4f}")
```

---

## Documentation

| | |
|---|---|
| **[About](ABOUT.md)** | What HermesCube is (and is not) |
| **[Docs index](docs/README.md)** | Full map of guides |
| **[User Guide](docs/USER_GUIDE.md)** | Install, store, search, evolve |
| **[Day-to-day](docs/DAY_TO_DAY.md)** | Operator usefulness |
| **[CubeDream](docs/CUBEDREAM.md)** | Solo + together dreaming |
| **[Cuboasis](docs/CUBOASIS.md)** | Space, Cubewave, policy |
| **[Hive](docs/HIVE.md)** · **[HQ](docs/HQ.md)** · **[Interviews](docs/INTERVIEW.md)** | Multi-agent |
| **[Code map](docs/CODEMAP.md)** | Where to edit in the package |
| **[Assessment](docs/ASSESSMENT.md)** | Honest ship grades |
| **[Contributing](CONTRIBUTING.md)** | Dev setup, tests, PRs |

---

## Project structure

```
hermescube/
├── ABOUT.md                 # Product about
├── PURPOSE.md               # North star (maintainers / agents)
├── hermescube/              # Library + CLI + MemoryProvider
│   ├── cube.py · har.py · hrr.py · embed.py
│   ├── provider.py          # Hermes MemoryProvider socket
│   ├── tools_recall.py      # search / probe / feedback
│   ├── manage*.py           # manage hub peels
│   ├── dream.py · dream_circle.py
│   ├── cuboasis.py · hive.py · hq.py · interview.py
│   └── …                    # see docs/CODEMAP.md
├── plugin/                  # Hermes plugin register + CLI
├── skills/                  # hermescube-operate · import · interview-me
├── docs/                    # Guides + assets/
├── tests/                   # pytest (466+)
├── scripts/                 # install · update · isolation check
└── benchmarks/              # HAR / real-use (results outside repo)
```

---

## Real-use bench

```bash
# Results land in ~/.hermes/hermescube-lab/results/ — not the repo
PYTHONPATH=. python3 benchmarks/real_use_bench.py
```

Gates: durable facts beat noise, warm prefetch stays ms-class, questions don't bury facts.

---

## License

MIT — see [LICENSE](LICENSE).  
Built to sit beside [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent); not affiliated as an official Nous product.
