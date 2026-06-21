-- Migration 0047: vwap_5m — session-anchored VWAP feature table for 5-minute bars
--
-- New table only. Does NOT alter intraday_bars, pattern_memory, or any existing table.
-- Populated by scripts/build_vwap_5m.py (read-only on intraday_bars).
--
-- Schema notes:
--   ticker       — underlying symbol (matches intraday_bars.ticker)
--   ts           — bar open timestamp, UTC (matches intraday_bars.ts for timeframe='5m')
--   vwap         — session-anchored VWAP at this bar: cumsum(tp*vol)/cumsum(vol)
--                  where tp = (high+low+close)/3.  Resets each ET trading day.
--   dist_from_vwap — (close - vwap) / vwap, signed, fractional (NOT percent).
--                  Negative = below VWAP. Null when vwap=0 (pathological).
--   above_vwap   — true iff close > vwap at this bar
--   session_date — ET calendar date of the bar (America/New_York)

CREATE TABLE IF NOT EXISTS vwap_5m (
    id              BIGSERIAL           PRIMARY KEY,
    ticker          TEXT                NOT NULL,
    ts              TIMESTAMPTZ         NOT NULL,
    vwap            DOUBLE PRECISION    NOT NULL,
    dist_from_vwap  DOUBLE PRECISION,
    above_vwap      BOOLEAN             NOT NULL,
    session_date    DATE                NOT NULL,
    computed_at     TIMESTAMPTZ         NOT NULL DEFAULT now(),
    UNIQUE (ticker, ts)
);

CREATE INDEX IF NOT EXISTS idx_vwap_5m_ticker_ts      ON vwap_5m (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_vwap_5m_session_date   ON vwap_5m (ticker, session_date);
