# PURPOSE.md — HermesCube north star

**One line:** HermesCube is the **local deep-memory warehouse** for Hermes Agent — long-tail durable recall that works *with* hot MEMORY.md, not instead of it.

## Problem

Agents lose the long tail: context windows fill, MEMORY.md is char-capped, cloud memory leaks and costs, flat logs don't retrieve by meaning under load.

## Solution (layered — Hermes 0.19+ contract)

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

**Living Cube (0.21+):** Hermes is the active nervous system; HermesCube is
the durable lifetime structure — immutable events → temporal claims →
verified procedures, with subagent branches and branched consolidation.
Compression never erases provenance.

**Hive nexus (0.22+):** many agents, one collective. Each agent keeps its
private cube (its soul-record); a shared hive directory holds the collective
cube plus soul cards. Nightly pilgrimage: OFFER distilled experience →
ASSIMILATE (threat-scanned, deduped, branch-tagged) → DRAW focus-relevant
wisdom back, quarantined as `hive_shared` and labeled `[HIVE:<agent>]`.
See [docs/HIVE.md](docs/HIVE.md).

**Grounded self-evolution (0.23+):** the Cube improves itself under rules
enforced in code — real friction lands in an append-only witness ledger,
every evolve cycle reports (no silent failures), promotions commit
falsifiable predictions a verifier later settles, a mechanical critic flags
bookkeeping theatre, and a gardener surfaces dormant memories without
deleting. See [docs/SELF_EVOLUTION.md](docs/SELF_EVOLUTION.md).

| Layer | Job | Cube relation |
|-------|-----|----------------|
| MEMORY.md | Hot inject, tiny | Extended via `on_memory_write` mirror |
| memory tool | Agent-initiated doctrine | Mirrored into cube |
| **Cube** | WAL turns, deep archive, entity/colony, dense export | **This package** |
| Hermespace | FOA / dual-decode / load | `space_bridge` tiny strip |

## Non-goals

- Not a second agent brain / not J-space weights  
- Not a cloud memory SaaS  
- Not a replacement for MEMORY.md  
- Not “HAR always beats scan” marketing — lex-first + bio rank; honest benches  

## Yield Gradient (0.8+)

Closed loop: feedback teaches which memories *pay off for similar queries* (query-local, not global trust / not colony trails). Hot path stays multiplicative boost only.

## Success metrics

1. **No lost day-to-day turns** — WAL sync before return  
2. **Hot path ms-class** — warm prefetch without full L1 every inject  
3. **IR useful** — hybrid lexical+HRR; score-first; labeled recall tracked  
4. **User data isolation** — only `$HERMES_HOME/memories/memory.cube`  
5. **Company agents** — same plugin socket; cube = deep extension per profile  

## Research spine (Fudoshin)

Canon: `brain/research/hermes-stack-benchmarks/`  
Study tree: clean Hermes `v2026.7.20` at `~/projects/hermes-agent-study`  
Key RE: MemoryProvider ABC, MemoryManager one-external, `<memory-context>` fence, builtin+external coexistence.

## Version posture

Ship purpose-aligned increments. Public GH scrubbed. `hermescube update` never overwrites cube data.
