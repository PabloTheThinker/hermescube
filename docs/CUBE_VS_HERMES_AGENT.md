# HermesCube vs Hermes Agent memory (holographic)

Head-to-head: same **8 core facts** + filler scale. Both are Hermes `MemoryProvider` plugins.

| | Hermes Agent **holographic** | **HermesCube** |
|--|--|--|
| Role | Stock fact store (`fact_store`) | User plugin + `.cube` archive |
| Write path | Explicit tool add (sync_turn no-op) | Auto `sync_turn` + manage/seed |
| Storage | SQLite + HRR (warns SNR at high N) | Columnar `.cube` L1/L2/L3 |
| Install | Bundled with Hermes | `hermes plugins install` + `hermescube update` |

**Not scored:** hot `MEMORY.md` / `USER.md` (always-on Hermes inject).

_Bench stamp: 2026-07-22T14:02:48.934341+00:00_

## Prefetch latency & hit rate

| Approx N | Cube avg ms | Holo avg ms | Cube hit | Holo hit |
|----------|------------:|------------:|---------:|---------:|
| 8 | 0.663 | 0.584 | 1.0 | 1.0 |
| 58 | 3.151 | 0.562 | 1.0 | 1.0 |
| 208 | 9.193 | 0.546 | 1.0 | 1.0 |
| 508 | 20.943 | 0.655 | 1.0 | 1.0 |
| 1008 | 40.174 | 0.626 | 1.0 | 1.0 |

## Honest read

1. **Hit rate:** both **1.0** on core facts at every N tested (through ~1000).
2. **Prefetch speed:** holographic wins raw ms (sub-ms even at 1k) — optimized fact index.
3. **Cube** stays interactive (≈40 ms @1k) but is not the latency champ yet.
4. **Holographic** emits “HRR near capacity / SNR degrade” warnings as N grows; Cube does not spam that path.
5. **Product gap Cube wins:** conversation auto-capture, durable-vs-noise ranking, typed layers, `hermescube update` without wiping user cube, sleep consolidate.
6. **Product gap Holo wins:** entity `probe`/`reason` tools, faster pure fact prefetch.

## Recommendation

- Everyday agent that should **remember chats** → **HermesCube** (`memory.provider: hermescube`).
- Explicit structured fact graph + algebraic tools → stock **holographic** (or both if Hermes allows — usually one provider).
- Always keep tight **MEMORY.md** for doctrine either way.

## Reproduce

```bash
python3 $HERMES_HOME/hermescube-lab/run_cube_vs_agent.py
# results → $HERMES_HOME/hermescube-lab/results/cube-vs-agent-scale.json
```
