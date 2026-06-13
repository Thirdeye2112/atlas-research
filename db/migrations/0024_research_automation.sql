-- 0024: Research Automation Layer
-- Adds source tracking, robustness columns, and automation-ready indexes.

ALTER TABLE research_questions
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';

ALTER TABLE test_specifications
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';

ALTER TABLE backtest_runs
    ADD COLUMN IF NOT EXISTS robustness_passed  BOOLEAN,
    ADD COLUMN IF NOT EXISTS robustness_notes   TEXT,
    ADD COLUMN IF NOT EXISTS promoted           BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS promoted_at        TIMESTAMPTZ;

ALTER TABLE promoted_signals
    ADD COLUMN IF NOT EXISTS promotion_score    DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS robustness_notes   TEXT;

-- Index to quickly find promoted runs per spec
CREATE INDEX IF NOT EXISTS idx_backtest_runs_promoted
    ON backtest_runs (spec_id, promoted, run_date DESC)
    WHERE promoted = TRUE;

-- Index for source-filtered queries
CREATE INDEX IF NOT EXISTS idx_test_specs_source
    ON test_specifications (source, condition_type);

CREATE INDEX IF NOT EXISTS idx_rq_source
    ON research_questions (source, category);
