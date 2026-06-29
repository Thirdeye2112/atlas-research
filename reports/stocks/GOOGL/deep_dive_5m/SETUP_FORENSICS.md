# GOOGL setup forensics (intraday) — horizon 6bars

Bars 101,927 (2021-01-04->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |      n |
|:---------------|--------------:|--------:|-------:|
| vol_ratio      |        0.0106 | 0.0007  | 101921 |
| tod_min        |        0.01   | 0.00145 | 101921 |
| bb_break_dn    |        0.0098 | 0.00183 | 101921 |
| vol_z          |        0.0093 | 0.0029  | 101902 |
| vol_climax     |        0.0067 | 0.03354 | 101921 |
| bb_squeeze     |        0.0052 | 0.0988  | 101921 |
| ema_stack_bear |        0.0042 | 0.18141 | 101921 |
| range_pct      |        0.0026 | 0.41496 |  96955 |

Most BEARISH features:

| feature     |   spearman_ic |   p |      n |
|:------------|--------------:|----:|-------:|
| dist_lo_20  |       -0.0183 |   0 | 101902 |
| mfi         |       -0.0183 |   0 | 101879 |
| williams_r  |       -0.0169 |   0 | 101908 |
| stoch_k     |       -0.0169 |   0 | 101908 |
| dist_ema20  |       -0.016  |   0 | 101921 |
| or_position |       -0.0157 |   0 | 101921 |
| rsi         |       -0.0157 |   0 | 101920 |
| bb_pct      |       -0.0156 |   0 | 101902 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-03->2023-05 | +0.0106 | 20384 |
| 2023-05->2024-05 | +0.0230 | 20384 |
| 2024-05->2025-06 | -0.0054 | 20384 |
| 2025-06->2026-06 | +0.0199 | 20385 |

**Mean OOS rank-IC = +0.0120** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| bb_pct      |  0.00388191  |
| rsi         |  0.00301324  |
| bb_width    |  0.00283963  |
| vol_z       |  0.00124223  |
| atr_pct     |  0.000578764 |
| lower_wick  |  0.000544891 |
| dist_lo_20  |  0.00050286  |
| vwap_dist   |  0.000280988 |
| range_pct   |  0.000210639 |
| vol_ratio   |  0.000196737 |
| dist_ema200 |  0.000181123 |
| tod_min     |  0.000174649 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5196, win 51%. Winners vs losers (Cohen's d): `or_position` lower (d=-0.08), `bb_break_up` higher (d=+0.07), `dist_ema200` lower (d=-0.06), `williams_r` lower (d=-0.06), `stoch_k` lower (d=-0.06), `consec_dir` lower (d=-0.06)

**inverted_hammer (long)** — n=2358, win 52%. Winners vs losers (Cohen's d): `dist_ema20` higher (d=+0.08), `dist_ema50` higher (d=+0.08), `atr_pct` lower (d=-0.08), `dist_hi_20` higher (d=+0.08), `dist_ema9` higher (d=+0.07), `ema9_slope` higher (d=+0.07)

**bullish_harami (long)** — n=3306, win 51%. Winners vs losers (Cohen's d): `macd_bull_cross` lower (d=-0.07), `mfi` higher (d=+0.06), `rsi_slope` higher (d=+0.05), `tod_min` higher (d=+0.05), `ema_stack_bull` lower (d=-0.05), `dist_lo_20` higher (d=+0.05)

**morning_star (long)** — n=923, win 52%. Winners vs losers (Cohen's d): `vol_z` lower (d=-0.17), `vol_ratio` lower (d=-0.16), `vol_climax` lower (d=-0.14), `consec_dir` lower (d=-0.14), `mfi` lower (d=-0.12), `tod_min` lower (d=-0.11)

**bearish_engulfing (short)** — n=4715, win 48%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.07), `dist_lo_20` higher (d=+0.06), `mfi` higher (d=+0.06), `candle_ret` lower (d=-0.06), `body_pct` higher (d=+0.06), `bb_pct` higher (d=+0.05)

**shooting_star (short)** — n=2617, win 49%. Winners vs losers (Cohen's d): `consec_dir` higher (d=+0.11), `vol_z` lower (d=-0.07), `body_dir` higher (d=+0.07), `above_ema200` higher (d=+0.06), `vol_ratio` lower (d=-0.06), `body_pct` higher (d=+0.05)

**evening_star (short)** — n=918, win 48%. Winners vs losers (Cohen's d): `bb_width` higher (d=+0.17), `dist_lo_20` higher (d=+0.13), `above_ema200` lower (d=-0.11), `bb_break_dn` higher (d=+0.11), `atr_pct` higher (d=+0.11), `or_position` higher (d=+0.10)

**hanging_man (short)** — n=2802, win 48%. Winners vs losers (Cohen's d): `mfi` higher (d=+0.10), `bb_squeeze` lower (d=-0.09), `dist_lo_20` higher (d=+0.07), `dist_ema20` higher (d=+0.07), `ema9_slope` higher (d=+0.07), `dist_ema9` higher (d=+0.07)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.45 sd
- `vol_ratio`: +0.36 sd
- `vol_z`: +0.35 sd
- `body_pct`: +0.33 sd
- `vol_climax`: +0.29 sd
- `dist_lo_20`: +0.27 sd
- `bb_squeeze`: -0.14 sd
- `rsi_oversold`: +0.14 sd

## 5. Exit timing (winning long setups)

Entries=9527. Avg cumulative return peaks at **+18 bars** (+0.02%); average max adverse excursion (stop guide) **-0.50%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.01 | -0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.01 | +0.02 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- bb_width <= 0.35
|   |--- value: [-0.11]
|--- bb_width >  0.35
|   |--- atr_pct <= 0.11
|   |   |--- value: [-0.04]
|   |--- atr_pct >  0.11
|   |   |--- value: [0.01]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 1 | -0.110 | +0.053 | 2874 |
| 3 | -0.042 | +0.072 | 1897 |
| 4 | +0.010 | +0.005 | 35998 |
