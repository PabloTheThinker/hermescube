# HermesCube vs Hermes Agent memory (holographic)

Head-to-head after **HermesCube 0.5.0** framework housing (LexIndex + Void).

| | Hermes Agent **holographic** | **HermesCube** |
|--|--|--|
| Role | Stock fact store (`fact_store`) | User plugin + `.cube` + CubeVoid |
| Write | Tool-add (sync_turn no-op) | Auto `sync_turn` + manage/seed |
| Storage | SQLite + HRR | Columnar `.cube` L1/L2/L3 |
| Install | Bundled | `hermes plugins install` + `hermescube update` |

_Bench stamp: 2026-07-22T16:26:37.037575+00:00_ · real-use gates: **PASS**

## Prefetch latency & hit rate

| Approx N | Cube avg ms | Holo avg ms | Cube hit | Holo hit |
|----------|------------:|------------:|---------:|---------:|
| 8 | 1.227 | 1.095 | 1.0 | 1.0 |
| 58 | 5.629 | 0.629 | 1.0 | 1.0 |
| 208 | 1.04 | 1.053 | 1.0 | 1.0 |
| 508 | 1.529 | 0.611 | 1.0 | 1.0 |
| 1008 | 2.325 | 0.608 | 1.0 | 1.0 |

## Assessment (0.5.0)

- **Hit rate:** tie at 1.0 on core facts through N≈1000.
- **Latency:** holographic still slightly faster at pure fact lookup; Cube closed the gap hard (was ~40ms @1k → **~2.3ms** with LexIndex).
- **Cube wins:** conversation capture, durable-vs-noise ranking, colony/mirror void, install/update UX.
- **Holo wins:** sub-ms fact index, entity probe/reason tools.
- **Real-use suite:** all operator gates green on 0.5.0.

## Reproduce

```bash
python3 $HERMES_HOME/hermescube-lab/run_cube_vs_agent.py
PYTHONPATH=. python3 benchmarks/real_use_bench.py
```
