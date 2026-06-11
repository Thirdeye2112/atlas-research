-- 0014: OMNI EMA-of-lows variants and HMA patterns
-- Key hypothesis: OMNI tracks candle lows, not closes.

INSERT INTO conditional_patterns (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    -- ── EMA of lows — cross signals (SP500 universe) ──────────────────────────
    ('omni_ema_lows_55_cross_up',   'ema_lows_cross_up',   'SP500', '{"period": 55}', '{1,5,10,20}', 15),
    ('omni_ema_lows_82_cross_up',   'ema_lows_cross_up',   'SP500', '{"period": 82}', '{1,5,10,20}', 15),
    ('omni_ema_lows_87_cross_up',   'ema_lows_cross_up',   'SP500', '{"period": 87}', '{1,5,10,20}', 15),
    ('omni_ema_lows_89_cross_up',   'ema_lows_cross_up',   'SP500', '{"period": 89}', '{1,5,10,20}', 15),
    ('omni_ema_lows_55_cross_down', 'ema_lows_cross_down', 'SP500', '{"period": 55}', '{1,5,10,20}', 15),
    ('omni_ema_lows_87_cross_down', 'ema_lows_cross_down', 'SP500', '{"period": 87}', '{1,5,10,20}', 15),

    -- ── EMA of lows — support bounce (SP500) ──────────────────────────────────
    ('omni_ema_lows_87_support',    'ema_lows_support',    'SP500', '{"period": 87, "touch_pct": 0.005}', '{1,5,10}', 10),
    ('omni_ema_lows_87_support_1pct','ema_lows_support',   'SP500', '{"period": 87, "touch_pct": 0.01}',  '{1,5,10}', 10),

    -- ── Hull MA — cross signals (SP500) ───────────────────────────────────────
    ('omni_hma_82_cross_up',        'hma_cross_up',        'SP500', '{"period": 82}', '{1,5,10,20}', 15),
    ('omni_hma_87_cross_up',        'hma_cross_up',        'SP500', '{"period": 87}', '{1,5,10,20}', 15),
    ('omni_hma_87_cross_down',      'hma_cross_down',      'SP500', '{"period": 87}', '{1,5,10,20}', 15),

    -- ── SPY-specific (single-ticker) ──────────────────────────────────────────
    ('spy_ema_lows_55_cross_up',    'ema_lows_cross_up',   'SPY',   '{"period": 55}', '{1,5,10,20}', 5),
    ('spy_ema_lows_82_cross_up',    'ema_lows_cross_up',   'SPY',   '{"period": 82}', '{1,5,10,20}', 5),
    ('spy_ema_lows_87_cross_up',    'ema_lows_cross_up',   'SPY',   '{"period": 87}', '{1,5,10,20}', 5),
    ('spy_ema_lows_89_cross_up',    'ema_lows_cross_up',   'SPY',   '{"period": 89}', '{1,5,10,20}', 5),
    ('spy_ema_lows_87_cross_down',  'ema_lows_cross_down', 'SPY',   '{"period": 87}', '{1,5,10,20}', 5),
    ('spy_ema_lows_87_support',     'ema_lows_support',    'SPY',   '{"period": 87, "touch_pct": 0.005}', '{1,5,10}', 3),
    ('spy_hma_87_cross_up',         'hma_cross_up',        'SPY',   '{"period": 87}', '{1,5,10,20}', 5),
    ('spy_hma_82_cross_up',         'hma_cross_up',        'SPY',   '{"period": 82}', '{1,5,10,20}', 5)

ON CONFLICT (name) DO NOTHING;
