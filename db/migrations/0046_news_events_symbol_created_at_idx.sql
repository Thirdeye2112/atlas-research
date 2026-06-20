-- Migration 0046: composite index for the pattern→event-context news join.
-- The look-ahead news join (scripts/build_pattern_event_context.py) looks up, per
-- pattern instance, news for one symbol within a small created_at window. With only
-- a standalone idx_news_symbol that means scanning ALL of a symbol's news per
-- pattern (O(patterns * news_per_symbol)). A composite (symbol, created_at) index
-- turns each lookup into a bounded range scan.

CREATE INDEX IF NOT EXISTS idx_news_symbol_created_at
    ON news_events (symbol, created_at);
