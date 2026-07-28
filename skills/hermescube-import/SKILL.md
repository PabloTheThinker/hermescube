---
name: hermescube-import
description: >-
  Bootstrap HermesCube from existing hot memories. Use when the cube is empty,
  the user says "import my memories", "start the warehouse", "seed hermescube",
  or the system prompt shows needs_import / bootstrap hint.
version: 0.43.0
author: PabloTheThinker
license: MIT
origin: hermescube-bundled
platforms: [linux, macos]
metadata:
  hermes:
    category: memory
    tags: [hermescube, bootstrap, import, MEMORY.md, onboarding]
---

# hermescube-import

## When to use

- Fresh HermesCube install / empty `memory.cube`  
- User asks to import or seed memories into the warehouse  
- System prompt shows **Start here** / `needs_import` / bootstrap hint  
- Moving from MEMORY.md-only to Cube + MEMORY.md layered memory  

## Procedure

### 1. Check readiness

```
hermescube_manage action=bootstrap mode=status
```

Read: `hot_files`, `needs_import`, `skills_missing`, `hint`.

### 2. Seed warehouse + skills (one call)

```
hermescube_manage action=bootstrap mode=all
```

This will:

1. Install bundled skills (`hermescube-operate`, `hermescube-import`, `interview-me`) into `$HERMES_HOME/skills/`  
2. Parse `MEMORY.md`, `USER.md`, `SOUL.md` (when present) into durable cube entries  
3. Skip duplicates (idempotent) and block injection / credential-shaped lines  

### 3. Confirm

```
hermescube_search query="what do we know about the user"
```

Or re-check:

```
hermescube_manage action=bootstrap mode=status
```

### 4. Optional force re-import

Only if the user explicitly wants a refresh after large MEMORY.md edits:

```
hermescube_manage action=bootstrap mode=import
```

(Use content/mode args: `mode=import` with `force` via `mode=import:force` if offered.)

## Modes

| mode | Job |
|------|-----|
| `status` | Readiness card only |
| `import` | Hot markdown → cube |
| `skills` | Install bundled Cube skills |
| `all` | skills + import (default for first run) |

## Safety

- Does **not** wipe the cube  
- Does **not** overwrite MEMORY.md  
- Threat-scanned; blocked lines are counted, not stored  
- Secrets / injection patterns are skipped  

## After import

Switch to **hermescube-operate** for day-to-day search, feedback, triage, and Cuboasis review.
