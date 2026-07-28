# CubeDream — multi-layer dreaming, alone and together

**Status:** L1 + L2 Chorus MVP **shipped in 0.46.0** (Conversation / auto-circle still open)  
**Date:** 2026-07-27  
**North star:** Agents keep a private soul dream **and** can join a shared **dream circle** at the hive — dreaming *together* by reinforcing the same themes, interviewing craft, then committing only what survives multi-agent evidence.

---

## 0. The idea in one picture

```
                 ┌──────────────────────────────────────┐
                 │         L4  Hot markdown (Hermes)    │
                 │     proposals only — never Cube auto │
                 └──────────────────▲───────────────────┘
                                    │ optional diffs
     ┌──────────────────────────────┼──────────────────────────────┐
     │                              │                              │
┌────┴─────┐                 ┌──────┴──────┐                ┌─────┴─────┐
│ L1 Soul  │  signals + RSVP │ L2 Circle   │  close/commit  │ L3 Hive   │
│  dream   │ ───────────────►│  (together) │ ──────────────►│ collective│
│ private  │ ◄─── draw ──────│ shared log  │                │ hive.cube │
└──────────┘                 └─────────────┘                └───────────┘
   parallel                     join / reinforce                 locked
   per agent                    multi-writer append              assimilate
```

**Dreaming alone** = L1 (always available).  
**Dreaming together** = L2 Circle (the new product).  
**Fleet memory** = L3 Hive (already mostly built as pilgrimage).  
**Prompt memory** = L4 Hermes MEMORY.md (Hermes-owned).

Pilgrimage today is *async merge* (offer → assimilate → draw). A circle is *co-presence*: several agents contribute into one staged dream before the hive hardens anything.

---

## 1. What Hermes / peers taught us

| Source | Steal | Leave behind |
|--------|-------|--------------|
| **Hermes** `background_review` | Real executor for hot markdown; turn cadence | Silent dual-writer of MEMORY.md from Cube |
| **OMH** dreaming | Due-reasons + handoff briefs; claim boundaries; no fake auto-launch | Project-memory product competing with Cube |
| **OpenClaw** Light/Deep/REM | Stage before promote; Dream Diary; multi-*workspace* sweep | One MEMORY.md host assumption |
| **AgentDrive Loom** | Multi-substrate signals → one candidate pool; **reinforcement when many sources agree**; adversarial stress; snapshot reads | Genome lanes / live swarm mutation |
| **Cube hive + interview** | Distilled offer only; peer dialogue; consent-gated mint | Treating interview as the whole dream |

**Together ≠ merge later.**  
OpenClaw sweeps many workspaces but still dreams *per file*. Loom’s insight is better: **agreement across agents is itself a ranking signal.** That is the heart of CubeDream Circle.

---

## 2. The four layers (multi-layer cube dream)

### L1 — Soul dream (private warehouse)

- **Where:** `$HERMES_HOME/memories/dreams/`
- **Inputs:** own `.cube` L1, Engram, Cubewave, session digests, Cuboasis candidates
- **Phases:** Light (stage) → Deep (score) → Apply (gated via Cuboasis / auto-safe)
- **Also runs:** existing `sleep_replay` + `crystalize` as *structure* commits (not themes)
- **Concurrency:** fully parallel across agents
- **Never:** peer MEMORY.md, raw turns, re-offer of `hive_shared` knowledge

### L2 — Circle dream (dreaming *together*)

- **Where:** `$HIVE/dreams/circles/<circle_id>/`
- **What it is:** a time-bounded, append-only **shared dream room** agents join
- **Writers:** many agents (signal log); one closer holds the commit lock
- **Product of togetherness:**
  1. **Shared Light** — each agent posts distilled dream *signals* (not whole cubes)
  2. **Reinforcement** — same `canonical_key` from ≥2 agents boosts score (“we dreamed this”)
  3. **Dialogue** — optional peer interviews *inside* the circle (reuse `interview.py` + HQ claim)
  4. **Shared Deep** — one scoring pass over the circle corpus
  5. **Close** — promote survivors into L3 hive candidates / hive.cube under lock; each soul may draw

Circle layout:

