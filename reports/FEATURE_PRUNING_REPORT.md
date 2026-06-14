# Feature Pruning Experiment Report

**Date:** 2026-06-14
**Target:** label_return_5d (5-day forward return)
**Data:** 655,440 rows, 2011-07-01 to 2026-03-17 (parquet archive)
**Split:** 80% train (524,352 rows) / 20% validation (131,088 rows)
**Model:** LightGBM regressor, 300 estimators, 10% early-stopping carve-out

---

## Feature Health Classification

Run via `python scripts/inspect_feature_health.py` against 530 rows of
`feature_performance` (model=v1, target=label_return_5d, 28 features classified).

| Category | Count | Features |
|---|---|---|
| STRONG | 0 | — |
| USEFUL | 4 | omni_82_distance (IC=+0.0242, t=+1.89, stab=0.79), omni_82_above (IC=+0.0149), realized_vol_20, volume_ratio_20 |
| WEAK | 12 | atr_14 (IC=−0.035, sign_stab=0.00), dollar_volume_20, omni_82_bounce, omni_82_slope, realized_vol_60, distance_sma200, rs_spy_120, above_sma200, above_sma50, return_60d, rs_spy_60, distance_sma50 |
| DEGRADING | 12 | return_1d, return_3d, return_5d, return_10d, return_20d, rsi_14, macd_histogram, above_sma20, distance_sma20, rs_spy_20, roc_20, omni_82_value |
| CANDIDATE REMOVE | 0 | — |

**Key finding:** All short-to-medium return lookback features (return_Nd) are sign-unstable
(stability < 0.45 across 19 folds), meaning their predictive direction flips more than
half the time. rsi_14 and macd_histogram also degrade badly.

---

## Feature Set Experiment Results

Five feature sets were tested; baseline is the current production set.

| Feature Set | n_feat | Mean Rank IC | Decile Spread | Runtime |
|---|---|---|---|---|
| features_current (baseline) | 39 | +0.0172 | +0.0004 | 3.6s |
| features_remove_weak | 27 | +0.0236 | +0.0006 | 1.6s |
| **features_remove_degrading** | **27** | **+0.0397** | +0.0003 | 1.5s |
| features_keep_only_useful | 5 | +0.0102 | +0.0001 | 1.3s |
| features_mean_reversion_plus_omni | 14 | +0.0155 | +0.0025 | 1.4s |

### Top features by gain — features_remove_degrading

`spy_return_20d(19), realized_vol_60(7), distance_sma50(5), volume_ratio_20(4), realized_vol_20(3)`

The dominant signal is **market regime** (SPY 20d return) and **volatility** (realized vol 60d),
not individual stock price momentum. When the noisy sign-unstable return features are removed,
the model locks onto these stable macro-structural signals.

---

## Analysis

### Why does removing degrading features double IC?

Degrading features add noise. A feature with sign_stability = 0.30 means it was predictive
in the expected direction only 30% of folds — it acts as a random label-corruption signal
during training, forcing the model to waste capacity on contradictory patterns.

Removing the 12 degrading features:
- Reduces active feature space from 39 to 27 (−31%)
- Eliminates all short-lookback return features (label leakage risk for return_5d target)
- Eliminates rsi_14 (highly correlated with other removed features, sign-unstable)
- IC improvement: +0.0172 → +0.0397 (+131%)

### Why does features_mean_reversion_plus_omni underperform?

MR+OMNI includes rsi_14 (degrading) and replaces broad-market features with OMNI-specific
ones. The best decile spread (+0.0025 vs +0.0003) suggests it discriminates top/bottom
extremes better but sacrifices middle-universe precision (lower IC overall). Worth keeping
as an overlay for extreme signals, not as a replacement.

### Why does features_keep_only_useful underperform baseline?

5 features cannot capture market regime. SPY return and realized vol features (which the
useful set lacks) are the strongest signals. Dropping below ~15 features sacrifices too
much regime context.

---

## Degrading Features Dropped (12)

```
return_1d, return_3d, return_5d, return_10d, return_20d
rsi_14, macd_histogram
above_sma20, distance_sma20
rs_spy_20, roc_20
omni_82_value
```

These remain in the EAV and can be reinstated at any time. Only the model training set
is being changed.

---

## Holdout Validation (2026-06-14)

Final validation on untouched period: trained 2011-07-01 to 2025-06-30, evaluated
2025-07-01 to 2026-03-17 (179 dates, 32,757 rows). Both V1 and V2 trained on identical
pre-holdout data with same LightGBM hyperparameters.

| Metric | V1 (39 feat) | V2 (27 feat) | Winner |
|---|---|---|---|
| Mean Rank IC | +0.0196 | +0.0152 | **V1** |
| IC Std (lower=better) | +0.1065 | +0.1030 | V2 |
| Decile Spread | +0.0020 | +0.0014 | **V1** |
| AUC | +0.5000 | +0.4943 | **V1** |
| Brier (lower=better) | +0.3333 | +0.3362 | **V1** |
| Top Decile Return | +0.0040 | +0.0045 | V2 |
| Bot Decile Return | +0.0020 | +0.0031 | V2 |

**Score: V1 wins 4/7. Promotion threshold not met (required >= 4 of 7).**

Prediction overlap (Jaccard, top decile per day): **39.5%** — the two models select
materially different stocks. V2 is not a drop-in substitute.

---

## Conclusion

**Verdict: KEEP V1 — holdout does not confirm replacement.**

The historical pruning experiment showed V2 improving IC by +131% on a 2011-2026 dataset.
However, the untouched holdout (July 2025 to March 2026) shows V1 winning on 4/7 metrics.
The 2025-2026 bull market appears to favour trend/momentum features (above_sma20, rs_spy_20,
rsi_14, macd_histogram) that V2 excludes. These features were classified as "degrading"
across historical folds but may be temporarily mean-reverting back to significance in the
current regime.

**V2 is preserved and ready as an alternative.** It is the default when
`MODEL_FEATURE_SET_VERSION=v2` is set in `.env`. Reassess after:
- 6+ months of additional live data (next review ~2027-01-01), or
- A market regime change (bear market, high volatility) where trend signals degrade

**Do not delete** any features from `feature_snapshots`, `ALL_FEATURES`, or `PHASE1_FEATURES`.
The degrading classification is regime-sensitive, not permanent.

**Next retrain should use TRAIN_FEATURES_V1 (39 features)**, which includes the 6
MOMENTUM_V2 features not yet in the current 33-feature production model.
