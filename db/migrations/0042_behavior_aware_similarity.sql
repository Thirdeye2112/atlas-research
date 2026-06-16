-- Migration 0042: Behavior-Aware Similarity Tables
-- ===================================================
-- market_behavior_concepts : enriched behavior definitions with intraday weights + feature index
-- intraday_behavior_events  : bridge table (ticker, date) -> active behaviors for fast intraday lookup
-- intraday_candle_memory_v2 : v1 memory + 20-dim behavior vector -> 36-dim combined feature vector
-- intraday_similarity_v2_results : comparison backtest results (4 variants)
-- intraday_behavior_importance    : which behavior labels improve prediction quality

-- 1. market_behavior_concepts
CREATE TABLE IF NOT EXISTS market_behavior_concepts (
    behavior_id          TEXT PRIMARY KEY,
    category             TEXT NOT NULL,
    direction            TEXT NOT NULL,
    description          TEXT,
    intraday_weight      REAL NOT NULL DEFAULT 1.5,
    is_daily_persistent  BOOLEAN DEFAULT TRUE,
    feature_index        INTEGER,
    active               BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- 2. intraday_behavior_events: daily behavior state per ticker, indexed for fast candle joins
CREATE TABLE IF NOT EXISTS intraday_behavior_events (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    event_date      DATE NOT NULL,
    behavior_id     TEXT NOT NULL,
    intensity       REAL NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, event_date, behavior_id)
);
CREATE INDEX IF NOT EXISTS idx_ibe_ticker_date ON intraday_behavior_events (ticker, event_date);
CREATE INDEX IF NOT EXISTS idx_ibe_behavior_id ON intraday_behavior_events (behavior_id);

-- 3. intraday_candle_memory_v2: v1 columns + behavior extension
CREATE TABLE IF NOT EXISTS intraday_candle_memory_v2 (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    timeframe           TEXT NOT NULL DEFAULT '5m',
    feature_version     TEXT NOT NULL DEFAULT 'behavior_v2',
    -- Candle fields
    open_price          REAL,
    high_price          REAL,
    low_price           REAL,
    close_price         REAL,
    volume              BIGINT,
    body_pct            REAL,
    upper_wick_ratio    REAL,
    lower_wick_ratio    REAL,
    is_green            BOOLEAN,
    range_pct           REAL,
    vol_ratio           REAL,
    vol_zscore          REAL,
    vwap_dist_pct       REAL,
    or_position         REAL,
    ema9_slope_norm     REAL,
    rsi14               REAL,
    macd_hist_norm      REAL,
    atr_pct             REAL,
    tod_min             INTEGER,
    time_of_day         TEXT,
    candle_num          INTEGER,
    -- Daily context
    daily_ml_rank       REAL,
    daily_conviction    TEXT,
    daily_confluence    REAL,
    daily_regime        TEXT,
    daily_vix           TEXT,
    daily_jarvis        TEXT,
    -- Feature vectors
    feature_vector_v1   DOUBLE PRECISION[],   -- 16-dim v1 vector
    behavior_vector     DOUBLE PRECISION[],   -- 20-dim behavior intensity vector
    active_behaviors    TEXT[],               -- list of detected behavior_ids for this candle's day
    behavior_count      SMALLINT DEFAULT 0,
    feature_vector      DOUBLE PRECISION[],   -- 36-dim combined (v1 || behavior)
    -- Forward outcomes (same as v1)
    future_return_1     REAL,
    future_return_3     REAL,
    future_return_6     REAL,
    future_return_12    REAL,
    future_return_24    REAL,
    future_return_eod   REAL,
    mfe_6               REAL,
    mae_6               REAL,
    mfe_12              REAL,
    mae_12              REAL,
    mfe_24              REAL,
    mae_24              REAL,
    hit_plus_0_5_atr    BOOLEAN,
    hit_plus_1_0_atr    BOOLEAN,
    hit_minus_0_5_atr   BOOLEAN,
    hit_minus_1_0_atr   BOOLEAN,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, ts, timeframe)
);
CREATE INDEX IF NOT EXISTS idx_icmv2_ticker_ts   ON intraday_candle_memory_v2 (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_icmv2_time_of_day ON intraday_candle_memory_v2 (time_of_day);
CREATE INDEX IF NOT EXISTS idx_icmv2_regime      ON intraday_candle_memory_v2 (daily_regime);

-- 4. Comparison backtest results (4 variants x multiple K x multiple horizons)
CREATE TABLE IF NOT EXISTS intraday_similarity_v2_results (
    id              BIGSERIAL PRIMARY KEY,
    run_date        DATE NOT NULL,
    variant         TEXT NOT NULL,
    k               INTEGER NOT NULL,
    horizon         INTEGER NOT NULL,
    is_size         INTEGER,
    oos_size        INTEGER,
    hit_rate        REAL,
    expectancy      REAL,
    profit_factor   REAL,
    mfe_accuracy    REAL,
    mae_accuracy    REAL,
    calibration_mse REAL,
    top_q_exp       REAL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_date, variant, k, horizon)
);

-- 5. Behavior label importance (which behaviors add predictive value)
CREATE TABLE IF NOT EXISTS intraday_behavior_importance (
    id               BIGSERIAL PRIMARY KEY,
    run_date         DATE NOT NULL,
    behavior_id      TEXT NOT NULL,
    n_with           INTEGER,
    n_without        INTEGER,
    hit_rate_with    REAL,
    hit_rate_without REAL,
    hit_lift         REAL,
    expectancy_with  REAL,
    expectancy_without REAL,
    exp_lift         REAL,
    is_informative   BOOLEAN,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_date, behavior_id)
);
