# TSLA setup forensics (intraday) — horizon 6bars

Bars 106,799 (2021-01-04->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |     p |      n |
|:---------------|--------------:|------:|-------:|
| rsi_overbought |        0.0209 | 0     | 106793 |
| vwap_dist      |        0.0203 | 0     | 106793 |
| above_vwap     |        0.0199 | 0     | 106793 |
| or_position    |        0.0133 | 1e-05 | 106793 |
| dist_ema50     |        0.0132 | 2e-05 | 106793 |
| dist_ema200    |        0.0127 | 3e-05 | 106793 |
| above_ema200   |        0.0124 | 5e-05 | 106793 |
| rsi            |        0.0122 | 7e-05 | 106792 |

Most BEARISH features:

| feature         |   spearman_ic |       p |      n |
|:----------------|--------------:|--------:|-------:|
| ema_stack_bear  |       -0.0106 | 0.00052 | 106793 |
| rsi_slope       |       -0.009  | 0.00319 | 106790 |
| macd_bull_cross |       -0.0073 | 0.01695 | 106793 |
| body_dir        |       -0.0069 | 0.0251  | 106793 |
| consec_dir      |       -0.0066 | 0.02988 | 106793 |
| candle_ret      |       -0.0062 | 0.04121 | 106793 |
| macd_bear_cross |       -0.0062 | 0.04313 | 106793 |
| cc_ret          |       -0.0061 | 0.04565 | 106792 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0570 | 21359 |
| 2023-03->2024-04 | +0.0307 | 21358 |
| 2024-04->2025-05 | +0.0011 | 21359 |
| 2025-05->2026-06 | +0.0173 | 21359 |

**Mean OOS rank-IC = +0.0265** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| or_position |   0.0609282  |
| vwap_dist   |   0.0488015  |
| atr_pct     |   0.0307412  |
| macd_hist   |   0.0141373  |
| dist_hi_20  |   0.00932135 |
| rsi_slope   |   0.00567272 |
| dist_ema200 |   0.00541817 |
| gap_pct     |   0.0038548  |
| cc_ret      |   0.00265173 |
| rsi         |   0.00178052 |
| bb_pct      |   0.00143474 |
| vol_ratio   |   0.00112991 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5042, win 50%. Winners vs losers (Cohen's d): `williams_r` higher (d=+0.14), `stoch_k` higher (d=+0.14), `upper_wick` lower (d=-0.11), `above_ema200` higher (d=+0.11), `above_vwap` higher (d=+0.11), `rsi` higher (d=+0.11)

**inverted_hammer (long)** — n=2688, win 53%. Winners vs losers (Cohen's d): `or_position` higher (d=+0.10), `vwap_dist` higher (d=+0.09), `dist_ema200` higher (d=+0.07), `vol_ratio` lower (d=-0.07), `ema_stack_bear` lower (d=-0.07), `dist_lo_20` higher (d=+0.06)

**bullish_harami (long)** — n=3991, win 51%. Winners vs losers (Cohen's d): `ema_stack_bull` higher (d=+0.06), `above_vwap` higher (d=+0.06), `or_position` higher (d=+0.05), `mfi` lower (d=-0.05), `dist_lo_20` lower (d=-0.04), `ema9_slope` lower (d=-0.04)

**morning_star (long)** — n=934, win 49%. Winners vs losers (Cohen's d): `bb_break_up` higher (d=+0.16), `gap_pct` higher (d=+0.12), `rsi_slope` higher (d=+0.10), `upper_wick` lower (d=-0.10), `vwap_dist` lower (d=-0.07), `macd_bear_cross` higher (d=+0.07)

**bearish_engulfing (short)** — n=5430, win 48%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.07), `above_ema200` lower (d=-0.07), `macd_bear_cross` higher (d=+0.06), `ema_stack_bull` lower (d=-0.06), `dist_ema200` lower (d=-0.05), `candle_ret` lower (d=-0.05)

**shooting_star (short)** — n=2750, win 51%. Winners vs losers (Cohen's d): `above_vwap` lower (d=-0.10), `macd_bear_cross` lower (d=-0.09), `vwap_dist` lower (d=-0.09), `consec_dir` higher (d=+0.08), `or_position` lower (d=-0.07), `vol_climax` higher (d=+0.07)

**evening_star (short)** — n=1038, win 49%. Winners vs losers (Cohen's d): `lower_wick` lower (d=-0.18), `dist_ema200` lower (d=-0.15), `above_ema200` lower (d=-0.14), `vol_z` lower (d=-0.13), `consec_dir` lower (d=-0.12), `vol_ratio` lower (d=-0.11)

**hanging_man (short)** — n=2995, win 50%. Winners vs losers (Cohen's d): `rsi_overbought` higher (d=+0.08), `mfi` higher (d=+0.06), `vol_z` lower (d=-0.06), `tod_min` lower (d=-0.06), `above_vwap` lower (d=-0.06), `vwap_dist` lower (d=-0.05)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.50 sd
- `atr_pct`: +0.41 sd
- `vol_ratio`: +0.36 sd
- `vol_z`: +0.35 sd
- `body_pct`: +0.34 sd
- `vol_climax`: +0.24 sd
- `bb_width`: +0.22 sd
- `dist_lo_20`: +0.19 sd

## 5. Exit timing (winning long setups)

Entries=10323. Avg cumulative return peaks at **+16 bars** (+0.03%); average max adverse excursion (stop guide) **-0.93%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.00 | +0.00 | +0.01 | +0.00 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.01 | +0.02 | +0.01 | +0.02 | +0.02 | +0.03 | +0.03 | +0.02 | +0.02 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- vwap_dist <= -0.24
|   |--- tod_min <= 1167.50
|   |   |--- value: [-0.03]
|   |--- tod_min >  1167.50
|   |   |--- value: [-0.26]
|--- vwap_dist >  -0.24
|   |--- tod_min <= 1167.50
|   |   |--- value: [0.02]
|   |--- tod_min >  1167.50
|   |   |--- value: [0.15]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | -0.030 | -0.006 | 14343 |
| 3 | -0.264 | +0.080 | 2079 |
| 5 | +0.017 | +0.010 | 23143 |
| 6 | +0.154 | +0.124 | 3153 |
