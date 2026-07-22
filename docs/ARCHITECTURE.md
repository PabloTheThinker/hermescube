# Architecture

Design rationale, data flow, and algorithmic choices in HermesCube.

---

## Design Philosophy

HermesCube is built on three principles:

1. **Append-only is the only safe write pattern.** Entries are never deleted
   or modified in-place. Superseded entries are marked, not removed. This
   eliminates whole classes of corruption and makes crash recovery trivial.

2. **Semantic search beats keyword search for memory.** Agent conversations
   are about meaning, not exact words. HRR vectors capture compositional
   semantics without requiring an embedding API.

3. **The system should improve with use.** Learned embeddings train on
   accumulated data. k-means refines incrementally. β tracks attention
   drift. Every evolve cycle makes retrieval better.

---

## The .cube Binary Format

A `.cube` file is a single binary with three contiguous layers:

```
┌──────────────────────────────────────────┐
│ HEADER (40 bytes)                        │
├──────────────────────────────────────────┤
│ L1 — Entry Log (append-only)             │
│   Entry 0: [header 36B | desc | data |   │
│             parents | vector 2048B]      │
│   Entry 1: ...                           │
│   Entry N: ...                           │
├──────────────────────────────────────────┤
│ L2 — Topic Index (rewritten on evolve)   │
│   bucket_count (4B)                      │
│   Bucket 0: [centroid 2048B | count 4B | │
│              entry_ids… | terms…]        │
│   Bucket 1: ...                          │
├──────────────────────────────────────────┤
│ L3 — β Vector (256 × f64 = 2048B)       │
└──────────────────────────────────────────┘
```

### Header (40 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | magic | `b"CUBE"` |
| 4 | 4 | version | uint32 LE, currently 1 |
| 8 | 4 | dim | uint32 LE, vector dimension |
| 12 | 8 | entry_count | uint64 LE |
| 20 | 4 | l2_bucket_count | uint32 LE |
| 24 | 8 | l1_data_size | uint64 LE, bytes of L1 |
| 32 | 8 | l3_offset | uint64 LE, byte offset to L3 |

### L1 — Entry Record

Each entry is a fixed-size header (42 bytes) followed by variable-length fields
and a 256-dim f64 vector:

```
[id: 12B][timestamp: 16B][type: 1B][outcome: 1B]
[desc_len: 4B][data_len: 4B][causal_count: 4B]
[description: desc_len bytes UTF-8]
[data: data_len bytes UTF-8 JSON]
[causal_parents: causal_count × 12 bytes each]
[vector: dim × 8 bytes f64 LE]
```

Total entry size: `42 + desc_len + data_len + causal_count × 12 + dim × 8`

### L2 — Topic Index

64 buckets by default. Each bucket:

```
[centroid: dim × f64 LE]
[entry_count: uint32 LE]
[entry_ids: entry_count × 12 bytes]
[terms_len: uint16 LE]
[terms: terms_len bytes UTF-8, comma-separated]
```

L2 is empty (all zero centroids) until the first `evolve()`.

### L3 — β Vector

```
[beta: dim × f64 LE]
```

---

## HRR Algebra

Holographic Reduced Representations (Plate 1995) are a vector symbolic
architecture. They encode compositional structure into fixed-width
distributed representations.

### Why HRR?

Alternatives considered:

| Approach | Pros | Cons |
|----------|------|------|
| Embedding API (OpenAI, Cohere) | Perfect semantics | Network latency, cost, privacy |
| Local embedding model | Good semantics, local | 100MB+ model download, GPU recommended |
| TF-IDF / BM25 | Simple, fast | No semantic understanding |
| **HRR** | **Zero-deps, compositional, local** | **Approximate semantics** |

HRR gives compositional semantics without a model download. `bind(user, prefers_python)`
produces a vector dissimilar to both inputs — perfect for associative memory.

### Operations

