# PURPOSE.md — HermesCube north star

**One line:** HermesCube is the **library under Hermes** — the local deep-memory **book** and **generator core** of a Hermes base. It works *with* hot MEMORY.md (the desk catalog), not instead of it.

Public pitch: **[ABOUT.md](ABOUT.md)** · Install: **[README.md](README.md)** · Blueprint: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** · Heart: **[docs/HERMESPACE.md](docs/HERMESPACE.md)** · global-workspace research production: **[docs/HERMESPACE_PRODUCTION.md](docs/HERMESPACE_PRODUCTION.md)** · Provenance: **[docs/BLACKBOX.md](docs/BLACKBOX.md)**.

---

## Problem

Agents lose the long tail: context windows fill, MEMORY.md is char-capped, cloud memory leaks and costs, and flat session logs do not retrieve by meaning or compress into **chapters** over years.

## Solution (Hermes base)

```
Hermes base
├── Agent + skills + state.db     librarian + reading-room camera
├── MEMORY.md                     desk card catalog (always-on, small)
└── HermesCube                    ★ library building
      memory.cube                 bound volume (SoT for durable memory)
      blackbox                    heart provenance (prove runs)
      Cuboasis / growth / dream   rooms, editions, chapter-binding nights
      space_bridge → Hermespace   FOA desk powered by the stacks
```

| Layer | Job | Relation |
|-------|-----|----------|
| MEMORY.md | Hot doctrine (tiny) | Cube mirrors via `on_memory_write` |
| memory tool | Agent hot writes | Mirrored into the book |
| **HermesCube** | Durable library + generator | **This package** |
| **Blackbox** | Flight proof in the heart | Capture / prove / breathe |
| **Hermespace** | FOA desk | Consumes Cube power; never a second archive |

Hermespace without Cube is a desk with no deep floor.  
Cube without Hermespace is still a complete memory plugin.  
**Together:** Cube holds the library; Space focuses the turn.

### Library metaphor (product language)

| Metaphor | Mechanism |
|----------|-----------|
| Book | `memory.cube` per `$HERMES_HOME` / profile |
| Chapter / arc | Crystals, growth eras, dream consolidations, merge spines |
| Page | Single warehouse entry |
| Compress better than a log | Append → index by meaning → bind chapters (not infinite CCTV tape) |
| Multi-agent | Many readers; optional hive = inter-library loan |

### Generator (Cube → Hermespace)

| Surface | API | What Space gets |
|---------|-----|-----------------|
| **Inject power** | `space_bridge.build_space_inject` / `center.supply` | Cap-bounded FOA strip |
| **Seal intake** | `seal_learning` / `center.return_flow` | Desk decisions → book |
| **World charge** | `pulse_charge` / `center.autonomic_tick` | Wisdom → WorldModel |
| **Provenance** | `center.flight_*` / `center.breathe` | Evidence-oriented runs |
| **Status** | `center_status` / `heart_status` | Library + organ readiness |

**Rule:** `memory.cube` is authoritative for durable memory. Hermespace projections are working surfaces.

Anthropic **global-workspace research** (Jacobian lens / GWT-style FOA) is research instrumentation on activations. Hermespace is the **operator FOA desk** for Hermes Agent; HermesCube is the durable generator behind it. Production playbook: [docs/HERMESPACE_PRODUCTION.md](docs/HERMESPACE_PRODUCTION.md).

## Solo path vs fleet path

| Path | Day-to-day | Optional |
|------|------------|----------|
| **Solo** (default) | doctor · query · feedback · blackbox · triage · dream solo | crystalize / merge / relations |
| **Fleet** | hive · HQ · interview · dream circle | only when hive is configured |

New operators open the **library** first (remember + prove + doctor). Fleet is consortium, not day one.

## Capability stack (0.50 — library direction)

| Area | What ships | Doc |
|------|------------|-----|
| Warehouse (book) | `.cube`, HAR, WAL, threat scan, dense export | SPEC · ARCHITECTURE |
| Blackbox (heart stamp) | capture · prove · verify · breathe | BLACKBOX |
| Cuboasis | review-first, space, Cubewave | CUBOASIS |
| Living growth (editions) | Eden→Elder, CUBE.md, curator | GROWTH |
| Hive / HQ / interviews | pilgrimage, charters, peer craft | HIVE · HQ · INTERVIEW |
| CubeDream | L1 solo · L2 circle · L4 proposals only | CUBEDREAM |
| Center | beat · supply · return · blackbox organ · breathe | ANATOMY · HERMESPACE |

## Non-goals

- Not a second agent brain  
- Not a cloud memory SaaS  
- Not a replacement for MEMORY.md **or** Hermespace’s FOA desk  
- Not day-one feature tourism (hive/dream/HQ behind the front desk)  
- **Never** wipe `memory.cube` on `hermescube update`  
- **Never** auto-rewrite Hermes MEMORY.md from dream (proposals only)

## Success metrics

1. **No lost day-to-day turns** — WAL before return  
2. **Hot path ms-class** for prefetch (breathe stays post-session)  
3. **IR useful** — hybrid lexical+HRR; feedback tracked  
4. **User data isolation** — only `$HERMES_HOME/memories/`  
5. **Hermes base default** — `memory.provider=hermescube` is the deep core  
6. **Chapters form** — growth-merge / dream / crystals reduce raw sprawl  
7. **Prove when it matters** — blackbox claims on real trajectories  
8. **Community clarity** — remember + prove + doctor in the README hero  

## Version posture

Ship purpose-aligned increments. Dual `plugin.yaml` versions stay identical.  
`hermescube update` never overwrites cube data.

**0.50 direction:** name and ship the **library / chapter / Hermes-base core** story; blackbox + breathe as heart provenance; day-one surface stays thin.

### Historical layers (compressed)

Living Cube · Hive · self-evolution · Fleet HQ · interviews · Cuboasis · CubeDream · Hermespace heart (0.48) · anatomical center (0.49) · blackbox + library direction (0.50). Detail: [CHANGELOG.md](CHANGELOG.md).
