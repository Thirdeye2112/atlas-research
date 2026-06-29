# NVDA setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature      |   spearman_ic |       p |    n |
|:-------------|--------------:|--------:|-----:|
| rsi_oversold |        0.0634 | 0.0001  | 3776 |
| bb_break_dn  |        0.0479 | 0.00325 | 3776 |
| atr_pct      |        0.0401 | 0.01369 | 3776 |
| bb_width     |        0.0397 | 0.01497 | 3757 |
| dist_ema200  |        0.0272 | 0.09456 | 3776 |
| body_pct     |        0.025  | 0.12528 | 3776 |
| vol_climax   |        0.0213 | 0.19099 | 3776 |
| range_pct    |        0.0206 | 0.20533 | 3776 |

Most BEARISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| bb_squeeze     |       -0.0632 | 0.0001  | 3776 |
| mfi            |       -0.053  | 0.00113 | 3762 |
| ema_stack_bull |       -0.047  | 0.00386 | 3776 |
| bb_pct         |       -0.0313 | 0.05512 | 3757 |
| dist_hi_20     |       -0.0274 | 0.09267 | 3757 |
| rsi            |       -0.0266 | 0.10174 | 3774 |
| stoch_k        |       -0.0248 | 0.12765 | 3763 |
| williams_r     |       -0.0248 | 0.12765 | 3763 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | -0.0301 | 755 |
| 2017-06->2020-06 | +0.0437 | 755 |
| 2020-06->2023-06 | -0.0289 | 755 |
| 2023-06->2026-06 | +0.0123 | 756 |

**Mean OOS rank-IC = -0.0007** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature        |   importance |
|:---------------|-------------:|
| mfi            |   0.140561   |
| macd_hist      |   0.0823016  |
| atr_pct        |   0.0423634  |
| rsi            |   0.031685   |
| ema9_slope     |   0.0201069  |
| bb_pct         |   0.0154659  |
| vol_ratio      |   0.0139545  |
| lower_wick     |   0.00544946 |
| roc_10         |   0.0046399  |
| ema_stack_bull |   0.00396093 |
| stoch_k        |   0.00391723 |
| bb_squeeze     |   0.00361564 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=67, win 60%. Winners vs losers (Cohen's d): `rsi` higher (d=+0.50), `body_dir` lower (d=-0.47), `atr_pct` lower (d=-0.45), `rsi_overbought` higher (d=+0.44), `williams_r` lower (d=-0.42), `stoch_k` lower (d=-0.42)

**double_bottom (long)** — n=90, win 47%. Winners vs losers (Cohen's d): `dist_ema200` higher (d=+0.54), `above_ema200` higher (d=+0.37), `dist_ema50` higher (d=+0.33), `ema_stack_bull` higher (d=+0.28), `roc_10` higher (d=+0.28), `ema9_slope` higher (d=+0.23)

**inverted_hammer (long)** — n=54, win 67%. Winners vs losers (Cohen's d): `ema_stack_bear` lower (d=-0.58), `vol_z` lower (d=-0.54), `candle_ret` lower (d=-0.49), `vol_ratio` lower (d=-0.49), `rsi_slope` lower (d=-0.47), `range_pct` lower (d=-0.46)

**bullish_harami (long)** — n=129, win 60%. Winners vs losers (Cohen's d): `macd_hist` lower (d=-0.33), `consec_dir` lower (d=-0.27), `bb_squeeze` lower (d=-0.26), `stoch_k` lower (d=-0.25), `williams_r` lower (d=-0.25), `gap_pct` higher (d=+0.17)

**morning_star (long)** — n=38, win 50%. Winners vs losers (Cohen's d): `ema_stack_bear` lower (d=-0.77), `dist_ema20` higher (d=+0.64), `dist_hi_20` higher (d=+0.63), `rsi` higher (d=+0.62), `bb_pct` higher (d=+0.60), `stoch_k` higher (d=+0.59)

**bearish_engulfing (short)** — n=162, win 39%. Winners vs losers (Cohen's d): `bb_break_dn` lower (d=-0.18), `above_ema200` lower (d=-0.18), `bb_pct` higher (d=+0.18), `rsi_overbought` lower (d=-0.17), `stoch_k` higher (d=+0.16), `williams_r` higher (d=+0.16)

**shooting_star (short)** — n=89, win 52%. Winners vs losers (Cohen's d): `macd_bull_cross` lower (d=-0.52), `rsi_overbought` lower (d=-0.37), `dist_ema50` lower (d=-0.34), `dist_ema200` lower (d=-0.30), `bb_width` lower (d=-0.29), `rsi_slope` lower (d=-0.29)

**evening_star (short)** — n=44, win 45%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.40), `macd_hist` higher (d=+0.35), `bb_width` higher (d=+0.34), `mfi` higher (d=+0.30), `lower_wick` higher (d=+0.29), `bb_break_dn` lower (d=-0.28)

**hanging_man (short)** — n=138, win 47%. Winners vs losers (Cohen's d): `dist_ema200` lower (d=-0.43), `dist_ema50` lower (d=-0.36), `ema_stack_bull` lower (d=-0.34), `vol_z` higher (d=+0.29), `bb_squeeze` higher (d=+0.28), `macd_bear_cross` higher (d=+0.26)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.49 sd
- `range_pct`: +0.34 sd
- `dist_hi_20`: -0.32 sd
- `above_ema200`: -0.32 sd
- `bb_width`: +0.29 sd
- `dist_ema50`: -0.26 sd
- `ema_stack_bear`: +0.25 sd
- `body_pct`: +0.22 sd

## 5. Exit timing (winning long setups)

Entries=312. Avg cumulative return peaks at **+15 days** (+3.07%); average max adverse excursion (stop guide) **-4.87%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.28 | +0.51 | +0.77 | +0.75 | +0.84 | +1.13 | +1.31 | +1.48 | +1.47 | +1.73 | +2.13 | +2.35 | +2.55 | +2.78 | +3.07 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- macd_hist <= -0.00
|   |--- macd_hist <= -0.01
|   |   |--- value: [1.13]
|   |--- macd_hist >  -0.01
|   |   |--- value: [4.46]
|--- macd_hist >  -0.00
|   |--- dist_ema200 <= 15.81
|   |   |--- value: [0.21]
|   |--- dist_ema200 >  15.81
|   |   |--- value: [1.26]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +1.128 | +1.017 | 720 |
| 3 | +4.461 | -0.172 | 15 |
| 5 | +0.208 | +1.068 | 265 |
| 6 | +1.257 | +1.727 | 511 |
