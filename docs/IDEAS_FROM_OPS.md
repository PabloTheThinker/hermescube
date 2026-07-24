# Ideas log — conversation → Cube edge (public-safe)

## Inspiration sources (this arc)
- AppleCare → **continuity**: memories that keep the “employee” employed (Care)
- Animus / high-load FOA → small working set, deep Mneme underneath
- Day-to-day no-loss → WAL + sleep replay
- Client agents → same socket, isolated cubes (no cross-pollution)
- Biological CLS / Hopfield / Hebbian → Engram Net + sleep_replay

## Shipped
| Idea | Module |
|------|--------|
| Associative neural field | `engram_net.py` |
| Offline consolidation | `sleep_replay.py` + manage `replay` + session_end |
| Measure IR | `scripts/labeled_ir_bench.py` |
| Repo isolation | `check_isolation.sh` |

## Next (not yet)
- Prospective memory: `focus` intents that boost until `resolve` success
- Care-critical tag half-life (generic flag in entry.data, not brand-specific)
- Animus strip = top engram hubs only under load
- Night cron template in docs only (user installs)