**`embed_text(text)`** — Deterministic hash embedding:
- Extract `[a-z0-9_]+` tokens from lowercased text
- For each token: SHA-256 → uint16 pairs → index ±1 into vector
- For each bigram: SHA-256 → index +1
- Normalize to unit length

**`bind(a, b)`** — Circular convolution:
- With numpy: `ifft(fft(a) * fft(b)).real` — O(dim log dim)
- Without numpy: nested loops — O(dim²)

**`superpose(vectors)`** — Sum + normalize. Capacity: O(sqrt(dim)) ≈ 16 items
for dim=256 before similarity degrades.

### Backend Selection

```python
try:
    import numpy as _np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False
```

Every operation checks `has_numpy()` and dispatches to the appropriate
implementation. The pure-Python path is identical in output but slower.

---

## HAR Query Protocol

Holographic Associative Retrieval is the core retrieval algorithm.

### Algorithm

```
query(text, top_k):
  1. q = embed_text(text)  or  embedder.embed_query(text)
  2. qβ = bind(q, β)              # bind with attention state
  3. scored = []
     for each bucket in L2:
       score = cosine_sim(qβ, bucket.centroid)
       if score > min_score:
         scored.append((score, bucket))
  4. top_buckets = sort(scored, reverse)[:max(3, top_k/2)]
  5. results = []
     for score, bucket in top_buckets:
       for eid in bucket.entry_ids:
         entry = read_entry(eid)
         recency = exp(-age_hours / 48)  # exponential time-decay
         results.append((entry, score * recency))
  6. if max(scored) < 0.3:            # low confidence fallback
     return linear_scan(text, top_k)
  7. return sort(results, reverse)[:top_k]
```

### Why bind with β?

β acts as the agent's "attention state" — it captures what the agent has been
focusing on. Binding the query with β means the search considers not just
"what matches the query" but "what matches the query *in the context of what
the agent cares about*."

β evolves over time:
- **On append:** `β = normalize(β + 0.1 × entry_vector)` — light nudge
- **On evolve:** `β = normalize(0.7 × β + 0.3 × topic_mean) × 0.995` — blend + decay

### Recency Weighting

```python
weight = exp(-age_hours / 48.0)
```

Exponential decay with 48-hour half-life. Recent entries get weights near 1.0;
week-old entries get ~0.2; month-old entries get ~0.02.

---

## K-Means Clustering

### Initialization

**k-means++** — selects centroids with probability proportional to squared
distance from nearest existing centroid. Uses deterministic SHA-256 hashing
for reproducibility (no process-global RNG dependence).

### Incremental Refinement

When centroids already exist (from a previous evolve), a single refinement
iteration runs instead of full k-means++ + 3 iterations. This is significantly
faster for large archives.

```python
if has_populated and len(existing_centroids) == k:
    centroids = kmeans_iteration(vecs, existing_centroids, k)
else:
    centroids = kmeans_init(vecs, k)
    for _ in range(3):
        centroids = kmeans_iteration(vecs, centroids, k)
```

### When entries < k

If fewer entries than clusters exist, centroids are padded with noise:
`normalize(existing + randn() × 0.01)`. The seed is deterministic from input
vectors.

---

## Learned Embeddings

### Problem

Hash-based embedding has no notion of semantic similarity. "Python" and
"programming language" produce unrelated vectors.

### Solution

TF-IDF + random projection trained on accumulated descriptions:

1. Build vocabulary from all descriptions (filter by document frequency)
2. Compute IDF weights: `log(N / (1 + df))`
3. Generate random projection matrix: vocab_size × dim
4. To embed: TF-IDF weight each token, multiply by projection row, average

### Training

Trains during `evolve()`. Needs ≥2 descriptions. With numpy, uses Gaussian
random projection (better quality). Without, uses sparse binary projection.

### Persistence

Saved atomically to `{cube_dir}/memory.embedder`. Format:
```
[HEMB][meta_len: 4B][JSON metadata][projection: vocab × dim × f64 LE]
```

Corrupt files are quarantined to `{path}.corrupt.{timestamp}`.

