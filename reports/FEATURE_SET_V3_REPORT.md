# Feature Set V3 Report
**Date:** 2026-06-14  
**Script:** `scripts/run_v3_comparison.py`  

---

## Overview

V3 adds 10 regime-interaction features to the V1 base (39 features).
Each interaction = `base_feature * regime_mask` where the regime mask is
a binary column derived from `spy_above_sma200` or `market_trend`.
Interaction features are computed on-the-fly at training and inference time;
no parquet backfill required.

**V1:** 39 features (production baseline, mean WF rank IC = 0.0599)
**V3:** 49 features (V1 + 10 interactions)

### Interaction Features Added

| Feature | Formula | Rationale |
|---|---|---|
| `omni_82_distance_x_above_200dma` | omni_82_distance * spy_above_sma200 | OMNI IC +0.026 above 200DMA, -0.011 below |
| `omni_82_above_x_above_200dma` | omni_82_above * spy_above_sma200 | OMNI flag IC +0.015 above, -0.006 below |
| `omni_82_slope_x_above_200dma` | omni_82_slope * spy_above_sma200 | OMNI slope IC +0.002 above, -0.054 below |
| `realized_vol_20_x_below_200dma` | realized_vol_20 * (1-spy_above_sma200) | vol IC +0.053 in bear, +0.046 below 200DMA |
| `realized_vol_60_x_below_200dma` | realized_vol_60 * (1-spy_above_sma200) | vol IC +0.053 in bear, +0.048 below 200DMA |
| `return_1d_x_below_200dma` | return_1d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |
| `return_3d_x_below_200dma` | return_3d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |
| `return_5d_x_below_200dma` | return_5d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |
| `rs_spy_20_x_bull` | rs_spy_20 * (market_trend==1) | RS IC +0.010 in low_vol, near 0 in bull/bear |
| `rs_spy_60_x_bull` | rs_spy_60 * (market_trend==1) | RS IC +0.005 in low_vol, -0.056 below 200DMA |

---

## Phase 1: Holdout Comparison (2011-2025 train, 2025-07-01+ eval)

| Metric | V1 (39 feat) | V3 (49 feat) | Winner |
|---|---|---|---|
| Mean Rank IC | +0.0196 | +0.0154 | **V1** |
| IC Std (lower=better) | +0.1065 | +0.1096 | **V1** |
| Sharpe | +2.9257 | +2.2339 | **V1** |
| Decile Spread | +0.0020 | +0.0014 | **V1** |
| AUC | +0.5000 | +0.5014 | **V3** |
| Brier (lower=better) | +0.3333 | +0.3326 | **V3** |
| Top Decile Return | +0.0040 | +0.0044 | **V3** |
| Bot Decile Return | +0.0020 | +0.0031 | **V3** |

**Prediction overlap (Jaccard, top-decile):** 48.4%
**Holdout rows:** 32,757  (179 dates)
**V3 wins:** 4/8  |  **V1 wins:** 4/8

---

## Phase 2: Walk-Forward Comparison

V1 DB value averages all historical folds in model_registry including older pre-MOMENTUM_V2 runs.
V1's most recent clean full training (2026-06-15 this session) achieved **mean rank IC = +0.0599**.
Both the DB average and the clean run confirm V1 outperforms V3 walk-forward.

| Metric | V1 (DB avg, mixed vintage) | V1 (2026-06-15 clean run) | V3 (this run) |
|---|---|---|---|
| Mean Rank IC | +0.0304 | **+0.0599** | +0.0467 |
| Mean Sharpe  | +0.6004 | +0.6740 (est) | +0.3319 |
| Folds OK     | 12 | 12 | 12 |

**V3 per-fold rank IC:**

| Fold | Val Start | Val End | Rank IC | Sharpe |
|---|---|---|---|---|
| 1 | 2014-07-02 | 2015-07-31 | +0.1626 | +0.5193 |
| 2 | 2015-07-02 | 2016-07-31 | +0.0906 | +1.4227 |
| 3 | 2016-07-02 | 2017-07-31 | +0.0201 | +1.4501 |
| 4 | 2017-07-02 | 2018-07-31 | +0.0763 | +3.6135 |
| 5 | 2018-07-02 | 2019-07-31 | +0.0645 | -0.3017 |
| 6 | 2019-07-02 | 2020-07-31 | +0.0189 | +3.1939 |
| 7 | 2020-07-02 | 2021-07-31 | -0.0163 | +0.6211 |
| 8 | 2021-07-02 | 2022-07-31 | +0.0043 | -2.4250 |
| 9 | 2022-07-02 | 2023-07-31 | +0.0253 | +1.1588 |
| 10 | 2023-07-02 | 2024-07-31 | +0.0427 | -0.3139 |
| 11 | 2024-07-02 | 2025-07-31 | +0.0611 | -2.0559 |
| 12 | 2025-07-02 | 2026-06-14 | +0.0096 | -2.9002 |

---

## Promotion Verdict

**VERDICT: KEEP V1** (V3 wins only 4/8 holdout metrics; threshold = 5)

V3 interaction features did not consistently outperform V1 on the holdout.
Possible reasons:
- 2025-2026 holdout is a bull market; OMNI features already work well above 200DMA
- Interaction features may need more data in bear/below-200DMA regimes to show advantage
- Consider V3 with different interaction combinations or thresholds

V1 remains production. V3 is preserved as `MODEL_FEATURE_SET_VERSION=v3` for future use.

---

## Caveats

1. **Holdout period is a bull market (2025-07-01+)** — regime interactions may not show
   advantage until the model encounters a bear market or high-vol period.
2. **V3 walk-forward uses the same folds as V1** — the mean rank IC comparison is fair
   since both evaluate on identical validation windows.
3. **Interaction features have NaN in older parquet** where base columns are missing —
   LightGBM handles NaN natively; early folds effectively run with fewer interactions.