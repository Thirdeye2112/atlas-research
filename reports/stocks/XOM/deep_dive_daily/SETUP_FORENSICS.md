# XOM setup forensics (daily) — horizon 5days

Bars 3,781 (2011-06-13->2026-06-25). 39 TA features. Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.

## 1. Univariate forward-return IC (which single signals forecast the move)

Most BULLISH features:

| feature        |   spearman_ic |       p |    n |
|:---------------|--------------:|--------:|-----:|
| atr_pct        |        0.1001 | 0       | 3776 |
| range_pct      |        0.0757 | 0       | 3776 |
| bb_width       |        0.0738 | 1e-05   | 3757 |
| upper_wick     |        0.0585 | 0.00032 | 3776 |
| dist_lo_20     |        0.0327 | 0.04523 | 3757 |
| ema_stack_bear |        0.0243 | 0.13557 | 3776 |
| vol_climax     |        0.0233 | 0.15299 | 3776 |
| bb_break_dn    |        0.0211 | 0.19536 | 3776 |

Most BEARISH features:

| feature    |   spearman_ic |       p |    n |
|:-----------|--------------:|--------:|-----:|
| bb_squeeze |       -0.0515 | 0.00155 | 3776 |
| dist_hi_20 |       -0.0469 | 0.004   | 3757 |
| lower_wick |       -0.0345 | 0.0338  | 3776 |
| consec_dir |       -0.0313 | 0.05424 | 3776 |
| ema9_slope |       -0.0278 | 0.0882  | 3775 |
| dist_ema9  |       -0.0278 | 0.08804 | 3776 |
| dist_ema50 |       -0.0272 | 0.09501 | 3776 |
| body_dir   |       -0.0271 | 0.0963  | 3776 |

## 2. Walk-forward GBM (all-TA, OOS predictive power)

| test window | OOS rank-IC | n |
|---|---|---|
| 2014-06->2017-06 | +0.0297 | 755 |
| 2017-06->2020-06 | -0.0016 | 755 |
| 2020-06->2023-06 | +0.1303 | 755 |
| 2023-06->2026-06 | +0.0550 | 756 |

**Mean OOS rank-IC = +0.0533** (positive ⇒ the TA stack forecasts forward returns out-of-sample).

Top OOS permutation importances (which TA the model actually used):

| feature     |   importance |
|:------------|-------------:|
| dist_ema200 |   0.0424225  |
| atr_pct     |   0.0391439  |
| gap_pct     |   0.0135553  |
| dist_ema50  |   0.0112212  |
| upper_wick  |   0.00874774 |
| dist_lo_20  |   0.00795873 |
| stoch_k     |   0.0077021  |
| mfi         |   0.00627005 |
| dist_hi_20  |   0.00499269 |
| dist_ema20  |   0.00240986 |
| lower_wick  |   0.00211988 |
| bb_width    |   0.00134277 |

## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)

**double_bottom (long)** — n=134, win 49%. Winners vs losers (Cohen's d): `williams_r` lower (d=-0.37), `stoch_k` lower (d=-0.37), `upper_wick` higher (d=+0.33), `atr_pct` higher (d=+0.32), `vol_ratio` lower (d=-0.31), `lower_wick` lower (d=-0.30)

**inverted_hammer (long)** — n=90, win 56%. Winners vs losers (Cohen's d): `lower_wick` lower (d=-0.52), `upper_wick` higher (d=+0.43), `body_dir` lower (d=-0.40), `bb_squeeze` lower (d=-0.40), `candle_ret` lower (d=-0.30), `bb_break_dn` higher (d=+0.27)

**bullish_harami (long)** — n=107, win 54%. Winners vs losers (Cohen's d): `macd_hist` lower (d=-0.47), `ema_stack_bear` lower (d=-0.39), `range_pct` higher (d=+0.33), `above_ema200` higher (d=+0.32), `macd_bear_cross` higher (d=+0.32), `gap_pct` higher (d=+0.30)

**morning_star (long)** — n=35, win 54%. Winners vs losers (Cohen's d): `ema_stack_bear` higher (d=+0.55), `rsi` lower (d=-0.43), `bb_break_up` lower (d=-0.38), `bb_squeeze` lower (d=-0.37), `bb_pct` lower (d=-0.37), `dist_hi_20` higher (d=+0.32)

**bearish_engulfing (short)** — n=124, win 40%. Winners vs losers (Cohen's d): `rsi_overbought` lower (d=-0.27), `vol_ratio` higher (d=+0.18), `upper_wick` lower (d=-0.18), `ema_stack_bull` higher (d=+0.14), `macd_hist` higher (d=+0.14), `vol_z` higher (d=+0.14)

**shooting_star (short)** — n=78, win 32%. Winners vs losers (Cohen's d): `rsi_slope` lower (d=-0.79), `ema9_slope` lower (d=-0.55), `dist_ema9` lower (d=-0.55), `stoch_k` lower (d=-0.54), `williams_r` lower (d=-0.54), `bb_pct` lower (d=-0.50)

**evening_star (short)** — n=48, win 48%. Winners vs losers (Cohen's d): `above_ema200` higher (d=+0.40), `ema_stack_bear` lower (d=-0.40), `ema_stack_bull` higher (d=+0.35), `rsi_slope` lower (d=-0.35), `rsi` higher (d=+0.34), `rsi_oversold` higher (d=+0.31)

**hanging_man (short)** — n=117, win 49%. Winners vs losers (Cohen's d): `rsi_overbought` lower (d=-0.45), `bb_width` lower (d=-0.29), `candle_ret` higher (d=+0.29), `dist_hi_20` higher (d=+0.28), `roc_10` lower (d=-0.25), `macd_bull_cross` lower (d=-0.24)

## 4. Short discovery (pre-drop TA fingerprint)

Standardized deviation of each TA from normal in the worst-decile forward-return bars:

- `range_pct`: +0.40 sd
- `atr_pct`: +0.39 sd
- `bb_width`: +0.35 sd
- `dist_hi_20`: -0.32 sd
- `body_pct`: +0.24 sd
- `vol_ratio`: +0.21 sd
- `vol_z`: +0.21 sd
- `dist_lo_20`: +0.20 sd

## 5. Exit timing (winning long setups)

Entries=323. Avg cumulative return peaks at **+14 days** (+0.76%); average max adverse excursion (stop guide) **-3.09%**.

| +days | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cum% | -0.05 | -0.00 | +0.01 | +0.20 | +0.13 | +0.25 | +0.32 | +0.44 | +0.55 | +0.57 | +0.55 | +0.67 | +0.69 | +0.76 | +0.74 |

## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check

```
|--- dist_ema200 <= -6.77
|   |--- rsi <= 36.03
|   |   |--- value: [-0.82]
|   |--- rsi >  36.03
|   |   |--- value: [1.54]
|--- dist_ema200 >  -6.77
|   |--- vol_z <= 0.48
|   |   |--- value: [-0.06]
|   |--- vol_z >  0.48
|   |   |--- value: [-0.60]
```

Leaf forward return (in-sample train vs out-of-sample test):

| leaf | IS fwd% | OOS fwd% | OOS n |
|---|---|---|---|
| 2 | -0.818 | +0.172 | 49 |
| 3 | +1.536 | +0.438 | 107 |
| 5 | -0.056 | +0.396 | 1011 |
| 6 | -0.604 | +0.576 | 344 |
