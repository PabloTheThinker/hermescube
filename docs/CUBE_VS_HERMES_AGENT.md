# HermesCube vs Hermes Agent memory (holographic)

Head-to-head on the same 8 core facts + filler scale. Both implement Hermes `MemoryProvider`.

**Not included:** hot `MEMORY.md` / `USER.md` inject (always-on Hermes layer, separate from plugins).

_Stamp: 2026-07-22T16:31:24.847321+00:00_

## Prefetch latency & hit rate

| Approx N | Cube avg ms | Holo avg ms | Cube hit | Holo hit | Cube vs holo (× if >1 Cube faster) |
|----------|------------:|------------:|---------:|---------:|-------------------------------------:|
| 8 | 1.265 | 0.679 | 1.0 | 1.0 | 0.54× |
| 58 | 5.65 | 0.63 | 1.0 | 1.0 | 0.11× |
| 208 | 1.058 | 1.052 | 1.0 | 1.0 | 0.99× |
| 508 | 1.591 | 0.615 | 1.0 | 1.0 | 0.39× |
| 1008 | 2.296 | 0.623 | 1.0 | 1.0 | 0.27× |

## Takeaways

1. **Both** can hit core facts when seeded cleanly.
2. At **small N**, stock holographic is often slightly faster (lean SQLite fact store).
3. **HermesCube** auto-`sync_turn` (conversation → memory); holographic is tool-add unless auto_extract is on.
4. Cube: install/update under `$HERMES_HOME`, typed entries, sleep consolidate, durable-vs-noise ranking.
5. Pick **holographic** for fact_store/entity tools; **hermescube** for always-on turn archive + hierarchical cube.
