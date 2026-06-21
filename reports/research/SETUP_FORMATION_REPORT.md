# Setup-Formation Measurement Report

**MEASURE & REPORT ONLY.** This is a foundation measurement of how often a recognizable N-candle structure is *forming* on 5-minute bars, and what its historical forward base rate looks like. It is **not a predictor and not a trading signal** -- no projection or signal-generation logic has been built on top of these numbers. A null/neutral result (no setup forming, or a flat base rate) is reported honestly where that's what the data shows.

- **Run ID:** `20260621T163148Z-16c317bb`
- **Git commit:** `25accacc430d3c43cb96a21fcf51b47aba81dbfa` (branch `research/setup-formation`)
- **Timestamp (UTC):** 2026-06-21T16:38:09.269501+00:00
- **Tickers:** AAPL, NKE, INTC
- **N (formation window sizes):** [2, 3, 4, 5]
- **K (forward horizons, bars):** [1, 2, 3, 4, 5]
- **Total wall time:** 380.5s

## 1. Stock selection

Picked from tickers with sufficient 5m history in `intraday_bars`, using a 20-day rolling Kaufman Efficiency Ratio (ER) on daily closes derived from 5m bars (averaged over full history) plus daily return std% as the volatility axis -- a 'trend cleanliness vs. choppiness' ranking, not narrative/reputation picking.

| Ticker | Role | ER (trend cleanliness) | Daily ret std% | Bars (5m) | Date range |
|---|---|---|---|---|---|
| AAPL | liquid megacap | 0.262 | 1.6% | 67,241 | 2023-01-03 14:30:00+00:00 .. 2026-06-18 17:10:00+00:00 |
| NKE | cleaner mid/large-cap trender | 0.247 | 2.22% | 105,770 | 2021-01-04 14:30:00+00:00 .. 2026-06-18 18:00:00+00:00 |
| INTC | choppy / volatile | 0.223 | 3.25% | 106,393 | 2021-01-04 14:30:00+00:00 .. 2026-06-18 17:20:00+00:00 |

- **AAPL** (liquid megacap): Highest efficiency ratio (tied) of 30 scanned candidates, with the lowest daily return std% of all 30 -- calm, efficient, highly liquid megacap.
- **NKE** (cleaner mid/large-cap trender): Top-quartile efficiency ratio among non-megacap names, below-median volatility -- trends with comparatively low noise; different sector (consumer/apparel) from the megacap tech pick.
- **INTC** (choppy / volatile): 4th-lowest efficiency ratio (weak trend persistence) combined with 4th-highest volatility of 30 candidates -- large swings that don't resolve into clean sustained trends. TSLA was rejected for this slot despite higher raw volatility (4.14%) because its ER (0.252) was actually above median -- its big moves DO resolve into real trends, the opposite of the 'choppy/non-resolving' character this slot needs.

## 2. How often is a setup forming? (per N, per ticker)

State frequency at each decision point (k=1 row only -- one row per decision point), split by walk-forward portion (`in_sample` = first 70% chronologically per ticker, `held_out` = last 30%).

| Ticker | N | Portion | Total decision points | SETUP_FORMING | NEUTRAL | FLAT |
|---|---|---|---|---|---|---|
| AAPL | 2 | in_sample | 47,048 | 27,349 (58.1%) | 18,775 (39.9%) | 924 (2.0%) |
| AAPL | 2 | held_out | 20,168 | 11,535 (57.2%) | 8,308 (41.2%) | 325 (1.6%) |
| AAPL | 3 | in_sample | 47,047 | 28,016 (59.5%) | 18,671 (39.7%) | 360 (0.8%) |
| AAPL | 3 | held_out | 20,168 | 11,777 (58.4%) | 8,268 (41.0%) | 123 (0.6%) |
| AAPL | 4 | in_sample | 47,046 | 28,132 (59.8%) | 18,744 (39.8%) | 170 (0.4%) |
| AAPL | 4 | held_out | 20,168 | 11,822 (58.6%) | 8,303 (41.2%) | 43 (0.2%) |
| AAPL | 5 | in_sample | 47,045 | 28,205 (60.0%) | 18,767 (39.9%) | 73 (0.2%) |
| AAPL | 5 | held_out | 20,168 | 11,842 (58.7%) | 8,312 (41.2%) | 14 (0.1%) |
| NKE | 2 | in_sample | 74,019 | 41,612 (56.2%) | 24,874 (33.6%) | 7,533 (10.2%) |
| NKE | 2 | held_out | 31,726 | 17,547 (55.3%) | 13,161 (41.5%) | 1,018 (3.2%) |
| NKE | 3 | in_sample | 74,018 | 43,252 (58.4%) | 25,133 (34.0%) | 5,633 (7.6%) |
| NKE | 3 | held_out | 31,726 | 17,950 (56.6%) | 13,238 (41.7%) | 538 (1.7%) |
| NKE | 4 | in_sample | 74,017 | 44,047 (59.5%) | 25,622 (34.6%) | 4,348 (5.9%) |
| NKE | 4 | held_out | 31,726 | 18,109 (57.1%) | 13,350 (42.1%) | 267 (0.8%) |
| NKE | 5 | in_sample | 74,016 | 44,534 (60.2%) | 25,930 (35.0%) | 3,552 (4.8%) |
| NKE | 5 | held_out | 31,726 | 18,177 (57.3%) | 13,386 (42.2%) | 163 (0.5%) |
| INTC | 2 | in_sample | 74,455 | 41,625 (55.9%) | 30,731 (41.3%) | 2,099 (2.8%) |
| INTC | 2 | held_out | 31,913 | 16,169 (50.7%) | 15,021 (47.1%) | 723 (2.3%) |
| INTC | 3 | in_sample | 74,454 | 42,229 (56.7%) | 31,150 (41.8%) | 1,075 (1.4%) |
| INTC | 3 | held_out | 31,913 | 16,287 (51.0%) | 15,286 (47.9%) | 340 (1.1%) |
| INTC | 4 | in_sample | 74,453 | 42,511 (57.1%) | 31,364 (42.1%) | 578 (0.8%) |
| INTC | 4 | held_out | 31,913 | 16,377 (51.3%) | 15,351 (48.1%) | 185 (0.6%) |
| INTC | 5 | in_sample | 74,452 | 42,662 (57.3%) | 31,472 (42.3%) | 318 (0.4%) |
| INTC | 5 | held_out | 31,913 | 16,432 (51.5%) | 15,381 (48.2%) | 100 (0.3%) |

## 3. What's actually firing (setup-type composition)

Counts of `setup_type` among SETUP_FORMING decision points (in-sample), per ticker at N=2 and N=5 (the shortest and longest window -- composition is nearly identical across N=3,4,5 since the candlestick detector's max pattern span is 3 bars, so once N>=3 every pattern fits regardless of N).

- **AAPL N=2:** tweezer_top (8328), tweezer_bottom (7705), bearish_engulfing (3662), bullish_engulfing (3573), marubozu (3365), bearish_harami (2543)
- **AAPL N=5:** tweezer_top (8539), tweezer_bottom (7898), bearish_engulfing (3711), bullish_engulfing (3603), marubozu (3407), bearish_harami (2594)
- **NKE N=2:** marubozu (10599), tweezer_bottom (10166), tweezer_top (9989), bearish_engulfing (4757), bullish_engulfing (4643), bullish_harami (3962)
- **NKE N=5:** marubozu (11326), tweezer_bottom (10756), tweezer_top (10569), bearish_engulfing (4864), bullish_engulfing (4753), bullish_harami (4088)
- **INTC N=2:** tweezer_top (8624), tweezer_bottom (8330), marubozu (7269), bullish_engulfing (6031), bearish_engulfing (5893), bearish_harami (4824)
- **INTC N=5:** tweezer_top (8935), tweezer_bottom (8646), marubozu (7404), bullish_engulfing (6111), bearish_engulfing (5976), bearish_harami (4947)

**Caveat:** tweezer_top/tweezer_bottom (high/low match within 0.08%, the same tolerance `build_candle_memory.py` already uses for its own 5m candlestick layer) account for roughly a third to half of all SETUP_FORMING calls across tickers. This is a real property of the existing detector applied at 5m resolution, not a bug introduced here -- but it means a large share of 'forming' classifications are driven by an equal-extremes geometry check rather than the more complex multi-bar reversal shapes. Worth knowing before reading too much into the aggregate forming-rate.

## 4. Forward base-rate curves (by N and K)

For each ticker/N: mean forward return and ATR-hit rate over K=1..5 bars, for SETUP_FORMING decision points vs. the unconditional ALL baseline (every decision point regardless of state) -- this is the comparison that tells you whether 'forming' actually differs from doing nothing. 95% CIs shown; `hit_target` is null (excluded from the hit-rate calc) for decision points with no directional thesis.

**Read the hit-rate column carefully:** `hit_target` only exists for rows with a classified `direction`, and only SETUP_FORMING rows get a direction (NEUTRAL/FLAT never do) -- so the "ALL" row's hit-rate is computed over *the same underlying rows* as the SETUP_FORMING row at that N/K (see the `Hit n` column: it's identical between the two states). The hit-rate comparison is therefore tautological, not an independent baseline -- it will always show 0.0pp difference. The **mean forward return** column is the real baseline comparison here, since it's defined for every decision point regardless of state.


