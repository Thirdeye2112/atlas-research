-- 0012: Expanded signals — calendar, intermarket, breadth, technical structures
-- Adds 23 new patterns across 8 new condition types.

INSERT INTO conditional_patterns (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    -- ── Technical structure ───────────────────────────────────────────────────
    ('nr7',                  'nr7',              'SP500', '{"lookback": 7}',                  '{1,5,10}',    20),
    ('breakout_52w_high',    'breakout_52w_high','SP500', '{}',                               '{1,5,10,20}', 20),
    ('volume_climax_down',   'volume_climax_down','SP500','{"multiplier": 2.0, "lookback": 20}','{1,5,10}',  20),
    ('volume_climax_up',     'volume_climax_up', 'SP500', '{"multiplier": 2.0, "lookback": 20}','{1,5,10}', 20),
    ('near_52w_high_3pct',   'near_52w_high',    'SP500', '{"within_pct": 3.0}',              '{5,10,20}',   20),
    ('near_52w_low_3pct',    'near_52w_low',     'SP500', '{"within_pct": 3.0}',              '{5,10,20}',   20),

    -- ── Gap patterns (up-side; gap_down already exists) ───────────────────────
    ('gap_up_2pct',          'gap_up',           'SP500', '{"min_gap_pct": 2.0}',             '{1,5,10}',    20),
    ('gap_up_4pct',          'gap_up',           'SP500', '{"min_gap_pct": 4.0}',             '{1,5,10}',    20),

    -- ── Wider RSI bands ───────────────────────────────────────────────────────
    ('oversold_rsi_25',      'oversold_rsi',     'SP500', '{"threshold": 25}',                '{1,5,10,20}', 20),
    ('overbought_rsi_65',    'overbought_rsi',   'SP500', '{"threshold": 65}',                '{1,5,10,20}', 20),
    ('consecutive_down_2',   'consecutive_down', 'SP500', '{"n_days": 2}',                    '{1,5,10}',    20),
    ('consecutive_up_2',     'consecutive_up',   'SP500', '{"n_days": 2}',                    '{1,5,10}',    20),

    -- ── SPY-specific patterns (ticker forward-return from SPY only) ────────────
    ('spy_down_3d',          'consecutive_down', 'SPY',   '{"n_days": 3}',                    '{1,5,10,20}', 15),
    ('spy_up_3d',            'consecutive_up',   'SPY',   '{"n_days": 3}',                    '{1,5,10,20}', 15),

    -- ── Intermarket / cross-asset ─────────────────────────────────────────────
    ('tlt_up_5d',            'consecutive_up',   'TLT',   '{"n_days": 5}',                    '{1,5,10,20}', 10),
    ('tlt_down_5d',          'consecutive_down', 'TLT',   '{"n_days": 5}',                    '{1,5,10,20}', 10),
    ('gld_up_5d',            'consecutive_up',   'GLD',   '{"n_days": 5}',                    '{1,5,10,20}', 10),
    ('spy_below_sma200',     'below_sma',        'SPY',   '{"period": 200}',                  '{5,10,20}',   10),
    ('spy_above_sma50',      'above_sma',        'SPY',   '{"period": 50}',                   '{5,10,20}',   10),
    ('vix_spike_30',         'above_level',      '^VIX',  '{"threshold": 30.0}',              '{1,5,10}',    10),

    -- ── Calendar / seasonal ───────────────────────────────────────────────────
    ('end_of_month_3d',      'end_of_month',     'SP500', '{"n_days": 3}',                    '{1,5}',       20),
    ('turn_of_month_3d',     'turn_of_month',    'SP500', '{"n_days": 3}',                    '{1,5}',       20),
    ('monday_seasonality',   'day_of_week',      'SP500', '{"weekday": 0}',                   '{1,5}',       30),
    ('friday_seasonality',   'day_of_week',      'SP500', '{"weekday": 4}',                   '{1,5}',       30)

ON CONFLICT (name) DO NOTHING;
