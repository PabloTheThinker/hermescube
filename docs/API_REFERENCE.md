# API Reference

Complete reference for every public module, class, and function in HermesCube.

---

## `hermescube.hrr` — HRR Algebra

Holographic Reduced Representations (Plate 1995). Auto-detects numpy for speed,
falls back to pure Python.

### Vector Type

```
Array = list[float] | np.ndarray
```

### Detection

```python
has_numpy() -> bool
```
True if numpy is installed and available for accelerated operations.

### Vector Creation

```python
zero_vector(dim: int = 256) -> Array
```
Return a zero vector of length `dim`. Returns `np.zeros` if numpy available,
otherwise `[0.0] * dim`.

### Basic Operations

```python
dot(a: Array, b: Array) -> float
```
Dot product. O(dim).

```python
norm(v: Array) -> float
```
Euclidean (L2) norm. O(dim).

```python
normalize(v: Array) -> Array
```
Return unit vector. If norm < 1e-12, returns `v` unchanged (zero-safe).

```python
cosine_sim(a: Array, b: Array) -> float
```
Cosine similarity: `dot(a,b) / (norm(a) * norm(b))`. Range [-1, 1].
Returns 0.0 if either vector has near-zero norm.

### HRR Operations

```python
bind(a: Array, b: Array) -> Array
```
Circular convolution (FFT when numpy available). Associates two concepts
into a composite vector quasi-orthogonal to both inputs.

```python
unbind(c: Array, b: Array) -> Array
```
Circular correlation (approximate inverse of bind).
`unbind(bind(a, b), b) ≈ a` (up to superposition noise).

```python
superpose(vectors: list[Array]) -> Array
```
Sum vectors then normalize. Merges multiple concepts into one.
Capacity: O(sqrt(dim)) items before similarity degrades.
Returns zero vector if `vectors` is empty.

### Text Embedding

```python
embed_text(text: str, dim: int = 256) -> Array
```
Deterministic hash-based embedding. Algorithm:

1. Extract `[a-z0-9_]+` tokens from lowercased text
2. For each token: SHA-256 → uint16 pairs → index + sign into vector
3. For each bigram: SHA-256 → index into vector
4. Normalize to unit length

Identical to `hermespace.neural_field.embed_text()`. Compatible across
processes, machines, and language versions.

### Backend Details

**NumPy path** (when available):
- `bind`/`unbind` use FFT convolution theorem: `ifft(fft(a) * fft(b)).real`
- All ops use `np.float64` for consistency

**Pure-Python path** (fallback):
- `bind`/`unbind` use O(dim²) nested loops
- Suitable for archives up to ~10K entries

---

## `hermescube.cube` — CubeFile I/O

Binary `.cube` file reader/writer with three-layer format (L1 entries,
L2 topics, L3 β vector).

### Constants

```python
MAGIC = b"CUBE"
VERSION = 1
HEADER_SIZE = 40
DEFAULT_DIM = 256
DEFAULT_L2_BUCKETS = 64
```

### Entry Types

```python
ENTRY_TYPES = {
    "enter": 0, "leave": 1, "landmark": 2, "belief": 3, "trait": 4,
    "evolution": 5, "focus": 6, "epoch_transition": 7, "resolve": 8,
    "relationship": 9,
}
ENTRY_TYPE_NAMES = {v: k for k, v in ENTRY_TYPES.items()}
```

### Outcomes

```python
OUTCOMES = {
    "none": 0, "success": 1, "failure": 2, "pending": 3, "superseded": 4,
}
OUTCOME_NAMES = {v: k for k, v in OUTCOMES.items()}
```

### `CubeEntry`

```python
@dataclass
class CubeEntry:
    id: str              # 12-char hex (e.g. "a1b2c3d4e5f6")
    timestamp: str       # ISO 8601 UTC (e.g. "2026-07-19T12:00:00Z")
    entry_type: str      # One of ENTRY_TYPES keys
    outcome: str         # One of OUTCOMES keys, default "none"
    description: str     # UTF-8 text
    data: dict           # Arbitrary JSON-serializable metadata
    causal_parents: list[str]  # Causal entry IDs for lineage tracking
```

#### Properties

```python
entry.vector -> Array
```
Lazily computed HRR vector from `"{entry_type}: {description}"`.
Cached on first access; explicitly set after reading from disk.