### AAPL

| N | K | State | Portion | n | Mean fwd return | 95% CI | Hit rate (±1 ATR) | Hit n |
|---|---|---|---|---|---|---|---|---|
| 2 | 1 | SETUP_FORMING | in_sample | 27,349 | 0.000% | [-0.002%, 0.003%] | 12.9% | 27,349 |
| 2 | 1 | SETUP_FORMING | held_out | 11,535 | 0.001% | [-0.002%, 0.004%] | 12.5% | 11,535 |
| 2 | 2 | SETUP_FORMING | in_sample | 27,349 | 0.001% | [-0.002%, 0.004%] | 25.8% | 27,349 |
| 2 | 2 | SETUP_FORMING | held_out | 11,535 | 0.003% | [-0.001%, 0.008%] | 25.5% | 11,535 |
| 2 | 3 | SETUP_FORMING | in_sample | 27,349 | 0.003% | [-0.001%, 0.007%] | 35.1% | 27,349 |
| 2 | 3 | SETUP_FORMING | held_out | 11,535 | 0.007% | [0.001%, 0.012%] | 34.7% | 11,535 |
| 2 | 4 | SETUP_FORMING | in_sample | 27,349 | 0.004% | [-0.000%, 0.009%] | 41.7% | 27,349 |
| 2 | 4 | SETUP_FORMING | held_out | 11,535 | 0.007% | [0.001%, 0.013%] | 41.2% | 11,535 |
| 2 | 5 | SETUP_FORMING | in_sample | 27,349 | 0.005% | [-0.000%, 0.010%] | 46.7% | 27,349 |
| 2 | 5 | SETUP_FORMING | held_out | 11,535 | 0.011% | [0.004%, 0.018%] | 46.4% | 11,535 |
| 2 | 1 | ALL | in_sample | 47,048 | 0.001% | [-0.001%, 0.003%] | 12.9% | 27,349 |
| 2 | 1 | ALL | held_out | 20,168 | 0.002% | [-0.000%, 0.004%] | 12.5% | 11,535 |
| 2 | 2 | ALL | in_sample | 47,048 | 0.002% | [-0.000%, 0.005%] | 25.8% | 27,349 |
| 2 | 2 | ALL | held_out | 20,168 | 0.004% | [0.001%, 0.007%] | 25.5% | 11,535 |
| 2 | 3 | ALL | in_sample | 47,048 | 0.004% | [0.001%, 0.007%] | 35.1% | 27,349 |
| 2 | 3 | ALL | held_out | 20,168 | 0.006% | [0.002%, 0.010%] | 34.7% | 11,535 |
| 2 | 4 | ALL | in_sample | 47,048 | 0.005% | [0.001%, 0.008%] | 41.7% | 27,349 |
| 2 | 4 | ALL | held_out | 20,168 | 0.008% | [0.004%, 0.013%] | 41.2% | 11,535 |
| 2 | 5 | ALL | in_sample | 47,048 | 0.006% | [0.002%, 0.010%] | 46.7% | 27,349 |
| 2 | 5 | ALL | held_out | 20,168 | 0.010% | [0.005%, 0.015%] | 46.4% | 11,535 |
| 3 | 1 | SETUP_FORMING | in_sample | 28,016 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,016 |
| 3 | 1 | SETUP_FORMING | held_out | 11,777 | 0.002% | [-0.001%, 0.005%] | 12.2% | 11,777 |
| 3 | 2 | SETUP_FORMING | in_sample | 28,016 | 0.002% | [-0.002%, 0.005%] | 25.6% | 28,016 |
| 3 | 2 | SETUP_FORMING | held_out | 11,777 | 0.004% | [-0.000%, 0.008%] | 25.3% | 11,777 |
| 3 | 3 | SETUP_FORMING | in_sample | 28,016 | 0.003% | [-0.001%, 0.007%] | 34.8% | 28,016 |
| 3 | 3 | SETUP_FORMING | held_out | 11,777 | 0.007% | [0.001%, 0.012%] | 34.6% | 11,777 |
| 3 | 4 | SETUP_FORMING | in_sample | 28,016 | 0.004% | [-0.000%, 0.008%] | 41.4% | 28,016 |
| 3 | 4 | SETUP_FORMING | held_out | 11,777 | 0.007% | [0.001%, 0.013%] | 41.0% | 11,777 |
| 3 | 5 | SETUP_FORMING | in_sample | 28,016 | 0.004% | [-0.001%, 0.009%] | 46.5% | 28,016 |
| 3 | 5 | SETUP_FORMING | held_out | 11,777 | 0.011% | [0.004%, 0.017%] | 46.2% | 11,777 |
| 3 | 1 | ALL | in_sample | 47,047 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,016 |
| 3 | 1 | ALL | held_out | 20,168 | 0.002% | [-0.000%, 0.004%] | 12.2% | 11,777 |
| 3 | 2 | ALL | in_sample | 47,047 | 0.002% | [-0.000%, 0.005%] | 25.6% | 28,016 |
| 3 | 2 | ALL | held_out | 20,168 | 0.004% | [0.001%, 0.007%] | 25.3% | 11,777 |
| 3 | 3 | ALL | in_sample | 47,047 | 0.004% | [0.001%, 0.007%] | 34.8% | 28,016 |
| 3 | 3 | ALL | held_out | 20,168 | 0.006% | [0.002%, 0.010%] | 34.6% | 11,777 |
| 3 | 4 | ALL | in_sample | 47,047 | 0.005% | [0.001%, 0.008%] | 41.4% | 28,016 |
| 3 | 4 | ALL | held_out | 20,168 | 0.008% | [0.004%, 0.013%] | 41.0% | 11,777 |
| 3 | 5 | ALL | in_sample | 47,047 | 0.006% | [0.002%, 0.010%] | 46.5% | 28,016 |
| 3 | 5 | ALL | held_out | 20,168 | 0.010% | [0.005%, 0.015%] | 46.2% | 11,777 |
| 4 | 1 | SETUP_FORMING | in_sample | 28,132 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,132 |
| 4 | 1 | SETUP_FORMING | held_out | 11,822 | 0.002% | [-0.001%, 0.005%] | 12.2% | 11,822 |
| 4 | 2 | SETUP_FORMING | in_sample | 28,132 | 0.001% | [-0.002%, 0.005%] | 25.6% | 28,132 |
| 4 | 2 | SETUP_FORMING | held_out | 11,822 | 0.004% | [-0.000%, 0.008%] | 25.4% | 11,822 |
| 4 | 3 | SETUP_FORMING | in_sample | 28,132 | 0.003% | [-0.001%, 0.007%] | 34.8% | 28,132 |
| 4 | 3 | SETUP_FORMING | held_out | 11,822 | 0.006% | [0.001%, 0.011%] | 34.6% | 11,822 |
| 4 | 4 | SETUP_FORMING | in_sample | 28,132 | 0.004% | [-0.000%, 0.008%] | 41.4% | 28,132 |
| 4 | 4 | SETUP_FORMING | held_out | 11,822 | 0.007% | [0.001%, 0.012%] | 41.0% | 11,822 |
| 4 | 5 | SETUP_FORMING | in_sample | 28,132 | 0.004% | [-0.001%, 0.009%] | 46.5% | 28,132 |
| 4 | 5 | SETUP_FORMING | held_out | 11,822 | 0.011% | [0.004%, 0.017%] | 46.2% | 11,822 |
| 4 | 1 | ALL | in_sample | 47,046 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,132 |
| 4 | 1 | ALL | held_out | 20,168 | 0.002% | [-0.000%, 0.004%] | 12.2% | 11,822 |
| 4 | 2 | ALL | in_sample | 47,046 | 0.002% | [-0.000%, 0.005%] | 25.6% | 28,132 |
| 4 | 2 | ALL | held_out | 20,168 | 0.004% | [0.001%, 0.007%] | 25.4% | 11,822 |
| 4 | 3 | ALL | in_sample | 47,046 | 0.004% | [0.001%, 0.007%] | 34.8% | 28,132 |
| 4 | 3 | ALL | held_out | 20,168 | 0.006% | [0.002%, 0.010%] | 34.6% | 11,822 |
| 4 | 4 | ALL | in_sample | 47,046 | 0.005% | [0.001%, 0.008%] | 41.4% | 28,132 |
| 4 | 4 | ALL | held_out | 20,168 | 0.008% | [0.004%, 0.013%] | 41.0% | 11,822 |
| 4 | 5 | ALL | in_sample | 47,046 | 0.006% | [0.002%, 0.010%] | 46.5% | 28,132 |
| 4 | 5 | ALL | held_out | 20,168 | 0.010% | [0.005%, 0.015%] | 46.2% | 11,822 |
| 5 | 1 | SETUP_FORMING | in_sample | 28,205 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,205 |
| 5 | 1 | SETUP_FORMING | held_out | 11,842 | 0.002% | [-0.001%, 0.005%] | 12.2% | 11,842 |
| 5 | 2 | SETUP_FORMING | in_sample | 28,205 | 0.002% | [-0.002%, 0.005%] | 25.6% | 28,205 |
| 5 | 2 | SETUP_FORMING | held_out | 11,842 | 0.004% | [-0.001%, 0.008%] | 25.4% | 11,842 |
| 5 | 3 | SETUP_FORMING | in_sample | 28,205 | 0.003% | [-0.001%, 0.007%] | 34.8% | 28,205 |
| 5 | 3 | SETUP_FORMING | held_out | 11,842 | 0.006% | [0.001%, 0.011%] | 34.6% | 11,842 |
| 5 | 4 | SETUP_FORMING | in_sample | 28,205 | 0.004% | [-0.000%, 0.008%] | 41.4% | 28,205 |
| 5 | 4 | SETUP_FORMING | held_out | 11,842 | 0.006% | [0.000%, 0.012%] | 41.0% | 11,842 |
| 5 | 5 | SETUP_FORMING | in_sample | 28,205 | 0.004% | [-0.001%, 0.009%] | 46.5% | 28,205 |
| 5 | 5 | SETUP_FORMING | held_out | 11,842 | 0.010% | [0.004%, 0.017%] | 46.2% | 11,842 |
| 5 | 1 | ALL | in_sample | 47,045 | 0.001% | [-0.001%, 0.003%] | 12.7% | 28,205 |
| 5 | 1 | ALL | held_out | 20,168 | 0.002% | [-0.000%, 0.004%] | 12.2% | 11,842 |
| 5 | 2 | ALL | in_sample | 47,045 | 0.002% | [-0.000%, 0.005%] | 25.6% | 28,205 |
| 5 | 2 | ALL | held_out | 20,168 | 0.004% | [0.001%, 0.007%] | 25.4% | 11,842 |
| 5 | 3 | ALL | in_sample | 47,045 | 0.004% | [0.001%, 0.007%] | 34.8% | 28,205 |
| 5 | 3 | ALL | held_out | 20,168 | 0.006% | [0.002%, 0.010%] | 34.6% | 11,842 |
| 5 | 4 | ALL | in_sample | 47,045 | 0.005% | [0.001%, 0.008%] | 41.4% | 28,205 |
| 5 | 4 | ALL | held_out | 20,168 | 0.008% | [0.004%, 0.013%] | 41.0% | 11,842 |
| 5 | 5 | ALL | in_sample | 47,045 | 0.006% | [0.002%, 0.010%] | 46.5% | 28,205 |
| 5 | 5 | ALL | held_out | 20,168 | 0.010% | [0.005%, 0.015%] | 46.2% | 11,842 |

