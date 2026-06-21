-- Migration 0048: gaps — classic daily gaps and Fair Value Gap (FVG / 3-bar imbalance)
--
-- New table only. Does NOT alter raw_bars, intraday_bars, pattern_memory, or any
-- existing table. Populated by scripts/build_gaps.py (read-only on price tables).
--
-- gap_type values:
--   'classic' — daily only: today.open > prior_day.high (up) or < prior_day.low (down)
--   'fvg'     — any timeframe: 3-bar imbalance (C1.high < C3.low or C1.low > C3.high)
--
-- direction values:
--   'up'   — bullish gap (classic gap-up, or bullish FVG)
--   'down' — bearish gap (classic gap-down, or bearish FVG)
--
-- Look-ahead: detect_close_ts is the timestamp at which this gap becomes known.
--   For 'classic': = ts (today's date midnight UTC; gap known at today's open)
--   For 'fvg':     = ts = C3.ts (C3 open); gap is confirmed at C3's bar CLOSE
--                  (ts + 5min for 5m bars, or day's close for daily bars)
--
-- Forward labels (NOT detection features — do NOT use in signal generation):
--   filled  — true once price trades into the gap zone after detection
--   fill_ts — timestamp of the fill bar (NULL until filled)

CREATE TABLE IF NOT EXISTS gaps (
    id              BIGSERIAL           PRIMARY KEY,
    ticker          TEXT                NOT NULL,
    ts              TIMESTAMPTZ         NOT NULL,          -- detection bar timestamp (C3 open for FVG)
    timeframe       TEXT                NOT NULL,           -- 'daily', '5m'
    gap_type        TEXT                NOT NULL,           -- 'classic', 'fvg'
    direction       TEXT                NOT NULL,           -- 'up', 'down'
    zone_top        DOUBLE PRECISION    NOT NULL,           -- upper edge of gap zone
    zone_bottom     DOUBLE PRECISION    NOT NULL,           -- lower edge of gap zone
    size_pct        DOUBLE PRECISION    NOT NULL,           -- (zone_top-zone_bottom)/zone_bottom*100
    detect_close_ts TIMESTAMPTZ         NOT NULL,           -- when this gap is known (see note above)
    bar1_ts         TIMESTAMPTZ,                            -- C1 timestamp (FVG) or prior-day (classic)
    bar3_ts         TIMESTAMPTZ,                            -- C3 timestamp (FVG), NULL for classic
    -- Forward-looking labels — clearly NOT detection features
    filled          BOOLEAN             DEFAULT FALSE,
    fill_ts         TIMESTAMPTZ,
    computed_at     TIMESTAMPTZ         NOT NULL DEFAULT now(),
    UNIQUE (ticker, ts, timeframe, gap_type, direction)
);

CREATE INDEX IF NOT EXISTS idx_gaps_ticker_ts       ON gaps (ticker, ts);
CREATE INDEX IF NOT EXISTS idx_gaps_ticker_tf_ts    ON gaps (ticker, timeframe, ts);
CREATE INDEX IF NOT EXISTS idx_gaps_type_dir        ON gaps (gap_type, direction);
CREATE INDEX IF NOT EXISTS idx_gaps_ts              ON gaps (ts);
