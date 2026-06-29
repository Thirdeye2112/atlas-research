# TSLA setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| bb_width       |        0.0968 | 0       | 3757 |
| bb_break_up    |        0.0928 | 0       | 3776 |
| dist_lo_20     |        0.0611 | 0.00018 | 3757 |
| macd_hist      |        0.0571 | 0.00044 | 3776 |
| rsi_overbought |        0.0541 | 0.00088 | 3776 |
| bb_pct         |        0.0522 | 0.00137 | 3757 |
| atr_pct        |        0.0396 | 0.01504 | 3776 |
| roc_10         |        0.0365 | 0.02511 | 3766 |

Most BEARISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| above_ema200    |       -0.0285 | 0.07955 | 3776 |
| consec_dir      |       -0.0163 | 0.31622 | 3776 |
| ema_stack_bear  |       -0.0155 | 0.34088 | 3776 |
| dist_ema200     |       -0.0117 | 0.47212 | 3776 |
| body_dir        |       -0.0097 | 0.54942 | 3776 |
| candle_ret      |       -0.0097 | 0.55104 | 3776 |
| bb_squeeze      |       -0.0071 | 0.66469 | 3776 |
| macd_bear_cross |       -0.0053 | 0.74692 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.0447 | 755 |
| 2017-06->2020-06 | +0.0768 | 755 |
| 2020-06->2023-06 | +0.0612 | 755 |
| 2023-06->2026-06 | +0.0405 | 756 |

**Mean OOS rank-IC = +0.0558** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature    |   importance |
|:-----------|-------------:|
| atr_pct    |   0.0186429  |
| rsi        |   0.0111396  |
| lower_wick |   0.00904629 |
| stoch_k    |   0.00668921 |
| dist_ema20 |   0.00391602 |
| rsi_slope  |   0.00354014 |
| candle_ret |   0.0031296  |
| range_pct  |   0.0025415  |
| consec_dir |   0.00214755 |
| dist_hi_20 |   0.00213406 |
| ema9_slope |   0.00200397 |
| cc_ret     |   0.00172049 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=51, win 59%. Winners vs losers (Cohen's d): `roc_10` lower (d=-0.73), `bb_width` lower (d=-0.72), `macd_hist` lower (d=-0.65), `dist_lo_20` lower (d=-0.60), `range_pct` lower (d=-0.52), `bb_squeeze` higher (d=+0.52)

**double_bottom (long)** — n=54, win 63%. Winners vs losers (Cohen's d): `dist_ema200` higher (d=+0.74), `macd_bull_cross` higher (d=+0.70), `lower_wick` lower (d=-0.65), `candle_ret` higher (d=+0.64), `body_pct` higher (d=+0.61), `bb_squeeze` higher (d=+0.59)

**inverted_hammer (long)** — n=52, win 56%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.76), `rsi` lower (d=-0.73), `ema_stack_bull` lower (d=-0.73), `above_ema200` lower (d=-0.67), `dist_ema50` lower (d=-0.66), `bb_pct` lower (d=-0.63)

**bullish_harami (long)** — n=140, win 54%. Winners vs losers (Cohen's d): `above_ema200` lower (d=-0.50), `ema_stack_bull` lower (d=-0.39), `range_pct` lower (d=-0.34), `macd_hist` higher (d=+0.26), `body_pct` lower (d=-0.25), `dist_ema200` lower (d=-0.23)

**morning_star (long)** — n=33, win 58%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.69), `vol_ratio` lower (d=-0.47), `vol_climax` lower (d=-0.43), `macd_bull_cross` lower (d=-0.43), `cc_ret` lower (d=-0.42), `upper_wick` lower (d=-0.42)

**bearish_engulfing (short)** — n=160, win 42%. Winners vs losers (Cohen's d): `rsi_slope` higher (d=+0.31), `range_pct` lower (d=-0.29), `candle_ret` higher (d=+0.23), `body_pct` lower (d=-0.23), `vol_ratio` lower (d=-0.23), `ema_stack_bull` higher (d=+0.22)

**shooting_star (short)** — n=100, win 50%. Winners vs losers (Cohen's d): `above_ema200` higher (d=+0.38), `ema_stack_bear` lower (d=-0.33), `ema_stack_bull` higher (d=+0.29), `mfi` higher (d=+0.20), `macd_bear_cross` higher (d=+0.20), `stoch_k` higher (d=+0.16)

**evening_star (short)** — n=37, win 49%. Winners vs losers (Cohen's d): `ema_stack_bear` higher (d=+0.96), `bb_width` lower (d=-0.66), `macd_bear_cross` higher (d=+0.51), `ema_stack_bull` lower (d=-0.51), `dist_lo_20` lower (d=-0.50), `gap_pct` lower (d=-0.45)

**hanging_man (short)** — n=86, win 49%. Winners vs losers (Cohen's d): `range_pct` higher (d=+0.40), `bb_width` higher (d=+0.38), `dist_ema200` higher (d=+0.33), `macd_hist` higher (d=+0.33), `williams_r` higher (d=+0.32), `stoch_k` higher (d=+0.32)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.25 sd
- `bb_pct`: -0.22 sd
- `stoch_k`: -0.22 sd
- `williams_r`: -0.22 sd
- `roc_10`: -0.20 sd
- `macd_hist`: -0.20 sd
- `mfi`: -0.20 sd
- `dist_hi_20`: -0.19 sd

## 5. Exit timing (winning long setups)

Entries=278. Avg cumulative return peaks at **+13 days** (+3.71%); average max adverse excursion (stop guide) **-6.88%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.39 | +0.63 | +0.74 | +0.94 | +1.17 | +1.11 | +1.62 | +2.09 | +2.08 | +2.33 | +3.11 | +3.15 | +3.71 | +3.47 | +3.62 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- bb_width <= 36.34
|   |--- atr_pct <= 5.62
|   |   |--- value: [0.41]
|   |--- atr_pct >  5.62
|   |   |--- value: [3.00]
|--- bb_width >  36.34
|   |--- value: [5.94]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.411 | +0.924 | 931 |
| 3 | +3.004 | +0.467 | 282 |
| 4 | +5.938 | +1.574 | 298 |
