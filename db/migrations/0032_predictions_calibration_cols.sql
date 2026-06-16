-- Migration 0032: Add adaptive confidence calibration columns to predictions.
-- Populated by confidence_calibrator.py which runs after model scoring in predict.py.

ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS raw_confidence            DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS calibrated_confidence     DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS confidence_context        TEXT,
    ADD COLUMN IF NOT EXISTS confidence_sample_size    INTEGER,
    ADD COLUMN IF NOT EXISTS confidence_adjustment_reason TEXT;

COMMENT ON COLUMN predictions.raw_confidence             IS 'Original confidence = abs(prob - 0.5) * 2 before calibration';
COMMENT ON COLUMN predictions.calibrated_confidence      IS 'Context-adjusted confidence after applying historical accuracy multiplier';
COMMENT ON COLUMN predictions.confidence_context         IS 'Serialized context bucket key used for calibration lookup';
COMMENT ON COLUMN predictions.confidence_sample_size     IS 'Historical sample size backing the calibration multiplier';
COMMENT ON COLUMN predictions.confidence_adjustment_reason IS 'Human-readable explanation of the calibration applied';
