-- Migration 0045: pattern_event_context
-- Causal-context layer: links each pattern_memory instance to the real-world
-- events (corporate actions, news) around its decision bar, with an explicit
-- LOOK-AHEAD-safe before/after split. Built by scripts/build_pattern_event_context.py.
-- New table only; pattern_memory is NOT altered.
--
-- Look-ahead rule (CRITICAL): an event is a valid "why" (relation='before') only
-- if its timestamp is <= the pattern's decision bar. Decision bar:
--   daily -> close of confirm_date (16:00 America/New_York, DST-aware)
--   5m    -> open  of confirm_date (09:30 America/New_York) — conservative,
--            because pattern_memory stores only the DATE for 5m (no intraday ts),
--            so same-session news cannot be proven to precede the bar and is
--            tagged 'same_day_unverified' (NOT 'before').
-- Predictive uses MUST filter to relation='before' (offset_days <= 0); 'after'
-- and 'same_day_unverified' are explanatory only.

CREATE TABLE IF NOT EXISTS pattern_event_context (
    id                  BIGSERIAL PRIMARY KEY,
    pattern_id          BIGINT      NOT NULL REFERENCES pattern_memory(id) ON DELETE CASCADE,
    ticker              TEXT        NOT NULL,
    timeframe           TEXT        NOT NULL,         -- 'daily' | '5m' (denormalized)
    decision_bar        TIMESTAMPTZ NOT NULL,         -- the look-ahead boundary

    event_kind          TEXT        NOT NULL,         -- 'corporate_action' | 'news'
    event_type          TEXT,                         -- ca_type (forward_splits,...) | news source
    event_ref           TEXT,                         -- CA dedup key | news_id
    event_time          TIMESTAMPTZ NOT NULL,         -- CA: ex_date@16:00 ET; news: created_at (UTC)

    offset_days         DOUBLE PRECISION,             -- signed (event_time - decision_bar) in days
    offset_trading_days INTEGER,                      -- CA only; signed NYSE-session offset; NULL for news
    relation            TEXT        NOT NULL,         -- 'before' | 'after' | 'same_day_unverified'

    headline            TEXT,                         -- news headline (NULL for CA)
    detail              JSONB,                        -- CA rates/dates or news summary/source/url
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pec_pattern   ON pattern_event_context (pattern_id);
CREATE INDEX IF NOT EXISTS idx_pec_ticker    ON pattern_event_context (ticker, timeframe);
CREATE INDEX IF NOT EXISTS idx_pec_kind_rel  ON pattern_event_context (event_kind, relation);
CREATE INDEX IF NOT EXISTS idx_pec_relation  ON pattern_event_context (relation);
