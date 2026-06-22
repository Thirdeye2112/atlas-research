-- Migration 0054: Foundation Retest -- one stock, conditional TA, timeframe corroboration
-- Foundation measurement, NOT a predictor, NOT a trading signal. See
-- reports/research/FOUNDATION_RETEST_REPORT.md.
-- Read-only against all existing tables; writes only here.
-- Grain: one row per (trigger_type, decision_ts, forward_k).

CREATE TABLE IF NOT EXISTS research_foundation_retest (
    id                  BIGSERIAL PRIMARY KEY,

    run_id              TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,          -- '5m'

    trigger_type        TEXT NOT NULL,          -- e.g. 'rsi_reclaim_bull', 'swing_pivot_low_confirmed'
    decision_ts         TIMESTAMPTZ NOT NULL,   -- the bar at which the trigger fires AND is causally knowable
    direction            TEXT NOT NULL,          -- 'long' | 'short'

    daily_trend          TEXT,                   -- prior trading day's daily trend ('up'/'down'/'range'/NULL)
    daily_market_trend   TEXT,
    daily_dist_support    DOUBLE PRECISION,
    daily_dist_resistance DOUBLE PRECISION,
    daily_agrees          BOOLEAN,                -- NULL if daily context unknown

    forward_k            INTEGER NOT NULL,
    fwd_return            DOUBLE PRECISION,        -- simple pct return, close[T] -> close[T+k]
    fwd_direction          TEXT,                    -- up | down | flat
    outcome_b             TEXT,                    -- WIN | LOSS | NEITHER (ATR R-bracket, capped at k)
    max_r                 SMALLINT,
    realized_r            DOUBLE PRECISION,
    baseline_realized_r_mean DOUBLE PRECISION,     -- the matching baseline cell's mean realized_R (for delta = realized_r - this, computed at aggregation time, stored here for convenience/audit)

    in_sample_flag         BOOLEAN NOT NULL,

    created_at             TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rftest_trigger_k
    ON research_foundation_retest (trigger_type, forward_k);
CREATE INDEX IF NOT EXISTS idx_rftest_run_id
    ON research_foundation_retest (run_id);
CREATE INDEX IF NOT EXISTS idx_rftest_agg_lookup
    ON research_foundation_retest (trigger_type, forward_k, in_sample_flag, daily_agrees);


CREATE TABLE IF NOT EXISTS research_foundation_retest_baseline (
    id                  BIGSERIAL PRIMARY KEY,

    run_id              TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,

    decision_ts          TIMESTAMPTZ NOT NULL,
    direction             TEXT NOT NULL,           -- random long/short

    forward_k             INTEGER NOT NULL,
    fwd_return             DOUBLE PRECISION,
    fwd_direction           TEXT,
    outcome_b              TEXT,
    max_r                  SMALLINT,
    realized_r             DOUBLE PRECISION,

    in_sample_flag          BOOLEAN NOT NULL,

    created_at              TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rftestb_k
    ON research_foundation_retest_baseline (forward_k, in_sample_flag);
CREATE INDEX IF NOT EXISTS idx_rftestb_run_id
    ON research_foundation_retest_baseline (run_id);
