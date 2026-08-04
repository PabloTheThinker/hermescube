# About HermesCube

**HermesCube is the library under [Hermes Agent](https://github.com/NousResearch/hermes-agent) — the deep-memory core of a Hermes base.**

It is a durable, semantic, offline **book** of long memory (`memory.cube`) private to your `$HERMES_HOME`. Hot `MEMORY.md` stays the desk card catalog. HermesCube is not a second agent, not cloud memory SaaS, and not a replacement for Hermes’s built-in memory tools. One plugin socket. One living library. Optional [Hermespace](https://github.com/PabloTheThinker/hermespace) is the reading desk that runs on Cube power.

---

## The idea (library language)

| You say… | Product |
|----------|---------|
| **Library building** | HermesCube |
| **One book** | `memory.cube` per Hermes home / profile |
| **Chapter / arc** | Crystals, growth eras, dream consolidations, project spines |
| **Page / passage** | Landmark, belief, trait, relationship entries |
| **Card catalog** | Hot MEMORY.md + journey graph |
| **Heart / provenance** | Blackbox flight records — prove runs, don’t vibe “done” |
| **Librarian on duty** | Hermes Agent this turn |
| **Inter-library loan** | Optional Hive between agents |

A session log is CCTV tape: huge, linear, weak recall.  
A cube is a **bound book**: append pages, index by meaning, bind chapters over months and years.

---

## What it is for

| You want… | HermesCube gives you… |
|-----------|------------------------|
| Memories that survive context compression | Append-only `.cube` + WAL under `$HERMES_HOME/memories/` |
| Recall by *meaning*, not only grep | HAR + learned embeddings + entity/relation graphs (no embedding API) |
| Proof that work happened | [Blackbox](docs/BLACKBOX.md) capture / prove / breathe |
| Safe lock if disaster | [Checkpoint ark](docs/CHECKPOINT.md) — clone book + core identity |
| Safe writes under load | Cuboasis review-first gates, threat scan, atomic replace |
| Growth over months | Living version, diary (`CUBE.md`), maturity eras, curator |
| Optional multi-agent life | Hive pilgrimage, Fleet HQ, peer interviews, CubeDream circles |

---

## How it sits in Hermes base

```
Hermes base (the house)
├── Hermes Agent          hands + voice + tools (librarian on duty)
├── MEMORY.md             desk card catalog (tiny, always open)
├── state.db              reading-room CCTV → blackbox receipts
├── skills                procedure binders
└── HermesCube            ★ the library
    ├── memory.cube         the bound volume (SoT for long-tail)
    ├── blackbox            heart provenance (flights + prove)
    ├── relations           cross-references
    ├── Cuboasis            quiet rooms / governance
    ├── space_bridge        inject / seal / charge → Hermespace desk
    └── hive (opt-in)       inter-library loan
```

**Solo path (default):** doctor · query · feedback · blackbox · optional dream solo.  
**Fleet path (opt-in):** hive / HQ / interviews / dream circles.

---

## Product layers (0.50 — library direction)

1. **Warehouse (the book)** — `.cube`, HAR, WAL, mirror from MEMORY.md  
2. **Blackbox (the heart stamp)** — redacted flights, integrity, claim prove, breathe cycle  
3. **Cuboasis** — review-first policy, space, Cubewave  
4. **Living growth (editions)** — Eden → Elder; diary; curator  
5. **Hive + HQ + interviews** — collective shelves (opt-in)  
6. **CubeDream** — night chapter-binding; MEMORY.md *proposals only*  
7. **Hermespace heart + center** — circulatory beat; organ map includes blackbox  

Full stack: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

---

## Non-goals

- Not a second brain or weight store  
- Not cloud sync or a hosted memory product  
- Not a replacement for `MEMORY.md`  
- Not “open every organ on day one” — remember + prove + doctor first  

---

## Where to go next

| Doc | Audience |
|-----|----------|
| [README.md](README.md) | Install, day-one commands |
| [PURPOSE.md](PURPOSE.md) | North star (Hermes-base core) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Full Architecture Blueprint |
| [docs/BLACKBOX.md](docs/BLACKBOX.md) | Flight recorder |
| [docs/HERMESPACE.md](docs/HERMESPACE.md) · [ANATOMY.md](docs/ANATOMY.md) | Heart / center |
| [docs/HERMESPACE_PRODUCTION.md](docs/HERMESPACE_PRODUCTION.md) | global-workspace research → Hermes + Hermespace production |
| [docs/README.md](docs/README.md) | Full index |

**One sentence:**  
*HermesCube is the library under Hermes — a local book of long memory that compresses life into chapters, with a heart that can prove what was actually done.*

**License:** MIT — [LICENSE](LICENSE)  
**Home:** https://github.com/PabloTheThinker/hermescube
