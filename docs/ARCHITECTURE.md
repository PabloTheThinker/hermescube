# Architecture Blueprint — HermesCube

**Status:** living blueprint (v0.50 — library / Hermes-base core)  
**Audience:** maintainers, agents, and Hermespace integrators  
**Companions:** [PURPOSE.md](../PURPOSE.md) · [ABOUT.md](../ABOUT.md) · [CODEMAP.md](CODEMAP.md) · [SPEC.md](SPEC.md) · [ANATOMY.md](ANATOMY.md) · [HERMESPACE.md](HERMESPACE.md) · [BLACKBOX.md](BLACKBOX.md)

This document is the **single architecture map** for HermesCube: where it sits as the **library under Hermes**, how every product layer fits, how data flows on a turn, and how the binary warehouse works underneath.

---

## 0. One-line identity

HermesCube is the **library under Hermes** — local deep-memory **book** and **heart** for [Hermes Agent](https://github.com/NousResearch/hermes-agent), and the **generator core** that powers [Hermespace](https://github.com/PabloTheThinker/hermespace).

**Metaphor:** `memory.cube` is a **book**; crystals/growth/dreams bind **chapters (arcs)**; blackbox is **provenance in the heart**; MEMORY.md is the desk **card catalog**. Multi-agent readers share one library; Hive is optional inter-library loan.

It is **not** a second agent runtime, not a cloud memory SaaS, and not a replacement for Hermes `MEMORY.md`.

---

## 1. Design principles

1. **Append-only is the only safe durable write.** Entries are marked superseded, never silently deleted. Crash recovery stays simple.
2. **Semantic recall over keyword-only.** HRR + HAR + learned embeddings + graphs — no embedding API required.
3. **Compress into chapters over time.** Crystalize, merge, dream — not infinite CCTV tape in the context window.
4. **The system improves with use.** Evolve, trust feedback, Cubewave/Engram, growth eras, curator.
5. **One external MemoryProvider.** Builtin MEMORY.md always coexists; Cube is the deep core of a Hermes base.
6. **Soft-fail at every integration edge.** Hermespace and fleet hooks never crash the agent loop.
7. **Solo library first.** Hive / HQ / dream-circles are opt-in consortium features.
8. **User data never lives in git.** Runtime SoT is `$HERMES_HOME/memories/memory.cube`.
9. **Prove when it matters.** Blackbox flights stamp runs; “done” needs evidence.
10. **Learn frameworks; remake Cube-native.** Steal algorithms — do not clone foreign stores.

---

## 2. Ecosystem placement

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Hermes Agent (Nous)                                                      │
│  state.db · skills · gateway · memory tool · MemoryManager               │
│  MEMORY.md / USER.md     hot doctrine (always-on, char-capped)           │
│  MemoryProvider socket   ONE external plugin                             │
│       └── HermesCube     living warehouse + tools + heart                │
│                                                                          │
│  Hermespace (optional)   FOA desk · dual decode · pulse                  │
│       ↑ powered by       center.beat / space_bridge (arteries & veins)   │
└──────────────────────────────────────────────────────────────────────────┘
```

| Layer | Owner | Authority |
|-------|-------|-----------|
| `MEMORY.md` / `USER.md` | Hermes builtin | Hot doctrine |
| `state.db` | Hermes | Canonical sessions / tools |
| **`memory.cube`** | **HermesCube** | **Durable long-tail SoT** |
| Hermespace world / desk | Hermespace | Working projections (charged from Cube) |
| Hive `hive.cube` | Fleet opt-in | Collective distilled memory |

**Nous contract (coding methods we honor):** `initialize` → `sync_turn` → `prefetch` / `queue_prefetch` → tools → `on_memory_write` → `on_session_end` → `on_session_switch` → `shutdown`. Soft-fail. Profile-scoped `hermes_home`. Prefetch caps.

---

## 3. Product architecture (full stack)

Read top-down. Lower layers never depend on upper ones.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ L7  Hermespace center     anatomical beat · supply · return · autonomic │
├─────────────────────────────────────────────────────────────────────────┤
│ L6  CubeDream             L1 soul · L2 circle · L3 hive · L4 proposals  │
├─────────────────────────────────────────────────────────────────────────┤
│ L5  Fleet                 Hive pilgrimage · HQ · peer interviews        │
├─────────────────────────────────────────────────────────────────────────┤
│ L4  Living growth         Eden→Elder · CUBE.md · curator · self-evol.   │
├─────────────────────────────────────────────────────────────────────────┤
│ L3  Cuboasis              space · wave · connections · progress · gate  │
├─────────────────────────────────────────────────────────────────────────┤
│ L2  Provider socket       CubeMemoryProvider · manage peels · tools     │
├─────────────────────────────────────────────────────────────────────────┤
│ L1  Warehouse engine      .cube · HRR · HAR · embed · WAL · threats     │
├─────────────────────────────────────────────────────────────────────────┤
│ L0  Framework housing     paths · config · lexindex · void              │
└─────────────────────────────────────────────────────────────────────────┘
```

| Layer | Job | Primary modules | Detail doc |
|-------|-----|-----------------|------------|
| **L0** | Path/config OS inside Cube | `framework/` | [FRAMEWORK.md](FRAMEWORK.md) |
| **L1** | Binary archive + retrieval | `cube` `hrr` `har` `embed` `threats` `bio_rank` | SPEC · this §8 |
| **L2** | Hermes ABC adapter | `provider` `manage*` `tools_recall` `session_end` | this §7 |
| **L3** | Pocket infra + governance | `cuboasis` `cubewave` `memory_gate` | [CUBOASIS.md](CUBOASIS.md) |
| **L4** | Lifetime growth | `genealogy` `living` `curator` `self_evolution` | [GROWTH.md](GROWTH.md) |
| **L5** | Multi-agent | `hive` `hq` `interview` | [HIVE](HIVE.md) · [HQ](HQ.md) · [INTERVIEW](INTERVIEW.md) |
| **L6** | Night cycles | `dream` `dream_circle` | [CUBEDREAM.md](CUBEDREAM.md) |
| **L7** | Hermespace heart | `space_bridge` `center` | [HERMESPACE](HERMESPACE.md) · [ANATOMY](ANATOMY.md) |

---

## 4. Anatomical view (heart × nervous FOA)

Functional analogues for integration design — not biophysics. Full map: [ANATOMY.md](ANATOMY.md).

```
                 Hermespace = nervous FOA (PFC / desk)
              Cowan ≤4 · GWT broadcast · Sweller load · pulse
                         ▲ arteries              │ veins
                         │ (diastole supply)     │ (systole seal)
                 HermesCube = HEART (.cube SoT)
         hippocampus encode · immune gate · lymph (hive)
         vascular beds (Cuboasis) · dolphin-USWS dream/idle
```

| Organ | Cube/Space role | API |
|-------|-----------------|-----|
| Heart | Durable pump | `ensure_heart` · `heart_status` |
| Arteries | FOA strip out | `center.supply` · `build_space_inject` |
| Veins | Desk seal in | `center.return_flow` · `seal_learning` |
| Autonomic | Idle rhythm | `autonomic_tick` · Space pulse |
| Immune | Threat + candidates | `threats` · `memory_gate` |
| Lymph | Collective | `hive` pilgrimage |
| Vascular beds | Chambers | Cuboasis `space` |

**Turn beat (recommended for Space):** `center.beat(query, seals=…, load=desk_load)`.

---

## 5. Runtime data layout

### Install layout

| Path | Contents |
|------|----------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin code (git checkout preferred) |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` + plugin config |
| `$HERMES_HOME/memories/` | **User data only** |

### Memories directory (solo)

```
$HERMES_HOME/memories/
├── memory.cube              # durable SoT
├── memory.embedder          # optional learned projection
├── candidates.jsonl         # Cuboasis review queue
├── progress.jsonl           # Cuboasis progress ledger
├── cuboasis_state.json
├── cubewave.json
├── engram_net.json
├── colony_graph.json
├── COLONY.md
├── journey.jsonl / journey.md
├── CUBE.md                  # living diary
├── genealogy / living sidecars
└── dreams/                  # CubeDream L1
```

Fleet adds hive root (charters, `hive.cube`, dream circles) — see [HIVE.md](HIVE.md) / [CUBEDREAM.md](CUBEDREAM.md).  
Profile nesting (optional): `memories/profiles/<identity>/<workspace>/` via `framework/paths.py`.

---

## 6. Solo path vs fleet path

```
Solo (default)                         Fleet (opt-in)
─────────────────                      ────────────────────────────
prefetch / sync_turn                   + hive offer → assimilate → draw
search / manage / feedback             + HQ charter / route / handoff
Cuboasis space/connect/progress        + peer interview
dream solo                             + dream circle / auto-circle
center.beat ↔ Hermespace               (same heart; shared lymph)
```

New operators learn **solo** first. Fleet compounds on top when hive is configured.

---

## 7. Provider socket & lifecycles

`CubeMemoryProvider` implements Hermes `MemoryProvider`.

### Context awareness

| `agent_context` | Writes? | Purpose |
|-----------------|---------|---------|
| `primary` | Yes | Normal sessions |
| `subagent` | Read-focused | Privilege flows up |
| `cron` / `flush` | Restricted | Avoid polluting user memory |
| `skip_memory=True` | No | Explicit opt-out |

### Turn lifecycle

```
User message
  │
  ├─► prefetch(user_msg)           # HAR + graphs → <memory-context> fence
  │     frozen snapshot (no mid-turn drift)
  │
  ├─► [Hermespace] center.beat / inject strip under load (optional)
  │
  ├─► LLM call
  │
  └─► sync_turn(user, assistant)   # background _SyncQueue
        ├─ threat scan + sanitize
        ├─ memory_policy gate (review-first | auto-safe | off)
        ├─ cube.append (atomic)
        ├─ β nudge · entities · colony / engram / cubewave touch
        └─ evolve if interval
```

### Session lifecycle

```
initialize(session_id, hermes_home=…)
  open/create cube → load embedder → frozen snapshot → growth touch

[ turns … ]

on_memory_write(...)     # mirror builtin MEMORY.md writes
on_pre_compress(...)     # harvest safe user text; never store compressor prose
on_session_end(...)
  flush sync queue → auto-extract (policy) → living pulse → dream due? → evolve
on_session_switch(...)
  refresh parent/user ids; FIFO after end flush

shutdown()
  save embedder · flush · close
```

### Tools (agent-facing)

| Tool | Job |
|------|-----|
| `hermescube_search` | Semantic / hybrid recall |
| `hermescube_manage` | Hub → warehouse / cuboasis / growth / fleet / dream peels |
| `hermescube_feedback` | Asymmetric trust (+helpful / −unhelpful) |
| `hermescube_probe` | Entity / associative probe |

Manage peels: `manage_warehouse` · `manage_cuboasis` · `manage_growth` · `manage_fleet` · `manage_dream` — keep `provider.py` thin ([CODEMAP.md](CODEMAP.md)).

### Frozen snapshot + sync queue

- Prefetch reads a **frozen** β/L2 snapshot captured at init / after evolve.  
- Writes serialize on a single-thread `_SyncQueue` so the agent turn returns fast.  
- Circuit breaker: repeated evolve failures open a cooldown (no hammer loops).

---

## 8. Warehouse engine (L1 binary)

### Design philosophy (engine)

1. Append-only durable log  
2. Semantic HRR vectors without network  
3. Evolve improves centroids + embeddings over time  

### `.cube` layout

```
┌──────────────────────────────────────────┐
│ HEADER (40 bytes)                        │
├──────────────────────────────────────────┤
│ L1 — Entry Log (append-only)             │
├──────────────────────────────────────────┤
│ L2 — Topic Index (rewritten on evolve)   │
├──────────────────────────────────────────┤
│ L3 — β Vector (attention state)          │
└──────────────────────────────────────────┘
```

#### Header (40 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | magic `CUBE` |
| 4 | 4 | version (uint32 LE) |
| 8 | 4 | dim |
| 12 | 8 | entry_count |
| 20 | 4 | l2_bucket_count |
| 24 | 8 | l1_data_size |
| 32 | 8 | l3_offset |

#### L1 entry record

```
[id 12B][timestamp 16B][type 1B][outcome 1B]
[desc_len 4B][data_len 4B][causal_count 4B]
[description UTF-8][data JSON][causal_parents…][vector dim×f64]
```

#### L2 topic index

Default 64 buckets: centroid + entry ids + terms. Empty until first `evolve()`.

#### L3 β

Agent attention state (`dim × f64`). Bound into queries so recall is contextual.

Full binary normative detail: [SPEC.md](SPEC.md).

### HRR algebra

Holographic Reduced Representations (Plate 1995) — compositional vectors, local, zero required deps.

| Op | Role |
|----|------|
| `embed_text` | Deterministic hash bag-of-features (+ bigrams) |
| `bind` | Circular convolution (association) |
| `unbind` | Correlation (retrieval) |
| `superpose` | Bundle; capacity ~O(√dim) |
| `cosine_sim` | Rank |

Numpy accelerates FFT paths; pure Python remains correct.

### HAR query protocol

```
query(text, top_k):
  1. q = embed(text)  [hash or learned]
  2. qβ = bind(q, β)
  3. score L2 centroids; take top buckets
  4. score candidate entries (lex + HRR + bio_rank + trust + engram/cubewave)
  5. low-confidence → linear scan fallback
  6. return top_k
```

β updates lightly on append; blends on evolve. Recency uses type-aware half-lives ([bio_rank.py](../hermescube/bio_rank.py) — elephant/dolphin/human maps).

### Learned embeddings

TF-IDF + random projection trained on accumulated descriptions during `evolve()`, persisted as `memory.embedder` (atomic write; corrupt → quarantine).

### Concurrency & crash safety

| Mechanism | Role |
|-----------|------|
| `threading.RLock` | In-process reentrancy |
| `fcntl.flock` | Cross-process exclusive open |
| Atomic rewrite | Write `.tmp` → `fsync` → `os.replace` |
| L2 rewrite order | Invalidate L3 before truncate |

---

## 9. Cuboasis (pocket infrastructure)

Cube-native oasis — not a generic “nexus” product.

| Pillar | Job |
|--------|-----|
| **Space** | Vaults + chambers (one store, many rooms) |
| **Wave** | Cubewave ELM/LMS association field (no torch) |
| **Connections** | Unified SPO ∪ colony ∪ engram ∪ Cubewave ∪ HAR |
| **Progress** | Append-only ledger → usefulness → capability |
| **Governance** | `memory_gate`: capture → review → approve/reject |

Policy modes: `review-first` | `auto-safe` | `off`.  
Evidence states: `prepared_not_observed` · `observed` · `verified` · `superseded` · `refuted` · `rejected`.

Detail: [CUBOASIS.md](CUBOASIS.md) · OMH ideas: [IDEAS_FROM_OMH.md](IDEAS_FROM_OMH.md).

---

## 10. Living growth & self-evolution

- Birth at living version `0.0.0`, era **Cube of Eden**  
- Age = **cycles** + lived wall-clock (not human years)  
- Eras: Eden → Awakening → Formed → Seasoned → Elder  
- Diary: `CUBE.md`; curator refines skills with consent  
- Self-evolution: witness ledger, falsifiable predictions, critic, gardener — no silent theatre  

Detail: [GROWTH.md](GROWTH.md) · [SELF_EVOLUTION.md](SELF_EVOLUTION.md).

---

## 11. Fleet architecture (opt-in)

```
Agent soul cubes (private)          Hive root
─────────────                       ─────────
memory.cube                         hive.cube
soul card                           charters / routes / handoffs
offer distilled  ──pilgrimage──►    assimilate (threat, dedupe, tag)
draw focus ◄──────────────────      [HIVE:agent] quarantine labels
```

- **Hive** — collective memory with provenance  
- **HQ** — ownership, routing, claims, verify, baselines  
- **Interview** — peer craft transfer, consent-gated skill drafts  

Subagents: read-focused memory tools; work flows upward.

---

## 12. CubeDream architecture

```
L4  Hermes MEMORY.md     proposals only — never auto-applied by Cube
 ▲
L3  Hive commit          locked assimilate into hive.cube
 ▲
L2  Dream circle         multi-agent signals · reinforce · dialogue · skim
 ▲
L1  Soul dream           private Light→Deep→Apply + sleep_replay/crystalize
```

**Together ≠ merge later** — agreement across agents is a ranking signal.  
Detail: [CUBEDREAM.md](CUBEDREAM.md).

---

## 13. Hermespace integration architecture

| API tier | Module | Version |
|----------|--------|---------|
| Heart pump | `space_bridge` | `GENERATOR_API_VERSION = 1.0` |
| Circulatory center | `center` | `CENTER_API_VERSION = 1.1` |

| Call | When |
|------|------|
| `ensure_heart` | Install / enter |
| `beat` / `supply`+`return_flow` | Each material turn |
| `autonomic_tick` | Space idle / pulse |
| `heart_status` / `center_status` | Doctor / desktop |

Load-tiered arterial budgets (Sweller-aligned): low 900 · mid 640 · high 420 · protect 280 chars.

Authority rule: **Cube is SoT; Space projects.**  
Detail: [HERMESPACE.md](HERMESPACE.md) · [ANATOMY.md](ANATOMY.md).

---

## 14. Safety & isolation

| Control | Mechanism |
|---------|-----------|
| Prompt injection | `threats.scan_text` / `has_blockable_threat` before durable write |
| Credential-like text | Cuboasis safety gate (assignment-like patterns) |
| Review-first | Candidates sidecar; not execution evidence |
| Evidence fencing | Prefetch packets quoted; claim boundary text |
| Subagent privilege | Read-focused tools; no downward privilege |
| Dual plugin.yaml | Root + `plugin/` must stay identical (`check_isolation.sh`) |
| Update hygiene | `hermescube update` never overwrites `memory.cube` |

---

## 15. Module map (edit guide)

Prefer peeling new surfaces into focused modules over growing `provider.py`.

```
L1 warehouse     cube har hrr embed threats bio_rank dense
L2 provider      provider tools_recall manage* session_end bootstrap agent_manual
L3 cuboasis      cuboasis cubewave memory_gate evidence claims relations colony engram_net
L4 growth        genealogy living curator self_evolution journey wisdom
L5 fleet         hive hq interview
L6 dream         dream dream_circle
L7 heart         space_bridge center
L0 framework     framework/paths config void lexindex
```

Full edit table: [CODEMAP.md](CODEMAP.md).

---

## 16. Data-flow summary (end-to-end)

```
                    ┌──────────── Hermespace desk ────────────┐
 order/idle ───────►│ FOA · load · dual decode · pulse        │
                    └──────────┬──────────────────▲───────────┘
                     systole   │                  │ diastole
                               ▼                  │
┌─ Hermes MemoryManager ──────────────────────────────────────┐
│  prefetch ← Cube HAR     sync_turn → Cube WAL               │
│  on_memory_write → mirror   session_end → pulse/dream/evolve│
└──────────────────────────────┬──────────────────────────────┘
                               ▼
                    memory.cube (SoT) + sidecars
                               │
              Cuboasis gate · colony · engram · cubewave
                               │
              growth / hive / dream (scheduled or manage)
```

---

## 17. Non-goals

- Second agent brain / closed-model activation weights  
 
- Cloud memory SaaS  
- Replacing MEMORY.md or Hermespace FOA desk  
- Auto-rewriting Hermes MEMORY.md from dream (proposals only)  
- Porting AgentDrive / Conductor / OMH skill OS wholesale  
- “HAR always beats scan” marketing — honest benches only  

---

## 18. Version posture & doc index

Ship purpose-aligned increments. Dual `plugin.yaml` identical. Assessment: [ASSESSMENT.md](ASSESSMENT.md).

| Doc | Role |
|-----|------|
| [PURPOSE.md](../PURPOSE.md) | North star |
| [ABOUT.md](../ABOUT.md) | Public pitch |
| **This blueprint** | Whole-project architecture |
| [CODEMAP.md](CODEMAP.md) | Where to edit |
| [SPEC.md](SPEC.md) | Binary normative |
| [FRAMEWORK.md](FRAMEWORK.md) | Housing / void |
| [CUBOASIS.md](CUBOASIS.md) | Pocket infra |
| [ANATOMY.md](ANATOMY.md) | Heart × Space organs |
| [HERMESPACE.md](HERMESPACE.md) | Generator contract |
| [CUBEDREAM.md](CUBEDREAM.md) | Night cycles |
| [HIVE.md](HIVE.md) / [HQ.md](HQ.md) | Fleet |
| [GROWTH.md](GROWTH.md) | Living eras |

---

*Blueprint version tracks product **0.49** (anatomical center). Update this file when a layer’s contract or authority rule changes.*