### NKE

| N | K | State | Portion | n | Mean fwd return | 95% CI | Hit rate (±1 ATR) | Hit n |
|---|---|---|---|---|---|---|---|---|
| 2 | 1 | SETUP_FORMING | in_sample | 41,612 | -0.001% | [-0.003%, 0.002%] | 15.2% | 41,612 |
| 2 | 1 | SETUP_FORMING | held_out | 17,547 | -0.003% | [-0.007%, 0.001%] | 14.0% | 17,547 |
| 2 | 2 | SETUP_FORMING | in_sample | 41,612 | 0.001% | [-0.002%, 0.004%] | 28.7% | 41,612 |
| 2 | 2 | SETUP_FORMING | held_out | 17,547 | -0.004% | [-0.010%, 0.001%] | 27.2% | 17,547 |
| 2 | 3 | SETUP_FORMING | in_sample | 41,612 | 0.000% | [-0.003%, 0.004%] | 37.8% | 41,612 |
| 2 | 3 | SETUP_FORMING | held_out | 17,547 | -0.007% | [-0.014%, -0.000%] | 36.5% | 17,547 |
| 2 | 4 | SETUP_FORMING | in_sample | 41,612 | -0.001% | [-0.005%, 0.004%] | 44.1% | 41,612 |
| 2 | 4 | SETUP_FORMING | held_out | 17,547 | -0.010% | [-0.018%, -0.002%] | 42.9% | 17,547 |
| 2 | 5 | SETUP_FORMING | in_sample | 41,612 | -0.001% | [-0.006%, 0.005%] | 48.9% | 41,612 |
| 2 | 5 | SETUP_FORMING | held_out | 17,547 | -0.011% | [-0.020%, -0.002%] | 47.5% | 17,547 |
| 2 | 1 | ALL | in_sample | 74,019 | -0.000% | [-0.002%, 0.001%] | 15.2% | 41,612 |
| 2 | 1 | ALL | held_out | 31,726 | -0.001% | [-0.004%, 0.002%] | 14.0% | 17,547 |
| 2 | 2 | ALL | in_sample | 74,019 | -0.001% | [-0.003%, 0.001%] | 28.7% | 41,612 |
| 2 | 2 | ALL | held_out | 31,726 | -0.003% | [-0.007%, 0.002%] | 27.2% | 17,547 |
| 2 | 3 | ALL | in_sample | 74,019 | -0.001% | [-0.004%, 0.001%] | 37.8% | 41,612 |
| 2 | 3 | ALL | held_out | 31,726 | -0.004% | [-0.009%, 0.001%] | 36.5% | 17,547 |
| 2 | 4 | ALL | in_sample | 74,019 | -0.002% | [-0.005%, 0.001%] | 44.1% | 41,612 |
| 2 | 4 | ALL | held_out | 31,726 | -0.005% | [-0.012%, 0.001%] | 42.9% | 17,547 |
| 2 | 5 | ALL | in_sample | 74,019 | -0.002% | [-0.006%, 0.001%] | 48.9% | 41,612 |
| 2 | 5 | ALL | held_out | 31,726 | -0.007% | [-0.014%, 0.000%] | 47.5% | 17,547 |
| 3 | 1 | SETUP_FORMING | in_sample | 43,252 | -0.001% | [-0.003%, 0.002%] | 15.0% | 43,252 |
| 3 | 1 | SETUP_FORMING | held_out | 17,950 | -0.003% | [-0.007%, 0.001%] | 13.7% | 17,950 |
| 3 | 2 | SETUP_FORMING | in_sample | 43,252 | 0.001% | [-0.002%, 0.004%] | 28.5% | 43,252 |
| 3 | 2 | SETUP_FORMING | held_out | 17,950 | -0.006% | [-0.011%, -0.000%] | 26.9% | 17,950 |
| 3 | 3 | SETUP_FORMING | in_sample | 43,252 | 0.001% | [-0.003%, 0.005%] | 37.5% | 43,252 |
| 3 | 3 | SETUP_FORMING | held_out | 17,950 | -0.008% | [-0.014%, -0.001%] | 36.2% | 17,950 |
| 3 | 4 | SETUP_FORMING | in_sample | 43,252 | -0.000% | [-0.004%, 0.004%] | 43.9% | 43,252 |
| 3 | 4 | SETUP_FORMING | held_out | 17,950 | -0.011% | [-0.019%, -0.003%] | 42.6% | 17,950 |
| 3 | 5 | SETUP_FORMING | in_sample | 43,252 | -0.000% | [-0.005%, 0.004%] | 48.6% | 43,252 |
| 3 | 5 | SETUP_FORMING | held_out | 17,950 | -0.012% | [-0.020%, -0.003%] | 47.2% | 17,950 |
| 3 | 1 | ALL | in_sample | 74,018 | -0.000% | [-0.002%, 0.001%] | 15.0% | 43,252 |
| 3 | 1 | ALL | held_out | 31,726 | -0.001% | [-0.004%, 0.002%] | 13.7% | 17,950 |
| 3 | 2 | ALL | in_sample | 74,018 | -0.001% | [-0.003%, 0.001%] | 28.5% | 43,252 |
| 3 | 2 | ALL | held_out | 31,726 | -0.003% | [-0.007%, 0.002%] | 26.9% | 17,950 |
| 3 | 3 | ALL | in_sample | 74,018 | -0.001% | [-0.004%, 0.001%] | 37.5% | 43,252 |
| 3 | 3 | ALL | held_out | 31,726 | -0.004% | [-0.009%, 0.001%] | 36.2% | 17,950 |
| 3 | 4 | ALL | in_sample | 74,018 | -0.002% | [-0.005%, 0.001%] | 43.9% | 43,252 |
| 3 | 4 | ALL | held_out | 31,726 | -0.005% | [-0.012%, 0.001%] | 42.6% | 17,950 |
| 3 | 5 | ALL | in_sample | 74,018 | -0.002% | [-0.006%, 0.001%] | 48.6% | 43,252 |
| 3 | 5 | ALL | held_out | 31,726 | -0.007% | [-0.014%, 0.000%] | 47.2% | 17,950 |
| 4 | 1 | SETUP_FORMING | in_sample | 44,047 | -0.001% | [-0.003%, 0.001%] | 15.0% | 44,047 |
| 4 | 1 | SETUP_FORMING | held_out | 18,109 | -0.003% | [-0.007%, 0.000%] | 13.7% | 18,109 |
| 4 | 2 | SETUP_FORMING | in_sample | 44,047 | 0.001% | [-0.002%, 0.004%] | 28.5% | 44,047 |
| 4 | 2 | SETUP_FORMING | held_out | 18,109 | -0.006% | [-0.011%, -0.001%] | 26.9% | 18,109 |
| 4 | 3 | SETUP_FORMING | in_sample | 44,047 | 0.001% | [-0.003%, 0.005%] | 37.5% | 44,047 |
| 4 | 3 | SETUP_FORMING | held_out | 18,109 | -0.008% | [-0.014%, -0.001%] | 36.1% | 18,109 |
| 4 | 4 | SETUP_FORMING | in_sample | 44,047 | -0.000% | [-0.005%, 0.004%] | 43.9% | 44,047 |
| 4 | 4 | SETUP_FORMING | held_out | 18,109 | -0.011% | [-0.018%, -0.003%] | 42.6% | 18,109 |
| 4 | 5 | SETUP_FORMING | in_sample | 44,047 | -0.001% | [-0.005%, 0.004%] | 48.6% | 44,047 |
| 4 | 5 | SETUP_FORMING | held_out | 18,109 | -0.012% | [-0.020%, -0.003%] | 47.2% | 18,109 |
| 4 | 1 | ALL | in_sample | 74,017 | -0.000% | [-0.002%, 0.001%] | 15.0% | 44,047 |
| 4 | 1 | ALL | held_out | 31,726 | -0.001% | [-0.004%, 0.002%] | 13.7% | 18,109 |
| 4 | 2 | ALL | in_sample | 74,017 | -0.001% | [-0.003%, 0.001%] | 28.5% | 44,047 |
| 4 | 2 | ALL | held_out | 31,726 | -0.003% | [-0.007%, 0.002%] | 26.9% | 18,109 |
| 4 | 3 | ALL | in_sample | 74,017 | -0.001% | [-0.004%, 0.001%] | 37.5% | 44,047 |
| 4 | 3 | ALL | held_out | 31,726 | -0.004% | [-0.009%, 0.001%] | 36.1% | 18,109 |
| 4 | 4 | ALL | in_sample | 74,017 | -0.002% | [-0.005%, 0.001%] | 43.9% | 44,047 |
| 4 | 4 | ALL | held_out | 31,726 | -0.005% | [-0.012%, 0.001%] | 42.6% | 18,109 |
| 4 | 5 | ALL | in_sample | 74,017 | -0.002% | [-0.006%, 0.001%] | 48.6% | 44,047 |
| 4 | 5 | ALL | held_out | 31,726 | -0.007% | [-0.014%, 0.000%] | 47.2% | 18,109 |
| 5 | 1 | SETUP_FORMING | in_sample | 44,534 | -0.001% | [-0.003%, 0.002%] | 15.0% | 44,534 |
| 5 | 1 | SETUP_FORMING | held_out | 18,177 | -0.003% | [-0.007%, 0.000%] | 13.7% | 18,177 |
| 5 | 2 | SETUP_FORMING | in_sample | 44,534 | 0.001% | [-0.002%, 0.004%] | 28.5% | 44,534 |
| 5 | 2 | SETUP_FORMING | held_out | 18,177 | -0.006% | [-0.011%, -0.001%] | 26.9% | 18,177 |
| 5 | 3 | SETUP_FORMING | in_sample | 44,534 | 0.001% | [-0.003%, 0.005%] | 37.5% | 44,534 |
| 5 | 3 | SETUP_FORMING | held_out | 18,177 | -0.008% | [-0.014%, -0.001%] | 36.1% | 18,177 |
| 5 | 4 | SETUP_FORMING | in_sample | 44,534 | -0.000% | [-0.004%, 0.004%] | 43.9% | 44,534 |
| 5 | 4 | SETUP_FORMING | held_out | 18,177 | -0.011% | [-0.018%, -0.003%] | 42.5% | 18,177 |
| 5 | 5 | SETUP_FORMING | in_sample | 44,534 | -0.001% | [-0.005%, 0.004%] | 48.6% | 44,534 |
| 5 | 5 | SETUP_FORMING | held_out | 18,177 | -0.012% | [-0.020%, -0.003%] | 47.1% | 18,177 |
| 5 | 1 | ALL | in_sample | 74,016 | -0.000% | [-0.002%, 0.001%] | 15.0% | 44,534 |
| 5 | 1 | ALL | held_out | 31,726 | -0.001% | [-0.004%, 0.002%] | 13.7% | 18,177 |
| 5 | 2 | ALL | in_sample | 74,016 | -0.001% | [-0.003%, 0.001%] | 28.5% | 44,534 |
| 5 | 2 | ALL | held_out | 31,726 | -0.003% | [-0.007%, 0.002%] | 26.9% | 18,177 |
| 5 | 3 | ALL | in_sample | 74,016 | -0.001% | [-0.004%, 0.001%] | 37.5% | 44,534 |
| 5 | 3 | ALL | held_out | 31,726 | -0.004% | [-0.009%, 0.001%] | 36.1% | 18,177 |
| 5 | 4 | ALL | in_sample | 74,016 | -0.002% | [-0.005%, 0.001%] | 43.9% | 44,534 |
| 5 | 4 | ALL | held_out | 31,726 | -0.005% | [-0.012%, 0.001%] | 42.5% | 18,177 |
| 5 | 5 | ALL | in_sample | 74,016 | -0.002% | [-0.006%, 0.001%] | 48.6% | 44,534 |
| 5 | 5 | ALL | held_out | 31,726 | -0.007% | [-0.014%, 0.000%] | 47.1% | 18,177 |

