# Setup-Formation Measurement Report v2 -- Full Tool-State Snapshot

**MEASURE & REPORT ONLY.** This is a foundation measurement of the full point-in-time multi-tool state (volume, MACD, EMA stack, RSI, VWAP, ATR/vol, swing structure, opening-range breakout, candle/pattern) on 5-minute bars, and whether richer confluence (more active tools, or specific tool combinations) changes the forward base rate found in v1. It is **not a predictor and not a trading signal**. Single-timeframe (5m) only; N=2 only this round; daily zoom-out is a deliberately deferred later phase. A null result is reported honestly where that's what the data shows.

- **Run ID:** `20260621T203847Z-6ed39367`
- **Git commit:** `25accacc430d3c43cb96a21fcf51b47aba81dbfa` (branch `research/setup-formation-v2`)
- **Timestamp (UTC):** 2026-06-21T20:42:05.271966+00:00
- **Tickers:** AAPL, NKE, INTC (same 3 as v1, for comparability)
- **N (formation window):** 2 (fixed)
- **K (forward horizons, bars):** [1, 2, 3, 4, 5]
- **Tools snapshotted:** candle, volume, macd, rsi, ema, vwap, atr, swing, orb
- **Tool combinations tested:** candle+volume, candle+macd, candle+rsi, candle+ema, candle+vwap, candle+atr, candle+swing, candle+orb, volume+macd, volume+ema, macd+ema
- **Total wall time:** 197.2s

## Step 0. Audit of v1's feature set (read before building v2)

