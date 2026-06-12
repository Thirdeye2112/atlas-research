# CONSENSUS — Key Research Findings

## Jarvis Indicator (UI name for OMNI — Oscar Carboni's proprietary)

**Confirmed formula:** EMA(Low, 82)  
**Backtested on:** SPY daily bars, 2011-2026 (n=3,750 bars)

### Why EMA of Lows?

Oscar describes OMNI as "landing on the bottom of candles." Standard close-based EMA sits *through* the body; EMA of lows sits at the candle *floor*.

Variant comparison results:

| Variant        | Above Lows % | Avg Dist Low % | Cross-Up Hit% (5d) | n signals |
|----------------|-------------|----------------|---------------------|-----------|
| **ema_lows_82**| **99.1%**   | **+0.47%**     | **55.3%**           | 94        |
| ema_lows_87    | 99.0%       | +0.51%         | 54.3%               | 91        |
| ema_lows_89    | 99.1%       | +0.53%         | 54.0%               | 90        |
| hma_82         | 97.2%       | +0.50%         | 56.1%               | 94        |
| ema_lows_55    | 97.4%       | +0.28%         | 52.1%               | 108       |
| ema_close_87   | 90.3%       | +1.44%         | 52.1%               | 88        |

**Why period 82:** Highest `above_lows_pct` combined with a compact average distance (+0.47%) — it sits just above lows without floating too high.

### SPY Cross-Up Hit Rates (SPY-specific, 2011-2026)

| Horizon | Hit Rate | Avg Return | n    |
|---------|---------|------------|------|
| 1d      | 51.1%   | +0.16%     | 94   |
| 5d      | 55.3%   | +0.44%     | 94   |
| 10d     | 60.6%   | +0.88%     | 94   |
| **20d** | **81.9%**| **+1.74%** | **94** |

The 20-day result is exceptional. When SPY's close crosses above OMNI(82), 82% of the time SPY is higher 20 trading days later.

### ML Features (added to ALL_FEATURES, v1.5)

| Feature          | Description                                           |
|------------------|-------------------------------------------------------|
| `omni_82_value`  | Raw EMA(Low, 82) indicator value                      |
| `omni_82_above`  | 1.0 if Close > OMNI, else 0.0                         |
| `omni_82_distance` | (Close − OMNI) / OMNI — % above or below            |
| `omni_82_slope`  | (OMNI − OMNI[−5]) / OMNI[−5] — fractional trend     |
| `omni_82_bounce` | 1.0 if Low within 0.5% of OMNI and Close > Open      |

### Conditional Patterns (migration 0015)

- `omni_82_cross_up` / `omni_82_cross_down` — trend change signals
- `omni_82_above_3d` / `omni_82_above_5d` — sustained above OMNI
- `omni_82_bounce` / `omni_82_bounce_1pct` — support hold entry
- `omni_82_green_slope` — above OMNI with rising OMNI (strongest)

---

## OSCAR Oscillator

**Formula:** `A = max(High, N); B = min(Low, N); rough = (Close - B)/(A - B)*100; oscar[i] = oscar[i-1]*2/3 + rough*1/3`

A smoothed stochastic oscillator (0–100 range). Cross above 50 = bullish signal.

### SPY Cross-Up Hit Rates by Period

| Period | n signals | Hit% 5d | Avg Ret% |
|--------|-----------|---------|---------|
| 8      | 188       | 61.2%   | 0.195%  |
| 21     | 92        | 62.0%   | 0.088%  |
| 34     | 64        | 64.1%   | 0.054%  |
| 55     | 51        | **76.5%** | **0.540%** |
| 87     | 33        | 69.7%   | 0.858%  |
| 89     | 33        | 72.7%   | 0.790%  |

Period 55 has best hit rate; period 87 has best return-per-signal.

---

## Calendar Conditional Patterns (migration 0018)

Backtested on SP500 aggregate (2019-2026).

| Pattern           | Horizon | N      | Hit%  | Avg Ret | p-value | Notes                              |
|-------------------|---------|--------|-------|---------|---------|-------------------------------------|
| `fomc_day`        | 5d      | 10,742 | 50.9% | −0.23%  | <0.001  | Flat 5d; mean-reversion risk        |
| `fomc_day`        | 20d     | 10,742 | 58.2% | +0.89%  | <0.001  | Bullish 20d after FOMC              |
| `opex_week`       | 5d      | 78,474 | 53.8% | +0.22%  | <0.001  | Mild bullish bias in OPEX week      |
| `opex_week`       | 20d     | 78,474 | 58.8% | +1.13%  | <0.001  | Strong 20d bullish drift            |
| `month_end_3d`    | 5d      | 95,271 | 55.2% | +0.32%  | <0.001  | Month-end effect confirmed          |
| `month_end_3d`    | 20d     | 95,271 | 57.1% | +0.89%  | <0.001  | Consistent 20d positive drift       |

**Key insight:** FOMC day is weak/negative at 1-5d horizon but consistently bullish at 20d. Month-end and OPEX week show reliable bullish drift across horizons.

---

## Sector Rotation Patterns (migration 0019)

Using `sector_relative_strength` table (38,638 rows, 11 SPDR ETFs, 2011-2026).

