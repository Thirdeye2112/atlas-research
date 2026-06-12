"""Apply migrations 0020 and 0021 directly, bypassing apply_migration.py."""
from sqlalchemy import create_engine, text
import os; from dotenv import load_dotenv; from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
e = create_engine(os.environ["DATABASE_URL"])

ddl = """
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

CREATE TABLE IF NOT EXISTS oscar_scrape_log (
    id              SERIAL PRIMARY KEY,
    video_id        VARCHAR(64) NOT NULL UNIQUE,
    video_title     VARCHAR(500),
    channel         VARCHAR(100) DEFAULT 'OscarCarboni',
    published_at    TIMESTAMP WITH TIME ZONE,
    duration_secs   INTEGER,
    transcript_chars INTEGER,
    status          VARCHAR(20) DEFAULT 'pending',
    ingested_at     TIMESTAMP WITH TIME ZONE,
    error_msg       TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_oscar_scrape_status ON oscar_scrape_log(status);
CREATE INDEX IF NOT EXISTS idx_oscar_scrape_published ON oscar_scrape_log(published_at DESC);
"""

with e.connect() as c:
    for stmt in ddl.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            c.execute(text(stmt))
    c.commit()
    # Verify tables
    for tbl in ["ipo_registry", "ipo_backtest_results", "oscar_scrape_log"]:
        r = c.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
        print(f"  {tbl}: exists, {r} rows")
print("Migrations applied.")
