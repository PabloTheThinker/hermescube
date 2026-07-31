# Changelog

## [Unreleased]

### Agent continuity handoff (3am page)
- `hermescube handoff` + tool `hermescube_handoff` — open/list/take/complete
- Auto-snapshot unfinished sessions on session_end
- System prompt injects open packets for any connecting agent
- Docs: [docs/HANDOFF.md](docs/HANDOFF.md) — addresses handoff-as-bottleneck

### Batched LTM uploads (every 10 assistant turns + session/dream flush)
- `sync_turn_interval` default **10** — buffer durable turns; batch write to cube
- Always flush on session_end, shutdown, “remember”, high witness, failures
- Config: `plugins.hermescube.sync_turn_interval` / `sync_buffer_max`
- Docs: [docs/BATCHED_LTM.md](docs/BATCHED_LTM.md)

### Security suite — sealed homes (no leakage)
- `hermescube security audit|harden` — path containment, secret scan, permission vault
- Checkpoint create/restore refuse path escape, `.env`, secret-like files
- `connect` hardens modes after attach; docs [SECURITY.md](docs/SECURITY.md)
- Generator rule: one HERMES_HOME → one book → no cross-profile population

### Terminal connect layer (any Hermes agent → own cube)
- `hermescube setup` · `connect` · `status` — dial a HERMES_HOME into its own library book
- Module `hermescube.connect`: ensure dirs, plugin link, create cube, set `memory.provider=hermescube`
- Docs: [docs/CLI.md](docs/CLI.md)

### Identity ark — safe-lock checkpoints
- `hermescube checkpoint create|list|restore` — flash clone of `memory.cube` + SOUL/MEMORY/USER (+ optional config)
- Never packs `.env` / auth secrets; restore backs up live files as `*.pre-restore-*`
- Docs: [docs/CHECKPOINT.md](docs/CHECKPOINT.md); center organ `ark`
- Mental model: offline identity arc mark so a fresh restart can restore the librarian + library

## [0.50.0] - 2026-07-30

### Library under Hermes — Hermes-base core direction
- **Product language:** HermesCube is the **library under Hermes**; `memory.cube` is a **book**; crystals/growth/dream bind **chapters (arcs)**; MEMORY.md is the desk **card catalog**
- **North star refresh:** [PURPOSE.md](PURPOSE.md) · [ABOUT.md](ABOUT.md) · [README.md](README.md) lead with *remember + prove + doctor*
- **Architecture / docs:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/HERMESPACE.md](docs/HERMESPACE.md) · [docs/README.md](docs/README.md) · [docs/BLACKBOX.md](docs/BLACKBOX.md) · [docs/ANATOMY.md](docs/ANATOMY.md)
- Community one-liner: *local book of long memory that compresses life into chapters, with a heart that can prove what was done*

