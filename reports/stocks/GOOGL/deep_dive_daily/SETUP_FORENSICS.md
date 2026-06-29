# GOOGL setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| rsi_oversold    |        0.0977 | 0       | 3776 |
| bb_squeeze      |        0.0449 | 0.00577 | 3776 |
| bb_break_dn     |        0.0422 | 0.00942 | 3776 |
| ema_stack_bear  |        0.0381 | 0.01915 | 3776 |
| range_pct       |        0.0343 | 0.03532 | 3776 |
| atr_pct         |        0.0333 | 0.04058 | 3776 |
| macd_bull_cross |        0.0281 | 0.08434 | 3776 |
| upper_wick      |        0.0223 | 0.16977 | 3776 |

Most BEARISH features:

| feature     |   spearman_ic |     p |    n |
|:------------|--------------:|------:|-----:|
| williams_r  |       -0.0793 | 0     | 3763 |
| stoch_k     |       -0.0793 | 0     | 3763 |
| ema9_slope  |       -0.073  | 1e-05 | 3775 |
| dist_ema9   |       -0.0729 | 1e-05 | 3776 |
| rsi         |       -0.0719 | 1e-05 | 3774 |
| bb_pct      |       -0.0717 | 1e-05 | 3757 |
| dist_ema20  |       -0.0712 | 1e-05 | 3776 |
| dist_ema200 |       -0.0659 | 5e-05 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.0276 | 755 |
| 2017-06->2020-06 | +0.1212 | 755 |
| 2020-06->2023-06 | -0.0564 | 755 |
| 2023-06->2026-06 | +0.1578 | 756 |

**Mean OOS rank-IC = +0.0625** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature         |   importance |
|:----------------|-------------:|
| dist_hi_20      |  0.0571636   |
| macd_hist       |  0.0544972   |
| dist_ema50      |  0.0346022   |
| atr_pct         |  0.0169817   |
| dist_ema200     |  0.0165517   |
| dist_ema20      |  0.0143941   |
| rsi             |  0.0126507   |
| consec_dir      |  0.0110801   |
| bb_pct          |  0.00725739  |
| cc_ret          |  0.00141724  |
| lower_wick      |  0.000664915 |
| macd_bull_cross |  0.000626398 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=52, win 52%. Winners vs losers (Cohen's d): `consec_dir` lower (d=-0.42), `vol_climax` higher (d=+0.39), `mfi` lower (d=-0.34), `macd_bull_cross` higher (d=+0.31), `gap_pct` higher (d=+0.31), `bb_squeeze` lower (d=-0.30)

**double_bottom (long)** — n=131, win 57%. Winners vs losers (Cohen's d): `body_pct` higher (d=+0.44), `lower_wick` lower (d=-0.36), `range_pct` higher (d=+0.33), `rsi` higher (d=+0.32), `candle_ret` higher (d=+0.31), `bb_squeeze` higher (d=+0.28)

**inverted_hammer (long)** — n=61, win 67%. Winners vs losers (Cohen's d): `bb_width` lower (d=-0.42), `dist_lo_20` lower (d=-0.41), `macd_hist` higher (d=+0.39), `above_ema200` higher (d=+0.38), `ema_stack_bull` higher (d=+0.31), `atr_pct` lower (d=-0.27)

**bullish_harami (long)** — n=118, win 60%. Winners vs losers (Cohen's d): `rsi` higher (d=+0.37), `bb_pct` higher (d=+0.35), `stoch_k` higher (d=+0.34), `williams_r` higher (d=+0.34), `bb_break_dn` lower (d=-0.26), `dist_ema20` higher (d=+0.26)

**morning_star (long)** — n=44, win 45%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.62), `range_pct` lower (d=-0.49), `bb_squeeze` higher (d=+0.44), `ema_stack_bear` lower (d=-0.43), `bb_break_up` lower (d=-0.41), `above_ema200` higher (d=+0.40)

**bearish_engulfing (short)** — n=149, win 45%. Winners vs losers (Cohen's d): `above_ema200` higher (d=+0.36), `atr_pct` lower (d=-0.28), `ema_stack_bear` lower (d=-0.28), `ema_stack_bull` higher (d=+0.25), `gap_pct` lower (d=-0.23), `dist_hi_20` higher (d=+0.23)

**shooting_star (short)** — n=80, win 45%. Winners vs losers (Cohen's d): `consec_dir` higher (d=+0.49), `vol_z` lower (d=-0.39), `vol_ratio` lower (d=-0.39), `ema_stack_bear` higher (d=+0.28), `candle_ret` higher (d=+0.27), `mfi` higher (d=+0.27)

**evening_star (short)** — n=41, win 56%. Winners vs losers (Cohen's d): `lower_wick` higher (d=+0.57), `macd_bear_cross` lower (d=-0.54), `vol_ratio` higher (d=+0.45), `bb_break_dn` higher (d=+0.41), `vol_z` higher (d=+0.40), `cc_ret` lower (d=-0.37)

**hanging_man (short)** — n=110, win 45%. Winners vs losers (Cohen's d): `bb_pct` higher (d=+0.57), `stoch_k` higher (d=+0.51), `williams_r` higher (d=+0.51), `dist_ema9` higher (d=+0.51), `ema9_slope` higher (d=+0.51), `vol_z` higher (d=+0.43)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.28 sd
- `range_pct`: +0.26 sd
- `above_ema200`: -0.25 sd
- `vol_z`: +0.24 sd
- `vol_ratio`: +0.21 sd
- `body_pct`: +0.16 sd
- `ema_stack_bull`: -0.15 sd
- `ema_stack_bear`: +0.14 sd

## 5. Exit timing (winning long setups)

Entries=329. Avg cumulative return peaks at **+15 days** (+1.59%); average max adverse excursion (stop guide) **-3.43%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.24 | +0.22 | +0.24 | +0.44 | +0.56 | +0.61 | +0.73 | +0.70 | +0.87 | +1.06 | +1.12 | +1.24 | +1.25 | +1.42 | +1.59 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema200 <= 9.92
|   |--- dist_ema200 <= -4.05
|   |   |--- value: [2.14]
|   |--- dist_ema200 >  -4.05
|   |   |--- value: [0.71]
|--- dist_ema200 >  9.92
|   |--- vol_ratio <= 1.29
|   |   |--- value: [-0.13]
|   |--- vol_ratio >  1.29
|   |   |--- value: [-1.17]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +2.141 | +0.299 | 260 |
| 3 | +0.714 | +0.891 | 402 |
| 5 | -0.133 | +0.487 | 727 |
| 6 | -1.167 | +1.151 | 122 |
