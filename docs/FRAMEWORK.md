# HermesCube framework housing

How memory **operates inside** the cube — Hermes only provides the socket
(`MemoryProvider`) and `$HERMES_HOME`. Everything else is Cube-owned.

## Layers

```
┌─────────────────────────────────────────────────────────┐
│  Hermes Agent                                           │
│    memory.provider: hermescube                          │
│    MemoryProvider ABC (prefetch / sync_turn / tools)    │
└──────────────────────────┬──────────────────────────────┘
                           │ adapter
┌──────────────────────────▼──────────────────────────────┐
│  CubeMemoryProvider  (hermescube/provider.py)           │
│    Hermes lifecycle + tools + session snapshot          │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│  framework/  — Cube OS                                  │
│    paths.py     user-home locations                     │
│    config.py    plugins.hermescube config               │
│    void.py      CubeVoid — recall / reinforce / board   │
│    lexindex.py  inverted index (holo-class candidates)  │
├─────────────────────────────────────────────────────────┤
│  bio_rank · mirror · colony · har · cube · embed · hrr  │
└─────────────────────────────────────────────────────────┘
                           │
              $HERMES_HOME/memories/
                 memory.cube
                 colony_graph.json
                 COLONY.md
                 memory.embedder
```

## Infinite void (CubeVoid)

1. **Imprint** — append L1 with entity hygiene + optional dance  
2. **Recall** — HAR/scan → bio rank → mirror expand → colony trail boost  
3. **Lexindex** — shrink candidates before scan when N is large  
4. **Stigmergy** — ants/bees trails; board throttled (not every prefetch)  
5. **Sleep** — evolve offline only  

## Design rules

- Learn frameworks from others; **remake** inside Cube (no clone of holographic SQLite stack).  
- Hot path: no LLM rewrite by default.  
- User data never in the git tree.  
- Colony board is human-readable culture sheet.

## Version

Introduced as structured housing in **0.5.0** (review fixes + framework package).
