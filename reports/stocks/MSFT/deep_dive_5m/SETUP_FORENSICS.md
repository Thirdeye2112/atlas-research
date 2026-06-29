# MSFT setup forensics (intraday) — horizon 6bars

Bars 67,609 (2023-01-03->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |     n |
|:----------------|--------------:|--------:|------:|
| vol_z           |        0.0127 | 0.00096 | 67584 |
| vol_climax      |        0.0109 | 0.00472 | 67603 |
| bb_break_dn     |        0.0108 | 0.00498 | 67603 |
| macd_hist       |        0.0102 | 0.00808 | 67603 |
| vol_ratio       |        0.0096 | 0.01293 | 67603 |
| macd_bear_cross |        0.0095 | 0.01364 | 67603 |
| upper_wick      |        0.0074 | 0.05627 | 67370 |
| roc_10          |        0.0066 | 0.08541 | 67593 |

Most BEARISH features:

| feature     |   spearman_ic |       p |     n |
|:------------|--------------:|--------:|------:|
| candle_ret  |       -0.0192 | 0       | 67603 |
| rsi_slope   |       -0.0172 | 1e-05   | 67599 |
| cc_ret      |       -0.0164 | 2e-05   | 67602 |
| consec_dir  |       -0.0161 | 3e-05   | 67603 |
| body_dir    |       -0.0151 | 9e-05   | 67603 |
| or_position |       -0.0093 | 0.01541 | 67603 |
| mfi         |       -0.0089 | 0.02095 | 67571 |
| bb_squeeze  |       -0.0082 | 0.03354 | 67603 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2023-09->2024-05 | +0.0192 | 13521 |
| 2024-05->2025-02 | +0.0370 | 13520 |
| 2025-02->2025-10 | +0.0087 | 13521 |
| 2025-10->2026-06 | +0.0112 | 13521 |

**Mean OOS rank-IC = +0.0190** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| tod_min     |  0.0213964   |
| atr_pct     |  0.0207871   |
| dist_hi_20  |  0.0168758   |
| or_position |  0.00984522  |
| range_pct   |  0.00909982  |
| roc_10      |  0.00477549  |
| vwap_dist   |  0.00400131  |
| rsi         |  0.00293519  |
| vol_ratio   |  0.00230715  |
| vol_z       |  0.00151578  |
| mfi         |  0.000892688 |
| upper_wick  |  0.000651362 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=3388, win 50%. Winners vs losers (Cohen's d): `upper_wick` higher (d=+0.11), `bb_squeeze` lower (d=-0.10), `williams_r` lower (d=-0.09), `stoch_k` lower (d=-0.09), `dist_hi_20` lower (d=-0.06), `ema_stack_bear` higher (d=+0.06)

**inverted_hammer (long)** — n=1773, win 51%. Winners vs losers (Cohen's d): `atr_pct` higher (d=+0.08), `body_pct` higher (d=+0.07), `ema_stack_bear` lower (d=-0.06), `vol_z` lower (d=-0.06), `vol_ratio` lower (d=-0.06), `ema_stack_bull` higher (d=+0.06)

**bullish_harami (long)** — n=2462, win 51%. Winners vs losers (Cohen's d): `rsi_slope` lower (d=-0.07), `bb_break_dn` higher (d=+0.06), `stoch_k` higher (d=+0.06), `williams_r` higher (d=+0.06), `macd_hist` higher (d=+0.06), `vol_ratio` higher (d=+0.04)

**morning_star (long)** — n=643, win 50%. Winners vs losers (Cohen's d): `roc_10` higher (d=+0.17), `or_position` higher (d=+0.15), `vol_z` lower (d=-0.13), `dist_ema20` higher (d=+0.13), `dist_ema50` higher (d=+0.13), `lower_wick` higher (d=+0.13)

**bearish_engulfing (short)** — n=3436, win 48%. Winners vs losers (Cohen's d): `ema_stack_bear` higher (d=+0.06), `bb_width` higher (d=+0.05), `dist_hi_20` lower (d=-0.05), `rsi` lower (d=-0.05), `upper_wick` higher (d=+0.04), `above_ema200` lower (d=-0.04)

**shooting_star (short)** — n=1807, win 48%. Winners vs losers (Cohen's d): `dist_lo_20` lower (d=-0.13), `dist_ema200` lower (d=-0.11), `bb_width` lower (d=-0.11), `roc_10` lower (d=-0.10), `macd_bull_cross` higher (d=+0.10), `dist_ema20` lower (d=-0.10)

**evening_star (short)** — n=643, win 51%. Winners vs losers (Cohen's d): `mfi` higher (d=+0.28), `bb_pct` higher (d=+0.20), `consec_dir` lower (d=-0.16), `williams_r` higher (d=+0.15), `stoch_k` higher (d=+0.15), `tod_min` lower (d=-0.12)

**hanging_man (short)** — n=1940, win 51%. Winners vs losers (Cohen's d): `rsi` lower (d=-0.10), `atr_pct` higher (d=+0.09), `rsi_oversold` lower (d=-0.08), `vol_ratio` higher (d=+0.07), `dist_hi_20` lower (d=-0.07), `bb_break_up` lower (d=-0.06)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.51 sd
- `atr_pct`: +0.48 sd
- `bb_width`: +0.36 sd
- `body_pct`: +0.36 sd
- `dist_hi_20`: -0.32 sd
- `vol_z`: +0.32 sd
- `vol_ratio`: +0.31 sd
- `vol_climax`: +0.23 sd

## 5. Exit timing (winning long setups)

Entries=6682. Avg cumulative return peaks at **+18 bars** (+0.02%); average max adverse excursion (stop guide) **-0.38%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- tod_min <= 1167.50
|   |--- or_position <= 0.45
|   |   |--- value: [0.01]
|   |--- or_position >  0.45
|   |   |--- value: [-0.00]
|--- tod_min >  1167.50
|   |--- dist_ema200 <= 0.22
|   |   |--- value: [0.09]
|   |--- dist_ema200 >  0.22
|   |   |--- value: [-0.02]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.014 | +0.004 | 10814 |
| 3 | -0.004 | -0.001 | 12886 |
| 5 | +0.091 | -0.006 | 2156 |
| 6 | -0.022 | -0.046 | 1186 |
