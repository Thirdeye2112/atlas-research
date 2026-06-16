-- Migration 0031: prediction_outcomes
-- Stores resolved prediction outcomes for closed-loop learning.
-- Populated by scripts/compute_prediction_outcomes.py.
-- PRIMARY KEY: (ticker, prediction_date, model_version)

CREATE TABLE IF NOT EXISTS prediction_outcomes (
    ticker                TEXT        NOT NULL,
    prediction_date       DATE        NOT NULL,
    model_version         TEXT        NOT NULL DEFAULT 'v1',
    feature_set_version   TEXT        NOT NULL DEFAULT 'v1',

    -- What Atlas predicted
    predicted_rank        NUMERIC(7,5),      -- cross-sectional rank percentile 0-1
    predicted_prob        NUMERIC(7,5),      -- raw ML probability
    predicted_return      NUMERIC(10,6),     -- estimated forward return
    predicted_direction   SMALLINT,          -- +1 bullish / -1 bearish / 0 neutral

    -- What actually happened
    actual_return_5d      NUMERIC(10,6),
    actual_return_10d     NUMERIC(10,6),
    actual_return_20d     NUMERIC(10,6),

    -- Was the prediction correct?
    direction_correct_5d  BOOLEAN,
    direction_correct_10d BOOLEAN,
    direction_correct_20d BOOLEAN,

    -- Rank accuracy
    rank_quintile         SMALLINT,          -- 1=bottom 5th … 5=top 5th of predicted_rank on that date
    outcome_quintile      SMALLINT,          -- 1=bottom 5th … 5=top 5th of actual_return_5d on that date
    rank_hit              BOOLEAN,           -- top-quintile prediction with top-2-quintile outcome

    -- Context at prediction time
    jarvis_green          BOOLEAN,           -- jarvis_quality_adjusted > 0
    quality_tier          SMALLINT,          -- 1=large/mid cap … 4=micro/junk
    above_sma200          BOOLEAN,           -- individual stock close > its own SMA200
    sector_regime         TEXT,              -- 'bull' / 'bear' / 'range'  (SPY market_trend)
    vix_regime            TEXT,              -- 'low' / 'moderate' / 'high' (realized_vol_20 proxy)

    -- Confluence context
    confluence_score      NUMERIC(6,2),
    conviction_level      TEXT,              -- VERY_HIGH / HIGH / MODERATE / LOW / NEUTRAL
    ml_signal_strength    NUMERIC(7,5),      -- ml_str (0-1)

    created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (ticker, prediction_date, model_version)
);

CREATE INDEX IF NOT EXISTS idx_po_date         ON prediction_outcomes(prediction_date);
CREATE INDEX IF NOT EXISTS idx_po_conviction   ON prediction_outcomes(conviction_level);
CREATE INDEX IF NOT EXISTS idx_po_jarvis       ON prediction_outcomes(jarvis_green);
CREATE INDEX IF NOT EXISTS idx_po_quality_tier ON prediction_outcomes(quality_tier);
CREATE INDEX IF NOT EXISTS idx_po_vix_regime   ON prediction_outcomes(vix_regime);
CREATE INDEX IF NOT EXISTS idx_po_sector       ON prediction_outcomes(sector_regime);
CREATE INDEX IF NOT EXISTS idx_po_direction    ON prediction_outcomes(predicted_direction);
CREATE INDEX IF NOT EXISTS idx_po_rank_hit     ON prediction_outcomes(rank_hit);
