# AAPL setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 38 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| rsi_oversold   |        0.0601 | 0.00022 | 3776 |
| rsi_overbought |        0.0546 | 0.00079 | 3776 |
| macd_hist      |        0.0414 | 0.01087 | 3776 |
| dist_hi_20     |        0.0358 | 0.02827 | 3757 |
| vol_z          |        0.0354 | 0.03003 | 3757 |
| vol_ratio      |        0.0346 | 0.03343 | 3776 |
| bb_pct         |        0.0343 | 0.03568 | 3757 |
| ema_stack_bear |        0.0323 | 0.04705 | 3776 |

Most BEARISH features:

| feature      |   spearman_ic |       p |    n |
|:-------------|--------------:|--------:|-----:|
| lower_wick   |       -0.0422 | 0.00948 | 3776 |
| dist_ema200  |       -0.029  | 0.07448 | 3776 |
| atr_pct      |       -0.0281 | 0.08407 | 3776 |
| above_ema200 |       -0.0081 | 0.61757 | 3776 |
| vol_climax   |        0.0037 | 0.8199  | 3776 |
| body_dir     |        0.0041 | 0.79974 | 3776 |
| candle_ret   |        0.0041 | 0.80003 | 3776 |
| consec_dir   |        0.0058 | 0.72221 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | -0.0455 | 755 |
| 2017-06->2020-06 | -0.0553 | 755 |
| 2020-06->2023-06 | +0.0846 | 755 |
| 2023-06->2026-06 | +0.0103 | 756 |

**Mean OOS rank-IC = -0.0015** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| dist_ema9   |   0.0280276  |
| dist_ema200 |   0.0166121  |
| rsi_slope   |   0.0150033  |
| bb_width    |   0.0132077  |
| roc_10      |   0.0117973  |
| dist_hi_20  |   0.0108954  |
| macd_hist   |   0.00873021 |
| vol_z       |   0.0078813  |
| dist_lo_20  |   0.00598408 |
| gap_pct     |   0.0040537  |
| consec_dir  |   0.00404358 |
| ema9_slope  |   0.00238452 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=59, win 76%. Winners vs losers (Cohen's d): `macd_hist` lower (d=-0.61), `ema_stack_bear` lower (d=-0.57), `dist_lo_20` lower (d=-0.50), `above_ema200` higher (d=+0.50), `vol_ratio` higher (d=+0.46), `vol_z` higher (d=+0.43)

**double_bottom (long)** — n=94, win 64%. Winners vs losers (Cohen's d): `bb_pct` higher (d=+0.68), `dist_hi_20` higher (d=+0.64), `bb_break_up` higher (d=+0.48), `ema_stack_bear` lower (d=-0.44), `dist_ema200` higher (d=+0.41), `above_ema200` higher (d=+0.37)

**inverted_hammer (long)** — n=60, win 68%. Winners vs losers (Cohen's d): `lower_wick` higher (d=+0.62), `macd_hist` lower (d=-0.60), `upper_wick` lower (d=-0.59), `rsi_slope` higher (d=+0.50), `rsi_oversold` higher (d=+0.50), `dist_lo_20` lower (d=-0.42)

**bullish_harami (long)** — n=105, win 60%. Winners vs losers (Cohen's d): `ema_stack_bear` higher (d=+0.54), `macd_bear_cross` higher (d=+0.38), `vol_ratio` lower (d=-0.38), `vol_z` lower (d=-0.36), `dist_ema50` lower (d=-0.32), `above_ema200` lower (d=-0.30)

**morning_star (long)** — n=39, win 36%. Winners vs losers (Cohen's d): `rsi_slope` lower (d=-0.68), `dist_lo_20` higher (d=+0.60), `rsi_overbought` higher (d=+0.60), `mfi` higher (d=+0.48), `above_ema200` lower (d=-0.48), `vol_z` lower (d=-0.40)

**bearish_engulfing (short)** — n=151, win 37%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.29), `stoch_k` lower (d=-0.27), `williams_r` lower (d=-0.27), `bb_break_dn` higher (d=+0.26), `gap_pct` higher (d=+0.25), `ema_stack_bull` lower (d=-0.23)

**shooting_star (short)** — n=96, win 36%. Winners vs losers (Cohen's d): `bb_break_up` lower (d=-0.49), `vol_ratio` lower (d=-0.42), `vol_z` lower (d=-0.36), `macd_bear_cross` lower (d=-0.28), `gap_pct` higher (d=+0.28), `bb_pct` lower (d=-0.27)

**evening_star (short)** — n=39, win 41%. Winners vs losers (Cohen's d): `ema_stack_bear` lower (d=-0.95), `stoch_k` higher (d=+0.61), `williams_r` higher (d=+0.61), `rsi` higher (d=+0.57), `dist_ema9` higher (d=+0.54), `ema9_slope` higher (d=+0.54)

**hanging_man (short)** — n=109, win 37%. Winners vs losers (Cohen's d): `ema_stack_bear` lower (d=-0.39), `macd_hist` lower (d=-0.30), `bb_width` lower (d=-0.28), `rsi_overbought` lower (d=-0.21), `macd_bull_cross` higher (d=+0.16), `macd_bear_cross` lower (d=-0.16)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.41 sd
- `rsi`: -0.32 sd
- `dist_hi_20`: -0.31 sd
- `bb_pct`: -0.28 sd
- `rsi_overbought`: -0.27 sd
- `ema_stack_bull`: -0.27 sd
- `dist_ema20`: -0.26 sd
- `stoch_k`: -0.26 sd

## 5. Exit timing (winning long setups)

Entries=298. Avg cumulative return peaks at **+15 days** (+1.97%); average max adverse excursion (stop guide) **-3.42%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.15 | +0.43 | +0.52 | +0.75 | +1.08 | +1.04 | +1.23 | +1.11 | +1.22 | +1.42 | +1.52 | +1.49 | +1.66 | +1.76 | +1.97 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- rsi <= 68.82
|   |--- ema9_slope <= -0.69
|   |   |--- value: [1.48]
|   |--- ema9_slope >  -0.69
|   |   |--- value: [0.19]
|--- rsi >  68.82
|   |--- dist_ema20 <= 4.04
|   |   |--- value: [1.87]
|   |--- dist_ema20 >  4.04
|   |   |--- value: [1.05]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +1.484 | +1.679 | 135 |
| 3 | +0.193 | +0.374 | 1175 |
| 5 | +1.867 | +1.097 | 42 |
| 6 | +1.048 | +0.093 | 159 |
