-- migration 0028: add feature_set_version to model_registry
-- tracks which feature set (v1=current, v2=remove_degrading) was used for each training run

ALTER TABLE model_registry
  ADD COLUMN IF NOT EXISTS feature_set_version TEXT DEFAULT 'v1';

COMMENT ON COLUMN model_registry.feature_set_version IS
  'Feature set used for training: v1=all features, v2=degrading features removed';
