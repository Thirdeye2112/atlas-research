# AAPL setup forensics (intraday) — horizon 6bars

Bars 67,664 (2023-01-03->2026-06-26). 42 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |     n |
|:----------------|--------------:|--------:|------:|
| vol_climax      |        0.0176 | 0       | 67658 |
| range_pct       |        0.0146 | 0.00015 | 67652 |
| bb_break_dn     |        0.0139 | 0.00029 | 67658 |
| rsi_oversold    |        0.0103 | 0.00766 | 67658 |
| vol_z           |        0.0102 | 0.00805 | 67639 |
| macd_bear_cross |        0.0069 | 0.07197 | 67658 |
| body_pct        |        0.0062 | 0.10517 | 67658 |
| upper_wick      |        0.0057 | 0.1369  | 67652 |

Most BEARISH features:

| feature     |   spearman_ic |       p |     n |
|:------------|--------------:|--------:|------:|
| dist_ema9   |       -0.017  | 1e-05   | 67658 |
| ema9_slope  |       -0.017  | 1e-05   | 67657 |
| consec_dir  |       -0.0169 | 1e-05   | 67658 |
| bb_squeeze  |       -0.0167 | 1e-05   | 67658 |
| candle_ret  |       -0.0161 | 3e-05   | 67658 |
| or_position |       -0.0154 | 6e-05   | 67658 |
| rsi_slope   |       -0.0143 | 0.00021 | 67654 |
| rsi         |       -0.0138 | 0.00033 | 67656 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2023-09->2024-05 | +0.0112 | 13532 |
| 2024-05->2025-02 | +0.0172 | 13531 |
| 2025-02->2025-10 | -0.0177 | 13532 |
| 2025-10->2026-06 | +0.0438 | 13532 |

**Mean OOS rank-IC = +0.0136** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| vwap_dist   |   0.0408705  |
| tod_min     |   0.0351383  |
| bb_width    |   0.0165156  |
| atr_pct     |   0.0144932  |
| or_position |   0.014443   |
| dist_lo_20  |   0.0113526  |
| mfi         |   0.00998552 |
| dist_ema200 |   0.00648653 |
| macd_hist   |   0.00561606 |
| bb_squeeze  |   0.00424612 |
| dist_ema9   |   0.00185546 |
| rsi_slope   |   0.00166502 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=3463, win 51%. Winners vs losers (Cohen's d): `or_position` lower (d=-0.14), `bb_break_up` lower (d=-0.08), `rsi_slope` lower (d=-0.07), `dist_ema200` lower (d=-0.06), `macd_bull_cross` lower (d=-0.06), `vol_ratio` lower (d=-0.06)

**inverted_hammer (long)** — n=1715, win 52%. Winners vs losers (Cohen's d): `above_vwap` lower (d=-0.13), `bb_squeeze` lower (d=-0.12), `rsi` lower (d=-0.12), `williams_r` lower (d=-0.12), `stoch_k` lower (d=-0.12), `or_position` lower (d=-0.12)

**bullish_harami (long)** — n=2451, win 51%. Winners vs losers (Cohen's d): `rsi_oversold` higher (d=+0.13), `rsi` lower (d=-0.09), `ema_stack_bull` lower (d=-0.08), `upper_wick` higher (d=+0.08), `lower_wick` lower (d=-0.08), `dist_ema50` lower (d=-0.07)

**morning_star (long)** — n=589, win 46%. Winners vs losers (Cohen's d): `bb_width` lower (d=-0.18), `rsi_overbought` lower (d=-0.18), `upper_wick` lower (d=-0.14), `atr_pct` lower (d=-0.13), `dist_hi_20` higher (d=+0.12), `consec_dir` higher (d=+0.11)

**bearish_engulfing (short)** — n=3887, win 48%. Winners vs losers (Cohen's d): `rsi_oversold` lower (d=-0.04), `bb_squeeze` higher (d=+0.04), `macd_hist` higher (d=+0.04), `above_ema200` lower (d=-0.04), `rsi_overbought` higher (d=+0.04), `dist_lo_20` higher (d=+0.04)

**shooting_star (short)** — n=1893, win 46%. Winners vs losers (Cohen's d): `dist_ema200` lower (d=-0.11), `mfi` lower (d=-0.11), `ema_stack_bear` higher (d=+0.09), `above_vwap` lower (d=-0.09), `macd_bull_cross` higher (d=+0.09), `williams_r` lower (d=-0.09)

**evening_star (short)** — n=565, win 47%. Winners vs losers (Cohen's d): `vol_climax` lower (d=-0.22), `bb_squeeze` lower (d=-0.21), `ema_stack_bear` lower (d=-0.21), `vol_ratio` lower (d=-0.20), `rsi_slope` higher (d=+0.17), `dist_ema9` higher (d=+0.17)

**hanging_man (short)** — n=1975, win 50%. Winners vs losers (Cohen's d): `vol_z` lower (d=-0.14), `vol_ratio` lower (d=-0.13), `vol_climax` lower (d=-0.11), `vwap_dist` higher (d=+0.11), `bb_break_dn` lower (d=-0.09), `range_pct` lower (d=-0.09)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.49 sd
- `atr_pct`: +0.49 sd
- `bb_width`: +0.38 sd
- `body_pct`: +0.36 sd
- `vol_ratio`: +0.34 sd
- `vol_z`: +0.33 sd
- `dist_hi_20`: -0.31 sd
- `dist_lo_20`: +0.28 sd

## 5. Exit timing (winning long setups)

Entries=6677. Avg cumulative return peaks at **+18 bars** (+0.03%); average max adverse excursion (stop guide) **-0.39%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.00 | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.02 | +0.03 | +0.03 | +0.03 | +0.03 | +0.03 | +0.03 | +0.03 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- atr_pct <= 0.31
|   |--- rsi_slope <= 0.61
|   |   |--- value: [0.02]
|   |--- rsi_slope >  0.61
|   |   |--- value: [-0.00]
|--- atr_pct >  0.31
|   |--- value: [0.06]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.015 | +0.006 | 13286 |
| 3 | -0.003 | +0.004 | 10903 |
| 4 | +0.057 | +0.011 | 2875 |
