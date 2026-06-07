# Atlas Research Engine — Architecture

> Institutional-grade research database and ML pipeline.  
> Companion system to Atlas Alpha (Node/Express + React).  
> Built across Phases 1, 1.5, and 2 — June 2026.

---

## Contents

1. [System Overview](#1-system-overview)
2. [Repository Layout](#2-repository-layout)
3. [Database Schema](#3-database-schema)
4. [Feature Pipeline](#4-feature-pipeline)
5. [Validation Layer](#5-validation-layer)
6. [Parquet Export](#6-parquet-export)
7. [ML Pipeline — Phase 2](#7-ml-pipeline--phase-2)
8. [Atlas Alpha Integration](#8-atlas-alpha-integration)
9. [Configuration Reference](#9-configuration-reference)
10. [Run Sequence](#10-run-sequence)
11. [Interpretation Thresholds](#11-interpretation-thresholds)
12. [Architectural Decisions](#12-architectural-decisions)
13. [Deferred / Future Work](#13-deferred--future-work)

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Atlas Alpha                             │
│  Node/Express API  ·  Vite/React UI  ·  Drizzle/Postgres   │
│                                                             │
│  /api/research/*  (read-only, 5 endpoints)                  │
│         │                                                   │
│         └─── pg.Pool ──► DATABASE_URL_RESEARCH              │
└─────────────────────────────────────────────────────────────┘
                              │
                    (separate Postgres instance)
                              │
┌─────────────────────────────────────────────────────────────┐
│                 Atlas Research Engine                        │
│  Python · PostgreSQL · LightGBM · Parquet                   │
│                                                             │
│  nightly_pipeline.py                                        │
│    ├── yahoo_ingest     → raw_bars                          │
│    ├── validate         → data_quality_score                │
│    ├── feature_factory  → feature_snapshots (EAV)           │
│    ├── label_factory    → labels                            │
│    ├── parquet_export   → exports/parquet/*.parquet         │
│    └── production_export → production_exports               │
│                                                             │
│  run_training.py (walk-forward LightGBM)                    │
│    ├── dataset.py       ← parquet files                     │
│    ├── evaluate.py      → metrics                           │
│    ├── walk_forward.py  → model_registry, feature_perf      │
│    ├── train.py         → models/*.joblib                   │
│    └── predict.py       → predictions                       │
└─────────────────────────────────────────────────────────────┘
```

**Key isolation guarantee:** Atlas Alpha's Drizzle-managed database and the Research Engine database are completely separate Postgres instances. Research jobs, migrations, and training loads cannot affect Atlas Alpha's API latency or tables.

---

## 2. Repository Layout

```
atlas-research/
├── config/
│   └── settings.py              All configuration (plain module, no Pydantic)
├── db/
│   └── schema.sql               Canonical schema — run once via init_db.py
├── exports/
│   └── parquet/                 Daily parquet files (ML substrate)
│       └── feature_matrix_YYYY-MM-DD.parquet
├── models/                      Saved model artifacts (joblib)
│   └── {name}_{version}_{date}/model.joblib
├── scripts/
│   ├── init_db.py               One-time DB setup + seed
│   ├── backfill_history.py      Cold-start: download + features + parquet
│   ├── run_nightly.py           Incremental nightly run
│   ├── run_training.py          Walk-forward training entry point
│   └── inspect_results.py       Post-training diagnostic tool
├── src/atlas_research/
│   ├── db/
│   │   ├── connection.py        SQLAlchemy engine + get_connection()
│   │   └── repository.py        All DB reads/writes
│   ├── exports/
│   │   ├── parquet_export.py    Wide matrix → daily parquet
│   │   └── production_export.py JSON export → production_exports table
│   ├── features/
│   │   ├── trend.py             (close) → numpy → distance/above SMA
│   │   ├── momentum.py          (close) → numpy → returns, RSI, MACD, ROC
│   │   ├── volatility.py        (close, high, low) → ATR, realized vol
│   │   ├── volume.py            (close, volume) → ratio, dollar volume
│   │   ├── relative_strength.py (close, spy_close) → RS vs SPY
│   │   ├── regime.py            (spy_close) → market trend flags
│   │   └── feature_factory.py   Pandas→numpy boundary; two entry points
│   ├── ingest/
│   │   ├── yahoo_ingest.py      Batched OHLCV download (yfinance)
│   │   └── validate.py          Severity-based validation (FATAL/WARNING)
│   ├── labels/
│   │   └── label_factory.py     Forward return labels (5 horizons)
│   ├── models/
│   │   ├── dataset.py           Load parquet → arrays; quality filter; purge
│   │   ├── evaluate.py          Brier, AUC, Rank IC, IC t-stat, Sharpe
│   │   ├── train.py             LightGBM regressor + classifier + Platt
│   │   ├── walk_forward.py      Expanding-window WF + baseline mode
│   │   └── predict.py           Score live universe → predictions table
│   ├── pipelines/
│   │   └── nightly_pipeline.py  10-step orchestrator
│   └── utils/
│       └── logging.py           structlog configuration
├── tests/
│   ├── test_features.py
│   ├── test_validation.py
│   ├── test_parquet_export.py
│   └── test_models.py
└── artifacts/                   Drop-in files for Atlas Alpha
    ├── api-server/src/routes/
    │   └── research.ts          5 read-only Express endpoints
    └── api-client-react/src/pages/
        └── ResearchLab.tsx      Research Lab React page
```

---

## 3. Database Schema

All tables live in the Research Engine Postgres instance (`DATABASE_URL_RESEARCH`). Atlas Alpha never writes to this database.

### Core tables

| Table | Purpose | Key columns |
|---|---|---|
| `securities` | Universe registry | `ticker, name, sector, industry, active` |
| `raw_bars` | OHLCV from Yahoo Finance | `ticker, date, open, high, low, close, adjusted_close, volume` |
| `feature_snapshots` | EAV feature store | `ticker, date, feature_name, feature_value, feature_version, snapshot_version` |
| `feature_metadata` | Feature registry | `feature_name, category, source_module, description, data_type, active` |
| `labels` | Forward return labels | `ticker, date, return_5d, return_20d, positive_5d, positive_20d` |
| `research_runs` | Pipeline audit log | `run_type, status, started_at, finished_at, tickers_processed` |
| `model_registry` | Trained model metadata | `model_name, model_version, target, horizon, rank_ic, auc, brier, artifact_path` |
| `predictions` | Daily model scores | `ticker, date, model_name, expected_return, probability_positive, rank_percentile` |
| `production_exports` | JSON export snapshots | `export_date, export_type, payload (jsonb)` |
| `feature_performance` | Per-feature IC diagnostics | `feature_name, model_version, target, horizon_days, eval_start, spearman_ic, lgbm_gain` |

### Critical indexes

```sql
-- Point-in-time reproducibility
CREATE INDEX idx_feature_snapshots_version_ticker_date
  ON feature_snapshots(snapshot_version, ticker, date);

-- Prediction serving
CREATE INDEX idx_predictions_ticker_date
  ON predictions(ticker, date DESC);

-- Feature IC queries
CREATE INDEX idx_feature_perf_name_model
  ON feature_performance(feature_name, model_version, target);
```

### `feature_performance` vs `model_registry`

These tables have different purposes and must not be conflated:

- **`feature_performance`**: per-feature IC diagnostics. Answers "which features have predictive power?" Row = (feature, model version, target, horizon, eval window). `spearman_ic` here is a *feature-level* correlation with the target, not a model-level metric.
- **`model_registry`**: per-fold model performance. Answers "how good is the model?" Row = one trained model (one fold). `rank_ic` here is the Spearman correlation between the *model's predictions* and outcomes on the validation set.

**Health strip IC metrics come from `model_registry.rank_ic` only.** `wf_mean_rank_ic` = `AVG(rank_ic)` across rows grouped by `(model_version, target, horizon)`.

---

## 4. Feature Pipeline

### Feature set (Phase 1 — 27 features)

**Phase-1 features (23):** Returns (1d, 3d, 5d, 10d, 20d, 60d), Trend (distance\_sma20/50/200, above\_sma20/50/200), Momentum (rsi\_14, macd\_histogram, roc\_20), Volatility (atr\_14, realized\_vol\_20/60), Volume (volume\_ratio\_20, dollar\_volume\_20), Relative Strength (rs\_spy\_20/60/120)

**Regime features (4):** spy\_above\_sma50, spy\_above\_sma200, spy\_return\_20d, market\_trend

**Training features (28):** `ALL_FEATURES` + `data_quality_score`

### Purity contract

All feature modules (`trend.py`, `momentum.py`, etc.) accept `numpy.ndarray` only — zero pandas imports. `feature_factory.py` owns the single pandas→numpy conversion boundary. This makes future Polars migration a one-file change.

```python
# Two entry points
build_features(ticker, bars_df, spy_bars_df)          # pandas DataFrames in
build_features_from_arrays(close, high, low, vol, spy) # numpy arrays in
# Both produce identical outputs — enforced by tests
```

### EAV storage

Features are stored in EAV format (`feature_name, feature_value` per row) with `snapshot_version` tagging. The version enables point-in-time reproducibility: re-running training with `snapshot_version = 'run_2026-06-06'` gives identical feature inputs.

Parquet files are the canonical ML substrate — they are pre-pivoted to wide format with labels already joined.

### Backfill optimization

The backfill script uses a **ticker-loop** (not a date-loop):

```
For each ticker:
  Load full history once (1 DB query)
  For each date:
    Slice to point-in-time bars
    Compute features
    Upsert to feature_snapshots
```

This is O(tickers) DB queries, not O(dates × tickers). For 185 tickers × 15 years = 693,750 avoided queries.

---

## 5. Validation Layer

Every ticker's bars are validated before feature computation. Two severity levels:

### FATAL — ticker skipped entirely

| Check | Reason |
|---|---|
| No bars / empty DataFrame | Nothing to compute |
| Insufficient bars (< 15) | All features would be None |
| Missing required columns | Schema violation |
| NaN rate ≥ 2% | Data too corrupt to trust |
| Zero or negative prices | Impossible in live market; feed error |
| Duplicate dates | Primary key violation; wrong features |
| Flat prices (last N identical) | Feed is stuck; all indicators meaningless |

### WARNING — ticker proceeds with reduced quality score

| Check | Penalty |
|---|---|
| NaN rate < 2% | −0.05 |
| Date gap > 5 calendar days | −0.10 |
| Volume outlier (> 20× 20-day mean) | −0.15 |
| Adjustment anomaly (adj/raw ratio > 3×) | −0.20 |
| Future date (last bar after snap_date) | −0.05 |

`data_quality_score = 1.0 − sum(warning penalties)`, clamped to [0.0, 1.0].

Both `data_quality_score` and `data_quality_flags` (pipe-separated warning names) are written as columns in the parquet matrix and available to the model as features.

---

## 6. Parquet Export

One file per trading date: `exports/parquet/feature_matrix_YYYY-MM-DD.parquet`

### Schema (wide, one row per ticker)

```
ticker                 TEXT      — primary identifier
date                   DATE      — snapshot date
return_1d … rs_spy_120 FLOAT64   — 27 feature columns (ALL_FEATURES)
data_quality_score     FLOAT64   — 1.0 = clean; lower = warnings
data_quality_flags     TEXT      — "volume_outlier|nan_prices_low"
label_return_5d        FLOAT64   — NULL until T+5 bars exist
label_return_20d       FLOAT64
label_positive_5d      BOOL
label_positive_20d     BOOL
```

### Why parquet

- Columnar: training reads only needed features
- Compressed: ~10× smaller than CSV (snappy default)
- Typed: float64/bool preserved exactly
- Ecosystem: pandas, polars, arrow, spark, dask all read natively
- Labels left-joined: training does `df[df['label_return_5d'].notna()]` with no subsequent JOIN

---

## 7. ML Pipeline — Phase 2

### Models

| Model | Target | Algorithm |
|---|---|---|
| `return_regressor` | `label_return_5d` (float) | LightGBM regression + MSE |
| `positive_classifier` | `label_positive_5d` (0/1) | LightGBM binary + Platt calibration |

Both models use the same 28-feature input (`ALL_FEATURES + data_quality_score`).

### Quality filter (hard)

Rows with `data_quality_score < 0.70` are excluded from training before any model sees them. `data_quality_score` is also included as a training feature so the model can condition on data quality.

### Walk-forward validation

**Expanding window** — one model_registry row per fold:

```
Fold 1:  train 2010–2012  →  val 2013
Fold 2:  train 2010–2013  →  val 2014
...
Fold N:  train 2010–2022  →  val 2023
```

**Purge gap:** 5 trading days removed from the end of each training set before the validation window. Prevents 5-day label leakage (a bar on day T with `return_5d` uses prices through T+5).

**Parallel folds:** `WF_PARALLEL_FOLDS=1` (sequential). Placeholder comment in `walk_forward.py` for future `ProcessPoolExecutor`. Correctness must be proven on real data before parallelising.

### Metrics (per fold)

| Metric | Applies to | Interpretation |
|---|---|---|
| `rank_ic` | Regression | Spearman ρ(predictions, outcomes). Primary signal quality metric. |
| `mean_ic` | Regression | Mean daily cross-sectional IC across dates in val window |
| `sharpe` | Both | Annualised Sharpe of long-top-5 / short-bottom-5 portfolio |
| `auc` | Classification | ROC AUC of probability model |
| `brier` | Classification | Mean squared error of probabilities (baseline = 0.25) |

### Artifact storage

```
models/
  return_regressor_v1_2022-12-31/
    model.joblib   (TrainedModelBundle: regressor + classifier + Platt + importances)
```

SHA-256 hash stored in `model_registry.artifact_hash` for audit.

### Prediction columns

| Column | Source |
|---|---|
| `expected_return` | Regressor output (log return) |
| `probability_positive` | Platt-calibrated classifier probability |
| `expected_drawdown` | `min(expected_return, 0)` — proxy for downside |
| `confidence` | `abs(probability_positive − 0.5) × 2` — 0 = uncertain, 1 = certain |
| `rank_percentile` | Cross-sectional percentile rank of probability_positive |

---

## 8. Atlas Alpha Integration

### Files to drop in

```
artifacts/api-server/src/routes/research.ts    → copy to Atlas Alpha API routes
artifacts/api-client-react/src/pages/ResearchLab.tsx  → copy to Atlas Alpha pages
```

### Registration (index.ts)

```typescript
import { researchRouter } from './routes/research.js'
app.use('/api/research', researchRouter)
```

### Registration (App.tsx)

```tsx
import ResearchLab from './pages/ResearchLab'
<Route path="/research" element={<ResearchLab />} />
// Nav: { path: '/research', label: 'Research' }
```

### Environment variable

```
DATABASE_URL_RESEARCH=postgresql://atlas:password@localhost:5432/atlas_research
```

### API endpoints (all read-only)

| Endpoint | Query params | Returns |
|---|---|---|
| `GET /api/research/predictions` | `model`, `date`, `limit`, `min_prob` | Ranked predictions for latest date |
| `GET /api/research/predictions/:ticker` | `model`, `days` | 90-day history + sparkline series data |
| `GET /api/research/models/latest` | — | Model registry + fold summary |
| `GET /api/research/runs/latest` | `limit` | Pipeline run log |
| `GET /api/research/metrics/latest` | — | Health dashboard aggregate |

### Champion view (model=champion, default)

Joins `return_regressor` and `positive_classifier` predictions on `(ticker, date)` via `FULL OUTER JOIN`. Uses regressor's `expected_return` and classifier's `probability_positive` together, with `COALESCE` degrading gracefully if only one model exists.

### Model selector options

| Value | Behaviour |
|---|---|
| `champion` | Combined regressor + classifier (default) |
| `return` | `return_regressor` sorted by rank_percentile |
| `probability` | `positive_classifier` sorted by probability |
| `drawdown` | `return_regressor` sorted by expected_drawdown ASC |

### IC metric vocabulary (consistent everywhere)

| Field | Meaning | Surface |
|---|---|---|
| `latest_rank_ic` | Most recent fold's validation Spearman IC | Health strip "Latest IC" cell |
| `wf_mean_rank_ic` | Mean IC across all folds (robustness) | Health strip "WF IC" cell |
| `wf_std_rank_ic` | Std of IC across folds (stability) | Health strip "WF IC ± std" |
| `wf_n_folds` | Number of folds contributing | Health strip subtitle |
| `mean_rank_ic` | Same mean, from foldSummary response | Models tab fold cards |
| `std_rank_ic` | Same std, from foldSummary response | Models tab stability bar |

**Source:** Always `model_registry.rank_ic` aggregated. Never from `feature_performance` (which contains per-feature IC diagnostics, not model-level performance).

### ResearchLab.tsx panels

| Panel | Always visible | Contents |
|---|---|---|
| HealthPanel | Yes (sticky) | 9 metric cells including WF IC (mean ± std), Latest IC, AUC/Brier |
| PredictionsTable | Tab: Predictions | Sortable/filterable ranked predictions, model selector, confidence bars |
| TickerDrawer | On row click | 90-day sparkline (P(+) / Exp Return / Rank), prediction log, latest actual |
| ModelMetricsPanel | Tab: Models | Fold summary cards with signal strength + stability bar + AUC/Brier |
| TopFeaturesPanel | Tab: Models | Top 10 features by mean cross-sectional IC, horizontal bars |
| RunsPanel | Tab: Runs | Pipeline run log with status, timestamps, error messages |

---

## 9. Configuration Reference

All settings live in `config/settings.py`. Override via environment variables.

```python
# Database
DATABASE_URL                # Research Engine Postgres

# Download
DOWNLOAD_BATCH_SIZE   = 50     # Tickers per Yahoo Finance batch
DOWNLOAD_BATCH_DELAY_S = 2.0   # Seconds between batches
BACKFILL_YEARS        = 15     # Years of history to download

# Features
FEATURE_VERSION       = 'v1'    # EAV row tag
SNAPSHOT_VERSION      = None    # Set per pipeline run if None

# Quality
TRAIN_MIN_QUALITY_SCORE = 0.70  # Hard filter before training

# Walk-forward
WF_MIN_TRAIN_YEARS    = 3       # Minimum history before first fold
WF_VAL_MONTHS         = 12      # Validation window length
WF_PURGE_DAYS         = 5       # Label leakage prevention gap
WF_PARALLEL_FOLDS     = 1       # Sequential (do not change until correctness proven)

# Model
MODEL_VERSION         = 'v1'    # Increment when training logic changes
MODEL_DIR             = 'models/'

# Export
PARQUET_OUTPUT_DIR    = 'exports/parquet/'
PARQUET_COMPRESSION   = 'snappy'
```

---

## 10. Run Sequence

### First-time (cold start)

```bash
# 1. Install dependencies
pip install lightgbm scikit-learn pyarrow joblib scipy yfinance \
            sqlalchemy psycopg python-dotenv structlog tenacity rich

# 2. Configure
cp .env.example .env
# Edit: DATABASE_URL, DATABASE_URL_RESEARCH

# 3. Initialise database (creates tables, seeds 185 securities, seeds feature_metadata)
python scripts/init_db.py

# 4. Backfill (download + features + labels + parquet)
# With BACKFILL_YEARS=5: ~30 min. With BACKFILL_YEARS=15: ~1.5 hr.
python scripts/backfill_history.py

# 5. Verify parquet coverage
python scripts/inspect_results.py --parquet-only

# 6. Baseline training (sanity check, ~5 min)
python scripts/run_training.py --baseline

# 7. Full walk-forward (~8 folds, ~20-40 min)
python scripts/run_training.py

# 8. Score today's universe
python scripts/run_training.py --predict-only

# 9. Inspect results
python scripts/inspect_results.py
```

### Nightly (incremental)

```bash
python scripts/run_nightly.py       # incremental ingest + features + parquet
python scripts/run_training.py --predict-only   # score with existing model
```

### Backfill resume flags

```bash
python scripts/backfill_history.py --skip-ingest              # re-run features + parquet only
python scripts/backfill_history.py --skip-ingest --skip-features  # parquet only
python scripts/backfill_history.py --start 2015-01-01 --end 2024-12-31
```

---

## 11. Interpretation Thresholds

### Rank IC (primary signal quality metric)

| Range | Assessment |
|---|---|
| > 0.05 | Strong — institutional-grade equity signal |
| 0.02–0.05 | Moderate — meaningful, worth building on |
| 0.01–0.02 | Weak — expand feature set or check data quality |
| < 0.01 | No signal — verify labels and coverage first |

### WF stability (std\_rank\_ic / mean\_rank\_ic)

| Ratio | Assessment |
|---|---|
| < 0.5× | HIGH stability — signal is consistent across folds |
| 0.5–1.0× | MODERATE — present but variable |
| > 1.0× | LOW — likely overfitting or regime sensitivity |

### Classifier metrics

| Metric | Baseline | Good | Strong |
|---|---|---|---|
| AUC | 0.50 | > 0.53 | > 0.56 |
| Brier | 0.25 | < 0.24 | < 0.22 |

---

## 12. Architectural Decisions

| Decision | What | Why |
|---|---|---|
| **Separate Postgres** | Research Engine ≠ Atlas Alpha DB | Prevents training load affecting API latency; independent migrations |
| **Parquet as ML substrate** | Canonical training input is parquet, not the DB | Columnar, compressed, framework-agnostic; already wide and labeled |
| **EAV for feature_snapshots** | One row per (ticker, date, feature\_name) | New features added without ALTER TABLE; snapshot\_version enables reproducibility |
| **Feature purity** | Zero pandas in feature modules | Polars migration = one-file change in feature\_factory.py |
| **Severity-based validation** | FATAL skips; WARNING scores | Partial data is normal; hard skips prevent corrupt features, not all features |
| **data\_quality\_score as feature** | Score included in training features | Model learns to discount low-quality bars automatically |
| **Hard quality filter at 0.70** | Rows below threshold excluded before training | Prevents clearly bad data from polluting gradients |
| **Champion view by default** | `model=champion` joins both model types | Users consume best available signal, not model plumbing |
| **Walk-forward sequential** | `WF_PARALLEL_FOLDS=1` | Correctness first; placeholder comment for future ProcessPoolExecutor |
| **feature\_performance ≠ model IC** | WF mean IC from model\_registry, not feature\_performance | Different tables for different questions; conflating them produces wrong metrics |
| **foldSummary by (version, target, horizon)** | Three-column GROUP BY | Prevents averaging across incompatible model families |
| **IS NOT DISTINCT FROM for horizon** | Used in champion and foldSummary joins | Handles NULL horizon correctly; standard = fails on NULL = NULL |
| **No ONNX** | Predictions served from Postgres | Precomputed predictions are sufficient; defer ONNX until latency requirements justify it |
| **No SHAP per fold** | SHAP deferred to production\_export only, top 25 features | SHAP per fold is expensive; gain importance is sufficient for feature\_performance |

---

## 13. Deferred / Future Work

### Near-term (after pipeline proves correctness)

| Item | Notes |
|---|---|
| **Latest IC colour-awareness** | Green if improving vs WF mean, red if deteriorating. PMs care about signal decay, not raw IC alone. |
| **GET /api/research/champion** | Returns active models, weights, training cutoff, wfMeanIC. The "research heartbeat" endpoint. |
| **Parallel fold execution** | `ProcessPoolExecutor` in walk\_forward.py once sequential correctness is proven. |
| **SHAP for topDrivers** | `production_export.py` topDrivers field; top 25 features only; not per fold. |
| **Polars migration** | Replace pandas in nightly pipeline. Feature modules already accept numpy arrays; only feature\_factory.py conversion changes. |

### Medium-term (Phase 3)

| Item | Notes |
|---|---|
| **Similarity Engine** | FAISS HNSW index over the feature matrix. "437 similar historical setups" makes predictions explainable and the platform dramatically more powerful. Next major institutional feature after pipeline stabilises. |
| **Champion Registry table** | `champion_models(model_family, model_version, active, weight, priority, started_at, retired_at)`. Makes `model=champion` configuration-driven instead of route-hardcoded. Needed before adding a third model type. |
| **Meta-Ensemble Layer** | `Champion Score = 0.45 × Return + 0.35 × Probability + 0.20 × Risk`, trained dynamically. Weights determined by WF IC of each component. |
| **Decision-centric table columns** | Edge (return/drawdown ratio), Stability (WF-IC-adjusted), Regime Fit, Analog Confidence, Consensus. More decision-relevant than raw probability. |
| **VIX / breadth regime features** | Stubs present in `regime.py`. Requires VIX data feed and full-universe breadth computation. |
| **AUC/Brier health strip cell** | Currently combined with AUC; may deserve its own cell once calibration variance is understood. |

### Long-term (Phase 4+)

| Item | Notes |
|---|---|
| **FastAPI sidecar** | Live inference if sub-100ms latency is required. Defer ONNX until deployment requirements justify it. |
| **IC-optimal weight feedback** | Feed WF IC back to Atlas Alpha ScoreOpts as suggested weight for each feature category. UI-gated toggle. |
| **Backtest substrate** | Parquet matrix is already the correct format. Backtest layer reads parquet, applies signal, computes returns. |

---

*Architecture current as of June 2026. Phases 1, 1.5, and 2 complete.*
