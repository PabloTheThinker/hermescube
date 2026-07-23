# PURPOSE.md — HermesCube north star

**One line:** HermesCube is the **local deep-memory warehouse** for Hermes Agent — long-tail durable recall that works *with* hot MEMORY.md, not instead of it.

## Problem

Agents lose the long tail: context windows fill, MEMORY.md is char-capped, cloud memory leaks and costs, flat logs don't retrieve by meaning under load.

## Solution (layered — Hermes 0.19 contract)

```
┌─────────────────────────────────────────────────────────┐
│ Hermes Agent                                            │
│  MEMORY.md / USER.md     short doctrine (always-on)     │
│  memory tool batch       atomic hot writes              │
│  MemoryProvider socket   ONE external plugin            │
│       └── HermesCube     warehouse .cube + tools        │
│  Hermespace (optional)   FOA desk; cube strip under load│
└─────────────────────────────────────────────────────────┘
```

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
