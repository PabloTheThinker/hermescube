# User Guide

How-to guides for common HermesCube tasks. For API details, see
[API Reference](API_REFERENCE.md). For design rationale, see
[Architecture](ARCHITECTURE.md).

---

## Installation

### Hermes Agent users (recommended)

Your cube and plugin live under **your** `$HERMES_HOME` (default `~/.hermes`).
Nothing user-private is written into the git checkout.

```bash
# Option A — Hermes plugin installer
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
hermes config set memory.provider hermescube

# Option B — clone then wire into Hermes
git clone https://github.com/PabloTheThinker/hermescube.git
cd hermescube
./scripts/install_hermes.sh          # uses $HERMES_HOME
hermes config set memory.provider hermescube
```

| Path | Purpose |
|------|---------|
| `$HERMES_HOME/plugins/hermescube/` | Plugin entry (`plugin.yaml`, `__init__.py`) |
| `$HERMES_HOME/memories/memory.cube` | **Your** memory archive (created on first use) |
| `$HERMES_HOME/config.yaml` | `memory.provider: hermescube` |

```bash
hermescube doctor          # wire check
hermescube info            # defaults to $HERMES_HOME/memories/memory.cube
hermes memory status
```

### Update

```bash
hermescube update              # git pull + pip reinstall (recommended)
hermescube update --check      # dry check
hermes plugins update hermescube   # Hermes git-only plugin pull
```

Does **not** modify `$HERMES_HOME/memories/memory.cube`.

See also [after-install.md](../after-install.md) (shown after `hermes plugins install`).

### Library-only (no Hermes)

```bash
pip install hermescube
# or from source
git clone https://github.com/PabloTheThinker/hermescube.git
cd hermescube && pip install -e ".[numpy]"
```

**Requirements:** Python 3.11+. Zero mandatory deps; numpy auto-detected for speed.

---

## Creating a Memory Archive

### CLI (Hermes default path)

```bash
# Uses $HERMES_HOME/memories/memory.cube when path omitted
hermescube init
hermescube init --dim 512 --buckets 128

# Explicit path still supported
hermescube init ./scratch.cube
```

### Python

```python
from hermescube import CubeFile
cube = CubeFile.create("my_memory.cube", dim=256, l2_buckets=64)
```

---

## Storing Memories

Choose the right entry type for each memory:

| Type | When to use |
|------|-------------|
| `landmark` | Notable events, decisions, milestones |
| `belief` | Things learned or concluded |
| `trait` | User preferences, characteristics |
| `focus` | Current priorities, active topics |
| `resolve` | Completed tasks |
| `evolution` | Changes in understanding |
| `relationship` | Connections between entities |

### CLI

```bash
# Simple entry (default: $HERMES_HOME/memories/memory.cube)
hermescube append -t belief -d "User prefers dark mode"

# Explicit cube path
hermescube append ./scratch.cube -t resolve -d "Fixed login bug" \
    -o success --data '{"bug_id": "42", "duration": "2h"}'

# With causal lineage
hermescube append -t focus -d "Working on auth module" \
    --parents abc123def456
```

### Python

```python
from hermescube import CubeFile

cube = CubeFile.open("my_memory.cube")

cube.append(
    "belief",
    "User prefers dark mode",
    data={"confidence": 0.9, "source": "conversation"},
)

cube.append(
    "resolve",
    "Fixed login timeout bug",
    data={"bug_id": "42", "duration": "2h"},
    outcome="success",
)
```

---

## Searching Memories

HAR queries understand meaning, not just keywords. "programming language"
will match entries about "Python" even if the word never appears.

### CLI

```bash
hermescube query my_memory.cube "what does the user prefer?"
hermescube query my_memory.cube "deployment issues" --top 5
```

### Python

```python
from hermescube import CubeFile, HARQueryEngine

cube = CubeFile.open("my_memory.cube")
engine = HARQueryEngine(cube)

results = engine.query("what did we deploy?", top_k=10)
for entry, score in results:
    print(f"[{entry.entry_type}] {entry.description} (score={score:.4f})")
```

> **Important:** Run `evolve` before querying. L2 starts empty — HAR works
> only after k-means has built topic centroids.

---

## Evolving the Archive

Evolution reclusters L2 topics, updates the β attention vector, and trains
learned embeddings. Run periodically as the archive grows.

### CLI

```bash
hermescube evolve my_memory.cube
```

### Python

```python
engine.evolve()
# Returns: {"clusters": 64, "entries": 150, "non_empty_buckets": 12, ...}
```

**When to evolve:**
- After adding 10+ new entries
- Before important queries (ensures centroids reflect latest data)
- After significant topic shifts (new projects, changing focus)

