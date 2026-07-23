# Changelog

## [0.7.1] - 2026-07-23

### Purpose lock (Hermes clean v0.19 RE)
- PURPOSE.md — warehouse / extension-layer north star
- system_prompt_block: no full L1 scan on prompt assembly (init-path tax)
- Prompt states Hermes 0.19 layering + <memory-context> contract
- Research: HERMES-CLEAN-V019-RE-PURPOSE-2026-07-23.md
- Study tree: ~/projects/hermes-agent-study @ v2026.7.20

All notable changes to HermesCube are documented here.

## [0.7.0] - 2026-07-22

### Hermespace module integration
- `hermescube.space_bridge` — FOA inject strip + seal_to_cube + module_status
- Dense deep-memory for Space high-load (small char strip, not full archive)
- docs/HERMESPACE.md — architecture: Space desk + Cube warehouse
- Hermespace wires soft-import in hermes_bridge + remember_learning seal

## [0.6.3] - 2026-07-22

### Ship piece — install/update hardened
- `install_hermes.sh`: git-first layout, origin stamps, `--from-git`
- `update.sh`: pull via plugin git · source pin · or origin cache; rsync code only
- Never touches user `memory.cube` / colony data
- doctor reports ship layout path
- after-install.md rewritten for everyday ops

## [0.6.2] - 2026-07-22

### Hermes 0.19 RE + dense archive packing
- Align auto_extract with holo: skip compaction-summary "user" messages
- `density_stats` + `hermescube info` packing report
- `hermescube.dense` export/import gzip JSONL (zip-class text archive; live cube keeps vectors)
- Research: Hermes 0.19 memory batch + provider layering → Cube benefit

## [0.6.1] - 2026-07-22

### Day-to-day durability + MEMORY.md extension
- **sync_turn is WAL-sync** (append before return) — no async drop of chat
- **on_memory_write** mirrors MEMORY.md/USER.md into cube as durable extension
- system_prompt positions Cube as extension of hot memory, not replacement
- docs/DAY_TO_DAY.md · tests/test_day_to_day.py

## [0.6.0] - 2026-07-22

### Hyper-memory (surpass holographic latency class)
- Hot path: cached entity index; colony disk I/O off critical path
- Fair warm-cache microbench @N=1008: **~0.12 ms** prefetch, hit 1.0
- **Lex-first two-stage query**: candidate gen → batch vector+bio rank only on candidates
- Resident engine cache (entries + lex + matrix) — no full rescan every turn
- **hermescube_probe** tool: probe/related entity graph (agent-focused)
- Goal: beat stock holographic prefetch while keeping Cube auto-turn + colony + void

## [0.5.0] - 2026-07-22

### Framework housing + review fixes
- **`hermescube/framework/`**: paths, config, CubeVoid (void OS), LexIndex
- Provider uses path housing + Void for prefetch/reinforce (thinner adapter)
- **Entity hygiene**: multiword/$/canon phrases; drop bare Mission/Zero noise
- **Colony board throttle**: `maybe_write_markdown_board` (not every prefetch)
- Lexindex candidate shrink on large scans (toward holo-class speed without cloning)
- Docs: `docs/FRAMEWORK.md` — how memory operates inside the cube

## [0.4.0] - 2026-07-22

### Colony communication (original — not a holographic clone)
- **`colony.py`:** ant pheromone trails between entities (deposit / evaporate / trail_boost)
- **Bee waggle dances:** each memory carries kind (pollen type) + where (entities)
- **Markdown board:** `$HERMES_HOME/memories/COLONY.md` human-readable trail map
- Prefetch lays scent; helpful feedback reinforces trails; mirror_expand uses trail boost
- Bio stack: elephant durability + dolphin social co-activation + whale culture sheet + ant/bee stigmergy

## [0.3.9] - 2026-07-22

### Mirror infrastructure (holographic RE + bio)
- New `hermescube/mirror.py`: entity extract, entity index, **mirror_expand** (co-entity + causal parent resonance)
- HAR query finishes with mirror expand — related memories co-activate
- Append annotates `data.entities`
- Research: holographic reverse-engineer note; skill workflow update

## [0.3.8] - 2026-07-22

### Real-use quality (long exp)
- **Durable channel boost:** seed/manage/extract outrank sync_turn in ranking
- **Fact extract (no LLM):** `Name = role`, prefers…, path lines → durable entries
- **`benchmarks/real_use_bench.py`:** public-benefit gates (hit rate, latency, Q-index, persistence, IR) — results under `$HERMES_HOME/hermescube-lab/` not git tree
- Long-run 8×197-entry exp: hit_frac **1.0**, prefetch ~**8.6 ms** avg

## [0.3.7] - 2026-07-22

### Dogfood fix (fresh install experience)
- `sync_turn`: index **assistant answer** when user message is a question (stop Q-text polluting IR)
- Rank penalty for question-shaped descriptions
- Fresh install dogfood + labeled IR bench note in research canon

## [0.3.6] - 2026-07-22

