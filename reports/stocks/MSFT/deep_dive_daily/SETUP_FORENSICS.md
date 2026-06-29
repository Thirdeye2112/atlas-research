# MSFT setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| rsi_oversold    |        0.0761 | 0       | 3776 |
| bb_break_dn     |        0.0656 | 5e-05   | 3776 |
| bb_squeeze      |        0.0566 | 0.0005  | 3776 |
| ema_stack_bear  |        0.0417 | 0.01033 | 3776 |
| upper_wick      |        0.0226 | 0.16565 | 3776 |
| macd_bear_cross |        0.0139 | 0.39212 | 3776 |
| atr_pct         |        0.0124 | 0.44552 | 3776 |
| body_pct        |        0.0053 | 0.7441  | 3776 |

Most BEARISH features:

| feature    |   spearman_ic |   p |    n |
|:-----------|--------------:|----:|-----:|
| dist_ema9  |       -0.104  |   0 | 3776 |
| ema9_slope |       -0.1039 |   0 | 3775 |
| dist_lo_20 |       -0.0945 |   0 | 3757 |
| dist_ema20 |       -0.0911 |   0 | 3776 |
| williams_r |       -0.0907 |   0 | 3763 |
| stoch_k    |       -0.0907 |   0 | 3763 |
| bb_pct     |       -0.0872 |   0 | 3757 |
| macd_hist  |       -0.0771 |   0 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.1112 | 755 |
| 2017-06->2020-06 | +0.1722 | 755 |
| 2020-06->2023-06 | +0.0638 | 755 |
| 2023-06->2026-06 | +0.0777 | 756 |

**Mean OOS rank-IC = +0.1062** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature        |   importance |
|:---------------|-------------:|
| macd_hist      |  0.126411    |
| rsi_slope      |  0.0151388   |
| roc_10         |  0.00879662  |
| vol_ratio      |  0.00563984  |
| rsi            |  0.00487907  |
| vol_z          |  0.00373148  |
| ema_stack_bear |  0.00142467  |
| lower_wick     |  0.00133933  |
| cc_ret         |  0.000974437 |
| upper_wick     |  0.000286046 |
| gap_pct        |  0.000169791 |
| range_pct      |  7.62127e-05 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=30, win 63%. Winners vs losers (Cohen's d): `ema_stack_bull` higher (d=+1.02), `bb_width` lower (d=-0.66), `bb_break_up` higher (d=+0.66), `macd_bull_cross` higher (d=+0.64), `dist_lo_20` lower (d=-0.53), `above_ema200` higher (d=+0.53)

**double_bottom (long)** — n=130, win 57%. Winners vs losers (Cohen's d): `body_pct` lower (d=-0.45), `range_pct` lower (d=-0.41), `dist_hi_20` higher (d=+0.41), `cc_ret` lower (d=-0.40), `atr_pct` lower (d=-0.35), `bb_width` lower (d=-0.35)

**inverted_hammer (long)** — n=58, win 67%. Winners vs losers (Cohen's d): `macd_hist` higher (d=+0.82), `dist_ema200` lower (d=-0.43), `bb_break_dn` higher (d=+0.41), `above_ema200` lower (d=-0.34), `vol_z` higher (d=+0.34), `vol_ratio` higher (d=+0.32)

**bullish_harami (long)** — n=111, win 65%. Winners vs losers (Cohen's d): `lower_wick` higher (d=+0.42), `body_pct` lower (d=-0.38), `cc_ret` lower (d=-0.28), `rsi_oversold` higher (d=+0.26), `macd_bear_cross` higher (d=+0.26), `candle_ret` lower (d=-0.24)

**morning_star (long)** — n=41, win 56%. Winners vs losers (Cohen's d): `mfi` lower (d=-0.65), `dist_ema20` lower (d=-0.59), `dist_ema50` lower (d=-0.57), `ema_stack_bear` higher (d=+0.57), `dist_lo_20` lower (d=-0.55), `macd_hist` lower (d=-0.55)

**bearish_engulfing (short)** — n=144, win 37%. Winners vs losers (Cohen's d): `ema_stack_bull` lower (d=-0.29), `macd_bear_cross` higher (d=+0.27), `gap_pct` lower (d=-0.24), `vol_z` lower (d=-0.24), `rsi_oversold` lower (d=-0.23), `vol_ratio` lower (d=-0.23)

**shooting_star (short)** — n=85, win 49%. Winners vs losers (Cohen's d): `body_pct` lower (d=-0.41), `above_ema200` lower (d=-0.38), `range_pct` lower (d=-0.37), `stoch_k` higher (d=+0.35), `williams_r` higher (d=+0.35), `upper_wick` higher (d=+0.29)

**evening_star (short)** — n=41, win 51%. Winners vs losers (Cohen's d): `above_ema200` higher (d=+0.61), `vol_z` higher (d=+0.48), `macd_bear_cross` higher (d=+0.44), `gap_pct` lower (d=-0.44), `dist_ema200` higher (d=+0.42), `atr_pct` lower (d=-0.41)

**hanging_man (short)** — n=139, win 40%. Winners vs losers (Cohen's d): `rsi_slope` higher (d=+0.45), `ema9_slope` higher (d=+0.45), `dist_ema9` higher (d=+0.45), `williams_r` higher (d=+0.43), `stoch_k` higher (d=+0.43), `ema_stack_bull` lower (d=-0.31)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.33 sd
- `range_pct`: +0.28 sd
- `above_ema200`: -0.21 sd
- `ema_stack_bull`: -0.18 sd
- `bb_width`: +0.18 sd
- `body_pct`: +0.17 sd
- `dist_ema200`: -0.17 sd
- `dist_lo_20`: +0.17 sd

## 5. Exit timing (winning long setups)

Entries=293. Avg cumulative return peaks at **+15 days** (+1.38%); average max adverse excursion (stop guide) **-2.94%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | +0.20 | +0.24 | +0.45 | +0.59 | +0.63 | +0.68 | +0.76 | +0.72 | +0.79 | +0.87 | +1.10 | +1.18 | +1.08 | +1.26 | +1.38 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema50 <= -4.07
|   |--- value: [2.22]
|--- dist_ema50 >  -4.07
|   |--- dist_ema200 <= 16.42
|   |   |--- value: [0.50]
|   |--- dist_ema200 >  16.42
|   |   |--- value: [-0.68]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 1 | +2.219 | +0.887 | 228 |
| 3 | +0.501 | +0.195 | 985 |
| 4 | -0.675 | +0.093 | 298 |
