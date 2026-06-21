# VWAP 5m Feature — Build Report

**Date:** 2026-06-21  
**Branch:** feat/vwap-5m  
**Status:** Smoke-test validated; full-universe run initiated (5 558 tickers, ETA ~13h)

---

## 1. Definition Used

### Typical Price
```
typical_price = (high + low + close) / 3     # HLC3 — standard VWAP convention
```

### Session-Anchored VWAP
```
VWAP_T = Σ(typical_price_i × volume_i, for i = session_open .. T)
         / Σ(volume_i,                 for i = session_open .. T)
```

VWAP is a **running cumulative** anchored to the first 5m bar of each trading
session. It resets to the current bar's typical price at bar 0 (first bar of day)
and converges over the session.

Derived features stored:
| Column | Definition | Type |
|--------|-----------|------|
| `vwap` | Session VWAP at this bar | float |
| `dist_from_vwap` | `(close − vwap) / vwap` — signed, fractional | float |
| `above_vwap` | `close > vwap` | bool |
| `session_date` | ET calendar date of the bar | date |

---

## 2. Timestamp & Session Handling

### Source timestamps
`intraday_bars.ts` is **UTC with timezone** (stored as `TIMESTAMPTZ`).
The ingestion pipeline (`ingest_intraday_5m.py`) converts all source timestamps
to UTC before writing, regardless of vendor (Yahoo or Alpaca).

### Session boundary detection
```python
et_ts = df["ts"].dt.tz_convert("America/New_York")
df["session_date"] = et_ts.dt.date
```

pandas `tz_convert` delegates to the IANA timezone database (via `zoneinfo` or
`dateutil`), so DST transitions are handled automatically. The VWAP cumsum is
grouped by `session_date`, so each ET calendar day gets its own reset.

**US market hours** are already pre-filtered in `intraday_bars`: the ingest
pipeline keeps only bars where local ET time is `09:30 ≤ t < 16:00`
(570 ≤ minute-of-day < 960). No additional hour filtering is needed here.

### DST validation
Sessions around the 2025 spring-forward (2025-03-09) checked explicitly:

| session_date | First bar ET time | tp=vwap at bar 0 | status |
|-------------|-------------------|------------------|--------|
| 2025-03-06  | 09:30 ET (EST)   | PASS             | OK     |
| 2025-03-07  | 09:30 ET (EST)   | PASS             | OK     |
| 2025-03-11  | 09:30 ET (EDT)   | PASS             | OK     |
| 2025-03-12  | 09:30 ET (EDT)   | PASS             | OK     |

Sessions before and after the clock change show 09:30 first-bar alignment,
confirming that DST does not misidentify session boundaries.

---

## 3. Look-Ahead Validation

### Method
For SPY session 2021-01-04 (first available), the stored VWAP was compared
against manually re-computed expected VWAP bar-by-bar.

### Expected VWAP formula (manual re-computation)
```
tp_i = (high_i + low_i + close_i) / 3
cum_tp_vol_T = Σ(tp_i × vol_i, i=0..T)
cum_vol_T    = Σ(vol_i, i=0..T)
expected_VWAP_T = cum_tp_vol_T / cum_vol_T
```

### Results (SPY 2021-01-04, first 8 bars)

| bar | ts (ET) | tp | vol | stored_vwap | expected_vwap | match |
|-----|---------|-----|-----|-------------|---------------|-------|
| 0 | 09:30 | 374.8600 | 18,181 | 374.8600 | 374.8600 | OK |
| 1 | 09:35 | 374.2067 | 12,410 | 374.5950 | 374.5950 | OK |
| 2 | 09:40 | 373.8967 | 7,713 | 374.4543 | 374.4543 | OK |
| 3 | 09:45 | 374.1717 | 10,010 | 374.3958 | 374.3958 | OK |
| 4 | 09:50 | 373.5817 | 9,437 | 374.2627 | 374.2627 | OK |
| 5 | 09:55 | 373.5133 | 4,981 | 374.2032 | 374.2032 | OK |
| 6 | 10:00 | 373.3667 | 10,711 | 374.0812 | 374.0812 | OK |
| 7 | 10:05 | 373.0067 | 5,912 | 374.0012 | 374.0012 | OK |

**Bar-0 check:** VWAP[0] = typical_price[0] (volume cancels in ratio).
Confirmed: `tp = 374.86000000`, `vwap = 374.86000000`, `delta = 0.00e+00`.

**Session reset check:** 20 consecutive SPY sessions checked — all PASS
(bar-0 delta = 0 for every session, confirming clean daily reset).

**Implementation note:** `groupby("session_date").cumsum()` on rows sorted
ascending by ts is algebraically equivalent to the formula above: VWAP at bar T
only sees tp×vol for bars 0..T of the same session. It is independent of bars T+1
onward. No lookahead.

---

## 4. Sanity Checks

### VWAP within session H/L range (SPY)

