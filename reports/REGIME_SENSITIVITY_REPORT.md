# Regime Sensitivity Report
**Date:** 2026-06-15  
**Script:** `scripts/run_regime_sensitivity.py`  
**Table:** `feature_regime_performance` (migration 0029)  
**Features evaluated:** 39 (TRAIN_FEATURES_V1)  
**Dates:** 2011-07-01 to 2026-03-17 (3,697 dates, 655,440 rows)

---

## Regime Coverage

| Regime | Rows | Dates |
|---|---|---|
| bull_market (market_trend=1) | 435,901 | 2,452 |
| bear_market (market_trend=-1) | 66,459 | 370 |
| high_vol (vol >= 66th pct) | 220,096 | 1,230 |
| low_vol (vol <= 33rd pct) | 215,305 | 1,230 |
| above_200dma (spy_above_sma200=1) | 534,974 | 3,012 |
| below_200dma (spy_above_sma200=0) | 89,732 | 499 |

---

## Classification Summary

| Class | Count |
|---|---|
| Always Useful | 0 |
| Regime Sensitive | 20 |
| Mostly Noise | 12 |
| Potentially Harmful | 7 |

**No feature passes the "Always Useful" bar** (IC > 0.01 AND sign_stability > 0.55 in ALL 6 regimes). Every feature's predictive power varies by market regime.

---

## Detailed Results

Mean IC per (feature, regime). Positive = predicts forward 5d return correctly; negative = contrarian signal.

| Feature | Class | Bull | Bear | HighVol | LowVol | >200DMA | <200DMA |
|---|---|---|---|---|---|---|---|
| **omni_82_distance** | Regime Sensitive | +0.026 | -0.011 | -0.002 | +0.038 | +0.031 | -0.020 |
| **omni_82_above** | Regime Sensitive | +0.015 | -0.006 | -0.004 | +0.020 | +0.019 | -0.014 |
| **realized_vol_60** | Regime Sensitive | +0.004 | +0.053 | +0.015 | +0.014 | +0.010 | +0.048 |
| **realized_vol_20** | Regime Sensitive | +0.002 | +0.053 | +0.017 | +0.009 | +0.009 | +0.046 |
| **rs_spy_120** | Regime Sensitive | +0.005 | -0.025 | -0.005 | +0.005 | +0.012 | -0.031 |
| **volume_ratio_20** | Regime Sensitive | +0.004 | +0.006 | +0.006 | -0.002 | +0.003 | +0.010 |
| **omni_82_bounce** | Mostly Noise | +0.004 | +0.002 | +0.003 | +0.007 | +0.004 | +0.003 |
| **omni_82_slope** | Regime Sensitive | +0.002 | -0.049 | -0.016 | +0.006 | +0.007 | -0.054 |
| **distance_sma200** | Regime Sensitive | +0.001 | -0.039 | -0.008 | +0.003 | +0.011 | -0.041 |
| **above_sma200** | Regime Sensitive | -0.002 | -0.020 | -0.003 | +0.004 | +0.006 | -0.022 |
| **rsi_14** | Regime Sensitive | +0.001 | -0.039 | -0.008 | +0.009 | +0.002 | -0.030 |
| **above_sma50** | Regime Sensitive | -0.002 | -0.037 | -0.015 | +0.005 | +0.002 | -0.037 |
| **above_sma20** | Regime Sensitive | -0.001 | -0.043 | -0.010 | +0.007 | +0.000 | -0.033 |
| **rs_spy_20** | Regime Sensitive | -0.001 | -0.051 | -0.013 | +0.010 | -0.002 | -0.031 |
| **roc_20** | Regime Sensitive | -0.001 | -0.051 | -0.013 | +0.010 | -0.002 | -0.031 |
| **return_20d** | Regime Sensitive | -0.001 | -0.051 | -0.013 | +0.010 | -0.002 | -0.031 |
| **rs_spy_60** | Regime Sensitive | -0.003 | -0.045 | -0.025 | +0.005 | +0.004 | -0.056 |
| **return_60d** | Regime Sensitive | -0.003 | -0.045 | -0.025 | +0.005 | +0.004 | -0.056 |
| **return_10d** | Regime Sensitive | -0.003 | -0.050 | -0.011 | +0.006 | -0.002 | -0.036 |
| **distance_sma50** | Regime Sensitive | -0.002 | -0.054 | -0.020 | +0.006 | +0.001 | -0.052 |
| **distance_sma20** | Regime Sensitive | -0.002 | -0.058 | -0.015 | +0.008 | -0.001 | -0.041 |
| **atr_14** | Potentially Harmful | -0.032 | -0.025 | -0.029 | -0.037 | -0.033 | -0.025 |
| **macd_histogram** | Potentially Harmful | -0.004 | -0.042 | -0.011 | +0.002 | -0.007 | -0.024 |
| **omni_82_value** | Potentially Harmful | -0.009 | -0.002 | -0.023 | -0.009 | -0.010 | -0.009 |
| **dollar_volume_20** | Potentially Harmful | -0.005 | -0.006 | -0.022 | -0.008 | -0.007 | -0.020 |
| **return_5d** | Potentially Harmful | -0.006 | -0.049 | -0.017 | -0.002 | -0.002 | -0.044 |
| **return_3d** | Potentially Harmful | -0.009 | -0.029 | -0.013 | -0.001 | -0.004 | -0.031 |
| **return_1d** | Potentially Harmful | -0.007 | -0.013 | -0.013 | -0.002 | -0.006 | -0.020 |

