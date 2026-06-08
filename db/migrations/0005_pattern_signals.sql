-- =============================================================
-- Migration 0005: Pattern signals table (Layer 3)
-- Stores daily candlestick and chart pattern detections with
-- forward outcome returns for statistical analysis.
-- =============================================================

CREATE TABLE IF NOT EXISTS pattern_signals (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT        NOT NULL,
    signal_date     DATE        NOT NULL,
    pattern_name    TEXT        NOT NULL,
    pattern_type    TEXT        NOT NULL,   -- single_bar, two_bar, three_bar, chart
    direction       TEXT        NOT NULL,   -- bullish, bearish, neutral
    strength_score  DOUBLE PRECISION,       -- 0–1 composite strength
    -- Forward returns (log) — filled by outcome resolver
    fwd_return_1d   DOUBLE PRECISION,
    fwd_return_3d   DOUBLE PRECISION,
    fwd_return_5d   DOUBLE PRECISION,
    fwd_return_10d  DOUBLE PRECISION,
    fwd_return_20d  DOUBLE PRECISION,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (ticker, signal_date, pattern_name)
);

CREATE INDEX IF NOT EXISTS idx_pattern_signals_ticker_date
    ON pattern_signals(ticker, signal_date DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_signals_pattern_date
    ON pattern_signals(pattern_name, signal_date DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_signals_direction
    ON pattern_signals(direction, signal_date DESC);

-- Pattern outcome statistics view (aggregate hit rates per pattern)
CREATE OR REPLACE VIEW pattern_outcome_stats AS
SELECT
    pattern_name,
    direction,
    COUNT(*)                                        AS total_signals,
    COUNT(fwd_return_5d)                            AS with_outcomes,
    ROUND(AVG(fwd_return_5d)::numeric, 6)           AS mean_fwd_5d,
    ROUND(STDDEV(fwd_return_5d)::numeric, 6)        AS std_fwd_5d,
    ROUND(AVG(fwd_return_1d)::numeric, 6)           AS mean_fwd_1d,
    ROUND(AVG(fwd_return_10d)::numeric, 6)          AS mean_fwd_10d,
    ROUND(AVG(fwd_return_20d)::numeric, 6)          AS mean_fwd_20d,
    ROUND(
        SUM(CASE WHEN fwd_return_5d > 0 THEN 1 ELSE 0 END)::numeric /
        NULLIF(COUNT(fwd_return_5d), 0), 4
    )                                               AS hit_rate_5d,
    MIN(signal_date)                                AS first_signal,
    MAX(signal_date)                                AS last_signal
FROM pattern_signals
GROUP BY pattern_name, direction
ORDER BY ABS(mean_fwd_5d) DESC NULLS LAST;
