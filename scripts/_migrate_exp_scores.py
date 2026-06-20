"""One-time migration: create experimental_score_snapshots and score_backtest_results."""
import os, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent / 'src'))
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(__import__('pathlib').Path(__file__).resolve().parent.parent / '.env')
import psycopg2

DDL = """
CREATE TABLE IF NOT EXISTS experimental_score_snapshots (
    ticker                   TEXT        NOT NULL,
    date                     DATE        NOT NULL,
    score_v1_current         DOUBLE PRECISION,
    score_v2_mean_reversion  DOUBLE PRECISION,
    score_v3_hybrid          DOUBLE PRECISION,
    score_v4_tier_adjusted   DOUBLE PRECISION,
    bucket_v1                TEXT,
    bucket_v2                TEXT,
    bucket_v3                TEXT,
    bucket_v4                TEXT,
    computed_at              TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (ticker, date)
);
CREATE INDEX IF NOT EXISTS idx_ess_date   ON experimental_score_snapshots (date);
CREATE INDEX IF NOT EXISTS idx_ess_bucket ON experimental_score_snapshots (bucket_v2);

CREATE TABLE IF NOT EXISTS score_backtest_results (
    id               SERIAL PRIMARY KEY,
    score_version    TEXT        NOT NULL,
    bucket           TEXT        NOT NULL,
    horizon_days     INTEGER     NOT NULL,
    n                INTEGER,
    hit_rate         DOUBLE PRECISION,
    avg_return       DOUBLE PRECISION,
    median_return    DOUBLE PRECISION,
    max_drawdown     DOUBLE PRECISION,
    perm_p           DOUBLE PRECISION,
    perm_pass        BOOLEAN,
    yearly_breakdown JSONB,
    computed_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE (score_version, bucket, horizon_days)
);

CREATE TABLE IF NOT EXISTS feature_pruning_results (
    id              SERIAL PRIMARY KEY,
    feature_set     TEXT        NOT NULL UNIQUE,
    n_features      INTEGER,
    mean_rank_ic    DOUBLE PRECISION,
    ic_std          DOUBLE PRECISION,
    auc             DOUBLE PRECISION,
    brier           DOUBLE PRECISION,
    decile_spread   DOUBLE PRECISION,
    runtime_s       DOUBLE PRECISION,
    top_features    JSONB,
    computed_at     TIMESTAMPTZ DEFAULT now()
);
"""

url = os.environ.get('DATABASE_URL')
conn = psycopg2.connect(url)
cur = conn.cursor()
cur.execute(DDL)
conn.commit()
print('Created: experimental_score_snapshots, score_backtest_results, feature_pruning_results')
conn.close()
