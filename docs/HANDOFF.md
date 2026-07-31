# Agent handoff — continuity when the agent breaks

> “the model isn't the bottleneck. the handoff is.”  
> — [@MichaelGannotti](https://x.com/michaelgannotti/status/2082885191153168780)

HermesCube stores a **continuity packet** any agent on this `HERMES_HOME` can open, take, and complete. Not a full transcript — a sealed brief: goal, next steps, blockers, files, cube evidence.

## Layout

```text
$HERMES_HOME/memories/handoffs/
  open/<id>.json
  archive/<id>.json
  ledger.jsonl
```

## Blackbox holds the line

Every open / take / complete is **also sealed into the blackbox**:

```text
$HERMES_HOME/memories/blackbox/
  handoff-line.jsonl          # append-only stream (no cube needed)
  handoffs/<id>-<event>-*.json  # integrity-hashed flight records
```

If `memory.cube` is damaged:

```bash
hermescube handoff line              # read the hold-the-line stream
hermescube handoff recover           # rebuild open/*.json from blackbox
```

Cube landmarks still record handoffs when healthy — blackbox is the **independent** continuity rail.

## Terminal

```bash
hermescube handoff open --goal "Finish blackbox prove path" \
  --next "run tests; push docs" --files "hermescube/blackbox/prove.py" \
  --agent ilo --severity high

hermescube handoff list
hermescube handoff take --id ho_… --agent next-agent
hermescube handoff complete --id ho_… --note "Shipped"
hermescube handoff status
```

## Agent tool

`hermescube_handoff` actions: `open` · `list` · `take` · `complete` · `abandon` · `status`

Injected into system prompt when open packets exist (via `agent_manual`).

## Automatic

On **session end**, if the last exchange looks like unfinished task work, Cube **auto-opens** a high-severity handoff so a crash still leaves a 3am page.

## Flow

```
Agent A working → opens handoff (or auto on death)
Agent B connects to same HERMES_HOME
  → sees <agent-handoff> strip
  → take → work → complete
```

Fleet HQ handoffs (`hermescube hq handoff`) remain for multi-lane org chart.  
**This module is for any single home / any agent crash continuity.**