### INTC

| N | K | State | Portion | n | Mean fwd return | 95% CI | Hit rate (±1 ATR) | Hit n |
|---|---|---|---|---|---|---|---|---|
| 2 | 1 | SETUP_FORMING | in_sample | 41,625 | -0.001% | [-0.004%, 0.002%] | 13.3% | 41,625 |
| 2 | 1 | SETUP_FORMING | held_out | 16,169 | 0.004% | [-0.004%, 0.013%] | 12.9% | 16,169 |
| 2 | 2 | SETUP_FORMING | in_sample | 41,625 | -0.002% | [-0.006%, 0.002%] | 26.9% | 41,625 |
| 2 | 2 | SETUP_FORMING | held_out | 16,169 | 0.009% | [-0.001%, 0.020%] | 25.4% | 16,169 |
| 2 | 3 | SETUP_FORMING | in_sample | 41,625 | -0.003% | [-0.008%, 0.002%] | 36.3% | 41,625 |
| 2 | 3 | SETUP_FORMING | held_out | 16,169 | 0.018% | [0.004%, 0.031%] | 34.2% | 16,169 |
| 2 | 4 | SETUP_FORMING | in_sample | 41,625 | -0.004% | [-0.009%, 0.002%] | 42.9% | 41,625 |
| 2 | 4 | SETUP_FORMING | held_out | 16,169 | 0.022% | [0.007%, 0.037%] | 40.6% | 16,169 |
| 2 | 5 | SETUP_FORMING | in_sample | 41,625 | -0.003% | [-0.010%, 0.003%] | 47.7% | 41,625 |
| 2 | 5 | SETUP_FORMING | held_out | 16,169 | 0.026% | [0.009%, 0.043%] | 45.2% | 16,169 |
| 2 | 1 | ALL | in_sample | 74,455 | -0.001% | [-0.003%, 0.001%] | 13.3% | 41,625 |
| 2 | 1 | ALL | held_out | 31,913 | 0.007% | [0.001%, 0.012%] | 12.9% | 16,169 |
| 2 | 2 | ALL | in_sample | 74,455 | -0.001% | [-0.004%, 0.002%] | 26.9% | 41,625 |
| 2 | 2 | ALL | held_out | 31,913 | 0.014% | [0.006%, 0.021%] | 25.4% | 16,169 |
| 2 | 3 | ALL | in_sample | 74,455 | -0.002% | [-0.006%, 0.002%] | 36.3% | 41,625 |
| 2 | 3 | ALL | held_out | 31,913 | 0.021% | [0.011%, 0.030%] | 34.2% | 16,169 |
| 2 | 4 | ALL | in_sample | 74,455 | -0.003% | [-0.007%, 0.001%] | 42.9% | 41,625 |
| 2 | 4 | ALL | held_out | 31,913 | 0.027% | [0.016%, 0.038%] | 40.6% | 16,169 |
| 2 | 5 | ALL | in_sample | 74,455 | -0.003% | [-0.008%, 0.001%] | 47.7% | 41,625 |
| 2 | 5 | ALL | held_out | 31,913 | 0.034% | [0.022%, 0.047%] | 45.2% | 16,169 |
| 3 | 1 | SETUP_FORMING | in_sample | 42,229 | -0.001% | [-0.004%, 0.001%] | 13.0% | 42,229 |
| 3 | 1 | SETUP_FORMING | held_out | 16,287 | 0.004% | [-0.005%, 0.012%] | 12.5% | 16,287 |
| 3 | 2 | SETUP_FORMING | in_sample | 42,229 | -0.002% | [-0.005%, 0.002%] | 26.6% | 42,229 |
| 3 | 2 | SETUP_FORMING | held_out | 16,287 | 0.009% | [-0.002%, 0.019%] | 25.1% | 16,287 |
| 3 | 3 | SETUP_FORMING | in_sample | 42,229 | -0.003% | [-0.008%, 0.002%] | 36.0% | 42,229 |
| 3 | 3 | SETUP_FORMING | held_out | 16,287 | 0.016% | [0.003%, 0.029%] | 34.0% | 16,287 |
| 3 | 4 | SETUP_FORMING | in_sample | 42,229 | -0.003% | [-0.009%, 0.002%] | 42.7% | 42,229 |
| 3 | 4 | SETUP_FORMING | held_out | 16,287 | 0.020% | [0.005%, 0.035%] | 40.3% | 16,287 |
| 3 | 5 | SETUP_FORMING | in_sample | 42,229 | -0.003% | [-0.009%, 0.003%] | 47.5% | 42,229 |
| 3 | 5 | SETUP_FORMING | held_out | 16,287 | 0.023% | [0.006%, 0.039%] | 44.9% | 16,287 |
| 3 | 1 | ALL | in_sample | 74,454 | -0.001% | [-0.003%, 0.001%] | 13.0% | 42,229 |
| 3 | 1 | ALL | held_out | 31,913 | 0.007% | [0.001%, 0.012%] | 12.5% | 16,287 |
| 3 | 2 | ALL | in_sample | 74,454 | -0.001% | [-0.004%, 0.002%] | 26.6% | 42,229 |
| 3 | 2 | ALL | held_out | 31,913 | 0.014% | [0.006%, 0.021%] | 25.1% | 16,287 |
| 3 | 3 | ALL | in_sample | 74,454 | -0.002% | [-0.006%, 0.002%] | 36.0% | 42,229 |
| 3 | 3 | ALL | held_out | 31,913 | 0.021% | [0.011%, 0.030%] | 34.0% | 16,287 |
| 3 | 4 | ALL | in_sample | 74,454 | -0.003% | [-0.007%, 0.001%] | 42.7% | 42,229 |
| 3 | 4 | ALL | held_out | 31,913 | 0.027% | [0.016%, 0.038%] | 40.3% | 16,287 |
| 3 | 5 | ALL | in_sample | 74,454 | -0.003% | [-0.008%, 0.001%] | 47.5% | 42,229 |
| 3 | 5 | ALL | held_out | 31,913 | 0.034% | [0.022%, 0.047%] | 44.9% | 16,287 |
| 4 | 1 | SETUP_FORMING | in_sample | 42,511 | -0.001% | [-0.004%, 0.002%] | 13.0% | 42,511 |
| 4 | 1 | SETUP_FORMING | held_out | 16,377 | 0.004% | [-0.004%, 0.012%] | 12.5% | 16,377 |
| 4 | 2 | SETUP_FORMING | in_sample | 42,511 | -0.002% | [-0.005%, 0.002%] | 26.5% | 42,511 |
| 4 | 2 | SETUP_FORMING | held_out | 16,377 | 0.009% | [-0.001%, 0.019%] | 25.0% | 16,377 |
| 4 | 3 | SETUP_FORMING | in_sample | 42,511 | -0.003% | [-0.007%, 0.002%] | 36.0% | 42,511 |
| 4 | 3 | SETUP_FORMING | held_out | 16,377 | 0.016% | [0.003%, 0.029%] | 33.9% | 16,377 |
| 4 | 4 | SETUP_FORMING | in_sample | 42,511 | -0.003% | [-0.009%, 0.002%] | 42.6% | 42,511 |
| 4 | 4 | SETUP_FORMING | held_out | 16,377 | 0.020% | [0.006%, 0.035%] | 40.2% | 16,377 |
| 4 | 5 | SETUP_FORMING | in_sample | 42,511 | -0.003% | [-0.009%, 0.003%] | 47.4% | 42,511 |
| 4 | 5 | SETUP_FORMING | held_out | 16,377 | 0.024% | [0.007%, 0.040%] | 44.8% | 16,377 |
| 4 | 1 | ALL | in_sample | 74,453 | -0.001% | [-0.003%, 0.001%] | 13.0% | 42,511 |
| 4 | 1 | ALL | held_out | 31,913 | 0.007% | [0.001%, 0.012%] | 12.5% | 16,377 |
| 4 | 2 | ALL | in_sample | 74,453 | -0.001% | [-0.004%, 0.002%] | 26.5% | 42,511 |
| 4 | 2 | ALL | held_out | 31,913 | 0.014% | [0.006%, 0.021%] | 25.0% | 16,377 |
| 4 | 3 | ALL | in_sample | 74,453 | -0.002% | [-0.006%, 0.002%] | 36.0% | 42,511 |
| 4 | 3 | ALL | held_out | 31,913 | 0.021% | [0.011%, 0.030%] | 33.9% | 16,377 |
| 4 | 4 | ALL | in_sample | 74,453 | -0.003% | [-0.007%, 0.001%] | 42.6% | 42,511 |
| 4 | 4 | ALL | held_out | 31,913 | 0.027% | [0.016%, 0.038%] | 40.2% | 16,377 |
| 4 | 5 | ALL | in_sample | 74,453 | -0.003% | [-0.008%, 0.001%] | 47.4% | 42,511 |
| 4 | 5 | ALL | held_out | 31,913 | 0.034% | [0.022%, 0.047%] | 44.8% | 16,377 |
| 5 | 1 | SETUP_FORMING | in_sample | 42,662 | -0.001% | [-0.004%, 0.002%] | 13.0% | 42,662 |
| 5 | 1 | SETUP_FORMING | held_out | 16,432 | 0.004% | [-0.004%, 0.012%] | 12.5% | 16,432 |
| 5 | 2 | SETUP_FORMING | in_sample | 42,662 | -0.002% | [-0.005%, 0.002%] | 26.5% | 42,662 |
| 5 | 2 | SETUP_FORMING | held_out | 16,432 | 0.009% | [-0.001%, 0.019%] | 25.0% | 16,432 |
| 5 | 3 | SETUP_FORMING | in_sample | 42,662 | -0.003% | [-0.008%, 0.002%] | 35.9% | 42,662 |
| 5 | 3 | SETUP_FORMING | held_out | 16,432 | 0.016% | [0.003%, 0.029%] | 33.9% | 16,432 |
| 5 | 4 | SETUP_FORMING | in_sample | 42,662 | -0.003% | [-0.009%, 0.002%] | 42.6% | 42,662 |
| 5 | 4 | SETUP_FORMING | held_out | 16,432 | 0.020% | [0.005%, 0.035%] | 40.2% | 16,432 |
| 5 | 5 | SETUP_FORMING | in_sample | 42,662 | -0.003% | [-0.009%, 0.003%] | 47.4% | 42,662 |
| 5 | 5 | SETUP_FORMING | held_out | 16,432 | 0.023% | [0.007%, 0.040%] | 44.9% | 16,432 |
| 5 | 1 | ALL | in_sample | 74,452 | -0.001% | [-0.003%, 0.001%] | 13.0% | 42,662 |
| 5 | 1 | ALL | held_out | 31,913 | 0.007% | [0.001%, 0.012%] | 12.5% | 16,432 |
| 5 | 2 | ALL | in_sample | 74,452 | -0.001% | [-0.004%, 0.002%] | 26.5% | 42,662 |
| 5 | 2 | ALL | held_out | 31,913 | 0.014% | [0.006%, 0.021%] | 25.0% | 16,432 |
| 5 | 3 | ALL | in_sample | 74,452 | -0.002% | [-0.006%, 0.002%] | 35.9% | 42,662 |
| 5 | 3 | ALL | held_out | 31,913 | 0.021% | [0.011%, 0.030%] | 33.9% | 16,432 |
| 5 | 4 | ALL | in_sample | 74,452 | -0.003% | [-0.007%, 0.001%] | 42.6% | 42,662 |
| 5 | 4 | ALL | held_out | 31,913 | 0.027% | [0.016%, 0.038%] | 40.2% | 16,432 |
| 5 | 5 | ALL | in_sample | 74,452 | -0.003% | [-0.008%, 0.001%] | 47.4% | 42,662 |
| 5 | 5 | ALL | held_out | 31,913 | 0.034% | [0.022%, 0.047%] | 44.9% | 16,432 |

