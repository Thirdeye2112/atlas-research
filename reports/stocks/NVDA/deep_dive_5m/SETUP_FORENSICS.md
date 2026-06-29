# NVDA setup forensics (intraday) — horizon 6bars

Bars 67,665 (2023-01-03->2026-06-26). 43 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |     n |
|:---------------|--------------:|--------:|------:|
| bb_width       |        0.0211 | 0       | 67640 |
| atr_pct        |        0.014  | 0.00028 | 67659 |
| vol_z          |        0.0134 | 0.00051 | 67640 |
| range_pct      |        0.0133 | 0.00056 | 67612 |
| vol_climax     |        0.0114 | 0.00304 | 67659 |
| ema_stack_bear |        0.0111 | 0.0039  | 67659 |
| body_pct       |        0.0103 | 0.00719 | 67659 |
| vol_ratio      |        0.0089 | 0.02117 | 67659 |

Most BEARISH features:

| feature    |   spearman_ic |       p |     n |
|:-----------|--------------:|--------:|------:|
| dist_hi_20 |       -0.019  | 0       | 67640 |
| bb_squeeze |       -0.0186 | 0       | 67659 |
| candle_ret |       -0.0185 | 0       | 67659 |
| cc_ret     |       -0.0181 | 0       | 67658 |
| rsi_slope  |       -0.0162 | 2e-05   | 67655 |
| consec_dir |       -0.016  | 3e-05   | 67659 |
| mfi        |       -0.0143 | 0.00021 | 67621 |
| ema9_slope |       -0.0128 | 0.00086 | 67658 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2023-09->2024-05 | +0.0132 | 13532 |
| 2024-05->2025-02 | +0.0628 | 13532 |
| 2025-02->2025-10 | +0.0031 | 13532 |
| 2025-10->2026-06 | +0.0505 | 13532 |

**Mean OOS rank-IC = +0.0324** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| roc_10      |  0.0137631   |
| macd_hist   |  0.0126601   |
| tod_min     |  0.0107289   |
| or_position |  0.00934394  |
| bb_width    |  0.00219043  |
| gap_pct     |  0.00214108  |
| rsi         |  0.000964508 |
| atr_pct     |  0.000918409 |
| vwap_dist   |  0.000885059 |
| dist_ema200 |  0.000519734 |
| vol_ratio   |  0.000458447 |
| vol_z       |  0.000398481 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=3412, win 51%. Winners vs losers (Cohen's d): `dist_ema50` higher (d=+0.10), `gap_pct` higher (d=+0.09), `cc_ret` higher (d=+0.09), `ema9_slope` higher (d=+0.08), `dist_ema9` higher (d=+0.08), `macd_bull_cross` higher (d=+0.08)

**inverted_hammer (long)** — n=1471, win 53%. Winners vs losers (Cohen's d): `gap_pct` higher (d=+0.12), `cc_ret` higher (d=+0.11), `bb_squeeze` lower (d=-0.09), `rsi_slope` higher (d=+0.08), `vol_ratio` higher (d=+0.08), `bb_break_dn` lower (d=-0.07)

**bullish_harami (long)** — n=2457, win 52%. Winners vs losers (Cohen's d): `bb_squeeze` lower (d=-0.08), `above_vwap` lower (d=-0.07), `range_pct` lower (d=-0.07), `mfi` lower (d=-0.06), `dist_ema50` higher (d=+0.06), `body_pct` lower (d=-0.05)

**morning_star (long)** — n=510, win 49%. Winners vs losers (Cohen's d): `dist_ema50` higher (d=+0.15), `gap_pct` higher (d=+0.14), `tod_min` lower (d=-0.11), `stoch_k` higher (d=+0.09), `williams_r` higher (d=+0.09), `bb_break_up` higher (d=+0.09)

**bearish_engulfing (short)** — n=3723, win 48%. Winners vs losers (Cohen's d): `macd_bull_cross` higher (d=+0.06), `lower_wick` higher (d=+0.05), `macd_hist` lower (d=-0.05), `dist_lo_20` lower (d=-0.05), `ema9_slope` lower (d=-0.04), `dist_ema9` lower (d=-0.04)

**shooting_star (short)** — n=1815, win 51%. Winners vs losers (Cohen's d): `above_vwap` lower (d=-0.11), `atr_pct` lower (d=-0.09), `or_position` lower (d=-0.08), `vwap_dist` lower (d=-0.08), `above_ema200` lower (d=-0.08), `gap_pct` higher (d=+0.07)

**evening_star (short)** — n=602, win 47%. Winners vs losers (Cohen's d): `gap_pct` lower (d=-0.20), `rsi_slope` lower (d=-0.18), `cc_ret` lower (d=-0.16), `macd_bull_cross` higher (d=+0.13), `range_pct` higher (d=+0.12), `lower_wick` higher (d=+0.11)

**hanging_man (short)** — n=2069, win 50%. Winners vs losers (Cohen's d): `dist_ema200` lower (d=-0.14), `upper_wick` higher (d=+0.11), `dist_ema50` lower (d=-0.08), `above_ema200` lower (d=-0.07), `dist_hi_20` higher (d=+0.07), `or_position` higher (d=+0.07)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.53 sd
- `body_pct`: +0.38 sd
- `vol_ratio`: +0.37 sd
- `vol_z`: +0.35 sd
- `vol_climax`: +0.27 sd
- `rsi_oversold`: +0.18 sd
- `dist_lo_20`: +0.17 sd
- `above_ema200`: -0.16 sd

## 5. Exit timing (winning long setups)

Entries=6400. Avg cumulative return peaks at **+18 bars** (+0.04%); average max adverse excursion (stop guide) **-0.75%**.

| +bars | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.00 | +0.01 | +0.01 | +0.01 | +0.01 | +0.00 | +0.02 | +0.00 | +0.01 | +0.02 | +0.02 | +0.03 | +0.03 | +0.04 | +0.04 | +0.03 | +0.03 | +0.04 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- tod_min <= 1202.50
|   |--- dist_ema200 <= -3.63
|   |   |--- value: [0.15]
|   |--- dist_ema200 >  -3.63
|   |   |--- value: [0.01]
|--- tod_min >  1202.50
|   |--- value: [0.17]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | +0.147 | +0.100 | 1044 |
| 3 | +0.006 | +0.012 | 24854 |
| 4 | +0.173 | -0.035 | 1166 |
