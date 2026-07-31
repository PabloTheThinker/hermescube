# Hold the line — one blackbox rail for all of HermesCube

If `memory.cube` is damaged, **this stream still has the spine**.

```text
$HERMES_HOME/memories/blackbox/
  hold-the-line.jsonl     # unified append-only SoT
  seals/<organ>-*.json    # integrity-hashed flight seals
  handoff-line.jsonl      # handoff mirror (compat)
  handoffs/               # legacy handoff flights
```

## Organs sealed

| Organ | When |
|-------|------|
| **cube** | Critical appends: resolve, belief, trait, focus, relationship, evolution, [HANDOFF…] |
| **handoff** | open / take / complete / abandon |
| **checkpoint** | ark create |
| **connect** | attach home to Cube |
| **security** | audit |
| **flight** | session capture |
| **breathe** | full pulmonary cycle |
| **provider** | batched turn flush |
| **session** | session end |

## CLI

```bash
hermescube blackbox hold          # status + tail of unified line
hermescube handoff line           # handoff-only stream
hermescube handoff recover        # rebuild open packets from blackbox
```

## Design rule

**Cube = library book.**  
**Blackbox hold-the-line = flight data recorder for the whole organism.**

Not every chitchat landmark — only durable critical spine + explicit organ events.
