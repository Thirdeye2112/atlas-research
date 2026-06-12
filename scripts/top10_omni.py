from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / ".env")
e = create_engine(os.environ['DATABASE_URL'])
with e.connect() as c:
    rows = c.execute(text("""
        SELECT p.ticker, p.rank_percentile, p.probability_positive,
               fs_above.feature_value as omni_above,
               fs_dist.feature_value as omni_distance
        FROM predictions p
        LEFT JOIN feature_snapshots fs_above ON fs_above.ticker=p.ticker
          AND fs_above.feature_name='omni_82_above' AND fs_above.date=p.date
        LEFT JOIN feature_snapshots fs_dist ON fs_dist.ticker=p.ticker
          AND fs_dist.feature_name='omni_82_distance' AND fs_dist.date=p.date
        WHERE p.date = (SELECT MAX(date) FROM predictions)
        ORDER BY p.rank_percentile DESC, p.probability_positive DESC LIMIT 10
    """)).fetchall()
print(f"\n{'#':<4} {'Ticker':<8} {'Rank%':>8} {'P(+)':>7} {'OMNI':>7} {'Dist%':>8}")
print("-" * 46)
for i, r in enumerate(rows, 1):
    omni = "Green" if r.omni_above and float(r.omni_above) > 0.5 else "Red" if r.omni_above is not None else "-"
    dist = f"{float(r.omni_distance)*100:+.1f}%" if r.omni_distance is not None else "-"
    print(f"{i:<4} {r.ticker:<8} {float(r.rank_percentile):>8.4f} {float(r.probability_positive):>7.4f} {omni:>7} {dist:>8}")

# Also show distribution stats
stats = c.execute(text("""
    SELECT MIN(rank_percentile), MAX(rank_percentile), AVG(rank_percentile),
           COUNT(DISTINCT rank_percentile) as distinct_ranks
    FROM predictions WHERE date=(SELECT MAX(date) FROM predictions)
""")).fetchone()
print(f"\nrank_percentile distribution: min={float(stats[0]):.4f} max={float(stats[1]):.4f} avg={float(stats[2]):.4f} distinct={stats[3]}")
