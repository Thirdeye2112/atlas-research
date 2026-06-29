# JPM setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature         |   spearman_ic |       p |    n |
|:----------------|--------------:|--------:|-----:|
| ema_stack_bear  |        0.071  | 1e-05   | 3776 |
| atr_pct         |        0.0397 | 0.01469 | 3776 |
| macd_bull_cross |        0.0293 | 0.07169 | 3776 |
| upper_wick      |        0.0269 | 0.09853 | 3776 |
| vol_z           |        0.0173 | 0.28786 | 3757 |
| range_pct       |        0.0163 | 0.31615 | 3776 |
| vol_ratio       |        0.0121 | 0.45839 | 3776 |
| rsi_slope       |        0.0113 | 0.48717 | 3773 |

Most BEARISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| mfi            |       -0.0773 | 0       | 3756 |
| rsi            |       -0.0624 | 0.00013 | 3775 |
| dist_hi_20     |       -0.0549 | 0.00077 | 3757 |
| dist_ema20     |       -0.0542 | 0.00086 | 3776 |
| dist_ema50     |       -0.054  | 0.00089 | 3776 |
| ema_stack_bull |       -0.0497 | 0.00227 | 3776 |
| bb_pct         |       -0.0486 | 0.00288 | 3757 |
| dist_ema200    |       -0.0485 | 0.00289 | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.0011 | 755 |
| 2017-06->2020-06 | +0.0362 | 755 |
| 2020-06->2023-06 | -0.0281 | 755 |
| 2023-06->2026-06 | -0.0393 | 756 |

**Mean OOS rank-IC = -0.0075** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature    |   importance |
|:-----------|-------------:|
| macd_hist  |  0.0285895   |
| dist_lo_20 |  0.0163214   |
| dist_ema20 |  0.013933    |
| stoch_k    |  0.0110348   |
| atr_pct    |  0.00500624  |
| dist_ema9  |  0.00483021  |
| rsi_slope  |  0.00406699  |
| ema9_slope |  0.00120989  |
| consec_dir |  0.00120861  |
| lower_wick |  0.00109738  |
| candle_ret |  6.43818e-05 |
| body_dir   |  0           |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**bull_flag (long)** — n=40, win 50%. Winners vs losers (Cohen's d): `dist_ema50` lower (d=-1.19), `dist_ema20` lower (d=-0.87), `rsi` lower (d=-0.82), `ema_stack_bull` lower (d=-0.82), `bb_width` lower (d=-0.56), `bb_break_up` higher (d=+0.55)

**double_bottom (long)** — n=125, win 60%. Winners vs losers (Cohen's d): `consec_dir` lower (d=-0.44), `bb_pct` lower (d=-0.38), `rsi` lower (d=-0.34), `ema_stack_bull` lower (d=-0.33), `dist_hi_20` lower (d=-0.27), `dist_ema20` lower (d=-0.25)

**inverted_hammer (long)** — n=71, win 62%. Winners vs losers (Cohen's d): `vol_ratio` lower (d=-0.67), `dist_ema200` lower (d=-0.66), `dist_ema50` lower (d=-0.56), `above_ema200` lower (d=-0.55), `ema_stack_bear` higher (d=+0.54), `vol_z` lower (d=-0.54)

**bullish_harami (long)** — n=108, win 57%. Winners vs losers (Cohen's d): `rsi_oversold` lower (d=-0.41), `gap_pct` lower (d=-0.39), `atr_pct` lower (d=-0.39), `consec_dir` higher (d=+0.38), `body_dir` higher (d=+0.34), `above_ema200` higher (d=+0.31)

**morning_star (long)** — n=40, win 55%. Winners vs losers (Cohen's d): `roc_10` lower (d=-0.58), `consec_dir` higher (d=+0.56), `range_pct` higher (d=+0.50), `cc_ret` higher (d=+0.49), `candle_ret` higher (d=+0.46), `body_pct` higher (d=+0.46)

**bearish_engulfing (short)** — n=142, win 44%. Winners vs losers (Cohen's d): `macd_hist` higher (d=+0.30), `range_pct` lower (d=-0.25), `gap_pct` lower (d=-0.24), `bb_pct` higher (d=+0.24), `bb_break_dn` lower (d=-0.23), `dist_ema9` higher (d=+0.23)

**shooting_star (short)** — n=99, win 49%. Winners vs losers (Cohen's d): `bb_squeeze` higher (d=+0.50), `atr_pct` lower (d=-0.48), `bb_break_up` lower (d=-0.47), `dist_lo_20` lower (d=-0.44), `bb_width` lower (d=-0.39), `macd_bull_cross` lower (d=-0.36)

**hanging_man (short)** — n=110, win 41%. Winners vs losers (Cohen's d): `dist_hi_20` lower (d=-0.44), `cc_ret` lower (d=-0.42), `atr_pct` higher (d=+0.40), `body_dir` lower (d=-0.37), `candle_ret` lower (d=-0.32), `gap_pct` lower (d=-0.31)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `atr_pct`: +0.59 sd
- `bb_width`: +0.44 sd
- `range_pct`: +0.43 sd
- `above_ema200`: -0.42 sd
- `dist_ema200`: -0.41 sd
- `dist_hi_20`: -0.40 sd
- `dist_ema50`: -0.35 sd
- `body_pct`: +0.31 sd

## 5. Exit timing (winning long setups)

Entries=315. Avg cumulative return peaks at **+13 days** (+1.62%); average max adverse excursion (stop guide) **-3.16%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.01 | +0.18 | +0.27 | +0.47 | +0.49 | +0.50 | +0.76 | +0.84 | +0.98 | +1.20 | +1.50 | +1.60 | +1.62 | +1.60 | +1.56 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema200 <= -13.29
|   |--- value: [1.79]
|--- dist_ema200 >  -13.29
|   |--- roc_10 <= -5.75
|   |   |--- value: [-1.69]
|   |--- roc_10 >  -5.75
|   |   |--- value: [0.29]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 1 | +1.788 | +1.528 | 86 |
| 3 | -1.686 | +0.946 | 106 |
| 4 | +0.293 | +0.351 | 1319 |
