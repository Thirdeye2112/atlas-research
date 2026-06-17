-- Atlas Candlestick Knowledge Layer v1
-- Migration 0043
-- Created: June 2026

BEGIN;

-- ============================================
-- TABLE: candlestick_concepts
-- Canonical knowledge base for all candle patterns
-- ============================================
CREATE TABLE IF NOT EXISTS candlestick_concepts (
    id SERIAL PRIMARY KEY,
    candle_name VARCHAR(64) NOT NULL UNIQUE,
    category VARCHAR(32) NOT NULL CHECK (category IN ('single','double','triple','multi')),
    bullish_bearish_neutral VARCHAR(8) NOT NULL CHECK (bullish_bearish_neutral IN ('bullish','bearish','neutral')),
    plain_english_meaning TEXT NOT NULL,
    psychological_interpretation TEXT NOT NULL,
    why_it_forms TEXT NOT NULL,
    confirmation_rules TEXT NOT NULL,
    invalidation_rules TEXT NOT NULL,
    expected_next_behavior TEXT NOT NULL,
    larger_pattern_role TEXT NOT NULL,
    shape_definition TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candlestick_concepts_name ON candlestick_concepts(candle_name);
CREATE INDEX IF NOT EXISTS idx_candlestick_concepts_category ON candlestick_concepts(category);
CREATE INDEX IF NOT EXISTS idx_candlestick_concepts_direction ON candlestick_concepts(bullish_bearish_neutral);

-- ============================================
-- TABLE: candlestick_detection_rules
-- Machine-executable pattern detection rules
-- ============================================
CREATE TABLE IF NOT EXISTS candlestick_detection_rules (
    id SERIAL PRIMARY KEY,
    candle_name VARCHAR(64) NOT NULL REFERENCES candlestick_concepts(candle_name),
    rule_expression TEXT NOT NULL,
    required_conditions TEXT NOT NULL,
    optional_conditions TEXT,
    timeframe VARCHAR(16) NOT NULL DEFAULT 'daily',
    version INTEGER NOT NULL DEFAULT 1,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candlestick_detection_rules_name ON candlestick_detection_rules(candle_name);
CREATE INDEX IF NOT EXISTS idx_candlestick_detection_rules_version ON candlestick_detection_rules(candle_name, version);

-- ============================================
-- TABLE: candlestick_events
-- Event log of all detected patterns
-- ============================================
CREATE TABLE IF NOT EXISTS candlestick_events (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(16) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(16) NOT NULL DEFAULT 'daily',
    candle_name VARCHAR(64) NOT NULL REFERENCES candlestick_concepts(candle_name),
    direction VARCHAR(8) NOT NULL CHECK (direction IN ('bullish','bearish','neutral')),
    strength VARCHAR(16) NOT NULL DEFAULT 'standard',
    context JSONB,
    o DOUBLE PRECISION, h DOUBLE PRECISION, l DOUBLE PRECISION,
    c DOUBLE PRECISION, v DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ticker, timestamp, timeframe, candle_name)
);

CREATE INDEX IF NOT EXISTS idx_candlestick_events_ticker ON candlestick_events(ticker);
CREATE INDEX IF NOT EXISTS idx_candlestick_events_timestamp ON candlestick_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_candlestick_events_name ON candlestick_events(candle_name);
CREATE INDEX IF NOT EXISTS idx_candlestick_events_ticker_timestamp ON candlestick_events(ticker, timestamp);
CREATE INDEX IF NOT EXISTS idx_candlestick_events_timeframe ON candlestick_events(timeframe);

-- ============================================
-- TABLE: candlestick_outcomes
-- Empirical truth table with forward returns
-- ============================================
CREATE TABLE IF NOT EXISTS candlestick_outcomes (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(16) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    candle_name VARCHAR(64) NOT NULL REFERENCES candlestick_concepts(candle_name),
    event_id INTEGER REFERENCES candlestick_events(id),
    return_1 DOUBLE PRECISION, return_3 DOUBLE PRECISION, return_6 DOUBLE PRECISION,
    return_12 DOUBLE PRECISION, return_24 DOUBLE PRECISION, return_eod DOUBLE PRECISION,
    mfe DOUBLE PRECISION, mae DOUBLE PRECISION,
    hit_target BOOLEAN, hit_stop BOOLEAN,
    regime VARCHAR(32), vix_proxy DOUBLE PRECISION, vwap_position VARCHAR(16),
    prior_trend VARCHAR(16), volume_context VARCHAR(16), daily_context VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_candlestick_outcomes_ticker ON candlestick_outcomes(ticker);
CREATE INDEX IF NOT EXISTS idx_candlestick_outcomes_timestamp ON candlestick_outcomes(timestamp);
CREATE INDEX IF NOT EXISTS idx_candlestick_outcomes_name ON candlestick_outcomes(candle_name);
CREATE INDEX IF NOT EXISTS idx_candlestick_outcomes_event_id ON candlestick_outcomes(event_id);
CREATE INDEX IF NOT EXISTS idx_candlestick_outcomes_ticker_timestamp ON candlestick_outcomes(ticker, timestamp);

COMMIT;