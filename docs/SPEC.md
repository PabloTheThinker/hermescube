# HermesCube Specification v0.1

HermesCube is a standalone memory project — a binary columnar archive with
holographic associative retrieval. Designed for persistent agent memory that
grows forever without pruning, decay, or capping.

---

## 1. Overview

HermesCube stores entries in a **`.cube`** binary file with three layers:

| Layer | What | Access pattern |
|-------|------|----------------|
| **L1** | Append-only entry log (exact text, timestamps, types) | Sequential replay, ID lookup |
| **L2** | Compressed topic index (64 term-bucket centroids) | Fast topic match for queries |
| **L3** | HRR β vector (256-dim, agent's attention state) | Session continuity, query binding |

Queries use **HAR (Holographic Associative Retrieval)**:
1. Hash-embed query text → 256-dim vector `q`
2. Bind `q` with the β vector → `qβ = hrr.bind(q, β)`
3. Cosine-match `qβ` against L2 topic centroids
4. Retrieve L1 entries for the best-matching topics
5. Rank by combined centroid score + recency

---


### Hermes Agent deployment (normative for end users)

When used as a Hermes memory provider:

| Artifact | Location |
|----------|----------|
| Plugin code | `$HERMES_HOME/plugins/hermescube/` |
| Cube file | `$HERMES_HOME/memories/memory.cube` |
| Activation | `memory.provider: hermescube` in `$HERMES_HOME/config.yaml` |

Install: `hermes plugins install PabloTheThinker/hermescube` then `./scripts/install_hermes.sh`.

## 2. `.cube` Binary Format

### 2.1 Overall Layout

```
┌─────────────────────────────────────────────┐
│ HEADER (fixed 32 bytes)                     │
├─────────────────────────────────────────────┤
│ L1 — Entry log (append-only)                │
│  ┌──────────────────────────────────────┐   │
│  │ Entry header (36 bytes fixed)        │   │
│  │ Description (variable, UTF-8)        │   │
│  │ Data blob (variable, JSON UTF-8)     │   │
│  │ Causal parents (variable, 12B each)  │   │
│  │ Entry vector (dim×8 bytes, f64 LE)   │   │
│  └──────────────────────────────────────┘   │
│  ... repeated for each entry                │
├─────────────────────────────────────────────┤
│ L2 — Topic index (rewritten on evolve)      │
│  ┌──────────────────────────────────────┐   │
│  │ Bucket count (4 bytes, uint32 LE)    │   │
│  │ For each of 64 buckets:              │   │
│  │   Centroid vector (dim×8 f64 LE)     │   │
│  │   Entry count (4 bytes, uint32 LE)   │   │
│  │   Entry IDs (count × 12 bytes)       │   │
│  │   Terms length (2 bytes, uint16 LE)  │   │
│  │   Terms (UTF-8, comma-separated)     │   │
│  └──────────────────────────────────────┘   │
├─────────────────────────────────────────────┤
│ L3 — β vector (overwritten on save)         │
│  ┌──────────────────────────────────────┐   │
│  │ Beta vector (dim×8 bytes, f64 LE)    │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 2.2 Header (40 bytes)

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | magic | `b"CUBE"` |
| 4 | 4 | version | uint32 LE, currently 1 |
| 8 | 4 | dim | uint32 LE, vector dimension (256) |
| 12 | 8 | entry_count | uint64 LE, total entries appended |
| 20 | 4 | l2_bucket_count | uint32 LE, bucket count (64) |
| 24 | 8 | l1_data_size | uint64 LE, byte size of L1 data section |
| 32 | 8 | l3_offset | uint64 LE, byte offset to L3 section |

### 2.3 L1 — Entry Record

Each entry has a fixed-size header followed by variable-length fields.

**Entry header (36 bytes):**

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 12 | id | ASCII hex, e.g. `"a1b2c3d4e5f6"` |
| 12 | 16 | timestamp | ASCII ISO, e.g. `"2026-07-19T12:00"` |
| 28 | 1 | entry_type | enum (see §2.4) |
| 29 | 1 | outcome | enum (see §2.5) |
| 30 | 4 | description_len | uint32 LE |
| 34 | 4 | data_len | uint32 LE |
| 38 | 4 | causal_count | uint32 LE (0 if none) |

Followed by variable data:
- **Description**: `description_len` bytes, UTF-8
- **Data**: `data_len` bytes, UTF-8 JSON
- **Causal parents**: `causal_count` × 12 bytes each (ASCII hex IDs)
- **Entry vector**: `dim` × 8 bytes, f64 LE (the HRR vector for this entry)

### 2.4 Entry Type Enum

| Code | Type |
|------|------|
| 0 | enter |
| 1 | leave |
| 2 | landmark |
| 3 | belief |
| 4 | trait |
| 5 | evolution |
| 6 | focus |
| 7 | epoch_transition |
| 8 | resolve |
| 9 | relationship |

### 2.5 Outcome Enum

| Code | Outcome |
|------|---------|
| 0 | none |
| 1 | success |
| 2 | failure |
| 3 | pending |
| 4 | superseded |

### 2.6 L2 — Topic Index

Rewritten by `evolve()`. 64 buckets by default.

```
bucket_count: uint32 LE (64)

For each bucket i:
  centroid: dim × f64 LE
  entry_count: uint32 LE
  entry_ids: entry_count × 12 bytes each (hex ASCII)
  terms_len: uint16 LE
  terms: terms_len bytes (UTF-8, comma-separated)
```

On `evolve()`, k-means reclusters all entry vectors into 64 centroids.
L2 is empty until the first `evolve()` call.

### 2.7 L3 — β Vector

```
beta: dim × f64 LE (2048 bytes for dim=256)
```

Loaded on `open()`, written on `evolve()` or explicit `save_beta()`.

---

## 3. HRR Algebra

All vectors are 256-dim float64. Operations use numpy when available,
pure-Python fallback otherwise.

### 3.1 `embed_text(text, dim=256)` → vector

Deterministic hash embedding (identical to Hermespace `neural_field.py:21`):

```
v = [0] * dim
toks = extract [a-z0-9_]+ tokens from text.lower()
for each token:
  h = SHA256(token)
  for i in (0, 2, 4, ...):
    idx = ((h[i] << 8) | h[i+1]) % dim
    sign = +1 if h[idx % len(h)] % 2 == 0 else -1
    v[idx] += sign
for each bigram (a, b):
  h = SHA256(a + "#" + b)
  idx = ((h[0] << 8) | h[1]) % dim
  v[idx] += 1.0
return normalize(v)
```

### 3.2 `bind(a, b)` → vector

Circular convolution (Plate 1995):

```
z[k] = sum_i a[i] * b[(k - i) % dim]
```

Implemented via FFT convolution theorem when numpy available:
```
return ifft(fft(a) * fft(b)).real
```

### 3.3 `unbind(c, b)` → vector

Approximate inverse of circular convolution:

```
c ≈ a ⊛ b
a ≈ c ⊛ b⁻¹  where b⁻¹[k] = b[(-k) % dim]
```

Via FFT:
```
return ifft(fft(c) * conj(fft(b))).real
```

### 3.4 Other ops

```
superpose(vectors) = normalize(sum(vectors))
cosine_sim(a, b) = dot(a, b) / (norm(a) * norm(b))
normalize(v) = v / norm(v)  (or zero vector if norm < 1e-12)
dot(a, b) = sum(a[i] * b[i] for i in range(dim))
norm(v) = sqrt(dot(v, v))
```

---

## 4. HAR Query Protocol

### 4.1 Query Flow

```
query(text, top_k=10):
  1. q = embed_text(text)                    # hash-embed query
  2. qβ = hrr.bind(q, β)                     # bind with attention state
  3. scores = []                              # match against L2 centroids
     for each bucket in L2:
       score = cosine_sim(qβ, bucket.centroid)
       if score > threshold (default 0.0):
         scores.append((score, bucket))
  4. top_buckets = sort(scores, reverse)[:max(3, top_k/2)]
  5. for score, bucket in top_buckets:
       for eid in bucket.entry_ids:
         entry = read_entry(eid)
         results.append((entry, score * recency_weight(entry)))
  6. deduplicate by entry.id
  7. sort by score, return top_k
```

### 4.2 β Update Strategy

**On append (online, light):**
```
β_new = normalize(β + 0.1 * entry_vector)
```
This gives basic session continuity. The 0.1 weight prevents any single
entry from dominating β.

**On evolve (batch, full):**
```
β_new = normalize(0.7 * β + 0.3 * topic_centroid_mean)
β_new = decay(β_new, 0.995)  # mild fade of old topics
```
Evolve also reclusters L2 centroids via k-means (3 iterations).

### 4.3 Fallback

If HAR confidence (max centroid score) < 0.3, fall back to linear scan:
```
for each entry in L1:
  score = cosine_sim(q, entry.vector)
rank by score, return top_k
```

---

## 5. CLI Interface

```
hermescube init <path>                  Create empty .cube file
hermescube info <path>                  Show entry count, size, bucket stats
hermescube append <path> --type <t>     Append an entry
  --desc "..." [--data '{"k":"v"}']
  [--parents id1,id2] [--outcome <o>]
hermescube query <path> <text>          HAR query, show top results
hermescube evolve <path>                Recluster L2, decay β
hermescube dump <path> [--jsonl]        Export all entries
hermescube beta <path> [--show]         Show β vector stats
```

---

## 6. Python API

```python
from hermescube.cube import CubeFile, CubeEntry
from hermescube.har import HARQueryEngine
from hermescube import hrr

# Create or open a cube
cube = CubeFile.open("memory.cube")
# or CubeFile.create("memory.cube")

# Append an entry
entry = cube.append(
    entry_type="belief",
    description="The agent prefers concise replies",
    data={"confidence": 0.8, "source": "experience"},
)
# (β updated automatically with 0.1 weight)

# Query
engine = HARQueryEngine(cube)
results = engine.query("how should I reply?", top_k=5)
for entry, score in results:
    print(entry.description, score)

# Evolve
engine.evolve()

# Direct β access
beta = cube.read_l3()
engine.update_beta(new_beta)
```
