# HermesCube vs Hermes Agent holographic — hyper 0.6

After lex-first two-stage + resident cache (studied holo pipeline; Cube store).

_Stamp: 2026-07-22T18:00:23.632210+00:00_

| N | Cube ms | Holo ms | Cube hit | Holo hit |
|--:|--------:|--------:|---------:|---------:|
| 8 | 0.276 | 0.601 | 1.0 | 1.0 |
| 58 | 0.123 | 0.61 | 1.0 | 1.0 |
| 208 | 0.12 | 0.584 | 1.0 | 1.0 |
| 508 | 0.122 | 0.59 | 1.0 | 1.0 |
| 1008 | 0.125 | 0.582 | 1.0 | 1.0 |

Warm-cache microbench (Cube alone @1008): **~0.12 ms**, hit 1.0.
