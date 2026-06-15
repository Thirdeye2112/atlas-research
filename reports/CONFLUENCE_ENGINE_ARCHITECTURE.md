# Atlas Confluence Engine v1 — Architecture

**Date:** 2026-06-14
**Status:** Architecture complete, ready for integration
**Scope:** Experimental scoring overlay — does NOT replace Atlas Score, does NOT modify UI

---

## Purpose

The Confluence Engine answers: *"How many historically validated signals agree on this ticker right now?"*

Atlas Score measures technical quality. Confluence measures **signal alignment** — the degree to which independent evidence sources point in the same direction, weighted by their historical predictive quality. A high confluence score (80+) means multiple validated systems simultaneously flag an opportunity. A low score (20-40) means signals disagree or data is thin.

**Score interpretation:**
| Range  | Meaning |
|--------|---------|
| 80-100 | Strong multi-signal alignment, good regime fit, low risk |
| 60-80  | Moderate agreement, some divergence |
| 40-60  | Mixed or weak signals |
| 0-40   | Disagreement, data gaps, or high risk |

The score is **not directional** — `confluence_direction` carries the direction separately.

---

## Files Created

```
db/migrations/
    0030_confluence_tables.sql       — 3 new tables

src/atlas_research/confluence/
    __init__.py                      — public API: run_confluence, score_ticker
    engine.py                        — orchestrator; loads parquet, calls all components
    alignment.py                     — counts bullish/bearish/neutral signals
    score.py                         — 0-100 quality formula with regime + risk adjustments
    repository.py                    — DB reads/writes for all 3 confluence tables
    components/
        __init__.py
        base.py                      — ComponentResult dataclass
        ml.py                        — ML component (predictions table)
        pattern.py                   — Conditional pattern component
        probability.py               — Calibrated signal component
        feature_ic.py                — Feature IC / regime sensitivity component
        regime.py                    — Market regime component + fitness lookup
        risk.py                      — Risk penalty component

scripts/
    run_confluence.py                — CLI runner with --date, --ticker, --top flags
```

---

## Database Schema

### `confluence_score_runs`
Tracks each scoring run.

| Column         | Type        | Notes |
|----------------|-------------|-------|
| id             | BIGSERIAL PK |      |
| run_date       | DATE         |      |
| run_at         | TIMESTAMPTZ  |      |
| engine_version | TEXT         | 'v1' |
| n_tickers      | INTEGER      |      |
| notes          | TEXT         |      |

### `confluence_score_snapshots`
One row per (ticker, date, engine_version).

| Column                     | Type   | Notes |
|----------------------------|--------|-------|
| ticker                     | TEXT   |       |
| snapshot_date              | DATE   |       |
| engine_version             | TEXT   | 'v1'  |
| confluence_score           | FLOAT  | 0-100 |
| confluence_direction       | TEXT   | bullish \| bearish \| neutral |
| confluence_probability     | FLOAT  | ML probability_positive |
| confluence_expected_return | FLOAT  | ML expected return |
| confluence_risk            | FLOAT  | 0-1 normalised risk |
| aligned_signal_count       | INT    |       |
| conflicting_signal_count   | INT    |       |
| neutral_signal_count       | INT    |       |
| total_signal_count         | INT    |       |
| regime                     | TEXT   | bull \| bear \| range |
| vol_regime                 | TEXT   | high_vol \| low_vol |

### `confluence_score_components`
One row per (snapshot_id, component_name) — 6 rows per ticker per run.

| Column         | Type   | Notes |
|----------------|--------|-------|
| snapshot_id    | BIGINT | FK -> snapshots |
| ticker         | TEXT   |       |
| snapshot_date  | DATE   |       |
| component_name | TEXT   | ml \| pattern \| probability \| feature_ic \| regime \| risk |
| signal         | TEXT   | bullish \| bearish \| neutral |
| strength       | FLOAT  | 0-1  |
| score          | FLOAT  | 0-100 component quality |
| weight         | FLOAT  | fraction of final score |
| available      | BOOL   | False when data is absent |
| details        | JSONB  | component-specific metadata |

---

## Components

### 1. ML Component (weight: 30%)
**Source:** `predictions` table
**Fields read:** `probability_positive`, `expected_return`, `confidence`, `rank_percentile`
**Direction logic:**
- `probability_positive > 0.55` → bullish
- `probability_positive < 0.45` → bearish
- else → neutral

