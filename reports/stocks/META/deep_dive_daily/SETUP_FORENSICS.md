# META setup forensics (daily) — horizon 5days

Bars 3,545 (2012-05-18->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| atr_pct        |        0.0308 | 0.06716 | 3540 |
| bb_width       |        0.0266 | 0.11484 | 3521 |
| ema_stack_bull |        0.0234 | 0.16465 | 3540 |
| bb_squeeze     |        0.0217 | 0.19586 | 3540 |
| body_pct       |        0.018  | 0.28537 | 3540 |
| bb_break_dn    |        0.0165 | 0.32685 | 3540 |
| range_pct      |        0.0146 | 0.38385 | 3540 |
| vol_ratio      |        0.0139 | 0.40789 | 3540 |

Most BEARISH features:

| feature    |   spearman_ic |       p |    n |
|:-----------|--------------:|--------:|-----:|
| macd_hist  |       -0.0703 | 3e-05   | 3540 |
| roc_10     |       -0.0611 | 0.00028 | 3530 |
| vol_climax |       -0.0566 | 0.00076 | 3540 |
| stoch_k    |       -0.056  | 0.00088 | 3527 |
| williams_r |       -0.056  | 0.00088 | 3527 |
| bb_pct     |       -0.0559 | 0.00091 | 3521 |
| ema9_slope |       -0.0469 | 0.00524 | 3539 |
| dist_ema9  |       -0.0468 | 0.00538 | 3540 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2015-03->2018-01 | +0.0083 | 708 |
| 2018-01->2020-10 | +0.0327 | 708 |
| 2020-10->2023-08 | +0.0820 | 708 |
| 2023-08->2026-06 | -0.0112 | 708 |

**Mean OOS rank-IC = +0.0279** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature        |   importance |
|:---------------|-------------:|
| dist_ema200    |   0.298587   |
| ema_stack_bull |   0.141624   |
| macd_hist      |   0.0414222  |
| rsi            |   0.0352304  |
| dist_lo_20     |   0.0341058  |
| bb_pct         |   0.0318221  |
| dist_ema50     |   0.0168162  |
| atr_pct        |   0.0152611  |
| bb_width       |   0.0129401  |
| mfi            |   0.0104767  |
| roc_10         |   0.00709249 |
| dist_ema20     |   0.00546214 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=51, win 65%. Winners vs losers (Cohen's d): `vol_z` lower (d=-0.74), `vol_climax` lower (d=-0.68), `upper_wick` lower (d=-0.68), `bb_pct` lower (d=-0.59), `macd_hist` lower (d=-0.56), `consec_dir` higher (d=+0.53)

**double_bottom (long)** — n=96, win 52%. Winners vs losers (Cohen's d): `ema_stack_bear` lower (d=-0.77), `macd_bull_cross` lower (d=-0.63), `rsi` higher (d=+0.53), `ema_stack_bull` higher (d=+0.47), `dist_hi_20` higher (d=+0.42), `bb_break_up` higher (d=+0.38)

**inverted_hammer (long)** — n=53, win 75%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.50), `rsi_oversold` higher (d=+0.38), `body_dir` lower (d=-0.33), `bb_squeeze` higher (d=+0.33), `macd_bear_cross` higher (d=+0.33), `bb_pct` lower (d=-0.32)

**bullish_harami (long)** — n=118, win 58%. Winners vs losers (Cohen's d): `consec_dir` lower (d=-0.27), `body_pct` lower (d=-0.25), `rsi` higher (d=+0.25), `bb_pct` higher (d=+0.24), `roc_10` higher (d=+0.24), `dist_hi_20` higher (d=+0.23)

**morning_star (long)** — n=36, win 56%. Winners vs losers (Cohen's d): `lower_wick` higher (d=+0.78), `candle_ret` lower (d=-0.53), `body_pct` lower (d=-0.53), `rsi_oversold` lower (d=-0.39), `macd_bull_cross` lower (d=-0.39), `dist_ema200` higher (d=+0.34)

**bearish_engulfing (short)** — n=146, win 47%. Winners vs losers (Cohen's d): `macd_hist` lower (d=-0.40), `dist_hi_20` lower (d=-0.38), `bb_squeeze` lower (d=-0.36), `roc_10` lower (d=-0.36), `dist_ema20` lower (d=-0.35), `mfi` lower (d=-0.35)

**shooting_star (short)** — n=87, win 39%. Winners vs losers (Cohen's d): `ema_stack_bear` higher (d=+0.48), `ema_stack_bull` lower (d=-0.46), `rsi_slope` higher (d=+0.44), `dist_hi_20` higher (d=+0.38), `williams_r` higher (d=+0.37), `stoch_k` higher (d=+0.37)

**evening_star (short)** — n=42, win 52%. Winners vs losers (Cohen's d): `atr_pct` higher (d=+0.82), `range_pct` higher (d=+0.67), `gap_pct` lower (d=-0.62), `cc_ret` lower (d=-0.59), `ema_stack_bear` higher (d=+0.56), `dist_hi_20` lower (d=-0.54)

**hanging_man (short)** — n=100, win 48%. Winners vs losers (Cohen's d): `rsi_overbought` higher (d=+0.64), `vol_z` higher (d=+0.49), `vol_ratio` higher (d=+0.46), `rsi` higher (d=+0.43), `mfi` higher (d=+0.42), `macd_bull_cross` higher (d=+0.37)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.56 sd
- `above_ema200`: -0.46 sd
- `range_pct`: +0.43 sd
- `ema_stack_bull`: -0.39 sd
- `dist_ema200`: -0.37 sd
- `ema_stack_bear`: +0.29 sd
- `rsi`: -0.29 sd
- `dist_ema50`: -0.28 sd

## 5. Exit timing (winning long setups)

Entries=292. Avg cumulative return peaks at **+15 days** (+1.01%); average max adverse excursion (stop guide) **-4.67%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.11 | +0.32 | +0.49 | +0.65 | +0.62 | +0.63 | +0.64 | +0.57 | +0.96 | +0.86 | +0.84 | +0.96 | +0.80 | +0.88 | +1.01 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema200 <= 13.29
|   |--- rsi <= 34.16
|   |   |--- value: [-0.75]
|   |--- rsi >  34.16
|   |   |--- value: [1.18]
|--- dist_ema200 >  13.29
|   |--- dist_ema200 <= 21.97
|   |   |--- value: [-0.73]
|   |--- dist_ema200 >  21.97
|   |   |--- value: [1.19]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | -0.748 | +2.142 | 112 |
| 3 | +1.178 | -0.200 | 621 |
| 5 | -0.726 | +1.029 | 394 |
| 6 | +1.185 | +0.313 | 289 |
