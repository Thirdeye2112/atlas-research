# Atlas Research Engine — Roadmap

## Vision
A multi-timeframe pattern recognition and prediction engine that learns from
historical price action across all US-listed equities, identifies high-probability
setups using candlestick patterns, technical analysis, and ML, and presents
actionable intraday and daily outcomes with forward probability estimates.

---

## Layer 1 — Daily Cross-Sectional Research Foundation ✅ BUILT
**Status:** Complete and operational.

- 183-ticker universe (manual curation)
- Daily OHLCV bars via yfinance (2019–present)
- 27 engineered features: returns, trend, momentum, volatility, volume, relative strength, regime
- LightGBM regressor (label_return_5d) + classifier (label_positive_5d) with Platt calibration
- Expanding walk-forward validation (5 folds, 2022–2026)
- Parquet export pipeline (1,853 files, 102MB)
- PostgreSQL schema with migration infrastructure
- ResearchLab UI in Atlas Alpha (predictions, fold metrics, feature importance)
- nightly_pipeline.py scheduled runner

**Current signal quality:**
- WF Mean Rank IC: 0.0014 (weak — expected at this universe size)
- Fold 5 (partial, live): Rank IC 0.078 — improving trend
- Interpretation: foundation proven, signal strengthens with universe expansion

---

## Layer 2 — Full US Universe Expansion 🔲 NEXT
**Goal:** Expand from 183 tickers to full US equity universe (~3,000–5,000 tickers).

**Tasks:**
- Build `scripts/build_universe.py` — pulls Russell 3000 or all NYSE/NASDAQ listings
- Filter by liquidity: min avg dollar volume $1M/day, price > $1
- Backfill daily bars for all new tickers (15 years where available)
- Re-run feature engineering and label generation
- Re-run walk-forward training on expanded universe
- Expected: Rank IC improvement from cross-sectional breadth

**Data source:** yfinance (free, daily bars, ~15yr history available)
**Storage impact:** ~5,000 tickers × 15yr × 252 days ≈ 19M rows raw_bars (currently 339K)
**Parquet:** grows from 102MB to ~2GB
**Training time:** 30–60 min per walk-forward run (vs current ~3 min)

---

## Layer 3 — Daily Candlestick & Technical Pattern Engine 🔲 NEXT
**Goal:** Detect named candlestick and chart patterns on daily bars; compute forward
outcome statistics for each pattern; rank setups by historical edge.

**Pattern categories:**
- Single-bar: Doji, Hammer, Shooting Star, Marubozu, Spinning Top
- Two-bar: Engulfing (bull/bear), Harami, Piercing Line, Dark Cloud Cover
- Three-bar: Morning/Evening Star, Three White Soldiers, Three Black Crows
- Chart patterns: Cup & Handle, Head & Shoulders, Double Top/Bottom, Flags, Wedges
- Volume confirmation: pattern + volume spike, pattern + volume dry-up
- Support/resistance: proximity to 52-week high/low, pivot levels

**Tasks:**
- Build `src/atlas_research/patterns/candlestick.py` — single and multi-bar patterns
- Build `src/atlas_research/patterns/chart_patterns.py` — multi-bar chart structures
- Build `src/atlas_research/patterns/scanner.py` — daily scan across full universe
- Add `pattern_signals` table to DB (migration 0005)
- Compute forward return statistics per pattern (hit rate, mean return, Sharpe)
- Integrate pattern features into LightGBM feature set
- Add pattern scan to nightly pipeline

**Dependencies:** Layer 2 (needs broad universe for statistical significance)
**Data source:** existing daily bars in raw_bars table
**Libraries:** TA-Lib (optional), or pure-pandas implementation

---

## Layer 4 — Transcript Hypothesis Engine 🔲 NEXT
**Status:** Schema built (migration 0003), modules written, not yet running.

**Goal:** Extract market hypotheses from text transcripts (earnings calls, analyst
notes, research PDFs), backtest them against historical price action, and promote
statistically valid hypotheses into the feature set.

**Tasks:**
- Fix `sys.path` in transcript scripts (fix_transcript_paths.py exists)
- Set ANTHROPIC_API_KEY in .env
- Run `python scripts/run_transcript_pipeline.py` on sample transcripts
- Review `python scripts/inspect_hypotheses.py` output
- Wire promoted hypotheses into nightly feature engineering

**Dependencies:** Layer 1 (uses existing raw_bars for backtesting)
**Unblocked by:** Layers 2 and 3

---

## Layer 5 — Intraday 5-Minute Engine 🔲 REQUIRES PAID DATA
**Goal:** 5-minute bar analysis, intraday pattern detection, and same-session
outcome prediction.

**Constraint:** Free sources (yfinance) provide only 60 days of 5-minute history.
15-year 5-minute history requires a paid vendor.

**Paid data options:**
- Polygon.io Starter ($29/mo) — 2yr intraday history
- Polygon.io Stocks Starter ($79/mo) — full history
- Alpaca Markets — free tier has 5-min, limited history
- Databento — pay-per-query, institutional quality
- Tradier — free tier with brokerage account

**Prototype path (no paid data):**
- Use yfinance 60-day 5-min window as a rolling prototype
- Build intraday pattern detection on recent data only
- Validate approach before committing to paid vendor

**Tasks (prototype):**
- Build `src/atlas_research/ingest/intraday_ingest.py` — yfinance 5-min, rolling 60 days
- Add `intraday_bars` table (migration 0006)
- Build intraday feature engineering (VWAP, opening range, intraday momentum)
- Build intraday pattern scanner
- Evaluate signal quality on 60-day window

**Decision point:** After prototype proves signal quality, select paid vendor.

---

## Layer 6 — Prediction Feedback Loop 🔲 AFTER LIVE HISTORY
**Goal:** Close the loop — compare predictions to actual outcomes, score the model,
and use prediction errors to improve features and retrain.

**Prerequisite:** `predictions` table must have 20+ trading days of live history.
**Earliest:** ~1 month after Layer 1 predictions start running nightly.

**Tasks:**
- Build `src/atlas_research/feedback/outcome_resolver.py`
  — joins predictions to labels at T+5 days, scores hit/miss
- Add `prediction_outcomes` table (migration 0007)
- Build feedback metrics: directional accuracy, return capture, IC over time
- Wire outcome stats into model retraining signal
- Add feedback metrics to ResearchLab UI

---

## Layer 7 — Pattern & Outcome UI 🔲 AFTER LAYER 3
**Goal:** Visual presentation of pattern setups, historical outcome distributions,
and forward probability estimates.

**Tasks:**
- Pattern scan results page in Atlas Alpha
- Per-ticker pattern history with annotated chart
- Outcome distribution charts (win rate, avg return by pattern)
- Intraday setup alerts (Layer 5 prerequisite)
- Integrated daily + intraday view

---

## Implementation Order (recommended)
```
Now:        Layer 2 (universe expansion) — unblocks Layer 3 statistical power
Parallel:   Layer 4 (transcript engine) — self-contained, ready to run
Next:       Layer 3 (candlestick/pattern engine) — needs Layer 2 breadth
Later:      Layer 5 prototype (60-day intraday) — no vendor needed to start
Then:       Layer 6 (feedback loop) — needs 30+ days live predictions
Finally:    Layer 7 (pattern UI) — after Layers 3 + 6 have data
```

---

## What Will Not Be Built Without Decisions
- Full 15-year intraday history — requires paid vendor decision
- Real-time intraday signals — requires streaming data infrastructure
- Order execution / paper trading — out of scope for research engine