### Update system (Hermes-aligned)
- `hermescube update` — git pull installed plugin + pip reinstall (cube data untouched)
- `hermescube update --check` — compare local vs remote
- `scripts/update.sh` — same flow for shell
- Docs: use with `hermes plugins update hermescube` (git-only) or full `hermescube update`
- Project tree cleanup: stronger `.gitignore` (no cubes/pycache/egg-info)

## [0.3.5] - 2026-07-22

### Hermes-native user install (end-user workflow)
- **Install path A:** `hermes plugins install PabloTheThinker/hermescube` then `./scripts/install_hermes.sh`
- **Install path B:** `git clone` + `./scripts/install_hermes.sh` (uses `$HERMES_HOME`)
- Root `plugin.yaml` + `__init__.py` + `cli.py` so Hermes discovers the repo as a memory provider plugin
- Install script: pip into Hermes Python, materialize `$HERMES_HOME/plugins/hermescube/`, set `memory.provider` only if unset, verify cube path under user home
- **User data isolation:** cube always `$HERMES_HOME/memories/memory.cube` — never the project/git tree
- CLI: path defaults to user cube; `hermescube doctor`; `query [path.cube] text…`
- Docs: README, USER_GUIDE, CONTRIBUTING, SPEC, ARCHITECTURE, after-install aligned to this workflow

## [0.3.4] - 2026-07-22

### Everyday ops
- Rank **score-first** (stop layer quotas burying gold hits)
- Lexical **stopword filter** so "who is X" matches names, not "is" in unrelated lines
- Skill rewritten for daily dogfood checklist

## [0.3.3] - 2026-07-22

### IR quality
- Hybrid **lexical + HRR** ranking (stem/synonym bridge, no LLM)
- Labeled relevance@k metric (was HAR↔scan agreement — misleading)
- Live labeled Recall@10 ≈ **0.875** on agent memory bench

### Tests
- 200+ including lexical bridge

## [0.3.2] - 2026-07-22

### Bio-cognitive memory architecture
- **`bio_rank` module:** cortical layers (sensory/associative/executive/meta), type-aware half-lives (elephant social/spatial retention), trust×outcome composite scoring, hierarchical layer diversification on query.
- **Unihemispheric sleep:** `evolve_consolidated` exposes NREM (k-means+dedup) + REM hubs + meta report — still **never** on prefetch hot path.
- **Prefetch inject:** `[type|layer]` tags; system prompt shows layers + hemisphere policy.
- **Classify:** relationship + spatial/VPS landmark cues.

### Tests
- **198+** including `test_bio_rank.py`.

## [0.3.1] - 2026-07-22

### Performance (Quicksilver speed spine)
- **Prefetch hot path:** LLM query-rewrite is **off by default** (was ~4–5s per call via aux LLM). Opt-in: `HERMESCUBE_QUERY_REWRITE=1` or `plugins.hermescube.query_rewrite: true`.
- **Linear scan:** batch cosine via numpy matmul (N×d · d) instead of N separate norm/dot loops.
- **Learned embedder:** OOV / zero-weight queries fall back to hash embed (never return zero vector after tiny evolve).

### Fixed
- Config load respects session `hermes_home` (tests no longer inherit operator live config).
- Cross-session search after evolve on small corpora.

### Tests
- **192** passed.

## [0.3.0] - 2026-07-20

### Added
- **HermesAgent plugin registration**: `plugin/__init__.py` with `register(ctx)` entry point. Plugin installs to `$HERMES_HOME/plugins/memory/hermescube/` and activates via `memory.provider: hermescube` in config.yaml.
- **`plugin.yaml`**: Plugin metadata, config schema, tool listing for the HermesAgent plugin system.
- **`plugin/cli.py`**: 4 CLI commands for hermes memory management: `hermescube-status`, `hermescube-evolve`, `hermescube-dump`, `hermescube-compact`.
- **`hermescube_feedback` tool**: Rate memory entries helpful/unhelpful. Adjusts trust scores (0.0–1.0). Clamped, tracks feedback count.
- **Auto-extract on session end**: 5 regex patterns extract user preferences, project decisions, and tool quirks from conversations. Enabled via `auto_extract: true` config.
- **Circuit breaker for evolve**: 3 consecutive evolve failures → 5-minute cooldown. Prevents repeated expensive failures.
- **Per-profile cube isolation**: When `agent_identity` is passed to `initialize()`, cube files are scoped to `memories/profiles/{identity}/`. Set via `agent_workspace` for workspace-level isolation.
- **Context-aware write skip**: `agent_context` values `"cron"`, `"flush"`, and `skip_memory=True` prevent writes (prevents cron system prompts from corrupting user memory).
- **Provenance metadata**: `on_memory_write` captures `write_origin`, `execution_context`, `session_id`, `platform` in entry data for audit trails.
- **Session switch contract**: Full `reset`/`rewound`/`parent_session_id` support per the HermesAgent MemoryProvider ABC contract.

