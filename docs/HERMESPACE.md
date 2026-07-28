# HermesCube × Hermespace — heart / generator contract

**HermesCube is the heart.** Hermespace is the pocket workbench that **runs on Cube power**.

Companion: [PabloTheThinker/hermespace](https://github.com/PabloTheThinker/hermespace)  
North star: [PURPOSE.md](../PURPOSE.md)  
Contract version: `GENERATOR_API_VERSION = "1.0"` (additive fields OK within `1.x`)

```
Hermes Agent
  ├── Hermespace     FOA desk · dual decode · inject budget · pulse/idle
  │     ↑ powered by heart
  └── HermesCube     .cube SoT · Cuboasis · Hive · CubeDream · growth
           │
           └─ space_bridge  (ensure · status · inject · seal · charge · pulse)
```

## Why “heart”

Hermespace alone can keep a turn-focused desk and a JSONL world projection.
Under load those surfaces either **bloat context** or **starve memory**.

Cube is the heart:

1. **Stores** the long tail in `memory.cube` (no prune-as-policy)
2. **Bootstraps** via `ensure_heart` so Space never depends on a missing file
3. **Generates** a dense FOA strip when Space asks (`build_space_inject`)
4. **Intakes** sealed desk decisions into the archive (`seal_learning`)
5. **Charges** Space’s WorldModel on idle/pulse (`pulse_charge` / `sync_world_beliefs`)

Space remains the workbench. Cube remains the warehouse. The heart is the
cable between them — not a second brain inside Space.

## Authority

| Surface | Authority |
|---------|-----------|
| `$HERMES_HOME/memories/memory.cube` | **Durable memory SoT** |
| Hermespace world JSONL / `world.json` | Working projection — recharge from Cube |
| Hermespace ACTIVE desk | Turn FOA only — seal important decisions into Cube |
| MEMORY.md | Hot doctrine — Cube mirrors; dream paths only *propose* edits |

## Stable APIs (Cube `hermescube.space_bridge`)

```python
from hermescube.space_bridge import (
    GENERATOR_API_VERSION,
    ensure_heart,
    heart_status,          # preferred (module_status is alias)
    build_space_inject,
    seal_learning,         # preferred structured seal
    seal_to_cube,          # bool back-compat
    sync_world_beliefs,
    pulse_charge,
)
```

| Call | Typical Space use |
|------|-------------------|
| `ensure_heart()` | Install / `Workbench.enter` / first pulse |
| `heart_status()` | Doctor / desktop / feature detect `api_version` |
| `build_space_inject(query, high_load=…)` | `pre_llm_call` after world/fabric |
| `seal_learning(content, entry_type=…)` | `remember_learning` / sealed decisions |
| `seal_to_cube(…)` | Legacy bool path (`cube_seal`) |
| `pulse_charge(agent_id=…)` | `idle_tick` / pulse job — ensure + world charge |
| `sync_world_beliefs()` | Explicit charge without ensure |

## Hermespace integration checklist

Wire these on the Space side (soft-import; never hard-fail):

1. **Install / enter** — `ensure_heart()` once so `memory.cube` exists  
2. **Feature detect** — `heart_status()["api_version"]` starts with `"1."`  
3. **Inject** — keep `build_space_inject` in `hermes_bridge` under high load  
4. **Seal** — prefer `seal_learning` (id + ok); keep `seal_to_cube` as fallback  
5. **Pulse** — call `pulse_charge(agent_id=…)` from idle/pulse so World Beliefs stay charged  
6. **Doctor** — surface `heart_ready`, `entries`, `growth.era_label` on desktop/status  
7. **Do not** grow a second durable archive in Space — project from Cube  

### Recommended `cube_module.py` shape (Space)

```python
def cube_ensure():
    try:
        from hermescube.space_bridge import ensure_heart
        return ensure_heart()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def cube_status():
    try:
        from hermescube.space_bridge import heart_status
        return heart_status()
    except Exception as e:
        return {"available": False, "heart_ready": False, "error": str(e)}

def cube_inject(query, *, high_load=False, max_chars=None):
    try:
        from hermescube.space_bridge import build_space_inject
        return build_space_inject(query, high_load=high_load, max_chars=max_chars) or ""
    except Exception:
        return ""

def cube_seal(content, **kwargs):
    try:
        from hermescube.space_bridge import seal_learning, seal_to_cube
        if kwargs.pop("structured", False):
            return seal_learning(content, **kwargs)
        return bool(seal_to_cube(content, **kwargs))
    except Exception:
        return False

def cube_pulse(*, agent_id="hermes-agent"):
    try:
        from hermescube.space_bridge import pulse_charge
        return pulse_charge(agent_id=agent_id)
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

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
python -c "from hermescube.space_bridge import heart_status; print(heart_status())"
```

## What Cube does *not* do for Space

- Does not own FOA caps, dual decode, or pulse timers  
- Does not replace `Workbench.receive_order`  
- Does not dump full L1 into inject (heart = dense strip)  
- Does not require Space to operate as Hermes `memory.provider`

## Roadmap posture (Cube side)

Deepen the heart — don’t fork a second archive inside Space:

1. Keep inject hygiene (no dogfood / superseded / PERSIST spam)
2. Prefer wisdom → hubs → query hits under load
3. `pulse_charge` keeps WorldModel Beliefs fed from Cube
4. Cuboasis governance + CubeDream stay Cube-native; Space may *display* cards, not reimplement the gate
