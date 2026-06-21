-- Migration 0052: Dome/Leg Early-Signature Study (research)
-- Foundation measurement, NOT a predictor, NOT a trading signal -- see
-- reports/research/DOME_LEG_SIGNATURE_REPORT.md. Formalizes a read-only
-- exploration into two new tables:
--   research_dome_leg_signature: one row per detected leg (up="dome",
--     down="bowl"), candle geometry at the leg's start and peak/trough,
--     and the early-signature fields (does the first few bars off the
--     start predict the eventual leg size / correction depth).
--   research_dome_leg_realtime: one row per bar tested by the zero-
--     look-ahead real-time shape filter (or the random baseline), with
--     forward returns at multiple horizons.
-- Numbered 0052 (live DB is at 0051_research_pattern_fulfillment.sql).

CREATE TABLE IF NOT EXISTS research_dome_leg_signature (
    id                  BIGSERIAL PRIMARY KEY,

    run_id              TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,          -- '5m'
    leg_dir             TEXT NOT NULL,          -- 'up' (dome) | 'down' (bowl)

    start_ts            TIMESTAMPTZ NOT NULL,   -- leg start (the swing LOW for up, HIGH for down)
    peak_ts             TIMESTAMPTZ NOT NULL,   -- leg's terminal extreme (peak for up, trough for down)
    corr_ts             TIMESTAMPTZ,            -- the pivot that ends the leg (forward outcome, not a feature)

    leg_amp             DOUBLE PRECISION NOT NULL,   -- |peak-start|/start, magnitude
    leg_bars            INTEGER NOT NULL,
    corr_depth          DOUBLE PRECISION,            -- depth of the move that ends the leg (forward outcome)
    corr_bars           INTEGER,

    early_gain          DOUBLE PRECISION,            -- magnitude move over the first early_bars off the start
    early_bars          INTEGER NOT NULL,
    early_slope         DOUBLE PRECISION,            -- early_gain / early_bars

    -- candle geometry at start and at peak/trough (from intraday/features.py, reused verbatim)
    start_body_pct          DOUBLE PRECISION,
    start_upper_wick_pct    DOUBLE PRECISION,
    start_lower_wick_pct    DOUBLE PRECISION,
    start_rng_atr_ratio     DOUBLE PRECISION,
    start_vol_ratio         DOUBLE PRECISION,
    start_close_loc         DOUBLE PRECISION,
    start_is_green          BOOLEAN,

    peak_body_pct            DOUBLE PRECISION,
    peak_upper_wick_pct      DOUBLE PRECISION,
    peak_lower_wick_pct      DOUBLE PRECISION,
    peak_rng_atr_ratio       DOUBLE PRECISION,
    peak_vol_ratio           DOUBLE PRECISION,
    peak_close_loc           DOUBLE PRECISION,
    peak_is_green            BOOLEAN,

    in_sample_flag       BOOLEAN NOT NULL,

    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rdls_ticker_dir
    ON research_dome_leg_signature (ticker, leg_dir);
CREATE INDEX IF NOT EXISTS idx_rdls_run_id
    ON research_dome_leg_signature (run_id);
CREATE INDEX IF NOT EXISTS idx_rdls_in_sample
    ON research_dome_leg_signature (leg_dir, in_sample_flag);


CREATE TABLE IF NOT EXISTS research_dome_leg_realtime (
    id                  BIGSERIAL PRIMARY KEY,

    run_id              TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    timeframe           TEXT NOT NULL,          -- '5m'
    bar_ts              TIMESTAMPTZ NOT NULL,

    filter_type         TEXT NOT NULL,          -- 'bottom_like' | 'top_like' | '__BASELINE__'

    forward_k           INTEGER NOT NULL,
    forward_r            DOUBLE PRECISION,       -- (close[t+k]-close[t])/atr14[t]

    in_sample_flag        BOOLEAN NOT NULL,

    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rdlr_ticker_filter
    ON research_dome_leg_realtime (ticker, filter_type, forward_k);
CREATE INDEX IF NOT EXISTS idx_rdlr_run_id
    ON research_dome_leg_realtime (run_id);
CREATE INDEX IF NOT EXISTS idx_rdlr_agg_lookup
    ON research_dome_leg_realtime (filter_type, forward_k, in_sample_flag);
