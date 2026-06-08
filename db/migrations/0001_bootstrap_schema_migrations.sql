-- =============================================================
-- Migration 0001: Bootstrap schema_migrations tracking table
-- This must be the first migration applied.
-- The apply_migration.py script creates this table itself before
-- reading from it, so this file is provided for documentation
-- and for environments where the table was created manually.
-- =============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name   TEXT        PRIMARY KEY,
    applied_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum         TEXT        NOT NULL,   -- SHA-256 of file contents
    execution_time_ms INTEGER    NOT NULL DEFAULT 0
);

COMMENT ON TABLE schema_migrations IS
    'Tracks applied database migrations. Managed by scripts/apply_migration.py.';

COMMENT ON COLUMN schema_migrations.migration_name IS
    'Filename of the migration, e.g. 0001_bootstrap_schema_migrations.sql';

COMMENT ON COLUMN schema_migrations.checksum IS
    'SHA-256 of the file contents at time of application. Used to detect drift.';
