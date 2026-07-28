# HermesCube project assessment & audit

**Date:** 2026-07-27  
**Version:** 0.42.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Live CI + A− lift pass (governance / isolation / session-end / security / doctor) + Hermes MemoryProvider contract

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness (public) | **A** | Clean `main`, isolation check, 440 tests, no open PRs |
| Hermes Agent integration | **A** | Native MemoryProvider; profile/workspace/`user_id`; session-end flush |
| Day-to-day no-loss | **A** | WAL sync_turn; MEMORY.md mirror; compaction-safe extract |
| Recall quality + speed | **A** | IR/assoc gates; trust×rank + entity overlap; infra allowlist; warm prefetch |
| Compounding usefulness | **A** | Triage→crystalize→merge→relations agent-visible |
| Cuboasis / governance | **A** | Review-first wired into sync extract; prompt queue + redact blocked candidates |
| Multi-project / gateway isolation | **A** | Nested sidecars + vault/`user_id`/`user_id_alt`; prefetch cache keyed; peer_card nests |
| Night-job / session-end cost | **A** | Single L1 + reuse entries; stage timers; observe capped; idle skip evolve; flush bool |
| Fleet / hive / growth stack | **A−** | On main; hive assimilate/draw now run memory_safety |
| Install / update UX | **A** | Dual-manifest guard; doctor version skew + nest args; install seeds `memory_policy` |
| Security baseline | **A** | JWT/Slack/ghp gates; doctrine-override threats; blocked candidate redaction |
| Code health | **B** | Powerful surface; `provider.py` still large |

**Verdict: Ship and run.** Suitable as the deep memory layer for Hermes-based company agents. Remaining polish is provider modularization and CLI coverage — not blockers.

---

## 2. What the product is

HermesCube is a **Hermes Agent memory provider plugin** plus a **binary `.cube` archive**:

- Code lives in the open repo / `$HERMES_HOME/plugins/hermescube`
- **User memory** lives only under `$HERMES_HOME/memories/` (never the git tree)
- Hot `MEMORY.md` / `USER.md` stay Hermes-native; Cube is the **warehouse**
- **Cuboasis** is the pocket-dimension spine: space · wave · connections · progress · governance

Borrowed from official Hermes holographic / MemoryManager: trust-weighted IR, consolidate nudge pattern, session-boundary flush, merge-delimiter harvest — **algorithms only**, not cloud SDKs or a second SQLite fact store (relations.sqlite3 is a local SPO index beside the cube).

---

## 3. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **440 passed** (incl. A− lift suite + Hermes alignment) |
| Coverage | ~76% package lines; CLI still lighter |
| Versions aligned | `plugin.yaml` / `pyproject` / `__init__` via `check_isolation.sh` |
| Tracked `.cube` / user data in git | **none** |
| Public remote | PabloTheThinker/hermescube · `main` only |

### Strengths (0.42)
- Agent-visible Cuboasis policy + pending candidate summaries (`mode=review`)
- Sync-turn fact extracts honor `memory_policy` + vault/`user_id` tags
- System-prompt Cuboasis strip is **light** (no full L1 remap)
- Session-end records `session_end_ms` / stage timers / flush OK flag
- Blocked candidate bodies redacted to hash + reasons
- Hive assimilate/draw pass `memory_safety`
- Doctor: `--identity`/`--workspace`, version skew, effective plugin config
- Entity extract: infra allowlist (`redis`/`postgres`/…) + hashtag/handle; semver filtered

### Remaining gaps
- `provider.py` still the hub (modularization deferred)
- Live file density still vector-dominated (f16 migrator deferred)
- CLI line coverage still the weakest package slice
- Solo users can ignore hive/HQ — PURPOSE should keep “solo path” first (docs)

---

## 4. How it works for a company agent

1. Agent starts → Hermes loads SOUL + MEMORY.md + Cube system block (+ Cuboasis policy / Living strips)  
2. Each user turn → Cube **prefetch** injects top related memories (+ relational SPO assist)  
3. After reply → Cube **sync_turn** WAL-writes the exchange (vault/`user_id` tags; extracts gated by policy)  
4. Session end → triage → numeric conflict scan → capped crystalize → living pulse → growth merge (timed + flushed)  
5. After N turns → consolidate nudge in system prompt (includes Cuboasis review when review-first)

See [DAY_TO_DAY.md](DAY_TO_DAY.md) and [CUBOASIS.md](CUBOASIS.md).

---

## 5. Solo path vs fleet path

| Path | Use when | Surface |
|------|----------|---------|
| **Solo** | One Hermes home, one agent | prefetch · sync_turn · feedback · triage · Cuboasis review |
| **Fleet** | Many agents, shared hive | hive pilgrimage · HQ route/handoff · interview · curator |

Day-to-day usefulness does not require the fleet path.
