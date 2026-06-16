-- 0037_intraday_tables.sql
-- Atlas Intraday 5-Minute Learning Engine v1

-- 5-minute OHLCV bars (and any other timeframe)
CREATE TABLE IF NOT EXISTS intraday_bars (
    id        BIGSERIAL       PRIMARY KEY,
    ticker    TEXT            NOT NULL,
    ts        TIMESTAMPTZ     NOT NULL,          -- candle open timestamp (UTC)
    timeframe TEXT            NOT NULL DEFAULT '5m',
    open      DOUBLE PRECISION,
    high      DOUBLE PRECISION,
    low       DOUBLE PRECISION,
    close     DOUBLE PRECISION,
    volume    BIGINT,
    source    TEXT            DEFAULT 'yahoo',
    UNIQUE (ticker, ts, timeframe)
);
CREATE INDEX IF NOT EXISTS idx_ibar_ticker_ts ON intraday_bars (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_ibar_ts        ON intraday_bars (ts);

-- Technical-analysis features (EAV - populated optionally for persistence)
CREATE TABLE IF NOT EXISTS intraday_features (
    id              BIGSERIAL       PRIMARY KEY,
    ticker          TEXT            NOT NULL,
    ts              TIMESTAMPTZ     NOT NULL,
    timeframe       TEXT            NOT NULL DEFAULT '5m',
    feature_name    TEXT            NOT NULL,
    feature_value   DOUBLE PRECISION,
    feature_version TEXT            DEFAULT 'v1',
    UNIQUE (ticker, ts, timeframe, feature_name, feature_version)
);
CREATE INDEX IF NOT EXISTS idx_ifeat_ticker_ts ON intraday_features (ticker, ts);

-- Detected technical-analysis setups
CREATE TABLE IF NOT EXISTS intraday_setups (
    id                BIGSERIAL       PRIMARY KEY,
    setup_id          TEXT            UNIQUE NOT NULL,  -- deterministic key
    ticker            TEXT            NOT NULL,
    ts                TIMESTAMPTZ     NOT NULL,
    timeframe         TEXT            NOT NULL DEFAULT '5m',
    setup_type        TEXT            NOT NULL,
    direction         TEXT            NOT NULL,         -- 'long' | 'short'
    confidence_inputs JSONB,                            -- feature values at detection
    regime            TEXT,
    quality_tier      INTEGER,
    -- Daily context (attached from prediction_outcomes)
    daily_conviction  TEXT,
    daily_regime      TEXT,
    daily_vix_regime  TEXT,
    daily_ml_rank     DOUBLE PRECISION,
    daily_confluence  DOUBLE PRECISION,
    daily_jarvis      BOOLEAN,
    created_at        TIMESTAMPTZ     DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_isetup_ticker_ts   ON intraday_setups (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_isetup_setup_type  ON intraday_setups (setup_type);
CREATE INDEX IF NOT EXISTS idx_isetup_ts          ON intraday_setups (ts);

-- Forward outcomes for each setup × horizon
CREATE TABLE IF NOT EXISTS intraday_outcomes (
    id             BIGSERIAL       PRIMARY KEY,
    setup_id       TEXT            NOT NULL REFERENCES intraday_setups(setup_id),
    horizon_bars   INTEGER         NOT NULL,
    future_return  DOUBLE PRECISION,
    mfe            DOUBLE PRECISION,    -- max favorable excursion pct from entry
    mae            DOUBLE PRECISION,    -- max adverse excursion pct from entry
    hit_target     BOOLEAN,
    hit_stop       BOOLEAN,
    time_to_target INTEGER,             -- bars to target (NULL if not hit)
    time_to_stop   INTEGER,             -- bars to stop (NULL if not hit)
    UNIQUE (setup_id, horizon_bars)
);
CREATE INDEX IF NOT EXISTS idx_iout_setup_id ON intraday_outcomes (setup_id);

-- Walk-forward validated and promoted setups (output table)
CREATE TABLE IF NOT EXISTS intraday_promoted_setups (
    id                   BIGSERIAL       PRIMARY KEY,
    setup_type           TEXT            NOT NULL,
    direction            TEXT            NOT NULL,
    timeframe            TEXT            NOT NULL DEFAULT '5m',
    -- In-sample metrics
    sample_size          INTEGER,
    win_rate             DOUBLE PRECISION,
    expectancy           DOUBLE PRECISION,
    profit_factor        DOUBLE PRECISION,
    max_drawdown         DOUBLE PRECISION,
    -- Out-of-sample metrics
    oos_sample_size      INTEGER,
    oos_win_rate         DOUBLE PRECISION,
    oos_expectancy       DOUBLE PRECISION,
    oos_profit_factor    DOUBLE PRECISION,
    -- Promotion decision
    walk_forward_passed  BOOLEAN,
    promoted             BOOLEAN         DEFAULT FALSE,
    notes                TEXT,
    scored_date          DATE            DEFAULT CURRENT_DATE,
    UNIQUE (setup_type, direction, timeframe, scored_date)
);
