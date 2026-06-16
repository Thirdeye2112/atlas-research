# Atlas Behavior-Aware Similarity Engine - Validation Report
Generated: 2026-06-16  |  Walk-forward split: 2026-05-20
IS: 32,350 candles  |  OOS: 13,869 candles

## 1. Executive Summary

- Best variant (K=50, H=6): **raw_candle** (49.1% hit rate)
- Technical baseline HR: 49.1%
- Behavior-aware HR: 49.1%
- Behavior+context HR: 49.1%
- **Promotion decision: DO NOT PROMOTE -- v2 does not beat technical baseline by >1pp OOS**

## 2. Comparison Table (Primary K=50, Horizon=6)

| Variant                                             | Hit Rate   |   Expectancy |   P/F |   Top-Q Exp |   Cal MSE |
|-----------------------------------------------------|------------|--------------|-------|-------------|-----------|
| Raw Candle (shape+volume, 7 dims)                   | 49.1%      |       0.0011 |  1.01 |      0.0132 |    0.4862 |
| Technical (shape+vol+trend+momentum, 12 dims)       | 49.1%      |       0.0011 |  1.01 |      0.0096 |    0.4883 |
| Behavior-Aware (36 dims, behavior 1.5x)             | 49.1%      |       0.0011 |  1.01 |      0.016  |    0.4867 |
| Behavior+Context (36 dims, behavior 2.0x, ctx 3.0x) | 49.1%      |       0.0011 |  1.01 |     -0.0036 |    0.4904 |

## 3. K Sensitivity -- Behavior-Aware Variant

|   K | Hit Rate   |   Expectancy |   P/F |   Top-Q Exp |
|-----|------------|--------------|-------|-------------|
|  25 | 49.1%      |       0.0011 |  1.01 |      0.0087 |
|  50 | 49.1%      |       0.0011 |  1.01 |      0.016  |
| 100 | 49.1%      |       0.0011 |  1.01 |      0.0257 |

## 4. Horizon Sweep -- Behavior-Aware Variant (K=50)

| Horizon           | Hit Rate   |   Expectancy |   P/F |
|-------------------|------------|--------------|-------|
| 1 candles (5m)    | 49.9%      |       0.0004 |  1.01 |
| 3 candles (15m)   | 49.7%      |       0.0008 |  1.01 |
| 6 candles (30m)   | 49.1%      |       0.0011 |  1.01 |
| 12 candles (60m)  | 49.2%      |       0.0011 |  1    |
| 24 candles (120m) | 49.5%      |       0.0044 |  1.01 |

## 5. Behavior Label Importance (OOS, K=50, H=6)

**Informative behaviors (|hit lift| >= 3pp, n >= 20):**

| Behavior             |   N (with) | HR With   | HR Without   | Hit Lift   |   Exp Lift |
|----------------------|------------|-----------|--------------|------------|------------|
| LOW_VOL_DRIFT_UP     |         78 | 71.8%     | 49.0%        | +22.8%     |     0.2846 |
| RSI_OVERSOLD_RECLAIM |        312 | 63.1%     | 48.8%        | +14.4%     |     0.1641 |
| ABOVE_ALL_EMAS       |       6256 | 53.3%     | 45.6%        | +7.7%      |     0.0649 |
| NEAR_52W_HIGH        |       3477 | 54.2%     | 47.3%        | +6.9%      |     0.0347 |
| RSI_OVERBOUGHT       |       2069 | 53.9%     | 48.2%        | +5.7%      |     0.0155 |
| GAP_UP_LARGE         |        899 | 53.5%     | 48.8%        | +4.7%      |     0.1158 |
| MACD_BULL_CROSS      |        468 | 52.8%     | 49.0%        | +3.8%      |     0.1924 |
| LARGE_DAILY_RANGE    |       5033 | 46.9%     | 50.3%        | -3.4%      |    -0.0001 |
| GAP_DOWN_LARGE       |        390 | 45.4%     | 49.2%        | -3.8%      |    -0.0455 |
| GAP_DOWN_SMALL       |       3239 | 45.1%     | 50.3%        | -5.2%      |    -0.082  |
| MACD_BEAR_CROSS      |        665 | 40.8%     | 49.5%        | -8.8%      |    -0.1376 |
| BELOW_ALL_EMAS       |       1601 | 40.3%     | 50.2%        | -10.0%     |    -0.1017 |

**Full behavior importance table (sorted by hit lift):**

