import sys
from pathlib import Path
from datetime import date, timedelta
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv()

import numpy as np
from scipy import stats
from config import settings
from atlas_research.models.dataset import load_date_range, to_arrays

parquet_dir = settings.PARQUET_OUTPUT_DIR
feature_cols = settings.TRAIN_FEATURES
end   = date(2024, 12, 31)
start = date(2022, 1, 1)

print(f"Loading {start} to {end} ...")
df = load_date_range(start, end, feature_cols, "label_return_5d",
                     parquet_dir, min_quality_score=0.70)

if df.empty:
    print("No data loaded.")
    raise SystemExit

X, y, tickers, dates = to_arrays(df, feature_cols, "label_return_5d")
print(f"Rows: {len(X)}  Features: {X.shape[1]}  Label mean: {y.mean():.4f}")

ic_per_feat = []
for j in range(X.shape[1]):
    col = X[:, j]
    mask = ~np.isnan(col)
    if mask.sum() > 100:
        corr, _ = stats.spearmanr(col[mask], y[mask])
        ic_per_feat.append((feature_cols[j], corr))

ic_per_feat.sort(key=lambda x: abs(x[1]), reverse=True)
print(f"\nTop 10 features by Spearman IC vs label_return_5d:")
print(f"  {'Feature':<32} {'IC':>8}")
print("  " + "-" * 44)
for name, ic in ic_per_feat[:10]:
    flag = "  <- WATCH" if name in ("rsi_14", "macd_histogram") else ""
    flag = "  <- GOOD"  if name in ("rs_spy_60","rs_spy_120","return_20d","return_60d","realized_vol_20","realized_vol_60") else flag
    print(f"  {name:<32} {ic:>8.4f}{flag}")

rng = np.random.default_rng(42)
y_shuffled = rng.permutation(y)
shuffle_ics = []
for j in range(X.shape[1]):
    col = X[:, j]
    mask = ~np.isnan(col)
    if mask.sum() > 100:
        corr, _ = stats.spearmanr(col[mask], y_shuffled[mask])
        shuffle_ics.append(corr)

real_mean_ic    = np.mean([ic for _, ic in ic_per_feat])
shuffle_mean_ic = np.mean(shuffle_ics) if shuffle_ics else 0

print(f"\nLeakage check:")
print(f"  Real mean feature IC:     {real_mean_ic:.5f}")
print(f"  Shuffled mean feature IC: {shuffle_mean_ic:.5f}")
ratio = abs(real_mean_ic) / max(abs(shuffle_mean_ic), 1e-6)
if ratio > 3:
    print(f"  PASS {ratio:.1f}x - signal looks real")
elif ratio > 1.5:
    print(f"  MARGINAL {ratio:.1f}x - check purge gap")
else:
    print(f"  FAIL {ratio:.1f}x - POSSIBLE LEAKAGE")
