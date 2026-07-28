# PURPOSE.md — HermesCube north star

**One line:** HermesCube is the **local deep-memory warehouse** for Hermes Agent — long-tail durable recall that works *with* hot MEMORY.md, not instead of it.

Public pitch: **[ABOUT.md](ABOUT.md)**. Docs index: **[docs/README.md](docs/README.md)**. Code layout: **[docs/CODEMAP.md](docs/CODEMAP.md)**.

---

## Problem

Agents lose the long tail: context windows fill, MEMORY.md is char-capped, cloud memory leaks and costs, flat logs don't retrieve by meaning under load.

## Solution (Hermes MemoryProvider contract)

```
┌─────────────────────────────────────────────────────────┐
│ Hermes Agent                                            │
│  state.db                canonical sessions / tools     │
│  MEMORY.md / USER.md     short doctrine (always-on)     │
│  Skills                  executable procedures          │
│  memory tool batch       atomic hot writes              │
│  MemoryProvider socket   ONE external plugin            │
│       └── HermesCube     living warehouse + tools       │
│  Hermespace (optional)   FOA desk; cube strip under load│
└─────────────────────────────────────────────────────────┘
```

| Layer | Job | Cube relation |
|-------|-----|----------------|
| MEMORY.md | Hot inject, tiny | Extended via `on_memory_write` mirror |
| memory tool | Agent-initiated doctrine | Mirrored into cube |
| **Cube** | WAL turns, deep archive, Cuboasis, dream | **This package** |
| Hermespace | FOA / dual-decode / load | `space_bridge` tiny strip |

## Solo path vs fleet path

| Path | Day-to-day surface | Optional |
|------|--------------------|----------|
| **Solo** (default) | prefetch · sync_turn · feedback · triage · Cuboasis · dream solo | crystalize / merge / relations |
| **Fleet** | hive · HQ · interview · dream circle | only when hive is configured |

New operators learn the solo path first. Fleet layers compound on top.

## Capability stack (current product)

| Area | What ships | Doc |
|------|------------|-----|
| Warehouse | `.cube`, HAR, WAL, threat scan, dense export | SPEC · ARCHITECTURE |
| Cuboasis | review-first, space, Cubewave, connections, progress | CUBOASIS |
| Living growth | Eden→Elder, CUBE.md diary, curator | GROWTH |
| Self-evolution | witness, predictions, critic, gardener | SELF_EVOLUTION |
| Hive / HQ / interviews | pilgrimage, charters, peer craft | HIVE · HQ · INTERVIEW |
| **CubeDream (0.47)** | L1 solo · L2 circle · auto-circle · skim · L4 proposals | CUBEDREAM |

**First connect:** empty warehouse → optional auto-bootstrap from MEMORY.md/USER.md + operate/import skills. Manual: `hermescube_manage action=bootstrap mode=all`.

## Non-goals

- Not a second agent brain / not J-space weights  
- Not a cloud memory SaaS  
- Not a replacement for MEMORY.md  
- Not “HAR always beats scan” marketing — lex-first + bio rank; honest benches  
- Not AgentDrive / Mission Control — borrow algorithms, not the conductor OS  
- **Never** auto-rewrite Hermes MEMORY.md from Cube dream paths (proposals only)

## Success metrics

1. **No lost day-to-day turns** — WAL sync before return  
2. **Hot path ms-class** — warm prefetch without full L1 every inject  
3. **IR useful** — hybrid lexical+HRR; score-first; labeled recall tracked  
4. **User data isolation** — only `$HERMES_HOME/memories/`  
5. **Compounding sessions** — growth-merge / triage / dream without theatre  

## Version posture

Ship purpose-aligned increments. Dual `plugin.yaml` must stay identical.  
`hermescube update` never overwrites cube data. Assessment: [docs/ASSESSMENT.md](docs/ASSESSMENT.md).

### Historical layer notes (compressed)

Living Cube (0.21) · Hive (0.22) · self-evolution (0.23) · Fleet HQ (0.24) · interviews (0.25) · one night cycle (0.26) · living growth (0.27–0.30 Eden) · Cuboasis (0.40) · bootstrap/manual (0.43) · manage peels (0.45) · CubeDream MVP→full (0.46–0.47). Detail lives in [CHANGELOG.md](CHANGELOG.md).
