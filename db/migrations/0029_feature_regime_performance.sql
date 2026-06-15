-- migration 0029: feature regime performance table
-- Stores per-feature IC broken down by market regime.
-- Populated by scripts/run_regime_sensitivity.py.

CREATE TABLE IF NOT EXISTS feature_regime_performance (
    id              BIGSERIAL PRIMARY KEY,
    feature_name    TEXT        NOT NULL,
    regime          TEXT        NOT NULL,   -- bull|bear|high_vol|low_vol|above_200dma|below_200dma
    n_dates         INTEGER,
    n_observations  INTEGER,
    mean_ic         DOUBLE PRECISION,
    ic_std          DOUBLE PRECISION,
    rank_ic         DOUBLE PRECISION,
    sign_stability  DOUBLE PRECISION,   -- fraction of dates with IC > 0
    fold_stability  DOUBLE PRECISION,   -- fraction of yearly buckets with mean_ic > 0
    ic_tstat        DOUBLE PRECISION,
    classification  TEXT,               -- Always Useful|Regime Sensitive|Mostly Noise|Potentially Harmful
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (feature_name, regime)
);

CREATE INDEX IF NOT EXISTS idx_frp_feature ON feature_regime_performance (feature_name);
CREATE INDEX IF NOT EXISTS idx_frp_regime  ON feature_regime_performance (regime);
CREATE INDEX IF NOT EXISTS idx_frp_class   ON feature_regime_performance (classification);

COMMENT ON TABLE feature_regime_performance IS
    'Per-feature IC statistics broken down by market regime. Source for V3 regime-aware feature design.';
