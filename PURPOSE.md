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

**Fleet HQ (0.24+):** the hive root doubles as the command layer for any
number of agents — charters record who owns which lane, routing sends work
to its owner (command fallback for the rest), handoffs carry distilled
evidence packets, task claims prevent turf wars, `hq verify` catches ghost
routes and lane conflicts, and frozen baselines prove what changed.
Subagents get read-only memory tools: work flows upward, privilege does
not flow down. See [docs/HQ.md](docs/HQ.md).

**Peer interviews (0.25+):** agents that pilgrimage back can interview
each other with the interview-me protocol — inspect soul cards before
asking, one high-value question at a time, grounded answers, a structured
brief, and consent-gated skill drafts. See [docs/INTERVIEW.md](docs/INTERVIEW.md).

**One system (0.26+):** the layers are one machine, not four features.
The night cycle at the nexus runs OFFER → SOUL CARD → INTERVIEW →
ASSIMILATE → DRAW, so interviewed knowledge joins the collective in the
same visit. Interviews take HQ task claims and land in the HQ handoff
ledger; minted peer lessons commit falsifiable harness predictions;
handoffs route, carry distilled evidence packets, and settle
(`hq_action=handoff` / `complete`); echo guards and provenance filters
keep every fact attributed to the soul that lived it. `hive status` is
the single pane: souls, collective, charters, handoffs, interviews.

**Living growth (0.27+):** every cube is born at living version `0.0.0`
and strengthens with experience — the same visible growth story Hermes
Agent has for skills and MEMORY.md, but for the archive itself. Sessions,
draws, interviews, promotions, skill installs, and confirmed predictions
advance the version; helpful feedback *refines* installed skills in place
(patch bump + lessons ledger); era thresholds (25/50/75/90 strength)
earn major bumps. The diary is `memories/CUBE.md`. See [docs/GROWTH.md](docs/GROWTH.md).

**Curator + maturity (0.28+):** growth changes behavior. Elder cubes
prefer distilled knowledge in retrieval; soul cards advertise living
version to the hive; a curator matches drawn lessons to installed skills
and refines them (Hermes closed learning loop), forging and gardening on
era milestones — still consent-gated.

**Digital soul age (0.29+):** agents don't age in human years or on a
0–100 scorecard. Age is **cycles** (lived growth epochs) + **lived**
wall-clock since birth. Capability stays a separate coherence score;
era is the life stage that score earns. Soul cards and the system prompt
speak this language clearly.

**Cube of Eden (0.30+):** the origin era. Every fresh cube begins in the
garden before lived memory — `era: eden`, display **Cube of Eden** —
then leaves through Awakening → Formed → Seasoned → Elder as capability
rises. Legacy `genesis` migrates automatically.

**Nexus infrastructure (0.39+):** the cube gains a true internal
infrastructure layer — **space** (vaults + chambers), **connections**
(unified SPO ∪ colony ∪ engram ∪ HAR neighbors), and **progress**
(append-only ledger + usefulness rollup). Agents navigate with
`manage action=space|connect|progress|nexus`; triage can `mode=apply`
to forge and annotate instead of only planning. See [docs/NEXUS.md](docs/NEXUS.md).

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
- Not AgentDrive / Mission Control — borrow algorithms (merge, triage, SPO), not the conductor OS  

## Yield Gradient (0.8+)

Closed loop: feedback teaches which memories *pay off for similar queries* (query-local, not global trust / not colony trails). Hot path stays multiplicative boost only.

## Success metrics

1. **No lost day-to-day turns** — WAL sync before return  
2. **Hot path ms-class** — warm prefetch without full L1 every inject  
3. **IR useful** — hybrid lexical+HRR; score-first; labeled recall tracked  
4. **User data isolation** — only `$HERMES_HOME/memories/memory.cube`  
5. **Company agents** — same plugin socket; cube = deep extension per profile  
6. **Compounding sessions** — ≥2 axes → growth-merge crystal; triage skips empty crystalize  

## Research spine (Fudoshin)

Canon: `brain/research/hermes-stack-benchmarks/`  
Study tree: clean Hermes `v2026.7.20` at `~/projects/hermes-agent-study`  
Key RE: MemoryProvider ABC, MemoryManager one-external, `<memory-context>` fence, builtin+external coexistence.

## Version posture

Ship purpose-aligned increments. Public GH scrubbed. `hermescube update` never overwrites cube data.
