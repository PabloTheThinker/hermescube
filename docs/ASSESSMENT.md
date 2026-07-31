# HermesCube assessment & functional audit

**Date:** 2026-07-31  
**Version under test:** **0.50.0** (`e9c8271` main)  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Live home:** `$HERMES_HOME` (operator machine under test)

This replaces the 0.47-era snapshot for the **library under Hermes** direction (0.50) plus blackbox, checkpoint ark, CLI connect, and security suite.

---

## 1. Executive verdict

| Dimension | Grade | Evidence (this run) |
|-----------|:-----:|---------------------|
| Ship readiness | **A−** | Clean main; isolation OK; no PyPI required |
| Product clarity | **A** | Library/book/chapter story in README/ABOUT/PURPOSE |
| Hermes MemoryProvider | **A** | `memory.provider=hermescube` **active**; plugin available |
| Day-one CLI | **A** | `setup` · `connect` · `status` work end-to-end |
| Long-tail warehouse | **A** | 31 472 entries · integrity ok · 0 empty · 0 dups · 0 bad_vec |
| Recall | **A−** | Query returns relevant resolves/landmarks; some DOT noise |
| Blackbox (prove) | **A** | Capture 135 events · 6 redactions · integrity · claim **pass** |
| Identity ark | **A** | Checkpoint listed · create/restore path secured |
| Security / isolation | **A** | Audit **0 findings** · harden applied · check_isolation OK |
| Profile non-bleed | **A** | One home → one book; path containment in security/checkpoint |
| Hermespace heart | **A−** | Center API 1.2 · organs present · Space optional |
| Fleet / dream / hive | **B+** | Shipped but secondary; not day-one |
| Usefulness metric | **C** | Doctor `usefulness: None` — still unfilled |
| Triage plan | **C** | `no plan yet` — debt under monotropic load |
| Full suite tests | **B+** | Focused 16/16 on new surfaces; full 466-suite not re-run this pass |
| Docs honesty | **A** | CLI/SECURITY/BLACKBOX/CHECKPOINT match code |

**Verdict: Working as the Hermes-base library core.**  
Day-one path is solid. Deep organs (hive/dream) remain advanced. Biggest product gaps are **usefulness scoring**, **triage plan**, and **vector disk weight** — not functional breakage.

---

## 2. What HermesCube *is* (functional model)

```
Hermes Agent (librarian on duty)
  ├── MEMORY.md / USER.md     desk card catalog (hot, small)
  ├── state.db                session CCTV → blackbox flights
  ├── skills                  procedure binders
  ├── memory tool             intentional hot writes
  └── MemoryProvider ──► HermesCube
         │
         ├── memory.cube      BOOK (SoT long-tail)
         ├── blackbox/        HEART provenance (flights)
         ├── checkpoints/     ARK safe locks (identity + book)
         ├── relations        cross-refs
         ├── center/space_bridge   blood to Hermespace desk
         └── security         doors locked per HERMES_HOME
```

**One sentence:** local book of long memory that compresses life into chapters, with a heart that can prove work and an ark that can restore identity.

---

## 3. Proper use flow (operators & agents)

### 3.1 First attach (any Hermes user / any agent home)

```bash
export HERMES_HOME=~/.hermes   # or ~/.hermes/profiles/<name>
hermescube setup               # optional install_hermes.sh + connect
hermescube connect             # idempotent: dirs, book, provider, harden
hermescube status
hermes memory status           # must show hermescube ← active
# restart gateway / Desktop / session once
```

**Code path:** `cli.cmd_connect` → `connect.connect` →  
`ensure_dirs` → `ensure_plugin_link` → `ensure_cube` → `set_provider_hermescube` → `harden_home_permissions`.

**Guarantee:** that home’s agent only sees **that** home’s `memories/memory.cube`.

### 3.2 Everyday agent turn (automatic)

When `memory.provider=hermescube`:

1. **initialize** — open cube under provider’s `hermes_home` (`provider.CubeMemoryProvider`)  
2. **prefetch / queue_prefetch** — HAR strip into context (capped)  
3. **sync_turn** — extract/write durable signals; WAL safety  
4. **tools** — `hermescube_search` / `manage` / `feedback` / `probe`  
5. **on_memory_write** — mirror hot MEMORY.md writes into cube  
6. **on_session_end** — digest / optional pipelines  

Hot MEMORY.md stays the sticky notes; cube is the stacks.

### 3.3 Everyday human terminal

| Intent | Command |
|--------|---------|
| Health | `status` · `doctor` · `security audit` |
| Find passage | `query "…"` |
| Prove a run | `blackbox capture --latest` → `prove --claim "…"` |
| Safe lock | `checkpoint create --name …` |
| Night chapter bind | `dream status` / `dream solo` (advanced) |
| Update code only | `hermescube update` (never wipes book) |

### 3.4 Multi-pilot / multi-agent

```bash
HERMES_HOME=~/.hermes/profiles/client-a hermescube connect
HERMES_HOME=~/.hermes/profiles/client-b hermescube connect
```

No shared book unless homes are shared. Hive = optional inter-library loan (not required).

### 3.5 Disaster

```bash
hermescube checkpoint list
hermescube checkpoint restore --name <slug> --dry-run
hermescube checkpoint restore --name <slug>
# restart Hermes
```

---

## 4. Live functional results (2026-07-31)

