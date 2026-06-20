-- Migration 0043: Pipeline Run Log
-- ===================================================
-- Structured log for run_atlas_pipeline.py executions.
-- Persists start/finish/status/rows-affected for every step.

CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id            BIGSERIAL PRIMARY KEY,
    run_id        TEXT NOT NULL,           -- UUID per invocation
    mode          TEXT NOT NULL,           -- daily | nightly | weekly | intraday_only | research_refresh | health_check | full_safe
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL DEFAULT 'running',   -- running | complete | partial | failed
    step_name     TEXT,                   -- NULL = summary row; set for per-step rows
    step_status   TEXT,                   -- ok | failed | skipped
    rows_affected INTEGER,
    runtime_s     REAL,
    error_msg     TEXT,
    metadata      JSONB,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prl_run_id     ON pipeline_run_log (run_id);
CREATE INDEX IF NOT EXISTS idx_prl_started_at ON pipeline_run_log (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_prl_mode       ON pipeline_run_log (mode);
