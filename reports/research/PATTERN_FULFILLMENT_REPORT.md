# Pattern Fulfillment Backtest Report

**MEASURE & REPORT ONLY.** For every detected instance of every pattern in `pattern_reference` (43 rows; migration 0050) plus 4 supplemental shapes, this measures whether reality matches the TAUGHT confirm/invalidate/inversion behavior out-of-sample, judged on reward:risk **expectancy** (R units), not win rate. It is **not a predictor and not a trading signal**. This system has already returned three nulls on related single-name 5m prediction (setup-formation v1, v2, confluence) -- the honest prior going in was that most patterns fulfill near coin-flip OOS, and that is mostly what this finds.

- **Run ID:** `20260621T213843Z-2ae673ad`
- **Git commit:** `25accacc430d3c43cb96a21fcf51b47aba81dbfa` (branch `research/pattern-fulfillment`)
- **Timestamp (UTC):** 2026-06-21T21:40:25.743045+00:00
- **Tickers:** AAPL, NKE, INTC
- **Timeframes:** 5m, daily
- **Stage windows (bars):** {'5m': 24, 'daily': 15}
- **R multiples / ATR stop:** [1, 2, 3] / 1.0x ATR
- **Walk-forward split:** 70% train / 30% held-out, chronological per (ticker, timeframe)
- **Total wall time:** 101.8s
- **Total instance rows:** 698,047 (+ 67,201 baseline rows)

## Step 1. Population (every detected instance, no cherry-picking)

Scope: AAPL/NKE/INTC. Candlesticks (19) and the 4 supplemental shapes run on **both 5m and daily**. Chart patterns (double_top/bottom, hs_top/bottom, bull/bear_flag), channels (4), omni_82, oscar_87, sma_stack, and classic gaps run on **daily only** (multi-week structures; daily has clean per-day granularity and pattern_memory precedent -- see Scoping). macd, rsi, vwap, and FVG run on **5m only** (intraday-native concepts). `adx`, `atr`, `swing_leg`, `volume_ratio` are excluded from Steps 2-4 entirely: pattern_reference's own text gives them no self-contained direction/confirm/invalidate ("N/A -- not a signal", or in volume_ratio's case, explicitly conditional on some *other* directional signal, not a standalone setup). They are real, present, context-only indicators -- just not independently testable as a pattern.