### Changed
- **Tool renaming**: `memory_search` → `hermescube_search`, `memory_manage` → `hermescube_manage` — avoids shadowing the built-in `memory` tool and other reserved core tool names.
- **`get_config_schema()`**: Expanded from 3 to 6 fields with proper descriptions, defaults, and choices.
- **`save_config()`**: Saves to `hermescube.json` instead of `config.json` for provider-specific config.
- **`system_prompt_block()`**: Updated with new tool names and guidance.
- **`on_session_end()`**: Auto-extract runs even when cube is empty; evolve only runs when entries exist.
- **`_score_topics()`**: Reads L1 entries once (was reading per bucket — 64× overhead on large archives).

### Fixed
- **`_do_sync` β update**: Now captures the returned entry from `cube.append()` instead of re-reading L1[-1], closing a subtle race window.
- **`_read_entry_at()`**: Uses shared `_compute_entry_size()` instead of duplicate inline formula — no drift risk on format changes.
- **Entry serialization**: Extracted `_pack_entry_bytes()` as single source of truth for the on-disk L1 layout, shared by writer and reader.

### Tests
- **158 tests** (+23 from 135), 5/5 stable runs, 0 pyright errors.
- New test classes: `TestHermesCubeFeedback`, `TestAgentContextSkip`, `TestSessionSwitch`, `TestAutoExtract`, `TestPerProfileScoping`, `TestOnMemoryWriteMetadata`, `TestCircuitBreaker`.

## [0.2.1] - 2026-07-20

### Added
- **Atomic append rewrite**: Writes entire new file to `.tmp`, fsyncs, then `os.replace()` — eliminates all crash windows.
- **Cross-process `fcntl.flock`**: `LOCK_EX | LOCK_NB` acquired on open, released on close. Two processes cannot race on the same `.cube`.
- **Async write routing**: `on_pre_compress`, `on_memory_write`, `on_delegation` all route through `_SyncQueue` — no longer block agent turn on O(n) writes.

### Removed
- `_shift_tail()`, `_write_entry()`, `_update_header()` — replaced by atomic tmp+rename path.

## [0.2.0] - 2026-07-19

### Added
- **Learned embeddings** (`embed.py`): TF-IDF + random projection model trained on accumulated entries. Improves semantic similarity over hash-based encoding. Auto-trains during `evolve()`.
- **Incremental k-means**: Refines existing centroids instead of recomputing from scratch. Faster for large archives.
- **`CubeMemoryProvider`** (`provider.py`): Full HermesAgent `MemoryProvider` ABC implementation with 33 methods.
  - `memory_search` and `memory_manage` tools (OpenAI function-calling schemas)
  - Background sync with single-worker executor
  - Threat scanning (6 injection patterns)
  - `evolve_consolidated()`: k-means + deduplication + topic quality scoring
  - Memory nudge: reminds agent to consolidate every N turns
  - Structured `on_pre_compress()`: extracts goals/decisions/constraints
  - `get_config_schema()`, `save_config()`, `backup_paths()`
- **`threats.py`**: Prompt injection scanning (system_override, role_hijack, delimiter_escape, etc.)
- **CLI `beta` command**: Show β vector stats
- **`tests/test_cli.py`**: 14 tests covering all 7 CLI commands
- **`tests/test_embed.py`**: 9 tests for learned embeddings
- **pytest-cov** in CI with coverage reporting
- **`py.typed`** marker for PEP 561
- **Dependency upper bounds**: numpy<2, pytest<9, pyright<2

### Fixed
- **`write_l3()` bug**: Was appending a new L3 copy on every call (file grew 2KB per query). Now overwrites in place for queries, only appends when L2 is rewritten by `evolve()`.
- **`_recency_weight()`**: Now uses actual timestamp delta with exponential decay instead of hour-of-day heuristic.
- **`_write_entry()` double vector computation**: Vector is now cached on the entry after first computation.
- **Unused imports**: Removed `re`, `Counter`, `field` from provider.py; `Any` from cli.py.
- **Dead code**: Removed unused `setup_provider()` generator from test_provider.py.
- **Benchmarks**: Replaced `sys.path.insert` with try/except import fallback.
- **SPEC.md**: Corrected header size (40 bytes, not 32), L2 behavior (empty until evolve), API examples, beta CLI command.

### Changed
- **`evolve()` return value**: Now includes `embedder` stats (trained/vocab_size/etc.)
- **`HARQueryEngine`**: Accepts `use_learned_embeddings` parameter (default True)
- **Recency weighting**: Exponential time-decay (e^(-delta/48h)) replaces hour-of-day heuristic

## [0.1.0] - 2025-07-18

### Added
- Initial release
- `.cube` binary format (L1/L2/L3 layers)
- HRR algebra (numpy + pure-Python dual backend)
- HAR query engine with k-means clustering
- CLI: init, info, append, query, evolve, dump
- 76 tests passing
- CI/CD (GitHub Actions, test matrix 3.11-3.13)
- HermesAgent skill at `~/.hermes/skills/hermescube/`
