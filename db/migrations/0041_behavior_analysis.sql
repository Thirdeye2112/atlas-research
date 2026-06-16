-- Migration 0041: Daily behavior analysis framework
-- Named, reproducible daily-bar market behaviors: detection, backtest, interaction analysis

CREATE TABLE IF NOT EXISTS behavior_definitions (
    behavior_id     TEXT PRIMARY KEY,
    description     TEXT NOT NULL,
    category        TEXT NOT NULL,
    direction       TEXT NOT NULL,
    parameter_json  JSONB NOT NULL DEFAULT '{}',
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS detected_behaviors (
    id              BIGSERIAL PRIMARY KEY,
    ticker          TEXT NOT NULL,
    detection_date  DATE NOT NULL,
    behavior_id     TEXT NOT NULL REFERENCES behavior_definitions(behavior_id),
    intensity       DOUBLE PRECISION,
    UNIQUE (ticker, detection_date, behavior_id)
);

CREATE INDEX IF NOT EXISTS idx_db_behavior_id   ON detected_behaviors (behavior_id);
CREATE INDEX IF NOT EXISTS idx_db_ticker_date   ON detected_behaviors (ticker, detection_date DESC);

CREATE TABLE IF NOT EXISTS behavior_backtest_results (
    id              BIGSERIAL PRIMARY KEY,
    behavior_id     TEXT NOT NULL,
    as_of_date      DATE NOT NULL,
    sample_size     INTEGER NOT NULL,
    hit_rate_1d     DOUBLE PRECISION,
    hit_rate_5d     DOUBLE PRECISION,
    hit_rate_10d    DOUBLE PRECISION,
    avg_return_1d   DOUBLE PRECISION,
    avg_return_5d   DOUBLE PRECISION,
    avg_return_10d  DOUBLE PRECISION,
    expectancy_5d   DOUBLE PRECISION,
    profit_factor_5d DOUBLE PRECISION,
    best_sector     TEXT,
    worst_sector    TEXT,
    UNIQUE (behavior_id, as_of_date)
);

CREATE TABLE IF NOT EXISTS behavior_interaction_results (
    id              BIGSERIAL PRIMARY KEY,
    behavior_a      TEXT NOT NULL,
    behavior_b      TEXT NOT NULL,
    as_of_date      DATE NOT NULL,
    combined_n      INTEGER NOT NULL,
    combined_hit_rate_5d DOUBLE PRECISION,
    combined_avg_return_5d DOUBLE PRECISION,
    lift_vs_a       DOUBLE PRECISION,
    lift_vs_b       DOUBLE PRECISION,
    synergy_score   DOUBLE PRECISION,
    UNIQUE (behavior_a, behavior_b, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_bir_synergy ON behavior_interaction_results (synergy_score DESC);
