-- ─────────────────────────────────────────────────────────────────────────────
-- 0016  sector_relative_strength
--
-- Stores per-sector ETF relative strength metrics vs SPY, computed daily
-- by scripts/compute_sector_rs.py.
--
-- One row per (date, sector_ticker).
-- Covers: XLK XLF XLE XLV XLI XLP XLU XLY XLB XLRE XLC (11 sectors)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sector_relative_strength (
    id                  SERIAL          PRIMARY KEY,
    date                DATE            NOT NULL,
    sector_ticker       VARCHAR(10)     NOT NULL,
    sector_name         VARCHAR(80)     NOT NULL DEFAULT '',

    -- Raw returns (fractional, e.g. 0.023 = +2.3%)
    return_5d           DOUBLE PRECISION,
    return_20d          DOUBLE PRECISION,
    return_60d          DOUBLE PRECISION,

    -- Relative returns vs SPY (sector_return - spy_return)
    rs_vs_spy_5d        DOUBLE PRECISION,
    rs_vs_spy_20d       DOUBLE PRECISION,
    rs_vs_spy_60d       DOUBLE PRECISION,

    -- Rank among the 11 SPDR sector ETFs (1 = strongest, 11 = weakest)
    -- Based on rs_vs_spy_20d
    rank_among_sectors  SMALLINT,

    -- Leadership flags (top-3 / bottom-3 by 20d RS)
    is_leading          BOOLEAN         NOT NULL DEFAULT FALSE,
    is_lagging          BOOLEAN         NOT NULL DEFAULT FALSE,

    computed_at         TIMESTAMPTZ     NOT NULL DEFAULT now(),

    UNIQUE (date, sector_ticker)
);

CREATE INDEX IF NOT EXISTS idx_sector_rs_date
    ON sector_relative_strength (date DESC);

CREATE INDEX IF NOT EXISTS idx_sector_rs_ticker_date
    ON sector_relative_strength (sector_ticker, date DESC);
