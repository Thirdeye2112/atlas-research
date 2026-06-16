-- 0038_intraday_candidate_setups.sql
-- Atlas Intraday Candidate Watchlist
-- Daily snapshot of walk-forward metrics per setup type.
-- Status: collecting -> candidate -> promoted | rejected

CREATE TABLE IF NOT EXISTS intraday_candidate_setups (
    id                   BIGSERIAL        PRIMARY KEY,
    setup_type           TEXT             NOT NULL,
    direction            TEXT             NOT NULL,
    timeframe            TEXT             NOT NULL DEFAULT '5m',
    as_of_date           DATE             NOT NULL,
    -- In-sample metrics
    sample_size          INTEGER,
    win_rate             DOUBLE PRECISION,
    expectancy           DOUBLE PRECISION,
    profit_factor        DOUBLE PRECISION,
    max_drawdown         DOUBLE PRECISION,
    -- Out-of-sample metrics
    oos_sample_size      INTEGER,
    oos_win_rate         DOUBLE PRECISION,
    oos_expectancy       DOUBLE PRECISION,
    oos_profit_factor    DOUBLE PRECISION,
    -- Context breakdown (best daily context slice)
    best_context_label   TEXT,
    best_context_exp     DOUBLE PRECISION,
    -- Tracking
    last_seen            DATE,
    days_collected       INTEGER,
    status               TEXT             DEFAULT 'collecting',
    notes                TEXT,
    UNIQUE (setup_type, direction, timeframe, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_ics_status     ON intraday_candidate_setups (status);
CREATE INDEX IF NOT EXISTS idx_ics_as_of      ON intraday_candidate_setups (as_of_date DESC);
CREATE INDEX IF NOT EXISTS idx_ics_setup_type ON intraday_candidate_setups (setup_type, direction);
