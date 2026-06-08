import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()
from config import settings
from atlas_research.db.connection import get_connection
from sqlalchemy import text

print(f"Parquet dir: {settings.PARQUET_OUTPUT_DIR}")
print(f"Dir exists:  {settings.PARQUET_OUTPUT_DIR.exists()}")

with get_connection() as conn:
    n_snap   = conn.execute(text("SELECT COUNT(*) FROM feature_snapshots")).scalar()
    n_dates  = conn.execute(text("SELECT COUNT(DISTINCT date) FROM feature_snapshots")).scalar()
    min_d    = conn.execute(text("SELECT MIN(date) FROM feature_snapshots")).scalar()
    max_d    = conn.execute(text("SELECT MAX(date) FROM feature_snapshots")).scalar()
    n_labels = conn.execute(text("SELECT COUNT(*) FROM labels WHERE return_5d IS NOT NULL")).scalar()

print(f"feature_snapshots rows:  {n_snap:,}")
print(f"feature_snapshots dates: {n_dates:,}  ({min_d} -> {max_d})")
print(f"labels with return_5d:   {n_labels:,}")
