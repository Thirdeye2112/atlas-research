# XOM setup forensics (intraday) — horizon 6bars

Bars 106,039 (2021-01-04->2026-06-18). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature      |   spearman_ic |       p |      n |
|:-------------|--------------:|--------:|-------:|
| bb_width     |        0.0191 | 0       | 106014 |
| range_pct    |        0.0187 | 0       | 105790 |
| vol_climax   |        0.0181 | 0       | 106033 |
| rsi_oversold |        0.0132 | 2e-05   | 106033 |
| atr_pct      |        0.0124 | 5e-05   | 106033 |
| body_pct     |        0.0121 | 8e-05   | 106033 |
| vol_ratio    |        0.0097 | 0.00163 | 106033 |
| tod_min      |        0.0094 | 0.00231 | 106033 |

Most BEARISH features:

| feature     |   spearman_ic |       p |      n |
|:------------|--------------:|--------:|-------:|
| or_position |       -0.0174 | 0       | 106033 |
| dist_hi_20  |       -0.0173 | 0       | 106014 |
| bb_squeeze  |       -0.0159 | 0       | 106033 |
| mfi         |       -0.0143 | 0       | 105978 |
| bb_pct      |       -0.0121 | 8e-05   | 106014 |
| williams_r  |       -0.0112 | 0.00027 | 106020 |
| stoch_k     |       -0.0112 | 0.00027 | 106020 |
| rsi         |       -0.0104 | 0.00074 | 106032 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0384 | 21207 |
| 2023-03->2024-04 | +0.0367 | 21206 |
| 2024-04->2025-05 | +0.0258 | 21207 |
| 2025-05->2026-06 | +0.0627 | 21207 |

**Mean OOS rank-IC = +0.0409** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| or_position |   0.0329855  |
| tod_min     |   0.0186053  |
| vwap_dist   |   0.0141359  |
| dist_ema200 |   0.00476259 |
| mfi         |   0.00347296 |
| vol_z       |   0.00240502 |
| dist_ema50  |   0.00203737 |
| dist_hi_20  |   0.00154352 |
| rsi_slope   |   0.00148133 |
| roc_10      |   0.00141655 |
| atr_pct     |   0.00124607 |
| gap_pct     |   0.00122297 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5492, win 50%. Winners vs losers (Cohen's d): `or_position` lower (d=-0.15), `ema_stack_bull` lower (d=-0.09), `macd_bull_cross` higher (d=+0.08), `mfi` lower (d=-0.07), `ema_stack_bear` higher (d=+0.06), `vwap_dist` lower (d=-0.06)

**inverted_hammer (long)** — n=2814, win 51%. Winners vs losers (Cohen's d): `vol_ratio` higher (d=+0.10), `tod_min` higher (d=+0.10), `or_position` lower (d=-0.09), `vol_climax` higher (d=+0.07), `vol_z` higher (d=+0.07), `vwap_dist` lower (d=-0.06)

**bullish_harami (long)** — n=4118, win 52%. Winners vs losers (Cohen's d): `tod_min` higher (d=+0.08), `roc_10` higher (d=+0.06), `ema9_slope` higher (d=+0.06), `dist_ema9` higher (d=+0.06), `dist_ema20` higher (d=+0.06), `dist_hi_20` higher (d=+0.05)

**morning_star (long)** — n=878, win 50%. Winners vs losers (Cohen's d): `consec_dir` lower (d=-0.19), `vol_climax` lower (d=-0.11), `ema_stack_bull` higher (d=+0.11), `mfi` higher (d=+0.10), `vol_z` lower (d=-0.09), `rsi` higher (d=+0.08)

**bearish_engulfing (short)** — n=5597, win 49%. Winners vs losers (Cohen's d): `bb_squeeze` higher (d=+0.07), `dist_lo_20` lower (d=-0.05), `bb_width` lower (d=-0.05), `upper_wick` higher (d=+0.04), `above_vwap` lower (d=-0.04), `above_ema200` lower (d=-0.04)

**shooting_star (short)** — n=3057, win 50%. Winners vs losers (Cohen's d): `above_vwap` lower (d=-0.06), `macd_bull_cross` lower (d=-0.05), `rsi_slope` higher (d=+0.05), `range_pct` higher (d=+0.05), `body_pct` higher (d=+0.05), `bb_squeeze` higher (d=+0.05)

**evening_star (short)** — n=828, win 47%. Winners vs losers (Cohen's d): `rsi_oversold` lower (d=-0.11), `lower_wick` lower (d=-0.11), `upper_wick` higher (d=+0.11), `macd_bear_cross` lower (d=-0.10), `mfi` higher (d=+0.08), `ema_stack_bear` higher (d=+0.08)

**hanging_man (short)** — n=3201, win 48%. Winners vs losers (Cohen's d): `upper_wick` higher (d=+0.06), `vol_z` higher (d=+0.06), `body_dir` lower (d=-0.05), `vol_ratio` higher (d=+0.05), `gap_pct` higher (d=+0.05), `lower_wick` lower (d=-0.04)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.50 sd
- `atr_pct`: +0.46 sd
- `body_pct`: +0.34 sd
- `bb_width`: +0.31 sd
- `vol_z`: +0.30 sd
- `vol_ratio`: +0.30 sd
- `dist_hi_20`: -0.27 sd
- `vol_climax`: +0.24 sd

## 5. Exit timing (winning long setups)

Entries=10821. Avg cumulative return peaks at **+18 bars** (+0.03%); average max adverse excursion (stop guide) **-0.46%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.01 | +0.01 | +0.01 | +0.02 | +0.02 | +0.02 | +0.02 | +0.02 | +0.03 | +0.03 | +0.03 | +0.03 | +0.03 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- tod_min <= 1167.50
|   |--- or_position <= 0.43
|   |   |--- value: [0.02]
|   |--- or_position >  0.43
|   |   |--- value: [-0.01]
|--- tod_min >  1167.50
|   |--- dist_hi_20 <= -0.23
|   |   |--- value: [0.11]
|   |--- dist_hi_20 >  -0.23
|   |   |--- value: [0.01]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.022 | +0.011 | 15949 |
| 3 | -0.011 | -0.005 | 21251 |
| 5 | +0.107 | +0.034 | 2623 |
| 6 | +0.010 | -0.021 | 2591 |
