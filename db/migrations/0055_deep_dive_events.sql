-- Migration 0055: deep_dive_events
-- Minable store of the per-event deep-dive examination (one row per significant
-- move / fulfilled candlestick / chart-structure pattern), with the decision-bar
-- TA snapshot, the validated mean-reversion score, forward outcomes, and a
-- plain-text confluence read. Built by scripts/mine_universe.py across the daily
-- universe so BOTH atlas-research (feature/edge mining) and atlas-alpha (live
-- signal lookup via DATABASE_URL_RESEARCH) can query it.
--
-- Look-ahead note: all TA columns are computed from data up to and including the
-- event bar (ts). fwd_ret_* are OUTCOMES (future) — for predictive mining filter
-- on the TA/score columns, never on fwd_ret_*. New table only.

CREATE TABLE IF NOT EXISTS deep_dive_events (
    id            BIGSERIAL PRIMARY KEY,
    ticker        TEXT    NOT NULL,
    ts            DATE    NOT NULL,            -- event / decision bar
    timeframe     TEXT    NOT NULL DEFAULT '1d',
    event_type    TEXT    NOT NULL,            -- 'move' | 'candlestick' | 'structure'
    name          TEXT    NOT NULL,            -- e.g. significant_rise, bull_flag, double_bottom
    direction     TEXT,                        -- long|short|rise|drop

    -- move / candle context
    cc_ret        DOUBLE PRECISION,            -- close-to-close % (gap-inclusive)
    gap_pct       DOUBLE PRECISION,

    -- validated mean-reversion signal (see reports/SIGNAL_REGISTRY.md)
    mr_score      DOUBLE PRECISION,
    mr_oversold   SMALLINT,

    -- decision-bar TA snapshot (minable correlates)
    rsi           DOUBLE PRECISION,
    rsi_slope     DOUBLE PRECISION,
    macd_hist     DOUBLE PRECISION,
    stoch_k       DOUBLE PRECISION,
    williams_r    DOUBLE PRECISION,
    bb_pct        DOUBLE PRECISION,
    bb_width      DOUBLE PRECISION,
    atr_pct       DOUBLE PRECISION,
    vol_ratio     DOUBLE PRECISION,
    vol_z         DOUBLE PRECISION,
    mfi           DOUBLE PRECISION,
    dist_ema20    DOUBLE PRECISION,
    dist_ema50    DOUBLE PRECISION,
    dist_ema200   DOUBLE PRECISION,
    above_ema200  SMALLINT,
    ema_stack_bull SMALLINT,
    ema_stack_bear SMALLINT,
    dist_hi_20    DOUBLE PRECISION,
    dist_lo_20    DOUBLE PRECISION,
    roc_10        DOUBLE PRECISION,
    consec_dir    DOUBLE PRECISION,

    -- outcomes (FUTURE — explanatory/label only, never a predictor)
    fwd_ret_1     DOUBLE PRECISION,
    fwd_ret_3     DOUBLE PRECISION,
    fwd_ret_5     DOUBLE PRECISION,
    fwd_ret_10    DOUBLE PRECISION,

    confluence_n  SMALLINT,
    explained_by  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (ticker, ts, timeframe, event_type, name, direction)
);

CREATE INDEX IF NOT EXISTS idx_dde_ticker_ts   ON deep_dive_events (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_dde_type_name   ON deep_dive_events (event_type, name);
CREATE INDEX IF NOT EXISTS idx_dde_name_dir     ON deep_dive_events (name, direction);
CREATE INDEX IF NOT EXISTS idx_dde_mr_score     ON deep_dive_events (mr_score);
CREATE INDEX IF NOT EXISTS idx_dde_ts           ON deep_dive_events (ts);
