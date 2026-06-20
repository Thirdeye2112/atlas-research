"""Quick audit of securities vs raw_bars coverage."""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()
from sqlalchemy import create_engine, text
from config import settings

e = create_engine(settings.DATABASE_URL)
with e.connect() as c:
    cols = c.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='securities' ORDER BY ordinal_position"
    )).fetchall()
    print("securities columns:", [r[0] for r in cols])

    sec_ct = c.execute(text("SELECT COUNT(*) FROM securities WHERE active=true")).scalar()
    print(f"Active securities: {sec_ct}")

    fs_rows  = c.execute(text("SELECT COUNT(*) FROM feature_snapshots")).scalar()
    fs_dates = c.execute(text("SELECT COUNT(DISTINCT date) FROM feature_snapshots")).scalar()
    print(f"feature_snapshots: {fs_rows:,} rows | {fs_dates} distinct dates")

    total_missing = c.execute(text("""
        SELECT COUNT(DISTINCT rb.ticker)
        FROM raw_bars rb
        LEFT JOIN securities s ON s.ticker = rb.ticker
        WHERE s.ticker IS NULL
    """)).scalar()
    print(f"raw_bars tickers NOT in securities: {total_missing}")

    rows = c.execute(text("""
        SELECT rb.ticker,
               MIN(rb.date)::text  AS first_date,
               MAX(rb.date)::text  AS last_date,
               COUNT(*)            AS bars
        FROM raw_bars rb
        LEFT JOIN securities s ON s.ticker = rb.ticker
        WHERE s.ticker IS NULL
        GROUP BY rb.ticker
        ORDER BY bars DESC
        LIMIT 15
    """)).fetchall()
    print("\nTop missing tickers by bar count:")
    for r in rows:
        print(f"  {r.ticker:<12} {r.bars:>5} bars  ({r.first_date} – {r.last_date})")
