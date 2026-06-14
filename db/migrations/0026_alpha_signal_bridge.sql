-- 0026: Alpha Signal Calibration Bridge
-- Stores Atlas Alpha signal snapshots (synced from atlas_alpha DB) and
-- aggregated calibration results (score buckets, patterns, signals).
-- Source: atlas_alpha.signal_snapshots (patterns + forward returns).
-- Enriched: 1d/3d returns computed from atlas_research.raw_bars on sync.

-- ── Snapshot store ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alpha_signal_snapshots (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              TEXT        NOT NULL,
    snapshot_date       DATE        NOT NULL,

    -- Atlas Score
    atlas_score         NUMERIC(6,2),
    direction           TEXT,                       -- bullish / bearish / neutral
    bull_probability    NUMERIC(6,4),
    confidence_score    NUMERIC(6,2),

    -- Component scores (0–100)
    trend_score         NUMERIC(6,2),
    momentum_score      NUMERIC(6,2),
    volume_score        NUMERIC(6,2),
    rs_score            NUMERIC(6,2),
    regime_score        NUMERIC(6,2),
    exhaustion_score    NUMERIC(6,2),

    -- Key indicators
    rsi                 NUMERIC(6,2),
    rsi_zone            TEXT,                       -- oversold / neutral / overbought
    rvol                NUMERIC(8,4),
    atr_pct             NUMERIC(8,4),

    -- Exhaustion signals
    exhaustion_signal   TEXT,
    distribution_top    BOOLEAN,
    parabolic_rise      BOOLEAN,

    -- Structural signals
    patterns            JSONB,                      -- ["Bull Flag", "Golden Cross", ...]
    smart_gate_enter    BOOLEAN,
    pullback_class      TEXT,                       -- pullback / reversal / ambiguous

    -- Score metadata
    score_version       TEXT,

    -- Forward returns (5d/10d/20d from atlas_alpha; 1d/3d enriched from raw_bars)
    return_1d           NUMERIC(10,6),
    return_3d           NUMERIC(10,6),
    return_5d           NUMERIC(10,6),
    return_10d          NUMERIC(10,6),
    return_20d          NUMERIC(10,6),
    positive_1d         BOOLEAN GENERATED ALWAYS AS (return_1d > 0) STORED,
    positive_3d         BOOLEAN GENERATED ALWAYS AS (return_3d > 0) STORED,
    positive_5d         BOOLEAN GENERATED ALWAYS AS (return_5d > 0) STORED,
    positive_10d        BOOLEAN GENERATED ALWAYS AS (return_10d > 0) STORED,
    positive_20d        BOOLEAN GENERATED ALWAYS AS (return_20d > 0) STORED,

    synced_at           TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (ticker, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_alpha_snapshots_date
    ON alpha_signal_snapshots (snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_alpha_snapshots_score
    ON alpha_signal_snapshots (atlas_score, snapshot_date DESC)
    WHERE return_5d IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_alpha_snapshots_direction
    ON alpha_signal_snapshots (direction, snapshot_date DESC)
    WHERE return_5d IS NOT NULL;

-- ── Calibration results ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS alpha_signal_calibrations (
    id                  SERIAL PRIMARY KEY,
    calibration_date    DATE        NOT NULL,
    signal_type         TEXT        NOT NULL,       -- score_bucket | pattern | exhaustion | smart_gate | direction | component
    signal_key          TEXT        NOT NULL,       -- '80-100' | 'Bull Flag' | 'with_exhaustion' | 'true' | 'bullish' | 'trend_high'

    n_signals           INTEGER,
    n_resolved          INTEGER,                    -- subset with all returns available

    -- Hit rates
    hit_rate_1d         NUMERIC(6,4),
    hit_rate_3d         NUMERIC(6,4),
    hit_rate_5d         NUMERIC(6,4),
    hit_rate_10d        NUMERIC(6,4),
    hit_rate_20d        NUMERIC(6,4),

    -- Average returns
    avg_return_1d       NUMERIC(10,6),
    avg_return_3d       NUMERIC(10,6),
    avg_return_5d       NUMERIC(10,6),
    avg_return_10d      NUMERIC(10,6),
    avg_return_20d      NUMERIC(10,6),

    -- Distribution
    median_return_5d    NUMERIC(10,6),
    std_return_5d       NUMERIC(10,6),
    avg_drawdown_5d     NUMERIC(10,6),              -- mean of negative returns
    sharpe_5d           NUMERIC(8,4),               -- annualized

    -- Robustness
    year_breakdown      JSONB,                      -- {year: {n, hit_rate_5d, avg_return_5d}}
    min_n_per_year      INTEGER,                    -- smallest annual sample (robustness flag)
    sanity_pass         BOOLEAN,                    -- binomial p-value < 0.05 at 5d
    permutation_p_value NUMERIC(8,6),              -- permutation test p-value
    year_count          INTEGER,                    -- years with >= 3 samples

    -- Promotion
    status              TEXT        NOT NULL DEFAULT 'candidate',   -- promoted | candidate | rejected
    notes               TEXT,

    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (calibration_date, signal_type, signal_key)
);

CREATE INDEX IF NOT EXISTS idx_alpha_calibrations_type_status
    ON alpha_signal_calibrations (signal_type, status, calibration_date DESC);
