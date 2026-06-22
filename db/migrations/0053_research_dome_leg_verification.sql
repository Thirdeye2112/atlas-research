-- Migration 0053: Adversarial Verification of the Dome/Leg Early-Signature Result
-- Read-only against all existing tables; writes only here. See
-- reports/research/DOME_LEG_VERIFICATION.md for the full writeup.
-- Long-format: one row per (check_name, scope, leg_dir, metric_name).

CREATE TABLE IF NOT EXISTS research_dome_leg_verification (
    id              BIGSERIAL PRIMARY KEY,

    run_id          TEXT NOT NULL,
    check_name      TEXT NOT NULL,     -- 'check1_tautology' | 'check2_lookahead' | 'check3_permutation' | 'check4_recompute' | 'check5_fresh'
    scope           TEXT NOT NULL,     -- 'original_3' | 'fresh_5' | '10stock' | etc.
    leg_dir         TEXT,              -- 'up' | 'down' | NULL for scope-level metrics
    metric_name     TEXT NOT NULL,
    metric_value    DOUBLE PRECISION,
    n               INTEGER,
    p_value         DOUBLE PRECISION,
    notes           TEXT,

    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rdlv_check_scope
    ON research_dome_leg_verification (check_name, scope, leg_dir);
CREATE INDEX IF NOT EXISTS idx_rdlv_run_id
    ON research_dome_leg_verification (run_id);
