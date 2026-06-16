-- Migration 0040: Intraday Candle Memory + Similarity Latest
-- Stores every 5-min candle as a labeled historical example for similarity search

CREATE TABLE IF NOT EXISTS intraday_candle_memory (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    ts              TIMESTAMPTZ NOT NULL,
    timeframe       TEXT NOT NULL DEFAULT '5m',
    feature_version TEXT NOT NULL DEFAULT 'v1',

    -- Raw candle
    open_price      DOUBLE PRECISION,
    high_price      DOUBLE PRECISION,
    low_price       DOUBLE PRECISION,
    close_price     DOUBLE PRECISION,
    volume          BIGINT,

    -- Candle shape features
    body_pct        DOUBLE PRECISION,
    upper_wick_ratio DOUBLE PRECISION,
    lower_wick_ratio DOUBLE PRECISION,
    is_green        BOOLEAN,
    range_pct       DOUBLE PRECISION,

    -- Volume features
    vol_ratio       DOUBLE PRECISION,
    vol_zscore      DOUBLE PRECISION,

    -- Trend features
    vwap_dist_pct   DOUBLE PRECISION,
    or_position     DOUBLE PRECISION,
    ema9_slope_norm DOUBLE PRECISION,

    -- Momentum features
    rsi14           DOUBLE PRECISION,
    macd_hist_norm  DOUBLE PRECISION,
    atr_pct         DOUBLE PRECISION,

    -- Time context
    tod_min         INTEGER,
    time_of_day     TEXT,
    candle_num      INTEGER,

    -- Daily context from prediction_outcomes
    daily_ml_rank    DOUBLE PRECISION,
    daily_conviction TEXT,
    daily_confluence DOUBLE PRECISION,
    daily_regime     TEXT,
    daily_vix        TEXT,
    daily_jarvis     BOOLEAN,

    -- Precomputed 16-dim normalized feature vector for KNN
    feature_vector  DOUBLE PRECISION[],

    -- Multi-horizon forward returns (pct, close to close)
    future_return_1   DOUBLE PRECISION,
    future_return_3   DOUBLE PRECISION,
    future_return_6   DOUBLE PRECISION,
    future_return_12  DOUBLE PRECISION,
    future_return_24  DOUBLE PRECISION,
    future_return_eod DOUBLE PRECISION,

    -- Max favorable / adverse excursion (pct vs entry close)
    mfe_6   DOUBLE PRECISION,
    mae_6   DOUBLE PRECISION,
    mfe_12  DOUBLE PRECISION,
    mae_12  DOUBLE PRECISION,
    mfe_24  DOUBLE PRECISION,
    mae_24  DOUBLE PRECISION,

    -- ATR target / stop flags (checked over next 24 bars)
    hit_plus_0_5_atr  BOOLEAN,
    hit_plus_1_0_atr  BOOLEAN,
    hit_minus_0_5_atr BOOLEAN,
    hit_minus_1_0_atr BOOLEAN,

    created_at TIMESTAMPTZ DEFAULT now(),

    UNIQUE (ticker, ts, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_icm_ticker_ts
    ON intraday_candle_memory (ticker, ts DESC);

CREATE INDEX IF NOT EXISTS idx_icm_time_of_day
    ON intraday_candle_memory (time_of_day);

CREATE INDEX IF NOT EXISTS idx_icm_regime
    ON intraday_candle_memory (daily_regime);

-- Pre-computed similarity result for each ticker's latest candle (for API)
CREATE TABLE IF NOT EXISTS intraday_similarity_latest (
    ticker              TEXT PRIMARY KEY,
    as_of_ts            TIMESTAMPTZ,
    k_used              INTEGER,
    matched_sample      INTEGER,
    time_gate           TEXT,
    regime_gate         TEXT,
    similarity_return_6  DOUBLE PRECISION,
    similarity_hitrate   DOUBLE PRECISION,
    similarity_mfe_12    DOUBLE PRECISION,
    similarity_mae_12    DOUBLE PRECISION,
    pct_hit_plus_1atr    DOUBLE PRECISION,
    pct_hit_minus_1atr   DOUBLE PRECISION,
    top_neighbors       JSONB,
    raw_summary         JSONB,
    updated_at          TIMESTAMPTZ DEFAULT now()
);
