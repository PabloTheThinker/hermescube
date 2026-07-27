# HermesCube project assessment & audit

**Date:** 2026-07-26  
**Version:** 0.37.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Live dogfood path + Hermes-aligned usefulness phases (0.30–0.37) + research against [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness (public) | **A** | Clean `main`, isolation check, 400+ tests, no open stale PRs |
| Hermes Agent integration | **A** | Native MemoryProvider; honor profile/workspace/`user_id`; session-end flush |
| Day-to-day no-loss | **A** | WAL sync_turn; MEMORY.md mirror; compaction-safe extract |
| Recall quality + speed | **A** | IR 1.0 / assoc ≥0.8; holo-style trust×rank + entity overlap; prefetch warm |
| Compounding usefulness | **A** | Triage→crystalize→merge→relations agent-visible (strip + Hermes-aligned nudge) |
| Multi-project / gateway isolation | **A−** | Nested sidecars + vault + soft `user_id` filter; unlabeled never hard-dropped |
| Night-job / session-end cost | **A−** | Single L1 + capped crystalize + flush before switch |
| Fleet / hive / growth stack | **A−** | On main (0.22–0.29); not re-imported from AgentDrive OS |
| Install / update UX | **A−** | plugins install + `hermescube update` |
| Code health | **B** | Powerful surface; `provider.py` still large |

**Verdict: Ship and run.** Suitable as the deep memory layer for Hermes-based company agents. A− leftovers are polish (entity extraction recall, provider modularization), not blockers.

---

## 2. What the product is

HermesCube is a **Hermes Agent memory provider plugin** plus a **binary `.cube` archive**:

- Code lives in the open repo / `$HERMES_HOME/plugins/hermescube`
- **User memory** lives only under `$HERMES_HOME/memories/` (never the git tree)
- Hot `MEMORY.md` / `USER.md` stay Hermes-native; Cube is the **warehouse**

Borrowed from official Hermes holographic / MemoryManager: trust-weighted IR, consolidate nudge pattern, session-boundary flush, merge-delimiter harvest — **algorithms only**, not cloud SDKs or a second SQLite fact store.

---

## 3. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **405+ passed** (incl. Hermes alignment suite) |
| Assoc / IR gates | assoc_recall ≥ 0.8 · IR probes 1.0 |
| Versions aligned | `plugin.yaml` / `pyproject` / `__init__` via `check_isolation.sh` |
| Tracked `.cube` / user data in git | **none** |
| Public remote | PabloTheThinker/hermescube · `main` only |

### Strengths
- Agent-visible compounding (Living strip + system-prompt consolidate nudge)
- Profile/workspace sidecar nest + vault/`user_id` soft affinity
- Session-end cost controls + flush before Hermes session switch
- Compaction-safe auto-extract (pre-delimiter harvest)

### Remaining gaps
- Entity *extraction* recall still soft (~0.45 on assoc bench corpus) — annotation rate high once entities land
- `provider.py` still the hub (modularization deferred)
- Live file density still vector-dominated (f16 migrator deferred)

---

## 4. How it works for a company agent

1. Agent starts → Hermes loads SOUL + MEMORY.md + Cube system block (+ living/consolidate strips)  
2. Each user turn → Cube **prefetch** injects top related memories (+ relational SPO assist)  
3. After reply → Cube **sync_turn** WAL-writes the exchange (vault/`user_id` tags when set)  
4. Session end → triage → numeric conflict scan → capped crystalize → living pulse → growth merge (flushed before switch)  
5. After N turns → consolidate nudge in system prompt (Hermes builtin review does not cover Cube)

See [DAY_TO_DAY.md](DAY_TO_DAY.md).
