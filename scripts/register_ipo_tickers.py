"""
Register all raw_bars tickers that are missing from the securities table.
Uses ipo_registry for name/sector/exchange where available.
Run once before backfill_history.py to expand the ML training universe.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()

from sqlalchemy import text
from atlas_research.db.connection import get_raw_engine

def main() -> None:
    engine = get_raw_engine()
    with engine.begin() as c:
        missing = c.execute(text("""
            SELECT DISTINCT rb.ticker
            FROM raw_bars rb
            LEFT JOIN securities s ON s.ticker = rb.ticker
            WHERE s.ticker IS NULL
            ORDER BY rb.ticker
        """)).fetchall()

    tickers = [r[0] for r in missing]
    print(f"Found {len(tickers)} tickers in raw_bars not in securities.")

    with engine.connect() as c:
        ipo_rows = c.execute(text(
            "SELECT ticker, company_name, sector, exchange FROM ipo_registry"
        )).fetchall()
    ipo_map = {r.ticker: r for r in ipo_rows}

    inserted = 0
    with engine.begin() as c:
        for ticker in tickers:
            meta = ipo_map.get(ticker)
            name     = (meta.company_name or "").strip() or None if meta else None
            sector   = (meta.sector or "").strip()   or None if meta else None
            exchange = (meta.exchange or "").strip()  or None if meta else None
            c.execute(text("""
                INSERT INTO securities (ticker, name, sector, exchange, active)
                VALUES (:ticker, :name, :sector, :exchange, true)
                ON CONFLICT (ticker) DO UPDATE SET active = true
            """), {"ticker": ticker, "name": name, "sector": sector, "exchange": exchange})
            inserted += 1

    print(f"Registered {inserted} tickers into securities (active=true).")

    with engine.connect() as c:
        total = c.execute(text("SELECT COUNT(*) FROM securities WHERE active=true")).scalar()
    print(f"Total active securities now: {total}")


if __name__ == "__main__":
    main()