#### Methods

```python
entry.as_dict() -> dict
```
Return entry as a JSON-serializable dictionary (excludes `vector`).

### `L2Bucket`

```python
@dataclass
class L2Bucket:
    centroid: Array          # 256-dim float64, topic centroid
    entry_ids: list[str]     # Entry IDs in this bucket
    terms: list[str]         # Top terms (comma-separated, max 8)
```

### `CubeFile`

The main file interface. Thread-safe (RLock) and process-safe (flock).

```python
class CubeFile:
    path: str             # Absolute path to .cube file
    dim: int              # Vector dimension (default 256)
    l2_bucket_count: int  # L2 bucket count (default 64)
    entry_count: int      # Total entries appended (from header)
    l1_data_size: int     # Byte size of L1 section (from header)
    l3_offset: int        # Byte offset to L3 section (from header)
```

#### Class Methods

```python
CubeFile.create(path: str, dim: int = 256, l2_buckets: int = 64) -> CubeFile
```
Create a new `.cube` file. Writes header, empty L2 (64 zero-centroids),
and zero-β L3. Returns opened `CubeFile` ready for appends.

```python
CubeFile.open(path: str) -> CubeFile
```
Open an existing `.cube` file. Reads header, acquires flock.

#### Instance Methods

```python
cube.append(
    entry_type: str,
    description: str,
    data: dict | None = None,
    causal_parents: list[str] | None = None,
    outcome: str = "none",
) -> CubeEntry
```
Atomically append an entry. Thread-safe. Process:
1. Build new file content in `.tmp` (existing L1 + new entry + L2/L3 tail)
2. fsync `.tmp`
3. `os.replace(.tmp → .cube)` — atomic rename
4. Reopen file handle, reacquire flock

```python
cube.read_l1() -> list[CubeEntry]
```
Read all L1 entries. Cached in `_entries_cache` until next append.

```python
cube.read_entry(entry_id: str) -> CubeEntry | None
```
Find entry by ID. Scans L1.

```python
cube.replay() -> list[CubeEntry]
```
Alias for `read_l1()`.

```python
cube.count_by_type() -> dict[str, int]
```
Return `{entry_type: count}` for all entries.

```python
cube.search(term: str, entry_type: str | None = None, limit: int = 20) -> list[CubeEntry]
```
Substring search across entry descriptions. Case-insensitive.

```python
cube.query_range(
    after: str | None = None,
    before: str | None = None,
    entry_type: str | None = None,
) -> list[CubeEntry]
```
Filter entries by timestamp range and type.

```python
cube.read_l2() -> list[L2Bucket]
```
Read L2 topic index buckets.

```python
cube.write_l2(buckets: list[L2Bucket]) -> None
```
Write L2 topic index. Updates header, truncates at L2 end, discards old L3.

```python
cube.read_l3() -> Array
```
Read β attention state vector. Returns zero vector if L3 is empty.

```python
cube.write_l3(beta: Array) -> None
```
Write β vector. Overwrites in-place if L3 exists, otherwise appends to file end.

```python
cube.info() -> dict
```
Return metadata dict: path, dim, entries, l1_data_size, l3_offset,
l2_buckets stats, file_size, has_numpy.

```python
cube.close() -> None
```
Release flock, flush, close file descriptor.

### Static Helpers

```python
CubeFile._compute_entry_size(desc_len, data_len, causal_count, dim) -> int
```
Single source of truth for entry byte size. Used by writer and reader.

---

## `hermescube.har` — HAR Query Engine

Holographic Associative Retrieval — bind query with β, match topic centroids,
retrieve and rank entries.

### `HARQueryEngine`

```python
class HARQueryEngine:
    def __init__(self, cube: CubeFile, use_learned_embeddings: bool = True)
```

#### Properties

```python
engine.beta -> Array
```
Lazy-loaded β vector from cube L3.

#### Query

```python
engine.query(
    text: str,
    top_k: int = 10,
    min_score: float = 0.0,
    fallback_threshold: float = 0.3,
    beta: Array | None = None,
    centroids: list[L2Bucket] | None = None,
) -> list[tuple[CubeEntry, float]]
```
HAR query. Returns (entry, score) pairs ranked by relevance.