## 4b. Forward base-rate by daily context (N=5, K=5, SETUP_FORMING only)

`daily_context` = `{daily_trend}/{daily_loc}/mkt_{daily_market_trend}` from `pattern_memory`'s daily layer, strictly prior-day. Top cells by |mean return| with at least 30 decision points (in-sample); cells below that are noise, not shown. Full per-cell data (all N, all K) is in `setup_formation_summary.json`.

| Ticker | Daily context | In-sample n | Mean fwd5 return | 95% CI | Held-out n | Held-out mean | Held-out CI |
|---|---|---|---|---|---|---|---|
| AAPL | up/near_resistance/mkt_down | 44 | 0.114% | [0.033%, 0.196%] | 170 | 0.035% | [-0.017%, 0.088%] |
| AAPL | down/mid_range/mkt_down | 477 | 0.047% | [0.016%, 0.077%] | 0 | n/a | n/a |
| AAPL | down/near_resistance/mkt_up | 1,526 | -0.038% | [-0.056%, -0.020%] | 618 | 0.046% | [0.016%, 0.077%] |
| AAPL | up/mid_range/mkt_down | 102 | 0.036% | [-0.015%, 0.087%] | 263 | 0.015% | [-0.032%, 0.062%] |
| AAPL | up/near_support/mkt_up | 2,500 | 0.030% | [0.016%, 0.044%] | 2,287 | 0.030% | [0.017%, 0.043%] |
| AAPL | up/near_support/mkt_down | 750 | 0.027% | [0.003%, 0.051%] | 43 | 0.157% | [0.049%, 0.264%] |
| AAPL | range/near_support/mkt_up | 3,350 | 0.021% | [0.009%, 0.032%] | 967 | -0.004% | [-0.026%, 0.018%] |
| AAPL | range/mid_range/mkt_up | 1,535 | -0.018% | [-0.033%, -0.002%] | 0 | n/a | n/a |
| NKE | up/mid_range/mkt_down | 320 | -0.047% | [-0.123%, 0.029%] | 0 | n/a | n/a |
| NKE | up/near_support/mkt_down | 831 | 0.043% | [0.012%, 0.073%] | 613 | -0.052% | [-0.094%, -0.010%] |
| NKE | up/near_resistance/mkt_up | 5,413 | -0.018% | [-0.034%, -0.003%] | 2,295 | -0.015% | [-0.036%, 0.005%] |
| NKE | range/mid_range/mkt_up | 1,639 | 0.018% | [-0.007%, 0.043%] | 0 | n/a | n/a |
| NKE | down/near_resistance/mkt_up | 3,505 | 0.014% | [-0.007%, 0.035%] | 3,059 | 0.002% | [-0.016%, 0.020%] |
| NKE | range/near_resistance/mkt_down | 1,935 | -0.012% | [-0.037%, 0.013%] | 1,550 | -0.041% | [-0.081%, -0.001%] |
| NKE | down/near_support/mkt_down | 3,055 | 0.012% | [-0.006%, 0.029%] | 217 | 0.049% | [-0.014%, 0.112%] |
| NKE | up/near_support/mkt_up | 3,849 | -0.011% | [-0.026%, 0.004%] | 2,877 | 0.007% | [-0.020%, 0.034%] |
| INTC | down/mid_range/mkt_up | 49 | 0.398% | [-0.196%, 0.992%] | 305 | 0.228% | [0.043%, 0.412%] |
| INTC | down/mid_range/mkt_down | 85 | 0.227% | [0.094%, 0.361%] | 0 | n/a | n/a |
| INTC | range/near_support/mkt_down | 1,892 | 0.047% | [0.016%, 0.077%] | 894 | -0.024% | [-0.091%, 0.043%] |
| INTC | up/near_support/mkt_up | 5,963 | -0.028% | [-0.054%, -0.002%] | 2,286 | 0.068% | [0.022%, 0.113%] |
| INTC | up/near_resistance/mkt_down | 747 | 0.018% | [-0.023%, 0.059%] | 294 | -0.079% | [-0.208%, 0.050%] |
| INTC | up/near_resistance/mkt_up | 4,132 | -0.013% | [-0.028%, 0.002%] | 1,989 | 0.036% | [-0.015%, 0.087%] |
| INTC | down/near_resistance/mkt_up | 4,665 | 0.012% | [-0.003%, 0.027%] | 1,098 | 0.036% | [-0.018%, 0.089%] |
| INTC | down/near_support/mkt_up | 4,437 | -0.012% | [-0.027%, 0.003%] | 516 | 0.114% | [0.041%, 0.188%] |

