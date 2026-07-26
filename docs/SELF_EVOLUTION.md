# Grounded self-evolution — the harness inside the Cube

> Adapted from the [hermes-self-evolution](https://github.com/erenciracioglu-dotcom/hermes-self-evolution)
> harness pattern (Evolution + Critic + Verifier + Gardener) into
> HermesCube's own offline cycle — mechanical, local, no extra cron
> infrastructure required (though cron works great).

## The problem it solves

Self-improvement loops have three classic failure modes:

1. **Bookkeeping theatre** — "evolution" that only produces internal
   hygiene (re-indexing, log rotation) with no observable improvement.
2. **Silent failure** — the loop stalls and nobody notices, because a
   healthy loop and a dead loop look identical from outside.
3. **Ungrounded change** — structural changes justified by nothing but
   the model's own opinion of itself.

HermesCube enforces the counters to all three **in code**, not in prompts.

## The five rules

### 1. Witness log is ground truth

`memories/harness/witness_log.jsonl` is an append-only ledger of *real*
friction. Two sources:

- **Auto-detection** (`witness_detect: true`, default): `sync_turn`
  conservatively detects user corrections ("no, that's wrong", "I already
  told you", "still broken") and hard errors (tracebacks, fatal errors).
- **Manual**: the agent calls `hermescube_manage action=witness
  content="..." severity=high`, or the operator runs
  `hermescube harness witness --desc "..."`.

### 2. No silent cycles

Every evolve cycle appends a report to
`memories/harness/evolution_cycles.jsonl` — outcome `action` (anchored to
open witnesses, which it marks addressed), `noop` (pure index maintenance,
honest about it), or `failed`. A stalled harness is visible immediately:
the cycle log stops growing.

### 3. Falsifiable predictions

When a procedure is promoted through the consent gate, the Cube commits a
prediction to `memories/harness/predictions.jsonl`:
*"promoted procedure X earns trust ≥ 0.6"* with a horizon. Supported checks:

- `entry_feedback` — the promoted entry must reach a trust bar via
  `hermescube_feedback` ratings before the horizon (else `expired`;
  superseded → `refuted`).
- `witness_absence` — a friction pattern must NOT recur in the witness
  log before the horizon (recurrence → `refuted`).

### 4. Anti-collusion critic

`run_critic` is **mechanical** — pure heuristics over the ledgers, no LLM,
so it cannot share the model's blind spots (the same anti-collusion goal
the original harness achieves with model diversity). It flags:

- `bookkeeping_theatre` — ≥3 consecutive maintenance-only cycles while
  witnesses sit unaddressed
- `overdue_predictions` — open predictions past their horizon
- `failing_cycles` — repeated evolve failures

Verdicts append to `memories/harness/critiques.jsonl`.

### 5. Gardener surfaces, never deletes

`run_gardener` scans durable memories (durable / crystal / procedure) for
dormancy — old and low-trust — and writes proposals to
`memories/harness/gardener_report.json`. Archival happens only through
the existing consent-gated supersession path. Anti-entropy without
destruction.

## Where it runs

- **Session end** (automatic): grounded evolve + verifier + critic run on
  the background queue — the in-Cube equivalent of the harness's cron
  loops, firing every time a session closes.
- **Cron** (optional, recommended for gardener):

```bash
hermescube harness status                 # roll-up: witnesses, cycles, predictions, last critique
hermescube harness witness --desc "..."   # log real friction manually
hermescube harness critic                 # run the mechanical critic now
hermescube harness verify                 # settle open predictions
hermescube harness gardener               # dormancy report (proposals only)
```

- **In-session** (agent tools):

```
hermescube_manage action=witness content="search missed an obvious past session" severity=high
hermescube_manage action=harness harness_action=status|critic|verify|gardener
```

## Relationship to the original harness

| hermes-self-evolution | HermesCube equivalent |
|---|---|
| `facts/witness-log.md` (operator-populated) | `witness_log.jsonl` — auto-detected + manual, sanitized |
| Evolution cron citing witness anchors | `run_grounded_evolve` wrapping branched consolidation |
| No `[SILENT]` — every cycle reports | `evolution_cycles.jsonl` append-only, no-ops included |
| `facts/predictions.md` + Verifier cron | `predictions.jsonl` + `verify_predictions` (auto at session end) |
| Critic on a diverse model | Mechanical critic — zero LLM, zero collusion surface |
| Gardener surfacing dormant skills | `run_gardener` — proposals only, consent-gated archival |
| Constitution (Articles I–VI) | Rules enforced in code paths, not prose |

The two remain complementary: the external harness governs the *whole
Hermes instance* between sessions with LLM-driven cycles; the Cube's
built-in harness keeps the *memory layer itself* honest with mechanical
guarantees. Operators running both get witness data flowing from the same
place the memories live.
