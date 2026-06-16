-- Migration 0033: Feature reliability tracking table.
-- Populated nightly by scripts/compute_feature_reliability.py.
-- Tracks rolling IC across 30d / 90d / 180d windows to detect feature decay.

CREATE TABLE IF NOT EXISTS feature_reliability (
    feature_name        TEXT    NOT NULL,
    computed_date       DATE    NOT NULL,

    -- Rolling IC windows (Spearman rank correlation with label_return_5d)
    ic_30d              DOUBLE PRECISION,
    ic_90d              DOUBLE PRECISION,
    ic_180d             DOUBLE PRECISION,
    n_dates_30d         INTEGER,
    n_dates_90d         INTEGER,
    n_dates_180d        INTEGER,

    -- Regime-specific IC
    ic_bull             DOUBLE PRECISION,
    ic_bear             DOUBLE PRECISION,
    ic_high_vol         DOUBLE PRECISION,

    -- Trend classification
    ic_trend            TEXT,       -- improving | stable | declining | unreliable
    trend_delta         DOUBLE PRECISION,   -- ic_30d - ic_90d (positive = improving)

    -- Flags (set by classify_reliability())
    currently_reliable  BOOLEAN NOT NULL DEFAULT false,
    declining           BOOLEAN NOT NULL DEFAULT false,
    unreliable          BOOLEAN NOT NULL DEFAULT false,
    insufficient_data   BOOLEAN NOT NULL DEFAULT false,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (feature_name, computed_date)
);

CREATE INDEX IF NOT EXISTS idx_fr_date   ON feature_reliability(computed_date DESC);
CREATE INDEX IF NOT EXISTS idx_fr_trend  ON feature_reliability(ic_trend);
CREATE INDEX IF NOT EXISTS idx_fr_flags  ON feature_reliability(currently_reliable, declining, unreliable);

COMMENT ON TABLE feature_reliability IS
    'Rolling IC diagnostics per feature. Populated nightly. Used by check_retrain_needed.py and BotLab Learning tab.';
