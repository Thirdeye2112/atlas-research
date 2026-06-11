-- 0013: OMNI proxy (87-period EMA) and OSCAR oscillator conditional patterns
-- Tests Oscar Carboni's OMNI indicator hypothesis: OMNI ≈ 87-period EMA or OSCAR(87)

INSERT INTO conditional_patterns (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    -- ── OMNI proxy (87-period EMA) — SP500 universe ───────────────────────────
    ('omni_87_cross_up',    'omni_cross_up',  'SP500', '{"period": 87}',              '{1,5,10,20}', 15),
    ('omni_87_cross_down',  'omni_cross_down','SP500', '{"period": 87}',              '{1,5,10,20}', 15),
    ('omni_87_green_3d',    'omni_green_nd',  'SP500', '{"period": 87, "n_days": 3}', '{5,10,20}',   20),
    ('omni_87_red_3d',      'omni_red_nd',    'SP500', '{"period": 87, "n_days": 3}', '{5,10,20}',   20),

    -- ── OSCAR oscillator — SP500 universe ────────────────────────────────────
    ('oscar_87_cross_up',   'oscar_cross_up', 'SP500', '{"period": 87}',              '{1,5,10,20}', 15),
    ('oscar_87_cross_down', 'oscar_cross_down','SP500','{"period": 87}',              '{1,5,10,20}', 15),
    ('oscar_87_green',      'oscar_above_50', 'SP500', '{"period": 87}',              '{5,10,20}',   20),
    ('oscar_55_cross_up',   'oscar_cross_up', 'SP500', '{"period": 55}',              '{1,5,10,20}', 15),
    ('oscar_89_cross_up',   'oscar_cross_up', 'SP500', '{"period": 89}',              '{1,5,10,20}', 15),
    ('oscar_34_cross_up',   'oscar_cross_up', 'SP500', '{"period": 34}',              '{1,5,10}',    15),
    ('oscar_144_cross_up',  'oscar_cross_up', 'SP500', '{"period": 144}',             '{5,10,20}',   10),

    -- ── SPY-specific OMNI/OSCAR (single-ticker forward returns) ──────────────
    ('spy_omni_87_cross_up',  'omni_cross_up',  'SPY', '{"period": 87}',              '{1,5,10,20}', 5),
    ('spy_omni_87_cross_down','omni_cross_down', 'SPY', '{"period": 87}',              '{1,5,10,20}', 5),
    ('spy_oscar_87_cross_up', 'oscar_cross_up',  'SPY', '{"period": 87}',              '{1,5,10,20}', 5),
    ('spy_oscar_55_cross_up', 'oscar_cross_up',  'SPY', '{"period": 55}',              '{1,5,10,20}', 5),
    ('spy_oscar_89_cross_up', 'oscar_cross_up',  'SPY', '{"period": 89}',              '{1,5,10,20}', 5)

ON CONFLICT (name) DO NOTHING;
