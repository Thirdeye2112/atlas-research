-- Migration 0051: Pattern Fulfillment Backtest (research)
-- Foundation measurement: for every detected instance of every pattern in
-- pattern_reference (plus 4 supplemental shapes not in that table), does
-- reality match the taught confirm/invalidate/inversion behavior OOS, on a
-- reward:risk expectancy basis -- see reports/research/PATTERN_FULFILLMENT_REPORT.md.
-- NOT a predictor, NOT a trading signal.
-- Numbered 0051: live DB is currently at 0050_pattern_reference.sql (see
-- report Step 1 for the note on branch state when this was built).
-- Grain: one row per (pattern_type, ticker, timeframe, instance_ts).
-- Baseline (random-direction, same bracket) rows share this table with
-- pattern_type = '__BASELINE__'.

CREATE TABLE IF NOT EXISTS research_pattern_fulfillment (
    id                   BIGSERIAL PRIMARY KEY,

    run_id               TEXT NOT NULL,

    pattern_type         TEXT NOT NULL,        -- one of pattern_reference's 43, '__BASELINE__', or a supplemental shape
    ticker               TEXT NOT NULL,
    timeframe            TEXT NOT NULL,         -- '5m' | 'daily'
    instance_ts          TIMESTAMPTZ NOT NULL,  -- T_recog, point-in-time recognition bar

    direction            TEXT,                  -- 'long' | 'short' (resolved; may differ from a 'bidirectional' pattern's table default)

    -- Stage A: confirm / invalidate / neither (the taught decision tree)
    stage_a_outcome      TEXT NOT NULL,         -- CONFIRMED | INVALIDATED | NEITHER_A
    stage_a_event_ts     TIMESTAMPTZ,           -- bar where stage_a resolved; NULL for NEITHER_A

    -- Stage B: ATR R-bracket outcome for CONFIRMED instances (1xATR stop, R1/2/3 targets)
    outcome_b            TEXT,                  -- WIN | LOSS | NEITHER ; NULL unless stage_a_outcome = CONFIRMED
    max_r_b              SMALLINT,              -- highest R target reached before stop (0 if LOSS/NEITHER)
    realized_r_b         DOUBLE PRECISION,       -- expectancy unit for this instance's Stage-B trade

    -- Stage C: inversion test for INVALIDATED instances of the 21 codeable
    -- invalidation_becomes patterns (hs_top excluded -- source text itself
    -- disclaims a clean signal)
    inversion_tested     BOOLEAN NOT NULL DEFAULT FALSE,
    inversion_direction  TEXT,
    outcome_c            TEXT,                  -- WIN | LOSS | NEITHER
    max_r_c              SMALLINT,
    realized_r_c         DOUBLE PRECISION,

    in_sample_flag        BOOLEAN NOT NULL,

    created_at            TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rpf_pattern_ticker_tf
    ON research_pattern_fulfillment (pattern_type, ticker, timeframe);

CREATE INDEX IF NOT EXISTS idx_rpf_run_id
    ON research_pattern_fulfillment (run_id);

CREATE INDEX IF NOT EXISTS idx_rpf_agg_lookup
    ON research_pattern_fulfillment (pattern_type, timeframe, stage_a_outcome, in_sample_flag);

CREATE INDEX IF NOT EXISTS idx_rpf_inversion
    ON research_pattern_fulfillment (pattern_type, inversion_tested, in_sample_flag);
