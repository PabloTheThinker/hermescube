# HiveCube — the collective nexus

> Every agent keeps its own soul-record (its private cube). The Hive is where
> agents pilgrimage — typically at the end of the night — to offer what they
> learned and return with what the collective knows.

## Concept

```
        agent A cube          agent B cube          agent C cube
       (private soul)        (private soul)        (private soul)
             │                     │                     │
             │  1. OFFER (distilled experience, soul card)
             ▼                     ▼                     ▼
       ┌─────────────────────────────────────────────────────┐
       │                      HIVE                            │
       │  hive.cube        — collective distilled memory      │
       │  agents/*.json    — soul cards (who each agent is)   │
       │  offerings/       — quarantined uploads              │
       │  ledger.jsonl     — audit trail                      │
       └─────────────────────────────────────────────────────┘
             │  2. ASSIMILATE (scan → dedup → branch-tag)
             │  3. DRAW (focus-relevant wisdom, quarantined)
             ▼
        each agent returns with collective knowledge
```

The hive is a **directory** — local disk, NFS, or a synced folder. There is no
network protocol in HermesCube itself; transport is the operator's choice.
This preserves the zero-network, local-first principle.

## The pilgrimage cycle

1. **OFFER** — the agent distills durable experience: wisdom crystals,
   approved procedures, session digest landmarks, durable beliefs and
   resolves. Raw conversation turns and `private: true` entries are never
   offered. Each row carries a content hash and the source entry id.
2. **INTERVIEW** (optional, `--interview`) — the visiting agent interviews
   peer souls ([docs/INTERVIEW.md](INTERVIEW.md)): claim-guarded,
   evidence-grounded dialogue whose distilled facts are written as
   offerings — deliberately *before* assimilation, so they join the
   collective in this same visit.
3. **ASSIMILATE** — the hive merges pending offerings into `hive.cube`:
   threat-scanned (prompt-injection patterns blocked), deduplicated by
   content hash, branch-tagged `hive:<agent>`, provenance preserved.
4. **DRAW** — the agent pulls focus-relevant collective entries into its own
   cube under branch `hive:collective` with verification `hive_shared`.
   Own offerings are never drawn back — including facts others distilled
   *about* this agent in interviews (echo guard). Drawn entries appear in
   evidence packets under **COLLECTIVE (other agents)** — below
   user-authored and tool-verified facts, never above them. Crystal /
   procedure flags survive the draw.
5. **GROWTH** — living version advances ([docs/GROWTH.md](GROWTH.md)).
6. **CURATOR** — drawn lessons refine overlapping installed skills; era
   milestones forge procedure drafts and garden dormant memories.
7. **SOUL CARD** — published *last* so peers see post-growth living
   version, strength, era, and evolving skills on `agents/<agent>.json`.

`hermescube hive status` is the single pane for the whole nexus: souls,
collective size, pending offerings, charters and the command owner,
pending handoffs, and interviews held.

## Usage

```bash
# One-time: create the hive
hermescube hive init --hive /shared/hermes-hive

# Nightly per agent (cron-able)
HERMESCUBE_HIVE=/shared/hermes-hive \
  hermescube hive pilgrimage --hermes-home ~/.hermes --agent coder

# Inspect
hermescube hive status --hive /shared/hermes-hive
hermescube hive souls  --hive /shared/hermes-hive
```

From inside a Hermes session (agent tool):

```
hermescube_manage action=hive hive_action=status
hermescube_manage action=hive hive_action=pilgrimage focus="deployment"
```

Config (`plugins.hermescube` in config.yaml):

```yaml
plugins:
  hermescube:
    hive_path: /shared/hermes-hive     # empty = hive disabled
    hive_on_session_end: false          # true = pilgrimage after each session
```

Recommended: leave `hive_on_session_end: false` and schedule a nightly Hermes
cron job running `hermescube hive pilgrimage` — the "end of the night" upload.

## Trust model

| Tier | Verification | Rank in evidence |
|------|--------------|------------------|
| User-authored doctrine | `user_authored` | highest |
| Tool-verified outcomes | `tool_verified` | high |
| Own observed experience | `observed` | normal |
| Collective (hive) | `hive_shared` | quarantined, labeled |

Hard rules:

- Assimilation threat-scans every row; blockable injection patterns never
  enter the collective.
- Drawn entries are labeled `[HIVE:<agent>]` and bucketed separately in
  prefetch — the model always knows which memories came from other souls.
- Shared procedures arrive as knowledge, not installed skills. The
  consent gate (`promote`, optional `install_to_skills`) still applies.
- A hive never mutates an agent's own claims; contradictions surface as
  evidence, and the local agent decides.

## What this becomes

- **Fleet learning** — one agent solves a deployment failure at 2pm; every
  agent knows the fix by morning.
- **Specialist souls** — coder, ops, and research profiles publish soul
  cards; agents can see which peer to delegate toward.
- **Collective pattern recognition** — the hive cube is itself a cube:
  HAR retrieval, wisdom crystallization, and colony trails run on the
  collective, distilling cross-agent patterns no single agent could see.
- **Continuity of souls** — if an agent's host dies, its offered experience
  and soul card persist in the hive; a new instance can draw its lineage.
