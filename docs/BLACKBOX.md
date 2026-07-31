# Blackbox organ — flight recorder in the Cube heart

**Integrated:** 2026-07-30 · **Center API:** 1.2+  
**Inspired by:** [asimons81/hermes-blackbox](https://github.com/asimons81/hermes-blackbox) (Apache-2.0 concepts)  
**Home:** first-class `hermescube.blackbox` + anatomical organ in `center.py`

## Place in the library

HermesCube is the **library under Hermes**. Blackbox is the **heart’s provenance desk**:

- The book holds knowledge.  
- Blackbox holds **proof of runs** that produced knowledge.  
- Agents do not get to say **done** without a trajectory receipt.

## Promise

Capture Hermes runs as redacted **FlightRecords**. Hash the event stream. **Prove** natural-language claims against evidence. Optionally **breathe**: inhale flight → prove → exhale seals + relation weave.

## Handoff line (holds if cube breaks)

Agent continuity handoffs dual-write into the blackbox:

- `memories/blackbox/handoff-line.jsonl`
- `memories/blackbox/handoffs/*.json` (FlightRecord + sha256)

```bash
hermescube handoff line
hermescube handoff recover
```

See [HANDOFF.md](HANDOFF.md).

## CLI

```bash
hermescube blackbox status
hermescube blackbox capture --latest
hermescube blackbox prove --claim "tests pass" --latest
hermescube blackbox verify --record ~/.hermes/memories/blackbox/bb_….json
hermescube blackbox breathe --latest   # post-session / cron — not every chat turn
```

Python:

```python
from hermescube import center
center.flight_capture(latest=True)
center.flight_prove("tests pass")
center.breathe(latest=True)  # evidence-oriented full cycle
```

## Layout

```
hermescube/blackbox/
  flight.py     schema + integrity
  redact.py     secrets ON by default
  capture.py    state.db → FlightRecord
  prove.py      claim auditor
  inspire.py    breathe cycle (inhale / gas_exchange / exhale)
center.py       organ map + flight_* + breathe
```

Records default to `$HERMES_HOME/memories/blackbox/`.

## Breathe (pulmonary center)

```bash
hermescube blackbox breathe --latest
```

1. **Inhale** — capture redacted flight  
2. **Gas exchange** — prove standing claims  
3. **Exhale** — seal evidence into the book + relation hypoxia fix (`connect_dots`)

**Use after sessions or on a night cron.** Too heavy for every user message.

## Not this

- Not a pip dependency on the external blackbox repo (Cube-owned API)  
- Not cloud telemetry — local proof packages  
- Does not replace Cube HAR memory — different job (evidence of *runs*)

## Attribution

Design reverse-engineered from hermes-blackbox v0.1 for integration into HermesCube’s center. Credit: Tony Simons / Hermes fleet contributors.