### Blackbox organ — flight recorder in the Cube heart
- First-class `hermescube.blackbox` (concepts inspired by [asimons81/hermes-blackbox](https://github.com/asimons81/hermes-blackbox))
- Capture Hermes `state.db` → redacted FlightRecord + SHA-256 integrity; claim `prove`; CLI `hermescube blackbox`
- `center.py` API **1.2**: organ `blackbox`, `flight_capture` / `flight_prove` / **`breathe`**
- **Breathe cycle** (`blackbox.inspire`): evidence-oriented programming — inhale → prove → exhale seals + relation weave
- Tests: `tests/test_blackbox.py`

## [Unreleased]

### Architecture Blueprint — whole-project map
- Rewrite [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) as the full HermesCube Architecture Blueprint (ecosystem, L0–L7 stack, anatomy, lifecycles, Cuboasis/Hive/Dream/Hermespace, safety, module map)
- Refresh [docs/CODEMAP.md](docs/CODEMAP.md) + docs index / ABOUT / PURPOSE pointers

## [0.49.0] - 2026-07-28

### Anatomical center — stronger Cube × Hermespace heart integration
- Research merge: Nous MemoryProvider lifecycle/caps/soft-fail + Hermespace Baddeley/Cowan/GWT/Sweller/pulse + Cube bio-rank / species maps
- New `hermescube/center.py` (`CENTER_API_VERSION = "1.1"`): organ map, `beat`, `supply`/`return_flow` (diastole/systole), `autonomic_tick`, load-tiered strip budgets
- Docs: [docs/ANATOMY.md](docs/ANATOMY.md) — circulatory architecture + Space turn/idle wiring
- Tests: `tests/test_center.py`

## [0.48.0] - 2026-07-28

### Hermespace heart API — Cube ready as Space's core
- `space_bridge` stable contract `GENERATOR_API_VERSION = "1.0"`
- New: `ensure_heart`, `heart_status`, `seal_learning`, `pulse_charge`
- `module_status` / `seal_to_cube` kept as back-compat aliases for Hermespace 0.18
- Seals threat-scan + journey log; typed entry support (belief/landmark/trait/…)
- Docs: [docs/HERMESPACE.md](docs/HERMESPACE.md) integration checklist + recommended Space `cube_module` shape
- PURPOSE/ABOUT: Cube as Hermespace generator/heart (from prior purpose PR commits)

## [Unreleased]

## [0.47.0] - 2026-07-27

### CubeDream complete stack — dialogue, auto-circle, skim, L4 + peel
- **Conversation**: `dream_circle.dialogue_in_circle` runs peer interview inside a circle; brief facts become chorus signals
- **Auto-circle**: `run_auto_circle` / `hermescube dream auto-circle` — multi-agent night chorus from soul cubes (+ optional interview pair)
- **Adversarial skim**: conflict-aware demotion of circle candidates (report-ranked, no deletes)
- **L4 proposals**: `dream.propose_memory_md` / `hermescube dream propose` — MEMORY.md diffs never auto-applied
- Manage modes: `propose`, `auto-circle`, `circle:dialogue`, `circle:skim`
- Peel `search` / `probe` / `feedback` into `tools_recall.py` (provider hub thinner)
- Tests: `test_dream_full.py` + interview CLI list (466 total)

## [0.46.0] - 2026-07-27

### CubeDream — soul dreams + dream together (circle MVP)
- **L1 soul dream** (`dream.py`): due-reasons scheduler, `DREAMS.md` diary, `solo` / `solo:apply` (packages `sleep_replay` + crystalize; never touches MEMORY.md)
- **L2 dream circle** (`dream_circle.py`): open → join → signal → score → close → draw
- **Together bonus**: multi-agent agreement on `canonical_key` raises score; close promotes to `hive.cube` under hive dream lock
- Manage: `hermescube_manage action=dream`; CLI: `hermescube dream status|solo|circle …`
- Prompt reminder strip when soul dream is due; deep ASSESSMENT refreshed
- Tests: `test_dream_circle.py` (460 total)

## [0.45.0] - 2026-07-27

### Peel manage hub — code health + fleet CLI coverage
- Extract ~1.5k LOC of `hermescube_manage` handlers from `provider.py` into domain modules:
  `manage.py` (dispatch) · `manage_warehouse` · `manage_cuboasis` · `manage_growth` · `manage_fleet`
- Provider hub now ~2480 LOC (was ~4020); `_handle_manage` is a thin dispatcher
- CLI tests for `hermescube hive` / `hq` (init, status, charter, route, verify) + dispatch smoke
- Research note: OMH high-priority governance already shipped; remaining medium items are TTL/typed records + dreaming/eviction *proposals* (not silent mutate)
- Tests: `test_cli_hive_hq.py` (455 total)

## [0.44.0] - 2026-07-27

### Lift remaining sub-A grades — modularity, CLI, entities, density
- Extract `agent_manual.py` (system prompt) and `session_end.py` (session-end pipeline) from `provider.py` (~540 LOC out of the hub)
- Entity mine-on-pulse: `enrich_entries_with_mined_entities` + expanded infra allowlist; small-corpus DF fix
- CLI: `hermescube dense export|import|stats`; doctor shows density + bootstrap readiness
- Density stats: vector/text share % + recommendation (dense export companion; f16 remains future format bump)
- Solo-path callout in agent manual; tests: `test_cli_doctor_dense.py`, `test_entity_enrich.py` (451 total)

## [0.43.0] - 2026-07-27

### Instant agent onboarding — bootstrap + operate skills
- New `hermescube/bootstrap.py`: import MEMORY.md / USER.md / SOUL.md into the warehouse (idempotent, threat-scanned) + install bundled skills
- `hermescube_manage action=bootstrap` modes: `status` · `import` · `skills` · `all` (plus `import:force`)
- **Auto-bootstrap on initialize** when the warehouse is empty / skills missing (`auto_bootstrap`, default true)
- System prompt rewritten as an **instant operating manual** (mental model table, Start-here CTA, everyday loop, rules)
- Bundled skills: `hermescube-operate`, `hermescube-import` (+ existing `interview-me`)
- Install script copies skills and seeds the cube from hot markdown when empty
- Tests: `tests/test_bootstrap.py`

## [0.42.0] - 2026-07-27

### A− → A lifts — governance, isolation, cost, security, doctor
- **Governance**: sync-turn fact extracts honor `memory_policy`; system prompt shows `policy=` + pending candidate summaries (`mode=review`); consolidate nudge mentions Cuboasis when review-first
- **Light Cuboasis strip**: prompt path no longer full-scans L1; `cuboasis_status(light=True, entries=…)` for session-end reuse
- **Isolation**: vault switch updates HAR + clears prefetch; cache key includes vault/`user_id`; HAR matches entry `user_id_alt`; nested `peer_card.json`
- **Session-end cost**: stage timers + `session_end_ms` in progress metrics; observe capped to last 40 msgs; idle skip evolve; flush returns bool
- **Security**: JWT/Slack/ghp patterns; MEMORY.md doctrine-override threat; blocked candidates redacted (hash + reasons); hive assimilate/draw run `memory_safety`
- **Entity extract**: infra allowlist (`redis`/`postgres`/…), `#tag`/`@handle`, semver filter
- **Doctor / install**: `--identity`/`--workspace`, version skew check, effective `memory_policy`; install seeds `memory_policy` + hive keys
- Docs: ASSESSMENT refreshed to 0.42; tests: `test_a_minus_lifts.py` (440 total)

## [0.41.1] - 2026-07-27

### Sync queue flush honors timeout
- `_SyncQueue.flush(timeout)` no longer hangs forever on a wedged worker (ported from draft PR #6 stress work)
- Regression: `test_flush_honors_timeout_against_stuck_worker`

## [0.41.0] - 2026-07-27

### Cuboasis governance — review-first memory oasis
- New `hermescube/memory_gate.py`: safety gate, evidence states, candidate capture/review/approve/reject, rejected-decision recall, curation sync report, doctor card
- Manage: `cuboasis mode=capture|review|approve|reject|rejected|sync|doctor`
- Config: `memory_policy` (`review-first` / `auto-safe` / `off`) gates auto-extract durable writes
- Sidecar: `candidates.jsonl`; evidence packets show `evidence_state`
- CLI doctor surfaces candidate backlog + Cuboasis readiness
- Docs: CUBOASIS governance + IDEAS_FROM_OMH ship order started

[0.40.0] - 2026-07-27

### Cuboasis — pocket-dimension memory oasis (+ Cubewave)
- **Rename**: functional infra framework is now **Cuboasis** (was Nexus) — Cube-native name for the internal pocket dimension
- New `hermescube/cuboasis.py` spine: **space** · **wave** · **connections** · **progress**
- **Cubewave** (`hermescube/cubewave.py`): ELM/LMS neural-like association field wired into HAR beside EngramNet — brainwave mimic without torch
- Manage actions: `space`, `connect`, `progress`, `cuboasis` (`nexus` kept as alias); triage `mode=apply`
- Chamber-scoped prefetch: `space mode=chamber:<name>` soft-filters recall into a pocket room
- Claim → SPO: durable MEMORY.md mirrors bridge inferred subject/predicate/object into RelationStore
- Stronger entity extract (relation pairs, backticks, path basenames, Cuboasis/Cubewave/Eden phrases)
- Outcome-weighted capability: progress ledger usefulness folds into `genealogy.measure_strength`
- Sidecars: `cuboasis_state.json`, `cubewave.json` (+ legacy `nexus_state.json`)
- Docs: [docs/CUBOASIS.md](docs/CUBOASIS.md); PURPOSE updated

## [0.39.0] - 2026-07-27

### Nexus — functional memory infrastructure
- New `hermescube/nexus.py` spine: **space** (vaults + chambers), **connections** (unified SPO ∪ colony ∪ engram ∪ HAR), **progress** ledger
- Manage actions: `space`, `connect`, `progress`, `nexus`; triage `mode=apply` forges consolidate + annotates conflicts
- Sidecars: `progress.jsonl`, `nexus_state.json` (path registry + legacy migrate)
- Session-end + feedback write the progress ledger; system prompt shows a Nexus infra strip
- Docs: [docs/NEXUS.md](docs/NEXUS.md); PURPOSE updated

## [0.38.0] - 2026-07-27

### Cube of Eden — the origin era
- **Origin era renamed**: fresh cubes begin in **`eden`** (display: **Cube of Eden**) — the garden before lived memory — replacing the old `genesis` era label
- Life path: Cube of Eden → Awakening → Formed → Seasoned → Elder
- `era_label()` / `normalize_era()` helpers; legacy genealogies with `era: "genesis"` migrate automatically to `eden`
- Birth epoch kind is now `eden`; CUBE.md, CLI, soul cards, pilgrimage lines, and the system prompt say **Cube of Eden**
- Maturity ranking treats `eden` (and legacy `genesis`) as capability weight 0
- Docs: [docs/GROWTH.md](docs/GROWTH.md) reframed around Eden


## [0.37.0] - 2026-07-26

### Compaction-safe extract (Hermes holographic algorithm)
- Merge-delimiter harvest: keep pre-delimiter user text; never store compressor handoff prose
- `on_pre_compress` uses the same harvest guard for user rows
- Assessment refreshed for 0.37 grades

## [0.36.0] - 2026-07-26

### Session-boundary + gateway user isolation
- `on_session_end` flushes the sync queue before return (Hermes MemoryManager end→switch FIFO)
- `on_session_switch` refreshes `parent_session_id` and `user_id` / `user_id_alt`
- Durable writes tag `data.user_id`; HAR soft-boosts matching users (unlabeled never hard-dropped)

## [0.35.0] - 2026-07-26

### Hermes-aligned compounding + trust IR
- Consolidate nudge in `system_prompt_block` when `memory_nudge_interval` elapses (Hermes never calls Cube `should_review_memory`)
- Prefetch one-liner after nudge emit; counter resets only when nudge is taken
- Holo-style trust reweight + entity-overlap boost in HAR ranking (algorithms from holographic `FactRetriever`, Cube-native store)

## [0.34.0] - 2026-07-26

### Usefulness hardening
- Numeric / count contradiction scan before session-end crystalize (`conflict.py`, AgentDrive witness idea — Cube-native soft markers)
- Vault-aware `active_wisdom` + Living prompt strip (soft boost; unlabeled never hard-dropped)
- `docs/DAY_TO_DAY.md` rewritten as triage → crystalize → merge → relations → feedback loop
- Trimmed `hermescube_manage` action description sprawl

## [0.33.0] - 2026-07-26

### Night-job cost + hot-path polish
- Session-end reads L1 once and threads `entries` into triage / crystalize / sleep_replay / living / growth_merge (intentional reread only after crystalize or digest appends)
- Crystalize candidate set capped (~200) via triage consolidate∪recent durable
- Engram `association_boosts` pattern bank uses (K,d) numpy matmul with pure-Python fallback
- `assoc_recall_bench` cost gates: session-end at N=2k/5k, prefetch p50, growth-merge fire

## [0.32.0] - 2026-07-26

### Multi-project sidecar isolation
- Sidecars (engram, yield, relations, triage, journey, living) nest under `memories/profiles/<identity>/<workspace>/` when both identity and workspace are set
- Shared `.cube` warehouse stays at `memories/memory.cube` so unlabeled legacy memories still recall
- Optional `data.vault` / `data.topic` tags on durable writes; HAR soft vault affinity (never hard-drops unlabeled)
- One-shot legacy sidecar migrate (copy, no delete) into nested profile dirs

## [0.31.0] - 2026-07-26

### Compounding surfaces are agent-visible
- Living `prompt_strip` shows triage focus/queue counts, growth-merge readiness, and open SPO relations
- System prompt hints when to call `triage` / `merge` / `relations`
- Prefetch appends relation lines for who/owns/related queries (even if HAR is empty)
- `hermescube doctor` / `info` report triage plan, relations stats, last growth-merge id

## [0.30.0] - 2026-07-26

### AgentDrive-inspired compounding (Cube-native)

Borrowed the *algorithms*, not the AgentDrive OS. HermesCube stays a
Hermes MemoryProvider; these make offline consolidation and session growth
structurally smarter.

- **`growth_merge.py`**: when ≥2 of durable / procedure / association /
  yield / wisdom fire in a session, append one `[GROWTH-MERGE]` evolution
  crystal with evidence ids + engram coactivation (session-end +
  `manage action=merge`)
- **`triage.py`**: route L1 into working_set / reconsolidate / consolidate /
  archive with rehearsal-sensitive retention; persist
  `memories/triage_plan.json`; session-end skips crystalize when nothing
  needs promotion; living pulse reports `next_focus`
- **`relations.py`**: time-bounded SPO store at
  `memories/relations.sqlite3` (`as_of` query, expire, ingest from
  relationship/DOT entries and manage-add); tool
  `manage action=relations`
- Living pulse gains **triage** + **growth** chambers; connect_dots writes
  relation edges when a Hermes home is present
- Manage enum: `triage`, `merge`, `relations`
- 389 tests

## [0.28.0] - 2026-07-26

### Growth that strengthens the system — curator + maturity ranking
- **Maturity-aware retrieval**: `bio_rank.maturity_multiplier` — as the living cube's era/strength rises, crystals and procedures rank higher and ephemeral chatter ranks lower (high lexical identity still wins). Provider pushes genealogy onto `HARQueryEngine._maturity` on init and after every growth tick
- **Soul cards publish growth**: `build_soul_card` now includes `growth.{version,era,strength,epochs,skills}` so peers at the hive can see how mature each soul's archive is (`hermescube hive souls`)
- **`curator.py`**: Hermes-style closed learning loop for the Cube — match drawn/interviewed lessons to installed skills by topical overlap and `refine_skill` them; on era milestones (major bumps) also forge procedure drafts + run the gardener (consent-gated)
- **Pilgrimage step 6**: after growth tick, curator runs automatically; CLI prints refined skills / milestone forge+garden
- **Draws preserve distillation**: `crystal` / `procedure` / `entities` survive offer → assimilate → draw so maturity ranking and skill matching see peer-distilled knowledge for what it is
- CLI: `hermescube growth curate [--lesson …] [--milestone]`; tool: `manage action=curate`
- 354 tests pass

## [0.27.0] - 2026-07-26

### Living Cube Growth — from 0.0.0 to elder
- **`genealogy.py`**: every cube is born at living version `0.0.0` (distinct from package version and binary format version). Experience advances it — patch for sessions/draws/interviews, minor for promotes/skill-installs/refines/crystals/confirmed predictions, major when strength crosses an era threshold (25 awakening / 50 formed / 75 seasoned / 90 elder)
- **Strength score (0–100)**: weighted composite of durable memories, crystals, procedures, installed skills, hive draws, interviews, confirmed predictions, and mean trust — raw turn dumps cannot fake maturity
- **`CUBE.md`**: human-readable growth diary under `$HERMES_HOME/memories/` (the cube's equivalent of Hermes Agent's visible learning story), rewritten each epoch; append-only truth in `memories/growth/epochs.jsonl`
- **Skills evolve**: helpful feedback on a procedure/skill entry (or `hermescube growth refine`) bumps the skill's own `version:`, appends under `## Lessons from the cube` without rewriting the core body, and advances the cube's living version
- **Wired throughout**: genesis on provider init; session-end tick; pilgrimage prints a growth line; promote / skill_bridge record epochs; system prompt carries `Living Cube vX.Y.Z (era, strength N/100)`
- **CLI**: `hermescube growth status|epochs|refine`; `hermescube info` shows living version
- **Agent tool**: `hermescube_manage action=growth content=status|epochs|refine:<skill>`
- Docs: [docs/GROWTH.md](docs/GROWTH.md)

## [0.26.0] - 2026-07-26

### One system — deep integration of Hive, HQ, harness, and interviews
- **Pilgrimage reordered**: OFFER → SOUL CARD → INTERVIEW → ASSIMILATE → DRAW — interview-distilled facts now join the collective cube in the *same* visit instead of waiting for the next pilgrimage
- **Interviews are fleet citizens**: each dialogue takes an HQ task claim (`interview:<subject>:<topic>`; concurrent attempts get a conflict, not a duplicate) and every completed dialogue is recorded in the HQ handoff ledger as knowledge flowing subject → interviewer
- **Provenance boundary fixed**: when the interviewer's cube grounds answers, only subject-attributed entries (`from_agent` / `[HIVE:subject]` / `[INTERVIEW:subject]`) are admissible — the interviewer's own memories can no longer masquerade as the subject's answers (cube evidence also now scores above the unknown threshold)
- **Interview dedupe + echo guard**: interview facts use content hashes (re-interviewing dedupes at assimilation instead of piling up); `draw_wisdom` never returns facts others distilled *about* the drawing agent
- **Handoff lifecycle closed**: `manage action=hq hq_action=handoff` routes the task, distills an evidence packet from your cube, and records a pending handoff in one call; `hq_action=complete` / `hermescube hq complete --id` settles it — pending handoffs that never settle are still flagged by `hq verify`
- **Interviews feed the harness**: a minted peer lesson commits a falsifiable `witness_absence` prediction — the lesson is supposed to prevent friction on that topic, and the verifier checks that it did
- **One status pane**: `hive status` now folds in charters (and the command owner), pending handoffs, and interviews held
- Session-end pilgrimage invalidates the retrieval cache so freshly drawn wisdom is immediately searchable; system prompt hive line now surfaces interview + HQ tooling
- New `tests/test_integration.py`: full night-cycle coverage across all layers (336 tests total)

## [0.25.0] - 2026-07-26

### Peer interviews — interview-me at the Hive
- **Adapted from** [hermes-field-kit/interview-me](https://github.com/asimons81/hermes-field-kit/tree/main/skills/interview-me) (Tony Simons, Apache-2.0): adaptive, evidence-first, one high-value question at a time
- **`interview.py`**: peer dialogue protocol — inspect soul card/charter/offerings before asking; coverage map across 10 dimensions; grounded answers from dossier + HAR (unknown when no evidence); interview-me report contract brief; consent-gated skill draft minting (`origin: hermescube-peer-interview`)
- **Pilgrimage ritual**: `hermescube hive pilgrimage --interview` (or `interview_on_pilgrimage: true`) — after offer/assimilate/draw, interview peer souls and mint pending procedure drafts
- **CLI**: `hermescube interview dialogue|list`
- **Agent tool**: `hermescube_manage action=interview interview_action=dialogue|list|mint`
- **Bundled skill**: `skills/interview-me/SKILL.md` — works for human interviews and hive peer dialogue
- Safety: inspected content is untrusted evidence (sanitized + threat-scanned); no silent skill installs; persist/mint are explicit

## [0.24.0] - 2026-07-26

### Fleet HQ — clear ownership for 1, 100, or a million agents
- **Charters** (`hq.py`): permanent agents exist because they own a durable lane — role (`command`/`specialist`), lane, keywords, boundaries; `retire` keeps history but stops routing immediately (no ghost routing)
- **Routing**: explicit overrides (audited) → lane keyword match → command fallback; the orchestrator owns the outcome. `hermescube hq route --task "..."` / `manage action=hq hq_action=route`
- **Privilege stays at the top**: subagents now get read-only memory tools (`search`/`probe`/`feedback`) — `manage` (durable writes, hive, HQ) is blocked with a boundary error; work flows upward
- **Lane strips**: chartered agents see their lane, boundaries, and other lanes' owners in the system prompt — specialists hand off instead of quietly doing everything
- **Handoff packets**: delegations distill task-relevant evidence (typed, quoted, provenance-tagged) via HAR + evidence packets; `on_delegation` records fleet handoffs in the ledger
- **Task claims**: leased ownership per task key; concurrent claims return a conflict with the current owner — no two agents thinking the task belongs to them
- **Fleet verification**: `hq verify` flags ghost routes, lane conflicts, missing command charter, uncharted souls, stuck handoffs (non-zero exit when flagged, cron-able)
- **Baselines**: `hq freeze` snapshots charter/routing hashes + collective stats; `hq drift` proves what changed — production ready means recoverable
- CLI: `hermescube hq charter|retire|list|route|verify|freeze|drift|handoffs`
- HQ state lives inside the hive root (`charters/`, `routing.json`, `handoffs.jsonl`, `claims/`, `baseline.json`) — the hive *is* the fleet HQ

## [0.23.0] - 2026-07-26

### Grounded self-evolution harness (witness → evolve → verify → critique → garden)
- **Inspired by** [hermes-self-evolution](https://github.com/erenciracioglu-dotcom/hermes-self-evolution): Evolution/Critic/Verifier/Gardener pattern adapted into the Cube's own offline cycle, with the constitution's rules enforced in code
- **Witness ledger** (`self_evolution.py`): append-only ground truth of real friction — auto-detected from `sync_turn` (user corrections, tracebacks; conservative regexes, `witness_detect` config) or logged manually via `hermescube_manage action=witness` / `hermescube harness witness`
- **No silent cycles**: every session-end evolve appends a report to `evolution_cycles.jsonl` — `action` (witness-anchored; marks witnesses addressed), `noop` (honest maintenance), or `failed`
- **Falsifiable predictions**: procedure promotion commits "earns trust ≥ 0.6" predictions; verifier settles verdicts (confirmed / refuted / expired) at session end — `witness_absence` and `entry_feedback` check types
- **Mechanical critic**: no-LLM heuristics flag bookkeeping theatre (maintenance-only streaks while witnesses sit unaddressed), overdue predictions, failing cycle streaks — zero collusion surface
- **Gardener**: surfaces dormant durable memories (old + low-trust) as proposals in `gardener_report.json`; archival stays consent-gated, nothing is deleted
- **CLI**: `hermescube harness status|witness|critic|verify|gardener` (cron-able)
- **Agent tools**: `hermescube_manage action=witness` (severity low/medium/high), `action=harness harness_action=status|critic|verify|gardener`
- All ledgers live under `$HERMES_HOME/memories/harness/`

## [0.22.0] - 2026-07-26

### HiveCube — the collective nexus (multi-agent hive mind)
- **Hive nexus** (`hive.py`): a shared directory where many Hermes Agents pool distilled experience — collective `hive.cube`, per-agent soul cards, quarantined offerings, audit ledger. Local-first: transport (NFS/synced folder) is the operator's choice; no network code
- **Pilgrimage cycle**: OFFER (durable beliefs, wisdom crystals, procedures, resolves — never raw turns or `private` entries) → ASSIMILATE (threat-scan, content-hash dedup, branch-tag `hive:<agent>`) → DRAW (focus-relevant collective wisdom into the agent's cube, quarantined as `hive_shared`)
- **Soul cards**: each agent publishes a compact identity — wisdom, missions, resolves, beliefs, procedures — to `agents/<agent>.json`; `hermescube hive souls` lists who is in the hive
- **CLI**: `hermescube hive init|status|pilgrimage|assimilate|souls` — cron-able nightly upload ("end of the night" ritual)
- **Agent tool**: `hermescube_manage action=hive hive_action=status|pilgrimage|draw|offer` with optional `focus`
- **Config**: `hive_path` (or `HERMESCUBE_HIVE`), `hive_on_session_end` (default false; nightly cron recommended)
- **Evidence packets**: drawn entries bucket separately as **COLLECTIVE (other agents)** — labeled `[HIVE:<agent>]`, ranked below user-authored and tool-verified facts; agents never draw their own offerings back
- **Trust model**: hive knowledge never overwrites local claims; shared procedures stay consent-gated (no silent skill install)

## [0.21.0] - 2026-07-26

### Living Cube — Hermes-aligned lifetime memory
- **Hermes contract harding**: subclass `MemoryProvider` when available; root `plugin.yaml` synced to **0.21.0**; `register()` no longer runs `pip install`
- **Path fix**: treat Hermes-scoped `hermes_home` as the storage root (no double `profiles/` nesting)
- **Concurrency**: short-held sidecar `.cube.lock` instead of lifetime exclusive flock — multi-session Hermes can share one cube
- **MemoryEvent / Claim schemas** (`events.py`, `claims.py`): provenance, verification, bi-temporal validity
- **Idempotent ingest** (`ingest.py`): content-hash cursor; tool trajectory from `sync_turn(messages=...)`
- **Temporal supersession**: `on_memory_write` replace/remove uses Hermes `old_text` tombstones
- **Subagent branches** (`branches.py`): delegation traces isolated; verified outcomes promote to main
- **Evidence packets** (`evidence.py`): typed prefetch (facts / episodes / procedures / intents / contradictions)
- **Skill bridge** (`skill_bridge.py`): explicit `install_to_skills=true` on promote → Hermes `skills/<name>/SKILL.md`
- **Branched consolidate** (`consolidate.py`): snapshot sidecars before evolve; rollback on failure
- Platforms manifest: linux/macos (POSIX locks); Windows not claimed

## [0.20.0] - 2026-07-24

### Living archive — chambers (cubes within the cube)
- `living.py`: multi-chamber pulse — identity, doctrine, intent, procedure, associate, narrative, catalog
- Catalog index `memories/catalog.json` (types, entities, topic hubs)
- Connect-dots: soft `[DOT]` relationship links across shared entities
- `hermescube_manage action=pulse` + session_end living pulse
- Prompt strip: Living archive status for any Hermes agent
- State: `memories/living_state.json`

## [0.19.0] - 2026-07-24

### Close Nous-ahead gaps (honest table)
- **Peer card** (`peer_card.py`): structured user model from warehouse; cadence rebuild; prompt strip
- **Session digest** (`session_digest.py`): non-LLM 5-line narrative on session_end → `[SESSION]`
- **Consent gate** (`consent.py`): manage `drafts` / `promote` / `reject` (not silent skill install)
- **Conflict** (`conflict.py`): soft contradiction markers on belief/resolve add
- **Care half-life**: `data.care` slows forget (~90d floor)
- **Cadence knobs**: peer_card_cadence_s, session_digest, observe/replay_on_session_end, conflict_detect
- Hermespace: leave + render + add_landmark purge session-ended spam

## [0.18.0] - 2026-07-24

### IR quality + Animus hubs under load
- Lexical rank: high query-coverage dominates crystal/prestige bias; short number tokens kept
- Labeled IR live: hit@5 **0.425→0.75–0.83**, hit@1 **~0.40**, MRR **~0.52**
- `HARQueryEngine._lex_identity_guard` — strong lex floors above engram hub boosts
- EngramNet.hub_ids + high-load inject prefers Animus hubs over query sprawl

## [0.17.0] - 2026-07-24

### Trajectory observe — watch work → procedure drafts
- `trajectory.py`: multi-tool chains from session messages → `[TRAJECTORY]` + draft SKILL under memories/procedures/
- Auto on `on_session_end` (max 2); `manage action=observe` manual
- Delegation success → resolve + prospective close attempt
- Scrub secrets/home paths; skip memory-only thrash chains; fingerprint dedupe
- Dawson-lite: observational learning without media/VLM sprawl

## [0.16.0] - 2026-07-24

### Prospective memory — focus → resolve
- `prospective.py`: open focuses stay hot until matching resolve closes them
- `hermescube_manage action=intents` (list / close_id)
- manage add resolve auto-closes best lexical match
- System prompt strip: Open intents; focus type_prior raised
- CONTINUITY refreshed to live 0.16

## [0.15.0] - 2026-07-24

### Sleep replay + labeled IR + ideas spine
- `sleep_replay.py`: offline CLS consolidation into Engram (bundles + edge decay)
- `hermescube_manage action=replay` + session_end auto-replay
- `scripts/labeled_ir_bench.py` — stem self-retrieval metrics on user cube
- `docs/IDEAS_FROM_OPS.md` — conversation→architecture map (public-safe)


## [0.14.1] - 2026-07-24

### Isolation + Engram hot-path polish
- `scripts/check_isolation.sh` + CONTRIBUTING isolation rules (no operator paths / live memory in git)
- Engram: skip re-rank when net empty; fused cosine; tighter shadow-learn
- Still: update hosts only via `hermescube update`

## [0.14.0] - 2026-07-23

### Engram Net — Cube-native neural associative field
- `engram_net.py`: Hebbian co-activation graph + Hopfield-style pattern bank (no torch)
- HAR re-ranks with association boosts; shadow-learns on every retrieval set
- Feedback strengthens/weakens cohort wiring (with last prefetch ids)
- Persists `memories/engram_net.json`; save on feedback + periodic + shutdown
- Research spine: Hermes closed-loop learning + CLS + modern associative memory principles (original implementation)

## [0.13.0] - 2026-07-23

### Procedure Forge + functional stand-up (Nous skills-from-experience)
- `procedure.py`: promote high-trust success resolves → evolution procedures + draft SKILL.md under memories/procedures/
- `hermescube_manage action=forge` (operator-gated; does not auto-install into ~/.hermes/skills)
- `scripts/functional_standup.py` — Nous learning-loop capability map on live host
- Hermespace leave always purges session-ended landmark spam

## [0.12.0] - 2026-07-23

### Inject surface hygiene + Hermespace leave quiet
- `cube_recall` / `build_space_inject` filter noise + superseded (no PERSIST/firsthand/CRYSTALIZED leak into FOA)
- Hermespace `leave("session ended")` no longer writes landmark spam; render prefers material landmarks
- Live: inject LEAK=False; session landmarks cleared on leave cap

## [0.11.0] - 2026-07-23

### Journey prune/edit + wisdom hygiene (Nous /journey edit principle)
- `is_noise_text` filters dogfood/test tokens from active wisdom + world
- `hermescube_manage action=hygiene` — prune journey noise, supersede cube test junk, clean world, re-push
- `action=prune` — edit journey.jsonl (drop noise/kinds/ids, keep_last)
- Live: PERSIST-PROOF and firsthand meta out of Hermespace beliefs; doctrine-grade wisdom remains

## [0.10.0] - 2026-07-23

### Journey Ledger + Hermespace world bridge (original)
- `journey.py`: playable learn timeline (Nous /journey principle — memory not a black box)
- JSONL events on manage/crystalize/feedback; `journey.md` human face
- `hermescube_manage action=journey` (+ `sync_world=true` pushes crystals → Hermespace beliefs)
- Fixes empty Hermespace "Beliefs (Active Wisdom)" while Cube had crystals
- space_bridge inject prefers active wisdom strip first
- Research: Nous journey/memory-graph + closed loop; adapt without cloning

## [0.9.0] - 2026-07-23

### Wisdom Crystalizer (original — true functional memory loop)
- `wisdom.py`: lexical consensus clusters → `belief` crystals with evidence_ids
- Active wisdom strip in system prompt + doctor functional_loop metrics
- `hermescube_manage action=crystalize` (also runs on session_end)
- `sync_turn` chitchat gate (ok/proceed/thanks) — stops landmark spam
- Crystals get rank boost (source_boost 1.55)
- Research: episodic→semantic without LLM; closes Hermes-style learning loop on warehouse

## [0.8.1] - 2026-07-23

### Integrity / durability
- `CubeFile.integrity_check()` — count match, empty desc, duplicate ids, vector sanity
- `hermescube doctor` + `info` report live integrity
- Tests: close/reopen, evolve-keep, subprocess cold open
- Proven on ILO live cube: write → shutdown → reopen → evolve → subprocess query OK

## [0.8.0] - 2026-07-23

### Yield Gradient (original — Nous learning-loop principle, not a clone)
- `yield_trail.YieldGradient`: query-token buckets → entry payoff (helpful/unhelpful)
- Rank multiplies by bounded yield boost (query-local value-of-information)
- Feedback + last prefetch query train the map; JSON under memories/ (cube untouched)
- Addresses honest limits: use-conditioned IR, closed loop without LLM/cloud
- Research: YIELD-GRADIENT-2026-07-23.md · PURPOSE unchanged warehouse framing

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
