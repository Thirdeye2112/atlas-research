-- =============================================================
-- Atlas Prediction Error Attribution Schema
-- Migration: add after schema.sql
-- Run: psql $DATABASE_URL -f db/schema_attribution.sql
-- All CREATE TABLE / INDEX use IF NOT EXISTS — safe to re-run.
-- =============================================================

-- ---------------------------------------------------------
-- prediction_outcomes
-- One row per (ticker, prediction_date, horizon, engine_version).
-- Core prediction record written when a confluence score is produced.
-- Outcome columns are NULL until the horizon matures, then filled
-- by the nightly attribution pipeline.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_outcomes (
    id                      BIGSERIAL PRIMARY KEY,

    -- Prediction context (written at score time)
    ticker                  TEXT NOT NULL,
    prediction_date         DATE NOT NULL,
    horizon_days            INTEGER NOT NULL DEFAULT 5,
    predicted_direction     TEXT NOT NULL,          -- 'bullish' | 'bearish' | 'neutral'
    predicted_probability   DOUBLE PRECISION,       -- ML P(return > 0)
    expected_return         DOUBLE PRECISION,
    confluence_score        DOUBLE PRECISION,
    conviction_level        TEXT,                   -- 'LOW'|'MODERATE'|'HIGH'|'VERY_HIGH'
    conviction_score        DOUBLE PRECISION,
    aligned_count           INTEGER,
    conflicting_count       INTEGER,
    neutral_count           INTEGER,
    aligned_signals         TEXT[],                 -- component names that agreed
    conflicting_signals     TEXT[],
    neutral_signals         TEXT[],
    regime                  TEXT,
    vol_regime              TEXT,
    quality_tier            TEXT,                   -- 'VERY_HIGH'|'HIGH'|'MODERATE'|'LOW' (alias for conviction_level)
    feature_set_version     TEXT DEFAULT 'v1',
    model_version           TEXT DEFAULT 'v1',
    engine_version          TEXT DEFAULT 'v1',
    snapshot_id             BIGINT,                 -- FK to confluence_score_snapshots.id

    -- Realized outcome (filled in when horizon_days have elapsed)
    outcome_date            DATE,
    actual_return           DOUBLE PRECISION,       -- log return over horizon
    actual_direction        TEXT,                   -- 'up' | 'down' | 'flat'
    hit_or_miss             BOOLEAN,                -- predicted_direction matches actual_direction
    prediction_error        DOUBLE PRECISION,       -- (predicted_probability - actual_outcome) for Brier
    max_runup               DOUBLE PRECISION,       -- max return during horizon
    max_drawdown            DOUBLE PRECISION,       -- max drawdown during horizon
    outcome_computed_at     TIMESTAMPTZ,

    created_at              TIMESTAMPTZ DEFAULT now(),

    UNIQUE (ticker, prediction_date, horizon_days, engine_version)
);

CREATE INDEX IF NOT EXISTS idx_pred_outcomes_ticker_date
    ON prediction_outcomes(ticker, prediction_date DESC);

CREATE INDEX IF NOT EXISTS idx_pred_outcomes_date_level
    ON prediction_outcomes(prediction_date DESC, conviction_level);

CREATE INDEX IF NOT EXISTS idx_pred_outcomes_direction
    ON prediction_outcomes(predicted_direction, prediction_date DESC);

CREATE INDEX IF NOT EXISTS idx_pred_outcomes_pending
    ON prediction_outcomes(prediction_date, horizon_days)
    WHERE outcome_computed_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_pred_outcomes_regime
    ON prediction_outcomes(regime, prediction_date DESC);

