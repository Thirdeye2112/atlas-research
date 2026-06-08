import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

from atlas_research.db.connection import get_connection
from sqlalchemy import text

with get_connection() as conn:
    # Sample dates from both tables
    feat_dates = conn.execute(text(
        "SELECT DISTINCT date FROM feature_snapshots ORDER BY date DESC LIMIT 5"
    )).fetchall()
    label_dates = conn.execute(text(
        "SELECT DISTINCT date FROM labels ORDER BY date DESC LIMIT 5"
    )).fetchall()
    
    # Check overlap
    overlap = conn.execute(text("""
        SELECT COUNT(DISTINCT f.date)
        FROM feature_snapshots f
        INNER JOIN labels l ON f.date = l.date AND f.ticker = l.ticker
    """)).scalar()
    
    # Check date types
    feat_sample = conn.execute(text(
        "SELECT date, pg_typeof(date) FROM feature_snapshots LIMIT 1"
    )).fetchone()
    label_sample = conn.execute(text(
        "SELECT date, pg_typeof(date) FROM labels LIMIT 1"  
    )).fetchone()

print("feature_snapshots recent dates:", [str(r[0]) for r in feat_dates])
print("labels recent dates:            ", [str(r[0]) for r in label_dates])
print(f"Overlapping (date+ticker) rows: {overlap:,}")
print(f"feature_snapshots date type:    {feat_sample[1] if feat_sample else 'N/A'}")
print(f"labels date type:               {label_sample[1] if label_sample else 'N/A'}")
