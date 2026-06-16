"""Rebuild all parquet files to include INFERENCE_EXTRA_COLS."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from atlas_research.exports.parquet_export import run_parquet_export

parquet_dir = _ROOT / "exports" / "parquet"
files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
print(f"Rebuilding {len(files)} parquet files...")

ok = 0; skip = 0; fail = 0
for i, f in enumerate(files):
    d = datetime.strptime(f.stem.split("_", 2)[2], "%Y-%m-%d").date()
    try:
        result = run_parquet_export(d, output_dir=parquet_dir)
        if result:
            ok += 1
        else:
            skip += 1
    except Exception as exc:
        print(f"  FAIL {d}: {exc}")
        fail += 1
    if (i + 1) % 250 == 0:
        print(f"  Progress: {i+1}/{len(files)}  ok={ok} skip={skip} fail={fail}")

print(f"\nDone. ok={ok} skip={skip} fail={fail}")