| Pattern            | Horizon | N     | Hit%      | Avg Ret   | p-value | Interpretation                    |
|--------------------|---------|-------|-----------|-----------|---------|-----------------------------------|
| `xlv_leading_20d`  | 5d      | 30    | **86.7%** | +0.91%    | 0.004   | XLV top-2 for 20d → very bullish  |
| `xlv_leading_20d`  | 10d     | 30    | **83.3%** | +1.16%    | 0.002   |                                   |
| `xlv_leading_20d`  | 20d     | 30    | **93.3%** | +2.63%    | <0.001  | Best single pattern found         |
| `xle_leading_20d`  | 5d      | 199   | 53.3%     | −0.08%    | 0.660   | Not significant short-term        |
| `xle_leading_20d`  | 20d     | 199   | 65.8%     | +1.06%    | 0.002   | Inflation regime = bullish 20d    |
| `xly_vs_xlp`       | 5d      | 2,139 | 60.7%     | +0.20%    | <0.001  | Risk-on rotation confirmed        |
| `xly_vs_xlp`       | 20d     | 2,139 | 67.7%     | +0.85%    | <0.001  | Discretionary > Staples = bullish |

**Key insight:** `xlv_leading_20d` is the strongest SPY pattern found — **93.3% 20d hit rate** (n=30, p<0.001). When Health Care has led for 20 consecutive days, SPY continues higher. The XLY > XLP risk-on signal (n=2,139) is the most statistically robust.

---

## ML Model Quality (v1.5 — retrained 2026-06-11)

**Walk-forward results after Jarvis (OMNI) backfill (192/192 tickers):**

| Metric | v1.4 (pre-Jarvis) | v1.5 (post-Jarvis) | Change |
|--------|----------------|-----------------|--------|
| WF Mean IC | 0.0269 | **0.0546** | +103% (doubled) |
| WF Folds | 5 | **12** | +7 folds |
| Mean AUC | ~0.51 | **0.5239** | +0.014 |
| Features | 27 | **33** | +6 OMNI features |

**Top features by regressor gain (model `2025-07-01`):**

| Rank | Feature | Gain | Note |
|------|---------|------|------|
| 1 | above_sma20 | 119 | |
| **2** | **omni_82_above** | **96** | OMNI confirmed top-2 |
| **3** | **omni_82_bounce** | **58** | Support bounce signal |
| 4 | above_sma200 | 54 | |
| 5 | spy_above_sma50 | 52 | |

**Classifier top-5:** above_sma20 (56,722) → above_sma200 (54,166) → omni_82_above (50,666) → spy_above_sma50 (48,476) → omni_82_bounce (40,164)

**Edge tier:** IC 0.0546 = "Moderate edge" (threshold: <0.02 Early stage, <0.04 Developing, <0.06 Moderate edge, ≥0.06 Strong edge)

---

## Current System State (as of 2026-06-11)

### Infrastructure
- **Migrations applied:** 0001 through 0019
- **Tables:** raw_bars, feature_snapshots, model_registry, conditional_patterns, conditional_pattern_results, sector_relative_strength, market_calendar, transcript_sessions, transcript_chunks

### ML Pipeline
- **Features:** 33 (PHASE1 + REGIME + OMNI_82 x5)
- **OMNI backfill:** complete — 192/192 tickers have `omni_82_above`
- **Current model:** v1.5 (33 features, post-OMNI), trained through 2025-07-01, WF IC=0.0546
- **Model artifact:** `models/return_regressor_v1_2025-07-01/model.joblib`

### Conditional Probability Engine
- **Patterns:** 95+ (migrations 0010-0019)
- **Evaluators:** 39 (includes calendar + sector rotation types)
- **Latest results:** xlv_leading_20d 93.3% 20d, xly_vs_xlp 60.7% 5d

### Data
- **Universe:** 194 tickers (universe.csv)
- **Sector ETFs:** 11 SPDR ETFs + SPY tracked in sector_relative_strength
- **Market calendar:** 271 events (73 FOMC, 108 OPEX, 36 quarter-end, 36 triple witching, 18 half-year)
- **Transcripts:** 829 sessions found, 150 chunks stored (extraction pending API key)

### API Endpoints
- `GET /api/research/conditional/spy` — SPY streak + calendar_context
- `GET /api/research/conditional/context/:ticker` — active patterns
- `GET /api/research/conditional/pattern/:name` — full pattern stats
- `GET /api/research/sectors/snapshot` — today's sector RS rankings + regime
- `GET /api/research/sectors/history/:ticker` — sector RS history (60d)
- `GET /api/research/signal/:ticker` — ML signal (includes OMNI features)

### UI Components (Dashboard.tsx)
- `MLSignalBadge` — ML prediction + OMNI indicator
- `ConditionalNarrative` — active conditional patterns
- `SectorRotationBadge` — today's sector rotation + regime label

---

## Implementation Files

- `src/atlas_research/features/omni_proxy.py` — all indicator functions
- `src/atlas_research/conditional/engine.py` — 39 condition evaluators (incl. calendar + sector)
- `scripts/compute_sector_rs.py` — computes sector_relative_strength table
- `scripts/seed_market_calendar.py` — seeds market_calendar table
- `scripts/run_conditional_calendar.py` — calendar context detector + backtests
- `db/migrations/0013_omni_oscar_patterns.sql` — OSCAR/OMNI-87 patterns
- `db/migrations/0014_omni_lows_patterns.sql` — EMA-of-lows variants
- `db/migrations/0015_omni_82_patterns.sql` — OMNI-82 confirmed patterns
- `db/migrations/0016_sector_relative_strength.sql` — sector RS table
- `db/migrations/0017_market_calendar.sql` — market calendar table
- `db/migrations/0018_calendar_patterns.sql` — calendar conditional patterns
- `db/migrations/0019_sector_rotation_patterns.sql` — sector rotation patterns
- `config/settings.py` — OMNI_FEATURES added to ALL_FEATURES
