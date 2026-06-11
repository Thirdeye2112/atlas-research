-- 0011: Transcript hypothesis schema enhancements
-- Extends 0003_transcript_pipeline with versioning, posteriors, leaderboard
-- view, and actionable signal events table.

ALTER TABLE hypothesis_tests
    ADD COLUMN IF NOT EXISTS backtest_version INTEGER NOT NULL DEFAULT 1;

ALTER TABLE hypothesis_results
    ADD COLUMN IF NOT EXISTS confidence_posterior DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS bayes_factor         DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_htests_version
    ON hypothesis_tests(hypothesis_id, backtest_version DESC);

CREATE OR REPLACE VIEW hypothesis_leaderboard AS
SELECT
    h.hypothesis_id,
    ts.title            AS source_title,
    ts.event_date       AS source_date,
    ts.speaker,
    h.extracted_claim,
    h.direction,
    h.test_status,
    r.horizon_days,
    r.sample_size,
    r.hit_rate,
    r.avg_return,
    r.sharpe,
    r.p_value,
    r.composite_score,
    r.confidence_posterior,
    r.created_at        AS result_date
FROM hypothesis_results r
JOIN research_hypotheses h  ON h.hypothesis_id = r.hypothesis_id
LEFT JOIN transcript_sources ts ON ts.source_id = h.source_id
WHERE (r.p_value IS NULL OR r.p_value < 0.1)
ORDER BY r.composite_score DESC NULLS LAST;

CREATE TABLE IF NOT EXISTS transcript_signal_events (
    id            SERIAL PRIMARY KEY,
    hypothesis_id TEXT REFERENCES research_hypotheses(hypothesis_id),
    ticker        TEXT NOT NULL,
    signal_date   DATE NOT NULL,
    signal_type   TEXT NOT NULL DEFAULT 'hypothesis',
    direction     TEXT NOT NULL,
    confidence    DOUBLE PRECISION,
    source_id     TEXT REFERENCES transcript_sources(source_id),
    notes         TEXT,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (hypothesis_id, ticker, signal_date)
);

CREATE INDEX IF NOT EXISTS idx_tse_ticker_date
    ON transcript_signal_events(ticker, signal_date DESC);

CREATE INDEX IF NOT EXISTS idx_tse_signal_type
    ON transcript_signal_events(signal_type, signal_date DESC);