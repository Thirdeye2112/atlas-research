-- ─────────────────────────────────────────────────────────────────────────────
-- 0017  market_calendar
--
-- Key market dates: FOMC meetings, options expirations, quarter-ends,
-- triple witching. Populated by scripts/seed_market_calendar.py.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS market_calendar (
    id              SERIAL          PRIMARY KEY,
    date            DATE            NOT NULL,
    event_type      VARCHAR(40)     NOT NULL,
    -- fomc_meeting | options_expiry | quarter_end | triple_witching | half_year_end
    description     VARCHAR(200)    NOT NULL DEFAULT '',
    is_trading_day  BOOLEAN         NOT NULL DEFAULT TRUE,
    metadata        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),

    UNIQUE (date, event_type)
);

CREATE INDEX IF NOT EXISTS idx_market_cal_date
    ON market_calendar (date);

CREATE INDEX IF NOT EXISTS idx_market_cal_type
    ON market_calendar (event_type, date);
