# HermesCube project assessment & audit

**Date:** 2026-07-27  
**Version:** 0.44.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Sub-A lift (provider modularization, CLI doctor/dense, entity mine-on-pulse) + onboarding + Hermes contract

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness (public) | **A** | Clean `main`, isolation check, 451 tests, no open PRs |
| Agent onboarding | **A** | Instant prompt manual + auto-bootstrap MEMORY.md + bundled skills |
| Hermes Agent integration | **A** | Native MemoryProvider; profile/workspace/`user_id`; session-end flush |
| Day-to-day no-loss | **A** | WAL sync_turn; MEMORY.md mirror; compaction-safe extract |
| Recall quality + speed | **A** | IR/assoc + mine-on-pulse entity landmarks + expanded infra allowlist |
| Compounding usefulness | **A** | Triage→crystalize→merge→relations agent-visible |
| Cuboasis / governance | **A** | Review-first wired into sync extract; prompt queue + redact blocked candidates |
| Multi-project / gateway isolation | **A** | Nested sidecars + vault/`user_id`/`user_id_alt`; prefetch cache keyed; peer_card nests |
| Night-job / session-end cost | **A** | Pipeline in `session_end.py`; timers; observe capped; idle skip evolve |
| Fleet / hive / growth stack | **A** | Solo-path first in manual; hive gated; assimilate/draw safety |
| Install / update UX | **A** | Doctor density+bootstrap; `hermescube dense`; install seeds skills |
| Security baseline | **A** | JWT/Slack/ghp gates; doctrine-override threats; blocked candidate redaction |
| Docs honesty | **A** | ASSESSMENT aligned to 0.44 |
| Code health | **A−** | Prompt + session-end extracted; manage handlers still concentrated |
| CLI coverage | **A−** | Doctor/dense/bootstrap covered; hive/hq CLI still lighter |

**Verdict: Ship and run.** Suitable as the deep memory layer for Hermes-based company agents. Next polish: keep peeling manage handlers from `provider.py`.

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
| Tests | **451 passed** |
| Versions aligned | `plugin.yaml` / `pyproject` / `__init__` via `check_isolation.sh` |
| Tracked `.cube` / user data in git | **none** |
| Public remote | PabloTheThinker/hermescube · `main` only |

### Strengths (0.44)
- `agent_manual.py` + `session_end.py` peeled from the provider hub
- Entity mine-on-pulse persists `[ENTITY]` landmarks for assoc recall
- `hermescube dense` portable text companion; doctor surfaces density + bootstrap
- Instant onboarding (0.43) + A− closure (0.42) still hold

### Remaining gaps
- Manage handlers still live mostly in `provider.py`
- In-place f16 vector rewrite remains a future format bump (dense export covers ship/backup)
- Hive/HQ CLI paths still lighter on tests

---

## 4. How it works for a company agent

1. Agent starts → Hermes loads SOUL + MEMORY.md + Cube operating manual (+ Cuboasis / Living strips)  
2. Empty warehouse → auto-bootstrap imports hot markdown + installs operate/import skills  
3. Each turn → prefetch + sync_turn (policy-gated extracts)  
4. Session end → triage → conflicts → crystalize → pulse/entity-mine → growth merge (timed + flushed)  

See [DAY_TO_DAY.md](DAY_TO_DAY.md) and [CUBOASIS.md](CUBOASIS.md).

---

## 5. Solo path vs fleet path

| Path | Use when | Surface |
|------|----------|---------|
| **Solo** | One Hermes home, one agent | prefetch · sync_turn · feedback · triage · Cuboasis review |
| **Fleet** | Many agents, shared hive | hive pilgrimage · HQ route/handoff · interview · curator |

Day-to-day usefulness does not require the fleet path.
