# META setup forensics (intraday) — horizon 6bars

Bars 106,573 (2021-01-04->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |      n |
|:---------------|--------------:|--------:|-------:|
| vol_climax     |        0.015  | 0       | 106567 |
| bb_break_dn    |        0.0102 | 0.00086 | 106567 |
| ema_stack_bear |        0.0075 | 0.0146  | 106567 |
| vol_ratio      |        0.0066 | 0.03194 | 106567 |
| vol_z          |        0.0059 | 0.05525 | 106548 |
| body_pct       |        0.0046 | 0.12903 | 106567 |
| rsi_oversold   |        0.0027 | 0.37734 | 106567 |
| range_pct      |        0.0026 | 0.40154 | 105879 |

Most BEARISH features:

| feature     |   spearman_ic |       p |      n |
|:------------|--------------:|--------:|-------:|
| or_position |       -0.0137 | 1e-05   | 106567 |
| consec_dir  |       -0.0112 | 0.00026 | 106567 |
| lower_wick  |       -0.0108 | 0.00042 | 105879 |
| body_dir    |       -0.0098 | 0.00142 | 106567 |
| candle_ret  |       -0.0086 | 0.00507 | 106567 |
| vwap_dist   |       -0.0085 | 0.00545 | 106567 |
| rsi         |       -0.0075 | 0.01452 | 106566 |
| bb_pct      |       -0.0074 | 0.01578 | 106548 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0129 | 21313 |
| 2023-03->2024-04 | +0.0014 | 21314 |
| 2024-04->2025-05 | +0.0162 | 21313 |
| 2025-05->2026-06 | +0.0321 | 21314 |

**Mean OOS rank-IC = +0.0156** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| or_position |  0.00682392  |
| tod_min     |  0.00654188  |
| vwap_dist   |  0.00533899  |
| roc_10      |  0.00323917  |
| bb_width    |  0.00130903  |
| dist_lo_20  |  0.00101731  |
| mfi         |  0.000736826 |
| bb_squeeze  |  0.000366936 |
| dist_ema9   |  0.000330168 |
| dist_ema20  |  0.000218064 |
| ema9_slope  |  0.000206247 |
| bb_pct      |  0.000179134 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5448, win 50%. Winners vs losers (Cohen's d): `candle_ret` lower (d=-0.11), `body_dir` lower (d=-0.09), `ema_stack_bull` higher (d=+0.06), `mfi` higher (d=+0.06), `rsi_overbought` higher (d=+0.05), `gap_pct` higher (d=+0.05)

**inverted_hammer (long)** — n=2841, win 51%. Winners vs losers (Cohen's d): `candle_ret` lower (d=-0.07), `consec_dir` lower (d=-0.07), `rsi_slope` lower (d=-0.06), `bb_width` lower (d=-0.06), `mfi` lower (d=-0.06), `above_vwap` lower (d=-0.05)

**bullish_harami (long)** — n=3848, win 50%. Winners vs losers (Cohen's d): `vol_climax` higher (d=+0.06), `tod_min` higher (d=+0.05), `mfi` lower (d=-0.05), `macd_bull_cross` lower (d=-0.05), `vol_ratio` higher (d=+0.05), `body_pct` higher (d=+0.04)

**morning_star (long)** — n=1001, win 49%. Winners vs losers (Cohen's d): `rsi` lower (d=-0.19), `dist_ema200` lower (d=-0.18), `williams_r` lower (d=-0.17), `stoch_k` lower (d=-0.17), `ema_stack_bull` lower (d=-0.17), `bb_pct` lower (d=-0.16)

**bearish_engulfing (short)** — n=5097, win 49%. Winners vs losers (Cohen's d): `or_position` higher (d=+0.04), `atr_pct` higher (d=+0.03), `vwap_dist` higher (d=+0.03), `above_vwap` higher (d=+0.03), `gap_pct` lower (d=-0.03), `ema_stack_bull` higher (d=+0.03)

**shooting_star (short)** — n=3003, win 50%. Winners vs losers (Cohen's d): `vol_z` lower (d=-0.09), `tod_min` lower (d=-0.08), `rsi_slope` higher (d=+0.07), `consec_dir` higher (d=+0.07), `vol_ratio` lower (d=-0.07), `body_dir` higher (d=+0.06)

**evening_star (short)** — n=1017, win 51%. Winners vs losers (Cohen's d): `macd_bear_cross` higher (d=+0.16), `gap_pct` lower (d=-0.13), `rsi_overbought` lower (d=-0.12), `above_ema200` higher (d=+0.11), `ema_stack_bull` higher (d=+0.11), `macd_bull_cross` lower (d=-0.11)

**hanging_man (short)** — n=3092, win 50%. Winners vs losers (Cohen's d): `bb_pct` higher (d=+0.08), `dist_hi_20` higher (d=+0.08), `williams_r` higher (d=+0.08), `stoch_k` higher (d=+0.08), `rsi` higher (d=+0.07), `bb_break_dn` higher (d=+0.06)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.54 sd
- `atr_pct`: +0.53 sd
- `body_pct`: +0.38 sd
- `bb_width`: +0.32 sd
- `vol_ratio`: +0.31 sd
- `vol_z`: +0.31 sd
- `dist_hi_20`: -0.28 sd
- `dist_lo_20`: +0.25 sd

## 5. Exit timing (winning long setups)

Entries=10597. Avg cumulative return peaks at **+5 bars** (+0.01%); average max adverse excursion (stop guide) **-0.61%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.01 | +0.01 | +0.01 | +0.00 | +0.01 | +0.01 | +0.00 | +0.00 | +0.01 | +0.00 | +0.00 | +0.00 | +0.00 | +0.01 | +0.00 | -0.00 | +0.00 | +0.01 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- vol_ratio <= 2.65
|   |--- or_position <= 0.34
|   |   |--- value: [0.02]
|   |--- or_position >  0.34
|   |   |--- value: [-0.01]
|--- vol_ratio >  2.65
|   |--- value: [0.09]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.022 | +0.010 | 17024 |
| 3 | -0.007 | -0.008 | 23519 |
| 4 | +0.093 | +0.070 | 2084 |
