-- Migration 0020: IPO registry and backtest results
-- Tracks IPO events inferred from raw_bars first-appearance dates

CREATE TABLE IF NOT EXISTS ipo_registry (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(16) NOT NULL UNIQUE,
    ipo_date        DATE NOT NULL,
    ipo_price       NUMERIC(12,4),
    company_name    VARCHAR(200),
    sector          VARCHAR(100),
    exchange        VARCHAR(20),
    lockup_days     INTEGER DEFAULT 180,
    source          VARCHAR(50) DEFAULT 'inferred',
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ipo_registry_date ON ipo_registry(ipo_date);
CREATE INDEX IF NOT EXISTS idx_ipo_registry_sector ON ipo_registry(sector);

CREATE TABLE IF NOT EXISTS ipo_backtest_results (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(16) NOT NULL,
    horizon_days    INTEGER NOT NULL,
    return_pct      NUMERIC(10,4),
    vs_spy_pct      NUMERIC(10,4),
    day1_pop_pct    NUMERIC(10,4),
    computed_at     TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(ticker, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_ipo_backtest_ticker ON ipo_backtest_results(ticker);
CREATE INDEX IF NOT EXISTS idx_ipo_backtest_horizon ON ipo_backtest_results(horizon_days);

INSERT INTO schema_migrations(migration_name, applied_at) VALUES ('0020_ipo_registry.sql', NOW())
ON CONFLICT (migration_name) DO NOTHING;