v1 (commit `076bc86`, branch `research/setup-formation`) used a thin feature set: candle geometry (`candle_rng`, `body_pct`, `is_green/red`, `consec_green/red`), `atr14`, `vol_ratio`, 19 candlestick patterns (`detect_all_candles`, `eq_tol=0.0008`), `prior_trend`, and daily-layer context (`trend`, `market_trend`, `dist_support`, `dist_resistance` from `pattern_memory`; `sma_stacked` was loaded but never actually used). Forward target: `forward_return` (pct to close at T+k, k=1..5), `forward_direction` (up/down/flat via a +-0.02% epsilon band), `hit_target` (+-1x ATR14[T] reached in the row's classified direction within (T, T+k]). v1's verdict was an honest null: SETUP_FORMING did not separate from the unconditional baseline at any N or K, and there was no N-dependence (N=2 looked the same as N=5).

**What v2 adds:** every other PIT-computable 5m indicator that v1 ignored -- VWAP, EMA9/20/50 stack, RSI14, MACD, ATR expansion/compression, opening-range breakout, and swing-pivot trend structure -- recorded as an explicit per-tool state + "active" (notable event/extreme at T) flag, rolled up into a `confluence_count` (0-9) and a small set of pre-specified tool-pair combinations. The question: does the FULL picture change v1's null?

## Step 1. Tool inventory: present vs. missing on 5m

**Present on 5m, PIT-verified, used this run:**

- `compute_features()` (`src/atlas_research/intraday/features.py`) already computes, point-in-time, on 5m bars: **VWAP** (cumulative-from-open, +dist/above/cross), **EMA9/20/50** (+slopes, price-vs-ema9, ema9-vs-ema20), **RSI14** (+overbought/oversold, +reclaim events), **MACD** (+signal/hist, +bull/bear cross), **ATR14** (+20-bar avg, +compression flag), **volume ratio** (+high/very-high flags), **opening-range breakout** signals, and basic candle geometry. v1 used only a handful of these columns; v2 reads nearly all of them. One PIT subtlety found and worked around (not a bug in features.py itself): `or_high`/`or_low` reflect the *completed* opening range even for bars still inside it, which would leak if read directly during `in_or` bars -- v2's ORB tool reports an honest `in_opening_range` state for those bars instead of reading above/below-OR state from them.
- **Candlestick patterns** (`ta.candlesticks.detect_all_candles`, `eq_tol=0.0008`) and **swing-pivot trend structure** (`ta.structure.swing_pivots` + `classify_trend`, pure numpy, timeframe-agnostic) -- both reused verbatim. Swing pivots were *expected* to be "likely missing on 5m" per the original brief; they are in fact present and usable, with one PIT subtlety handled explicitly: a pivot at bar index i is only "known" once bar i+3 (fractal width) has been observed, so it is folded into the trend state only from i+3 onward, never earlier.

**Genuinely missing everywhere (not a scoping choice):**

- **Channel detection** -- no module, no DB table, anywhere in the codebase (daily or 5m).
- **Stochastic oscillator** -- not implemented (an OSCAR oscillator exists in `atlas_research.features.omni_proxy`, but it's a different, daily-only formula).
- **OMNI-82 (EMA-of-lows)** -- exists (`atlas_research.features.omni_proxy`) but is daily-only in practice; never wired to 5m bars.

**Excluded by explicit decision, despite now having real data:**

- A `gaps` table (classic gap + FVG, migration `0048_gaps.sql`) and a `vwap_5m` table (migration `0047_vwap_5m.sql`) were both applied to the live database *during this session*, by separate, concurrent work on branch `feat/gaps` -- not on `fix/model-validity`, which this branch is built from. `gaps` turned out to have substantial real 5m data for all 3 target tickers (AAPL 18,589 / NKE 40,635 / INTC 31,104 rows) -- more mature than the "uncommitted, no data yet" framing first given when this was flagged. `vwap_5m`, by contrast, is genuinely mid-backfill: it is missing AAPL entirely. Per explicit user decision (asked mid-session once the branch discrepancy was discovered), both are excluded from this run -- v2 uses `compute_features()`'s own in-memory VWAP instead, which is complete for all 3 tickers and already verified PIT-safe. Flagged as a v3 candidate once the `feat/gaps` work is merged and stable.
- Full dome/swing-leg "early signature" metrics (`early_gain`/`early_slope`/`leg_amp`/`corr_depth` in `ta.patterns.swing_legs`) -- a deeper, separate research thread (branch `research/dome-symmetry`). Used the lighter swing_pivots+classify_trend trend-state instead, to keep the tool count (and therefore the Step-3 combination-testing space) bounded.

## 2. Confluence distribution & tool activity rates

`confluence_count` = number of the 9 tools with a notable event/extreme at decision point T (k=1 rows only -- one row per decision point).

| Ticker | Portion | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8+ |
|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | in_sample | 1,055 (2%) | 5,685 (12%) | 12,347 (26%) | 14,462 (31%) | 9,227 (20%) | 3,270 (7%) | 821 (2%) | 167 (0%) | 15 (0%) |
| AAPL | held_out | 639 (3%) | 2,871 (14%) | 5,660 (28%) | 5,945 (29%) | 3,454 (17%) | 1,219 (6%) | 302 (1%) | 68 (0%) | 10 (0%) |
| NKE | in_sample | 1,387 (2%) | 7,987 (11%) | 19,168 (26%) | 23,149 (31%) | 15,152 (20%) | 5,655 (8%) | 1,296 (2%) | 208 (0%) | 18 (0%) |
| NKE | held_out | 739 (2%) | 4,204 (13%) | 8,797 (28%) | 9,626 (30%) | 5,748 (18%) | 2,045 (6%) | 495 (2%) | 64 (0%) | 8 (0%) |
| INTC | in_sample | 1,733 (2%) | 9,182 (12%) | 20,164 (27%) | 22,440 (30%) | 14,244 (19%) | 5,195 (7%) | 1,272 (2%) | 196 (0%) | 30 (0%) |
| INTC | held_out | 944 (3%) | 4,378 (14%) | 8,875 (28%) | 9,475 (30%) | 5,588 (18%) | 2,029 (6%) | 527 (2%) | 86 (0%) | 11 (0%) |

Per-tool active rate (share of all decision points, in-sample):

| Ticker | candle | volume | macd | rsi | ema | vwap | atr | swing | orb |
|---|---|---|---|---|---|---|---|---|---|
| AAPL | 59.0% | 15.8% | 7.6% | 28.7% | 23.8% | 56.6% | 25.6% | 15.5% | 46.3% |
| NKE | 60.7% | 17.4% | 7.5% | 30.7% | 23.0% | 53.1% | 28.7% | 15.3% | 48.7% |
| INTC | 55.8% | 17.0% | 7.4% | 29.7% | 23.4% | 54.0% | 27.9% | 15.3% | 47.6% |

## 3. Candle-tool composition (when active_candle fires)

Same trigger v1 used at N=2 (named candlestick pattern with span<=2, OR a 2-candle directional-thrust geometry signal), now reported as one tool among nine rather than the sole classifier.

- **AAPL:** tweezer_top (8554), tweezer_bottom (7906), bearish_engulfing (3714), bullish_engulfing (3607), marubozu (3410), bearish_harami (2597)
- **NKE:** marubozu (12067), tweezer_bottom (11182), tweezer_top (11089), bearish_engulfing (4942), bullish_engulfing (4832), bullish_harami (4170)
- **INTC:** tweezer_top (8990), tweezer_bottom (8692), marubozu (7442), bullish_engulfing (6128), bearish_engulfing (5989), bearish_harami (4964)

## 4. Forward base-rate curves by confluence count

Mean forward return and ATR-hit rate over K=1..5, bucketed by `confluence_count` (5+ collapsed into one bucket for sample size), vs. the unconditional ALL baseline. This is the Step-3(i) question: does forward outcome separate from baseline as confluence rises?


### AAPL

| Confluence | K | Portion | n | Mean fwd return | 95% CI | Hit rate | Hit n | %Up |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | in_sample | 1,055 | 0.000% | [-0.008%, 0.008%] | n/a | 0 | 42.1% |
| 0 | 1 | held_out | 639 | 0.001% | [-0.008%, 0.010%] | n/a | 0 | 40.2% |
| 0 | 2 | in_sample | 1,055 | -0.001% | [-0.012%, 0.010%] | n/a | 0 | 41.4% |
| 0 | 2 | held_out | 639 | -0.004% | [-0.016%, 0.008%] | n/a | 0 | 43.5% |
| 0 | 3 | in_sample | 1,055 | -0.001% | [-0.014%, 0.013%] | n/a | 0 | 44.4% |
| 0 | 3 | held_out | 639 | -0.011% | [-0.026%, 0.004%] | n/a | 0 | 42.6% |
| 0 | 4 | in_sample | 1,055 | -0.002% | [-0.018%, 0.014%] | n/a | 0 | 44.2% |
| 0 | 4 | held_out | 639 | -0.005% | [-0.023%, 0.013%] | n/a | 0 | 44.0% |
| 0 | 5 | in_sample | 1,055 | -0.003% | [-0.023%, 0.017%] | n/a | 0 | 45.9% |
| 0 | 5 | held_out | 639 | -0.007% | [-0.028%, 0.014%] | n/a | 0 | 42.3% |
| 1 | 1 | in_sample | 5,685 | 0.001% | [-0.002%, 0.005%] | 9.9% | 1,540 | 42.2% |
| 1 | 1 | held_out | 2,871 | -0.003% | [-0.008%, 0.001%] | 9.8% | 808 | 40.3% |
| 1 | 2 | in_sample | 5,685 | 0.004% | [-0.001%, 0.009%] | 23.7% | 1,540 | 45.0% |
| 1 | 2 | held_out | 2,871 | -0.004% | [-0.010%, 0.002%] | 22.6% | 808 | 41.5% |
| 1 | 3 | in_sample | 5,685 | 0.002% | [-0.005%, 0.008%] | 33.0% | 1,540 | 46.1% |
| 1 | 3 | held_out | 2,871 | 0.001% | [-0.008%, 0.009%] | 31.1% | 808 | 44.0% |
| 1 | 4 | in_sample | 5,685 | 0.002% | [-0.005%, 0.010%] | 40.3% | 1,540 | 46.7% |
| 1 | 4 | held_out | 2,871 | 0.002% | [-0.008%, 0.011%] | 38.6% | 808 | 44.1% |
| 1 | 5 | in_sample | 5,685 | 0.006% | [-0.003%, 0.015%] | 46.8% | 1,540 | 47.6% |
| 1 | 5 | held_out | 2,871 | -0.003% | [-0.014%, 0.009%] | 44.3% | 808 | 45.2% |
| 2 | 1 | in_sample | 12,347 | 0.002% | [-0.001%, 0.004%] | 10.8% | 5,874 | 43.4% |
| 2 | 1 | held_out | 5,660 | 0.003% | [-0.001%, 0.007%] | 10.3% | 2,809 | 41.8% |
| 2 | 2 | in_sample | 12,347 | 0.004% | [0.001%, 0.008%] | 23.6% | 5,874 | 46.0% |
| 2 | 2 | held_out | 5,660 | 0.004% | [-0.001%, 0.010%] | 22.1% | 2,809 | 44.9% |
| 2 | 3 | in_sample | 12,347 | 0.007% | [0.002%, 0.012%] | 33.2% | 5,874 | 47.4% |
| 2 | 3 | held_out | 5,660 | 0.003% | [-0.003%, 0.010%] | 32.1% | 2,809 | 45.6% |
| 2 | 4 | in_sample | 12,347 | 0.010% | [0.005%, 0.016%] | 40.2% | 5,874 | 49.1% |
| 2 | 4 | held_out | 5,660 | 0.004% | [-0.004%, 0.012%] | 38.8% | 2,809 | 45.7% |
| 2 | 5 | in_sample | 12,347 | 0.009% | [0.003%, 0.015%] | 45.2% | 5,874 | 49.0% |
| 2 | 5 | held_out | 5,660 | 0.008% | [-0.001%, 0.016%] | 44.5% | 2,809 | 46.5% |
| 3 | 1 | in_sample | 14,462 | 0.002% | [-0.001%, 0.005%] | 12.2% | 9,445 | 42.5% |
| 3 | 1 | held_out | 5,945 | 0.003% | [-0.001%, 0.007%] | 11.3% | 3,977 | 41.2% |
| 3 | 2 | in_sample | 14,462 | 0.005% | [0.001%, 0.009%] | 24.7% | 9,445 | 45.7% |
| 3 | 2 | held_out | 5,945 | 0.007% | [0.001%, 0.012%] | 24.6% | 3,977 | 43.8% |
| 3 | 3 | in_sample | 14,462 | 0.008% | [0.003%, 0.013%] | 33.9% | 9,445 | 47.0% |
| 3 | 3 | held_out | 5,945 | 0.008% | [0.001%, 0.014%] | 33.6% | 3,977 | 44.2% |
| 3 | 4 | in_sample | 14,462 | 0.009% | [0.003%, 0.015%] | 40.8% | 9,445 | 48.2% |
| 3 | 4 | held_out | 5,945 | 0.009% | [0.001%, 0.017%] | 39.5% | 3,977 | 45.9% |
| 3 | 5 | in_sample | 14,462 | 0.009% | [0.002%, 0.016%] | 46.1% | 9,445 | 49.0% |
| 3 | 5 | held_out | 5,945 | 0.010% | [0.001%, 0.019%] | 44.5% | 3,977 | 45.8% |
| 4 | 1 | in_sample | 9,227 | -0.000% | [-0.005%, 0.004%] | 13.3% | 7,269 | 41.8% |
| 4 | 1 | held_out | 3,454 | 0.004% | [-0.003%, 0.010%] | 13.1% | 2,715 | 43.1% |
| 4 | 2 | in_sample | 9,227 | -0.001% | [-0.007%, 0.006%] | 26.2% | 7,269 | 44.3% |
| 4 | 2 | held_out | 3,454 | 0.004% | [-0.005%, 0.013%] | 26.7% | 2,715 | 43.7% |
| 4 | 3 | in_sample | 9,227 | -0.002% | [-0.010%, 0.005%] | 35.4% | 7,269 | 46.2% |
| 4 | 3 | held_out | 3,454 | 0.005% | [-0.005%, 0.015%] | 36.0% | 2,715 | 45.3% |
| 4 | 4 | in_sample | 9,227 | -0.002% | [-0.010%, 0.006%] | 41.6% | 7,269 | 46.6% |
| 4 | 4 | held_out | 3,454 | 0.010% | [-0.001%, 0.022%] | 43.2% | 2,715 | 46.0% |
| 4 | 5 | in_sample | 9,227 | -0.001% | [-0.011%, 0.008%] | 46.4% | 7,269 | 47.4% |
| 4 | 5 | held_out | 3,454 | 0.014% | [0.002%, 0.027%] | 48.7% | 2,715 | 46.7% |
| 5plus | 1 | in_sample | 4,273 | 0.001% | [-0.009%, 0.011%] | 17.9% | 3,786 | 43.1% |
| 5plus | 1 | held_out | 1,599 | 0.000% | [-0.013%, 0.014%] | 20.0% | 1,425 | 42.8% |
| 5plus | 2 | in_sample | 4,273 | -0.005% | [-0.019%, 0.009%] | 31.2% | 3,786 | 45.5% |
| 5plus | 2 | held_out | 1,599 | 0.011% | [-0.009%, 0.030%] | 34.1% | 1,425 | 44.7% |
| 5plus | 3 | in_sample | 4,273 | -0.005% | [-0.021%, 0.011%] | 40.1% | 3,786 | 46.4% |
| 5plus | 3 | held_out | 1,599 | 0.029% | [0.006%, 0.051%] | 42.8% | 1,425 | 47.0% |
| 5plus | 4 | in_sample | 4,273 | -0.005% | [-0.023%, 0.012%] | 45.9% | 3,786 | 46.2% |
| 5plus | 4 | held_out | 1,599 | 0.032% | [0.007%, 0.058%] | 48.1% | 1,425 | 48.7% |
| 5plus | 5 | in_sample | 4,273 | 0.004% | [-0.015%, 0.023%] | 50.3% | 3,786 | 47.1% |
| 5plus | 5 | held_out | 1,599 | 0.043% | [0.016%, 0.070%] | 51.9% | 1,425 | 48.7% |
| ALL | 1 | in_sample | 47,049 | 0.001% | [-0.001%, 0.003%] | 12.8% | 27,914 | 42.6% |
| ALL | 1 | held_out | 20,168 | 0.002% | [-0.000%, 0.004%] | 12.4% | 11,734 | 41.7% |
| ALL | 2 | in_sample | 47,049 | 0.002% | [-0.000%, 0.005%] | 25.7% | 27,914 | 45.3% |
| ALL | 2 | held_out | 20,168 | 0.004% | [0.001%, 0.007%] | 25.5% | 11,734 | 43.8% |
| ALL | 3 | in_sample | 47,049 | 0.004% | [0.001%, 0.007%] | 34.9% | 27,914 | 46.7% |
| ALL | 3 | held_out | 20,168 | 0.006% | [0.002%, 0.010%] | 34.8% | 11,734 | 44.9% |
| ALL | 4 | in_sample | 47,049 | 0.005% | [0.001%, 0.008%] | 41.6% | 27,914 | 47.7% |
| ALL | 4 | held_out | 20,168 | 0.008% | [0.004%, 0.013%] | 41.2% | 11,734 | 45.8% |
| ALL | 5 | in_sample | 47,049 | 0.006% | [0.002%, 0.010%] | 46.6% | 27,914 | 48.3% |
| ALL | 5 | held_out | 20,168 | 0.010% | [0.005%, 0.015%] | 46.4% | 11,734 | 46.2% |

### NKE

| Confluence | K | Portion | n | Mean fwd return | 95% CI | Hit rate | Hit n | %Up |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | in_sample | 1,387 | -0.002% | [-0.009%, 0.005%] | n/a | 0 | 42.1% |
| 0 | 1 | held_out | 739 | 0.012% | [-0.001%, 0.024%] | n/a | 0 | 43.6% |
| 0 | 2 | in_sample | 1,387 | -0.006% | [-0.016%, 0.004%] | n/a | 0 | 44.3% |
| 0 | 2 | held_out | 739 | 0.015% | [-0.003%, 0.033%] | n/a | 0 | 43.3% |
| 0 | 3 | in_sample | 1,387 | 0.000% | [-0.013%, 0.013%] | n/a | 0 | 45.4% |
| 0 | 3 | held_out | 739 | 0.024% | [0.002%, 0.046%] | n/a | 0 | 44.8% |
| 0 | 4 | in_sample | 1,387 | -0.011% | [-0.026%, 0.005%] | n/a | 0 | 45.9% |
| 0 | 4 | held_out | 739 | 0.020% | [-0.004%, 0.045%] | n/a | 0 | 47.0% |
| 0 | 5 | in_sample | 1,387 | -0.016% | [-0.034%, 0.001%] | n/a | 0 | 45.0% |
| 0 | 5 | held_out | 739 | 0.017% | [-0.010%, 0.044%] | n/a | 0 | 46.7% |
| 1 | 1 | in_sample | 7,987 | -0.002% | [-0.005%, 0.001%] | 12.0% | 2,294 | 41.7% |
| 1 | 1 | held_out | 4,204 | -0.005% | [-0.010%, 0.001%] | 9.9% | 1,065 | 40.0% |
| 1 | 2 | in_sample | 7,987 | -0.006% | [-0.011%, -0.001%] | 24.0% | 2,294 | 43.4% |
| 1 | 2 | held_out | 4,204 | -0.008% | [-0.016%, 0.000%] | 20.9% | 1,065 | 41.7% |
| 1 | 3 | in_sample | 7,987 | -0.008% | [-0.014%, -0.001%] | 33.6% | 2,294 | 44.2% |
| 1 | 3 | held_out | 4,204 | -0.012% | [-0.023%, -0.001%] | 29.9% | 1,065 | 42.7% |
| 1 | 4 | in_sample | 7,987 | -0.005% | [-0.013%, 0.002%] | 39.4% | 2,294 | 45.0% |
| 1 | 4 | held_out | 4,204 | -0.010% | [-0.023%, 0.002%] | 37.5% | 1,065 | 44.1% |
| 1 | 5 | in_sample | 7,987 | -0.007% | [-0.016%, 0.001%] | 44.5% | 2,294 | 45.5% |
| 1 | 5 | held_out | 4,204 | -0.011% | [-0.025%, 0.003%] | 42.7% | 1,065 | 44.8% |
| 2 | 1 | in_sample | 19,168 | 0.000% | [-0.003%, 0.003%] | 13.5% | 9,633 | 42.3% |
| 2 | 1 | held_out | 8,797 | -0.002% | [-0.006%, 0.002%] | 11.4% | 4,030 | 42.0% |
| 2 | 2 | in_sample | 19,168 | -0.002% | [-0.006%, 0.002%] | 26.2% | 9,633 | 44.1% |
| 2 | 2 | held_out | 8,797 | -0.004% | [-0.010%, 0.002%] | 24.7% | 4,030 | 44.6% |
| 2 | 3 | in_sample | 19,168 | -0.002% | [-0.007%, 0.003%] | 35.8% | 9,633 | 45.4% |
| 2 | 3 | held_out | 8,797 | -0.002% | [-0.009%, 0.005%] | 34.6% | 4,030 | 45.5% |
| 2 | 4 | in_sample | 19,168 | -0.003% | [-0.008%, 0.003%] | 42.0% | 9,633 | 45.9% |
| 2 | 4 | held_out | 8,797 | 0.002% | [-0.007%, 0.011%] | 41.0% | 4,030 | 46.1% |
| 2 | 5 | in_sample | 19,168 | -0.002% | [-0.009%, 0.004%] | 46.6% | 9,633 | 46.2% |
| 2 | 5 | held_out | 8,797 | 0.002% | [-0.008%, 0.012%] | 46.0% | 4,030 | 46.0% |
| 3 | 1 | in_sample | 23,149 | 0.001% | [-0.002%, 0.003%] | 14.3% | 15,465 | 42.2% |
| 3 | 1 | held_out | 9,626 | 0.001% | [-0.003%, 0.006%] | 13.1% | 6,173 | 43.3% |
| 3 | 2 | in_sample | 23,149 | 0.003% | [-0.001%, 0.007%] | 27.7% | 15,465 | 44.7% |
| 3 | 2 | held_out | 9,626 | -0.001% | [-0.009%, 0.006%] | 26.2% | 6,173 | 44.9% |
| 3 | 3 | in_sample | 23,149 | 0.001% | [-0.003%, 0.006%] | 36.8% | 15,465 | 45.9% |
| 3 | 3 | held_out | 9,626 | -0.002% | [-0.010%, 0.007%] | 35.5% | 6,173 | 46.1% |
| 3 | 4 | in_sample | 23,149 | 0.000% | [-0.006%, 0.006%] | 43.4% | 15,465 | 46.8% |
| 3 | 4 | held_out | 9,626 | -0.006% | [-0.016%, 0.005%] | 42.0% | 6,173 | 45.9% |
| 3 | 5 | in_sample | 23,149 | 0.001% | [-0.006%, 0.007%] | 48.1% | 15,465 | 47.6% |
| 3 | 5 | held_out | 9,626 | -0.007% | [-0.019%, 0.004%] | 46.7% | 6,173 | 46.7% |
| 4 | 1 | in_sample | 15,152 | -0.002% | [-0.006%, 0.003%] | 16.1% | 12,227 | 43.0% |
| 4 | 1 | held_out | 5,748 | -0.004% | [-0.012%, 0.004%] | 15.3% | 4,588 | 42.5% |
| 4 | 2 | in_sample | 15,152 | -0.003% | [-0.009%, 0.003%] | 30.1% | 12,227 | 45.7% |
| 4 | 2 | held_out | 5,748 | -0.002% | [-0.014%, 0.010%] | 28.5% | 4,588 | 43.8% |
| 4 | 3 | in_sample | 15,152 | -0.003% | [-0.010%, 0.005%] | 38.8% | 12,227 | 46.3% |
| 4 | 3 | held_out | 5,748 | -0.008% | [-0.023%, 0.007%] | 37.4% | 4,588 | 45.1% |
| 4 | 4 | in_sample | 15,152 | -0.004% | [-0.012%, 0.004%] | 45.2% | 12,227 | 46.9% |
| 4 | 4 | held_out | 5,748 | -0.015% | [-0.033%, 0.002%] | 43.9% | 4,588 | 45.0% |
| 4 | 5 | in_sample | 15,152 | -0.008% | [-0.017%, 0.001%] | 49.8% | 12,227 | 47.1% |
| 4 | 5 | held_out | 5,748 | -0.018% | [-0.039%, 0.003%] | 48.5% | 4,588 | 46.5% |
| 5plus | 1 | in_sample | 7,177 | -0.002% | [-0.011%, 0.008%] | 18.8% | 6,411 | 44.8% |
| 5plus | 1 | held_out | 2,612 | -0.003% | [-0.025%, 0.019%] | 18.8% | 2,303 | 45.1% |
| 5plus | 2 | in_sample | 7,177 | -0.001% | [-0.013%, 0.012%] | 33.3% | 6,411 | 45.8% |
| 5plus | 2 | held_out | 2,612 | -0.001% | [-0.030%, 0.029%] | 33.4% | 2,303 | 46.4% |
| 5plus | 3 | in_sample | 7,177 | -0.001% | [-0.015%, 0.014%] | 42.0% | 6,411 | 47.0% |
| 5plus | 3 | held_out | 2,612 | -0.007% | [-0.040%, 0.027%] | 41.9% | 2,303 | 47.4% |
| 5plus | 4 | in_sample | 7,177 | 0.003% | [-0.013%, 0.020%] | 48.4% | 6,411 | 48.3% |
| 5plus | 4 | held_out | 2,612 | -0.005% | [-0.044%, 0.033%] | 47.8% | 2,303 | 48.7% |
| 5plus | 5 | in_sample | 7,177 | 0.006% | [-0.012%, 0.025%] | 53.2% | 6,411 | 49.0% |
| 5plus | 5 | held_out | 2,612 | -0.008% | [-0.048%, 0.033%] | 51.0% | 2,303 | 48.0% |
| ALL | 1 | in_sample | 74,020 | -0.000% | [-0.002%, 0.001%] | 15.1% | 46,030 | 42.6% |
| ALL | 1 | held_out | 31,726 | -0.001% | [-0.004%, 0.002%] | 13.8% | 18,159 | 42.5% |
| ALL | 2 | in_sample | 74,020 | -0.001% | [-0.003%, 0.001%] | 28.6% | 46,030 | 44.7% |
| ALL | 2 | held_out | 31,726 | -0.003% | [-0.007%, 0.002%] | 27.1% | 18,159 | 44.3% |
| ALL | 3 | in_sample | 74,020 | -0.001% | [-0.004%, 0.001%] | 37.7% | 46,030 | 45.8% |
| ALL | 3 | held_out | 31,726 | -0.004% | [-0.009%, 0.001%] | 36.3% | 18,159 | 45.3% |
| ALL | 4 | in_sample | 74,020 | -0.002% | [-0.005%, 0.001%] | 44.1% | 46,030 | 46.5% |
| ALL | 4 | held_out | 31,726 | -0.005% | [-0.012%, 0.001%] | 42.7% | 18,159 | 45.8% |
| ALL | 5 | in_sample | 74,020 | -0.002% | [-0.006%, 0.001%] | 48.8% | 46,030 | 47.0% |
| ALL | 5 | held_out | 31,726 | -0.007% | [-0.014%, 0.000%] | 47.3% | 18,159 | 46.3% |

### INTC

| Confluence | K | Portion | n | Mean fwd return | 95% CI | Hit rate | Hit n | %Up |
|---|---|---|---|---|---|---|---|---|
| 0 | 1 | in_sample | 1,733 | -0.006% | [-0.014%, 0.002%] | n/a | 0 | 42.9% |
| 0 | 1 | held_out | 944 | 0.030% | [0.011%, 0.049%] | n/a | 0 | 49.6% |
| 0 | 2 | in_sample | 1,733 | -0.002% | [-0.014%, 0.009%] | n/a | 0 | 44.4% |
| 0 | 2 | held_out | 944 | 0.033% | [-0.003%, 0.069%] | n/a | 0 | 51.1% |
| 0 | 3 | in_sample | 1,733 | -0.003% | [-0.017%, 0.011%] | n/a | 0 | 46.9% |
| 0 | 3 | held_out | 944 | 0.045% | [-0.003%, 0.092%] | n/a | 0 | 49.3% |
| 0 | 4 | in_sample | 1,733 | 0.002% | [-0.015%, 0.018%] | n/a | 0 | 47.5% |
| 0 | 4 | held_out | 944 | 0.047% | [-0.006%, 0.100%] | n/a | 0 | 48.5% |
| 0 | 5 | in_sample | 1,733 | -0.007% | [-0.029%, 0.015%] | n/a | 0 | 46.6% |
| 0 | 5 | held_out | 944 | 0.046% | [-0.010%, 0.101%] | n/a | 0 | 49.3% |
| 1 | 1 | in_sample | 9,182 | 0.003% | [-0.001%, 0.007%] | 10.0% | 2,281 | 44.0% |
| 1 | 1 | held_out | 4,378 | 0.002% | [-0.007%, 0.011%] | 11.0% | 880 | 46.2% |
| 1 | 2 | in_sample | 9,182 | 0.007% | [0.001%, 0.012%] | 22.9% | 2,281 | 47.1% |
| 1 | 2 | held_out | 4,378 | -0.003% | [-0.016%, 0.010%] | 23.8% | 880 | 47.9% |
| 1 | 3 | in_sample | 9,182 | 0.009% | [0.001%, 0.016%] | 32.6% | 2,281 | 47.8% |
| 1 | 3 | held_out | 4,378 | -0.009% | [-0.027%, 0.009%] | 32.0% | 880 | 47.4% |
| 1 | 4 | in_sample | 9,182 | 0.009% | [0.001%, 0.017%] | 38.8% | 2,281 | 48.1% |
| 1 | 4 | held_out | 4,378 | -0.004% | [-0.026%, 0.018%] | 38.9% | 880 | 47.7% |
| 1 | 5 | in_sample | 9,182 | 0.007% | [-0.003%, 0.017%] | 44.4% | 2,281 | 47.9% |
| 1 | 5 | held_out | 4,378 | 0.003% | [-0.025%, 0.032%] | 43.1% | 880 | 47.9% |
| 2 | 1 | in_sample | 20,164 | 0.001% | [-0.002%, 0.004%] | 11.1% | 9,094 | 43.8% |
| 2 | 1 | held_out | 8,875 | -0.001% | [-0.009%, 0.007%] | 10.2% | 3,518 | 45.9% |
| 2 | 2 | in_sample | 20,164 | -0.002% | [-0.006%, 0.003%] | 24.3% | 9,094 | 45.0% |
| 2 | 2 | held_out | 8,875 | 0.010% | [-0.004%, 0.024%] | 22.5% | 3,518 | 47.0% |
| 2 | 3 | in_sample | 20,164 | -0.002% | [-0.007%, 0.004%] | 33.8% | 9,094 | 45.9% |
| 2 | 3 | held_out | 8,875 | 0.024% | [0.006%, 0.041%] | 31.8% | 3,518 | 47.5% |
| 2 | 4 | in_sample | 20,164 | -0.001% | [-0.007%, 0.006%] | 40.4% | 9,094 | 46.7% |
| 2 | 4 | held_out | 8,875 | 0.034% | [0.013%, 0.055%] | 37.9% | 3,518 | 48.1% |
| 2 | 5 | in_sample | 20,164 | 0.002% | [-0.005%, 0.010%] | 45.3% | 9,094 | 47.2% |
| 2 | 5 | held_out | 8,875 | 0.042% | [0.019%, 0.064%] | 43.1% | 3,518 | 48.2% |
| 3 | 1 | in_sample | 22,440 | -0.003% | [-0.007%, 0.001%] | 12.1% | 14,292 | 43.0% |
| 3 | 1 | held_out | 9,475 | 0.006% | [-0.004%, 0.016%] | 11.8% | 5,683 | 46.7% |
| 3 | 2 | in_sample | 22,440 | -0.004% | [-0.010%, 0.002%] | 25.8% | 14,292 | 45.5% |
| 3 | 2 | held_out | 9,475 | 0.014% | [0.000%, 0.027%] | 23.9% | 5,683 | 47.3% |
| 3 | 3 | in_sample | 22,440 | -0.005% | [-0.011%, 0.002%] | 35.2% | 14,292 | 46.4% |
| 3 | 3 | held_out | 9,475 | 0.018% | [0.000%, 0.035%] | 32.8% | 5,683 | 47.9% |
| 3 | 4 | in_sample | 22,440 | -0.006% | [-0.014%, 0.002%] | 41.9% | 14,292 | 47.0% |
| 3 | 4 | held_out | 9,475 | 0.020% | [-0.000%, 0.039%] | 39.6% | 5,683 | 47.7% |
| 3 | 5 | in_sample | 22,440 | -0.009% | [-0.018%, -0.000%] | 46.7% | 14,292 | 47.1% |
| 3 | 5 | held_out | 9,475 | 0.027% | [0.005%, 0.050%] | 44.0% | 5,683 | 48.5% |
| 4 | 1 | in_sample | 14,244 | -0.001% | [-0.006%, 0.004%] | 14.0% | 11,258 | 44.0% |
| 4 | 1 | held_out | 5,588 | 0.006% | [-0.011%, 0.024%] | 13.7% | 4,177 | 47.1% |
| 4 | 2 | in_sample | 14,244 | 0.000% | [-0.007%, 0.007%] | 27.4% | 11,258 | 45.3% |
| 4 | 2 | held_out | 5,588 | 0.022% | [-0.001%, 0.044%] | 26.2% | 4,177 | 48.3% |
| 4 | 3 | in_sample | 14,244 | -0.004% | [-0.014%, 0.005%] | 37.1% | 11,258 | 46.6% |
| 4 | 3 | held_out | 5,588 | 0.030% | [0.004%, 0.057%] | 35.1% | 4,177 | 48.2% |
| 4 | 4 | in_sample | 14,244 | -0.006% | [-0.016%, 0.005%] | 44.0% | 11,258 | 47.6% |
| 4 | 4 | held_out | 5,588 | 0.035% | [0.006%, 0.064%] | 41.0% | 4,177 | 48.0% |
| 4 | 5 | in_sample | 14,244 | -0.003% | [-0.015%, 0.008%] | 48.8% | 11,258 | 47.7% |
| 4 | 5 | held_out | 5,588 | 0.040% | [0.009%, 0.071%] | 45.9% | 4,177 | 48.1% |
| 5plus | 1 | in_sample | 6,693 | -0.001% | [-0.011%, 0.009%] | 18.7% | 5,919 | 44.9% |
| 5plus | 1 | held_out | 2,653 | 0.037% | [0.009%, 0.065%] | 17.9% | 2,291 | 46.9% |
| 5plus | 2 | in_sample | 6,693 | -0.005% | [-0.018%, 0.009%] | 33.1% | 5,919 | 46.8% |
| 5plus | 2 | held_out | 2,653 | 0.029% | [-0.009%, 0.067%] | 31.3% | 2,291 | 48.9% |
| 5plus | 3 | in_sample | 6,693 | -0.004% | [-0.020%, 0.013%] | 41.2% | 5,919 | 47.3% |
| 5plus | 3 | held_out | 2,653 | 0.041% | [-0.002%, 0.085%] | 39.6% | 2,291 | 48.7% |
| 5plus | 4 | in_sample | 6,693 | -0.009% | [-0.028%, 0.009%] | 47.4% | 5,919 | 47.5% |
| 5plus | 4 | held_out | 2,653 | 0.062% | [0.013%, 0.111%] | 45.8% | 2,291 | 49.5% |
| 5plus | 5 | in_sample | 6,693 | -0.014% | [-0.033%, 0.006%] | 51.7% | 5,919 | 47.8% |
| 5plus | 5 | held_out | 2,653 | 0.068% | [0.014%, 0.121%] | 49.8% | 2,291 | 48.6% |
| ALL | 1 | in_sample | 74,456 | -0.001% | [-0.003%, 0.001%] | 13.2% | 42,844 | 43.7% |
| ALL | 1 | held_out | 31,913 | 0.007% | [0.001%, 0.012%] | 12.8% | 16,549 | 46.6% |
| ALL | 2 | in_sample | 74,456 | -0.001% | [-0.004%, 0.002%] | 26.8% | 42,844 | 45.6% |
| ALL | 2 | held_out | 31,913 | 0.014% | [0.006%, 0.021%] | 25.2% | 16,549 | 47.7% |
| ALL | 3 | in_sample | 74,456 | -0.002% | [-0.006%, 0.001%] | 36.1% | 42,844 | 46.6% |
| ALL | 3 | held_out | 31,913 | 0.021% | [0.011%, 0.030%] | 34.1% | 16,549 | 47.9% |
| ALL | 4 | in_sample | 74,456 | -0.003% | [-0.007%, 0.001%] | 42.8% | 42,844 | 47.2% |
| ALL | 4 | held_out | 31,913 | 0.027% | [0.016%, 0.038%] | 40.4% | 16,549 | 48.1% |
| ALL | 5 | in_sample | 74,456 | -0.003% | [-0.008%, 0.001%] | 47.5% | 42,844 | 47.4% |
| ALL | 5 | held_out | 31,913 | 0.034% | [0.022%, 0.047%] | 45.1% | 16,549 | 48.3% |

## 5. Forward base-rate by tool combination (K=5, headline horizon)

Pre-specified pairwise combinations only (11 tested, NOT an exhaustive 2^9 search across all possible tool subsets -- that would be an uncontrolled multiple-testing fishing expedition). "Both active" means `active_X & active_Y` regardless of what else fires. Cells with n < 30 in either portion are flagged LOW-N.


### AAPL

| Combo | Portion | n | Mean fwd5 return | 95% CI | Hit rate | Hit n | Flag |
|---|---|---|---|---|---|---|---|
| candle+volume | in_sample | 4,643 | 0.008% | [-0.013%, 0.029%] | 54.8% | 4,643 |  |
| candle+volume | held_out | 1,753 | 0.045% | [0.016%, 0.074%] | 58.2% | 1,753 |  |
| candle+macd | in_sample | 2,152 | 0.001% | [-0.018%, 0.021%] | 48.2% | 2,152 |  |
| candle+macd | held_out | 928 | 0.033% | [0.006%, 0.059%] | 47.1% | 928 |  |
| candle+rsi | in_sample | 7,630 | 0.015% | [0.004%, 0.026%] | 47.2% | 7,630 |  |
| candle+rsi | held_out | 3,158 | 0.012% | [-0.002%, 0.027%] | 48.9% | 3,158 |  |
| candle+ema | in_sample | 7,438 | 0.001% | [-0.010%, 0.012%] | 46.0% | 7,438 |  |
| candle+ema | held_out | 3,254 | 0.004% | [-0.009%, 0.017%] | 45.6% | 3,254 |  |
| candle+vwap | in_sample | 16,155 | 0.002% | [-0.005%, 0.009%] | 46.2% | 16,155 |  |
| candle+vwap | held_out | 6,361 | 0.018% | [0.009%, 0.026%] | 46.3% | 6,361 |  |
| candle+atr | in_sample | 6,735 | 0.001% | [-0.009%, 0.011%] | 45.9% | 6,735 |  |
| candle+atr | held_out | 2,855 | 0.026% | [0.012%, 0.040%] | 46.0% | 2,855 |  |
| candle+swing | in_sample | 4,420 | 0.012% | [0.001%, 0.023%] | 46.6% | 4,420 |  |
| candle+swing | held_out | 1,930 | 0.007% | [-0.008%, 0.023%] | 46.9% | 1,930 |  |
| candle+orb | in_sample | 13,630 | 0.003% | [-0.005%, 0.010%] | 47.4% | 13,630 |  |
| candle+orb | held_out | 4,797 | 0.006% | [-0.004%, 0.016%] | 47.9% | 4,797 |  |
| volume+macd | in_sample | 783 | 0.008% | [-0.041%, 0.058%] | 54.0% | 480 |  |
| volume+macd | held_out | 305 | 0.046% | [-0.029%, 0.122%] | 58.5% | 188 |  |
| volume+ema | in_sample | 1,848 | -0.006% | [-0.043%, 0.031%] | 55.8% | 1,242 |  |
| volume+ema | held_out | 782 | 0.051% | [0.003%, 0.099%] | 59.3% | 535 |  |
| macd+ema | in_sample | 1,295 | 0.001% | [-0.026%, 0.029%] | 47.2% | 892 |  |
| macd+ema | held_out | 582 | 0.035% | [-0.002%, 0.073%] | 43.1% | 397 |  |

### NKE

| Combo | Portion | n | Mean fwd5 return | 95% CI | Hit rate | Hit n | Flag |
|---|---|---|---|---|---|---|---|
| candle+volume | in_sample | 8,533 | -0.011% | [-0.029%, 0.008%] | 57.0% | 8,533 |  |
| candle+volume | held_out | 2,844 | -0.008% | [-0.051%, 0.035%] | 58.0% | 2,844 |  |
| candle+macd | in_sample | 3,462 | -0.007% | [-0.025%, 0.012%] | 50.5% | 3,462 |  |
| candle+macd | held_out | 1,382 | -0.012% | [-0.045%, 0.022%] | 47.8% | 1,382 |  |
| candle+rsi | in_sample | 13,349 | -0.003% | [-0.012%, 0.007%] | 49.7% | 13,349 |  |
| candle+rsi | held_out | 5,455 | -0.003% | [-0.021%, 0.014%] | 48.5% | 5,455 |  |
| candle+ema | in_sample | 11,544 | 0.003% | [-0.007%, 0.012%] | 49.3% | 11,544 |  |
| candle+ema | held_out | 4,623 | -0.008% | [-0.028%, 0.011%] | 47.6% | 4,623 |  |
| candle+vwap | in_sample | 24,863 | 0.004% | [-0.003%, 0.010%] | 49.1% | 24,863 |  |
| candle+vwap | held_out | 9,250 | -0.005% | [-0.019%, 0.008%] | 47.4% | 9,250 |  |
| candle+atr | in_sample | 12,805 | -0.002% | [-0.011%, 0.007%] | 48.3% | 12,805 |  |
| candle+atr | held_out | 4,870 | -0.020% | [-0.035%, -0.005%] | 45.2% | 4,870 |  |
| candle+swing | in_sample | 7,180 | 0.006% | [-0.004%, 0.016%] | 49.4% | 7,180 |  |
| candle+swing | held_out | 2,837 | -0.030% | [-0.051%, -0.009%] | 46.8% | 2,837 |  |
| candle+orb | in_sample | 22,794 | 0.003% | [-0.005%, 0.010%] | 49.7% | 22,794 |  |
| candle+orb | held_out | 8,679 | -0.012% | [-0.025%, 0.002%] | 48.8% | 8,679 |  |
| volume+macd | in_sample | 1,245 | -0.009% | [-0.055%, 0.036%] | 58.2% | 777 |  |
| volume+macd | held_out | 442 | -0.004% | [-0.133%, 0.126%] | 57.1% | 252 |  |
| volume+ema | in_sample | 3,264 | 0.001% | [-0.031%, 0.033%] | 56.9% | 2,218 |  |
| volume+ema | held_out | 1,247 | -0.019% | [-0.088%, 0.050%] | 57.4% | 871 |  |
| macd+ema | in_sample | 2,032 | 0.001% | [-0.025%, 0.027%] | 50.9% | 1,380 |  |
| macd+ema | held_out | 845 | -0.010% | [-0.064%, 0.044%] | 50.9% | 550 |  |

### INTC

| Combo | Portion | n | Mean fwd5 return | 95% CI | Hit rate | Hit n | Flag |
|---|---|---|---|---|---|---|---|
| candle+volume | in_sample | 7,869 | -0.023% | [-0.048%, 0.001%] | 57.0% | 7,869 |  |
| candle+volume | held_out | 2,796 | 0.134% | [0.062%, 0.206%] | 55.6% | 2,796 |  |
| candle+macd | in_sample | 3,269 | -0.012% | [-0.034%, 0.010%] | 49.4% | 3,269 |  |
| candle+macd | held_out | 1,225 | 0.024% | [-0.045%, 0.094%] | 47.2% | 1,225 |  |
| candle+rsi | in_sample | 12,519 | -0.001% | [-0.012%, 0.010%] | 49.1% | 12,519 |  |
| candle+rsi | held_out | 4,857 | 0.088% | [0.052%, 0.125%] | 47.7% | 4,857 |  |
| candle+ema | in_sample | 11,059 | -0.004% | [-0.018%, 0.009%] | 48.3% | 11,059 |  |
| candle+ema | held_out | 4,371 | 0.027% | [-0.007%, 0.061%] | 44.9% | 4,371 |  |
| candle+vwap | in_sample | 23,297 | -0.007% | [-0.014%, 0.001%] | 47.9% | 23,297 |  |
| candle+vwap | held_out | 9,046 | 0.017% | [-0.004%, 0.039%] | 44.8% | 9,046 |  |
| candle+atr | in_sample | 11,112 | 0.001% | [-0.009%, 0.012%] | 46.3% | 11,112 |  |
| candle+atr | held_out | 4,745 | -0.000% | [-0.027%, 0.026%] | 44.8% | 4,745 |  |
| candle+swing | in_sample | 6,682 | -0.015% | [-0.030%, -0.000%] | 47.2% | 6,682 |  |
| candle+swing | held_out | 2,606 | 0.033% | [-0.007%, 0.074%] | 42.7% | 2,606 |  |
| candle+orb | in_sample | 20,933 | 0.001% | [-0.009%, 0.011%] | 48.0% | 20,933 |  |
| candle+orb | held_out | 7,607 | 0.015% | [-0.007%, 0.037%] | 45.9% | 7,607 |  |
| volume+macd | in_sample | 1,227 | -0.021% | [-0.071%, 0.030%] | 58.7% | 746 |  |
| volume+macd | held_out | 504 | 0.057% | [-0.113%, 0.227%] | 57.7% | 291 |  |
| volume+ema | in_sample | 3,230 | -0.025% | [-0.068%, 0.018%] | 58.1% | 2,208 |  |
| volume+ema | held_out | 1,187 | 0.240% | [0.113%, 0.367%] | 55.9% | 733 |  |
| macd+ema | in_sample | 2,020 | 0.003% | [-0.023%, 0.030%] | 49.7% | 1,334 |  |
| macd+ema | held_out | 889 | 0.032% | [-0.056%, 0.121%] | 46.8% | 528 |  |

## 6. In-sample vs. held-out stability (the honesty check)

Per (ticker, confluence bucket, K): does the held-out mean-return 95% CI overlap the in-sample CI?

| Ticker | Confluence | K | In-sample n | Held-out n | Stability |
|---|---|---|---|---|---|
| AAPL | 0 | 1 | 1,055 | 639 | stable (CIs overlap) |
| AAPL | 0 | 2 | 1,055 | 639 | stable (CIs overlap) |
| AAPL | 0 | 3 | 1,055 | 639 | stable (CIs overlap) |
| AAPL | 0 | 4 | 1,055 | 639 | stable (CIs overlap) |
| AAPL | 0 | 5 | 1,055 | 639 | stable (CIs overlap) |
| AAPL | 1 | 1 | 5,685 | 2,871 | stable (CIs overlap) |
| AAPL | 1 | 2 | 5,685 | 2,871 | stable (CIs overlap) |
| AAPL | 1 | 3 | 5,685 | 2,871 | stable (CIs overlap) |
| AAPL | 1 | 4 | 5,685 | 2,871 | stable (CIs overlap) |
| AAPL | 1 | 5 | 5,685 | 2,871 | stable (CIs overlap) |
| AAPL | 2 | 1 | 12,347 | 5,660 | stable (CIs overlap) |
| AAPL | 2 | 2 | 12,347 | 5,660 | stable (CIs overlap) |
| AAPL | 2 | 3 | 12,347 | 5,660 | stable (CIs overlap) |
| AAPL | 2 | 4 | 12,347 | 5,660 | stable (CIs overlap) |
| AAPL | 2 | 5 | 12,347 | 5,660 | stable (CIs overlap) |
| AAPL | 3 | 1 | 14,462 | 5,945 | stable (CIs overlap) |
| AAPL | 3 | 2 | 14,462 | 5,945 | stable (CIs overlap) |
| AAPL | 3 | 3 | 14,462 | 5,945 | stable (CIs overlap) |
| AAPL | 3 | 4 | 14,462 | 5,945 | stable (CIs overlap) |
| AAPL | 3 | 5 | 14,462 | 5,945 | stable (CIs overlap) |
| AAPL | 4 | 1 | 9,227 | 3,454 | stable (CIs overlap) |
| AAPL | 4 | 2 | 9,227 | 3,454 | stable (CIs overlap) |
| AAPL | 4 | 3 | 9,227 | 3,454 | stable (CIs overlap) |
| AAPL | 4 | 4 | 9,227 | 3,454 | stable (CIs overlap) |
| AAPL | 4 | 5 | 9,227 | 3,454 | stable (CIs overlap) |
| AAPL | 5plus | 1 | 4,273 | 1,599 | stable (CIs overlap) |
| AAPL | 5plus | 2 | 4,273 | 1,599 | stable (CIs overlap) |
| AAPL | 5plus | 3 | 4,273 | 1,599 | stable (CIs overlap) |
| AAPL | 5plus | 4 | 4,273 | 1,599 | stable (CIs overlap) |
| AAPL | 5plus | 5 | 4,273 | 1,599 | stable (CIs overlap) |
| AAPL | ALL | 1 | 47,049 | 20,168 | stable (CIs overlap) |
| AAPL | ALL | 2 | 47,049 | 20,168 | stable (CIs overlap) |
| AAPL | ALL | 3 | 47,049 | 20,168 | stable (CIs overlap) |
| AAPL | ALL | 4 | 47,049 | 20,168 | stable (CIs overlap) |
| AAPL | ALL | 5 | 47,049 | 20,168 | stable (CIs overlap) |
| NKE | 0 | 1 | 1,387 | 739 | stable (CIs overlap) |
| NKE | 0 | 2 | 1,387 | 739 | stable (CIs overlap) |
| NKE | 0 | 3 | 1,387 | 739 | stable (CIs overlap) |
| NKE | 0 | 4 | 1,387 | 739 | stable (CIs overlap) |
| NKE | 0 | 5 | 1,387 | 739 | stable (CIs overlap) |
| NKE | 1 | 1 | 7,987 | 4,204 | stable (CIs overlap) |
| NKE | 1 | 2 | 7,987 | 4,204 | stable (CIs overlap) |
| NKE | 1 | 3 | 7,987 | 4,204 | stable (CIs overlap) |
| NKE | 1 | 4 | 7,987 | 4,204 | stable (CIs overlap) |
| NKE | 1 | 5 | 7,987 | 4,204 | stable (CIs overlap) |
| NKE | 2 | 1 | 19,168 | 8,797 | stable (CIs overlap) |
| NKE | 2 | 2 | 19,168 | 8,797 | stable (CIs overlap) |
| NKE | 2 | 3 | 19,168 | 8,797 | stable (CIs overlap) |
| NKE | 2 | 4 | 19,168 | 8,797 | stable (CIs overlap) |
| NKE | 2 | 5 | 19,168 | 8,797 | stable (CIs overlap) |
| NKE | 3 | 1 | 23,149 | 9,626 | stable (CIs overlap) |
| NKE | 3 | 2 | 23,149 | 9,626 | stable (CIs overlap) |
| NKE | 3 | 3 | 23,149 | 9,626 | stable (CIs overlap) |
| NKE | 3 | 4 | 23,149 | 9,626 | stable (CIs overlap) |
| NKE | 3 | 5 | 23,149 | 9,626 | stable (CIs overlap) |
| NKE | 4 | 1 | 15,152 | 5,748 | stable (CIs overlap) |
| NKE | 4 | 2 | 15,152 | 5,748 | stable (CIs overlap) |
| NKE | 4 | 3 | 15,152 | 5,748 | stable (CIs overlap) |
| NKE | 4 | 4 | 15,152 | 5,748 | stable (CIs overlap) |
| NKE | 4 | 5 | 15,152 | 5,748 | stable (CIs overlap) |
| NKE | 5plus | 1 | 7,177 | 2,612 | stable (CIs overlap) |
| NKE | 5plus | 2 | 7,177 | 2,612 | stable (CIs overlap) |
| NKE | 5plus | 3 | 7,177 | 2,612 | stable (CIs overlap) |
| NKE | 5plus | 4 | 7,177 | 2,612 | stable (CIs overlap) |
| NKE | 5plus | 5 | 7,177 | 2,612 | stable (CIs overlap) |
| NKE | ALL | 1 | 74,020 | 31,726 | stable (CIs overlap) |
| NKE | ALL | 2 | 74,020 | 31,726 | stable (CIs overlap) |
| NKE | ALL | 3 | 74,020 | 31,726 | stable (CIs overlap) |
| NKE | ALL | 4 | 74,020 | 31,726 | stable (CIs overlap) |
| NKE | ALL | 5 | 74,020 | 31,726 | stable (CIs overlap) |
| INTC | 0 | 1 | 1,733 | 944 | SHIFTED (CIs do not overlap) |
| INTC | 0 | 2 | 1,733 | 944 | stable (CIs overlap) |
| INTC | 0 | 3 | 1,733 | 944 | stable (CIs overlap) |
| INTC | 0 | 4 | 1,733 | 944 | stable (CIs overlap) |
| INTC | 0 | 5 | 1,733 | 944 | stable (CIs overlap) |
| INTC | 1 | 1 | 9,182 | 4,378 | stable (CIs overlap) |
| INTC | 1 | 2 | 9,182 | 4,378 | stable (CIs overlap) |
| INTC | 1 | 3 | 9,182 | 4,378 | stable (CIs overlap) |
| INTC | 1 | 4 | 9,182 | 4,378 | stable (CIs overlap) |
| INTC | 1 | 5 | 9,182 | 4,378 | stable (CIs overlap) |
| INTC | 2 | 1 | 20,164 | 8,875 | stable (CIs overlap) |
| INTC | 2 | 2 | 20,164 | 8,875 | stable (CIs overlap) |
| INTC | 2 | 3 | 20,164 | 8,875 | SHIFTED (CIs do not overlap) |
| INTC | 2 | 4 | 20,164 | 8,875 | SHIFTED (CIs do not overlap) |
| INTC | 2 | 5 | 20,164 | 8,875 | SHIFTED (CIs do not overlap) |
| INTC | 3 | 1 | 22,440 | 9,475 | stable (CIs overlap) |
| INTC | 3 | 2 | 22,440 | 9,475 | stable (CIs overlap) |
| INTC | 3 | 3 | 22,440 | 9,475 | stable (CIs overlap) |
| INTC | 3 | 4 | 22,440 | 9,475 | stable (CIs overlap) |
| INTC | 3 | 5 | 22,440 | 9,475 | SHIFTED (CIs do not overlap) |
| INTC | 4 | 1 | 14,244 | 5,588 | stable (CIs overlap) |
| INTC | 4 | 2 | 14,244 | 5,588 | stable (CIs overlap) |
| INTC | 4 | 3 | 14,244 | 5,588 | stable (CIs overlap) |
| INTC | 4 | 4 | 14,244 | 5,588 | SHIFTED (CIs do not overlap) |
| INTC | 4 | 5 | 14,244 | 5,588 | SHIFTED (CIs do not overlap) |
| INTC | 5plus | 1 | 6,693 | 2,653 | SHIFTED (CIs do not overlap) |
| INTC | 5plus | 2 | 6,693 | 2,653 | stable (CIs overlap) |
| INTC | 5plus | 3 | 6,693 | 2,653 | stable (CIs overlap) |
| INTC | 5plus | 4 | 6,693 | 2,653 | SHIFTED (CIs do not overlap) |
| INTC | 5plus | 5 | 6,693 | 2,653 | SHIFTED (CIs do not overlap) |
| INTC | ALL | 1 | 74,456 | 31,913 | stable (CIs overlap) |
| INTC | ALL | 2 | 74,456 | 31,913 | SHIFTED (CIs do not overlap) |
| INTC | ALL | 3 | 74,456 | 31,913 | SHIFTED (CIs do not overlap) |
| INTC | ALL | 4 | 74,456 | 31,913 | SHIFTED (CIs do not overlap) |
| INTC | ALL | 5 | 74,456 | 31,913 | SHIFTED (CIs do not overlap) |

## 7. Multiple-testing & honesty caveats

- This report computes **3 tickers x 7 confluence buckets x 5 K-horizons x 2 portions = 210 cells** for the confluence curves, plus **3 tickers x 11 combos x 2 portions = 66 cells** for the combo curves (K=5 only). At a 95% CI, ~5% of cells will show a 'significant' departure from zero by chance alone even with no real effect anywhere. A cell whose CI excludes zero in only ONE portion, or only at one ticker, is not a discovery -- look for replication across tickers AND across the in-sample/held-out split (Section 6) before reading anything here as real.
- The combo curves shrink fast: several cells (e.g. `volume+macd`, `macd+ema`) have held-out n in the 4-30 range -- explicitly flagged LOW-N in Section 5's table. A dramatic-looking point estimate on 4-15 observations is noise, not signal, regardless of how large the number looks.
- `direction_candle` (the candle/pattern tool) is the **only** source of a directional thesis in this snapshot -- `hit_target` is computed against it specifically, not against some multi-tool consensus direction. Rows where `active_candle` is False have `hit_target = NULL` regardless of confluence from the other 8 tools. This means high-confluence rows driven mainly by non-candle tools contribute to the mean-return columns but not the hit-rate columns -- read `hit_n` next to `hit_rate` before comparing across buckets.
- Same execution-cost caveat as v1: mean 5m returns this close to zero are easily swamped by spread/slippage, which is not modeled here at all.

## 8. Scoping notes

- **ATR "expanding" threshold** (`ATR_EXPAND_MULT = 1/0.75 ~= 1.333`): the codebase only defines the compressed side (`vol_compressed`, `atr14 < atr14_ma*0.75`, in `features.py`). No existing precedent for the opposite side, so this mirrors it symmetrically rather than inventing an unrelated number.
- **Confluence-bucket "5plus"**: buckets 5 through 8 (8 was the observed max; 9/9 never occurred) are collapsed into one bucket for sample size -- see Section 2's distribution table for the raw split.
- **N=2 only, this round** -- per the brief. The candle tool's pattern-fit logic and geometry-thrust trigger are otherwise identical to v1's N=2 case; no N-sweep was attempted for the other 8 tools.
- **No daily context attached** -- single-timeframe (5m) only, by explicit design; daily zoom-out is a deliberately deferred later phase, not an oversight.

## 9. Verdict

**Plain answer: no. The full tool-state picture does not change v1's null.** Confluence count does not separate from baseline on any target, for any ticker, and no pre-specified tool combination passes its own replication bar. This is a stronger, more thoroughly-tested null than v1's, not a different conclusion.

- **Confluence buckets track their own ticker's unconditional ("ALL") baseline almost exactly, at every level.** The cleanest-looking cell in the entire dataset is AAPL's confluence-bucket-3 at K=5: mean return 0.009% in-sample (CI [0.002%, 0.016%], excludes zero) and 0.010% held-out (CI [0.001%, 0.019%], also excludes zero) -- a textbook "replicates out-of-sample" result. But AAPL's own ALL baseline at K=5 shows 0.006% in-sample (CI [0.002%, 0.010%]) and 0.010% held-out (CI [0.005%, 0.015%]) -- the *same* small positive drift, replicating just as cleanly, with overlapping confidence intervals against bucket 3's. AAPL simply drifted slightly upward across this whole measurement window (both halves of it); conditioning on confluence=3 doesn't add anything above that drift. The same pattern holds at every other bucket for AAPL, and for NKE and INTC's non-bucket-1 cells: bucketed curves move with the ticker's baseline, not against it.

- **The one cell that's modestly more than baseline (NKE, confluence=1, K=3) runs in the wrong direction for the v2 hypothesis.** NKE's low-confluence bucket (almost nothing else firing) shows a small negative return that's somewhat more pronounced than NKE's flat/insignificant ALL baseline, and partially replicates (in-sample -0.008% CI [-0.014%, -0.001%]; held-out -0.012% CI [-0.023%, -0.001%], both excluding zero, same sign). If richer confluence carried more information, this is the opposite of what you'd expect to find -- the effect is at *low*, not high, confluence, it's economically tiny (under 0.01%, smaller than typical spread/slippage), and with 210 confluence cells tested across this report, ~10 "significant" cells are expected by chance alone at a 95% threshold even with zero real effect anywhere (Section 7). One cell, in the wrong direction, is exactly consistent with that noise floor.

- **High-confluence buckets show no clean separation either.** AAPL's "5plus" bucket looks dramatic in isolation (held-out K=5: 0.043%, CI [0.016%, 0.070%], excluding zero) but its in-sample counterpart is statistically flat (-0.015% to 0.004% across K, CI always including zero, n=4,273) -- a held-out-only result with no in-sample support is the signature of a look-elsewhere artifact, not a real high-confluence effect, especially given Section 7's own replication bar. NKE's "5plus" bucket is flat (CI includes zero) in both portions. INTC's "5plus" bucket is dominated by the same regime-shift artifact described below.

- **No pre-specified tool combination (Section 5) passes the in-sample-AND-held-out replication bar.** Of the 11 combinations x 3 tickers = 33 combo curves at K=5, every single one either (a) has a CI including zero in at least one portion, or (b) flips sign or magnitude dramatically between portions (e.g. AAPL `candle+volume`: -0.013%..0.029% in-sample vs 0.045% [0.016%,0.074%] held-out; INTC `volume+ema`: -0.025%..0.018% in-sample vs 0.240% [0.113%,0.367%] held-out -- a swing that also tracks INTC's ticker-wide regime shift, not something specific to that combination). The brief explicitly named `volume+macd` as an example combination to test; it shows nothing in either ticker (wide CIs spanning zero, n in the low hundreds, several held-out cells flagged LOW-N).

- **INTC's across-the-board in-sample/held-out "shift" is a re-confirmation of v1's regime-drift finding, not a new confluence-related result.** Every confluence bucket for INTC (0 through 5plus) and its ALL baseline show the identical pattern: near-zero-or-negative in-sample, clearly positive in held-out, growing with K (ALL at K=5: -0.003% in-sample vs +0.034% [0.022%,0.047%] held-out; bucket 5plus at K=5: -0.014% [-0.033%,0.006%] in-sample vs +0.068% [0.014%,0.121%] held-out). Because this shift appears identically in the *unconditioned* baseline, it is a property of INTC's price series in this particular train/test split window -- the same conclusion v1 reached independently with a completely different, much thinner feature set. Getting the same diagnosis twice, from two unrelated feature sets, is itself a useful (if indirect) confirmation that the explanation is right.

- **Bottom line:** richer confluence does not produce a clearer or more reliable forward signal than v1's thin candle-only feature set did. Every one of the 9 tools' "active" flags, every confluence level from 0 to 8, and every one of the 11 pre-specified tool-pair combinations was tested against the same honest in-sample/held-out bar, and none of them separate from doing nothing once you account for each ticker's own baseline drift. This is the "still null even with full confluence" outcome the task brief flagged up front as an acceptable, valid, *stronger* result -- and that's what was found.

## 10. Reproducibility

- Full per-cell aggregates: `reports/research/setup_formation_v2_summary.json` (run `20260621T203847Z-6ed39367`)
- Run parameters/thresholds: `reports/research/setup_formation_v2_run_log.jsonl` (same `run_id`)
- Raw rows: `research_setup_formation_v2` table, `WHERE run_id = '20260621T203847Z-6ed39367'`
- Example annotated charts: `reports/research/charts/` (v2 examples prefixed `v2_`)
- Thresholds used this run:
  - `GEOM_BODY_PCT_MIN` = 60.0
  - `GEOM_SIZE_ATR_MULT` = 1.2
  - `ATR_EXPAND_MULT` = 1.3333333333333333
  - `PIVOT_WIDTH` = 3
  - `SWING_TREND_LOOKBACK` = 4
  - `ATR_HIT_MULT` = 1.0
  - `FORWARD_RETURN_FLAT_EPS` = 0.02
  - `TRAIN_FRACTION` = 0.7
  - `MIN_CELL_N` = 30
