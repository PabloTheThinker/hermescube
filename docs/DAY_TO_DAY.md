# Day-to-day memory layering

HermesCube is an **extension** of Hermes agent memory — not a replacement.

## Two layers (both stay on)

| Layer | What | When |
|-------|------|------|
| **Hot** | `MEMORY.md` + `USER.md` | Always injected; short doctrine |
| **Deep** | HermesCube `.cube` | Prefetch each turn; long archive + chat |

```
Agent turn
  ├─ system: SOUL + MEMORY.md + USER.md + Cube system_prompt_block
  ├─ user msg + Cube prefetch (relevant deep recall)
  ├─ model reply
  ├─ Cube sync_turn  → WAL durable (no async drop)
  └─ if memory tool wrote MEMORY.md → Cube on_memory_write mirror
Session end → flush + sleep evolve
```

## No day-to-day interruption

- **One provider** at a time (`memory.provider: hermescube`) — Hermes rule.
- Built-in **memory tool still works**; Cube **mirrors** those writes into the archive.
- Prefetch is sub-ms warm; does not block chat.
- Turns are **sync-persisted** to cubelog before the turn returns.

## Agent mental model

> I have a pocket notebook (MEMORY.md) and a warehouse (Cube).  
> Notebook = what I always keep open. Warehouse = everything I might need later.  
> Writing in the notebook also files a copy in the warehouse.

## Config

```yaml
memory:
  provider: hermescube   # deep layer
  # MEMORY.md / USER.md still loaded by Hermes core
```

## Ops check

```bash
hermescube doctor
# after a chat day:
hermescube info
hermescube query "what did we decide"
```
