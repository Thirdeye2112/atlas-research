-- Migration 0056: trade_alerts
-- Daily output of the all-methods setup scan (scripts/daily_scan.py): every
-- tradeable setup that fired on the latest bar, across ALL methods (mean-reversion
-- /mr_score, candlestick, chart-structure, significant-move follow-through), with
-- its decision-bar TA, the historical base rate mined from deep_dive_events, and a
-- combined conviction score. atlas-alpha surfaces these via DATABASE_URL_RESEARCH.
-- New table only.

CREATE TABLE IF NOT EXISTS trade_alerts (
    id            BIGSERIAL PRIMARY KEY,
    scan_date     DATE    NOT NULL,            -- date the scan ran
    ts            DATE    NOT NULL,            -- the signal bar
    ticker        TEXT    NOT NULL,
    method        TEXT    NOT NULL,            -- mean_reversion|candlestick|structure|move
    name          TEXT    NOT NULL,
    direction     TEXT,                        -- long|short
    mr_score      DOUBLE PRECISION,
    mr_oversold   SMALLINT,
    confluence_n  SMALLINT,
    above_ema200  SMALLINT,
    rsi           DOUBLE PRECISION,
    cc_ret        DOUBLE PRECISION,
    -- historical base rate for this exact setup (from deep_dive_events)
    base_n        INTEGER,
    base_avg_fwd5 DOUBLE PRECISION,
    base_win5     DOUBLE PRECISION,
    conviction    DOUBLE PRECISION,            -- ranking score
    needs_5m_confirm BOOLEAN DEFAULT TRUE,     -- act next session on VWAP reclaim
    explained_by  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scan_date, ticker, method, name, direction)
);

CREATE INDEX IF NOT EXISTS idx_alerts_scan    ON trade_alerts (scan_date);
CREATE INDEX IF NOT EXISTS idx_alerts_conv     ON trade_alerts (scan_date, conviction DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_ticker   ON trade_alerts (ticker, scan_date);
