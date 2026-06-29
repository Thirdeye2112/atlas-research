-- Migration 0057: operationalize daily_scan alerts with forecast targets
-- Adds the predicted first-leg target, add-the-dip level, pullback timing, and the
-- liquidity tier to each alert, so atlas-alpha can surface an actionable plan
-- (entry -> target -> where to add on the first pullback), not just a setup.
--
-- Grounded in the deep-dive studies:
--   * liq_tier / exp_firstleg_pct / exp_wholerun_pct / exp_firstleg_bars come from
--     the whole-universe forecast study (reports/stocks/universe_forecast_targets.json):
--     per-liquidity-tier median first-leg & whole-run height and typical duration.
--   * retrace_frac / add_dip_price come from the first-pullback study
--     (reports/stocks/SWING_PULLBACK_STUDY.md): the first pullback retraces a fraction
--     of the first run (median ~0.70; bigger runs less, ~0.49; smaller runs more, ~0.87).
--   * base_n/base_avg_fwd5/base_win5 are now the TIER-SPECIFIC base rate where available
--     (falling back to the pooled rate), recorded in base_scope.

ALTER TABLE trade_alerts
  ADD COLUMN IF NOT EXISTS liq_tier          TEXT,                -- T1 (most liquid) .. T4
  ADD COLUMN IF NOT EXISTS entry_px          DOUBLE PRECISION,    -- decision-bar close
  ADD COLUMN IF NOT EXISTS exp_firstleg_pct  DOUBLE PRECISION,    -- predicted first-leg run %
  ADD COLUMN IF NOT EXISTS target_px         DOUBLE PRECISION,    -- entry_px * (1 + exp_firstleg_pct/100)
  ADD COLUMN IF NOT EXISTS exp_firstleg_bars INTEGER,             -- typical bars to first-leg peak
  ADD COLUMN IF NOT EXISTS retrace_frac      DOUBLE PRECISION,    -- expected first-pullback retrace of the run
  ADD COLUMN IF NOT EXISTS add_dip_px        DOUBLE PRECISION,    -- target_px - retrace_frac*(target_px-entry_px)
  ADD COLUMN IF NOT EXISTS exp_wholerun_pct  DOUBLE PRECISION,    -- predicted whole-run % (context)
  ADD COLUMN IF NOT EXISTS base_scope        TEXT;                -- 'tier' | 'pooled' (which base rate was used)
