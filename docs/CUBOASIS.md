# Cuboasis — pocket-dimension memory infrastructure

HermesCube is one warehouse file. **Cuboasis** is the custom internal framework
that turns that warehouse into a memory oasis for Hermes agents — a pocket
dimension with rooms, brainwave associations, and a compounding progress loop.

This is **not** a generic “nexus”. The name and shape are Cube-native.

```
┌─────────────────────────────────────────────────────────┐
│  SPACE       vaults + chambers (one store, many rooms)  │
│  WAVE        Cubewave neural field (brainwave mimic)    │
│  CONNECTIONS SPO ∪ colony ∪ engram ∪ Cubewave ∪ HAR     │
│  PROGRESS    append-only ledger + usefulness rollup     │
│  CUBOASIS    single status pane for agents / doctor     │
└─────────────────────────────────────────────────────────┘
```

## Manage actions

| Action | Args | Job |
|--------|------|-----|
| `space` | `mode=chamber:doctrine` | Map vaults/chambers; set session chamber affinity for prefetch |
| `connect` | `content=<entity>` | Unified neighbors across all connection layers |
| `progress` | `mode=record` | Append / roll up the progress ledger |
| `cuboasis` | — | Single pane (space + wave + connections + progress) |
| `nexus` | — | Deprecated alias of `cuboasis` |

Triage `mode=apply` forges consolidate queues and annotates conflicts — queues
that *do* work, not only advise.

## Cubewave

`hermescube/cubewave.py` is a small neural-*like* association field:

1. Frozen random token projection into an H-dim wave (ELM-style hidden layer)
2. Online LMS readout trained by helpful / unhelpful feedback
3. Soft Hebbian co-activation among co-retrieved entry ids
4. Multiplicative HAR re-rank (sibling to EngramNet — not a replacement)

No torch. Persists to `cubewave.json` under the cube sidecar dir.

## Sidecars

- `progress.jsonl` — append-only progress events
- `cuboasis_state.json` — last Cuboasis snapshot
- `cubewave.json` — Cubewave readout + edges
- `nexus_state.json` — legacy name (still migrated / readable)

## Chamber-scoped prefetch

`manage action=space mode=chamber:doctrine` sets a soft session chamber.
Prefetch / HAR then prefer that chamber’s memories (soft boost, not a hard cut).
Clear with `mode=chamber_clear`.

## Claim → SPO

Durable MEMORY.md mirrors create Claims with optional SPO fields. Cuboasis
bridges them into `RelationStore` so who/owns/related facts compound into the
connection graph automatically.
