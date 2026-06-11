-- ─────────────────────────────────────────────────────────────────────────────
-- 0019  sector_rotation_patterns
--
-- Sector-rotation conditional patterns using sector_relative_strength table.
-- Evaluators: sector_leading_nd, xly_vs_xlp, iwm_vs_spy.
-- All applied to SPY as the forward-return vehicle (regime → market return).
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO conditional_patterns
    (name, condition_type, universe, condition_params, horizons, min_sample_size)
VALUES
    ('xlv_leading_20d', 'sector_leading_nd', 'SPY',
     '{"sector_ticker": "XLV", "rank_threshold": 2, "n_days": 20}', ARRAY[5,10,20], 20),
    ('xle_leading_20d', 'sector_leading_nd', 'SPY',
     '{"sector_ticker": "XLE", "rank_threshold": 2, "n_days": 20}', ARRAY[5,10,20], 20),
    ('xlk_leading_20d', 'sector_leading_nd', 'SPY',
     '{"sector_ticker": "XLK", "rank_threshold": 2, "n_days": 20}', ARRAY[5,10,20], 20),
    ('xlf_leading_20d', 'sector_leading_nd', 'SPY',
     '{"sector_ticker": "XLF", "rank_threshold": 2, "n_days": 20}', ARRAY[5,10,20], 20),
    ('xly_vs_xlp',      'xly_vs_xlp',       'SPY', '{}',              ARRAY[5,10,20], 30),
    ('iwm_vs_spy_10d',  'iwm_vs_spy',        'SPY',
     '{"outperform_pct": 2.0, "n_days": 10}',                         ARRAY[5,10,20], 30)

ON CONFLICT (name) DO NOTHING;
