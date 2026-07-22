# HermesCube project assessment & audit

**Date:** 2026-07-22  
**Version:** 0.6.2  
**Repo:** https://github.com/PabloTheThinker/hermescube  
**Auditor:** ILO (Vektra) — live dogfood as `memory.provider: hermescube`

---

## 1. Executive verdict

| Dimension | Grade | Note |
|-----------|:-----:|------|
| Ship readiness (public) | **A−** | Clean git, gitleaks clean, 217 tests, no secrets |
| Hermes Agent integration | **A** | Native MemoryProvider; user-home data only |
| Day-to-day no-loss | **A−** | WAL sync_turn; MEMORY.md mirror |
| Recall quality + speed | **A** | Hit 1.0 vs holographic; warm ~0.12 ms @1k |
| Install / update UX | **A−** | plugins install + `hermescube update` |
| Density / portable archive | **B+** | Live vectors heavy; dense gzip ~147× for export |
| Code health | **B+** | Framework split; provider still large |
| Differentiation vs stock holo | **A** | Auto chat + colony + void + dense pack |

**Verdict: Ship and run.** Suitable as the deep memory layer for Hermes-based company agents (Vektra/ILO pattern).

---

## 2. What the product is

HermesCube is a **Hermes Agent memory provider plugin** plus a **binary `.cube` archive**:

- Code lives in the open repo / `$HERMES_HOME/plugins/hermescube`
- **User memory** lives only under `$HERMES_HOME/memories/` (never the git tree)
- Hot `MEMORY.md` / `USER.md` stay Hermes-native; Cube is the **warehouse**

```
Hermes Agent (company runtime)
  ├── MEMORY.md / USER.md     ← short always-on doctrine
  └── memory.provider: hermescube
        ├── CubeMemoryProvider (adapter)
        ├── framework/CubeVoid (OS)
        ├── hyper recall (lex → score)
        ├── colony + mirror (interconnect)
        └── memory.cube + COLONY.md
```

---

## 3. Audit checklist

| Check | Result |
|-------|--------|
| Tests | **217 passed** |
| Secrets / gitleaks | **clean** |
| Tracked `.cube` / user data in git | **none** |
| Working tree dirty (audit time) | clean vs origin (pycache untracked only) |
| `memory.provider` live | **hermescube** |
| Doctor | OK · package 0.6.2 · cube exists |
| Public remote | PabloTheThinker/hermescube · main |

### Strengths
- Real dogfood path (ILO production provider)
- Faster warm recall than stock holographic on fair bench
- Durable turns (sync WAL) + MEMORY.md extension mirror
- Colony/mirror original interconnect (not a holo clone)
- Dense export for backup/handoff without shipping vectors
- Install/update modeled on Hermes plugins

### Gaps / risks
- Live file density still vector-dominated (f16 migrator deferred to 0.7)
- `provider.py` still large (thinned but not fully modularized)
- Plugin copy-install has no `.git` → must use `hermescube update` not only `hermes plugins update`
- Seed path slower than holo fact_store bulk insert (acceptable for chat)

---

## 4. How it works for a company agent (e.g. ILO / Vektra)

1. Agent starts → Hermes loads SOUL + MEMORY.md + Cube system block  
2. Each user turn → Cube **prefetch** injects top related memories (sub-ms warm)  
3. After reply → Cube **sync_turn** WAL-writes the exchange (no drop on crash)  
4. If agent uses built-in **memory** tool → Cube **mirrors** into archive  
5. Session end → flush + sleep evolve  
6. Ops → `hermescube doctor` / `hermescube update` / dense export for backup  

**Benefit to the agent:** more durable history, less “forgot what we decided,” without blowing the hot MEMORY char budget.

**Benefit to the company framework:** one install path for all Hermes-based agents; profile-scoped cubes; portable dense packs for handoff; same socket as other providers.

---

## 5. Does it benefit *this* agent (ILO)?

| Before (or holo-only) | With Cube 0.6.x |
|----------------------|-----------------|
| Short MEMORY.md only | MEMORY.md + deep cube |
| Manual facts | Auto turns + extract |
| Holo-class fact ms | **Cube faster warm** |
| Chat forgotten across days | WAL + cross-session tests green |

**Yes — net benefit.** Live on ILO with 15 seeded ops facts + session capture path; doctor green; update path exercised.

---

## 6. Upload & systems status (this audit)

- Public main: **0.6.2** (`b3e0b1b` class)  
- Post-audit: clean tree, re-push if assessment doc added, `hermescube update` on Parallax  

---

## 7. Recommended next (not blockers)

1. f16/lazy-vector migrator for live density (0.7)  
2. Split remaining provider tools module  
3. Optional: `hermes update` hook note in USER_GUIDE when Hermes adds plugin cascade  

*Assessment complete.*