-- ---------------------------------------------------------
-- prediction_error_attribution
-- One row per matured prediction, classifying WHY it succeeded or failed.
-- Written after outcome_computed_at is populated.
-- Multiple failure classes per prediction are allowed (insert multiple rows).
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_error_attribution (
    id                  BIGSERIAL PRIMARY KEY,
    outcome_id          BIGINT NOT NULL REFERENCES prediction_outcomes(id) ON DELETE CASCADE,
    ticker              TEXT NOT NULL,
    prediction_date     DATE NOT NULL,
    horizon_days        INTEGER NOT NULL,
    hit_or_miss         BOOLEAN,

    -- Primary classification
    failure_class       TEXT NOT NULL,
    -- 'correct'                   -- prediction was right
    -- 'regime_mismatch'           -- regime context contradicted prediction
    -- 'low_liquidity_failure'     -- stock had unusually low volume
    -- 'momentum_exhaustion'       -- stock was overbought/oversold at prediction
    -- 'mean_reversion_failure'    -- predicted reversal but trend continued
    -- 'conflicting_signal_ignored'-- had 2+ conflicting signals but still predicted
    -- 'weak_confluence'           -- low score / low conviction prediction
    -- 'feature_drift'             -- features out of typical range at prediction
    -- 'model_overconfidence'      -- ML prob > 0.70 but wrong
    -- 'event_gap'                 -- unexpected large price gap (news/earnings)
    -- 'unknown'                   -- does not match other classes

    confidence          DOUBLE PRECISION,           -- 0-1 confidence in this classification
    details             JSONB,                      -- evidence: field names and values
    is_primary          BOOLEAN DEFAULT true,       -- true for the strongest classification
    computed_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_attr_outcome_id
    ON prediction_error_attribution(outcome_id);

CREATE INDEX IF NOT EXISTS idx_attr_class_date
    ON prediction_error_attribution(failure_class, prediction_date DESC)
    WHERE is_primary = true;

CREATE INDEX IF NOT EXISTS idx_attr_ticker_date
    ON prediction_error_attribution(ticker, prediction_date DESC);

-- ---------------------------------------------------------
-- signal_reliability_scores
-- Rolling hit rate / IC per component, broken out by window/regime/tier.
-- Recomputed nightly (upsert pattern).
-- One row per (computed_date, component, direction, window, filters).
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_reliability_scores (
    id                      BIGSERIAL PRIMARY KEY,
    computed_date           DATE NOT NULL,
    component_name          TEXT NOT NULL,          -- 'ml'|'pattern'|'probability'|'feature_ic'|'regime'
    signal_direction        TEXT NOT NULL DEFAULT 'all', -- 'bullish'|'bearish'|'all'
    window_days             INTEGER NOT NULL,        -- 30 | 90 | 180
    regime_filter           TEXT,                   -- NULL=all regimes; else specific regime
    quality_tier_filter     TEXT,                   -- NULL=all; else 'VERY_HIGH'|'HIGH'|etc
    horizon_days            INTEGER NOT NULL DEFAULT 5,

    -- Core metrics
    n_predictions           INTEGER,
    n_hits                  INTEGER,
    hit_rate                DOUBLE PRECISION,       -- fraction hit/n
    avg_return              DOUBLE PRECISION,       -- avg actual_return for this group
    ic                      DOUBLE PRECISION,       -- Spearman rank IC (strength vs actual_return)

    -- Trend vs prior same-window period
    prior_hit_rate          DOUBLE PRECISION,
    hit_rate_delta          DOUBLE PRECISION,       -- hit_rate - prior_hit_rate
    trend                   TEXT,                   -- 'improving'|'stable'|'degrading'

    computed_at             TIMESTAMPTZ DEFAULT now(),

    UNIQUE (computed_date, component_name, signal_direction, window_days, regime_filter, quality_tier_filter, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_reliability_date_component
    ON signal_reliability_scores(computed_date DESC, component_name);

CREATE INDEX IF NOT EXISTS idx_reliability_component_window
    ON signal_reliability_scores(component_name, window_days, computed_date DESC);

-- ---------------------------------------------------------
-- adaptive_weight_recommendations
-- Human-reviewed recommendations for weight adjustments.
-- NEVER auto-promoted — require explicit status='promoted' from a human.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS adaptive_weight_recommendations (
    id                  BIGSERIAL PRIMARY KEY,
    generated_date      DATE NOT NULL,
    component_name      TEXT NOT NULL,
    recommendation      TEXT NOT NULL,
    -- 'increase_weight'     -- component is outperforming; upweight
    -- 'reduce_weight'       -- component is underperforming; downweight
    -- 'invert_signal'       -- component is anti-correlated; consider flipping
    -- 'require_confirmation'-- only use when another signal confirms
    -- 'disable_in_regime'   -- unreliable in a specific market regime
    -- 'keep_unchanged'      -- no action needed

    current_weight      DOUBLE PRECISION,           -- from ComponentResult.weight
    suggested_weight    DOUBLE PRECISION,           -- recommended new value (NULL if qualitative)
    regime_filter       TEXT,                       -- NULL=global; else regime-specific
    horizon_days        INTEGER DEFAULT 5,
    window_days         INTEGER,                    -- reliability window this is based on
    priority            TEXT DEFAULT 'normal',      -- 'urgent'|'normal'|'low'
    rationale           TEXT NOT NULL,              -- human-readable explanation
    evidence            JSONB,                      -- supporting data (hit_rate, n, etc.)

    -- Review workflow
    status              TEXT DEFAULT 'pending',     -- 'pending'|'reviewed'|'promoted'|'rejected'
    reviewed_at         TIMESTAMPTZ,
    reviewed_by         TEXT,
    promoted_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    notes               TEXT,

    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_recommendations_date_status
    ON adaptive_weight_recommendations(generated_date DESC, status);

CREATE INDEX IF NOT EXISTS idx_recommendations_component
    ON adaptive_weight_recommendations(component_name, generated_date DESC);

CREATE INDEX IF NOT EXISTS idx_recommendations_pending
    ON adaptive_weight_recommendations(status, priority)
    WHERE status = 'pending';