| Check | Result |
|-------|--------|
| Version | 0.50.0 from git checkout |
| pytest (security+blackbox+center) | **16 passed** |
| check_isolation.sh | **OK** |
| doctor integrity | **ok** · 31472 entries · 0 empty/dup/bad_vec |
| functional_loop | healthy · crystals 130 · beliefs 314 |
| relations | 132 open |
| status | heart ready · provider hermescube |
| security audit | **ok · 0 findings** |
| connect | ok · harden 15 paths |
| blackbox capture | ok · 135 events · 6 redactions · integrity_ok |
| blackbox prove "hermescube" | **pass** conf 0.9 |
| checkpoint list | `library-arc-2026-07-30` present |
| query "library under Hermes" | top hits are correct resolves |
| hermes memory status | hermescube **← active** |
| center organs | heart, arteries, veins, autonomic, nervous_foa, hippocampus, immune, lymph, vascular_beds, **blackbox**, **ark** |

---

## 5. Code architecture (how layers work)

### 5.1 Module map (74 Python modules)

| Area | Modules | Role |
|------|---------|------|
| **L0 housing** | `framework/*` | paths, config, lexindex, void |
| **L1 book engine** | `cube.py`, `hrr.py`, `har.py`, `embed.py`, `bio_rank.py`, `threats.py` | binary archive + retrieval |
| **L2 Hermes socket** | `provider.py`, `manage*.py`, `tools_recall.py`, `session_end.py`, `mirror.py` | MemoryProvider ABC |
| **L3 governance** | `cuboasis.py`, `cubewave.py`, `memory_gate.py` | review-first writes |
| **L4 growth** | `genealogy.py`, `living.py`, `curator.py`, `self_evolution.py`, `growth_merge.py` | editions / chapters |
| **L5 fleet** | `hive.py`, `hq.py`, `interview.py` | multi-agent opt-in |
| **L6 dream** | `dream.py`, `dream_circle.py` | night consolidate |
| **L7 heart** | `space_bridge.py`, `center.py` | Hermespace blood + organs |
| **0.50 surfaces** | `blackbox/*`, `checkpoint.py`, `connect.py`, `security.py`, `cli.py` | prove · ark · dial · seal |

### 5.2 Critical paths (line-of-responsibility, not every LOC)

**Warehouse read/write** — `cube.CubeFile`  
- Append-only entries; integrity_check; L1 data + vectors.  
- Doctor proved: integrity ok at 31k entries.

**Recall** — `har.HARQueryEngine` + provider `prefetch`  
- Score-first hybrid retrieval; inject capped for load.  
- Live query returned doctrine resolves at score ~1.83.

**Provider** — `provider.CubeMemoryProvider`  
- Implements Hermes MemoryProvider: initialize, prefetch, sync_turn, tools, session_end, shutdown.  
- Soft-fail edges; profile-scoped home.

**Center** — `center.py` (API **1.2**)  
- `beat` / `supply` / `return_flow` / `autonomic_tick`  
- `flight_capture` / `flight_prove` / `breathe`  
- Organs include **blackbox** + **ark**

**Blackbox** — `blackbox/{flight,redact,capture,prove,inspire}.py`  
- state.db → redacted events → sha256 integrity → claim rules  
- `inspire.breathe`: inhale → gas_exchange → exhale (seal + relations)

**Checkpoint** — `checkpoint.py`  
- Copies SOUL/MEMORY/USER/CUBE + cube under `memories/checkpoints/<slug>/`  
- Security: no path escape, no .env, secret scan, 0600 files

**Security** — `security.py`  
- `assert_under_home`, `audit_home`, `harden_home_permissions`  
- Live audit clean after harden

**Connect CLI** — `connect.py` + `cli.py`  
- Day-one dial for any agent home

---

## 6. Security assessment

| Control | Status |
|---------|--------|
| One home one book | Enforced by path model |
| Checkpoint no .env | Enforced + tested |
| Path traversal | `assert_under_home` + slug rules |
| Vault permissions | harden → 0700 memories, 0600 cube/identity/.env |
| Secret patterns in ark | scanned; skip/block |
| Git pollution | check_isolation OK |
| Cross-pilot | Separate HERMES_HOME only safe pattern |

**Residual risks (honest):**  
- OS-level disk theft still needs full-disk encryption (out of scope).  
- `config.yaml` can hold non-secret settings; secrets must stay in `.env` (audit flags secret-like config).  
- Full 466-test suite not re-executed this pass — recommend CI on push.

---

## 7. Gaps & recommended next work

| Gap | Severity | Action |
|-----|----------|--------|
| Doctor `usefulness: None` | Med | Wire feedback → 7d helpful rate |
| Triage plan missing | Med | `hermescube` triage generate on schedule |
| Vector disk ~85% | Med | Document `dense` backup; optional dim policy |
| DOT relation noise in query | Low | Prefer crystals in prefetch ranking |
| Breathe 15–90s | Low | Cron only; never mid-turn |
| Full test suite runtime | Low | CI job on GitHub Actions |
| PyPI publish | Optional | Ship wheel for non-git users |

---

## 8. Grade summary (0.50 library core)

**Overall: A− / working production library for Hermes base.**

Keep running on:

1. `connect` → provider active  
2. Agent turns via MemoryProvider  
3. `query` / feedback  
4. `blackbox` for prove  
5. `checkpoint` for ark  
6. `security audit` after changes  

Do not sell day-one users hive/dream/HQ first — monotropic: **remember · prove · doctor · safe-lock**.

---

## 9. Reproduction commands

```bash
export HERMES_HOME=~/.hermes
cd /path/to/hermescube
PYTHONPATH=. python3 -m pytest tests/test_security.py tests/test_blackbox.py tests/test_center.py -q
bash scripts/check_isolation.sh
hermescube doctor
hermescube status
hermescube security audit
hermescube blackbox capture --latest
hermescube blackbox prove --claim "tests pass" --latest
hermescube checkpoint list
hermes memory status
```