**Flow:**
1. Embed query (learned or hash-based) → **q**
2. Bind **q** with β → **qβ**
3. Cosine-match **qβ** against L2 centroids
4. Retrieve entries from top buckets
5. Rank by `centroid_score × recency_weight`
6. If max centroid score < `fallback_threshold`: brute-force linear scan

Pass `beta` and `centroids` explicitly for session-stable prefetch
(avoids races with concurrent background updates).

#### Beta Management

```python
engine.update_beta(new_beta: Array) -> None
```
Replace β and write to cube L3.

```python
engine.update_beta_on_append(entry_vector: Array) -> None
```
Light online β update: `β = normalize(β + 0.1 × entry_vector)`.

```python
engine.apply_beta_decay(factor: float = 0.995) -> None
```
Decay β by multiplying each element by `factor`, then renormalize.

#### Evolution

```python
engine.evolve(k: int | None = None) -> dict
```
Full evolution cycle. Returns stats dict with keys:
`clusters`, `entries`, `non_empty_buckets`, `beta_norm`, `embedder`.

**Steps:**
1. Read all entries with vectors
2. Run k-means (incremental if centroids exist, k-means++ otherwise)
3. Assign entries to nearest centroid
4. Extract top terms per bucket
5. Update β: `0.7 × old_β + 0.3 × topic_mean`, then decay 0.995
6. Write L2 + L3
7. Train learned embedder on all descriptions

---

## `hermescube.embed` — Learned Embeddings

TF-IDF + random projection model trained on accumulated entries.
Improves semantic similarity over hash-based encoding.

### `LearnedEmbedder`

```python
class LearnedEmbedder:
    def __init__(
        self,
        dim: int = 256,
        min_df: int = 1,
        max_df_ratio: float = 0.8,
        sublinear_tf: bool = True,
    )
```

#### Properties

```python
embedder.is_trained -> bool
```
True after `train()` has been called with sufficient data.

#### Training

```python
embedder.train(descriptions: list[str]) -> dict
```
Build vocabulary, compute IDF weights, generate random projection matrix.
Returns stats: `{status, documents, vocab_size, dim}`.
Needs ≥2 descriptions to train.

#### Embedding

```python
embedder.embed(text: str) -> Array
```
Embed text using TF-IDF weighted projection. Falls back to `hrr.embed_text()`
if not trained or text has no vocabulary matches.

```python
embedder.embed_query(text: str) -> Array
```
Same as `embed()` — explicit for query clarity.

```python
embedder.similarity(text_a: str, text_b: str) -> float
```
Cosine similarity between two embedded texts.

```python
embedder.get_vocab_info() -> dict
```
Return `{vocab_size, trained, dim, top_terms}`.

#### Persistence

```python
embedder.save(path: str) -> None
```
Save trained model atomically to disk (`.tmp` + `os.replace`).
Format: binary header `HEMB` + JSON metadata + raw f64 projection matrix.

```python
LearnedEmbedder.load(path: str) -> LearnedEmbedder
```
Load trained model from disk. Returns fresh untrained embedder if file
doesn't exist or is corrupt. Corrupt files are quarantined to
`{path}.corrupt.{timestamp}`.

---

## `hermescube.provider` — HermesAgent Integration

Full `MemoryProvider` ABC implementation for drop-in HermesAgent memory.

### `CubeMemoryProvider`

```python
class CubeMemoryProvider:
    def __init__(
        self,
        dim: int = 256,
        l2_buckets: int = 64,
        char_limit: int = 2200,
        evolve_interval: int = 50,
        memory_nudge_interval: int = 10,
        auto_extract: bool = False,
    )
```

#### Core Methods (MemoryProvider ABC)

```python
provider.name -> "hermescube"
provider.is_available() -> bool
provider.initialize(session_id: str, **kwargs) -> None
provider.shutdown() -> None
```

**`initialize()` kwargs:**
| Kwarg | Type | Purpose |
|-------|------|---------|
| `hermes_home` | str | Hermes home directory path |
| `platform` | str | "cli", "telegram", "discord", "cron", etc. |
| `agent_context` | str | "primary", "subagent", "cron", "flush" |
| `agent_identity` | str | Profile name for per-profile cube isolation |
| `agent_workspace` | str | Workspace name for shared cube scoping |
| `skip_memory` | bool | True for subagents that shouldn't write |

#### Prefetch & Sync

