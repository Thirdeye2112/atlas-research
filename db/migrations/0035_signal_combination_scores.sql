-- 0035_signal_combination_scores.sql
-- Atlas Meta-Signal Engine v1
-- Stores rolling performance scores for every signal combination context.
-- Primary key: (combo_key, scored_date) — one row per combo per nightly run.

CREATE TABLE IF NOT EXISTS signal_combination_scores (
    combo_key             TEXT          NOT NULL,
    scored_date           DATE          NOT NULL,

    -- Combination dimensions (denormalized for query convenience)
    conviction_level      TEXT,
    sector_regime         TEXT,
    vix_regime            TEXT,
    quality_tier          INTEGER,
    ml_rank_bucket        TEXT,
    confluence_bucket     TEXT,
    jarvis_state          TEXT,

    -- 30-day rolling window
    n_30d                 INTEGER,
    pf_30d                DOUBLE PRECISION,
    expectancy_30d        DOUBLE PRECISION,
    win_rate_30d          DOUBLE PRECISION,
    avg_winner_30d        DOUBLE PRECISION,
    avg_loser_30d         DOUBLE PRECISION,

    -- 60-day rolling window (primary scoring window)
    n_60d                 INTEGER,
    pf_60d                DOUBLE PRECISION,
    expectancy_60d        DOUBLE PRECISION,
    win_rate_60d          DOUBLE PRECISION,
    avg_winner_60d        DOUBLE PRECISION,
    avg_loser_60d         DOUBLE PRECISION,

    -- 90-day rolling window
    n_90d                 INTEGER,
    pf_90d                DOUBLE PRECISION,
    expectancy_90d        DOUBLE PRECISION,
    win_rate_90d          DOUBLE PRECISION,
    avg_winner_90d        DOUBLE PRECISION,
    avg_loser_90d         DOUBLE PRECISION,

    -- Meta score and status
    meta_score            DOUBLE PRECISION,   -- normalized 0-100
    status                TEXT,               -- PROMOTED | CANDIDATE | REJECTED | INSUFFICIENT

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (combo_key, scored_date)
);

CREATE INDEX IF NOT EXISTS idx_scs_scored_date  ON signal_combination_scores(scored_date);
CREATE INDEX IF NOT EXISTS idx_scs_status       ON signal_combination_scores(status);
CREATE INDEX IF NOT EXISTS idx_scs_meta_score   ON signal_combination_scores(meta_score DESC);
CREATE INDEX IF NOT EXISTS idx_scs_pf_60d       ON signal_combination_scores(pf_60d DESC);
