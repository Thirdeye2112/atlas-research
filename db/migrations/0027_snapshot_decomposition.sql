-- migration 0027: extend alpha_signal_snapshots with score decomposition columns
-- mirrors the new columns added to atlas_alpha.signal_snapshots

ALTER TABLE alpha_signal_snapshots
  ADD COLUMN IF NOT EXISTS options_score     INTEGER,
  ADD COLUMN IF NOT EXISTS adx               DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS adx_trending      BOOLEAN,
  ADD COLUMN IF NOT EXISTS alignment_score   INTEGER,
  ADD COLUMN IF NOT EXISTS macd_histogram    DOUBLE PRECISION,
  ADD COLUMN IF NOT EXISTS rsi_divergence    VARCHAR(20),
  ADD COLUMN IF NOT EXISTS golden_cross      BOOLEAN,
  ADD COLUMN IF NOT EXISTS death_cross       BOOLEAN,
  ADD COLUMN IF NOT EXISTS vol_squeeze       BOOLEAN;

-- Derived columns for convenience (computed from stored component scores)
-- bull_flags: count of component scores strongly bullish (trend/momentum/volume/rs > 60, regime > 60, exhaustion > 70)
-- bear_flags: count of component scores strongly bearish (trend/momentum/volume/rs < 40, regime < 40, exhaustion < 30)
-- These are stored as generated columns so calibration can query them directly.

ALTER TABLE alpha_signal_snapshots
  ADD COLUMN IF NOT EXISTS bull_flags SMALLINT
    GENERATED ALWAYS AS (
      CASE WHEN trend_score    > 60 THEN 1 ELSE 0 END +
      CASE WHEN momentum_score > 60 THEN 1 ELSE 0 END +
      CASE WHEN volume_score   > 60 THEN 1 ELSE 0 END +
      CASE WHEN rs_score       > 60 THEN 1 ELSE 0 END +
      CASE WHEN regime_score   > 60 THEN 1 ELSE 0 END +
      CASE WHEN exhaustion_score > 70 THEN 1 ELSE 0 END
    ) STORED,
  ADD COLUMN IF NOT EXISTS bear_flags SMALLINT
    GENERATED ALWAYS AS (
      CASE WHEN trend_score    < 40 THEN 1 ELSE 0 END +
      CASE WHEN momentum_score < 40 THEN 1 ELSE 0 END +
      CASE WHEN volume_score   < 40 THEN 1 ELSE 0 END +
      CASE WHEN rs_score       < 40 THEN 1 ELSE 0 END +
      CASE WHEN regime_score   < 40 THEN 1 ELSE 0 END +
      CASE WHEN exhaustion_score < 30 THEN 1 ELSE 0 END
    ) STORED;
