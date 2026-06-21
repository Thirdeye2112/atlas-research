-- 0050: pattern_reference — ground-truth taught-behavior for every TA tool/pattern
-- the system detects. This is TEXTBOOK EXPECTATION, not validated behavior.
-- Never alter pattern_memory rows; this is a standalone reference table.

CREATE TABLE IF NOT EXISTS pattern_reference (
    pattern_type       TEXT PRIMARY KEY,
    category           TEXT NOT NULL
                           CHECK (category IN ('continuation','reversal','bilateral','context')),
    expected_direction TEXT NOT NULL
                           CHECK (expected_direction IN ('up','down','trend_continuation','bidirectional','n/a')),
    description        TEXT NOT NULL,
    taught_expectation TEXT NOT NULL,
    confirmation_condition   TEXT NOT NULL,
    invalidation_condition   TEXT NOT NULL,
    invalidation_becomes     TEXT,       -- NULL when invalidation has no clean flip signal
    source_note              TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE pattern_reference IS
    'Ground-truth taught behavior per pattern/TA-tool. '
    'WHAT the textbooks teach, NOT whether it holds empirically. '
    'Do not alter pattern_memory rows; use this table as the reference layer.';