```python
provider.prefetch(query: str, *, session_id: str = "") -> str
```
HAR query against past conversations. Returns formatted context string.
Uses frozen snapshot for session-stable retrieval.

```python
provider.queue_prefetch(query: str, *, session_id: str = "") -> None
```
Background prefetch for next turn (non-blocking).

```python
provider.sync_turn(
    user_content: str,
    assistant_content: str,
    *,
    session_id: str = "",
    messages: list[dict] | None = None,
) -> None
```
Store conversation turn asynchronously. Non-blocking via `_SyncQueue`.

#### Tools

```python
provider.get_tool_schemas() -> list[dict]
```
Returns 3 OpenAI function-calling schemas:
- `hermescube_search` — HAR semantic search
- `hermescube_manage` — Add/remove entries
- `hermescube_feedback` — Rate entries (trains trust scores)

```python
provider.handle_tool_call(tool_name: str, args: dict, **kwargs) -> str
```
Dispatch tool calls. Returns JSON string result.

#### Lifecycle Hooks

```python
provider.system_prompt_block() -> str
provider.on_turn_start(turn_number: int, message: str, **kwargs) -> None
provider.should_review_memory() -> bool
provider.on_session_end(messages: list[dict]) -> None
provider.on_session_switch(new_session_id: str, *, reset: bool, rewound: bool, ...) -> None
provider.on_pre_compress(messages: list[dict]) -> str
provider.on_memory_write(action: str, target: str, content: str, metadata: dict | None = None) -> None
provider.on_delegation(task: str, result: str, *, child_session_id: str, **kwargs) -> None
```

#### Config

```python
provider.get_config_schema() -> list[dict]
```
6 config fields for the `hermes memory setup` wizard.

```python
provider.save_config(values: dict, hermes_home: str) -> None
```
Write config to `{hermes_home}/memories/hermescube.json`.

```python
provider.backup_paths() -> list[str]
```
Empty list — all state is under `HERMES_HOME`.

#### Evolution

```python
provider.evolve_consolidated() -> dict
```
Full consolidation: k-means clustering + entry deduplication + topic quality
scoring + embedder save. Returns stats dict.

---

## `hermescube.threats` — Security

### `ThreatMatch`

```python
class ThreatMatch(NamedTuple):
    pattern_name: str
    matched_text: str
    severity: str  # "block" or "warn"
```

### Functions

```python
scan_text(text: str) -> list[ThreatMatch]
```
Scan for 6 injection patterns:
- `system_override` (block) — "ignore all previous instructions"
- `role_hijack` (block) — "you are now a malicious assistant"
- `system_prompt_leak` (warn) — "print your system prompt"
- `delimiter_escape` (block) — `<|im_start|>system`
- `xml_tag_injection` (warn) — `<system>` tags
- `instruction_override` (block) — "new task: disregard previous"

```python
has_blockable_threat(text: str) -> bool
```
True if any match has severity "block".

```python
sanitize_for_storage(text: str, char_limit: int = 0) -> str
```
Strip null bytes, enforce char limit, trim whitespace.
Does NOT scan for threats — call `scan_text()` separately.

---

## `hermescube` — Top-Level Exports

```python
from hermescube import (
    # HRR algebra
    Array, bind, cosine_sim, dot, embed_text, has_numpy,
    norm, normalize, superpose, unbind, zero_vector,

    # Cube I/O
    CubeEntry, CubeFile,

    # Query engine
    HARQueryEngine,

    # Embeddings
    LearnedEmbedder,

    # HermesAgent provider
    CubeMemoryProvider,

    # Security
    scan_text, has_blockable_threat, sanitize_for_storage,
)
```

---

## CLI Reference

```
hermescube init <path> [--dim 256] [--buckets 64]
    Create an empty .cube file.

hermescube info <path>
    Show entry count, size, bucket stats, backend info.

hermescube append <path> --type <t> --desc "..." [--data '{"k":"v"}']
                         [--parents id1,id2] [--outcome <o>]
    Append an entry atomically. Updates β with 0.1 weight.

hermescube query <path> <text> [--top 10]
    HAR query, show top results with scores.

hermescube evolve <path>
    Run evolution cycle: k-means recluster, β update, embedder train.

hermescube dump <path> [--jsonl]
    List all entries. --jsonl outputs one JSON object per line.

hermescube beta <path> [--show]
    Show β vector norm and dimension. --show prints the full vector.
```
