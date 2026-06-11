-- 0010: Conditional Probability Engine
-- Tables for conditional backtesting patterns and their results.

CREATE TABLE IF NOT EXISTS conditional_patterns (
    id               SERIAL PRIMARY KEY,
    name             TEXT NOT NULL UNIQUE,
    condition_type   TEXT NOT NULL,
    universe         TEXT NOT NULL DEFAULT 'SP500',
    condition_params JSONB NOT NULL DEFAULT '{}',
    horizons         INTEGER[] NOT NULL DEFAULT '{1,5,10,20}',
    min_sample_size  INTEGER NOT NULL DEFAULT 30,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conditional_patterns_type
    ON conditional_patterns(condition_type);

CREATE TABLE IF NOT EXISTS conditional_pattern_results (
    id            BIGSERIAL PRIMARY KEY,
    pattern_id    INTEGER NOT NULL REFERENCES conditional_patterns(id) ON DELETE CASCADE,
    ticker        TEXT,
    horizon_days  INTEGER NOT NULL,
    sample_size   INTEGER,
    hit_rate      DOUBLE PRECISION,
    avg_return    DOUBLE PRECISION,
    median_return DOUBLE PRECISION,
    std_return    DOUBLE PRECISION,
    sharpe        DOUBLE PRECISION,
    p_value       DOUBLE PRECISION,
    evaluated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (pattern_id, ticker, horizon_days)
);

CREATE INDEX IF NOT EXISTS idx_cpr_pattern_horizon
    ON conditional_pattern_results(pattern_id, horizon_days);

CREATE INDEX IF NOT EXISTS idx_cpr_ticker
    ON conditional_pattern_results(ticker, horizon_days);

INSERT INTO conditional_patterns (name, condition_type, universe, condition_params, horizons)
VALUES
    ('consecutive_down_3', 'consecutive_down', 'SP500', '{"n_days": 3}', '{1,5,10,20}'),
    ('consecutive_down_5', 'consecutive_down', 'SP500', '{"n_days": 5}', '{1,5,10,20}'),
    ('consecutive_up_3',   'consecutive_up',   'SP500', '{"n_days": 3}', '{1,5,10,20}'),
    ('consecutive_up_5',   'consecutive_up',   'SP500', '{"n_days": 5}', '{1,5,10,20}'),
    ('oversold_rsi_30',    'oversold_rsi',     'SP500', '{"threshold": 30}', '{1,5,10,20}'),
    ('oversold_rsi_35',    'oversold_rsi',     'SP500', '{"threshold": 35}', '{1,5,10,20}'),
    ('overbought_rsi_70',  'overbought_rsi',   'SP500', '{"threshold": 70}', '{1,5,10,20}'),
    ('gap_down_2pct',      'gap_down',         'SP500', '{"min_gap_pct": 2.0}', '{1,5,10}'),
    ('gap_down_4pct',      'gap_down',         'SP500', '{"min_gap_pct": 4.0}', '{1,5,10}'),
    ('near_52w_low_5pct',  'near_52w_low',     'SP500', '{"within_pct": 5.0}', '{5,10,20}'),
    ('near_52w_high_5pct', 'near_52w_high',    'SP500', '{"within_pct": 5.0}', '{5,10,20}'),
    ('high_volume_2x',     'high_volume',      'SP500', '{"multiplier": 2.0, "lookback": 20}', '{1,5,10}')
ON CONFLICT (name) DO NOTHING;