## 5. In-sample vs. held-out stability (the honesty check)

Per (ticker, N, K) for SETUP_FORMING: does the held-out mean-return 95% CI overlap the in-sample CI? This is the test of whether the base rate is stable out-of-sample, not whether it merely exists in-sample. `LOW-N` cells (n < 30) are flagged as too small to draw conclusions from rather than scored.

| Ticker | N | K | In-sample n | Held-out n | Stability |
|---|---|---|---|---|---|
| AAPL | 2 | 1 | 27,349 | 11,535 | stable (CIs overlap) |
| AAPL | 2 | 2 | 27,349 | 11,535 | stable (CIs overlap) |
| AAPL | 2 | 3 | 27,349 | 11,535 | stable (CIs overlap) |
| AAPL | 2 | 4 | 27,349 | 11,535 | stable (CIs overlap) |
| AAPL | 2 | 5 | 27,349 | 11,535 | stable (CIs overlap) |
| AAPL | 3 | 1 | 28,016 | 11,777 | stable (CIs overlap) |
| AAPL | 3 | 2 | 28,016 | 11,777 | stable (CIs overlap) |
| AAPL | 3 | 3 | 28,016 | 11,777 | stable (CIs overlap) |
| AAPL | 3 | 4 | 28,016 | 11,777 | stable (CIs overlap) |
| AAPL | 3 | 5 | 28,016 | 11,777 | stable (CIs overlap) |
| AAPL | 4 | 1 | 28,132 | 11,822 | stable (CIs overlap) |
| AAPL | 4 | 2 | 28,132 | 11,822 | stable (CIs overlap) |
| AAPL | 4 | 3 | 28,132 | 11,822 | stable (CIs overlap) |
| AAPL | 4 | 4 | 28,132 | 11,822 | stable (CIs overlap) |
| AAPL | 4 | 5 | 28,132 | 11,822 | stable (CIs overlap) |
| AAPL | 5 | 1 | 28,205 | 11,842 | stable (CIs overlap) |
| AAPL | 5 | 2 | 28,205 | 11,842 | stable (CIs overlap) |
| AAPL | 5 | 3 | 28,205 | 11,842 | stable (CIs overlap) |
| AAPL | 5 | 4 | 28,205 | 11,842 | stable (CIs overlap) |
| AAPL | 5 | 5 | 28,205 | 11,842 | stable (CIs overlap) |
| NKE | 2 | 1 | 41,612 | 17,547 | stable (CIs overlap) |
| NKE | 2 | 2 | 41,612 | 17,547 | stable (CIs overlap) |
| NKE | 2 | 3 | 41,612 | 17,547 | stable (CIs overlap) |
| NKE | 2 | 4 | 41,612 | 17,547 | stable (CIs overlap) |
| NKE | 2 | 5 | 41,612 | 17,547 | stable (CIs overlap) |
| NKE | 3 | 1 | 43,252 | 17,950 | stable (CIs overlap) |
| NKE | 3 | 2 | 43,252 | 17,950 | stable (CIs overlap) |
| NKE | 3 | 3 | 43,252 | 17,950 | stable (CIs overlap) |
| NKE | 3 | 4 | 43,252 | 17,950 | stable (CIs overlap) |
| NKE | 3 | 5 | 43,252 | 17,950 | stable (CIs overlap) |
| NKE | 4 | 1 | 44,047 | 18,109 | stable (CIs overlap) |
| NKE | 4 | 2 | 44,047 | 18,109 | stable (CIs overlap) |
| NKE | 4 | 3 | 44,047 | 18,109 | stable (CIs overlap) |
| NKE | 4 | 4 | 44,047 | 18,109 | stable (CIs overlap) |
| NKE | 4 | 5 | 44,047 | 18,109 | stable (CIs overlap) |
| NKE | 5 | 1 | 44,534 | 18,177 | stable (CIs overlap) |
| NKE | 5 | 2 | 44,534 | 18,177 | stable (CIs overlap) |
| NKE | 5 | 3 | 44,534 | 18,177 | stable (CIs overlap) |
| NKE | 5 | 4 | 44,534 | 18,177 | stable (CIs overlap) |
| NKE | 5 | 5 | 44,534 | 18,177 | stable (CIs overlap) |
| INTC | 2 | 1 | 41,625 | 16,169 | stable (CIs overlap) |
| INTC | 2 | 2 | 41,625 | 16,169 | stable (CIs overlap) |
| INTC | 2 | 3 | 41,625 | 16,169 | SHIFTED (CIs do not overlap) |
| INTC | 2 | 4 | 41,625 | 16,169 | SHIFTED (CIs do not overlap) |
| INTC | 2 | 5 | 41,625 | 16,169 | SHIFTED (CIs do not overlap) |
| INTC | 3 | 1 | 42,229 | 16,287 | stable (CIs overlap) |
| INTC | 3 | 2 | 42,229 | 16,287 | stable (CIs overlap) |
| INTC | 3 | 3 | 42,229 | 16,287 | SHIFTED (CIs do not overlap) |
| INTC | 3 | 4 | 42,229 | 16,287 | SHIFTED (CIs do not overlap) |
| INTC | 3 | 5 | 42,229 | 16,287 | SHIFTED (CIs do not overlap) |
| INTC | 4 | 1 | 42,511 | 16,377 | stable (CIs overlap) |
| INTC | 4 | 2 | 42,511 | 16,377 | stable (CIs overlap) |
| INTC | 4 | 3 | 42,511 | 16,377 | SHIFTED (CIs do not overlap) |
| INTC | 4 | 4 | 42,511 | 16,377 | SHIFTED (CIs do not overlap) |
| INTC | 4 | 5 | 42,511 | 16,377 | SHIFTED (CIs do not overlap) |
| INTC | 5 | 1 | 42,662 | 16,432 | stable (CIs overlap) |
| INTC | 5 | 2 | 42,662 | 16,432 | stable (CIs overlap) |
| INTC | 5 | 3 | 42,662 | 16,432 | SHIFTED (CIs do not overlap) |
| INTC | 5 | 4 | 42,662 | 16,432 | SHIFTED (CIs do not overlap) |
| INTC | 5 | 5 | 42,662 | 16,432 | SHIFTED (CIs do not overlap) |