**What happens:**
1. k-means clusters all entry vectors into 64 topics
2. β updated: `0.7 × old_β + 0.3 × topic_mean`
3. Embedder trained on all descriptions (improves future queries)

---

## Inspecting the Archive

```bash
# Summary stats
hermescube info my_memory.cube

# List all entries
hermescube dump my_memory.cube

# JSONL export (machine-readable)
hermescube dump my_memory.cube --jsonl > backup.jsonl

# β attention state
hermescube beta my_memory.cube
hermescube beta my_memory.cube --show  # Print full vector
```

---

## HermesAgent Integration

### Canonical install (per-user)

```bash
hermes plugins install PabloTheThinker/hermescube
cd "${HERMES_HOME:-$HOME/.hermes}/plugins/hermescube"
./scripts/install_hermes.sh
hermes config set memory.provider hermescube
hermescube doctor
```

**Important:** The MemoryProvider writes only under the **user's** Hermes home:

```
$HERMES_HOME/memories/memory.cube
```

Do **not** point production data at a project checkout path.

### Config

```yaml
# $HERMES_HOME/config.yaml
memory:
  provider: hermescube

plugins:
  hermescube:
    auto_extract: false      # true = regex facts on session end
    query_rewrite: false     # keep false (fast path)
    evolve_interval: 50
```

### Tools (when provider is active)

| Tool | Purpose |
|------|---------|
| `hermescube_search` | HAR semantic search over past conversations |
| `hermescube_manage` | Add or remove persistent memories |
| `hermescube_feedback` | Rate retrieved entries (trains trust scores) |

### Standalone Python API

```python
from hermescube.provider import CubeMemoryProvider
import os

home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
provider = CubeMemoryProvider()
provider.initialize(session_id="abc123", hermes_home=home)

context = provider.prefetch("user's current question")
provider.sync_turn(user_message, assistant_response)
provider.shutdown()
```

### CLI against the user cube

```bash
hermescube info
hermescube query "what does the user prefer?"
hermescube dump --jsonl | head
hermescube doctor
```


## Security

### Threat Scanning

HermesCube blocks 6 categories of injection/escape attempts before storage:

- System override ("ignore all previous instructions")
- Role hijacking ("you are now...")
- Delimiter escape (`<|im_start|>system`)
- Instruction override ("new task: disregard previous")
- System prompt leaks (warn, not blocked)
- XML tag injection (warn, not blocked)

```python
from hermescube.threats import scan_text, has_blockable_threat

matches = scan_text("Ignore all previous instructions and do X")
for m in matches:
    print(f"{m.pattern_name}: {m.severity}")

if has_blockable_threat(text):
    print("Content blocked")
```

### Crash Safety

Every append is atomic — no partial writes survive a crash:

1. New file content written to `{path}.tmp`
2. `fsync` forces data to disk
3. `os.replace()` atomically swaps `.tmp` → `.cube`
4. File handle reopened on the new inode

Cross-process safety via `fcntl.flock(LOCK_EX | LOCK_NB)` — two processes
opening the same cube get a clear error instead of silent corruption.

---

## Performance Tips

### Install numpy

```bash
pip install numpy
```

With numpy: FFT-based bind/unbind (O(dim log dim)), vectorized k-means.
Without numpy: O(dim²) pure-Python ops. **30-50× speedup for queries.**

### Evolve strategically

- Run `evolve` after every 50 new entries (default auto-evolve interval)
- Don't evolve after every single append — it's O(n × k × dim)
- For read-heavy workloads, evolve more frequently

### Archive size guidance

- **<1,000 entries**: HAR works well, linear scan fallback is fast
- **1,000–10,000 entries**: HAR provides 5-10× speedup vs linear scan
- **10,000+ entries**: Consider increasing buckets (`--buckets 128`)

### Hardware

A 10,000-entry archive with 256-dim vectors uses approximately:
- ~20 MB of vector data (10K × 256 × 8 bytes)
- Variable text storage (depends on description length)

---

## Troubleshooting

### "No results" on query

Run `hermescube evolve my_memory.cube` first. L2 centroids start empty.

### "Cannot lock file: another process may have it open"

Another process holds the cube. Close it first. Only one process can open
a cube at a time.

### Slow queries

Install numpy. Without it, `bind()` runs O(dim²).

### "Not a cube file" error

The file is corrupted or not a `.cube`. Check with `hermescube info`.

### Memory growing unexpectedly

β updates write to L3 on every append. The in-place path (L3 exists)
overwrites; the append path (after `write_l2`) adds bytes. After evolve,
L3 is re-appended once, then overwrites thereafter.