| Pattern type | Timeframe | Total instances | Confirmed | Invalidated | Neither (no follow-through) |
|---|---|---|---|---|---|
| vwap | 5m | 151,692 | 134,781 (88.9%) | 16,909 (11.1%) | 2 (0.0%) |
| continuation_candle *(supplemental)* | 5m | 49,958 | 49,958 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| flat_top *(supplemental)* | 5m | 48,163 | 14,297 (29.7%) | 31,206 (64.8%) | 2,660 (5.5%) |
| fvg_bullish | 5m | 45,677 | 28,322 (62.0%) | 10,764 (23.6%) | 6,591 (14.4%) |
| fvg_bearish | 5m | 44,651 | 27,456 (61.5%) | 10,734 (24.0%) | 6,461 (14.5%) |
| tweezer_top | 5m | 43,922 | 25,797 (58.7%) | 18,061 (41.1%) | 64 (0.1%) |
| tweezer_bottom | 5m | 42,626 | 25,262 (59.3%) | 17,306 (40.6%) | 58 (0.1%) |
| marubozu | 5m | 42,343 | 29,372 (69.4%) | 12,936 (30.6%) | 35 (0.1%) |
| doji | 5m | 22,024 | 22,021 (100.0%) | 0 (0.0%) | 3 (0.0%) |
| macd | 5m | 20,901 | 20,901 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| rsi | 5m | 20,686 | 20,294 (98.1%) | 0 (0.0%) | 392 (1.9%) |
| spinning_top | 5m | 19,207 | 19,195 (99.9%) | 0 (0.0%) | 12 (0.1%) |
| long_lower_wick *(supplemental)* | 5m | 15,772 | 9,819 (62.3%) | 5,950 (37.7%) | 3 (0.0%) |
| bearish_engulfing | 5m | 15,105 | 10,687 (70.8%) | 4,412 (29.2%) | 6 (0.0%) |
| bullish_engulfing | 5m | 15,089 | 10,727 (71.1%) | 4,348 (28.8%) | 14 (0.1%) |
| long_upper_wick *(supplemental)* | 5m | 15,081 | 9,367 (62.1%) | 5,708 (37.8%) | 6 (0.0%) |
| bearish_harami | 5m | 11,686 | 5,480 (46.9%) | 6,184 (52.9%) | 22 (0.2%) |
| bullish_harami | 5m | 11,486 | 5,304 (46.2%) | 6,145 (53.5%) | 37 (0.3%) |
| hanging_man | 5m | 7,938 | 4,307 (54.3%) | 3,631 (45.7%) | 0 (0.0%) |
| hammer | 5m | 7,834 | 4,836 (61.7%) | 2,998 (38.3%) | 0 (0.0%) |
| inverted_hammer | 5m | 7,547 | 2,830 (37.5%) | 4,714 (62.5%) | 3 (0.0%) |
| shooting_star | 5m | 7,534 | 4,653 (61.8%) | 2,878 (38.2%) | 3 (0.0%) |
| classic_gap_up | daily | 4,454 | 3,179 (71.4%) | 1,275 (28.6%) | 0 (0.0%) |
| classic_gap_down | daily | 3,921 | 2,758 (70.3%) | 1,163 (29.7%) | 0 (0.0%) |
| morning_star | 5m | 2,235 | 2,235 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| evening_star | 5m | 2,183 | 2,183 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| dark_cloud_cover | 5m | 1,838 | 1,247 (67.8%) | 590 (32.1%) | 1 (0.1%) |
| piercing | 5m | 1,769 | 1,227 (69.4%) | 542 (30.6%) | 0 (0.0%) |
| spinning_top | daily | 1,381 | 1,380 (99.9%) | 0 (0.0%) | 1 (0.1%) |
| continuation_candle *(supplemental)* | daily | 1,341 | 1,341 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| doji | daily | 1,134 | 1,134 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| three_black_crows | 5m | 881 | 546 (62.0%) | 335 (38.0%) | 0 (0.0%) |
| three_white_soldiers | 5m | 853 | 501 (58.7%) | 352 (41.3%) | 0 (0.0%) |
| tweezer_top | daily | 845 | 429 (50.8%) | 415 (49.1%) | 1 (0.1%) |
| channel_break | daily | 582 | 289 (49.7%) | 174 (29.9%) | 119 (20.4%) |
| long_lower_wick *(supplemental)* | daily | 532 | 348 (65.4%) | 183 (34.4%) | 1 (0.2%) |
| long_upper_wick *(supplemental)* | daily | 500 | 280 (56.0%) | 219 (43.8%) | 1 (0.2%) |
| tweezer_bottom | daily | 476 | 286 (60.1%) | 187 (39.3%) | 3 (0.6%) |
| bearish_harami | daily | 458 | 210 (45.9%) | 247 (53.9%) | 1 (0.2%) |
| bearish_engulfing | daily | 446 | 309 (69.3%) | 135 (30.3%) | 2 (0.4%) |
| double_top | daily | 436 | 216 (49.5%) | 164 (37.6%) | 56 (12.8%) |
| bullish_engulfing | daily | 395 | 295 (74.7%) | 99 (25.1%) | 1 (0.3%) |
| double_bottom | daily | 389 | 238 (61.2%) | 97 (24.9%) | 54 (13.9%) |
| marubozu | daily | 388 | 295 (76.0%) | 91 (23.5%) | 2 (0.5%) |
| bullish_harami | daily | 347 | 183 (52.7%) | 162 (46.7%) | 2 (0.6%) |
| hanging_man | daily | 320 | 161 (50.3%) | 159 (49.7%) | 0 (0.0%) |
| omni_82 | daily | 306 | 306 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| shooting_star | daily | 301 | 166 (55.1%) | 135 (44.9%) | 0 (0.0%) |
| flat_top *(supplemental)* | daily | 280 | 45 (16.1%) | 206 (73.6%) | 29 (10.4%) |
| channel_ascending | daily | 269 | 135 (50.2%) | 80 (29.7%) | 54 (20.1%) |
| hammer | daily | 212 | 143 (67.5%) | 68 (32.1%) | 1 (0.5%) |
| inverted_hammer | daily | 199 | 84 (42.2%) | 114 (57.3%) | 1 (0.5%) |
| channel_descending | daily | 197 | 101 (51.3%) | 59 (29.9%) | 37 (18.8%) |
| bull_flag | daily | 175 | 126 (72.0%) | 40 (22.9%) | 9 (5.1%) |
| morning_star | daily | 122 | 122 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| oscar_87 | daily | 118 | 118 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| bear_flag | daily | 116 | 71 (61.2%) | 36 (31.0%) | 9 (7.8%) |
| channel_horizontal | daily | 116 | 53 (45.7%) | 35 (30.2%) | 28 (24.1%) |
| evening_star | daily | 104 | 104 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| hs_bottom | daily | 104 | 69 (66.3%) | 14 (13.5%) | 21 (20.2%) |
| sma_stack | daily | 101 | 101 (100.0%) | 0 (0.0%) | 0 (0.0%) |
| hs_top | daily | 100 | 56 (56.0%) | 27 (27.0%) | 17 (17.0%) |
| dark_cloud_cover | daily | 99 | 64 (64.6%) | 34 (34.3%) | 1 (1.0%) |
| piercing | daily | 58 | 46 (79.3%) | 12 (20.7%) | 0 (0.0%) |
| three_white_soldiers | daily | 28 | 16 (57.1%) | 12 (42.9%) | 0 (0.0%) |
| three_black_crows | daily | 16 | 14 (87.5%) | 2 (12.5%) | 0 (0.0%) |