```
hive/dreams/circles/<circle_id>/
  meta.json           # topic, opened_by, members[], status open|scoring|closed
  signals.jsonl       # multi-writer append (agent_id, canonical_key, summary, evidence_refs)
  dialogues/          # interview session ids held during circle
  candidates.jsonl    # scored circle candidates (after Deep)
  DREAMS.md           # collective diary for this circle
  lock                # exclusive for score/close only (signals stay lock-free append)
```

### L3 — Hive collective (fleet memory)

- **Where:** `hive.cube` + offerings + soul cards (existing)
- **Role after a circle:** assimilate circle promotions + leftover offerings; publish diary line
- **Lock:** assimilate / crystalize-collective always under `hive/.locks/dream.lock`
- **Trust:** drawn knowledge stays `verification=hive_shared` (never laundered as local truth)

### L4 — Hot markdown (Hermes plane)

- Cube may emit **MEMORY.md diff proposals** into the agent’s dream diary
- Only Hermes `background_review` / human / `write_approval` applies them
- Dual-store mantra (from OMH): Cube write ≠ Hermes write until observed

---

## 3. What “dreaming together” means operationally

Three modes of togetherness, stacked:

| Mode | Metaphor | Mechanism |
|------|----------|-----------|
| **A. Chorus** | Many agents notice the same thing | Signal reinforcement by `canonical_key` + distinct `agent_id` |
| **B. Conversation** | Agents interview each other in the dream | Circle-scoped `peer_dialogue` / interview sessions |
| **C. Communion** | One closed dream becomes hive truth | Locked Deep → hive promote → souls draw |

Mode A can happen without chat (cheap, cron-friendly).  
Mode B is richer (craft transfer).  
Mode C is the only step that mutates the collective cube.

**Canonical key** (deterministic, Cube-native):

```
canonical_key = hash( normalize(entities ∪ top_tokens(summary)) )
```

If agent `ilo` and agent `coder` both post signals that collide on the same key, Deep sees:

```
supporting_agents: ["ilo","coder"]
occurrence_count: 2
together_bonus: +0.15  # tunable
```

That is the minimal mathematical meaning of “we dreamed this together.”

---

## 4. Circle lifecycle

```
open ──► join* ──► signal* ──► [dialogue*] ──► score ──► close ──► draw*
              (many)   (many)      (pairs)      (one)    (one)   (many)
```

1. **open** — any agent (or cron “night watch”) opens a circle with optional `topic` / `focus`
2. **join** — RSVP; listed in `meta.members` (soft; signals from non-members still accepted if policy allows guests)
3. **signal** — Light extract from own L1 → append to `signals.jsonl` (private filter: durable/crystal/resolve only; same rules as hive `_offerable`)
4. **dialogue** (optional) — interview peers who joined; briefs become *signals* with `kind=dialogue_fact`
5. **score** — lock → cluster by canonical_key → rank → write `candidates.jsonl` → diary
6. **close** — promote top candidates into hive (or Cuboasis-style hive candidate lane) → status=closed
7. **draw** — members pull circle/hive outcomes into soul cubes as `hive_shared`

Wake / abort (from Loom): operator activity, TTL expiry, lock steal after TTL, safety quarantine → checkpoint + `status=aborted` (signals kept for next circle).

---

## 5. Solo vs together — when to use which

| Situation | Layer |
|-----------|-------|
| End of a normal Hermes session | L1 soul dream (proposals + sleep_replay) |
| Nightly fleet quiet hour | Open L2 circle → members signal → close → L3 |
| Two agents pairing on one craft | L2 circle with `topic` + dialogue |
| Prompt file almost full | L1 reminder + L4 proposal only (OMH-style) |
| Subagent / background_review fork | No dream counters; no circle join |

---

## 6. Scoring (Deep) — together-aware

Base (OpenClaw-ish, Cube-native weights):

| Signal | Weight | Cube source |
|--------|--------|-------------|
| Frequency | 0.22 | signal count |
| **Together** | **0.20** | distinct agents on same key |
| Trust / yield | 0.18 | entry trust × yield gradient |
| Recency | 0.12 | last_seen |
| Conflict penalty | −0.15 | SPO / conflict markers |
| Hive laundering | −1.0 block | already `hive_shared` |

Plus optional **adversarial skim** (Loom-lite, no genomes): for top candidates, search local+hive for contradicting entries → `risk_flags` / demote. Report-only until thresholds mature.

Prefer: **no-op > merge/supersede proposal > promote > never delete**.

---

## 7. Safety & claim boundaries

