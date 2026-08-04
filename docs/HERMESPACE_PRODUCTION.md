# Hermespace FOA production playbook

**For:** anyone running [Hermes Agent](https://github.com/NousResearch/hermes-agent) with [Hermespace](https://github.com/PabloTheThinker/hermespace), optionally powered by **HermesCube** as the durable heart.  
**Honesty:** harness-level FOA workspace. No weight access. No consciousness claims.  
**Companions:** [ARCHITECTURE.md](ARCHITECTURE.md) · [HERMESPACE.md](HERMESPACE.md) · [ANATOMY.md](ANATOMY.md)

---

## 1. What Anthropic’s global-workspace research describes

Source: Anthropic, Jul 2026 — [*A global workspace in language models*](https://www.anthropic.com/research/global-workspace)  
Paper: *Verbalizable Representations Form a Global Workspace in Language Models*  
Open methods: [anthropics/jacobian-lens](https://github.com/anthropics/jacobian-lens) (open-weights only)

### Definition

Researchers found a small, privileged set of *verbalizable* internal activation patterns in Claude (and other LMs), using a **Jacobian lens**. Each pattern is linked to a vocabulary word. When it lights up, the model is not necessarily *saying* that word — the concept is **on its mind** (available for report, control, and silent multi-step use).

It is **not** chain-of-thought text. It is silent, inside weights, and **emerged in training** (not a hand-built module).

### Five Global Workspace (GWT) properties tested

| Property | Finding (Claude) |
|----------|------------------|
| **Verbal report** | Ask “what are you thinking?” → names workspace contents; causal swaps change the report |
| **Directed modulation** | “Hold citrus in mind while copying…” → concepts light up without appearing in output |
| **Internal / silent reasoning** | Multi-step intermediates appear in the workspace; swaps redirect answers |
| **Flexible reuse** | One “France” representation feeds capital / language / continent / currency tasks |
| **Selectivity** | Ablate the workspace → fluency survives; higher-order multi-step cognition collapses |

### What nobody outside Anthropic can do

| Capability | Available? |
|------------|------------|
| Live Claude Jacobian-lens on Anthropic APIs | **No** |
| Fit a lens on open-weight models (Qwen, etc.) | Yes (GPU + `jacobian-lens`) |
| Read Hermes Agent’s model weights this way | Only if *you* host that model + lens |

So for Hermes users, the production move is **externalize the workspace roles** into Hermespace + Cube — same *jobs*, different substrate. Hermespace does **not** use third-party “jspace” product naming.

---

## 2. Hermespace = FOA workspace harness

Hermespace implements the **five GWT roles as files + API**, not neural access.

| GWT property | Hermespace surface |
|--------------|--------------------|
| Limited capacity (~tens of concepts) | Hub ≤25 · activated ≤12 · FOA ≤4 |
| Verbal report | `Workspace.report()` · Report field · `hs workspace report` |
| Directed modulation | `hold` / `release` / `inhibit` |
| Silent reasoning | `reason_step` — model context only (never auto-dumped to user chat) |
| Flexible broadcast | One hub concept → `broadcast_block` / `pre_llm` inject |
| Selectivity | `gate.should_inject` — skip trivial acks; load → protect mode |
| Operator lens | Viewport / `hs workspace lens` over hub + silent chain |
| Night consolidation | `dream_harvest` → Cube seal → CubeDream / pulse charge |

```
Anthropic:   weights ──Jacobian lens──► ranked silent words
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
| **Day turn** | Gate → hold/reason → broadcast | `center.beat` / `cube_beat`: seal + inject strip |
| **High load** | Monotropic FOA · shrink menus | Arterial budgets: 900 → 640 → 420 → 280 chars |
| **Idle / pulse** | `idle_tick` · attractors | `autonomic_tick` / `pulse_charge` → World beliefs |
| **Night** | `dream_harvest` / grid dream | Seal → `.cube` · CubeDream solo/circle |

Authority:

| Surface | Role |
|---------|------|
| `$HERMES_HOME/memories/memory.cube` | Durable SoT |
| Hermespace hub / desk / world | Working projections |
| Hermes `MEMORY.md` | Hot doctrine (mirrored; dream only *proposes*) |

---

## 4. Production stack for any Hermes Agent user

### Minimum viable (desk only)

```bash
git clone https://github.com/PabloTheThinker/hermespace.git
cd hermespace && ./scripts/install_hermes.sh && ./scripts/smoke_test.sh
hermes plugins enable hermespace
```

### Recommended production (desk + heart)

```bash
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
hermes config set memory.provider hermescube
# install Hermespace on the same Hermes Python / HERMES_HOME
hermescube doctor
```

### Gateway / Telegram operators

| Practice | Why |
|----------|-----|
| Dual decode always | Users see Report; model keeps silent steps + Cube strip |
| Cap inject under load | Prevents context collapse |
| Pulse on a timer | Autonomic charge while idle |
| Seal decisions | Tomorrow’s agent still knows |
| Cuboasis `auto-safe` or `review-first` | Don’t auto-durable-write credentials / raw logs |
| Night harvest | Silent hub → Cube → optional CubeDream |

```
Hermes gateway ──► MemoryManager + hermescube
              └──► Hermespace plugin pre_llm broadcast
cron: hs pulse tick ──► idle_tick + autonomic_tick / workspace_harvest
```

---

## 5. Day / night ops

```
DAY
  message → GATE → hold / silent reason_step → cube_beat
       → Report to human | Context to model

NIGHT / IDLE
  pulse → harvest silent + high-salience hub → Cube / CubeDream
```

```python
from hermespace.cube_module import cube_beat
from hermespace import Workspace

ws = Workspace(agent_id="hermes-agent")
ws.hold("auth timeout", salience=0.9)
ws.reason_step("check session TTL before rewriting middleware", salience=0.85)
beat = cube_beat(
    "auth timeout",
    seals="Decision: patch session TTL; verify with integration test",
    load=0.7,
    agent_id="hermes-agent",
)
# model_context += beat["block"] + ws.broadcast_block(high_load=True)
```

```bash
hs workspace report
hs workspace lens
hs pulse tick
hermescube doctor
```

---

## 6. Non-goals (keep production honest)

- Claiming Hermespace *is* Claude’s internal workspace  
- Reading Anthropic API activations  
- Dumping silent reasoning into user chat  
- Replacing Hermes `MEMORY.md` or forking a second durable archive in Space  
- Consciousness / sentience product claims  
- Using third-party “jspace” product naming for Hermespace APIs  

---

## 7. Doc index

| Doc | Role |
|-----|------|
| **This playbook** | Research → Hermes + Hermespace production |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Whole Cube blueprint |
| [HERMESPACE.md](HERMESPACE.md) | Heart contract |
| [ANATOMY.md](ANATOMY.md) | Circulatory organs |
| Anthropic [global workspace](https://www.anthropic.com/research/global-workspace) | Primary research |

---

*Track with HermesCube 0.50+ / Hermespace that exposes `cube_beat` + `Workspace`.*