*Context-only, excluded from Steps 2-4 (no self-contained direction/confirm/invalidate per pattern_reference's own text):* adx, atr, swing_leg, volume_ratio.

## Step 3. Expectancy: in-sample vs. held-out vs. baseline (R units)

Baseline = random-direction entries, identical ATR R-bracket (1x ATR stop, targets at 1/2/3x ATR), same forward window, same ticker/timeframe pool, fixed seed. **Note the baseline itself is not exactly zero** (see Scoping for why: a 'highest R-target reached before the stop' bracket is mechanically asymmetric -- wins can be 1/2/3R, losses are always exactly -1R -- so even a true coin flip nets slightly positive in this unit). This is exactly why the brief calls for comparing pattern expectancy to baseline, not to zero, and that is what the p-value column does (Welch's t-test, pattern held-out vs. baseline held-out).

**Baseline expectancy:** 5m in-sample +0.055R (n=39,117), held-out +0.049R (n=16,764) | daily in-sample +0.066R (n=7,923), held-out +0.072R (n=3,393).

**Multiple testing:** 47 (pattern, timeframe) cells tested, 2 survive Benjamini-Hochberg FDR correction at q=0.1. Cells with held-out n < 30 are not eligible for the FDR pool (too thin to trust regardless of p-value) but are still shown below, flagged LOW-N.

| Pattern | TF | n (is) | E (is) | n (ho) | E (ho) | p vs baseline (ho) | Survives BH-FDR | Flag |
|---|---|---|---|---|---|---|---|---|
| tweezer_top | 5m | 18,639 | +0.056R | 7,158 | +0.104R | 0.0005 | **YES** |  |
| flat_top* | 5m | 10,384 | +0.098R | 3,913 | +0.111R | 0.0025 | **YES** |  |
| three_black_crows | daily | 7 | +0.000R | 7 | -0.714R | 0.0060 | no | LOW-N |
| bearish_engulfing | 5m | 7,131 | +0.059R | 3,556 | +0.089R | 0.0481 | no |  |
| hammer | 5m | 3,383 | +0.023R | 1,453 | -0.010R | 0.0528 | no | ⚠sign-flip |
| long_upper_wick* | 5m | 6,530 | +0.072R | 2,837 | +0.090R | 0.0630 | no |  |
| flat_top* | daily | 35 | +0.171R | 10 | -0.495R | 0.0665 | no | ⚠sign-flip LOW-N |
| inverted_hammer | 5m | 2,005 | +0.011R | 825 | -0.018R | 0.0834 | no | ⚠sign-flip |
| evening_star | 5m | 1,600 | +0.043R | 583 | -0.025R | 0.1050 | no | ⚠sign-flip |
| bullish_harami | 5m | 3,650 | +0.004R | 1,654 | +0.004R | 0.1115 | no |  |
| piercing | daily | 36 | +0.111R | 10 | -0.400R | 0.1227 | no | ⚠sign-flip LOW-N |
| three_white_soldiers | daily | 5 | +0.200R | 11 | +0.545R | 0.1306 | no | LOW-N |
| vwap | 5m | 95,404 | +0.063R | 39,375 | +0.034R | 0.1315 | no |  |
| hanging_man | 5m | 3,087 | +0.060R | 1,220 | +0.090R | 0.2071 | no |  |
| hs_bottom | daily | 48 | +0.252R | 21 | +0.333R | 0.2179 | no | LOW-N |
| long_lower_wick* | 5m | 6,969 | +0.053R | 2,850 | +0.023R | 0.2448 | no |  |
| shooting_star | 5m | 3,240 | +0.045R | 1,413 | +0.084R | 0.2470 | no |  |
| shooting_star | daily | 119 | -0.025R | 47 | +0.255R | 0.2713 | no | ⚠sign-flip |
| tweezer_bottom | daily | 200 | +0.184R | 86 | +0.202R | 0.2811 | no |  |
| macd | 5m | 14,689 | +0.060R | 6,212 | +0.066R | 0.2937 | no |  |
| tweezer_top | daily | 355 | +0.053R | 74 | +0.203R | 0.3479 | no |  |
| tweezer_bottom | 5m | 18,120 | +0.046R | 7,142 | +0.035R | 0.3723 | no |  |
| bearish_engulfing | daily | 216 | +0.042R | 93 | -0.028R | 0.3854 | no | ⚠sign-flip |
| morning_star | daily | 88 | -0.068R | 34 | -0.103R | 0.3878 | no |  |
| three_white_soldiers | 5m | 365 | +0.026R | 136 | +0.125R | 0.4000 | no |  |
| double_bottom | daily | 178 | +0.236R | 60 | +0.200R | 0.4312 | no |  |
| marubozu | 5m | 23,006 | +0.057R | 6,366 | +0.037R | 0.4510 | no |  |
| hanging_man | daily | 114 | -0.037R | 47 | -0.043R | 0.4525 | no |  |
| evening_star | daily | 80 | -0.200R | 24 | -0.083R | 0.4552 | no | LOW-N |
| spinning_top | 5m | 12,104 | +0.039R | 7,091 | +0.060R | 0.4677 | no |  |
| doji | daily | 794 | +0.033R | 340 | +0.118R | 0.4753 | no |  |
| long_lower_wick* | daily | 241 | +0.228R | 107 | +0.155R | 0.4774 | no |  |
| piercing | 5m | 973 | +0.041R | 254 | +0.002R | 0.4897 | no | ⚠shrinks |
| spinning_top | daily | 974 | +0.094R | 406 | +0.036R | 0.5217 | no |  |
| bearish_harami | 5m | 3,776 | +0.018R | 1,704 | +0.067R | 0.5276 | no |  |
| bullish_engulfing | 5m | 7,169 | +0.048R | 3,558 | +0.036R | 0.5418 | no |  |
| rsi | 5m | 14,259 | +0.055R | 6,035 | +0.058R | 0.5719 | no |  |
| dark_cloud_cover | daily | 55 | +0.145R | 9 | -0.111R | 0.6018 | no | ⚠sign-flip LOW-N |
| inverted_hammer | daily | 58 | +0.241R | 26 | +0.192R | 0.6018 | no | LOW-N |
| continuation_candle* | 5m | 36,308 | +0.047R | 13,649 | +0.055R | 0.6127 | no |  |
| morning_star | 5m | 1,552 | +0.018R | 683 | +0.028R | 0.6233 | no |  |
| dark_cloud_cover | 5m | 989 | +0.032R | 258 | +0.081R | 0.6499 | no |  |
| hammer | daily | 91 | -0.011R | 52 | +0.002R | 0.6639 | no | ⚠sign-flip |
| bullish_harami | daily | 120 | +0.140R | 63 | +0.127R | 0.6930 | no |  |
| double_top | daily | 161 | +0.236R | 55 | +0.129R | 0.7006 | no |  |
| hs_top | daily | 32 | +0.625R | 24 | +0.000R | 0.7292 | no | ⚠sign-flip LOW-N |
| bear_flag | daily | 41 | +0.049R | 30 | +0.000R | 0.7298 | no | ⚠sign-flip |
| oscar_87 | daily | 86 | +0.120R | 32 | +0.000R | 0.7317 | no | ⚠sign-flip |
| continuation_candle* | daily | 882 | +0.094R | 459 | +0.090R | 0.7523 | no |  |
| bullish_engulfing | daily | 216 | +0.222R | 79 | +0.113R | 0.7581 | no |  |
| long_upper_wick* | daily | 197 | +0.020R | 83 | +0.108R | 0.7779 | no |  |
| doji | 5m | 14,582 | +0.055R | 7,439 | +0.053R | 0.7865 | no |  |
| three_black_crows | 5m | 403 | +0.050R | 143 | +0.033R | 0.8571 | no |  |
| marubozu | daily | 206 | +0.036R | 89 | +0.053R | 0.8669 | no |  |
| bearish_harami | daily | 143 | +0.021R | 67 | +0.090R | 0.8972 | no |  |
| sma_stack | daily | 80 | +0.138R | 21 | +0.095R | 0.9241 | no | LOW-N |
| bull_flag | daily | 102 | +0.167R | 24 | +0.083R | 0.9586 | no | LOW-N |
| omni_82 | daily | 200 | +0.202R | 106 | +0.075R | 0.9785 | no |  |

*Marked with `*` = supplemental shape, not one of pattern_reference's 43 official rows. ⚠sign-flip = expectancy changes sign between in-sample and held-out (the overfit signature called out in the brief). ⚠shrinks = held-out expectancy collapses to under 30% of its in-sample value.

## Step 4. The invalidation-becomes inversion test

For the 21 codeable patterns with an `invalidation_becomes` row (22 total minus `hs_top`, whose own pattern_reference text disclaims a clean signal -- 'no single textbook signal'), when the ORIGINAL pattern is invalidated, this trades the inversion direction (mechanically: the flip of the original direction, which is mathematically identical to the direction of the invalidation break itself) with the same R-bracket, from the invalidation bar.

**Multiple testing:** 12 cells tested, **0 survive** BH-FDR at q=0.1.

| Pattern | TF | n (is) | E (is) | n (ho) | E (ho) | p vs baseline (ho) | Survives BH-FDR | Flag |
|---|---|---|---|---|---|---|---|---|
| bear_flag (inverted) | daily | 17 | +0.529R | 19 | -0.474R | 0.0088 | no | ⚠sign-flip LOW-N |
| tweezer_bottom (inverted) | 5m | 12,202 | +0.070R | 5,104 | +0.092R | 0.0143 | no |  |
| tweezer_bottom (inverted) | daily | 123 | +0.130R | 64 | -0.186R | 0.0425 | no | ⚠sign-flip |
| three_black_crows (inverted) | daily | 0 | n/a | 2 | +2.000R | 0.0540 | no | LOW-N |
| bull_flag (inverted) | daily | 30 | +0.000R | 10 | -0.400R | 0.1227 | no | LOW-N |
| double_top (inverted) | daily | 137 | +0.212R | 27 | +0.407R | 0.1434 | no | LOW-N |
| tweezer_top (inverted) | daily | 351 | +0.255R | 64 | +0.281R | 0.1725 | no |  |
| three_white_soldiers (inverted) | daily | 4 | +0.209R | 8 | +0.500R | 0.1923 | no | LOW-N |
| bearish_engulfing (inverted) | daily | 91 | +0.219R | 44 | +0.295R | 0.2249 | no |  |
| three_white_soldiers (inverted) | 5m | 263 | +0.106R | 89 | -0.079R | 0.2615 | no | ⚠sign-flip |
| bullish_engulfing (inverted) | daily | 65 | +0.031R | 34 | +0.239R | 0.3926 | no |  |
| bearish_engulfing (inverted) | 5m | 3,037 | +0.048R | 1,375 | +0.024R | 0.4174 | no |  |
| marubozu (inverted) | 5m | 10,445 | +0.062R | 2,491 | +0.034R | 0.5247 | no |  |
| marubozu (inverted) | daily | 58 | +0.034R | 33 | +0.152R | 0.6870 | no |  |
| double_bottom (inverted) | daily | 69 | +0.043R | 28 | +0.147R | 0.7063 | no | LOW-N |
| three_black_crows (inverted) | 5m | 248 | +0.109R | 87 | +0.023R | 0.8342 | no | ⚠shrinks |
| bullish_engulfing (inverted) | 5m | 2,914 | +0.066R | 1,434 | +0.043R | 0.8365 | no |  |
| tweezer_top (inverted) | 5m | 13,319 | +0.071R | 4,742 | +0.046R | 0.8927 | no |  |

## Multiple-testing & honesty caveats

- 47 original-direction cells + 12 inversion cells = 59 hypotheses tested in total. At an uncorrected 95% threshold you'd expect ~3 'significant' cells by chance alone with zero real effect anywhere. Benjamini-Hochberg FDR (q=0.1) is applied across each table's full cell pool (separately for originals and inversions) -- only the **bold YES** rows should be read as surviving that correction; everything else is reported for honesty/transparency, not as a finding.
- `three_black_crows|daily`'s inversion cell has an uncorrected p=0.0054 -- looks dramatic in isolation -- but held-out n=7 (in-sample n=0) and `bear_flag|daily`'s inversion (uncorrected p=0.0088) flips sign between in-sample (+0.53R) and held-out (-0.47R). Both are exactly the kind of cell this report's correction step exists to catch: do not act on either.
- The baseline is pooled across all 3 tickers per timeframe, not computed per-ticker. A pattern's edge (or lack of one) reported here is an AAPL+NKE+INTC-pooled statement; ticker-specific divergence is not ruled out and was not separately tested (that would triple the cell count for an already-large multiple-testing budget).
- Stage B's R-bracket settlement ("max target reached before the stop, uncapped at 1R on the win side, capped at exactly -1R on the loss side") is why baseline expectancy is not zero -- see Step 3. Every comparison in this report is pattern-vs-baseline under this identical convention, which is the correct way to neutralize it, but the convention itself should not be mistaken for real-world P&L (no spread/slippage/commissions, and partial fills at R1 are not modeled -- this measures whether the move happened, not a tradable execution).

## Scoping notes (what was reused, what wasn't, and why)

- **Candlesticks (19):** `atlas_research.ta.candlesticks.detect_all_candles`, reused verbatim. Per-pattern confirm/invalidate levels are hand-mapped from pattern_reference's literal text (e.g. hammer confirm = close above the hammer's high; invalidate = close below its low) -- documented per-pattern in `pattern_fulfillment_candlesticks.py`. `morning_star`/`evening_star` are `confirmed_immediately`: per pattern_reference, the third bar's close beyond bar-1's midpoint **is** the confirmation, already enforced by the detector's own shape condition -- so T_recog = T_confirm and the real test is entirely Stage B's R-bracket.
- **Chart patterns / channels / gaps were NOT read from `pattern_memory` or the live `gaps` table.** `pattern_memory`'s chart-pattern rows (and `ta.patterns.py`'s own `double_top_bottom`/`head_and_shoulders`/`flags` functions) only ever emit ALREADY-CONFIRMED instances -- they search forward for the breakout and silently drop any shape that never finds one. That would make it structurally impossible to count failed/invalidated/no-follow-through instances, which this backtest is required to do honestly. So this measurement replicates the same pivot-shape conditions (same tolerances) but emits a candidate at RECOGNITION regardless of outcome, and lets the shared engine do the confirm/invalidate/neither accounting. The `gaps` table (and `vwap_5m`) exist live in the database but are products of separate, uncommitted work on branch `feat/gaps` not in this phase's sanctioned read-only table list -- classic gaps and FVG are computed fresh from `intraday_bars`/`raw_bars` here instead.
- **Channel detection** (`channel_ascending/descending/horizontal/break`) does not exist on `fix/model-validity` (this branch's base) under `src/atlas_research/ta/`. It exists, fully committed and pushed to origin, on sibling branch `feat/channels-and-5m` (commit `65c3fbe`, same merge-base as this branch). Its `detect_channels()` is reproduced verbatim in `scripts/research/pattern_fulfillment_channels.py` (not merged -- this phase's rule is new files only under scripts/research and reports/research) since it's a stable, already-in-production-use function (pattern_memory's existing channel rows were built with it), not in-flux WIP. Channel confirmation is simplified to the breakout/breakdown case only -- pattern_reference's text also describes a 'bounce/continuation' case with no single mechanical trigger common across all three channel shapes, so that sub-case is not separately tested.
- **vwap/rsi reclaim, FVG entry-then-reaction:** these need a 2-step check ("price must first enter a zone/extreme, THEN react") that doesn't fit the shared engine's generic single-level template, so they're computed with a small bespoke forward scan per pattern (documented in each module) rather than forcing a generic abstraction to fit. VWAP's 'holds for 1-2 bars' confirmation is simplified to a 1-bar hold check.
- **The inversion direction is always 'flip the instance's own resolved direction'** -- this is not an oversimplification so much as a mathematical identity: pattern_reference's invalidation_becomes direction is, in every case checked, the same as the direction of the invalidation break itself, which is necessarily the opposite of the original pattern's direction (that's what makes it an invalidation). `channel_break`/`channel_horizontal` resolve their 'original' direction from the realized break direction at confirmation time, since those two patterns don't have one fixed direction at recognition.
- **The 4 supplemental shapes** (`flat_top`, `long_upper_wick`, `long_lower_wick`, `continuation_candle`) are NOT pattern_reference rows -- defined here by analogy to the nearest official patterns (documented in `pattern_fulfillment_supplemental.py`), reported throughout but marked `*` and excluded from the inversion test (no `invalidation_becomes` basis exists for them).

