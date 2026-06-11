-- ─────────────────────────────────────────────────────────────────────────────
-- 0018  calendar_conditional_patterns
--
-- Calendar-aware conditional patterns that cross-reference market_calendar.
-- Evaluators implemented in engine.py: fomc_proximity, opex_week,
-- triple_witching_week. month_end_3d reuses the existing end_of_month
-- evaluator. Backtested on SP500 universe (aggregate) and SPY (single).
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO conditional_patterns
    (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    -- FOMC day (exact match)
    ('fomc_day',          'fomc_proximity',       'SP500', '{"proximity_days": 0}', ARRAY[1,5,10,20], 20),
    ('fomc_proximity_3d', 'fomc_proximity',       'SP500', '{"proximity_days": 3}', ARRAY[1,5,10,20], 30),
    ('spy_fomc_day',      'fomc_proximity',       'SPY',   '{"proximity_days": 0}', ARRAY[1,5,10,20], 20),
    ('opex_week',         'opex_week',            'SP500', '{}',                    ARRAY[1,5,10,20], 30),
    ('spy_opex_week',     'opex_week',            'SPY',   '{}',                    ARRAY[1,5,10,20], 20),
    ('month_end_3d',      'end_of_month',         'SP500', '{"n_days": 3}',         ARRAY[1,5,10,20], 30),
    ('triple_witching_week',     'triple_witching_week', 'SP500', '{}',             ARRAY[1,5,10,20], 20),
    ('spy_triple_witching_week', 'triple_witching_week', 'SPY',   '{}',             ARRAY[1,5,10,20], 10)

ON CONFLICT (name) DO NOTHING;
