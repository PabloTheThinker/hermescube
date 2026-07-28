# HermesCube project assessment & audit

**Date:** 2026-07-27  
**Version:** 0.46.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Deep read of tree + pytest (460) + isolation + CubeDream L1/L2 ship + prior 0.42–0.45 lifts

---

## 1. Executive verdict

| # | Dimension | Grade | Note |
|---|-----------|:-----:|------|
| 1 | Ship readiness | **A−** | Clean `main`, isolation OK, CI matrix; no PyPI package yet (README badges fixed to git/CI) |
| 2 | Agent onboarding | **A** | Instant manual + auto-bootstrap + operate/import skills |
| 3 | Hermes MemoryProvider fidelity | **A−** | Full hook surface; no live Hermes ABC pin in CI |
| 4 | Day-to-day no-loss | **A** | sync_turn persist; MEMORY.md mirror; session-end flush |
| 5 | Recall quality | **A−** | HAR + Engram + Cubewave + entities; benches local-only |
| 6 | Cuboasis governance | **A** | review-first / candidates / safety / reject recall |
| 7 | Isolation | **A** | Nested sidecars + vault / user_id soft affinity |
| 8 | Session-end / cost | **A−** | Timed pipeline; sleep_replay still thinly tested |
| 9 | Fleet (hive / HQ / interview) | **A−** | Libraries + hive/HQ CLI; interview CLI thinner |
| 10 | **CubeDream (solo + together)** | **B+** | **0.46 ships L1 scheduler + L2 circle MVP**; dialogue-in-circle + auto-circle cron still open |
| 11 | Install / doctor / CLI | **A−** | doctor/dense/dream/hive; CLI cov uneven |
| 12 | Security | **A−** | Threat + memory_safety; regex residual risk |
| 13 | Docs honesty | **A−** | ASSESSMENT + CUBEDREAM aligned to shipped vs design |
| 14 | Code health | **B+** | Manage peeled; provider still ~2500 LOC |
| 15 | Test quality | **A−** | **460 passed**; dream/circle covered; manage_warehouse/cli thinner |

**Verdict: Ship and run** for solo Hermes memory. **Dreaming together (Chorus)** is now real code — open → signal → score → close → draw — not just a design note. Remaining dream work is Conversation (interview-in-circle) and auto-circle cron.

---

## 2. Top strengths

1. Hermes-shaped MemoryProvider with flush discipline and hot-markdown mirroring  
2. Cuboasis review-first governance with concrete tests  
3. Recall stack (HAR / Engram / Cubewave / entities) without hard isolation drops  
4. Instant agent onboarding (manual + bootstrap + skills)  
5. **Multi-layer CubeDream** — L1 soul diary/scheduler + L2 shared circle with together-bonus  

## 3. Top gaps / risks

1. `provider.py` still ~2500 LOC (orchestration hub)  
2. No PyPI publish; install is git/plugin path  
3. Circle dialogue (interview inside dream) and adversarial skim not shipped  
4. Uneven CLI / manage_warehouse coverage  
5. No live Hermes ABC assertion in CI  

## 4. CubeDream status (0.46)

| Piece | Status | Path |
|-------|--------|------|
| L1 due-reasons + diary | **Shipped** | `hermescube/dream.py` |
| L1 solo apply (replay/crystalize) | **Shipped** | `dream.run_solo_dream(apply=…)` |
| Prompt reminder strip | **Shipped** | `agent_manual` + `reminder_strip` |
| L2 circle open/join/signal/score/close/draw | **Shipped** | `hermescube/dream_circle.py` |
| Together bonus (multi-agent key agree) | **Shipped** | `TOGETHER_BONUS` / `canonical_key` |
| Hive dream lock on close | **Shipped** | `hive/.locks/dream.lock` |
| Manage + CLI | **Shipped** | `action=dream`, `hermescube dream …` |
| Dialogue-in-circle | **Design** | reuse `interview.py` next |
| Auto-circle night cron | **Design** | `dream.mode=auto-circle` |
| L4 MEMORY.md proposals | **Design** | never auto-apply |

See [CUBEDREAM.md](CUBEDREAM.md).

## 5. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **460 passed** |
| Versions | `0.46.0` aligned (`check_isolation.sh` OK) |
| Tracked user `.cube` | **none** |
| Dream/circle modules | **present** |

## 6. Next three ship items

1. Circle **Conversation** — wire `interview.peer_dialogue` under `circles/<id>/dialogues`  
2. `auto-circle` quiet-hour cron using soul offerings as Chorus signals  
3. Peel more of `provider.py` (search/probe/feedback) + interview CLI e2e tests  

## 7. Metrics

| Metric | Value |
|--------|------:|
| Tests | 460 |
| `provider.py` LOC | ~2507 |
| Manage actions | 32 (incl. `dream`) |
| Largest modules | provider · cli · har · cube · interview |
