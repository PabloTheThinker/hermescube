# HermesCube project assessment & audit

**Date:** 2026-07-27  
**Version:** 0.45.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Manage-hub peel + fleet CLI coverage + prior onboarding / A− lifts

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness (public) | **A** | Clean `main`, isolation check, 455 tests |
| Agent onboarding | **A** | Instant prompt manual + auto-bootstrap + skills |
| Hermes Agent integration | **A** | Native MemoryProvider; profile/workspace/`user_id` |
| Day-to-day no-loss | **A** | WAL sync_turn; MEMORY.md mirror; compaction-safe |
| Recall quality + speed | **A** | IR/assoc + entity landmarks + infra allowlist |
| Compounding usefulness | **A** | Triage→crystalize→merge→relations agent-visible |
| Cuboasis / governance | **A** | Review-first; candidate capture/approve/reject |
| Multi-project / gateway isolation | **A** | Nested sidecars + vault/`user_id`/`user_id_alt` |
| Night-job / session-end cost | **A** | Timed pipeline in `session_end.py` |
| Fleet / hive / growth stack | **A** | Solo-first; hive gated; CLI + manage covered |
| Install / update UX | **A** | Doctor density+bootstrap; `hermescube dense` |
| Security baseline | **A** | Threat/JWT/Slack gates; blocked candidate redaction |
| Docs honesty | **A** | ASSESSMENT aligned to 0.45 |
| Code health | **A** | Manage handlers peeled by domain; hub ~2480 LOC |
| CLI coverage | **A** | Doctor/dense/bootstrap + hive/HQ CLI tests |

**Verdict: Ship and run.** Sub-A grades from 0.44 are closed. Remaining research backlog is medium-priority OMH ports (TTL/typed records, dreaming/eviction *proposals*), not ship blockers.

---

## 2. Research notes (0.45)

### What was concentrated
- `provider.py` held **31** manage actions (~1483 LOC): warehouse, Cuboasis spine, growth/living, fleet.
- Fleet library tests (`test_hive.py`, `test_hq.py`) were solid; **CLI** `hermescube hive|hq` had no coverage.
- OMH high-priority governance (candidates, safety, evidence_state, review-first) already landed in 0.41–0.42.

### Extraction map

| Module | Actions |
|--------|---------|
| `manage_warehouse` | bootstrap · add · remove · relations · hygiene · prune · crystalize · replay · journey |
| `manage_cuboasis` | triage · merge · space · connect · progress · cuboasis · nexus |
| `manage_growth` | growth · curate · promote · reject · drafts · pulse · forge · intents · observe · peer · witness · harness |
| `manage_fleet` | hive · hq · interview |
| `manage` | `dispatch_manage` + `known_actions` |

### Still optional (not blockers)
- In-place f16 vector rewrite (dense export remains the portable companion)
- OMH medium: typed TTL / staleness, dreaming & eviction *proposals* (never silent delete)
- Further peel of search/probe/feedback if the hub grows again

---

## 3. What the product is

HermesCube is a **Hermes Agent memory provider plugin** plus a **binary `.cube` archive**:

- Code lives in the open repo / `$HERMES_HOME/plugins/hermescube`
- **User memory** lives only under `$HERMES_HOME/memories/` (never the git tree)
- Hot `MEMORY.md` / `USER.md` stay Hermes-native; Cube is the **warehouse**
- **Cuboasis** is the pocket-dimension spine: space · wave · connections · progress · governance

---

## 4. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **455 passed** |
| Versions aligned | `plugin.yaml` / `pyproject` / `__init__` via `check_isolation.sh` |
| Tracked `.cube` / user data in git | **none** |
| Public remote | PabloTheThinker/hermescube · `main` only |

### Strengths (0.45)
- Manage domain modules; provider is orchestration + Hermes contract
- Hive/HQ CLI exercised end-to-end
- Instant onboarding (0.43) + entity/dense (0.44) still hold

### Remaining gaps
- f16 format bump deferred (honest; dense CLI covers backup/ship)
- Medium OMH ports above — design before code

---

## 5. Solo path vs fleet path

| Path | Use when | Surface |
|------|----------|---------|
| **Solo** | One Hermes home, one agent | prefetch · sync_turn · feedback · triage · Cuboasis review |
| **Fleet** | Many agents, shared hive | hive pilgrimage · HQ route/handoff · interview · curator |

Day-to-day usefulness does not require the fleet path.
