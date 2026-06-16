-- 0034_trade_attribution.sql
-- Atlas Trade Attribution Engine v1
-- One row per directional prediction trade (ticker, entry_date = PRIMARY KEY)

CREATE TABLE IF NOT EXISTS trade_attribution (
    -- Identity
    ticker                    TEXT          NOT NULL,
    entry_date                DATE          NOT NULL,
    exit_date                 DATE,

    -- Prices
    entry_price               DOUBLE PRECISION,
    exit_price                DOUBLE PRECISION,

    -- Returns by hold period (as % of entry, directionally adjusted)
    return_pct                DOUBLE PRECISION,        -- 5d hold × direction
    return_pct_10d            DOUBLE PRECISION,        -- 10d hold × direction
    return_pct_20d            DOUBLE PRECISION,        -- 20d hold × direction

    -- Trade geometry
    holding_days              INTEGER     DEFAULT 5,
    max_favorable_excursion   DOUBLE PRECISION,        -- as % of entry
    max_adverse_excursion     DOUBLE PRECISION,        -- as % of entry
    profit_factor             DOUBLE PRECISION,        -- MFE / MAE per-trade ratio

    -- Exit classification
    exit_reason               TEXT        DEFAULT '5d_hold',
    stop_hit                  BOOLEAN     DEFAULT FALSE,
    target1_hit               BOOLEAN     DEFAULT FALSE,
    target2_hit               BOOLEAN     DEFAULT FALSE,
    target3_hit               BOOLEAN     DEFAULT FALSE,
    signal_flip_exit          BOOLEAN     DEFAULT FALSE,
    time_exit                 BOOLEAN     DEFAULT TRUE,

    -- ATR-based levels (absolute %)
    atr_stop_return_pct       DOUBLE PRECISION,        -- return if stopped out
    atr_pct                   DOUBLE PRECISION,        -- ATR as % of entry at entry

    -- Prediction context (copied from prediction_outcomes)
    prediction_rank           DOUBLE PRECISION,
    prediction_prob           DOUBLE PRECISION,
    calibrated_confidence     DOUBLE PRECISION,
    predicted_direction       INTEGER,
    jarvis_green              BOOLEAN,
    quality_tier              INTEGER,
    sector_regime             TEXT,
    vix_regime                TEXT,
    confluence_score          DOUBLE PRECISION,
    conviction_level          TEXT,
    ml_signal_strength        DOUBLE PRECISION,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (ticker, entry_date)
);

CREATE INDEX IF NOT EXISTS idx_ta_entry_date ON trade_attribution(entry_date);
CREATE INDEX IF NOT EXISTS idx_ta_quality_tier ON trade_attribution(quality_tier);
CREATE INDEX IF NOT EXISTS idx_ta_conviction ON trade_attribution(conviction_level);
CREATE INDEX IF NOT EXISTS idx_ta_sector_regime ON trade_attribution(sector_regime);
CREATE INDEX IF NOT EXISTS idx_ta_vix_regime ON trade_attribution(vix_regime);
CREATE INDEX IF NOT EXISTS idx_ta_jarvis ON trade_attribution(jarvis_green);
