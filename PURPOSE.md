# PURPOSE.md — HermesCube north star

**One line:** HermesCube is the **local deep-memory generator** for Hermes Agent — the durable warehouse that **powers Hermespace**, working *with* hot MEMORY.md, not instead of it.

Public pitch: **[ABOUT.md](ABOUT.md)**. Docs index: **[docs/README.md](docs/README.md)**. Code layout: **[docs/CODEMAP.md](docs/CODEMAP.md)**. Hermespace contract: **[docs/HERMESPACE.md](docs/HERMESPACE.md)**.

---

## Problem

Agents lose the long tail: context windows fill, MEMORY.md is char-capped, cloud memory leaks and costs, flat logs don't retrieve by meaning under load — and a workbench alone cannot invent a lifetime archive.

## Solution (Hermes + Hermespace stack)

```
┌─────────────────────────────────────────────────────────────────┐
│ Hermes Agent                                                    │
│  state.db · MEMORY.md · skills · memory tool                    │
│  MemoryProvider socket ──► HermesCube  (ONE external plugin)    │
│                                                                 │
│  Hermespace          pocket workbench (FOA · dual decode · load)│
│    ↑ powered by generator                                       │
│  HermesCube          living warehouse + generator core          │
│    .cube · Cuboasis · Hive · CubeDream · growth                 │
│    space_bridge → inject strip · seal · world-belief charge     │
└─────────────────────────────────────────────────────────────────┘
```

| Layer | Job | Relation |
|-------|-----|----------|
| MEMORY.md | Hot doctrine (tiny, always-on) | Cube mirrors via `on_memory_write` |
| memory tool | Agent-initiated hot writes | Mirrored into cube |
| **HermesCube** | Durable warehouse + **generator** | **This package** — SoT for long-tail memory |
| **Hermespace** | FOA desk / dual decode / inject budget | Consumes Cube power; never a second archive |

Hermespace without Cube is a desk with no deep floor.  
Cube without Hermespace is still a complete memory plugin.  
**Together:** Cube generates durable truth; Space focuses the turn.

### Generator (Cube → Hermespace)

| Surface | API | What Space gets |
|---------|-----|-----------------|
| **Inject power** | `space_bridge.build_space_inject` | Cap-bounded FOA strip (wisdom → hubs → query) |
| **Seal intake** | `space_bridge.seal_to_cube` | Desk decisions → durable `.cube` |
| **World charge** | `space_bridge.sync_world_beliefs` | Active wisdom → Hermespace `WorldModel` |
| **Status** | `space_bridge.module_status` | Generator readiness |

**Rule:** `memory.cube` is authoritative for durable memory. Hermespace world/desk
projections are working surfaces — charged from Cube, never a competing SoT.
See [docs/HERMESPACE.md](docs/HERMESPACE.md).

## Solo path vs fleet path

| Path | Day-to-day surface | Optional |
|------|--------------------|----------|
| **Solo** (default) | prefetch · sync_turn · feedback · triage · Cuboasis · dream solo | crystalize / merge / relations |
| **Fleet** | hive · HQ · interview · dream circle | only when hive is configured |

New operators learn the solo path first. Fleet layers compound on top.
Hermespace is orthogonal: a turn workbench that can sit on either path.

## Capability stack (current product)

| Area | What ships | Doc |
|------|------------|-----|
| Warehouse | `.cube`, HAR, WAL, threat scan, dense export | SPEC · ARCHITECTURE |
| Cuboasis | review-first, space, Cubewave, connections, progress | CUBOASIS |
| Living growth | Eden→Elder, CUBE.md diary, curator | GROWTH |
| Self-evolution | witness, predictions, critic, gardener | SELF_EVOLUTION |
| Hive / HQ / interviews | pilgrimage, charters, peer craft | HIVE · HQ · INTERVIEW |
| **CubeDream (0.47)** | L1 solo · L2 circle · auto-circle · skim · L4 proposals | CUBEDREAM |
| **Hermespace heart (0.48)** | `ensure_heart` · inject · seal · pulse charge (`space_bridge` 1.0) | HERMESPACE |

**First connect:** empty warehouse → optional auto-bootstrap from MEMORY.md/USER.md + operate/import skills. Manual: `hermescube_manage action=bootstrap mode=all`.

## Non-goals

- Not a second agent brain / not J-space weights  
- Not a cloud memory SaaS  
- Not a replacement for MEMORY.md **or** for Hermespace’s FOA desk  
- Not “HAR always beats scan” marketing — lex-first + bio rank; honest benches  
- Not AgentDrive / Mission Control — borrow algorithms, not the conductor OS  
- **Never** auto-rewrite Hermes MEMORY.md from Cube dream paths (proposals only)  
- Cube does **not** require Hermespace; Space does **not** reimplement Cube  

## Success metrics

1. **No lost day-to-day turns** — WAL sync before return  
2. **Hot path ms-class** — warm prefetch without full L1 every inject  
3. **IR useful** — hybrid lexical+HRR; score-first; labeled recall tracked  
4. **User data isolation** — only `$HERMES_HOME/memories/`  
5. **Hermespace powered** — under high load, Space inject stays cap-bounded *and* memory-bearing via Cube strip  
6. **One SoT** — desk seals flow into Cube; world beliefs recharge from Cube wisdom  
7. **Compounding sessions** — growth-merge / triage / dream without theatre  

## Version posture

Ship purpose-aligned increments. Dual `plugin.yaml` must stay identical.  
`hermescube update` never overwrites cube data. Assessment: [docs/ASSESSMENT.md](docs/ASSESSMENT.md).  
Hermespace upgrades should deepen the **generator** link (inject / seal / charge), not fork a second archive.

### Historical layer notes (compressed)

Living Cube (0.21) · Hive (0.22) · self-evolution (0.23) · Fleet HQ (0.24) · interviews (0.25) · one night cycle (0.26) · living growth (0.27–0.30 Eden) · Cuboasis (0.40) · bootstrap/manual (0.43) · manage peels (0.45) · CubeDream MVP→full (0.46–0.47). Detail lives in [CHANGELOG.md](CHANGELOG.md).