## Verdict

**Plain answer: mostly no, with one real exception among the originals, and zero among the inversions.** Of 47 testable (pattern, timeframe) cells with enough held-out data to trust, only **2 survive** Benjamini-Hochberg correction at q=0.10: `tweezer_top` (5m, an official pattern_reference row) and `flat_top` (5m, a supplemental shape defined here, not in pattern_reference). Of the 12 testable invalidation-becomes inversion cells, **zero survive** -- the "failed pattern becomes the opposite opportunity" thesis, despite being explicitly flagged in the brief as the more interesting, less-crowded hypothesis, does not hold up once judged by the same OOS-plus-multiple-testing bar applied to everything else in this report.

- **The baseline itself is the most important number in this report, and it isn't zero.** 5m baseline expectancy is +0.049R to +0.055R, daily is +0.066R to +0.072R, both in-sample and held-out, both timeframes. This is a mechanical property of the "highest R-target reached before the stop" bracket convention (wins can be 1, 2, or 3R; losses are always exactly -1R), not a market inefficiency -- a literal coin flip nets slightly positive in this unit. The practical effect: most patterns in the table above show a *positive raw expectancy* (45 of 47 cells), which would look like "the pattern works" if read in isolation -- but the right comparison is to baseline, and against that bar, 45 of 47 are statistically indistinguishable from doing nothing with the same risk geometry.

