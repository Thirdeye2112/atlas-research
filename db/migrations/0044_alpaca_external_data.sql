-- Migration 0044: alpaca_external_data (corporate_actions + news_events)
-- Real external data pulled from Alpaca for split/dividend/merger adjustment
-- and news-based features over the clean universe (2020-01-01 -> today).
-- Populated by scripts/ingest_alpaca_corpactions_news.py.

-- ---------------------------------------------------------------------------
-- corporate_actions: one normalized row per corporate action, all CA types.
-- ca_type holds Alpaca's PLURAL key (forward_splits, cash_mergers, ...).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS corporate_actions (
    ca_type         TEXT        NOT NULL,   -- Alpaca plural key: forward_splits, cash_dividends, ...
    symbol          TEXT        NOT NULL,   -- primary affected ticker (per-type extraction)
    related_symbol  TEXT,                   -- acquirer / new_symbol / source counterpart
    cusip           TEXT,

    -- splits
    old_rate        NUMERIC(18,6),
    new_rate        NUMERIC(18,6),

    -- dividends / cash merger / redemption / rights
    rate            NUMERIC(18,6),
    cash_amount     NUMERIC(18,6),          -- unified merger cash (rate if not None else cash_rate)

    -- dates
    process_date    DATE,
    ex_date         DATE,
    effective_date  DATE,
    record_date     DATE,
    payable_date    DATE,

    -- dividend flags
    special         BOOLEAN,
    "foreign"       BOOLEAN,

    raw             JSONB       NOT NULL,    -- full original record for audit / re-derivation
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dedup key: same action type for same symbol on same processing/effective date.
CREATE UNIQUE INDEX IF NOT EXISTS uq_corporate_actions
    ON corporate_actions (
        ca_type,
        symbol,
        COALESCE(cusip, ''),
        process_date,
        COALESCE(ex_date, effective_date)
    );

CREATE INDEX IF NOT EXISTS idx_ca_symbol  ON corporate_actions (symbol);
CREATE INDEX IF NOT EXISTS idx_ca_type    ON corporate_actions (ca_type);
CREATE INDEX IF NOT EXISTS idx_ca_ex_date ON corporate_actions (ex_date);

-- ---------------------------------------------------------------------------
-- news_events: fan-out, one row per (article, symbol). Universe-filtered.
-- Full HTML content is intentionally NOT stored (re-pullable from Alpaca).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS news_events (
    news_id     BIGINT      NOT NULL,       -- Alpaca article id
    symbol      TEXT        NOT NULL,       -- one row per mentioned symbol in our universe
    headline    TEXT,
    summary     TEXT,
    source      TEXT,
    url         TEXT,
    created_at  TIMESTAMP WITH TIME ZONE,   -- article publish time
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (news_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_news_symbol     ON news_events (symbol);
CREATE INDEX IF NOT EXISTS idx_news_created_at ON news_events (created_at);
