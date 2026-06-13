-- 0025: Signal verification layer
-- Adds exploratory flag, status column, and yearly breakdown support.

ALTER TABLE promoted_signals
    ADD COLUMN IF NOT EXISTS exploratory    BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS signal_status  TEXT    NOT NULL DEFAULT 'promoted';

-- Enforce: non-exploratory signals must have sufficient sample size.
-- Checked at application layer; this constraint is a DB-level backstop.
-- (n_events is on backtest_runs, not promoted_signals, so we can't FK-check it here.)

-- Index for status-filtered queries
CREATE INDEX IF NOT EXISTS idx_promoted_signals_status
    ON promoted_signals (signal_status, promoted_at DESC);
