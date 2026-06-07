-- =============================================================
-- atlas-research canonical schema
-- PostgreSQL 14+
-- Run once: psql $DATABASE_URL -f db/schema.sql
-- All tables are CREATE IF NOT EXISTS — safe to re-run.
-- =============================================================

-- ---------------------------------------------------------
-- securities
-- Master list of tradeable instruments.
-- Loaded from config/universe.csv on init.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS securities (
    id          SERIAL PRIMARY KEY,
    ticker      TEXT UNIQUE NOT NULL,
    name        TEXT,
    sector      TEXT,
    industry    TEXT,
    exchange    TEXT,
    active      BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------
-- raw_bars
-- Daily OHLCV.  Source of truth for all feature computation.
-- Primary key (ticker, date) — upsert-safe.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_bars (
    ticker          TEXT NOT NULL,
    date            DATE NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    adjusted_close  DOUBLE PRECISION,
    volume          BIGINT,
    source          TEXT DEFAULT 'yahoo',
    created_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

-- ---------------------------------------------------------
-- feature_snapshots
-- EAV (Entity-Attribute-Value) feature store.
-- One row per (ticker, date, feature_name, feature_version).
-- New features are added as new rows — no ALTER TABLE needed.
-- Pivot to wide matrix via repository.get_feature_matrix().
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_snapshots (
    ticker            TEXT NOT NULL,
    date              DATE NOT NULL,
    feature_name      TEXT NOT NULL,
    feature_value     DOUBLE PRECISION,
    feature_version   TEXT DEFAULT 'v1',
    -- snapshot_version tracks which pipeline run produced this row.
    -- Allows point-in-time reproducibility: re-running training with
    -- snapshot_version = 'run_2026-06-06' gives identical feature inputs.
    snapshot_version  TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date, feature_name, feature_version)
);

-- ---------------------------------------------------------
-- feature_metadata
-- Registry of every feature name ever written to feature_snapshots.
-- Populated automatically by the pipeline when new features appear.
-- Essential once feature count exceeds ~50 — provides lineage,
-- category grouping, and deprecation tracking.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_metadata (
    feature_name    TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    -- 'return' | 'trend' | 'momentum' | 'volatility' | 'volume'
    -- | 'relative_strength' | 'regime' | 'label' | 'custom'
    description     TEXT,
    source_module   TEXT NOT NULL,
    -- e.g. 'atlas_research.features.momentum'
    data_type       TEXT NOT NULL DEFAULT 'float',
    -- 'float' | 'bool' | 'int'
    first_seen      TIMESTAMPTZ DEFAULT now(),
    deprecated_at   TIMESTAMPTZ,
    -- set when a feature is removed; rows remain queryable
    active          BOOLEAN DEFAULT true,
    notes           TEXT
    -- for SHAP attribution notes, expected range, known issues
);

-- ---------------------------------------------------------
-- labels
-- Forward return labels.  Populated nightly as future bars
-- become available.  Null columns = not yet computable.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS labels (
    ticker              TEXT NOT NULL,
    date                DATE NOT NULL,
    return_1d           DOUBLE PRECISION,
    return_5d           DOUBLE PRECISION,
    return_10d          DOUBLE PRECISION,
    return_20d          DOUBLE PRECISION,
    return_60d          DOUBLE PRECISION,
    max_runup_20d       DOUBLE PRECISION,
    max_drawdown_20d    DOUBLE PRECISION,
    positive_5d         BOOLEAN,
    positive_20d        BOOLEAN,
    created_at          TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

-- ---------------------------------------------------------
-- research_runs
-- Execution log for every pipeline invocation.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS research_runs (
    id                  BIGSERIAL PRIMARY KEY,
    run_type            TEXT NOT NULL,
    started_at          TIMESTAMPTZ DEFAULT now(),
    finished_at         TIMESTAMPTZ,
    status              TEXT DEFAULT 'running',
    tickers_processed   INTEGER DEFAULT 0,
    bars_inserted       INTEGER DEFAULT 0,
    features_generated  INTEGER DEFAULT 0,
    labels_generated    INTEGER DEFAULT 0,
    error_message       TEXT
);

-- ---------------------------------------------------------
-- model_registry
-- Metadata for every trained model version.
-- Populated in Phase 2 (LightGBM).
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_registry (
    id              BIGSERIAL PRIMARY KEY,
    model_name      TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    target          TEXT NOT NULL,
    horizon         INTEGER,
    training_start  DATE,
    training_end    DATE,
    feature_version TEXT,
    auc             DOUBLE PRECISION,
    brier           DOUBLE PRECISION,
    ic              DOUBLE PRECISION,
    rank_ic         DOUBLE PRECISION,
    sharpe          DOUBLE PRECISION,
    promoted        BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------
-- predictions
-- Model output per (ticker, date, model).
-- Populated in Phase 2.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    ticker                  TEXT NOT NULL,
    date                    DATE NOT NULL,
    model_name              TEXT NOT NULL,
    model_version           TEXT NOT NULL,
    expected_return         DOUBLE PRECISION,
    probability_positive    DOUBLE PRECISION,
    expected_drawdown       DOUBLE PRECISION,
    confidence              DOUBLE PRECISION,
    rank_percentile         DOUBLE PRECISION,
    created_at              TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date, model_name, model_version)
);

-- ---------------------------------------------------------
-- production_exports
-- Snapshot of each nightly export payload.
-- Phase 1: feature-only payload.
-- Phase 2+: adds predictions, similarity summary.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS production_exports (
    id          BIGSERIAL PRIMARY KEY,
    export_date DATE NOT NULL,
    export_type TEXT NOT NULL,
    payload     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- =============================================================
-- Indexes
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_raw_bars_ticker_date
    ON raw_bars(ticker, date DESC);

CREATE INDEX IF NOT EXISTS idx_features_ticker_date
    ON feature_snapshots(ticker, date DESC);

CREATE INDEX IF NOT EXISTS idx_features_name_date
    ON feature_snapshots(feature_name, date DESC);

-- Reproducibility index: reconstruct exact training set for any run tag.
-- Query pattern: WHERE snapshot_version = 'run_2026-06-06' AND ticker IN (...)
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_version_ticker_date
    ON feature_snapshots(snapshot_version, ticker, date);

CREATE INDEX IF NOT EXISTS idx_labels_ticker_date
    ON labels(ticker, date DESC);

CREATE INDEX IF NOT EXISTS idx_predictions_date_rank
    ON predictions(date DESC, rank_percentile DESC);

CREATE INDEX IF NOT EXISTS idx_research_runs_status
    ON research_runs(status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_production_exports_date
    ON production_exports(export_date DESC, export_type);

-- =============================================================
-- Phase 2 additions
-- =============================================================

-- ---------------------------------------------------------
-- feature_performance
-- Per-feature predictive metrics for a specific (target,
-- horizon, model_version, eval_window).
-- Kept separate from feature_metadata because predictive
-- value depends on all four dimensions and changes over time.
-- Populated after each walk-forward fold completes.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_performance (
    id              BIGSERIAL PRIMARY KEY,
    feature_name    TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    target          TEXT NOT NULL,         -- 'return_5d' | 'positive_5d'
    horizon_days    INTEGER NOT NULL,      -- 5
    eval_start      DATE NOT NULL,
    eval_end        DATE NOT NULL,
    fold_number     INTEGER,               -- NULL = full OOS evaluation

    -- Univariate predictive metrics
    spearman_ic     DOUBLE PRECISION,      -- Spearman rank IC vs target
    pearson_ic      DOUBLE PRECISION,
    ic_tstat        DOUBLE PRECISION,      -- IC / (IC_std / sqrt(n_dates))
    mean_ic         DOUBLE PRECISION,      -- mean daily IC over eval window
    ic_std          DOUBLE PRECISION,

    -- LightGBM feature importance (from champion model of this fold)
    lgbm_gain       DOUBLE PRECISION,      -- SHAP placeholder; Phase 3
    lgbm_split      DOUBLE PRECISION,

    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE (feature_name, model_version, target, horizon_days, eval_start, eval_end, fold_number)
);

CREATE INDEX IF NOT EXISTS idx_feature_perf_name_model
    ON feature_performance(feature_name, model_version, target);

CREATE INDEX IF NOT EXISTS idx_feature_perf_eval
    ON feature_performance(eval_end DESC, target);

-- Extend model_registry with Phase 2 columns
-- (ALTER TABLE is safe to re-run with IF NOT EXISTS on columns via DO block)
DO $$ BEGIN
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS feature_names   TEXT[];
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS feature_count   INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS train_rows      INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS val_rows        INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS artifact_path   TEXT;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS artifact_hash   TEXT;  -- SHA-256
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS hyperparams     JSONB;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS fold_metrics    JSONB; -- per-fold array
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS notes           TEXT;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS updated_at      TIMESTAMPTZ DEFAULT now();
EXCEPTION WHEN others THEN NULL;
END $$;

-- Additional predictions index for Phase 2 queries
CREATE INDEX IF NOT EXISTS idx_predictions_ticker_date
    ON predictions(ticker, date DESC);

CREATE INDEX IF NOT EXISTS idx_predictions_model_version
    ON predictions(model_name, model_version, date DESC);
