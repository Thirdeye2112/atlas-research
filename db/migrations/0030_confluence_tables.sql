-- 0030: Confluence Engine schema
-- Tables for the Atlas Confluence scoring system.
-- Measures how many historically validated signals align on a ticker.

CREATE TABLE IF NOT EXISTS confluence_score_runs (
    id              BIGSERIAL PRIMARY KEY,
    run_date        DATE        NOT NULL,
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    engine_version  TEXT        NOT NULL DEFAULT 'v1',
    n_tickers       INTEGER,
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_confluence_runs_date
    ON confluence_score_runs (run_date DESC);

CREATE TABLE IF NOT EXISTS confluence_score_snapshots (
    id                          BIGSERIAL PRIMARY KEY,
    run_id                      BIGINT      REFERENCES confluence_score_runs(id),
    ticker                      TEXT        NOT NULL,
    snapshot_date               DATE        NOT NULL,
    engine_version              TEXT        NOT NULL DEFAULT 'v1',

    confluence_score            DOUBLE PRECISION,   -- 0-100, higher = stronger opportunity
    confluence_direction        TEXT,               -- bullish | bearish | neutral
    confluence_probability      DOUBLE PRECISION,   -- 0-1, ML probability_positive
    confluence_expected_return  DOUBLE PRECISION,   -- ML expected return
    confluence_risk             DOUBLE PRECISION,   -- 0-1, normalised risk level

    aligned_signal_count        INTEGER,
    conflicting_signal_count    INTEGER,
    neutral_signal_count        INTEGER,
    total_signal_count          INTEGER,

    regime                      TEXT,               -- bull | bear | range
    vol_regime                  TEXT,               -- high_vol | low_vol

    computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (ticker, snapshot_date, engine_version)
);

CREATE INDEX IF NOT EXISTS idx_css_date
    ON confluence_score_snapshots (snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_css_score
    ON confluence_score_snapshots (confluence_score DESC, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_css_direction
    ON confluence_score_snapshots (confluence_direction, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS confluence_score_components (
    id              BIGSERIAL PRIMARY KEY,
    snapshot_id     BIGINT      NOT NULL REFERENCES confluence_score_snapshots(id) ON DELETE CASCADE,
    ticker          TEXT        NOT NULL,
    snapshot_date   DATE        NOT NULL,

    component_name  TEXT        NOT NULL,   -- ml | pattern | probability | feature_ic | regime | risk
    signal          TEXT,                   -- bullish | bearish | neutral
    strength        DOUBLE PRECISION,       -- 0-1
    score           DOUBLE PRECISION,       -- 0-100 component quality contribution
    weight          DOUBLE PRECISION,       -- weight in final score
    available       BOOLEAN     NOT NULL DEFAULT true,

    details         JSONB,

    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (snapshot_id, component_name)
);

CREATE INDEX IF NOT EXISTS idx_csc_snapshot
    ON confluence_score_components (snapshot_id);
CREATE INDEX IF NOT EXISTS idx_csc_component
    ON confluence_score_components (component_name, snapshot_date DESC);

COMMENT ON TABLE confluence_score_snapshots IS
    'Per-ticker confluence scores. 0-100 measures historically validated signal alignment quality, not direction.';
COMMENT ON TABLE confluence_score_components IS
    'Per-component breakdown of each confluence score snapshot.';