| session_date | vwap_min | vwap_max | day_low | day_high | within_range |
|-------------|----------|----------|---------|----------|--------------|
| 2021-01-04  | 368.491  | 374.860  | 364.870 | 375.430  | OK |
| 2021-01-05  | 368.927  | 370.475  | 368.250 | 372.435  | OK |
| 2021-01-06  | 369.562  | 374.766  | 369.190 | 376.960  | OK |
| 2021-01-07  | 376.435  | 378.444  | 375.920 | 379.870  | OK |
| 2021-01-08  | 379.381  | 380.745  | 377.110 | 381.450  | OK |

VWAP min/max stays inside the session's price range for all checked days.

### dist_from_vwap distribution (smoke-test data, 3 tickers, 319k+ bars)

| percentile | dist_from_vwap |
|-----------|---------------|
| p1 | -0.02104 |
| p10 | -0.00731 |
| p25 | -0.00287 |
| p50 | +0.00016 |
| p75 | +0.00308 |
| p90 | +0.00741 |
| p99 | +0.02040 |
| mean | +0.00009 |

Distribution is tight and centered near zero (median ~0.016% from VWAP).
Tails at ±2% cover extreme intraday moves. Mean is +0.009%: equity prices
spend slightly more time above VWAP, consistent with the slight positive drift
seen in `above_vwap` fraction.

### above_vwap fraction: 0.5175
51.75% of bars close above VWAP. Slightly above 50% is expected — equities
have a positive drift bias, so prices tend to extend above the daily VWAP more
often than below.

---

## 5. Coverage

### Smoke test (validated)
| metric | value |
|--------|-------|
| Tickers | 3 (SPY, INTC, AMD) |
| Total rows | 319,204 |
| Date range | 2021-01-04 → 2026-06-18 |
| Bars per ticker (avg) | ~106,400 |
| Sessions per ticker (avg) | ~1,367 |

### Full run (initiated 2026-06-21 ~10:49 ET)
| metric | value |
|--------|-------|
| Universe in intraday_bars 5m | 5,561 tickers |
| Already done (smoke test) | 3 tickers |
| Queued | 5,558 tickers |
| ETA | ~13 hours |
| Log | `reports/validity/vwap_5m.log` |

The run is resumable: re-running `build_vwap_5m.py` will skip completed tickers
and pick up where it left off.

---

## 6. Example Chart

**File:** `reports/ta/vwap_SPY_2026-06-18.png`

The chart shows the most recent available SPY session:
- **Top panel:** OHLC candles with VWAP overlaid in blue.
  Green shading = bars where close > VWAP. Red shading = bars where close < VWAP.
- **Bottom panel:** `dist_from_vwap` (green bars = above, red = below).

The VWAP is smooth and tracks price, sitting between intraday highs and lows,
consistent with its theoretical properties.

---

## 7. Honest Notes / Caveats

### Early-session VWAP is noisy
At bar 0 (09:30), VWAP = that bar's typical price exactly. VWAP converges
toward a session mean as more bars contribute volume. For the first 30–60 minutes
(bars 0–12), dist_from_vwap is volatile and should be interpreted cautiously in
downstream models. A session-bar filter (e.g., skip first 6 bars for VWAP
features) may improve signal quality.

### Zero-volume bars
Zero or near-zero volume is treated as no contribution to the VWAP weighted sum
(volume is clipped to 0 before the cumsum). This prevents division-by-zero for
halted tickers, but also means a zero-volume bar's VWAP equals the prior bar's
VWAP — which is the correct behavior (no new information).

### VWAP is not predictive (by construction)
This is a feature-build, not a backtest. VWAP describes where price has been
relative to the session's volume-weighted center of gravity. Whether VWAP
position predicts future returns is a separate OOS question not addressed here.

### No cross-session carries
VWAP resets each session. Pre-market or post-market bars are not in
`intraday_bars` (the ingest pipeline filters to RTH only), so there is no
ambiguity about session boundaries.

### Table isolation
`vwap_5m` is a net-new table. It does not alter `intraday_bars`, `pattern_memory`,
or any other existing table. The build script is read-only on all existing tables.

---

## 8. Files Created

| File | Purpose |
|------|---------|
| `src/atlas_research/ta/vwap.py` | Pure computation module (`compute_vwap_features`) |
| `db/migrations/0047_vwap_5m.sql` | DDL for `vwap_5m` table + indexes |
| `scripts/build_vwap_5m.py` | Resumable batch runner (full universe) |
| `scripts/render_vwap_chart.py` | One-session VWAP chart renderer |
| `reports/ta/vwap_SPY_2026-06-18.png` | Example chart (SPY latest session) |
| `reports/validity/VWAP_5M_REPORT.md` | This report |
| `reports/validity/vwap_5m.log` | Run log (appended each run) |

---

*No signal claims. No edge claims. This is descriptive infrastructure.*
*Whether VWAP position predicts anything is a later OOS question.*
