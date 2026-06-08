-- =============================================================
-- Migration 003: Transcript Intelligence Pipeline (Phase 3)
-- Run once:  psql $DATABASE_URL -f db/migrations/003_transcript_intelligence.sql
-- Safe to re-run (all IF NOT EXISTS).
-- =============================================================

-- ---------------------------------------------------------
-- transcript_sources
-- One row per source document (earnings call, note, podcast…).
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcript_sources (
    id              SERIAL PRIMARY KEY,
    source_id       TEXT UNIQUE NOT NULL,   -- deterministic hash of path + mtime
    file_path       TEXT NOT NULL,
    source_type     TEXT NOT NULL DEFAULT 'transcript',  -- 'transcript' | 'note' | 'podcast'
    title           TEXT,
    speaker         TEXT,                   -- primary speaker / firm
    event_date      DATE,                   -- date the content was produced
    ticker_context  TEXT[],                 -- tickers explicitly mentioned
    word_count      INTEGER,
    chunk_count     INTEGER DEFAULT 0,
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transcript_sources_date
    ON transcript_sources(event_date DESC);

-- ---------------------------------------------------------
-- transcript_chunks
-- Semantic chunks of each source.  Extraction operates on chunks.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS transcript_chunks (
    id              SERIAL PRIMARY KEY,
    source_id       TEXT NOT NULL REFERENCES transcript_sources(source_id),
    chunk_index     INTEGER NOT NULL,       -- 0-based position within source
    chunk_text      TEXT NOT NULL,
    speaker_turn    TEXT,                   -- e.g. "ANALYST", "CEO", "HOST"
    char_start      INTEGER,
    char_end        INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE (source_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_source
    ON transcript_chunks(source_id, chunk_index);

-- ---------------------------------------------------------
-- research_hypotheses
-- One row per candidate claim extracted from transcript text.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS research_hypotheses (
    hypothesis_id       TEXT PRIMARY KEY,       -- UUID
    source_id           TEXT REFERENCES transcript_sources(source_id),
    chunk_id            INTEGER REFERENCES transcript_chunks(id),

    -- Raw extraction
    source_text         TEXT NOT NULL,          -- verbatim excerpt that generated the claim
    extracted_claim     TEXT NOT NULL,          -- LLM-cleaned natural-language claim

    -- Structured test specification
    market_object       TEXT,                   -- e.g. 'SPY', 'QQQ', 'universe'
    condition           TEXT,                   -- e.g. 'down_5_consecutive_days'
    condition_params    JSONB,                  -- {'n_days': 5, 'threshold': 0.0}
    target              TEXT,                   -- 'forward_return_1d' | 'forward_return_5d' | ...
    horizons            INTEGER[],              -- [1, 5]
    direction           TEXT,                   -- 'mean_reversion_long' | 'momentum_long' | 'short' | 'neutral'
    regime_filter       TEXT,                   -- 'bull_only' | 'bear_only' | NULL (all regimes)
    sector_filter       TEXT,                   -- NULL = all sectors

    -- Priors
    confidence_prior    REAL DEFAULT 0.5,       -- subjective prior 0-1 from claim strength
    novelty_score       REAL,                   -- 1.0 if no similar hypothesis exists

    -- Status
    test_status         TEXT NOT NULL DEFAULT 'queued',  -- 'queued'|'running'|'done'|'failed'|'skipped'
    skip_reason         TEXT,
    promoted            BOOLEAN DEFAULT false,

    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_status
    ON research_hypotheses(test_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_hypotheses_source
    ON research_hypotheses(source_id);

-- ---------------------------------------------------------
-- hypothesis_tests
-- One test run per (hypothesis, horizon, date_range).
-- A hypothesis may be re-tested as new data arrives.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS hypothesis_tests (
    id              SERIAL PRIMARY KEY,
    hypothesis_id   TEXT NOT NULL REFERENCES research_hypotheses(hypothesis_id),
    horizon_days    INTEGER NOT NULL,
    test_start      DATE NOT NULL,
    test_end        DATE NOT NULL,
    run_at          TIMESTAMPTZ DEFAULT now(),
    status          TEXT NOT NULL DEFAULT 'running',  -- 'running'|'done'|'failed'
    error_msg       TEXT,

    UNIQUE (hypothesis_id, horizon_days, test_start, test_end)
);

CREATE INDEX IF NOT EXISTS idx_htests_hypothesis
    ON hypothesis_tests(hypothesis_id, horizon_days);

-- ---------------------------------------------------------
-- hypothesis_results
-- Statistical results for each test run.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS hypothesis_results (
    id              SERIAL PRIMARY KEY,
    test_id         INTEGER NOT NULL REFERENCES hypothesis_tests(id),
    hypothesis_id   TEXT NOT NULL REFERENCES research_hypotheses(hypothesis_id),
    horizon_days    INTEGER NOT NULL,

    -- Sample statistics
    sample_size     INTEGER,                -- number of qualifying events
    event_dates     DATE[],                 -- when the condition fired
    tickers         TEXT[],                 -- which tickers were involved (if cross-sectional)

    -- Return metrics
    hit_rate        DOUBLE PRECISION,       -- fraction of events where direction was correct
    avg_return      DOUBLE PRECISION,       -- mean forward return on event dates
    median_return   DOUBLE PRECISION,
    std_return      DOUBLE PRECISION,
    sharpe          DOUBLE PRECISION,       -- avg_return / std_return * sqrt(252 / horizon)
    max_drawdown    DOUBLE PRECISION,

    -- Statistical significance
    t_stat          DOUBLE PRECISION,       -- t-test of avg_return vs 0
    p_value         DOUBLE PRECISION,
    rank_ic         DOUBLE PRECISION,       -- Spearman IC when cross-sectional

    -- Regime breakdown (JSONB for flexibility)
    regime_breakdown JSONB,                 -- {'bull': {hit_rate, avg_ret, n}, 'bear': {...}}

    -- Composite score for ranking
    composite_score DOUBLE PRECISION,       -- weighted combination of IC, hit_rate, sample_size

    created_at      TIMESTAMPTZ DEFAULT now(),

    UNIQUE (test_id)
);

CREATE INDEX IF NOT EXISTS idx_hresults_hypothesis
    ON hypothesis_results(hypothesis_id, horizon_days);

CREATE INDEX IF NOT EXISTS idx_hresults_score
    ON hypothesis_results(composite_score DESC NULLS LAST);

-- ---------------------------------------------------------
-- promoted_features
-- Hypotheses that passed statistical validation get promoted
-- to the feature research pipeline.
-- Distinct from model_registry: these are candidate features,
-- not trained models.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS promoted_features (
    id                  SERIAL PRIMARY KEY,
    hypothesis_id       TEXT NOT NULL REFERENCES research_hypotheses(hypothesis_id),
    feature_name        TEXT UNIQUE NOT NULL,   -- snake_case name for the new feature
    feature_description TEXT,
    feature_category    TEXT,                   -- 'event' | 'condition' | 'regime' | 'derived'
    implementation_spec JSONB,                  -- full spec needed to implement the feature

    -- Validation summary
    best_horizon_days   INTEGER,
    best_hit_rate       DOUBLE PRECISION,
    best_rank_ic        DOUBLE PRECISION,
    best_sharpe         DOUBLE PRECISION,
    sample_size         INTEGER,
    p_value             DOUBLE PRECISION,

    -- Lifecycle
    promotion_status    TEXT NOT NULL DEFAULT 'candidate',
    -- 'candidate' → 'in_development' → 'live' → 'deprecated'
    promoted_at         TIMESTAMPTZ DEFAULT now(),
    live_at             TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,
    notes               TEXT,

    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_promoted_status
    ON promoted_features(promotion_status, promoted_at DESC);

CREATE INDEX IF NOT EXISTS idx_promoted_hypothesis
    ON promoted_features(hypothesis_id);
