# WMT setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| atr_pct         |        0.0579 | 0.00037 | 3776 |
| upper_wick      |        0.0461 | 0.00457 | 3776 |
| rsi_oversold    |        0.0334 | 0.04037 | 3776 |
| ema_stack_bear  |        0.0301 | 0.06476 | 3776 |
| range_pct       |        0.0251 | 0.1234  | 3776 |
| bb_break_dn     |        0.0224 | 0.16957 | 3776 |
| macd_bear_cross |        0.0147 | 0.36543 | 3776 |
| bb_break_up     |        0.0139 | 0.39159 | 3776 |

Most BEARISH features:

| feature      |   spearman_ic |       p |    n |
|:-------------|--------------:|--------:|-----:|
| above_ema200 |       -0.0637 | 9e-05   | 3776 |
| dist_ema200  |       -0.0464 | 0.00438 | 3776 |
| dist_ema50   |       -0.0426 | 0.00881 | 3776 |
| rsi          |       -0.0366 | 0.02442 | 3774 |
| dist_ema20   |       -0.0351 | 0.03084 | 3776 |
| dist_hi_20   |       -0.0337 | 0.0388  | 3757 |
| dist_ema9    |       -0.0314 | 0.05334 | 3776 |
| ema9_slope   |       -0.0314 | 0.05353 | 3775 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.0063 | 755 |
| 2017-06->2020-06 | -0.0615 | 755 |
| 2020-06->2023-06 | +0.0588 | 755 |
| 2023-06->2026-06 | +0.0383 | 756 |

**Mean OOS rank-IC = +0.0105** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| dist_ema9   |   0.0439508  |
| dist_ema20  |   0.0236732  |
| dist_ema200 |   0.0230253  |
| atr_pct     |   0.0185638  |
| macd_hist   |   0.0162548  |
| dist_hi_20  |   0.0155923  |
| bb_pct      |   0.011413   |
| vol_z       |   0.010748   |
| cc_ret      |   0.0105956  |
| vol_ratio   |   0.00680397 |
| ema9_slope  |   0.00387988 |
| lower_wick  |   0.0021417  |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=137, win 57%. Winners vs losers (Cohen's d): `roc_10` higher (d=+0.53), `williams_r` higher (d=+0.47), `stoch_k` higher (d=+0.47), `macd_bull_cross` lower (d=-0.42), `vol_z` lower (d=-0.37), `dist_ema20` higher (d=+0.35)

**inverted_hammer (long)** — n=64, win 55%. Winners vs losers (Cohen's d): `roc_10` lower (d=-0.43), `body_dir` higher (d=+0.42), `consec_dir` higher (d=+0.36), `macd_bull_cross` lower (d=-0.28), `vol_climax` lower (d=-0.28), `lower_wick` higher (d=+0.28)

**bullish_harami (long)** — n=127, win 66%. Winners vs losers (Cohen's d): `stoch_k` higher (d=+0.25), `williams_r` higher (d=+0.25), `macd_bull_cross` higher (d=+0.24), `dist_lo_20` higher (d=+0.20), `gap_pct` lower (d=-0.20), `rsi_oversold` higher (d=+0.17)

**morning_star (long)** — n=32, win 53%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.63), `ema_stack_bear` higher (d=+0.59), `dist_ema200` lower (d=-0.55), `rsi_slope` higher (d=+0.50), `cc_ret` higher (d=+0.47), `lower_wick` lower (d=-0.43)

**bearish_engulfing (short)** — n=153, win 50%. Winners vs losers (Cohen's d): `range_pct` lower (d=-0.31), `cc_ret` higher (d=+0.30), `macd_bear_cross` lower (d=-0.24), `candle_ret` higher (d=+0.24), `body_pct` lower (d=-0.24), `dist_lo_20` higher (d=+0.21)

**shooting_star (short)** — n=112, win 43%. Winners vs losers (Cohen's d): `bb_squeeze` higher (d=+0.48), `above_ema200` higher (d=+0.30), `bb_break_up` higher (d=+0.28), `atr_pct` lower (d=-0.28), `dist_hi_20` higher (d=+0.27), `macd_bear_cross` lower (d=-0.26)

**evening_star (short)** — n=45, win 40%. Winners vs losers (Cohen's d): `above_ema200` higher (d=+0.55), `rsi_overbought` lower (d=-0.54), `ema_stack_bear` lower (d=-0.47), `bb_squeeze` higher (d=+0.46), `vol_z` lower (d=-0.42), `vol_ratio` lower (d=-0.39)

**hanging_man (short)** — n=87, win 43%. Winners vs losers (Cohen's d): `vol_z` higher (d=+0.51), `vol_ratio` higher (d=+0.45), `rsi_slope` lower (d=-0.41), `body_pct` higher (d=+0.39), `range_pct` higher (d=+0.38), `gap_pct` lower (d=-0.37)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.28 sd
- `range_pct`: +0.28 sd
- `bb_width`: +0.26 sd
- `body_pct`: +0.23 sd
- `vol_ratio`: +0.23 sd
- `vol_z`: +0.20 sd
- `dist_lo_20`: +0.20 sd
- `candle_ret`: +0.14 sd

## 5. Exit timing (winning long setups)

Entries=319. Avg cumulative return peaks at **+15 days** (+1.38%); average max adverse excursion (stop guide) **-2.32%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.15 | +0.13 | +0.30 | +0.33 | +0.42 | +0.47 | +0.53 | +0.63 | +0.77 | +0.85 | +0.91 | +1.11 | +1.06 | +1.15 | +1.38 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- atr_pct <= 1.15
|   |--- bb_width <= 5.36
|   |   |--- value: [-0.58]
|   |--- bb_width >  5.36
|   |   |--- value: [0.20]
|--- atr_pct >  1.15
|   |--- macd_hist <= 0.12
|   |   |--- value: [0.40]
|   |--- macd_hist >  0.12
|   |   |--- value: [-0.45]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | -0.576 | -1.250 | 14 |
| 3 | +0.200 | +0.883 | 28 |
| 5 | +0.401 | +0.420 | 1024 |
| 6 | -0.448 | +0.407 | 445 |
