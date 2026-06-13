-- =============================================================
-- Migration 0005: Probability engine schema (Phase 4A/4B)
-- Tables: research_questions, test_specifications, backtest_runs,
--         backtest_results, backtest_events, promoted_signals
-- All IF NOT EXISTS — safe to re-run.
-- =============================================================

-- What we are studying
CREATE TABLE IF NOT EXISTS research_questions (
    id          SERIAL      PRIMARY KEY,
    name        TEXT        NOT NULL UNIQUE,
    description TEXT,
    category    TEXT        NOT NULL DEFAULT 'general',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- How to measure one question: ticker + condition + parameters
-- params stored as canonical JSON text so UNIQUE constraint works
-- (JSONB does not support B-tree indexes required for UNIQUE)
CREATE TABLE IF NOT EXISTS test_specifications (
    id             SERIAL  PRIMARY KEY,
    question_id    INTEGER REFERENCES research_questions(id),
    ticker         TEXT    NOT NULL,
    condition_type TEXT    NOT NULL,
    params         TEXT    NOT NULL DEFAULT '{}',
    start_date     DATE,
    end_date       DATE,
    created_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (ticker, condition_type, params)
);

CREATE INDEX IF NOT EXISTS idx_test_specs_ticker_ctype
    ON test_specifications(ticker, condition_type);

-- One execution of a spec against historical data
CREATE TABLE IF NOT EXISTS backtest_runs (
    id          SERIAL  PRIMARY KEY,
    spec_id     INTEGER REFERENCES test_specifications(id),
    run_date    DATE    NOT NULL DEFAULT CURRENT_DATE,
    data_start  DATE,
    data_end    DATE,
    n_events    INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'complete',
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_backtest_runs_spec_date
    ON backtest_runs(spec_id, run_date DESC);

-- Aggregate statistics per horizon per run
CREATE TABLE IF NOT EXISTS backtest_results (
    id            SERIAL  PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    horizon_days  INTEGER NOT NULL,
    n             INTEGER,
    hit_rate      DOUBLE PRECISION,
    avg_return    DOUBLE PRECISION,
    median_return DOUBLE PRECISION,
    p25_return    DOUBLE PRECISION,
    p75_return    DOUBLE PRECISION,
    avg_max_runup DOUBLE PRECISION,
    avg_max_dd    DOUBLE PRECISION,
    UNIQUE (run_id, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_run
    ON backtest_results(run_id);

-- Per-occurrence signal outcomes
CREATE TABLE IF NOT EXISTS backtest_events (
    id            BIGSERIAL PRIMARY KEY,
    run_id        INTEGER   NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    ticker        TEXT      NOT NULL,
    signal_date   DATE      NOT NULL,
    ret_1d        DOUBLE PRECISION,
    ret_3d        DOUBLE PRECISION,
    ret_5d        DOUBLE PRECISION,
    ret_10d       DOUBLE PRECISION,
    ret_20d       DOUBLE PRECISION,
    max_runup_5d  DOUBLE PRECISION,
    max_runup_10d DOUBLE PRECISION,
    max_runup_20d DOUBLE PRECISION,
    max_dd_5d     DOUBLE PRECISION,
    max_dd_10d    DOUBLE PRECISION,
    max_dd_20d    DOUBLE PRECISION,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (run_id, ticker, signal_date)
);

CREATE INDEX IF NOT EXISTS idx_backtest_events_run
    ON backtest_events(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_events_date
    ON backtest_events(signal_date DESC);

-- Signals promoted to live display (future API use)
CREATE TABLE IF NOT EXISTS promoted_signals (
    id          SERIAL  PRIMARY KEY,
    spec_id     INTEGER REFERENCES test_specifications(id),
    ticker      TEXT    NOT NULL,
    signal_date DATE    NOT NULL,
    promoted_at TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ,
    notes       TEXT,
    UNIQUE (spec_id, ticker, signal_date)
);
