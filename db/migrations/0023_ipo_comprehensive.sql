-- Migration 0023: Comprehensive IPO analysis engine
-- Expands ipo_registry with full day1 OHLCV and metadata columns.
-- Creates ipo_performance table with all horizon returns, drawdowns,
-- volume profile, and market-context fields.
-- Drops the old stub ipo_backtest_results table (was empty).

-- ── Expand ipo_registry ───────────────────────────────────────────────────────

ALTER TABLE ipo_registry
  ADD COLUMN IF NOT EXISTS day1_open          NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS day1_close         NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS day1_high          NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS day1_low           NUMERIC(12,4),
  ADD COLUMN IF NOT EXISTS day1_volume        BIGINT,
  ADD COLUMN IF NOT EXISTS day1_pop_pct       NUMERIC(8,4),
  ADD COLUMN IF NOT EXISTS day1_category      VARCHAR(20),   -- hot/warm/cold/broken
  ADD COLUMN IF NOT EXISTS industry           VARCHAR(100),
  ADD COLUMN IF NOT EXISTS market_cap_at_ipo  NUMERIC(20,2),
  ADD COLUMN IF NOT EXISTS shares_offered     BIGINT,
  ADD COLUMN IF NOT EXISTS underwriter        VARCHAR(200),
  ADD COLUMN IF NOT EXISTS exchange           VARCHAR(20),
  ADD COLUMN IF NOT EXISTS year1_category     VARCHAR(20);   -- winner/moderate/loser/disaster

-- ── Comprehensive IPO performance table ──────────────────────────────────────

DROP TABLE IF EXISTS ipo_backtest_results;

CREATE TABLE IF NOT EXISTS ipo_performance (
  id                  SERIAL PRIMARY KEY,
  ticker              VARCHAR(16) NOT NULL UNIQUE REFERENCES ipo_registry(ticker),
  computed_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

  -- Returns at horizons (vs day1 close)
  return_1d           NUMERIC(10,4),
  return_5d           NUMERIC(10,4),
  return_10d          NUMERIC(10,4),
  return_20d          NUMERIC(10,4),
  return_30d          NUMERIC(10,4),
  return_60d          NUMERIC(10,4),
  return_90d          NUMERIC(10,4),
  return_120d         NUMERIC(10,4),
  return_150d         NUMERIC(10,4),
  return_180d         NUMERIC(10,4),
  return_252d         NUMERIC(10,4),

  -- Alpha vs SPY over same horizons
  vs_spy_1d           NUMERIC(10,4),
  vs_spy_5d           NUMERIC(10,4),
  vs_spy_10d          NUMERIC(10,4),
  vs_spy_20d          NUMERIC(10,4),
  vs_spy_30d          NUMERIC(10,4),
  vs_spy_60d          NUMERIC(10,4),
  vs_spy_90d          NUMERIC(10,4),
  vs_spy_120d         NUMERIC(10,4),
  vs_spy_150d         NUMERIC(10,4),
  vs_spy_180d         NUMERIC(10,4),
  vs_spy_252d         NUMERIC(10,4),

  -- Max drawdown in each window (from day1 close)
  max_dd_30d          NUMERIC(10,4),
  max_dd_90d          NUMERIC(10,4),
  max_dd_180d         NUMERIC(10,4),
  max_dd_252d         NUMERIC(10,4),

  -- Peak analysis
  days_to_first_peak  INTEGER,
  peak_return         NUMERIC(10,4),   -- (peak - day1_close) / day1_close
  peak_to_year_end    NUMERIC(10,4),   -- (year_end_close - peak) / peak

  -- Volume profile
  avg_volume_week1    BIGINT,          -- avg daily vol days 1-5
  avg_volume_month1   BIGINT,          -- avg daily vol days 1-20
  avg_volume_month3   BIGINT,          -- avg daily vol days 40-60
  volume_decay_pct    NUMERIC(10,4),   -- (month3 - week1) / week1

  -- Volatility
  volatility_30d      NUMERIC(10,4),   -- annualised daily-return std
  volatility_90d      NUMERIC(10,4),

  -- Market context at IPO date
  spy_regime_at_ipo   VARCHAR(10),     -- bull / bear
  vix_at_ipo          NUMERIC(8,4),
  sector_rs_at_ipo    NUMERIC(8,4),

  -- Classifications
  year1_category      VARCHAR(20)      -- winner/moderate/loser/disaster
);

CREATE INDEX IF NOT EXISTS idx_ipo_perf_ticker ON ipo_performance(ticker);
CREATE INDEX IF NOT EXISTS idx_ipo_perf_year1  ON ipo_performance(year1_category);

INSERT INTO schema_migrations(migration_name, applied_at)
  VALUES ('0023_ipo_comprehensive.sql', NOW())
  ON CONFLICT (migration_name) DO NOTHING;
