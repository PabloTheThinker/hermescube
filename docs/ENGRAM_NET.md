# Engram Net + Hermes RE notes (0.14)

## Hermes native memory (reverse engineered)

Lifecycle (`MemoryProvider` ABC → `MemoryManager`):
1. `initialize` — warm store  
2. `system_prompt_block` — static instructions  
3. `prefetch(query)` — **before** each turn (fast; cache OK)  
4. `sync_turn(user, asst)` — **after** turn durable write  
5. `queue_prefetch` — background next-turn  
6. Optional: `on_memory_write`, `on_session_end`, `on_pre_compress`

**Teknium/Nous pattern (public product thinking):** closed loop — agent *uses* memory, feedback trains what to keep; skills from experience; journey not black box; one external provider socket (no bloat).

Stock **holographic**: strong fact algebra (probe/reason/contradict).  
**Cube**: warehouse + WAL + wisdom + yield + **engram net**.

## Engram Net (new)

Software neural field inside Cube infrastructure:
- **Pattern bank** — multi-entry mean vectors; query completes via exp-kernel attention (modern Hopfield energy surrogate)
- **Co-graph** — Hebbian edges between entry ids when retrieved together
- **Shadow learn** on every successful query set
- **Feedback** rewires cohort (helpful ↑ / unhelpful ↓)
- Multiplies HAR scores in ~[0.88, 1.42]

Complements Yield Gradient (query→entry value) with **entry↔entry structure** — closer to cortical association areas.

## X / Teknium

Direct X scrape blocked this session (rate limit). Used: Nous/Hermes learning-loop principles already encoded in Cube PURPOSE + prior journey/yield work + MemoryProvider contract in-tree.
