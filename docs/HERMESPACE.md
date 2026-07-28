# HermesCube × Hermespace — generator contract

**HermesCube is the core.** Hermespace is the pocket workbench that **runs on Cube power**.

Companion: [PabloTheThinker/hermespace](https://github.com/PabloTheThinker/hermespace)  
North star: [PURPOSE.md](../PURPOSE.md)

```
Hermes Agent
  ├── Hermespace     FOA desk · dual decode · inject budget · pulse/idle
  │     ↑ powered by generator
  └── HermesCube     .cube SoT · Cuboasis · Hive · CubeDream · growth
           │
           └─ space_bridge  (inject strip · seal intake · world charge · status)
```

## Why “generator”

Hermespace alone can keep a turn-focused desk and a JSONL world projection.
Under load those surfaces either **bloat context** or **starve memory**.

Cube is the generator:

1. **Stores** the long tail in `memory.cube` (no prune-as-policy)
2. **Generates** a dense FOA strip when Space asks (`build_space_inject`)
3. **Intakes** sealed desk decisions into the archive (`seal_to_cube`)
4. **Charges** Space’s WorldModel active wisdom from Cube crystals (`sync_world_beliefs`)

Space remains the workbench. Cube remains the warehouse. The generator is the
cable between them — not a second brain inside Space.

## Authority

| Surface | Authority |
|---------|-----------|
| `$HERMES_HOME/memories/memory.cube` | **Durable memory SoT** |
| Hermespace world JSONL / `world.json` | Working projection — recharge from Cube |
| Hermespace ACTIVE desk | Turn FOA only — seal important decisions into Cube |
| MEMORY.md | Hot doctrine — Cube mirrors; dream paths only *propose* edits |

## APIs (Cube package)

```python
from hermescube.space_bridge import (
    build_space_inject,  # generator → FOA strip
    seal_to_cube,        # desk → durable archive
    sync_world_beliefs,  # cube wisdom → WorldModel
    module_status,       # generator readiness
    cube_recall,         # raw (desc, score) hits
)
```

| Call | Typical Space use |
|------|-------------------|
| `build_space_inject(query, high_load=…)` | After world/fabric; high load → ~420 chars dense strip |
| `seal_to_cube(content)` | `remember_learning` / sealed decisions |
| `sync_world_beliefs()` | Journey / hygiene / evolve — fill Beliefs (Active Wisdom) |
| `module_status()` | Doctor / desktop status |

## APIs (Space package)

Soft dependency — never hard-fail if Cube is missing:

```python
from hermespace.cube_module import cube_inject, cube_seal, cube_status
```

Wired in Hermespace `hermes_bridge.on_pre_llm_call` (high-load cube strip)
and learning seal paths.

## High load

Space already caps inject and drops bulky world prose.  
Cube adds a **dense strip** of the most relevant durable facts for the FOA
query — so monotropic turns still have *memory*, not bulk.

Prefer order under load: active wisdom → Animus/engram hubs → query hits.

## Install both

```bash
# Cube → user Hermes home (MemoryProvider)
hermes plugins install PabloTheThinker/hermescube
cd "$HERMES_HOME/plugins/hermescube" && ./scripts/install_hermes.sh
hermes config set memory.provider hermescube

# Space → existing Hermespace install (plugin + skill)
# Ensure hermescube is importable on the same Hermes Python
```

Verify:

```bash
hermescube doctor
python -c "from hermescube.space_bridge import module_status; print(module_status())"
```

## What Cube does *not* do for Space

- Does not own FOA caps, dual decode, or pulse timers  
- Does not replace `Workbench.receive_order`  
- Does not dump full L1 into inject (generator = dense strip)  
- Does not require Space to operate as Hermes `memory.provider`

## Roadmap posture (Cube side)

Deepen the generator — don’t fork a second archive inside Space:

1. Keep inject hygiene (no dogfood / superseded / PERSIST spam)
2. Prefer wisdom → hubs → query hits under load
3. Journey push keeps WorldModel Beliefs charged from Cube
4. Cuboasis governance + CubeDream stay Cube-native; Space may *display* cards, not reimplement the gate
