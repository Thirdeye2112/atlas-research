-- =============================================================
-- Migration 0006: IPO outcome engine schema (Phase 4C)
-- Tables: ipo_events, ipo_outcomes
--
-- ipo_events  — one row per IPO, all computed metrics
--               baseline price = day1_open (opening_price)
-- ipo_outcomes — aggregated study results (probability tables)
-- =============================================================

-- ipo_events: one row per IPO ticker
-- opening_price = day1_open (what investors who bought at open paid)
-- all returns computed from opening_price, NOT day1_close
CREATE TABLE IF NOT EXISTS ipo_events (
    ticker                  TEXT    PRIMARY KEY
                            REFERENCES ipo_registry(ticker) ON DELETE CASCADE,
    ipo_date                DATE,
    offer_price             DOUBLE PRECISION,   -- ipo_registry.ipo_price
    opening_price           DOUBLE PRECISION,   -- ipo_registry.day1_open
    lockup_expiration       DATE,               -- ipo_date + lockup_days

    -- Day 1 OHLC (from ipo_registry)
    day1_high               DOUBLE PRECISION,
    day1_low                DOUBLE PRECISION,
    day1_close              DOUBLE PRECISION,

    -- Week 1: trading days 1-5 (bars 0-4)
    week1_high              DOUBLE PRECISION,
    week1_low               DOUBLE PRECISION,
    week1_close             DOUBLE PRECISION,
    week1_return            DOUBLE PRECISION,   -- (week1_close / opening_price - 1) * 100

    -- Month 1: trading days 1-21 (bars 0-20)
    month1_high             DOUBLE PRECISION,
    month1_low              DOUBLE PRECISION,
    month1_close            DOUBLE PRECISION,
    month1_return           DOUBLE PRECISION,   -- (month1_close / opening_price - 1) * 100

    -- Key Day-1 ratios
    open_vs_offer           DOUBLE PRECISION,   -- (opening - offer) / offer * 100; the IPO pop
    close_vs_open           DOUBLE PRECISION,   -- (day1_close - opening) / opening * 100

    -- Peak analysis: within first 252 trading days
    peak_vs_open            DOUBLE PRECISION,   -- (peak_high / opening - 1) * 100
    days_to_peak            INTEGER,            -- 0-indexed trading days from IPO to peak
    retracement_from_peak   DOUBLE PRECISION,   -- (peak_high - min_after_peak) / peak_high * 100

    -- Timeline milestones (first day where close crosses threshold)
    -- 0 = happens on Day 1 itself; NULL = never revisited
    days_to_revisit_open    INTEGER,
    days_to_revisit_offer   INTEGER,

    -- Post-week1 behavior: bars 5-20 (for momentum studies)
    post_week1_high_20d     DOUBLE PRECISION,   -- max high in bars 5-20
    post_week1_low_20d      DOUBLE PRECISION,   -- min low in bars 5-20
    post_week1_return_20d   DOUBLE PRECISION,   -- (bar20_close / week1_close - 1) * 100

    -- Bucketing (derived, for GROUP BY queries)
    bucket_open_vs_offer    TEXT,   -- neg | 0-10 | 10-20 | 20-50 | 50+
    bucket_peak_vs_open     TEXT,   -- neg | 0-10 | 10-20 | 20-40 | 40-60 | 60+
    bucket_retracement      TEXT,   -- 0-10 | 10-25 | 25-50 | 50+

    computed_at             TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ipo_events_bucket_gap
    ON ipo_events(bucket_open_vs_offer);
CREATE INDEX IF NOT EXISTS idx_ipo_events_ipo_date
    ON ipo_events(ipo_date);
CREATE INDEX IF NOT EXISTS idx_ipo_events_revisit
    ON ipo_events(days_to_revisit_open, days_to_revisit_offer);

-- ipo_outcomes: aggregated study results
-- study_name  — e.g. "revisit_open_by_gap", "week1_momentum"
-- bucket_name — e.g. "20-50" or "" for overall
CREATE TABLE IF NOT EXISTS ipo_outcomes (
    id              SERIAL      PRIMARY KEY,
    study_name      TEXT        NOT NULL,
    bucket_name     TEXT        NOT NULL DEFAULT '',
    bucket_label    TEXT,
    n               INTEGER,
    pct_positive    DOUBLE PRECISION,   -- e.g. % that revisit open
    median_value    DOUBLE PRECISION,   -- study-specific median (days, return, etc.)
    p25_value       DOUBLE PRECISION,
    p75_value       DOUBLE PRECISION,
    avg_value       DOUBLE PRECISION,
    notes           TEXT,
    computed_at     TIMESTAMPTZ DEFAULT now(),
    UNIQUE (study_name, bucket_name)
);
