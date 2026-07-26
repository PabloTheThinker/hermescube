# Living Cube Growth — from 0.0.0 to elder

> Hermes Agent grows visibly: skills appear, MEMORY.md deepens, the agent
> gets stronger over weeks. HermesCube does the same for *memory itself*.

A fresh cube is born at living version **`0.0.0`**. Every lived experience —
durable writes, hive draws, peer interviews, promoted procedures, installed
skills, confirmed predictions, refined lessons — advances that version and
raises a strength score. The diary lives at `memories/CUBE.md`.

This is **not** the package version (`hermescube 0.27.x`) and **not** the
binary format version (`CubeFile.VERSION = 1`). It is the soul-age of one
agent's archive.

## The life of a cube

```
0.0.0  genesis     — empty archive, ready to live
0.0.x  patches     — sessions left durable knowledge; draws; interviews
0.x.0  minors      — procedures promoted; skills installed/refined; crystals
1.0.0+ majors      — strength crossed an era threshold (25 / 50 / 75 / 90)
```

| Era | Strength | Meaning |
|---|---|---|
| genesis | 0–24 | Just born |
| awakening | 25–49 | First real lessons landing |
| formed | 50–74 | Procedures and skills taking shape |
| seasoned | 75–89 | Predictions confirmed, hive wisdom drawn |
| elder | 90–100 | Deep, trusted, hard to fake |

Strength is weighted: procedures, crystals, installed skills, and confirmed
predictions weigh more than raw entry count. You cannot fake maturity by
dumping turns.

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
# See the cube's age
hermescube growth status
hermescube info                    # also shows Living version

# Epoch history (append-only truth)
hermescube growth epochs

# After a pilgrimage — growth line is printed automatically
hermescube hive pilgrimage --hermes-home ~/.hermes --agent coder
#   growth:      v0.0.3 → v0.0.4  (awakening, strength 28/100)
```

In-session:

```
hermescube_manage action=growth content=status
hermescube_manage action=growth content=epochs
hermescube_manage action=growth content=refine:deploy-safely query="lesson text"
```

The system prompt carries a one-line strip:

```
Living Cube v0.3.12 (formed, strength 54/100) — grows with every session; see memories/CUBE.md
```

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

One machine. The cube that starts empty at `0.0.0` is the same cube that,
weeks later, holds crystallized wisdom, evolving skills, and a diary of
every epoch it lived through — the All-Spark of that Hermes Agent's life.
