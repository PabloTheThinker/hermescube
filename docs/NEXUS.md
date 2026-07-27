# Nexus — functional memory infrastructure

HermesCube is one warehouse file. **Nexus** is the infrastructure that makes it
a navigable system: space, connections, and measurable progress.

```
┌──────────────────────────────────────────────────────────┐
│  SPACE          vaults + chambers (rooms without forks)  │
│  CONNECTIONS    SPO ∪ colony ∪ engram ∪ HAR related      │
│  PROGRESS       progress.jsonl + usefulness rollup       │
│  NEXUS pane     single status for agents / doctor        │
└──────────────────────────────────────────────────────────┘
```

## Agent tools (`hermescube_manage`)

| Action | Mode / content | What it does |
|--------|----------------|--------------|
| `space` | (default) | Chamber + vault map |
| `space` | `chamber:<name>` | Entry ids in a chamber |
| `space` | `mode=set` + `query=<vault>` | Soft-set active vault for session |
| `connect` | `content=<entity>` | Unified neighbors |
| `progress` | (default) | Ledger + growth + loop health |
| `progress` | `mode=record` | Append operator note |
| `nexus` | — | Single pane (space + connections + progress) |
| `triage` | `mode=apply` | Execute plan: forge consolidate + annotate conflicts |

## Sidecars

Under `$HERMES_HOME/memories/` (or nested profile sidecar):

- `progress.jsonl` — append-only progress events
- `nexus_state.json` — last nexus snapshot

## Design rules

1. **One warehouse** — vaults are soft tags; chambers are classification; never a second cube per room.
2. **Extend, don't replace** — relations / colony / engram stay; connect *unifies* them.
3. **Prove usefulness** — feedback and session_end write the progress ledger so growth is not only counter volume.

See also: [GROWTH.md](GROWTH.md), [HERMESPACE.md](HERMESPACE.md), [PURPOSE.md](../PURPOSE.md).