## 6. Multiple-testing & honesty caveats

- This report computes **3 tickers x 4 N-values x 5 K-horizons x 2 states (SETUP_FORMING/ALL) x 2 portions = 240 cells** for the main curves alone, plus per-daily-context-bucket cells on top of that. At a 95% CI, ~5% of cells will show a 'significant' departure from zero by chance alone even if there is no real effect anywhere. Do not treat any single cell's CI excluding zero as a discovery -- look for a pattern that **replicates across N, across tickers, and survives the held-out split** (Section 5) before treating anything here as a real effect, and even then, this is a measurement, not a model.
- Sample sizes shrink fast once you condition on daily-context bucket *and* setup_type *and* direction simultaneously. Cells below the n=30 threshold are noise, not signal -- flagged as `LOW-N` in Section 5 and in the context-cell data (`setup_formation_summary.json`), and should not be read as a finding even if the point estimate looks dramatic.
- `hit_target` and `forward_return` are measured the same way for SETUP_FORMING and ALL, so a small gap between the two is more informative than either number in isolation -- but with mean 5m returns this close to zero, real differences this small are easily swamped by execution costs (spread, slippage) not modeled here at all.
- Daily context (`daily_trend`/`daily_loc`/`daily_market_trend`) comes from `pattern_memory`'s daily layer as of the strictly-prior trading day's close (point-in-time via `merge_asof(..., allow_exact_matches=False)`) -- it cannot leak same-day information, but it also means the very first trading day(s) of a ticker's daily history have no prior-day row to attach (rare here since daily pattern_memory predates the 5m history for all 3 tickers by ~9 years).

