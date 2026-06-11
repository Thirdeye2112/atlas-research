-- 0015: OMNI-82 conditional patterns
-- EMA(Low, 82) confirmed as Oscar Carboni's OMNI indicator.
-- 81.9% 20-day hit rate on SPY cross-up signal (2011-2026).

INSERT INTO conditional_patterns (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    -- ── SP500 universe (all tickers) ──────────────────────────────────────────
    ('omni_82_cross_up',      'ema_lows_cross_up',    'SP500', '{"period": 82}',                   '{1,5,10,20}', 15),
    ('omni_82_cross_down',    'ema_lows_cross_down',  'SP500', '{"period": 82}',                   '{1,5,10,20}', 15),
    ('omni_82_above_3d',      'ema_lows_above_nd',    'SP500', '{"period": 82, "n_days": 3}',       '{1,5,10,20}', 15),
    ('omni_82_above_5d',      'ema_lows_above_nd',    'SP500', '{"period": 82, "n_days": 5}',       '{1,5,10,20}', 15),
    ('omni_82_bounce',        'ema_lows_support',     'SP500', '{"period": 82, "touch_pct": 0.005}','{1,5,10}',    10),
    ('omni_82_bounce_1pct',   'ema_lows_support',     'SP500', '{"period": 82, "touch_pct": 0.01}', '{1,5,10}',    10),
    ('omni_82_green_slope',   'ema_lows_green_slope', 'SP500', '{"period": 82, "slope_bars": 5}',   '{1,5,10,20}', 15),

    -- ── SPY single-ticker ─────────────────────────────────────────────────────
    ('spy_omni_82_cross_up',    'ema_lows_cross_up',    'SPY', '{"period": 82}',                   '{1,5,10,20}', 5),
    ('spy_omni_82_cross_down',  'ema_lows_cross_down',  'SPY', '{"period": 82}',                   '{1,5,10,20}', 5),
    ('spy_omni_82_above_3d',    'ema_lows_above_nd',    'SPY', '{"period": 82, "n_days": 3}',       '{1,5,10,20}', 5),
    ('spy_omni_82_bounce',      'ema_lows_support',     'SPY', '{"period": 82, "touch_pct": 0.005}','{1,5,10}',    3),
    ('spy_omni_82_green_slope', 'ema_lows_green_slope', 'SPY', '{"period": 82, "slope_bars": 5}',   '{1,5,10,20}', 5)

ON CONFLICT (name) DO NOTHING;
