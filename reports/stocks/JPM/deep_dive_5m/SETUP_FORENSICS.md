# JPM setup forensics (intraday) — horizon 6bars

Bars 105,402 (2021-01-04->2026-06-18). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |      n |
|:----------------|--------------:|--------:|-------:|
| tod_min         |        0.0167 | 0       | 105396 |
| vol_ratio       |        0.0148 | 0       | 105396 |
| vol_climax      |        0.0129 | 3e-05   | 105396 |
| vol_z           |        0.0126 | 4e-05   | 105377 |
| macd_hist       |        0.0081 | 0.00841 | 105396 |
| bb_squeeze      |        0.008  | 0.00918 | 105396 |
| macd_bear_cross |        0.0052 | 0.08867 | 105396 |
| upper_wick      |        0.005  | 0.10635 | 103339 |

Most BEARISH features:

| feature     |   spearman_ic |       p |      n |
|:------------|--------------:|--------:|-------:|
| or_position |       -0.0143 | 0       | 105396 |
| atr_pct     |       -0.0139 | 1e-05   | 105396 |
| candle_ret  |       -0.0106 | 0.00058 | 105396 |
| bb_width    |       -0.0104 | 0.00071 | 105377 |
| cc_ret      |       -0.0095 | 0.00208 | 105395 |
| rsi_slope   |       -0.009  | 0.00335 | 105393 |
| dist_ema200 |       -0.0077 | 0.01278 | 105396 |
| body_dir    |       -0.0068 | 0.02744 | 105396 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0355 | 21079 |
| 2023-03->2024-04 | +0.0683 | 21079 |
| 2024-04->2025-05 | +0.0277 | 21079 |
| 2025-05->2026-06 | +0.0496 | 21080 |

**Mean OOS rank-IC = +0.0453** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature        |   importance |
|:---------------|-------------:|
| or_position    |  0.0491213   |
| tod_min        |  0.0226901   |
| atr_pct        |  0.00762532  |
| dist_ema200    |  0.00468378  |
| vwap_dist      |  0.00441484  |
| rsi            |  0.00336276  |
| dist_ema50     |  0.0029141   |
| range_pct      |  0.00208017  |
| rsi_overbought |  0.00158483  |
| vol_ratio      |  0.00119203  |
| bb_width       |  0.00108956  |
| bb_pct         |  0.000896932 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5565, win 50%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.10), `or_position` lower (d=-0.10), `above_vwap` lower (d=-0.09), `macd_hist` higher (d=+0.09), `upper_wick` higher (d=+0.08), `vwap_dist` lower (d=-0.07)

**inverted_hammer (long)** — n=2624, win 51%. Winners vs losers (Cohen's d): `or_position` lower (d=-0.09), `bb_squeeze` higher (d=+0.08), `dist_ema50` lower (d=-0.06), `above_ema200` lower (d=-0.06), `dist_ema200` lower (d=-0.05), `body_dir` lower (d=-0.05)

**bullish_harami (long)** — n=3658, win 51%. Winners vs losers (Cohen's d): `roc_10` higher (d=+0.08), `macd_hist` higher (d=+0.07), `rsi_slope` lower (d=-0.06), `ema_stack_bull` lower (d=-0.06), `williams_r` higher (d=+0.06), `stoch_k` higher (d=+0.06)

**morning_star (long)** — n=911, win 50%. Winners vs losers (Cohen's d): `atr_pct` lower (d=-0.14), `roc_10` lower (d=-0.12), `macd_bear_cross` higher (d=+0.12), `candle_ret` lower (d=-0.11), `body_pct` lower (d=-0.11), `dist_ema20` lower (d=-0.10)

**bearish_engulfing (short)** — n=4600, win 47%. Winners vs losers (Cohen's d): `bb_break_dn` higher (d=+0.10), `rsi_oversold` higher (d=+0.07), `ema9_slope` lower (d=-0.07), `dist_ema9` lower (d=-0.07), `above_vwap` lower (d=-0.06), `bb_pct` lower (d=-0.06)

**shooting_star (short)** — n=2979, win 47%. Winners vs losers (Cohen's d): `stoch_k` lower (d=-0.09), `williams_r` lower (d=-0.09), `dist_hi_20` lower (d=-0.08), `body_pct` higher (d=+0.07), `rsi_overbought` lower (d=-0.07), `rsi` lower (d=-0.07)

**evening_star (short)** — n=993, win 46%. Winners vs losers (Cohen's d): `dist_lo_20` higher (d=+0.15), `atr_pct` higher (d=+0.15), `rsi_oversold` lower (d=-0.12), `lower_wick` lower (d=-0.11), `vol_climax` lower (d=-0.11), `candle_ret` lower (d=-0.11)

**hanging_man (short)** — n=3102, win 49%. Winners vs losers (Cohen's d): `vol_climax` lower (d=-0.12), `vol_ratio` lower (d=-0.09), `macd_bull_cross` higher (d=+0.08), `rsi_oversold` higher (d=+0.07), `vol_z` lower (d=-0.06), `tod_min` lower (d=-0.06)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.55 sd
- `atr_pct`: +0.55 sd
- `body_pct`: +0.41 sd
- `bb_width`: +0.38 sd
- `dist_hi_20`: -0.38 sd
- `vol_z`: +0.28 sd
- `vol_ratio`: +0.27 sd
- `dist_lo_20`: +0.22 sd

## 5. Exit timing (winning long setups)

Entries=10362. Avg cumulative return peaks at **+18 bars** (+0.02%); average max adverse excursion (stop guide) **-0.40%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.00 | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- tod_min <= 1167.50
|   |--- or_position <= 0.53
|   |   |--- value: [0.02]
|   |--- or_position >  0.53
|   |   |--- value: [-0.01]
|--- tod_min >  1167.50
|   |--- or_position <= 0.29
|   |   |--- value: [-0.02]
|   |--- or_position >  0.29
|   |   |--- value: [0.06]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.015 | +0.010 | 17373 |
| 3 | -0.014 | -0.005 | 19569 |
| 5 | -0.018 | +0.062 | 2074 |
| 6 | +0.063 | +0.047 | 3143 |
