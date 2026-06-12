from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    s = c.execute(text("""
        SELECT MIN(rank_percentile)::float, MAX(rank_percentile)::float,
               AVG(rank_percentile)::float,
               COUNT(DISTINCT ROUND(rank_percentile::numeric,4))
        FROM predictions WHERE date=(SELECT MAX(date) FROM predictions)
    """)).fetchone()
    print(f"min={s[0]:.4f} max={s[1]:.4f} avg={s[2]:.4f} distinct_rounded={s[3]}")
    top10 = c.execute(text("""
        SELECT ticker, rank_percentile::float, probability_positive::float
        FROM predictions WHERE date=(SELECT MAX(date) FROM predictions)
        ORDER BY rank_percentile DESC, ticker LIMIT 10
    """)).fetchall()
    print("\nTop 10 by rank:")
    for r in top10:
        print(f"  {r[0]:<8} rank={r[1]:.6f}  prob={r[2]:.6f}")
