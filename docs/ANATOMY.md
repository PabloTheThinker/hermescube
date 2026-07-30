# Anatomical center — Cube heart × Hermespace nervous system

Functional anatomy for agent memory (not biophysics). Merges:

- **Nous Hermes Agent** coding methods (MemoryProvider lifecycle, soft-fail, caps)
- **Hermespace** cognition (Baddeley / Cowan / GWT / Sweller / pulse)
- **HermesCube** bio-rank + Cuboasis + Hive + CubeDream
- **Comparative species** retention / sleep / social-map ideas already in `bio_rank.py`

```
                    ┌──────── Hermespace (nervous FOA) ────────┐
 orders ──────────► │  desk ≤4 · dual decode · load protect     │
                    │  GWT broadcast on pre_llm_call            │
 idle / pulse ────► │  autonomic → center.autonomic_tick()      │
                    └──────────────▲─────────────┬──────────────┘
                           arteries│             │veins
                        (diastole) │             │ (systole)
                    ┌──────────────┴─────────────▼──────────────┐
                    │         HermesCube HEART (.cube SoT)       │
                    │  hippocampus encode · immune gate · lymph  │
                    │  vascular beds (Cuboasis) · dream USWS     │
                    └────────────────────────────────────────────┘
```

## Organ map

| Organ | Analogue | Owner | API |
|-------|----------|-------|-----|
| **Heart** | Pump / durable blood store | Cube | `ensure_heart`, `heart_status` |
| **Arteries** | Supply to FOA | Cube → Space | `center.supply` / `build_space_inject` |
| **Veins** | Return from desk | Space → Cube | `center.return_flow` / `seal_learning` |
| **Autonomic** | Idle rhythm | Both | `center.autonomic_tick` / Space pulse |
| **Nervous FOA** | PFC / working memory | **Space** | Workbench, cognition.py |
| **Hippocampus** | Encode + consolidate | Cube | provider WAL, evolve, CubeDream |
| **Immune** | Pathogen defense | Cube | threats, memory_gate |
| **Lymph** | Collective fluid | Cube Hive | pilgrimage |
| **Vascular beds** | Local tissue rooms | Cuboasis | chambers / vaults |
| **Blackbox** | Flight provenance / prove | Cube | `flight_capture`, `flight_prove`, `breathe` |

## Species lessons (already in bio_rank + center)

| Species / system | Lesson | Where it lands |
|------------------|--------|----------------|
| Human hippocampus | Encode then consolidate offline | L1 + dream/evolve |
| Human PFC | Tiny FOA executive | Space desk; Cube supplies strip |
| Elephant | Long social/spatial maps | Long half-lives on trait/relationship |
| Dolphin USWS | One hemisphere offline | Dream/idle while gateway stays up |
| Whale culture | Migratory durable routes | resolve / evolution durability |
| Bee/ant colony | Stigmergy trails | colony pheromone + engram hubs |

## Nous methods we copy (discipline, not code)

1. **One external provider** — Cube is the MemoryProvider; Space is not a second one  
2. **Soft-fail** — every center phase catches; Space never crashes on missing Cube  
3. **Prefetch caps** — load-tiered strip budgets (900 / 640 / 420 / 280)  
4. **Builtin coexistence** — MEMORY.md stays hot; Cube mirrors  
5. **Lifecycle clarity** — ensure → seal → supply → (idle) charge  

## Hermespace methods we align with

1. **Cowan FOA ≤4** — strip is dense blood, not a novel  
2. **Sweller load** — `center.supply(load=0.8)` or `load="protect"` shrinks arteries  
3. **GWT broadcast** — Space still owns when to inject; Cube only generates the block  
4. **Pulse autonomic** — `idle_tick` / `world_evolve` should call `autonomic_tick`  
5. **Dual decode** — Cube strip goes to **model context**, not user chat dump  

## API (`hermescube.center` · `CENTER_API_VERSION = "1.1"`)

```python
from hermescube.center import (
    center_status,   # organ map + heart readiness
    beat,            # one turn: ensure → systole → diastole
    supply,          # diastole only
    return_flow,     # systole only
    autonomic_tick,  # idle / pulse
    strip_budget,    # chars for a load level
    ANATOMY,
)
```

### Turn cycle (recommended)

```python
from hermescube.center import beat

cycle = beat(
    query=user_text or desk.goal,
    seals=sealed_decision_text,   # or None
    load=desk_load_total,         # 0..1 from Hermespace cognition
    agent_id=agent_id,
)
model_context += cycle["block"]
```

### Idle / pulse

```python
from hermescube.center import autonomic_tick
autonomic_tick(agent_id=agent_id)  # ensure + charge WorldModel
```

## Authority (unchanged)

| Surface | Authority |
|---------|-----------|
| `memory.cube` | Durable SoT (heart blood) |
| Hermespace world / desk | Working projections — charged, never a second heart |
| MEMORY.md | Hot doctrine — mirrored, dream only proposes |

See also: [HERMESPACE.md](HERMESPACE.md) · [PURPOSE.md](../PURPOSE.md) · `bio_rank.py`.
