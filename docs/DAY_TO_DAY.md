# Day-to-day usefulness

HermesCube is an **extension** of Hermes agent memory — not a replacement.
This page is the short loop for *making the warehouse compound* without hunting manage enums.

## Two layers (both stay on)

| Layer | What | When |
|-------|------|------|
| **Hot** | `MEMORY.md` + `USER.md` | Always injected; short doctrine |
| **Deep** | HermesCube `.cube` | Prefetch each turn; long archive + chat |

```
Agent turn
  ├─ system: SOUL + MEMORY.md + USER.md + Cube system_prompt_block
  │          (+ Living strip: triage focus / merge ready / relations)
  ├─ user msg + Cube prefetch (HAR + relational SPO assist)
  ├─ model reply
  ├─ Cube sync_turn  → WAL durable (+ optional vault/topic tag)
  └─ if memory tool wrote MEMORY.md → Cube on_memory_write mirror
Session end → triage → numeric conflict scan → crystalize → living pulse → growth merge
```

## Compounding loop (use this)

1. **Triage** — session-end (and Living strip) shows `next_focus` + queue counts.
   Call `hermescube_manage action=triage` when you need the plan on demand.
2. **Crystalize** — offline, no LLM; consolidates near-duplicates into belief crystals.
   Session-end skips it when triage says nothing to consolidate; candidates are capped.
3. **Merge** — when ≥2 axes fired (durable / procedure / association / yield / wisdom),
   session-end emits one `[GROWTH-MERGE]` crystal. Or `action=merge`.
4. **Relations** — SPO store for who/owns/related. Prefetch injects lines for relational
   queries; Living strip shows open edges. `action=relations`.
5. **Feedback** — helpful/unhelpful yield + engram coactivation close the loop so the
   next prefetch ranks what paid off.

Living strip + system-prompt hints surface steps 1–4 so the agent does not need the
full manage enum.

## Multi-project homes

When both `agent_identity` and `agent_workspace` are set, compounding **sidecars**
(engram, yield, relations, triage, journey, living) nest under
`memories/profiles/<identity>/<workspace>/`. The `.cube` warehouse stays shared;
writes may carry `data.vault` / `data.topic`. Recall soft-boosts the active vault and
**never hard-drops unlabeled legacy memories**.

## No day-to-day interruption

- **One provider** at a time (`memory.provider: hermescube`) — Hermes rule.
- Built-in **memory tool still works**; Cube **mirrors** those writes into the archive.
- Prefetch is sub-ms warm; does not block chat.
- Turns are **sync-persisted** to cubelog before the turn returns.

## Agent mental model

> I have a pocket notebook (MEMORY.md) and a warehouse (Cube).
> Notebook = what I always keep open. Warehouse = everything I might need later.
> Writing in the notebook also files a copy in the warehouse.
> Triage tells me what to consolidate; merge compounds growth; relations answer who/owns.

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

See also: [LIVING_ARCHIVE.md](LIVING_ARCHIVE.md), [GROWTH.md](GROWTH.md), [ENGRAM_NET.md](ENGRAM_NET.md).
