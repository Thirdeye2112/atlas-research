-- 0036_predictions_meta_columns.sql
-- Atlas Meta-Signal Engine v1
-- Adds combo_key and meta-score columns to the predictions table.
-- These are nullable and filled in by the nightly meta-tagging step.

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS combo_key            TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS meta_score           DOUBLE PRECISION;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS combo_status         TEXT;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS combo_pf_60d         DOUBLE PRECISION;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS combo_expectancy_60d DOUBLE PRECISION;
ALTER TABLE predictions ADD COLUMN IF NOT EXISTS combo_sample_size    INTEGER;

CREATE INDEX IF NOT EXISTS idx_predictions_combo_key    ON predictions(combo_key);
CREATE INDEX IF NOT EXISTS idx_predictions_meta_score   ON predictions(meta_score DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_combo_status ON predictions(combo_status);
