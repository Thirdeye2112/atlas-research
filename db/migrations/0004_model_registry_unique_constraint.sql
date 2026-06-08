-- =============================================================
-- Migration 0004: Add unique constraint to model_registry
-- Required for ON CONFLICT (model_name, model_version, target,
-- training_end) DO UPDATE to work in walk-forward fold writes.
-- Safe to re-run (DROP IF EXISTS + ADD).
-- =============================================================

ALTER TABLE model_registry
    DROP CONSTRAINT IF EXISTS
        model_registry_model_name_model_version_target_training_end_key;

ALTER TABLE model_registry
    ADD CONSTRAINT
        model_registry_model_name_model_version_target_training_end_key
    UNIQUE (model_name, model_version, target, training_end);
