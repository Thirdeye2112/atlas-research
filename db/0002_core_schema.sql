-- =============================================================
-- Migration 0002: Core atlas-research schema (Phase 1 + 2)
-- Extracted from db/schema.sql for migration tracking.
-- All statements are IF NOT EXISTS — safe to re-run.
-- =============================================================

-- securities
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

-- raw_bars
CREATE TABLE IF NOT EXISTS raw_bars (
    ticker      TEXT        NOT NULL,
    date        DATE        NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION NOT NULL,
    volume      BIGINT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_raw_bars_date   ON raw_bars(date DESC);
CREATE INDEX IF NOT EXISTS idx_raw_bars_ticker ON raw_bars(ticker, date DESC);

-- feature_snapshots (EAV)
CREATE TABLE IF NOT EXISTS feature_snapshots (
    id               BIGSERIAL PRIMARY KEY,
    ticker           TEXT        NOT NULL,
    date             DATE        NOT NULL,
    feature_name     TEXT        NOT NULL,
    feature_value    DOUBLE PRECISION,
    snapshot_version TEXT        NOT NULL DEFAULT 'v1',
    created_at       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (ticker, date, feature_name, snapshot_version)
);

CREATE INDEX IF NOT EXISTS idx_feature_snapshots_ticker_date
    ON feature_snapshots(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_feature_snapshots_version_ticker_date
    ON feature_snapshots(snapshot_version, ticker, date);

-- feature_metadata
CREATE TABLE IF NOT EXISTS feature_metadata (
    feature_name    TEXT PRIMARY KEY,
    category        TEXT,
    source_module   TEXT,
    description     TEXT,
    data_type       TEXT DEFAULT 'float',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- labels
CREATE TABLE IF NOT EXISTS labels (
    ticker              TEXT    NOT NULL,
    date                DATE    NOT NULL,
    label_return_5d     DOUBLE PRECISION,
    label_return_20d    DOUBLE PRECISION,
    label_positive_5d   DOUBLE PRECISION,
    label_positive_20d  DOUBLE PRECISION,
    created_at          TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_labels_date ON labels(date DESC);

-- research_runs
CREATE TABLE IF NOT EXISTS research_runs (
    id              SERIAL PRIMARY KEY,
    run_date        DATE        NOT NULL DEFAULT CURRENT_DATE,
    status          TEXT        NOT NULL DEFAULT 'running',
    started_at      TIMESTAMPTZ DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    tickers_updated INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    notes           TEXT
);

-- model_registry
CREATE TABLE IF NOT EXISTS model_registry (
    id              SERIAL PRIMARY KEY,
    model_name      TEXT        NOT NULL,
    model_version   TEXT        NOT NULL DEFAULT 'v1',
    target          TEXT        NOT NULL,
    horizon         INTEGER     NOT NULL DEFAULT 5,
    training_start  DATE,
    training_end    DATE,
    feature_version TEXT        NOT NULL DEFAULT 'v1',
    auc             DOUBLE PRECISION,
    brier           DOUBLE PRECISION,
    ic              DOUBLE PRECISION,
    rank_ic         DOUBLE PRECISION,
    sharpe          DOUBLE PRECISION,
    artifact_path   TEXT,
    artifact_hash   TEXT,
    hyperparams     JSONB,
    fold_metrics    JSONB,
    promoted        BOOLEAN DEFAULT false,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (model_name, model_version, target, training_end)
);

-- predictions
CREATE TABLE IF NOT EXISTS predictions (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT        NOT NULL,
    date            DATE        NOT NULL,
    model_name      TEXT        NOT NULL,
    model_version   TEXT        NOT NULL DEFAULT 'v1',
    score_return    DOUBLE PRECISION,
    score_positive  DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (ticker, date, model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_predictions_ticker_date
    ON predictions(ticker, date DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_model_version
    ON predictions(model_name, model_version, date DESC);

-- production_exports
CREATE TABLE IF NOT EXISTS production_exports (
    id          SERIAL PRIMARY KEY,
    export_date DATE        NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- feature_performance
CREATE TABLE IF NOT EXISTS feature_performance (
    id              SERIAL PRIMARY KEY,
    feature_name    TEXT        NOT NULL,
    model_version   TEXT        NOT NULL DEFAULT 'v1',
    target          TEXT        NOT NULL,
    horizon_days    INTEGER     NOT NULL,
    eval_start      DATE        NOT NULL,
    eval_end        DATE        NOT NULL,
    fold_number     INTEGER,
    spearman_ic     DOUBLE PRECISION,
    pearson_ic      DOUBLE PRECISION,
    ic_tstat        DOUBLE PRECISION,
    mean_ic         DOUBLE PRECISION,
    ic_std          DOUBLE PRECISION,
    lgbm_gain       DOUBLE PRECISION,
    lgbm_split      DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (feature_name, model_version, target, horizon_days, eval_start, eval_end, fold_number)
);

CREATE INDEX IF NOT EXISTS idx_feature_perf_name_model
    ON feature_performance(feature_name, model_version, target);
CREATE INDEX IF NOT EXISTS idx_feature_perf_eval
    ON feature_performance(eval_end DESC, target);

-- Phase 2 columns on model_registry (idempotent)
DO $$ BEGIN
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS feature_names    TEXT[];
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS feature_count    INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS train_rows       INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS val_rows         INTEGER;
    ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMPTZ DEFAULT now();
EXCEPTION WHEN others THEN NULL;
END $$;