---

## Concurrency & Crash Safety

### In-Process: `threading.RLock()`

All public methods on `CubeFile` acquire the instance RLock. Guards against
concurrent append/read from multiple threads. The lock is reentrant so
`read_l1()` called from within `append()` (for the cache) doesn't deadlock.

### Cross-Process: `fcntl.flock(LOCK_EX | LOCK_NB)`

Acquired on `open()`/`create()`, released on `close()`. Non-blocking —
raises `RuntimeError` if another process holds the lock. The kernel
automatically releases the lock if the process crashes.

### Atomic Append

The old approach (in-place shift + write + header update) had multiple
crash windows. The current approach is atomic by construction:

1. Read entire existing file
2. Write new file content (header + existing L1 + new entry + L2/L3 tail)
   to `{path}.tmp`
3. `fsync` the `.tmp` file
4. Close old fd, `os.replace(.tmp → .cube)`, reopen
5. On failure, `.tmp` is cleaned up

`os.replace()` is atomic on the same filesystem — the file either exists
in its old state or its new state, never in between.

### `write_l2` Safety

L2 rewrites (during evolve) use a deliberate ordering:
1. Write new L2 data
2. Capture L2 end position
3. Update header with `l3_offset = 0` (invalidates L3)
4. `flush`
5. `truncate` at L2 end (discards old L3)
6. `fsync`

Step 3-4 before step 5 prevents a crash window where `l3_offset` points
past the truncated file. Subsequent `write_l3` will re-append β.

---

## Provider Architecture

`CubeMemoryProvider` implements the HermesAgent `MemoryProvider` ABC.

### Frozen Snapshot Pattern

At `initialize()`, β and L2 centroids are captured as a `_FrozenSnapshot`.
All `prefetch()` calls use this snapshot — never the live cube state.
This prevents mid-session drift from background sync tasks and avoids
races with concurrent writer threads.

### Background Sync Queue

All writes route through `_SyncQueue` — a single-threaded executor that
serializes mutations. The agent turn returns immediately; the sync task
runs on a daemon thread.

### Context Awareness

| `agent_context` | Writes? | Purpose |
|-----------------|---------|---------|
| `"primary"` | Yes | Normal agent sessions |
| `"subagent"` | No | Delegated sub-tasks |
| `"cron"` | No | Scheduled jobs (system prompts would corrupt user memory) |
| `"flush"` | No | Cleanup-only runs |
| `skip_memory=True` | No | Explicit opt-out |

### Circuit Breaker

Evolve operations can be expensive. After 3 consecutive failures, the
circuit breaker opens for 5 minutes. This prevents repeated expensive
failures from hammering the system.

---

## Data Flow

### Turn Lifecycle

```
User message
  │
  ├─► prefetch(user_msg)         # HAR recall → inject context
  │     uses frozen snapshot
  │
  ├─► LLM call                   # Agent thinks + responds
  │
  └─► sync_turn(user, assistant) # Background write
        ├─ threat scan
        ├─ sanitize
        ├─ classify turn type
        └─ _SyncQueue.submit
              ├─ cube.append()       # Atomic write
              ├─ update_beta_on_append()  # Light β update
              ├─ entries_since_evolve += 1
              └─ if threshold: evolve_consolidated()
                    ├─ engine.evolve()     # k-means + β update
                    ├─ save embedder
                    ├─ _deduplicate_entries()
                    └─ _refresh_snapshot()
```

### Session Lifecycle

```
initialize()
  ├─ resolve cube path (per-profile)
  ├─ open or create cube
  ├─ load embedder from disk
  └─ capture frozen snapshot

[ turns run... ]

on_session_end()
  ├─ auto_extract_facts() (if enabled)
  ├─ evolve_consolidated() (if not breaker-open)
  ├─ _refresh_snapshot()
  └─ _sync_queue.flush()

shutdown()
  ├─ save embedder
  ├─ _sync_queue.flush()
  └─ cube.close()
```
