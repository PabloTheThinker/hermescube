# HermesCube × Hermespace — heart / generator contract

**HermesCube is the library and the heart.** Hermespace is the pocket workbench that **runs on Cube power**.

Companion: [PabloTheThinker/hermespace](https://github.com/PabloTheThinker/hermespace)  
North star: [PURPOSE.md](../PURPOSE.md) · Library pitch: [ABOUT.md](../ABOUT.md) · Provenance: [BLACKBOX.md](BLACKBOX.md)  
Contract version: `GENERATOR_API_VERSION = "1.0"` (additive fields OK within `1.x`); center `1.2+` adds blackbox / breathe

```
Hermes Agent
  ├── Hermespace     FOA desk · dual decode · inject budget · pulse/idle
  │     ↑ powered by heart / library generator
  └── HermesCube     .cube book · blackbox · Cuboasis · Hive · CubeDream · growth
           │
           └─ space_bridge + center  (ensure · beat · inject · seal · charge · flight · breathe)
```

## Why “heart” (and library)

Cube is the heart **and** the stacks:

1. **Stores** durable long-tail memory (the book)  
2. **Bootstraps** via `ensure_heart` so Space never depends on a missing file  
3. **Pumps** FOA blood under load budgets  
4. **Returns** desk seals into the volume  
5. **Stamps** provenance via blackbox flights  

Space remains the workbench. Cube remains the warehouse/library. The heart is the
contract between them — not a second brain inside Space. Under load, Space either
**bloats context** or **starves memory**; Cube supplies a dense FOA strip so monotropic
turns still have *memory*, not bulk.

## Authority

| Surface | Authority |
|---------|-----------|
| `$HERMES_HOME/memories/memory.cube` | **Durable memory SoT (the book)** |
| Blackbox flights under `memories/blackbox/` | Provenance receipts for runs |
| Hermespace world JSONL / `world.json` | Working projection — recharge from Cube |
| Hermespace ACTIVE desk | Turn FOA only — seal important decisions into Cube |
| MEMORY.md | Hot doctrine / card catalog — Cube mirrors; dream paths only *propose* edits |

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

Wire these on the Space side (soft-import; never hard-fail). Prefer the
**anatomical center** when available (`hermescube.center`, API `1.2+`); fall
back to heart primitives (`space_bridge`, API `1.0`).

1. **Install / enter** — `ensure_heart()` once so `memory.cube` exists  
2. **Feature detect** — `center_status()` or `heart_status()["api_version"]` starts with `"1."`  
3. **Turn beat** — `center.beat(query, seals=…, load=desk_load)` *or* inject+seal separately  
4. **Inject** — keep arterial supply in `hermes_bridge` under high load (model context only)  
5. **Seal** — prefer `seal_learning` / `return_flow`; keep `seal_to_cube` as fallback  
6. **Pulse** — `autonomic_tick(agent_id=…)` / `pulse_charge` from idle so World Beliefs stay charged  
7. **Doctor** — surface `heart_ready`, organ map, `entries`, `growth.era_label`  
8. **Do not** grow a second durable archive in Space — project from Cube  

Full organ map: [ANATOMY.md](ANATOMY.md).

### Recommended Space adapter shape

```python
def cube_beat(query, *, seals=None, load=0.5, agent_id="hermes-agent"):
    try:
        from hermescube.center import beat
        return beat(query, seals=seals, load=load, agent_id=agent_id)
    except Exception:
        # fall back to heart 1.0
        from hermescube.space_bridge import build_space_inject, seal_to_cube, ensure_heart
        ensure_heart()
        if seals:
            seal_to_cube(seals if isinstance(seals, str) else "\n".join(seals))
        return {"block": build_space_inject(query, high_load=float(load) >= 0.65), "ok": True}

def cube_pulse(*, agent_id="hermes-agent"):
    try:
        from hermescube.center import autonomic_tick
        return autonomic_tick(agent_id=agent_id)
    except Exception:
        from hermescube.space_bridge import pulse_charge
        return pulse_charge(agent_id=agent_id)
```

Legacy `cube_inject` / `cube_seal` / `cube_status` remain valid (heart 1.0).

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

## Related

- [HERMESPACE_PRODUCTION.md](HERMESPACE_PRODUCTION.md) — Anthropic global-workspace research research → Hermes Agent + Hermespace production
- [ANATOMY.md](ANATOMY.md) — circulatory metaphor + APIs
- Hermespace [`docs/00-anthropic-gwt-to-hermespace.md`](https://github.com/PabloTheThinker/hermespace/blob/main/docs/00-anthropic-gwt-to-hermespace.md)
- Hermespace [`docs/20-hermescube-bridge.md`](https://github.com/PabloTheThinker/hermespace/blob/main/docs/20-hermescube-bridge.md)