**Strength:** blend of probability extremeness + cross-sectional rank percentile
**Score:** top-decile rank * confidence → maps to 50-100 for bullish, 50-100 for bearish

---

### 2. Pattern Component (weight: 20%)
**Source:** `conditional_patterns`, `conditional_pattern_results`
**Logic:** Queries market-wide patterns (ticker IS NULL) with `sample_size >= 20`.
Each pattern is tested for trigger against current feature row values. Triggered patterns
with `hit_rate >= 0.55` and positive `avg_return_5d` vote bullish; negative vote bearish.

**v1 pattern triggers evaluated:**
- `consecutive_down/up` — from `return_Nd`
- `oversold/overbought_rsi` — from `rsi_14`
- `gap_down` — from `return_1d`
- `near_52w_low/high` — from `dist_52w_low/high`
- `high_volume` — from `rvol_20`

*Ticker-specific pattern triggers require per-event evaluation — planned for v2.*

---

### 3. Probability Component (weight: 20%)
**Source:** `alpha_signal_calibrations`
**Logic:** Queries promoted signals (`status='promoted'`, `sanity_pass=TRUE`,
`n_resolved >= 30`, `hit_rate_5d >= 0.55`). Each active signal is weighted by
`(hit_rate - 0.5) * min(n_resolved/200, 1)`. Bullish fraction vs bearish fraction
determines direction.

**Active signal checks (v1):**
- `direction` → `atlas_direction` feature value
- `score_bucket` → `atlas_score` or `rank_percentile`
- `pattern` → `patterns` JSONB list
- `exhaustion` → `exhaustion_signal` column
- `smart_gate` → `smart_gate_enter` boolean

---

### 4. Feature IC Component (weight: 10%)
**Source:** `feature_regime_performance`
**Logic:** For the current regime (above_200dma / below_200dma / bull / bear),
queries features with `|mean_ic| >= 0.008` and `classification IN ('Always Useful',
'Regime Sensitive')`. For each such feature, evaluates the ticker's raw feature value
against IC sign to determine direction contribution:

```
sign = +1 if (IC > 0) == (value > 0) else -1   # positive IC + positive value = bullish
weighted_ic = |IC| * sign * sign_stability
```

Bullish vs bearish IC-weighted mass determines direction.

---

### 5. Regime Component (weight: 15%)
**Source:** `spy_above_sma200`, `market_trend`, `realized_vol_20/60` from feature row
**Logic:** Classifies market as bull / bear / range. Determines volatility regime.
Contributes a directional signal when regime is clear (bull + above 200DMA = bullish).

**Regime fitness multipliers** (applied to pre-regime score):
| Regime | Signal Direction | Fitness |
|--------|-----------------|---------|
| bull   | bullish         | 1.00    |
| bull   | bearish         | 0.72    |
| bear   | bearish         | 1.00    |
| bear   | bullish         | 0.72    |
| range  | either          | 0.88    |

---

### 6. Risk Component (weight: 5%, penalty only)
**Source:** Feature row values
**Logic:** Computes a penalty (0-25 points) deducted from final score. Does NOT contribute
a directional signal.

| Risk Flag                     | Penalty |
|-------------------------------|---------|
| `data_quality_score < 0.70`   | -10 pts |
| `data_quality_score < 0.80`   | -4 pts  |
| `dollar_volume_20 < $1M`      | -10 pts |
| `dollar_volume_20 < $5M`      | -4 pts  |
| `expected_drawdown < -5%`     | -5 pts  |
| `expected_drawdown < -2%`     | -2 pts  |
| `atr_pct > 6%`                | -3 pts  |

---

## Scoring Formula

```
# 1. Alignment
dominant_direction = sign(bull_weight - bear_weight)   # +1, -1, 0
alignment_ratio = aligned_count / total_available      # 0-1

# 2. Base quality
avg_strength = weighted avg strength of aligned components (excl. regime, risk)
base = (0.65 * avg_strength + 0.35 * alignment_ratio) * 100

# 3. Regime fitness adjustment
base_regime = base * regime_fitness(market_regime, dominant_direction)

# 4. Risk penalty
final = base_regime - risk_penalty                     # clamped 0-100
```