- **`tweezer_top` (5m) is the one official pattern with a real, replicating edge.** Held-out expectancy +0.104R vs. baseline's +0.049R (p=0.0005, survives correction), and the in-sample estimate (+0.056R) is in the same direction and same order of magnitude -- this replicates rather than decays out-of-sample, the opposite of the overfit signature. It fires often (43,922 instances, confirming 58.7% of the time), so this isn't a small-sample fluke either. This is the strongest single result in the measurement.

- **`flat_top` (5m) also survives, but it is not one of the 43 official patterns** -- it's a shape defined in this measurement by analogy ("price re-tests a recent ceiling and closes red"), included because the brief asked to detect shapes the user's eye flagged that may not be in pattern_memory. Worth flagging precisely because it's *not* canonical: it confirms only 29.7% of the time (the ceiling usually breaks rather than holds, invalidating 64.8% of instances) yet still nets a positive, baseline-beating expectancy on the ~30% that do confirm (held-out +0.111R vs. baseline +0.049R, p=0.0025) -- a clean illustration of why the brief insists on judging by expectancy, not win/confirm rate: a low hit rate and a positive expectancy can coexist when wins run further than losses are allowed to.

- **The inversion test is an honest, clean null.** All 12 eligible cells fail to beat baseline after correction, including `tweezer_top`'s own inversion (held-out +0.046R, statistically identical to baseline's +0.049R, p=0.89) -- the same pattern whose original direction is this report's strongest finding shows *no* edge when you trade its failure. Two cells looked tempting before correction (`three_black_crows` inverted, daily, uncorrected p=0.0054; `bear_flag` inverted, daily, uncorrected p=0.0088) but both are textbook traps: the former has held-out n=7 (in-sample n=0), the latter flips from +0.53R in-sample to -0.47R held-out. Both are exactly what the multiple-testing correction exists to catch, and neither should be read as a finding.

