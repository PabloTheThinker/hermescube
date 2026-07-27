# Ideas from oh-my-hermes (OMH) → HermesCube

Source: [rlaope/oh-my-hermes](https://github.com/rlaope/oh-my-hermes) (MIT), dissected 2026-07-27.

OMH is a **Hermes workflow / operating layer** (92 skills, routing, evidence
cards). HermesCube is a **deep memory store**. Copy the *memory governance
discipline*, not the skill catalog.

## What OMH does well (memory-relevant)

| OMH idea | Where it lives | Cuboasis fit |
|----------|----------------|--------------|
| **capture → review → approve** | `skills/omh-memory-new`, `src/workflows/memory.py` | **High** |
| Memory safety gate (creds / logs / temp progress) | `_project_memory_safety` in `memory.py` | **High** |
| Prepared / observed / verified claim boundaries | `skills/omh-routing/references/evidence-boundaries.md` | **High** |
| Curate without silent mutate (`memory-sync`) | `skills/omh-memory-sync`, `hermes_memory.py` | **High** |
| Rejected-decision recall (negative memory) | `skills/omh-decision-recall` | **High** |
| Typed records + TTL / staleness | `docs/MEMORY.md` (`fact/decision/lesson/procedure/episode`) | **High** |
| Policy modes: `review-first` / `auto-safe` / `off` | `docs/MEMORY.md` | **Medium–High** |
| Route explanation cards (“why this, not evidence yet”) | `src/routing/chat.py` | **Medium** |
| Rules distill → principle candidates | `skills/omh-rules-distill` | **Medium** |
| Doctor / readiness cards | `skills/omh-doctor`, `*-readiness` | **Medium** |
| Memory blocks with char budgets | `memory_blocks.py` | **Medium** |
| Dreaming / eviction *proposals* | `memory_dreaming.py`, `memory_eviction.py` | **Medium** |
| Full skill router / connector ops | most of `skills/` | **Low** (wrong layer) |

## Already covered in HermesCube

- Deep store: `.cube`, HAR, EngramNet, Cubewave, Yield Gradient
- Cuboasis space / connections / progress
- Claims + SPO relations, supersession
- Threat scan + `quote_evidence` directive fencing
- Witness / harness / predictions / gardener
- Hive quarantine + trust (collective, not project-memory review)

## Recreate next (Cube-native names)

### 1. Candidate chamber (High)

OMH: `.omh/memory/candidates|reviews|records`.

Cuboasis:

- Chamber or sidecar lane: `candidates` → `review_queue` → durable L1
- Manage: `action=cuboasis mode=capture|review|approve|reject`
- Never treat a candidate as approved recall until promoted

Schema sketch: `cube_memory_candidate/v1` with `safety`, `evidence_state`,
`review.status`, optional TTL.

### 2. Memory-specific safety gate (High)

Before durable append (beyond generic threat scan), block or force-review:

- credential-like text
- raw logs / full transcripts
- short-lived PR/commit chatter
- temporary task progress
- overlong dumps

Modes: `review-first` (default for auto-extract) · `auto-safe` · `off`.

### 3. Evidence-state on entries / claims (High)

Extend metadata (and prefetch cards):

| State | Meaning |
|-------|---------|
| `prepared_not_observed` | planned / inferred / candidate |
| `observed` | seen in turn / tool / file |
| `verified` | test / user confirm / trusted source |
| `superseded` / `refuted` | closed truth |

Align with existing `verification` on claims; make the boundary *visible* in
prompt strips (“not evidence of X”).

### 4. Curation review artifacts (High)

OMH `memory-sync`: duplicate / stale / conflict / risky → review card, no
silent delete.

Cuboasis: `action=curate` / triage already forges; add a **sync report**
artifact (duplicate clusters, stale TTL, low-trust high-impact, SPO conflicts)
written to progress ledger + optional review queue.

### 5. Rejected-decision recall (High)

Store rejects as searchable negative memory, labeled `rejected_decision` /
`not_approved`. Retrieval must never present them as current instruction.

### 6. Why-surfaced cards (Medium)

For prefetch / search hits: compact explanation —

- why ranked (lex / HAR / Cubewave / chamber)
- evidence_state
- claim_boundary one-liner

### 7. Doctor card for the oasis (Medium)

Fold into Cuboasis status / CLI doctor:

- cube R/W + lock
- sidecar health (engram, Cubewave, relations, progress)
- candidate backlog
- usefulness rate
- unresolved harness predictions

## Explicitly do **not** copy

- The 92-skill operating pack and meta-router as Cube internals
- Connector / executor / coding-handoff workflows
- Mutating Hermes `MEMORY.md` from a second project-memory product
  (Cube already mirrors via `on_memory_write`; keep dual-store states separate
  the way OMH does — OMH write ≠ Hermes write)

## Boundary mantra (steal the wording, keep Cube ownership)

> Prepared routing / candidates / handoffs are **not** execution evidence.
> Approval in one store is **not** proof the other store changed.

For Cuboasis: a promoted crystal is durable cube truth; it is still not proof
that MEMORY.md or Hive assimilated it unless that write was *observed*.

## Suggested ship order

1. ~~Safety gate + `evidence_state` on durable writes~~ **shipped 0.41**  
2. ~~Candidate chamber + approve/reject manage actions~~ **shipped 0.41**  
3. ~~Rejected-decision recall + curation sync report~~ **shipped 0.41**  
4. Cuboasis doctor card **shipped 0.41**; why-surfaced strip still open  
5. Rules-distill from repeated witnesses → procedure candidates  

### Hermes Agent research notes (2026-07-27)

Latest Hermes `main` (~v2026.7.20+): MemoryProvider ABC still one external
provider; Cube already implements core + optional hooks including
`on_session_switch`. Plugin ecosystem peers: holographic, honcho, mem0,
hindsight, retaindb, supermemory, byterover, openviking. Cube differentiator
remains local `.cube` + Cuboasis governance rather than SaaS memory APIs.
Watch: memory tool card UX, mode-aware provider deps, compression/history
durability fixes on Hermes main — none require Cube API breaks.

## Inspiration sources (paths in OMH clone)

- `docs/MEMORY.md`, `docs/MEMORY_CONTEXT.md`
- `skills/omh-memory-new/SKILL.md`, `omh-memory-sync`, `omh-decision-recall`
- `skills/omh-routing/references/evidence-boundaries.md`
- `src/workflows/memory.py`
- `src/plugin_bundle/omh/hermes_memory.py`, `memory_eviction.py`, `memory_blocks.py`