When dominant_direction = 0 (no consensus), base is forced to 20-30 regardless
of individual component strength.

---

## Alignment Engine

```python
bull_weight = sum(c.strength * c.weight for c in active if c.direction == +1)
bear_weight = sum(c.strength * c.weight for c in active if c.direction == -1)

# 15% buffer to avoid flip-flopping on marginal differences
if bull_weight > bear_weight * 1.15: dominant = "bullish"
elif bear_weight > bull_weight * 1.15: dominant = "bearish"
else: dominant = "neutral"
```

---

## API Contract

**Route:** `GET /api/research/confluence/:ticker`

**Response shape (sample):**
```json
{
  "ticker": "AAPL",
  "snapshot_date": "2026-06-14",
  "confluence_score": 74.3,
  "confluence_direction": "bullish",
  "confluence_probability": 0.63,
  "confluence_expected_return": 0.0118,
  "confluence_risk": 0.08,
  "aligned_signal_count": 3,
  "conflicting_signal_count": 1,
  "neutral_signal_count": 1,
  "total_signal_count": 5,
  "regime": "bull",
  "vol_regime": "low_vol",
  "components": {
    "ml":           { "signal": "bullish", "strength": 0.64, "score": 80.2, "available": true },
    "pattern":      { "signal": "bullish", "strength": 0.42, "score": 42.0, "available": true },
    "probability":  { "signal": "neutral", "strength": 0.15, "score": 30.0, "available": true },
    "feature_ic":   { "signal": "bullish", "strength": 0.58, "score": 58.0, "available": true },
    "regime":       { "signal": "bullish", "strength": 0.70, "score": 65.0, "available": true },
    "risk":         { "signal": "neutral", "strength": 0.08, "score":  0.0, "available": true,
                      "details": { "total_penalty": 2.0, "flags": ["moderate_drawdown"] } }
  }
}
```

**Implementation note:** This route should be added to atlas-alpha's research API.
The Python data is available via `repository.get_latest_snapshot(ticker)` and
`repository.get_components_for_snapshot(snapshot_id)`.

---

## CLI Usage

```bash
# Score all tickers for today's parquet
python scripts/run_confluence.py

# Score a specific date
python scripts/run_confluence.py --date 2026-06-14

# Score subset of tickers
python scripts/run_confluence.py --ticker AAPL MSFT NVDA

# Print top 30 bullish only
python scripts/run_confluence.py --top 30 --direction bullish
```

---

## Integration with Existing Systems

| System | Integration Point |
|--------|-------------------|
| Atlas Score | None — confluence is additive, not a replacement |
| ML Pipeline | `run_confluence.py` reads same parquet as `run_predict.py` |
| Predictions table | `confluence/components/ml.py` reads `predictions` table |
| Pattern engine | `confluence/components/pattern.py` reads `conditional_pattern_results` |
| Calibration | `confluence/components/probability.py` reads `alpha_signal_calibrations` |
| Regime study | `confluence/components/feature_ic.py` reads `feature_regime_performance` |
| Schedule | Run after nightly predict pass (confluence requires up-to-date predictions) |

---

## What V2 Should Add

1. **Per-ticker pattern triggers**: evaluate whether each `conditional_pattern` actually fired for this ticker on this date (requires event-level check against raw bars)
2. **OSCAR/OMNI proximity signal**: standalone OSCAR component reading `omni_82_above/distance` with regime context
3. **Sector RS component**: add sector relative strength as a 7th component
4. **Historical calibration**: backtest confluence scores against forward returns to validate score buckets
5. **Atlas-alpha UI card**: small "confluence" widget on the ticker detail page
6. **Alert system**: notify when confluence_score >= 75 and direction == "bullish" for watchlist tickers

---

## Deployment Checklist

- [ ] Apply migration: `psql $DATABASE_URL -f db/migrations/0030_confluence_tables.sql`
- [ ] Run initial score: `python scripts/run_confluence.py --date 2026-06-14`
- [ ] Verify DB rows: `SELECT COUNT(*) FROM confluence_score_snapshots`
- [ ] Add route to atlas-alpha: `GET /api/research/confluence/:ticker`
- [ ] Add to nightly pipeline after predict step
