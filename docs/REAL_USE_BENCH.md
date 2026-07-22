# Real-use benchmarks (HermesCube 0.3.7)

How operators benefit: after install, memory should **recall durable prefs/facts**
under conversational noise, stay **fast**, and **persist across sessions**.

## How to run

```bash
hermes plugins install PabloTheThinker/hermescube
cd "$HERMES_HOME/plugins/hermescube" && ./scripts/install_hermes.sh
hermescube update

# Lab outputs → $HERMES_HOME/hermescube-lab/results/ (never the git tree)
PYTHONPATH=. python3 benchmarks/real_use_bench.py
```

## Gates (pass/fail)

| Gate | Meaning | This run |
|------|---------|----------|
| durable hit rate ≥ 0.8 | Prefs/paths beat noise | **True** |
| prefetch p50 < 25 ms | Everyday snappy | **True** |
| question index OK | Q turns don't bury facts | **True** |
| cross-session OK | Restart keeps memory | **True** |
| labeled recall ≥ 0.7 | IR regression | **True** |

**Overall: PASS**

## Long-run experiment (8 rounds × ~197 entries)

| Metric | Value |
|--------|------:|
| Avg prefetch | **8.61 ms** |
| Avg hit fraction | **1.00** |
| Avg evolve (sleep) | **1378 ms** |

## What this means for others

1. Install into **your** `$HERMES_HOME` — your cube is private and portable with the profile.
2. `hermescube update` pulls code without wiping memories.
3. Prefer `hermescube_manage` / high-trust seeds for facts you care about; chat noise stays secondary.
4. Sleep/evolve is offline — hot path stays millisecond-class.

_Stamp real-use: 20260722T135258Z · long-exp: 2026-07-22T13:53:45.696996+00:00_