| Behavior             |    N | HR With   | HR Without   | Hit Lift   | Informative   |
|----------------------|------|-----------|--------------|------------|---------------|
| LOW_VOL_DRIFT_UP     |   78 | 71.8%     | 49.0%        | +22.8%     | YES           |
| RSI_OVERSOLD_RECLAIM |  312 | 63.1%     | 48.8%        | +14.4%     | YES           |
| ABOVE_ALL_EMAS       | 6256 | 53.3%     | 45.6%        | +7.7%      | YES           |
| NEAR_52W_HIGH        | 3477 | 54.2%     | 47.3%        | +6.9%      | YES           |
| RSI_OVERBOUGHT       | 2069 | 53.9%     | 48.2%        | +5.7%      | YES           |
| GAP_UP_LARGE         |  899 | 53.5%     | 48.8%        | +4.7%      | YES           |
| MACD_BULL_CROSS      |  468 | 52.8%     | 49.0%        | +3.8%      | YES           |
| GAP_UP_SMALL         | 3087 | 49.3%     | 49.0%        | +0.3%      | -             |
| INSIDE_DAY           | 1482 | 47.6%     | 49.3%        | -1.6%      | -             |
| ATR_EXPANSION        |  234 | 47.0%     | 49.1%        | -2.1%      | -             |
| LARGE_DAILY_RANGE    | 5033 | 46.9%     | 50.3%        | -3.4%      | YES           |
| GAP_DOWN_LARGE       |  390 | 45.4%     | 49.2%        | -3.8%      | YES           |
| GAP_DOWN_SMALL       | 3239 | 45.1%     | 50.3%        | -5.2%      | YES           |
| MACD_BEAR_CROSS      |  665 | 40.8%     | 49.5%        | -8.8%      | YES           |
| BELOW_ALL_EMAS       | 1601 | 40.3%     | 50.2%        | -10.0%     | YES           |
| ATR_SQUEEZE          |    0 | N/A       | 49.1%        | +nan%      | -             |
| DEATH_CROSS          |    0 | N/A       | 49.1%        | +nan%      | -             |
| GOLDEN_CROSS         |    0 | N/A       | 49.1%        | +nan%      | -             |
| VOL_SURGE_BEAR       |    0 | N/A       | 49.1%        | +nan%      | -             |
| VOL_SURGE_BULL       |    0 | N/A       | 49.1%        | +nan%      | -             |

## 6. MFE / MAE Prediction Accuracy (behavior_aware, K=50)

| Horizon   |   MFE MSE |   MAE MSE |
|-----------|-----------|-----------|
| H=1       |    0.5951 |    0.5182 |
| H=3       |    0.5951 |    0.5182 |
| H=6       |    0.5951 |    0.5182 |
| H=12      |    0.5951 |    0.5182 |
| H=24      |    0.5951 |    0.5182 |

## 7. Full Results Grid (all variants, K=50)

| Variant           | Horizon   | Hit Rate   |   Expectancy |   P/F |
|-------------------|-----------|------------|--------------|-------|
| raw_candle        | H=1       | 49.9%      |       0.0004 |  1.01 |
| raw_candle        | H=3       | 49.7%      |       0.0008 |  1.01 |
| raw_candle        | H=6       | 49.1%      |       0.0011 |  1.01 |
| raw_candle        | H=12      | 49.2%      |       0.0011 |  1    |
| raw_candle        | H=24      | 49.5%      |       0.0044 |  1.01 |
| technical         | H=1       | 49.9%      |       0.0004 |  1.01 |
| technical         | H=3       | 49.7%      |       0.0008 |  1.01 |
| technical         | H=6       | 49.1%      |       0.0011 |  1.01 |
| technical         | H=12      | 49.2%      |       0.0011 |  1    |
| technical         | H=24      | 49.5%      |       0.0044 |  1.01 |
| behavior_aware    | H=1       | 49.9%      |       0.0004 |  1.01 |
| behavior_aware    | H=3       | 49.7%      |       0.0008 |  1.01 |
| behavior_aware    | H=6       | 49.1%      |       0.0011 |  1.01 |
| behavior_aware    | H=12      | 49.2%      |       0.0011 |  1    |
| behavior_aware    | H=24      | 49.5%      |       0.0044 |  1.01 |
| behavior_plus_ctx | H=1       | 49.9%      |       0.0004 |  1.01 |
| behavior_plus_ctx | H=3       | 49.7%      |       0.0008 |  1.01 |
| behavior_plus_ctx | H=6       | 49.1%      |       0.0011 |  1.01 |
| behavior_plus_ctx | H=12      | 49.2%      |       0.0011 |  1    |
| behavior_plus_ctx | H=24      | 49.5%      |       0.0044 |  1.01 |

## 8. Methodology

- **Walk-forward**: strict 70/30 chronological split; IS builds KNN index, OOS queries against it.
- **No leakage**: OOS rows never appear in IS index.
- **Variants**: feature subsets with their own weight arrays, no shared state.
- **Hit rate**: fraction of OOS candles where predicted direction matches actual direction.
- **Expectancy**: (avg_win * win_rate) - (avg_loss * loss_rate) in % return units.
- **Top-Q Exp**: expectancy of OOS rows whose predicted return falls in top quartile.
- **Calibration MSE**: mean squared error between predicted (mean of matched IS returns) and actual OOS return.
- **MFE/MAE accuracy**: MSE between predicted (mean of matched IS MFE_12/MAE_12) and actual OOS MFE_12/MAE_12.
- **Behavior importance**: For each behavior, compare OOS hit rate of candles WITH vs WITHOUT that behavior active.
  Informative threshold: |hit_lift| >= 3pp AND n_with >= 20.

## 9. Promotion Policy

v2 replaces v1 in the nightly pipeline only if:
- Behavior-aware OOS hit rate > technical baseline OOS hit rate + 1pp
- Based on >= 1,000 OOS candles
- At least 3 behaviors are classified as informative

**Current status: HOLD -- continue accumulating data and re-validate after 30 more trading days**
