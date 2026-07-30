# Code map — where to edit

HermesCube is one Python package (`hermescube/`) plus a thin Hermes plugin (`plugin/`).  
Prefer **peeling** new surfaces into focused modules over growing `provider.py`.

**Architecture:** [ARCHITECTURE.md](ARCHITECTURE.md) is the whole-project blueprint.  
This file is the **edit guide** keyed to those layers.

## Layers (edit here first)

```
L7 heart/center     space_bridge.py  center.py
L6 dream            dream.py  dream_circle.py  manage_dream.py
L5 fleet            hive.py  hq.py  interview.py  manage_fleet.py
L4 growth           genealogy.py  living.py  curator.py  self_evolution.py
L3 cuboasis         cuboasis.py  cubewave.py  memory_gate.py  manage_cuboasis.py
L2 provider         provider.py  manage*.py  tools_recall.py  session_end.py
L1 warehouse        cube.py  har.py  hrr.py  embed.py  threats.py  bio_rank.py
L0 framework        framework/paths.py  config.py  void.py  lexindex.py
```

## Core warehouse (L1)

| Module | Role |
|--------|------|
| `cube.py` | `.cube` binary I/O, entries, atomic write |
| `hrr.py` | HRR algebra (bind / unbind / superpose) |
| `har.py` | HAR query engine, centroids, ranking |
| `embed.py` | Learned TF-IDF embedder |
| `threats.py` | Injection scan before store |
| `cli.py` | `hermescube` CLI |
| `bio_rank.py` / `dense.py` | Ranking helpers, dense export |

## Provider socket (L2)

| Module | Role |
|--------|------|
| `provider.py` | `CubeMemoryProvider` — prefetch, sync, prompt block |
| `tools_recall.py` | Search / probe / feedback tools |
| `manage.py` | Manage hub — dispatches to peels below |
| `manage_warehouse.py` | Append, evolve, density, relations… |
| `manage_cuboasis.py` | Space / connect / progress / policy |
| `manage_growth.py` | Growth, curator, genealogy surfaces |
| `manage_fleet.py` | Hive / HQ / interview manage actions |
| `manage_dream.py` | CubeDream manage actions |
| `session_end.py` | End-of-session pipeline |
| `bootstrap.py` / `agent_manual.py` | First-connect + operating manual |

## Cuboasis & living archive (L3–L4)

| Module | Role |
|--------|------|
| `cuboasis.py` / `cubewave.py` | Pocket infra + neural field |
| `memory_gate.py` / `evidence.py` | Review-first writes |
| `living.py` / `genealogy.py` / `curator.py` | Growth eras, diary, skill refine |
| `colony.py` / `relations.py` / `engram_net.py` | Stigmergy / graphs |
| `events.py` / `claims.py` / `procedure.py` | Living archive primitives |
| `consolidate.py` / `branches.py` | Branched consolidation |
| `self_evolution.py` | Witness / predictions / critic / gardener |
| `journey.py` / `wisdom.py` | Journey ledger + active wisdom |
| `framework/` | Lex index, paths, void helpers |

## Fleet & CubeDream (L5–L6)

| Module | Role |
|--------|------|
| `hive.py` | Pilgrimage offer / assimilate / draw |
| `hq.py` | Charters, routes, handoffs, claims |
| `interview.py` | Peer interview protocol |
| `dream.py` | L1 soul dream + L4 proposals |
| `dream_circle.py` | L2 circle (chorus, dialogue, skim, auto) |
| `nexus.py` | Compat shim → cuboasis |

## Hermespace heart (L7)

| Module | Role |
|--------|------|
| `space_bridge.py` | Heart pump API `1.0` — ensure / inject / seal / pulse |
| `center.py` | Anatomical center `1.2` (blackbox + breathe) — beat / supply / return / autonomic |

## Plugin & skills

| Path | Role |
|------|------|
| `plugin/` | Hermes `register(ctx)` + plugin CLI |
| `plugin.yaml` + root `plugin.yaml` | **Must stay identical** (`scripts/check_isolation.sh`) |
| `skills/hermescube-operate` | Day-to-day operate skill |
| `skills/hermescube-import` | Import / bootstrap skill |
| `skills/interview-me` | Interview protocol skill |

## Tests & scripts

| Path | Role |
|------|------|
| `tests/` | pytest suite (target: green + isolation) |
| `scripts/install_hermes.sh` | Wire into Hermes Python + config |
| `scripts/update.sh` / `check_isolation.sh` | Update + dual-yaml guard |
| `benchmarks/` | HAR / real-use / heart benches (results outside repo) |

## Rules of thumb

1. User data only under `$HERMES_HOME/memories/` — never commit cubes.  
2. New manage actions → peel module, not a 200-line blob in `provider.py`.  
3. CubeDream must never auto-rewrite Hermes `MEMORY.md` (proposals only).  
4. Solo path first; hive/HQ/dream-circle are opt-in.  
5. Hermespace integration goes through `center` / `space_bridge` — soft-fail only.
