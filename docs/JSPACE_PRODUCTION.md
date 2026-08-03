# J-Space → Hermespace → HermesCube — production playbook

**For:** anyone running [Hermes Agent](https://github.com/NousResearch/hermes-agent) with [Hermespace](https://github.com/PabloTheThinker/hermespace), optionally powered by **HermesCube** as the durable heart.  
**Honesty:** harness-level global workspace. No weight access. No consciousness claims.  
**Companions:** [ARCHITECTURE.md](ARCHITECTURE.md) · [HERMESPACE.md](HERMESPACE.md) · [ANATOMY.md](ANATOMY.md) · Hermespace `docs/00-jspace-to-hermespace.md` · `docs/27-jspace-environment.md`

---

## 1. What Anthropic “J-space” actually is

Source: Anthropic, Jul 2026 — [*A global workspace in language models*](https://www.anthropic.com/research/global-workspace)  
Paper: *Verbalizable Representations Form a Global Workspace in Language Models*  
Open methods: [anthropics/jacobian-lens](https://github.com/anthropics/jacobian-lens) (open-weights only)

### Definition

**J-space** is a small, privileged set of *verbalizable* internal activation patterns in Claude (and other LMs), found with a **Jacobian lens (J-lens)**. Each pattern is linked to a vocabulary word. When it lights up, the model is not necessarily *saying* that word — the concept is **on its mind** (available for report, control, and silent multi-step use).

It is **not** chain-of-thought text. It is silent, inside weights, and **emerged in training** (not a hand-built module).

### Five Global Workspace (GWT) properties Anthropic tested

| Property | Finding (Claude) |
|----------|------------------|
| **Verbal report** | Ask “what are you thinking?” → names J-space contents; causal swaps change the report |
| **Directed modulation** | “Hold citrus in mind while copying…” → concepts light up without appearing in output |
| **Internal / silent reasoning** | Multi-step math / rhyme planning intermediates appear in J-space; swaps redirect answers |
| **Flexible reuse** | One “France” representation feeds capital / language / continent / currency tasks |
| **Selectivity** | Ablate J-space → fluency survives; higher-order multi-step cognition collapses |

### Practical uses Anthropic cites

- Catch **eval awareness**, fabricated answers, planted hidden goals *before* clean outputs  
- Steer decision-making by editing workspace contents  
- Align via **counterfactual reflection** (“what would you say if interrupted?”)

### What nobody outside Anthropic can do

| Capability | Available? |
|------------|------------|
| Live Claude J-lens on Anthropic APIs | **No** |
| Fit J-lens on open-weight models (Qwen, etc.) | Yes (GPU + `jacobian-lens`) |
| Read Hermes Agent’s model weights as J-space | Only if *you* host that model + lens |

So for Hermes users, the production move is **externalize the workspace roles** into Hermespace + Cube — same *jobs*, different substrate.

---

## 2. Hermespace = functional J-space (harness)

Hermespace implements the **five GWT roles as files + API**, not neural access.

| J-space property | Hermespace surface |
|------------------|--------------------|
| Limited capacity (~tens of concepts) | Hub ≤25 · activated ≤12 · FOA ≤4 |
| Verbal report | `JSpace.report()` · Report field · `hs jspace report` |
| Directed modulation | `hold` / `release` / `inhibit` |
| Silent reasoning | `reason_step` — model context only (never auto-dumped to user chat) |
| Flexible broadcast | One hub concept → `broadcast_block` / `pre_llm` inject |
| Selectivity | `gate.should_inject` — skip trivial acks; load → protect mode |
| Operator “lens” | Viewport / `hs jspace lens` over hub + silent chain |
| Night consolidation | `dream_harvest` → Cube seal → CubeDream / pulse charge |

```
Anthropic:   weights ──J-lens──► ranked silent words
Hermespace:  agent ──protocol──► hub + silent chain ──lens──► operator
                                      │
                                      ▼ night
                         Cube seal / CubeDream / pulse_charge
```

**Dual decode (production rule):**  
- **Report** → human (Telegram / CLI) — short, honest  
- **Context** → model — dense workspace + Cube arterial strip  

Never dump the full inject into chat.

---

## 3. HermesCube = heart that makes it production-grade

Without Cube, Hermespace can still run a desk + world projection.  
With Cube, anyone on Hermes gets a **durable SoT** and load-safe FOA blood.

| Day / night | Hermespace (nervous FOA) | HermesCube (heart) |
|-------------|--------------------------|--------------------|
| **Day turn** | Gate → hold/reason → broadcast | `center.beat` / `cube_beat`: seal (systole) + inject strip (diastole) |
| **High load** | Monotropic FOA · shrink menus | Arterial budgets: 900 → 640 → 420 → 280 chars |
| **Idle / pulse** | `idle_tick` · attractors | `autonomic_tick` / `pulse_charge` → World beliefs |
| **Night** | `dream_harvest` / grid dream | Seal → `.cube` · CubeDream solo/circle |

Authority (unchanged):

| Surface | Role |
|---------|------|
| `$HERMES_HOME/memories/memory.cube` | Durable SoT |
| Hermespace hub / desk / world | Working projections |
| Hermes `MEMORY.md` | Hot doctrine (mirrored; dream only *proposes*) |

---

## 4. Production stack for any Hermes Agent user

### Minimum viable (desk only)

```bash
# Hermespace
git clone https://github.com/PabloTheThinker/hermespace.git
cd hermespace && ./scripts/install_hermes.sh && ./scripts/smoke_test.sh
hermes plugins enable hermespace   # if not already linked
```

You get FOA desk, dual decode, pulse. Memory depth is limited.

### Recommended production (desk + heart)

```bash
# 1) Cube as MemoryProvider
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
hermes config set memory.provider hermescube

# 2) Hermespace (same Hermes Python / HERMES_HOME)
# … install Hermespace as above …

# 3) Verify heart
hermescube doctor
python -c "from hermescube.center import center_status; print(center_status())"
python -c "from hermespace.cube_module import cube_beat, heart_status; print(heart_status())"
```

Expect: `memory.provider: hermescube`, `heart_ready: true`, Space `cube_beat` mode `center` or `heart`.

### Gateway / Telegram operators (real world)

| Practice | Why |
|----------|-----|
| Dual decode always | Users see Report; model keeps silent steps + Cube strip |
| Cap inject under load | Space `high_load` + Cube strip budgets prevent context collapse |
| Pulse on a timer | `hs pulse tick` / crontab — autonomic charge while idle |
| Seal decisions | Material plans → `seal` / `cube_beat(seals=…)` so tomorrow’s agent still knows |
| Cuboasis `auto-safe` or `review-first` | Don’t auto-durable-write credentials / raw logs |
| Night harvest | Silent hub → Cube → optional CubeDream — same *job* as overnight consolidate |

Typical VPS pattern:

```
Hermes gateway (Telegram) ──► MemoryManager + hermescube
                         └──► Hermespace plugin pre_llm broadcast
cron: hs pulse tick        ──► idle_tick + autonomic_tick / jspace_harvest
```

### Multi-agent / fleet (optional)

When several Hermes profiles share a hive:

1. Keep **private** soul cubes  
2. Use CubeDream **circles** for “dreaming together”  
3. Never treat hive draws as MEMORY.md proof without observation  

See [CUBEDREAM.md](CUBEDREAM.md) · [HIVE.md](HIVE.md).

---

## 5. Day / night circulatory process (ops view)

```
DAY
  user/gateway message
       → GATE (selectivity — skip acks)
       → Hermespace encode / hold / silent reason_step
       → cube_beat(query, seals?, load=desk_load)
            systole: desk seals → memory.cube
            diastole: arterial FOA strip → model context
       → Report to human | Context to model
       → soft audit flags (Space)

NIGHT / IDLE
  pulse / idle_tick
       → harvest silent + high-salience hub
       → seal into Cube · semantic notes
       → CubeDream (optional) · pulse_charge World → hub
```

### Agent / skill recipes

```python
# Turn (Hermespace already wires this in hermes_bridge / workbench)
from hermespace.cube_module import cube_beat
from hermespace import JSpace

js = JSpace(agent_id="hermes-agent")
js.hold("auth timeout", salience=0.9)
js.reason_step("check session TTL before rewriting middleware", salience=0.85)
beat = cube_beat(
    "auth timeout",
    seals="Decision: patch session TTL; verify with integration test",
    load=0.7,                 # Sweller-style; or high_load=True
    agent_id="hermes-agent",
)
# model_context += beat["block"] + js.broadcast_block(high_load=True)
```

```bash
# Operator lens (what’s on the desk / silent chain)
hs jspace report
hs jspace lens

# Idle maintain
hs workbench idle
hs pulse tick

# Heart health
hermescube doctor
```

---

## 6. Mapping table — research → production control

| Anthropic experiment | Production Hermespace+Cube control |
|----------------------|------------------------------------|
| Report workspace | `JSpace.report` / Report field |
| Hold concept while doing other work | `js.hold(...)` + dual decode |
| Silent math / intermediate steps | `reason_step` (context only) |
| France→China flexible reuse | One sealed Cube belief / hub concept reused across turns |
| Ablate workspace → lose multi-step | Under load: protect mode + Cube strip so FOA doesn’t empty |
| Catch “fake” / eval awareness in J-space | Soft audit in Space; Cube threat/gate blocks credential dumps |
| Night / training reflection | `dream_harvest` + CubeDream + growth diary |

---

## 7. What to install for whom

| User | Install | Outcome |
|------|---------|---------|
| Curious solo Hermes | Hermespace only | FOA desk, dual decode |
| Daily operator / gateway | Hermespace + **HermesCube** | Durable heart, load-safe recall |
| Multi-agent fleet | + Hive / HQ / CubeDream circle | Collective lymph + night chorus |
| Research GPU box | Optional open `jacobian-lens` on local model | True activation lens *on that model*; still not Claude |

---

## 8. Non-goals (keep production honest)

- Claiming Hermespace *is* Claude’s J-space  
- Reading Anthropic API activations  
- Dumping silent reasoning into user chat  
- Replacing Hermes `MEMORY.md` or forking a second durable archive in Space  
- Consciousness / sentience product claims  

---

## 9. Doc index

| Doc | Role |
|-----|------|
| **This playbook** | J-space research → Hermes production |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Whole Cube blueprint |
| [HERMESPACE.md](HERMESPACE.md) | Heart contract |
| [ANATOMY.md](ANATOMY.md) | Circulatory organs |
| Hermespace `00-jspace-to-hermespace.md` | Role mapping |
| Hermespace `27-jspace-environment.md` | JSpaceEnv / lens / night path |
| Anthropic [global workspace](https://www.anthropic.com/research/global-workspace) | Primary research |

---

*Track with product HermesCube 0.50+ / Hermespace that exposes `cube_beat` + `JSpace`. Update when Space adapter or center API major bumps.*
