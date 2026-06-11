ALTER TABLE labels
    ADD COLUMN IF NOT EXISTS return_1d          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS return_5d          DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS return_10d         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS return_20d         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS return_60d         DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS max_runup_20d      DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS max_drawdown_20d   DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS positive_5d        BOOLEAN,
    ADD COLUMN IF NOT EXISTS positive_20d       BOOLEAN;

DO $$ BEGIN
    UPDATE labels SET
        return_5d    = label_return_5d,
        return_20d   = label_return_20d,
        positive_5d  = label_positive_5d,
        positive_20d = label_positive_20d
    WHERE return_5d IS NULL AND label_return_5d IS NOT NULL;
EXCEPTION WHEN undefined_column THEN NULL;
END $$;