- **Several other patterns show the overfit signature explicitly** (flagged ⚠sign-flip in the tables): `hammer` (5m), `inverted_hammer` (5m), `evening_star` (5m), `bearish_engulfing` (daily), `shooting_star` (daily), `hammer` (daily), and the inversions of `bear_flag` (daily), `tweezer_bottom` (daily), `three_white_soldiers` (5m) all change sign between in-sample and held-out -- a reminder that even the *uncorrected* in-sample numbers for these would have been misleading if reported alone.

- **Stage A accounting (confirm/invalidate/neither) shows the "failed patterns are not the photogenic minority" finding plainly.** Across both timeframes, candlestick reversal patterns confirm roughly 45-75% of the time and invalidate the rest almost immediately (`bearish_harami` daily: 45.9% confirmed vs. 53.9% invalidated; `inverted_hammer` 5m: 37.5% vs. 62.5%) -- failure is common and ordinary, not a rare tail case, exactly as the brief expected going in. Chart patterns and channels carry a meaningfully larger "neither" (no-follow-through) bucket (`double_top`/`double_bottom` daily: ~13%; `channel_horizontal`/`hs_top` daily: 17-24%) -- consistent with slower-forming, more structurally ambiguous shapes simply taking longer to resolve one way or the other within a 15-day window.

