-- Migration 0058: confidence flag + 5m-arc drop context on each alert
-- Adds the validated multi-timeframe CONFIDENT-entry flag and the 5m-arc drop
-- targets to each scan alert, so atlas-alpha can rank/filter by the highest-edge
-- setups and show the intraday bounce expectation.
--
-- Grounded in the deep-dive studies:
--   * confident: the layered Layer-4 result (reports/stocks/MTF_CONFLUENCE_REFINED.md)
--     — an oversold dip that is NOT in a daily downtrend lifts always-T3 expectancy
--     +0.253R -> +0.414R (+63%). This is the entry filter that carries the edge.
--   * arc_retrace_frac / arc_drop_pct / wall_break_rate come from the whole-universe
--     5m arc study (reports/stocks/universe_arc_targets.json): per-liquidity-tier
--     median intraday bounce retrace, drop %, and the rate at which a run breaks the
--     nearest overhead wall — the intraday "throw -> top -> bounce" context.

ALTER TABLE trade_alerts
  ADD COLUMN IF NOT EXISTS confident        BOOLEAN,             -- oversold dip & not a daily downtrend
  ADD COLUMN IF NOT EXISTS arc_retrace_frac DOUBLE PRECISION,    -- tier median 5m intraday bounce retrace
  ADD COLUMN IF NOT EXISTS arc_drop_pct     DOUBLE PRECISION,    -- tier median 5m drop off the top (%)
  ADD COLUMN IF NOT EXISTS wall_break_rate  DOUBLE PRECISION;    -- tier rate a run breaks the nearest wall

CREATE INDEX IF NOT EXISTS idx_alerts_confident ON trade_alerts (scan_date, confident, conviction DESC);
