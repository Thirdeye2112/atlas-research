# WMT setup forensics (intraday) — horizon 6bars

Bars 105,574 (2021-01-04->2026-06-18). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature    |   spearman_ic |       p |      n |
|:-----------|--------------:|--------:|-------:|
| vol_climax |        0.0151 | 0       | 105568 |
| vol_ratio  |        0.0143 | 0       | 105568 |
| vol_z      |        0.0116 | 0.00016 | 105549 |
| vwap_dist  |        0.0097 | 0.00162 | 105568 |
| dist_ema50 |        0.0093 | 0.00261 | 105568 |
| tod_min    |        0.0089 | 0.00402 | 105568 |
| range_pct  |        0.0085 | 0.0064  | 103932 |
| lower_wick |        0.008  | 0.00962 | 103932 |

Most BEARISH features:

| feature         |   spearman_ic |       p |      n |
|:----------------|--------------:|--------:|-------:|
| ema_stack_bear  |       -0.0135 | 1e-05   | 105568 |
| candle_ret      |       -0.0131 | 2e-05   | 105568 |
| cc_ret          |       -0.0104 | 0.00069 | 105567 |
| consec_dir      |       -0.0099 | 0.00129 | 105568 |
| body_dir        |       -0.0098 | 0.00145 | 105568 |
| rsi_slope       |       -0.0084 | 0.00629 | 105557 |
| bb_squeeze      |       -0.0077 | 0.01233 | 105568 |
| macd_bull_cross |       -0.0044 | 0.15453 | 105568 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2022-02->2023-03 | +0.0343 | 21114 |
| 2023-03->2024-04 | +0.0214 | 21113 |
| 2024-04->2025-05 | -0.0322 | 21114 |
| 2025-05->2026-06 | +0.0078 | 21114 |

**Mean OOS rank-IC = +0.0078** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| dist_ema200 |  0.0640589   |
| vwap_dist   |  0.0631903   |
| tod_min     |  0.0217753   |
| vol_z       |  0.0117158   |
| atr_pct     |  0.00528057  |
| bb_width    |  0.00256852  |
| range_pct   |  0.000859295 |
| rsi_slope   |  0.000811765 |
| mfi         |  0.000759103 |
| cc_ret      |  0           |
| candle_ret  |  0           |
| vol_climax  |  0           |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=5524, win 50%. Winners vs losers (Cohen's d): `lower_wick` higher (d=+0.10), `vwap_dist` higher (d=+0.05), `vol_z` higher (d=+0.05), `ema_stack_bull` lower (d=-0.05), `bb_squeeze` lower (d=-0.04), `gap_pct` higher (d=+0.04)

**inverted_hammer (long)** — n=2747, win 51%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.05), `dist_lo_20` higher (d=+0.05), `macd_bull_cross` higher (d=+0.05), `tod_min` higher (d=+0.05), `vwap_dist` higher (d=+0.05), `ema9_slope` higher (d=+0.05)

**bullish_harami (long)** — n=4056, win 51%. Winners vs losers (Cohen's d): `vol_climax` higher (d=+0.06), `vol_ratio` higher (d=+0.06), `dist_ema9` lower (d=-0.06), `ema9_slope` lower (d=-0.06), `dist_ema20` lower (d=-0.06), `roc_10` lower (d=-0.06)

**morning_star (long)** — n=898, win 52%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.11), `lower_wick` higher (d=+0.11), `vol_z` higher (d=+0.08), `macd_hist` higher (d=+0.08), `dist_ema20` higher (d=+0.07), `ema9_slope` higher (d=+0.07)

**bearish_engulfing (short)** — n=5076, win 47%. Winners vs losers (Cohen's d): `bb_break_up` higher (d=+0.08), `ema_stack_bear` higher (d=+0.07), `gap_pct` lower (d=-0.06), `upper_wick` higher (d=+0.05), `bb_break_dn` higher (d=+0.05), `mfi` lower (d=-0.05)

**shooting_star (short)** — n=2940, win 48%. Winners vs losers (Cohen's d): `body_pct` higher (d=+0.08), `ema_stack_bear` higher (d=+0.08), `range_pct` higher (d=+0.08), `rsi_overbought` lower (d=-0.07), `bb_squeeze` higher (d=+0.07), `above_ema200` lower (d=-0.06)

**evening_star (short)** — n=919, win 47%. Winners vs losers (Cohen's d): `upper_wick` higher (d=+0.16), `bb_squeeze` higher (d=+0.13), `gap_pct` lower (d=-0.12), `ema_stack_bull` lower (d=-0.11), `above_vwap` lower (d=-0.10), `or_position` lower (d=-0.10)

**hanging_man (short)** — n=3035, win 47%. Winners vs losers (Cohen's d): `bb_width` higher (d=+0.07), `atr_pct` higher (d=+0.06), `dist_lo_20` higher (d=+0.06), `dist_hi_20` lower (d=-0.06), `cc_ret` lower (d=-0.06), `body_dir` lower (d=-0.06)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.51 sd
- `body_pct`: +0.37 sd
- `atr_pct`: +0.29 sd
- `dist_lo_20`: +0.26 sd
- `vol_z`: +0.22 sd
- `vol_ratio`: +0.22 sd
- `vol_climax`: +0.18 sd
- `bb_squeeze`: -0.15 sd

## 5. Exit timing (winning long setups)

Entries=10842. Avg cumulative return peaks at **+11 bars** (+0.01%); average max adverse excursion (stop guide) **-0.33%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.01 | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.01 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 | +0.00 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- tod_min <= 1202.50
|   |--- tod_min <= 1167.50
|   |   |--- value: [-0.00]
|   |--- tod_min >  1167.50
|   |   |--- value: [0.05]
|--- tod_min >  1202.50
|   |--- value: [-0.13]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | -0.002 | +0.009 | 37032 |
| 3 | +0.055 | +0.033 | 3392 |
| 4 | -0.130 | -0.001 | 1804 |
