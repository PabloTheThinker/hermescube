# Fleet HQ — clear ownership for 1, 100, or a million agents

> "More agents aren't the upgrade. Clearer ownership is."

The Hive gave agents a place to pool experience. HQ makes that place the
**command layer of a real fleet**. It encodes the hard-won rules of
production multi-agent systems — one command surface, permanent specialist
ownership, disposable subagents, curated context, privilege at the top,
verification, recoverable baselines — as executable structure, not prose.

```
                         HIVE ROOT (= FLEET HQ)
       ┌──────────────────────────────────────────────────────┐
       │  hive.cube       collective distilled memory          │
       │  agents/*.json   soul cards (who each agent is)       │
       │  charters/       WHO OWNS WHAT (role, lane, bounds)   │
       │  routing.json    explicit overrides (audited)         │
       │  handoffs.jsonl  work moving between lanes            │
       │  claims/         task ownership leases                │
       │  baseline.json   frozen control-plane snapshot        │
       └──────────────────────────────────────────────────────┘
```

## Charters: ownership, not personality

A permanent agent exists because it **owns a durable lane of work** — not
because the role sounds cool. A charter records exactly that:

```bash
hermescube hq charter --hive /shared/hq --agent rza --role command \
  --lane "orchestration, routing, approvals, final synthesis" \
  --keywords "routing,approval,synthesis" \
  --boundaries "owns external credentials; owns publishing"

hermescube hq charter --hive /shared/hq --agent masta-killa \
  --lane "coding, debugging, testing, releases" \
  --keywords "coding,debugging,testing,release,refactor"
```

Retiring keeps history but stops routing immediately — history can mention
ghosts; your routing layer can't send them work:

```bash
hermescube hq retire --hive /shared/hq --agent gza
```

## Routing: the orchestrator owns the outcome

```bash
hermescube hq route --hive /shared/hq --task "debugging the failing release tests"
# Owner: masta-killa  (via lane:debugging,testing,release)
```

Resolution order: explicit overrides (audited for ghosts) → lane keyword
match → **command fallback**. Small tasks don't summon a committee; work
that matches no lane goes to the command charter, because the orchestrator
owns the outcome even when no specialist owns the lane.

In-session, any agent can ask:

```
hermescube_manage action=hq hq_action=route content="deep research on competitors"
```

And every chartered agent's system prompt carries a **lane strip**: its
lane, its boundaries, and where other work goes — so specialists hand off
instead of quietly doing everything.

## Work flows upward; privilege does not flow down

Enforced in the provider, not suggested in a prompt:

- **Subagents get read-only memory tools** — `search`, `probe`, `feedback`.
  No `manage`: no durable writes, no hive, no HQ ops. A subagent that tries
  gets a boundary error telling it to return findings to its parent.
- Durable writes, promotions, pilgrimages, and charters belong to the
  parent/command context, where the consent gates already live.

## Handoffs carry context, claims prevent turf wars

- `build_handoff_packet(cube, task)` distills task-relevant **evidence**
  (typed, quoted, provenance-tagged) for a delegation — the right context,
  not the whole history, not nothing. Delegations are recorded in the
  handoff ledger automatically.
- `claim_task` takes a lease on a task key; a second agent claiming the
  same task gets a conflict with the current owner's name. No more two
  agents both thinking the task belongs to them.

## Verification: never trust one green status light

```bash
hermescube hq verify --hive /shared/hq
```

Flags, mechanically:

| Flag | Meaning |
|---|---|
| `ghost_route` | routing override targets a retired/unknown agent |
| `lane_conflict` | one keyword owned by two active charters |
| `no_command` | nobody owns outcomes |
| `uncharted_soul` | an agent uploads to the hive but owns no lane |
| `stuck_handoff` | pending handoff older than 48h |

Exit code is non-zero when flagged — cron it next to the pilgrimage.

## Baselines: production ready means recoverable

```bash
hermescube hq freeze   # snapshot charter hashes + routing hash + collective stats
hermescube hq drift    # prove what changed since the freeze
```

"It works right now" isn't enough. The baseline answers: can I verify
drift after an update, and can I prove what changed?

## Scaling story

Everything is content-hashed, append-only, and file-per-agent: 1 agent is
a directory; 100 agents are 100 charter files and one collective cube; a
million agents shard the same layout across hive roots (e.g. per team/
region) that pilgrimage upward into a parent hive — the same OFFER/
ASSIMILATE/DRAW cycle composes, because a hive's collective cube is
itself offerable.

## Where each layer lives

| Concern | Layer |
|---|---|
| Who am I, what have I lived | agent's private cube (isolated memory) |
| What does the fleet know | `hive.cube` (shared truth, quarantined draws) |
| Who owns what | `charters/` + `routing.json` |
| What work moved where | `handoffs.jsonl` + `claims/` |
| Is the control plane sane | `hq verify` |
| Can we rebuild it | `baseline.json` + `hq drift` |
