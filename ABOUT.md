# About HermesCube

**HermesCube is the local deep-memory generator for [Hermes Agent](https://github.com/NousResearch/hermes-agent).**  
It extends Hermes’s hot notebook (`MEMORY.md`) with a durable, semantic `.cube` archive — private to your `$HERMES_HOME`, offline, and crash-safe — and **powers [Hermespace](https://github.com/PabloTheThinker/hermespace)** as that workbench’s core.

It is **not** a second agent, a cloud memory SaaS, or a replacement for Hermes’s built-in memory tools. One plugin socket. One living warehouse. Hermespace is the FOA desk that runs on Cube power.

---

## What it is for

| You want… | HermesCube gives you… |
|-----------|------------------------|
| Memories that survive context compression | Append-only `.cube` + WAL turns under `$HERMES_HOME/memories/` |
| Recall by *meaning*, not grep | HAR + learned embeddings + entity/colony graphs (no embedding API) |
| Safe writes under load | Cuboasis review-first gates, threat scan, atomic `fsync` replace |
| Growth over months | Living version, diary (`CUBE.md`), maturity eras, curator |
| Optional multi-agent life | Hive pilgrimage, Fleet HQ, peer interviews, **CubeDream** circles |

## How it sits next to Hermes

```
Hermes Agent
├── MEMORY.md / USER.md     hot doctrine (always-on, char-capped)
├── state.db / skills       sessions + procedures
├── memory tool             agent-initiated hot writes
├── MemoryProvider  ──►  HermesCube          ← generator core
│                        ├── memory.cube      deep archive (SoT)
│                        ├── Cuboasis         governance + space
│                        ├── CubeDream        solo + together night cycles
│                        └── space_bridge     inject / seal / world charge
└── Hermespace (optional)   FOA desk powered by Cube generator
```

**Solo path (default):** prefetch → sync_turn → search/manage/feedback → optional dream solo.  
**Fleet path (opt-in):** hive / HQ / interviews / dream circles — only when hive is configured.

## Product layers (current: 0.47)

1. **Warehouse** — `.cube` binary, HAR retrieval, WAL, mirror from MEMORY.md  
2. **Cuboasis** — review-first memory policy, space, Cubewave, connections, progress  
3. **Living growth** — Cube of Eden → Elder; cycles; curator skill refine  
4. **Hive + HQ + interviews** — collective memory, routing, peer craft transfer  
5. **CubeDream** — L1 soul dream, L2 circle (chorus / conversation), L3 hive commit, L4 MEMORY.md *proposals only* (never auto-applied)  
6. **Hermespace heart (0.48)** — `ensure_heart` / inject / seal / pulse charge ([docs/HERMESPACE.md](docs/HERMESPACE.md))

## Non-goals

- Not a second brain or weight store  
- Not cloud sync or a hosted memory product  
- Not a replacement for `MEMORY.md`  
- Not AgentDrive / Mission Control — algorithms may be borrowed; the conductor OS is not  

## Where to go next

| Doc | Audience |
|-----|----------|
| [README.md](README.md) | Install, quick start, features |
| [PURPOSE.md](PURPOSE.md) | North star + version posture (agents / maintainers) |
| [docs/README.md](docs/README.md) | Full documentation index |
| [docs/CUBEDREAM.md](docs/CUBEDREAM.md) | Dreaming alone and together |
| [docs/HERMESPACE.md](docs/HERMESPACE.md) | Cube as Hermespace generator core |
| [docs/ASSESSMENT.md](docs/ASSESSMENT.md) | Honest ship grades |

**License:** MIT — [LICENSE](LICENSE)  
**Home:** https://github.com/PabloTheThinker/hermescube
