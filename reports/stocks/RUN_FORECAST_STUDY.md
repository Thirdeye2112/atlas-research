# Whole-run forecast from fewest candles (1045 runs, 10 names)

A = ultimate high, riding pullbacks until a lower-high reversal. Runs >= 5.0%, peak > 3 bars out. Daily candles (finest data = 5m; no 1-min in DB).

- Whole-run A: median **14.1%** over ~15 bars.
- Consolidation-breakout runs: 169 (median 17.2%).

## % of the total run each candle contributes (median)

- by candle 1: **24%** of A realized (candle 1 ≈ 24%)
- by candle 2: **28%** of A realized (candle 2 ≈ 5%)
- by candle 3: **33%** of A realized (candle 3 ≈ 5%)

## Predicting the whole-run A — OOS R² by candles used

| candles | ALL (lin/GBM) | consolidation-breakout (lin/GBM) |
|---|---|---|
| 1..1 | 0.060/-0.033 (n=978) | n/a |
| 1..2 | 0.018/-0.061 (n=978) | n/a |
| 1..3 | 0.005/-0.112 (n=978) | n/a |

_Fewest candles for a tradeable target = where R² is usefully > 0 and stops climbing. Compare ALL vs breakout to see if the consolidation context is the cleaner, more forecastable setup._