## 7. Scoping notes (what was reused, what wasn't, and why)

- **Candlestick detection:** `atlas_research.ta.candlesticks.detect_all_candles()` run directly against `intraday_bars` OHLC, with `eq_tol=0.0008` (the same tightened intraday tolerance `scripts/build_candle_memory.py` already uses for its own 5m candlestick layer, vs. the daily-tuned default of 0.003) and `skip_neutral=True`. No new pattern logic was written.
- **Why not query `pattern_memory`'s 5m layer directly:** it has no per-bar timestamp column for intraday rows (only `confirm_date`, a `date`), and carries 40-70+ pattern rows per ticker per single day at 5m -- there is no way to recover which specific 5-minute bar a 5m `pattern_memory` row corresponds to. This is a genuine data-model limitation, not something fixable from this script. The workaround was to recompute the *same* detector function directly from `intraday_bars`, which is PIT-safe and faithful to 'reuse what exists' at the function level, just not at the materialized-table level.
- **Chart patterns excluded:** `ta/patterns.py` (flags, head & shoulders, double top/bottom) and `structure.swing_pivots` require several confirmed swing pivots (3 for flags, 5 for H&S) which structurally cannot exist inside a 2-5 bar window. Using them here would have meant inventing new shrunk-down pattern logic, which the task brief explicitly forbids.
- **Daily context source:** `pattern_memory` (`timeframe='daily'`) directly, matching the task's literal instruction, rather than `prediction_outcomes`. It has dense coverage (~3,000 rows per ticker, full history) with the directly relevant fields (`trend`, `market_trend`, `dist_support`, `dist_resistance`).
- **Forward outcome target:** ±1x ATR(14) move within [T+1, T+K], in the row's classified `direction`. `hit_target` is `NULL` (excluded from hit-rate stats) for NEUTRAL/FLAT rows and any SETUP_FORMING row with no directional thesis (doesn't currently occur -- every SETUP_FORMING path assigns a direction -- but left as a safety case).

## 8. Verdict

**Plain answer: no clear difference across N. Longer formation windows (N=4, N=5) do not produce more, clearer, or more stable forming-setups than short ones (N=2) -- on every axis measured, N=2 and N=5 look the same.**

- **Forming rate is essentially flat across N.** SETUP_FORMING fires on ~55-60% of decision points for all three tickers at every N from 2 to 5, drifting up by only 1-4 percentage points from N=2 to N=5 (e.g. AAPL in-sample 58.1% -> 60.0%, INTC 55.9% -> 57.3%). The thing that visibly changes with N -- FLAT shrinking sharply (AAPL in-sample 2.0% at N=2 down to 0.2% at N=5) -- is a mechanical artifact of the FLAT rule (mean range/ATR over the whole window must stay below threshold), not evidence that "more structure becomes visible" at longer N: a single normal-sized candle anywhere in a longer window is enough to disqualify it from FLAT, so FLAT mechanically gets rarer as N grows regardless of what the market is doing. Setup-type composition is also nearly invariant across N=3,4,5, which is expected given the candlestick detector's max pattern span is 3 bars -- N=3,4,5 are functionally the same trigger for pattern-based calls.

- **SETUP_FORMING does not separate from the unconditional baseline.** Comparing SETUP_FORMING's mean forward return against the ALL (unconditional) baseline at matched (ticker, N, K) in Section 4, the two are statistically indistinguishable in nearly every cell -- CIs overlap heavily, and point estimates differ by hundredths of a percent (e.g. AAPL N=2,K=5 in-sample: SETUP_FORMING +0.005% vs ALL +0.006%). NKE's SETUP_FORMING return is, if anything, slightly *more* negative than ALL in several held-out cells. There is no (ticker, N) combination where SETUP_FORMING shows a forward edge that ALL doesn't also show. (Note: the hit-rate columns in Section 4 can't be used for this comparison at all -- see the caveat added above the Section 4 table -- only the mean-return columns are a real baseline check, and they show the same null result.)

- **N=2 vs N=5 curves are nearly identical for the same ticker/K.** There is no sense in which the longer window is "cleaner" -- e.g. AAPL N=2,K=5 in-sample mean return +0.005% vs N=5,K=5 in-sample +0.004%; same story for NKE and INTC. If a 4-5 candle structure carried more forward information than a 2-candle one, this is where it would show up, and it doesn't.

- **In-sample vs. held-out stability (Section 5) is good for AAPL/NKE, but it's stability toward "no effect," not toward a real edge.** Every (N,K) cell for AAPL and NKE is flagged "stable (CIs overlap)" -- the null result replicates cleanly out-of-sample rather than being an in-sample fluke.

- **INTC's apparent instability (SHIFTED at K=3,4,5, all N) is a baseline-level regime artifact, not a classifier problem.** INTC's held-out portion shows a sign flip (in-sample slightly negative -> held-out slightly positive forward returns), which looks at first like the classifier degrading out-of-sample. But the *same* sign flip, of similar magnitude, appears in INTC's unconditional ALL baseline over the identical split (e.g. N=2,K=5: SETUP_FORMING in-sample -0.003% -> held-out +0.026%; ALL in-sample -0.003% -> held-out +0.034%). That means the shift affects every decision point in INTC's held-out window equally, conditioned or not -- consistent with INTC simply having a different short-term drift regime in its later 30% of history than its earlier 70% (unsurprising for the name picked specifically for *not* having a persistent, resolving trend). This is a property of INTC's price series, not evidence that SETUP_FORMING calls became less reliable.

- **The daily-context breakdown (Section 4b) is consistent with the multiple-testing caveat in Section 6, not a discovery.** Across the ~24 reported (ticker x daily_context x K=5,N=5) cells, exactly one -- AAPL's `up / near_support / mkt_up` -- shows a same-signed, non-zero-excluding CI in both in-sample (n=2,500, +0.030%, CI[0.016%,0.044%]) and held-out (n=2,287, +0.030%, CI[0.017%,0.043%]). Several other cells sign-flip entirely between portions (e.g. AAPL `down/near_resistance/mkt_up` goes from -0.038% in-sample to +0.046% held-out; INTC `up/near_support/mkt_up` flips from -0.028% to +0.068%). One robust-looking cell out of ~24 is exactly what you'd expect from chance at a ~5% false-positive rate -- it is not, on its own, evidence of a real conditional effect, though it would be a reasonable specific hypothesis to test against fresh data if anyone wanted to follow up.

**Bottom line:** this measurement is an honest null. The mechanical classifier built from existing candlestick/geometry detectors fires on a majority of all decision points (55-60%) regardless of N, its forward base rate is not distinguishable from doing nothing, and there is no N-dependence in either the forming rate or the forward outcome curves. The task brief states a flat/null result is an acceptable, valid outcome to report rather than something to tune away -- that is what was found here, and nothing in this dataset should be read as a signal worth acting on.

## 9. Reproducibility

- Full per-cell aggregates: `reports/research/setup_formation_summary.json` (run `20260621T163148Z-16c317bb`)
- Run parameters/thresholds: `reports/research/setup_formation_run_log.jsonl` (same `run_id`)
- Raw rows: `research_setup_formation` table, `WHERE run_id = '20260621T163148Z-16c317bb'`
- Example annotated charts: `reports/research/charts/`
- Thresholds used this run:
  - `FLAT_RANGE_ATR_MULT` = 0.5
  - `FLAT_VOL_RATIO_MAX` = 0.7
  - `GEOM_BODY_PCT_MIN` = 60.0
  - `GEOM_SIZE_ATR_MULT` = 1.2
  - `SR_NEAR_TOL` = 0.03
  - `ATR_HIT_MULT` = 1.0
  - `FORWARD_RETURN_FLAT_EPS` = 0.02
  - `TRAIN_FRACTION` = 0.7
  - `MIN_CELL_N` = 30
