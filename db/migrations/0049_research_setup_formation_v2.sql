-- Migration 0049: Setup-Formation Measurement v2 (research)
-- Foundation measurement table: full multi-tool point-in-time STATE SNAPSHOT
-- on 5m bars (volume, MACD, EMA stack, RSI, VWAP, ATR/vol, swing structure,
-- opening-range breakout, candle/pattern), plus a confluence count, and the
-- forward base rate as a function of confluence and tool combinations. NOT a
-- predictor, NOT a trading signal -- see reports/research/SETUP_FORMATION_V2_REPORT.md.
-- Separate table from v1's research_setup_formation (untouched).
-- Grain: one row per (ticker, decision_ts, forward_k). N=2 fixed this run.
--
-- Numbered 0049 (not 0047) because the live DB has moved past this worktree's
-- migrations directory: 0047_vwap_5m.sql and 0048_gaps.sql were applied by a
-- separate, concurrent piece of work (branch feat/gaps) between v1's own
-- 0047_research_setup_formation.sql and this migration -- see
-- SETUP_FORMATION_V2_REPORT.md Step 1 for the full account.

CREATE TABLE IF NOT EXISTS research_setup_formation_v2 (
    id                  BIGSERIAL PRIMARY KEY,

    ticker              TEXT NOT NULL,
    n_window            INTEGER NOT NULL,          -- fixed at 2 this run
    decision_ts         TIMESTAMPTZ NOT NULL,      -- close of the bar at decision point T

    -- Per-tool point-in-time state + "active" (= a notable event/extreme at T)
    state_candle        TEXT,                      -- candlestick pattern name | directional_thrust_up/down | NULL
    direction_candle    TEXT,                      -- long | short | NULL
    active_candle       BOOLEAN NOT NULL,

    state_volume        TEXT NOT NULL,             -- very_high | high | normal | low
    active_volume       BOOLEAN NOT NULL,          -- newly crossed into high/very_high at T

    state_macd          TEXT NOT NULL,             -- bull | bear
    active_macd         BOOLEAN NOT NULL,          -- bull/bear cross fired at T

    state_rsi           TEXT NOT NULL,             -- oversold | overbought | neutral
    active_rsi          BOOLEAN NOT NULL,          -- reclaim event or newly-entered extreme at T

    state_ema           TEXT NOT NULL,             -- bull_stack | bear_stack | mixed
    active_ema          BOOLEAN NOT NULL,          -- stack state changed at T

    state_vwap          TEXT NOT NULL,             -- above | below
    active_vwap         BOOLEAN NOT NULL,          -- vwap cross fired at T

    state_atr           TEXT NOT NULL,             -- compressed | expanding | normal
    active_atr          BOOLEAN NOT NULL,          -- newly entered compressed/expanding at T

    state_swing         TEXT NOT NULL,             -- up | down | range (swing_pivots/classify_trend, PIT-lagged)
    active_swing        BOOLEAN NOT NULL,          -- a new swing pivot became known exactly at T

    state_orb           TEXT NOT NULL,             -- in_opening_range | above_or_high | below_or_low | inside_range
    active_orb          BOOLEAN NOT NULL,          -- opening-range breakout signal fired at T

    confluence_count    SMALLINT NOT NULL,         -- count of active_* flags above (0-9)
    active_tools_csv    TEXT NOT NULL,              -- comma-joined names of active tools at T, e.g. "volume,macd"

    -- Forward outcome (the ONLY part allowed to look ahead of decision_ts).
    -- direction tested for hit_target is direction_candle (the only tool
    -- producing a directional thesis) -- NULL/no-hit-computed otherwise.
    forward_k           INTEGER NOT NULL,
    forward_return       DOUBLE PRECISION,
    forward_direction    TEXT,
    hit_target           BOOLEAN,

    in_sample_flag       BOOLEAN NOT NULL,

    run_id                TEXT NOT NULL,

    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rsfv2_ticker_ts
    ON research_setup_formation_v2 (ticker, decision_ts);

CREATE INDEX IF NOT EXISTS idx_rsfv2_confluence
    ON research_setup_formation_v2 (confluence_count);

CREATE INDEX IF NOT EXISTS idx_rsfv2_active_tools
    ON research_setup_formation_v2 (active_tools_csv);

CREATE INDEX IF NOT EXISTS idx_rsfv2_run_id
    ON research_setup_formation_v2 (run_id);

CREATE INDEX IF NOT EXISTS idx_rsfv2_agg_lookup
    ON research_setup_formation_v2 (ticker, confluence_count, forward_k, in_sample_flag);
