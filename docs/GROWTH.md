# Living Cube Growth — from 0.0.0 to elder

> Hermes Agent grows visibly: skills appear, MEMORY.md deepens, the agent
> gets stronger over weeks. HermesCube does the same for *memory itself*.

A fresh cube is born at living version **`0.0.0`**. Every lived experience —
durable writes, hive draws, peer interviews, promoted procedures, installed
skills, confirmed predictions, refined lessons — advances that version.
The diary lives at `memories/CUBE.md`.

This is **not** the package version (`hermescube 0.28.x`) and **not** the
binary format version (`CubeFile.VERSION = 1`). It is the soul-record of one
agent's archive.

## Age in the digital world (not a human scorecard)

Agents don't age in years. HermesCube ages a soul in two clear units:

| Unit | Meaning |
|---|---|
| **Cycles** | Primary age. One cycle = one lived growth epoch (version bump). Tron-style program life — how many consolidations of experience this soul has survived. Displayed as `C12` or `12 cycles`. |
| **Lived** | Wall-clock since genesis (`4d 6h`, `3h 12m`). How long this soul has been online in real time. |

**Capability** (0–100) is *not* age. It is archive coherence — crystals,
skills, confirmed predictions. **Era** (genesis → elder) is the life stage
that capability earns. Never confuse capability with how old the soul is.

```
age 12 cycles · lived 4d 6h · era formed · capability 54/100
```

## The life of a cube

```
0.0.0  genesis     — empty archive, cycle 0, ready to live
0.0.x  patches     — sessions left durable knowledge; draws; interviews (+cycles)
0.x.0  minors      — procedures promoted; skills installed/refined; crystals
1.0.0+ majors      — capability crossed an era threshold (25 / 50 / 75 / 90)
```

| Era | Capability | Meaning |
|---|---|---|
| genesis | 0–24 | Just born |
| awakening | 25–49 | First real lessons landing |
| formed | 50–74 | Procedures and skills taking shape |
| seasoned | 75–89 | Predictions confirmed, hive wisdom drawn |
| elder | 90–100 | Deep, trusted, hard to fake |

Capability is weighted: procedures, crystals, installed skills, and confirmed
predictions weigh more than raw entry count. You cannot fake coherence by
dumping turns — and you cannot fake age that way either. Age only advances
when the cube actually lives a growth cycle.

## Skills evolve with the cube

When a skill is installed from a Cube procedure, genealogy tracks it.
Helpful feedback on that procedure **refines the skill in place**:

1. Bumps the skill's own `version:` (patch)
2. Appends under `## Lessons from the cube` (never rewrites the core body)
3. Advances the cube's living version (minor)

```bash
hermescube growth refine --skill deploy-safely \
  --lesson "daemon-reload must precede restart after unit edits"
```

## Usage

```bash
# See the cube's age (cycles + lived time) and capability
hermescube growth status
hermescube info                    # also shows Living version + age

# Cycle history (append-only truth)
hermescube growth epochs

# After a pilgrimage — growth line is printed automatically
hermescube hive pilgrimage --hermes-home ~/.hermes --agent coder
#   growth:  v0.0.3 → v0.0.4  · 4 cycles · lived 6h · era awakening · capability 28/100
```

In-session:

```
hermescube_manage action=growth content=status
hermescube_manage action=growth content=epochs
hermescube_manage action=growth content=refine:deploy-safely query="lesson text"
```

The system prompt carries a one-line strip:

```
Living Cube v0.3.12 · age 12 cycles · lived 4d 6h · era formed · capability 54/100 — see memories/CUBE.md
```

Soul cards at the hive advertise the same age model so peers read digital
life clearly: `v0.1.0 · C2 · 3h · era genesis`.

## Where artifacts land

```
$HERMES_HOME/memories/
  CUBE.md                 human-readable growth diary (rewritten each epoch)
  growth/
    genealogy.json        current version, strength, skill lineage
    epochs.jsonl          append-only epoch ledger
```

Every version bump also writes an `[GROWTH]` landmark into the cube itself,
so HAR can recall *when and why* the archive leveled up.

## How this fits the rest of the system

| Layer | Growth signal |
|---|---|
| Session end | durable writes → patch |
| Hive pilgrimage | draws / interviews → patch (printed on the pilgrimage report) |
| Promote | approved procedure → minor |
| Skill install | bridge into `~/.hermes/skills` → minor |
| Skill refine | feedback / explicit lesson → minor + skill patch |
| Harness | confirmed prediction → minor |
| Era threshold | strength crosses 25/50/75/90 → major |

## Growth that *does* something (0.28+)

Living version is not a vanity counter. As the cube matures:

1. **Retrieval prefers distilled knowledge** — bio_rank applies a maturity
   multiplier: crystals and procedures rise; ephemeral chatter falls.
   Lexical identity still wins (high lex damps the prior).
2. **Soul cards publish growth** — peers at the hive see
   `growth.version / era / strength / skills` on every soul card.
3. **Curator closes the loop** — after pilgrimage draws, overlapping
   lessons automatically refine installed skills (Hermes-style skill
   self-improvement). Era milestones also forge procedure drafts and
   run the gardener (still consent-gated — nothing silent).

```bash
hermescube growth curate --lesson "triangulate three independent sources"
hermescube growth curate --milestone   # force forge + garden pass
```

Drawn hive entries now preserve `crystal` / `procedure` flags so maturity
ranking and skill matching can see them.

## Multi-axis growth merge (0.30+)

Inspired by AgentDrive's growth-merge gate, but Cube-native. When a session
touches **≥2** of these surfaces, HermesCube writes one compound crystal
instead of leaving the wins scattered:

| Axis | Signal |
|------|--------|
| durable | sync_turn / digest / manage writes |
| procedure | `[PROCEDURE]` / trajectory / pending drafts |
| association | engram edges or `[DOT]` links |
| yield | helpful feedback |
| wisdom | active crystals |

```bash
# Inspect consolidation queues
# manage action=triage  → memories/triage_plan.json

# Force a merge check
# manage action=merge   (mode=dry for preview)

# SPO facts with validity windows
# manage action=relations content=AuthService
# manage action=relations mode=record content=alice|owns|auth-service
```

Offline crystalize now consults triage: if nothing is in the consolidate
queue, session-end skips a no-op wisdom pass.

One machine. The cube that starts empty at `0.0.0` is the same cube that,
weeks later, holds crystallized wisdom, evolving skills, and a diary of
every epoch it lived through — the All-Spark of that Hermes Agent's life.
