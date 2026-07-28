# HermesCube project assessment & audit

**Date:** 2026-07-27  
**Version:** 0.47.0  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Basis:** Full CubeDream stack (L1–L4 + together modes) + manage/tools peels + 466 tests

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness | **A−** | Clean main, isolation OK; install via git/plugin (no PyPI) |
| Agent onboarding | **A** | Manual + bootstrap + skills |
| Hermes MemoryProvider | **A−** | Full hooks; no live ABC pin in CI |
| Day-to-day no-loss | **A** | sync / mirror / flush |
| Recall quality | **A−** | HAR + Engram + Cubewave + entities |
| Cuboasis governance | **A** | review-first + candidates + safety |
| Isolation | **A** | Nested sidecars + vault / user_id |
| Session-end / cost | **A−** | Timed pipeline |
| Fleet | **A−** | hive/HQ/interview; CLI covered for interview list |
| **CubeDream** | **A−** | L1 solo · L2 Chorus+Conversation · auto-circle · skim · L4 proposals |
| Install / doctor / CLI | **A−** | dream/dense/hive/hq/interview |
| Security | **A−** | Threat + memory_safety on signals/offers |
| Docs honesty | **A** | ASSESSMENT + CUBEDREAM match shipped code |
| Code health | **A−** | Manage + tools_recall peeled; provider ~2265 LOC |
| Test quality | **A−** | **466 passed**; dream full stack covered |

**Verdict: Ship and run.** Multi-layer dreaming-together is product code: agents can chorus, interview inside a circle, auto-circle at night, skim conflicts, and stage MEMORY.md proposals without auto-applying them.

---

## 2. CubeDream matrix (0.47)

| Mode | Status | Entry |
|------|--------|-------|
| L1 soul due + diary | Shipped | `dream status` / `solo` |
| L1 apply (replay/crystalize) | Shipped | `solo --apply` |
| L2 Chorus | Shipped | `circle signal/score/close` |
| L2 Conversation | Shipped | `circle dialogue` |
| L2 Communion (close→hive) | Shipped | `circle close` + lock |
| Auto-circle night | Shipped | `dream auto-circle` |
| Adversarial skim | Shipped | `circle skim` |
| L4 MEMORY.md proposals | Shipped | `dream propose` (never apply) |

## 3. Remaining polish (not blockers)

- Stronger adversarial corpus / shadow-trial reports  
- Cron recipe docs for `auto-circle`  
- Live Hermes ABC pin in CI  
- Optional PyPI publish  

## 4. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **466 passed** |
| Versions | **0.47.0** aligned |
| Isolation | OK |
| Dream modules | `dream.py`, `dream_circle.py`, `manage_dream.py`, `tools_recall.py` |