- Append-only everywhere (cube + signals + diary). Eviction = supersede *proposal*.
- Circle signals are **prepared context**, not durable truth.
- Interview answers stay threat-scanned; mint still consent-gated.
- Private / sync_turn / hive_shared never enter circle signals (reuse `_offerable` gates).
- Closing a circle is not proof every member’s MEMORY.md changed.
- Diary line template:

> Circle `C` closed with agents […]. Promoted N hive candidates. This diary is not evidence of MEMORY.md writes.

---

## 8. How this sits on code we already have

| Need | Existing | Gap |
|------|----------|-----|
| Distill shareable rows | `hive.build_offering` / `_offerable` | Map rows → circle *signals* |
| Talk together | `interview.peer_dialogue` + HQ claims | Scope sessions under `circles/<id>/dialogues` |
| Merge collective | `assimilate_offerings` | Hive dream lock; circle→hive promote path |
| Review gate | `memory_gate` | Circle candidates may reuse candidate schema |
| Solo structure dream | `sleep_replay`, `crystalize`, `consolidate` | Wire as L1 Apply substeps |
| Chambers | Cuboasis space | Optional: tag circle promotions into a `dream` chamber |
| Progress | `record_progress` | `dream_circle_open/close` events |

**Feasible first code slice (small):**

1. `hermescube/dream.py` — state + due reasons (L1 scheduler)  
2. `hermescube/dream_circle.py` — open/join/signal/score/close (L2)  
3. CLI/manage: `dream status|solo|circle …`  
4. Hive lock helper used by circle close + assimilate  
5. Tests: two agents signal same key → together_bonus; lock excludes double-close  

LLM optional: L1/L2 Light can be **deterministic** (token/entity bundles) first; diary narrative later.

---

## 9. API sketch

```
hermescube dream status
hermescube dream solo [--apply]
hermescube dream circle open [--topic …]
hermescube dream circle join --id …
hermescube dream circle signal --id …
hermescube dream circle dialogue --id --subject …
hermescube dream circle score --id …
hermescube dream circle close --id …
hermescube dream circle draw --id …

hermescube_manage action=dream mode=solo|circle:open|circle:signal|…
```

Config:

```yaml
dream:
  mode: reminder            # off | reminder | auto-soul | auto-circle
  turn_interval: 8
  circle_ttl_s: 3600
  min_agents_together: 2    # for together_bonus
  max_promotes_per_circle: 5
  hive_lock_ttl_s: 300
```

`auto-circle` (cron): if hive quiet and ≥2 souls have pending undreamed signals → open night circle, auto-signal from each soul card/offering path, score, close. Agents offline still “dream together” via their last distilled offerings — Chorus mode without live chat.

---

## 10. Conceptual guarantees

1. **Soul sovereignty** — private dream never blocked by a busy hive.  
2. **Together is evidence** — multi-agent agreement raises rank; it does not skip safety.  
3. **One closer** — scoring/closing serialized; signaling concurrent.  
4. **Hermes owns the prompt file** — Cube dreams the warehouse + hive.  
5. **Reversible** — every circle has `circle_id`; promotions tagged `origin=dream_circle`.  

---

## 11. Ship order (revised for “together”)

1. ~~L1 scheduler + diary stub (reminder strip)~~ **shipped 0.46**  
2. ~~**L2 circle MVP** — open / signal / score / close (Chorus only)~~ **shipped 0.46**  
3. ~~Hive lock + circle→hive promote + draw~~ **shipped 0.46**  
4. Dialogue-in-circle (wire interview)  
5. ~~L1 Apply via sleep_replay packaging~~ **shipped 0.46** (`solo:apply`)  
6. L4 MEMORY.md proposals (optional)  
7. Adversarial skim + auto-circle cron  

---

## 12. Source map

| Source | Path |
|--------|------|
| Hermes background review | `~/hermes-agent/agent/background_review.py` |
| OMH dreaming | `rlaope/oh-my-hermes` → `memory_dreaming.py` |
| OpenClaw dreaming | `GitHub Repo Archives/openclaw/docs/concepts/dreaming.md` |
| Loom dreaming | `agentdrive/.../LOOM_DREAMING_SPEC.md` |
| Hive / interview | `hermescube/hive.py`, `interview.py`, `docs/INTERVIEW.md` |
| Solo sleep | `sleep_replay.py`, `consolidate.py`, `session_end.py` |
