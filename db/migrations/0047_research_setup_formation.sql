-- Migration 0047: Setup-Formation Measurement (research)
-- Foundation measurement table: how often a recognizable N-candle setup is
-- forming on 5m bars, and what its forward base rate looks like. NOT a
-- predictor, NOT a trading signal -- see reports/research/SETUP_FORMATION_REPORT.md.
-- Grain: one row per (ticker, n_window, decision_ts, forward_k).

CREATE TABLE IF NOT EXISTS research_setup_formation (
    id                  BIGSERIAL PRIMARY KEY,

    ticker              TEXT NOT NULL,
    n_window            INTEGER NOT NULL,          -- formation window size N (2..5)
    decision_ts         TIMESTAMPTZ NOT NULL,      -- close of the bar at decision point T

    -- Window classification (point-in-time, computed from data through decision_ts only)
    setup_state         TEXT NOT NULL,             -- SETUP_FORMING | NEUTRAL | FLAT
    setup_type          TEXT,                      -- candlestick pattern name, or directional_thrust_up/down; NULL for NEUTRAL/FLAT
    direction           TEXT,                      -- long | short; NULL when no directional thesis

    -- Daily multi-timeframe context, as of the strictly-prior trading day's close
    -- (from pattern_memory, timeframe='daily'; forward-filled, never same-day)
    daily_trend         TEXT,                      -- up | down | range
    daily_market_trend  TEXT,                      -- up | down
    daily_loc           TEXT,                      -- near_support | near_resistance | mid_range
    daily_context       TEXT,                      -- combined bucket: "{trend}/{loc}/mkt_{market_trend}"

    -- Forward outcome (the ONLY part allowed to look ahead of decision_ts)
    forward_k           INTEGER NOT NULL,          -- horizon in bars (1..5)
    forward_return       DOUBLE PRECISION,          -- pct, close[T] -> close[T+k]
    forward_direction    TEXT,                      -- up | down | flat
    hit_target           BOOLEAN,                   -- price moved >=1 ATR(14) in `direction` within [T+1, T+k]; NULL if no directional thesis

    -- Walk-forward bookkeeping
    in_sample_flag       BOOLEAN NOT NULL,          -- TRUE = training portion, FALSE = held-out portion (chronological split per ticker)

    -- Reproducibility
    run_id                TEXT NOT NULL,             -- ties rows to one measurement run (see reports/research/setup_formation_run_log.jsonl)

    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rsf_ticker_n_ts
    ON research_setup_formation (ticker, n_window, decision_ts);

CREATE INDEX IF NOT EXISTS idx_rsf_setup_state
    ON research_setup_formation (setup_state);

CREATE INDEX IF NOT EXISTS idx_rsf_run_id
    ON research_setup_formation (run_id);

CREATE INDEX IF NOT EXISTS idx_rsf_agg_lookup
    ON research_setup_formation (ticker, n_window, setup_state, daily_context, forward_k, in_sample_flag);
