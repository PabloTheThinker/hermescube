# Batched long-term memory (sync cadence)

**Problem:** Writing every agent turn into the cube burns disk I/O, evolve pressure, and can feel like “memory eating the turn.”

**Policy (default):** durable turns **buffer**, then **upload in batches**.

| Trigger | Behavior |
|---------|----------|
| Every **10** assistant messages | Flush buffer → cube (`sync_turn_interval`) |
| **Session end** | Always flush (then digest / dream-adjacent work) |
| **Shutdown** | Always flush |
| **Dream** | Operates on already-flushed warehouse; session_end flush first |
| User “remember this” | Immediate flush |
| High-severity witness / hard failure | Immediate flush |
| Buffer ≥ **25** | Forced flush (`sync_buffer_max`) |

Prefetch (read into context) is **separate** and stays capped. This policy is about **writes**.

## Config (`plugins.hermescube` in config.yaml)

```yaml
plugins:
  hermescube:
    sync_turn_interval: 10   # 0 = every turn (legacy)
    sync_buffer_max: 25
```

Or:

```bash
hermes config set plugins.hermescube.sync_turn_interval 10
```

Restart gateway/Desktop after changing provider config.

## Mental model

```
turn → (durable?) → buffer
                      │
         every 10 AI msgs ──► cube book
         session end ─────────► cube book + digest/pulse
         dream ───────────────► chapter bind on book already written
```

Hot MEMORY.md remains the sticky-note path (agent memory tool). Cube is the library stacks on a schedule.
