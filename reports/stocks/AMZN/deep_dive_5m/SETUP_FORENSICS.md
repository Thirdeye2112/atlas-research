# AMZN setup forensics (intraday) — horizon 6bars

Bars 104,870 (2021-01-04->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |      n |
|:---------------|--------------:|--------:|-------:|
| above_ema200   |        0.0128 | 3e-05   | 104864 |
| ema_stack_bull |        0.0098 | 0.00144 | 104864 |
| dist_ema200    |        0.0086 | 0.00528 | 104864 |
| dist_lo_20     |        0.0075 | 0.01529 | 104845 |
| tod_min        |        0.0075 | 0.01524 | 104864 |
| range_pct      |        0.0061 | 0.05232 | 102099 |
| vol_climax     |        0.0053 | 0.08747 | 104864 |
| lower_wick     |        0.005  | 0.11277 | 102099 |

Most BEARISH features:

| feature        |   spearman_ic |       p |      n |
|:---------------|--------------:|--------:|-------:|
| consec_dir     |       -0.0136 | 1e-05   | 104864 |
| cc_ret         |       -0.0134 | 1e-05   | 104863 |
| body_dir       |       -0.0132 | 2e-05   | 104864 |
| candle_ret     |       -0.0131 | 2e-05   | 104864 |
| rsi_slope      |       -0.0117 | 0.00015 | 104861 |
| ema_stack_bear |       -0.0071 | 0.02166 | 104864 |
| bb_break_dn    |       -0.0061 | 0.04874 | 104864 |
| dist_ema9      |       -0.0056 | 0.06932 | 104864 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0156 | 20973 |
| 2023-03->2024-04 | +0.0049 | 20973 |
| 2024-04->2025-05 | -0.0006 | 20973 |
| 2025-05->2026-06 | +0.0168 | 20973 |

**Mean OOS rank-IC = +0.0092** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| dist_ema200 |  0.00185065  |
| tod_min     |  0.00162173  |
| or_position |  0.0016053   |
| range_pct   |  0.000436975 |
| roc_10      |  0.000219383 |
| rsi         |  9.3251e-05  |
| upper_wick  |  0           |
| body_pct    |  0           |
| body_dir    |  0           |
| cc_ret      |  0           |
| candle_ret  |  0           |
| dist_ema50  |  0           |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5154, win 51%. Winners vs losers (Cohen's d): `range_pct` higher (d=+0.09), `roc_10` higher (d=+0.09), `atr_pct` higher (d=+0.08), `stoch_k` lower (d=-0.08), `williams_r` lower (d=-0.08), `body_pct` higher (d=+0.08)

**inverted_hammer (long)** — n=2571, win 52%. Winners vs losers (Cohen's d): `dist_lo_20` higher (d=+0.10), `vol_ratio` lower (d=-0.08), `bb_break_dn` lower (d=-0.08), `bb_width` higher (d=+0.07), `bb_break_up` higher (d=+0.07), `vol_z` lower (d=-0.07)

**bullish_harami (long)** — n=3586, win 51%. Winners vs losers (Cohen's d): `dist_ema200` lower (d=-0.08), `or_position` higher (d=+0.07), `dist_ema50` lower (d=-0.07), `vwap_dist` higher (d=+0.06), `rsi_slope` higher (d=+0.06), `vol_climax` higher (d=+0.06)

**morning_star (long)** — n=974, win 49%. Winners vs losers (Cohen's d): `macd_bear_cross` lower (d=-0.11), `bb_pct` higher (d=+0.09), `tod_min` lower (d=-0.08), `rsi_overbought` higher (d=+0.08), `dist_lo_20` higher (d=+0.07), `rsi_oversold` lower (d=-0.07)

**bearish_engulfing (short)** — n=5188, win 49%. Winners vs losers (Cohen's d): `bb_break_dn` higher (d=+0.05), `dist_lo_20` lower (d=-0.04), `vwap_dist` higher (d=+0.04), `dist_ema20` lower (d=-0.04), `macd_hist` higher (d=+0.04), `ema_stack_bull` lower (d=-0.04)

**shooting_star (short)** — n=2637, win 49%. Winners vs losers (Cohen's d): `dist_hi_20` higher (d=+0.09), `stoch_k` higher (d=+0.09), `williams_r` higher (d=+0.09), `rsi_overbought` higher (d=+0.08), `lower_wick` lower (d=-0.08), `above_vwap` higher (d=+0.08)

**evening_star (short)** — n=968, win 49%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.16), `lower_wick` higher (d=+0.10), `cc_ret` higher (d=+0.09), `above_ema200` lower (d=-0.08), `rsi_slope` higher (d=+0.08), `or_position` lower (d=-0.07)

**hanging_man (short)** — n=2852, win 51%. Winners vs losers (Cohen's d): `bb_width` lower (d=-0.07), `or_position` lower (d=-0.07), `upper_wick` higher (d=+0.07), `above_ema200` lower (d=-0.07), `dist_ema50` lower (d=-0.06), `rsi_slope` higher (d=+0.06)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.50 sd
- `body_pct`: +0.37 sd
- `vol_ratio`: +0.31 sd
- `vol_z`: +0.31 sd
- `vol_climax`: +0.26 sd
- `dist_lo_20`: +0.25 sd
- `bb_squeeze`: -0.15 sd
- `above_ema200`: -0.14 sd

## 5. Exit timing (winning long setups)

Entries=9897. Avg cumulative return peaks at **+11 bars** (+0.02%); average max adverse excursion (stop guide) **-0.54%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.02 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- or_position <= -0.55
|   |--- dist_ema200 <= -0.99
|   |   |--- value: [0.03]
|   |--- dist_ema200 >  -0.99
|   |   |--- value: [-0.24]
|--- or_position >  -0.55
|   |--- tod_min <= 1167.50
|   |   |--- value: [-0.00]
|   |--- tod_min >  1167.50
|   |   |--- value: [0.04]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.029 | +0.033 | 2306 |
| 3 | -0.239 | -0.016 | 1631 |
| 5 | -0.001 | +0.004 | 33542 |
| 6 | +0.037 | +0.007 | 4467 |