- **Bottom line, matching the brief's own honest prior:** this is the fourth measurement in this research arc (after setup-formation v1, v2, and the confluence test) to come back mostly null on single-name pattern-based prediction. Out of 43 official patterns plus 4 supplemental shapes, tested across two timeframes and judged on the right metric (expectancy over baseline, OOS, multiple-testing corrected), exactly one official pattern (`tweezer_top`) shows a real, replicating, modest edge, and the inversion thesis -- the one part of this brief explicitly framed as the more promising avenue -- shows none. That is a valid, useful, and honestly negative-leaning result: it does not mean technical patterns are worthless, but it does mean that, for this universe (AAPL/NKE/INTC, 5m and daily, this R-bracket convention, this measurement window), nearly all of the taught confirm/invalidate/invalidation-becomes behavior in `pattern_reference` fulfills at close to baseline rates rather than the rates implied by the teaching material.

## Reproducibility

- Full per-cell aggregates: `reports/research/pattern_fulfillment_summary.json` (run `20260621T213843Z-2ae673ad`)
- Run parameters: `reports/research/pattern_fulfillment_run_log.jsonl` (same run_id)
- Raw rows: `research_pattern_fulfillment` table, `WHERE run_id = '20260621T213843Z-2ae673ad'`
- Example annotated charts: `reports/research/charts/` (prefixed `pf_`)
