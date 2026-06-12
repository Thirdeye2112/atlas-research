-- Migration 0021: Oscar Carboni video scrape log

CREATE TABLE IF NOT EXISTS oscar_scrape_log (
    id              SERIAL PRIMARY KEY,
    video_id        VARCHAR(64) NOT NULL UNIQUE,
    video_title     VARCHAR(500),
    channel         VARCHAR(100) DEFAULT 'OscarCarboni',
    published_at    TIMESTAMP WITH TIME ZONE,
    duration_secs   INTEGER,
    transcript_chars INTEGER,
    status          VARCHAR(20) DEFAULT 'pending',
    ingested_at     TIMESTAMP WITH TIME ZONE,
    error_msg       TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oscar_scrape_status ON oscar_scrape_log(status);
CREATE INDEX IF NOT EXISTS idx_oscar_scrape_published ON oscar_scrape_log(published_at DESC);

INSERT INTO schema_migrations(migration_name, applied_at) VALUES ('0021_oscar_scrape_log.sql', NOW())
ON CONFLICT (migration_name) DO NOTHING;