### Features with insufficient regime data (n/a in all regimes)

These features are either (a) regime-defining columns that are constant within the subset, or (b) newer Momentum V2 features missing from pre-2024 parquet files:

- **Regime-defining (constant within subset):** `spy_above_sma50`, `spy_above_sma200`, `spy_return_20d`, `market_trend`
- **Insufficient history (Momentum V2, added ~2024):** `distance_sma20_momentum`, `omni_82_distance_5d_change`, `omni_82_slope_10d`, `rs_spy_20_momentum`, `rsi_momentum_5d`, `volume_trend_5d`
- **Missing older parquet:** `data_quality_score`

These features cannot be meaningfully evaluated on full history. Re-run this study in 12+ months when Momentum V2 features have sufficient coverage.

---

## Key Patterns

### 1. OMNI proxy is bull-market / low-vol / above-200DMA specific
`omni_82_distance` (+0.026 bull, +0.038 low_vol, +0.031 above_200dma) and `omni_82_above` (+0.015/+0.020/+0.019) are the strongest signals in trending, low-volatility markets. They **reverse sign** in bear markets and below_200dma environments. This is the clearest regime-conditional signal in the feature set.

### 2. Realized volatility is a bear-market / crisis signal
`realized_vol_20` (+0.053 bear, +0.046 below_200dma) and `realized_vol_60` (+0.053 bear, +0.048 below_200dma) are the only features with meaningful positive IC in bear markets. Stocks with higher recent volatility outperform in distressed regimes — consistent with a risk-on/compression dynamic when markets recover.

### 3. Momentum is mean-reverting (negative IC direction)
Short-term returns (return_1d/3d/5d) have negative IC in all regimes — meaning high recent return predicts lower future return. This is a mean-reversion relationship. LightGBM uses these features with implicit negative weights, which is correct. They are not "harmful" in isolation; the sign inversion is the signal. They are classified as "Potentially Harmful" by the IC threshold because raw IC is negative, not because the feature has no predictive value.

### 4. Distance/momentum features (SMA, RS) are contrarian in bears
`distance_sma20` (-0.058 bear), `omni_82_slope` (-0.049 bear), `rs_spy_20` (-0.051 bear) — overextended positions (high distance from SMA, strong RS) reverse hard in bear markets. These are momentum features that work as contrarian signals in downtrends.

### 5. Low-vol regime is distinctive
In low-volatility markets, `omni_82_distance` (+0.038) and `rs_spy_20` (+0.010) are positive while they're negative in other regimes. Low-vol is a regime where trend continuation is more reliable.

---

## Feature Set V3 Design

**V3 approach: regime-aware feature weighting rather than static pruning.**

Instead of removing features, V3 should modulate feature influence based on the current regime. Two implementation paths:

### Path A: Regime-conditioned sample weighting (recommended for initial V3)
During each training fold, assign per-sample weights based on the current regime to up-weight samples from regimes where the feature set has historically worked best. No architectural change to LightGBM.

### Path B: Separate models per regime cluster
Train distinct LightGBM models for: (1) bull/low-vol/above_200dma and (2) bear/high-vol/below_200dma. At inference time, select model based on current regime flags. Allows different feature importances per regime but doubles model complexity.

### Path C: Regime interaction features
Add interaction columns: `omni_82_distance * above_200dma`, `realized_vol_20 * bear_flag`. Lets a single model learn regime-specific weights for key features.

**Recommended V3 starting point:**
- Keep TRAIN_FEATURES_V1 (39 features) as base
- Add 3-4 regime interaction features: `omni_82_distance * spy_above_sma200`, `realized_vol_20 * (1-spy_above_sma200)`, `omni_82_slope * market_trend`
- Exclude `atr_14` and `dollar_volume_20` (no regime where they're positive; pure noise/harmful)
- Flag: `MODEL_FEATURE_SET_VERSION=v3`

---

## Caveats

1. **Momentum V2 features not evaluated** — `distance_sma20_momentum`, `rsi_momentum_5d`, etc. have insufficient history. These may have strong signals not captured here.
2. **Regime definitions are binary** — `market_trend == 1` is a hard cutoff. Continuous regime probability would be more robust.
3. **IC is cross-sectional Spearman** — captures rank correlation only. Some features may add value through non-linear interactions not visible in pairwise IC.
4. **Bear regime is small** (370 dates / 66k rows) — bear market IC estimates have wide confidence intervals.
