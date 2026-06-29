# AMZN setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| rsi_oversold    |        0.0523 | 0.0013  | 3776 |
| ema_stack_bear  |        0.0403 | 0.01327 | 3776 |
| bb_squeeze      |        0.0321 | 0.04885 | 3776 |
| macd_bear_cross |        0.0277 | 0.08917 | 3776 |
| bb_break_dn     |        0.0182 | 0.26472 | 3776 |
| atr_pct         |        0.0091 | 0.57463 | 3776 |
| macd_bull_cross |        0.0086 | 0.59779 | 3776 |
| upper_wick      |        0.0056 | 0.73124 | 3776 |

Most BEARISH features:

| feature    |   spearman_ic |       p |    n |
|:-----------|--------------:|--------:|-----:|
| dist_lo_20 |       -0.0743 | 1e-05   | 3757 |
| dist_ema20 |       -0.0611 | 0.00017 | 3776 |
| roc_10     |       -0.0602 | 0.00022 | 3766 |
| mfi        |       -0.0597 | 0.00025 | 3760 |
| rsi        |       -0.0586 | 0.00031 | 3774 |
| dist_ema50 |       -0.0553 | 0.00068 | 3776 |
| ema9_slope |       -0.0538 | 0.00094 | 3775 |
| dist_ema9  |       -0.0538 | 0.00094 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | -0.0512 | 755 |
| 2017-06->2020-06 | +0.0524 | 755 |
| 2020-06->2023-06 | +0.0058 | 755 |
| 2023-06->2026-06 | +0.0725 | 756 |

**Mean OOS rank-IC = +0.0199** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature    |   importance |
|:-----------|-------------:|
| macd_hist  |   0.0501946  |
| rsi        |   0.0438378  |
| dist_lo_20 |   0.0345521  |
| dist_hi_20 |   0.0318779  |
| bb_width   |   0.0164922  |
| roc_10     |   0.014211   |
| stoch_k    |   0.00975939 |
| vol_z      |   0.00599155 |
| dist_ema20 |   0.00523769 |
| atr_pct    |   0.00438318 |
| candle_ret |   0.00317252 |
| vol_ratio  |   0.00211538 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=57, win 63%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.67), `upper_wick` lower (d=-0.39), `candle_ret` lower (d=-0.32), `vol_climax` higher (d=+0.30), `gap_pct` higher (d=+0.30), `body_dir` lower (d=-0.27)

**double_bottom (long)** — n=120, win 61%. Winners vs losers (Cohen's d): `macd_hist` higher (d=+0.35), `upper_wick` lower (d=-0.30), `bb_squeeze` lower (d=-0.29), `rsi_slope` lower (d=-0.22), `atr_pct` lower (d=-0.20), `dist_hi_20` higher (d=+0.20)

**inverted_hammer (long)** — n=41, win 44%. Winners vs losers (Cohen's d): `rsi_slope` lower (d=-0.54), `dist_hi_20` lower (d=-0.53), `bb_squeeze` lower (d=-0.48), `lower_wick` lower (d=-0.46), `vol_ratio` higher (d=+0.46), `vol_z` higher (d=+0.43)

**bullish_harami (long)** — n=113, win 61%. Winners vs losers (Cohen's d): `upper_wick` lower (d=-0.25), `macd_bull_cross` lower (d=-0.25), `bb_break_dn` higher (d=+0.22), `lower_wick` higher (d=+0.20), `bb_pct` higher (d=+0.16), `range_pct` lower (d=-0.14)

**morning_star (long)** — n=31, win 71%. Winners vs losers (Cohen's d): `lower_wick` lower (d=-0.65), `bb_pct` lower (d=-0.45), `dist_ema9` lower (d=-0.43), `ema9_slope` lower (d=-0.43), `consec_dir` lower (d=-0.40), `mfi` lower (d=-0.39)

**bearish_engulfing (short)** — n=164, win 46%. Winners vs losers (Cohen's d): `mfi` higher (d=+0.37), `rsi_slope` lower (d=-0.28), `macd_bear_cross` higher (d=+0.27), `cc_ret` lower (d=-0.25), `rsi_oversold` lower (d=-0.21), `bb_pct` higher (d=+0.19)

**shooting_star (short)** — n=84, win 46%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.42), `body_pct` lower (d=-0.36), `ema_stack_bear` higher (d=+0.34), `range_pct` lower (d=-0.33), `gap_pct` higher (d=+0.30), `cc_ret` higher (d=+0.29)

**evening_star (short)** — n=34, win 44%. Winners vs losers (Cohen's d): `macd_hist` higher (d=+0.75), `dist_lo_20` higher (d=+0.72), `mfi` higher (d=+0.69), `roc_10` higher (d=+0.59), `stoch_k` higher (d=+0.58), `williams_r` higher (d=+0.58)

**hanging_man (short)** — n=103, win 50%. Winners vs losers (Cohen's d): `range_pct` lower (d=-0.38), `candle_ret` higher (d=+0.37), `rsi_overbought` lower (d=-0.29), `cc_ret` higher (d=+0.25), `lower_wick` lower (d=-0.23), `macd_hist` higher (d=+0.22)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.46 sd
- `range_pct`: +0.43 sd
- `body_pct`: +0.31 sd
- `bb_width`: +0.27 sd
- `dist_hi_20`: -0.25 sd
- `above_ema200`: -0.24 sd
- `vol_z`: +0.23 sd
- `vol_ratio`: +0.23 sd

## 5. Exit timing (winning long setups)

Entries=297. Avg cumulative return peaks at **+14 days** (+2.20%); average max adverse excursion (stop guide) **-3.51%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.34 | +0.63 | +0.74 | +0.96 | +1.04 | +1.27 | +1.24 | +1.48 | +1.59 | +1.64 | +1.78 | +2.04 | +2.08 | +2.20 | +2.15 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema200 <= -7.05
|   |--- value: [3.29]
|--- dist_ema200 >  -7.05
|   |--- bb_width <= 5.41
|   |   |--- value: [1.59]
|   |--- bb_width >  5.41
|   |   |--- value: [0.41]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 1 | +3.286 | +0.634 | 257 |
| 3 | +1.588 | +2.019 | 38 |
| 4 | +0.411 | +0.191 | 1216 |
