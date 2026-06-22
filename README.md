# Atlas Research Engine — Phase 1

Institutional-grade research database for Atlas Alpha ML workflows.
Standalone Python + PostgreSQL repository. Does not modify Atlas Alpha.

## What Phase 1 delivers

1. `raw_bars` — daily OHLCV stored from Yahoo Finance
2. `feature_snapshots` — EAV feature store (23 Phase-1 features)
3. `labels` — forward return labels at 1d, 5d, 10d, 20d, 60d horizons
4. `research_runs` — pipeline execution log
5. `production_export.py` — clean current-day feature output for Atlas Alpha

## Directory structure

```
atlas-research/
  README.md
  pyproject.toml
  .env.example
  config/
    settings.py          — all environment-based configuration
    universe.csv         — ticker universe (185 tickers + sector ETFs)
  db/
    schema.sql           — canonical 8-table PostgreSQL schema
    migrations/          — reserved for future Alembic migrations
  src/
    atlas_research/
      db/
        connection.py    — SQLAlchemy engine + get_connection()
        repository.py    — all DB reads/writes; EAV upsert + wide pivot
      ingest/
        yahoo_ingest.py  — download OHLCV; batched, retried
      features/
        trend.py         — SMA distances, above/below flags
        momentum.py      — returns, RSI, MACD histogram, ROC
        volatility.py    — ATR, realized vol
        volume.py        — relative volume, dollar volume
        relative_strength.py  — RS vs SPY at 20/60/120d
        regime.py        — SPY-based market regime (scaffolded)
        feature_factory.py   — orchestrates all modules → feature dict
      labels/
        label_factory.py — forward return labels + excursion stats
      pipelines/
        nightly_pipeline.py  — 8-step nightly orchestrator
      exports/
        production_export.py — Phase-1 export contract for Atlas Alpha
      utils/
        logging.py       — structlog structured logging
  scripts/
    init_db.py           — create schema + seed securities (run once)
    backfill_history.py  — download full history + features + labels
    run_nightly.py       — nightly entry point (cron or manual)
  tests/
    test_features.py     — pure feature computation tests (no DB)
    test_repository.py   — EAV pivot, label logic, export record tests
```

## Database tables

| Table | Description |
|---|---|
| `securities` | Master ticker list. Seeded from universe.csv. |
| `raw_bars` | Daily OHLCV. Primary key (ticker, date). |
| `feature_snapshots` | EAV feature store. One row per (ticker, date, feature_name). |
| `labels` | Forward return labels. One row per (ticker, date). |
| `research_runs` | Pipeline execution log. |
| `model_registry` | Trained model metadata (Phase 2). |
| `predictions` | Model output per ticker/date (Phase 2). |
| `production_exports` | Persisted export payloads. |

## Phase-1 features (23)

```
Returns:    return_1d, return_3d, return_5d, return_10d, return_20d, return_60d
Trend:      distance_sma20, distance_sma50, distance_sma200
            above_sma20, above_sma50, above_sma200
Momentum:   rsi_14, macd_histogram, roc_20
Volatility: atr_14, realized_vol_20, realized_vol_60
Volume:     volume_ratio_20, dollar_volume_20
RS vs SPY:  rs_spy_20, rs_spy_60, rs_spy_120
```

Regime features (spy_above_sma50, spy_above_sma200, market_trend, spy_return_20d)
are computed and stored alongside the Phase-1 features in the same EAV rows.

## EAV design rationale

`feature_snapshots` uses one row per (ticker, date, feature_name) rather than
wide columns. Benefits: new features added without ALTER TABLE; feature history
queryable by name; no null-column sprawl.

For ML training, call `repository.get_feature_matrix(date, feature_list)` which
pivots the EAV table into a wide DataFrame (tickers × features).

## Setup

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+ (separate instance from Atlas Alpha)

### 2. Install

```bash
git clone <repo> atlas-research && cd atlas-research
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure

```bash
cp .env.example .env
# Set DATABASE_URL to point at your PostgreSQL instance
```

### 4. Initialise database

```bash
python scripts/init_db.py
```

Creates all 8 tables and seeds the securities table from config/universe.csv.

### 5. Backfill history

```bash
python scripts/backfill_history.py
# Downloads 15 years of OHLCV, computes all features and labels
# First run: ~30-60 min depending on universe size and network speed
```

### 6. Run nightly

```bash
python scripts/run_nightly.py         # manual run
# or add to cron:
# 0 2 * * 1-5 cd /app && python scripts/run_nightly.py
```

### 7. Run tests

```bash
pytest tests/ -v
```

## Export contract (Phase 1)

```json
{
  "date": "2026-06-06",
  "ticker": "AAPL",
  "features": {
    "atr_14": 2.31,
    "distance_sma50": 0.021,
    "rsi_14": 58.3,
    "rs_spy_60": 0.043,
    "..."
  },
  "topDrivers": ["rs_spy_60", "distance_sma50", "volume_ratio_20"],
  "dataQuality": {
    "featuresPresent": 23,
    "featuresMissing": 0
  },
  "similaritySummary": null
}
```

`similaritySummary` is always `null` in Phase 1.
It will be populated in Phase 3 (similarity engine).

## Options data (Alpaca connector, research/backtesting only)

Options overlay is currently OI/reference-data based. It is not historical
trade-flow until OPRA/historical options tape is available.

- `scripts/options_check_account.py` -- confirm auth + options entitlement level
- `scripts/options_list_contracts.py` -- contract reference data + open interest for a few underlyings
- `scripts/options_market_data_test.py` -- probes/reports OPRA vs indicative feed entitlement
- `scripts/options_build_backtest_seed.py` -- merges the above into a single seed CSV
- `scripts/options_snapshot_universe.py` -- daily contract snapshot across an Atlas universe
- `scripts/options_build_oi_structure_features.py` -- per-ticker OI-structure features from that snapshot

See `docs/options_flow_data_limitations.md` for exactly what is and isn't
available on this account, and why. Every script in this connector defaults
to `paper=True`, reads credentials from `.env` only, never prints secrets,
and never calls an order-placing endpoint (enforced by
`tests/test_options_connector_safety.py`).

## What comes next

- **Phase 2**: LightGBM model training + model registry
  - Train on (feature_snapshots JOIN labels) query
  - Populate predictions table
  - Add probability_positive and expected_return to export payload

- **Phase 3**: Similarity engine + analog search
  - FAISS HNSW index on feature embeddings
  - Populate similaritySummary in export payload

- **Phase 4**: Atlas Alpha integration
  - Atlas Alpha reads from production_exports instead of computing its own scores
