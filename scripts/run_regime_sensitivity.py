"""
run_regime_sensitivity.py — Feature regime sensitivity study.

For each feature in TRAIN_FEATURES_V1, computes mean IC, rank IC, sign stability,
and fold stability broken down by six market regimes:

    bull_market      market_trend == 1
    bear_market      market_trend == -1
    high_vol         cross-sectional mean realized_vol_20 in top tertile per date
    low_vol          cross-sectional mean realized_vol_20 in bottom tertile per date
    above_200dma     spy_above_sma200 == 1
    below_200dma     spy_above_sma200 == 0

Regime flags are derived from the parquet data itself (no extra DB calls).

Classifications
---------------
    Always Useful      mean_ic > 0.01 AND sign_stability > 0.55 in ALL regimes
    Regime Sensitive   mean_ic > 0.01 OR sign_stability > 0.55 in SOME regimes
    Mostly Noise       |mean_ic| < 0.005 in ALL regimes
    Potentially Harmful mean_ic < -0.005 in MAJORITY of regimes

Results written to feature_regime_performance table.

Usage
-----
    python scripts/run_regime_sensitivity.py
    python scripts/run_regime_sensitivity.py --no-db
    python scripts/run_regime_sensitivity.py --parquet-dir exports/parquet
    python scripts/run_regime_sensitivity.py --min-obs 50
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from scipy import stats as scipy_stats

from config.settings import TRAIN_FEATURES_V1
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_regime_sensitivity")

TARGET_COL   = "label_return_5d"
REGIMES      = ["bull_market", "bear_market", "high_vol", "low_vol",
                "above_200dma", "below_200dma"]

# Classification thresholds
IC_USEFUL     = 0.010   # mean IC threshold for "useful"
IC_HARMFUL    = -0.005  # mean IC threshold for "harmful"
STAB_USEFUL   = 0.55    # sign_stability threshold for "useful"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_parquet(parquet_dir: Path, feature_cols: list[str]) -> pd.DataFrame:
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    needed = {"ticker", "date", TARGET_COL,
              "market_trend", "spy_above_sma200", "realized_vol_20"} | set(feature_cols)
    frames = []
    for f in files:
        try:
            df = pd.read_parquet(f, engine="pyarrow")
            avail = [c for c in needed if c in df.columns]
            frames.append(df[avail])
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out = out[out[TARGET_COL].notna()].copy()
    return out.sort_values("date").reset_index(drop=True)


# ── Regime flag assignment ────────────────────────────────────────────────────

def assign_regimes(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean regime columns to df. Each date gets its regime flags."""
    # Volatility tertiles per date (cross-sectional average)
    date_mean_vol = (
        df.groupby("date")["realized_vol_20"]
        .mean()
        .rename("_date_mean_vol")
    )
    df = df.join(date_mean_vol, on="date")

    # Compute vol tertile thresholds across all dates
    date_vols = df.groupby("date")["realized_vol_20"].mean()
    lo_thr = date_vols.quantile(1/3)
    hi_thr = date_vols.quantile(2/3)

    df["bull_market"]  = (df["market_trend"] == 1).astype(bool)
    df["bear_market"]  = (df["market_trend"] == -1).astype(bool)
    df["high_vol"]     = (df["_date_mean_vol"] >= hi_thr).astype(bool)
    df["low_vol"]      = (df["_date_mean_vol"] <= lo_thr).astype(bool)
    df["above_200dma"] = (df["spy_above_sma200"] == 1).astype(bool)
    df["below_200dma"] = (df["spy_above_sma200"] == 0).astype(bool)

    df = df.drop(columns=["_date_mean_vol"])
    return df


# ── Per-date IC computation ───────────────────────────────────────────────────

def compute_date_ics(
    df: pd.DataFrame,
    feature_cols: list[str],
    min_obs: int,
) -> pd.DataFrame:
    """
    For each (date, feature), compute cross-sectional Spearman IC vs TARGET_COL.
    Returns a long DataFrame: date, feature_name, ic, n.
    """
    rows = []
    dates = df["date"].unique()
    for d in dates:
        sub = df[df["date"] == d]
        y = sub[TARGET_COL].to_numpy(dtype=float)
        if len(y) < min_obs:
            continue
        for feat in feature_cols:
            if feat not in sub.columns:
                continue
            x = sub[feat].to_numpy(dtype=float)
            mask = ~np.isnan(x) & ~np.isnan(y)
            if mask.sum() < min_obs:
                continue
            ic, _ = scipy_stats.spearmanr(x[mask], y[mask])
            if not np.isnan(ic):
                rows.append({"date": d, "feature_name": feat, "ic": ic, "n": int(mask.sum())})
    return pd.DataFrame(rows)


# ── Regime-level aggregation ──────────────────────────────────────────────────

def aggregate_regime(
    date_ics: pd.DataFrame,
    df: pd.DataFrame,
    regime: str,
    feature_cols: list[str],
    min_dates: int,
) -> list[dict]:
    """
    Given date-level ICs and the regime mask, compute regime-level stats per feature.
    """
    # Get dates in this regime
    regime_dates = set(df[df[regime]]["date"].unique())
    sub = date_ics[date_ics["date"].isin(regime_dates)]

    results = []
    for feat in feature_cols:
        feat_ics = sub[sub["feature_name"] == feat]["ic"].to_numpy(dtype=float)
        n_dates  = len(feat_ics)
        n_obs    = int(sub[sub["feature_name"] == feat]["n"].sum())

        if n_dates < min_dates:
            continue

        mean_ic        = float(np.mean(feat_ics))
        ic_std         = float(np.std(feat_ics, ddof=1)) if n_dates > 1 else 0.0
        rank_ic        = float(np.mean(feat_ics))  # cross-sectional rank ICs
        sign_stability = float(np.mean(feat_ics > 0))
        ic_tstat       = float(mean_ic / (ic_std / np.sqrt(n_dates))) if ic_std > 0 and n_dates > 1 else 0.0

        # Fold stability: fraction of yearly buckets with positive mean IC
        feat_date_ic = sub[sub["feature_name"] == feat][["date", "ic"]].copy()
        feat_date_ic["year"] = pd.to_datetime(feat_date_ic["date"]).dt.year
        yearly_mean = feat_date_ic.groupby("year")["ic"].mean()
        fold_stability = float((yearly_mean > 0).mean()) if len(yearly_mean) > 0 else 0.0

        results.append({
            "feature_name":   feat,
            "regime":         regime,
            "n_dates":        n_dates,
            "n_observations": n_obs,
            "mean_ic":        round(mean_ic, 6),
            "ic_std":         round(ic_std, 6),
            "rank_ic":        round(rank_ic, 6),
            "sign_stability": round(sign_stability, 4),
            "fold_stability": round(fold_stability, 4),
            "ic_tstat":       round(ic_tstat, 4),
        })
    return results


# ── Classification ────────────────────────────────────────────────────────────

def classify_features(
    all_regime_rows: list[dict],
    feature_cols: list[str],
) -> dict[str, str]:
    """
    Assign each feature an overall classification based on regime performance.

    Always Useful      mean_ic > IC_USEFUL AND sign_stab > STAB_USEFUL in ALL regimes
    Regime Sensitive   mean_ic > IC_USEFUL OR sign_stab > STAB_USEFUL in SOME (not all) regimes
    Mostly Noise       |mean_ic| < IC_USEFUL in ALL regimes
    Potentially Harmful mean_ic < IC_HARMFUL in MAJORITY of regimes (>= 4 of 6)
    """
    from collections import defaultdict
    by_feature: dict[str, list[dict]] = defaultdict(list)
    for row in all_regime_rows:
        by_feature[row["feature_name"]].append(row)

    classifications: dict[str, str] = {}
    for feat in feature_cols:
        rows = by_feature.get(feat, [])
        if not rows:
            classifications[feat] = "Mostly Noise"
            continue

        n_useful   = sum(1 for r in rows if r["mean_ic"] > IC_USEFUL and r["sign_stability"] > STAB_USEFUL)
        n_harmful  = sum(1 for r in rows if r["mean_ic"] < IC_HARMFUL)
        n_noise    = sum(1 for r in rows if abs(r["mean_ic"]) < IC_USEFUL)
        n_regimes  = len(rows)

        if n_useful == n_regimes:
            classifications[feat] = "Always Useful"
        elif n_harmful >= max(1, n_regimes // 2 + 1):
            classifications[feat] = "Potentially Harmful"
        elif n_noise == n_regimes:
            classifications[feat] = "Mostly Noise"
        else:
            classifications[feat] = "Regime Sensitive"

    return classifications


# ── Output ────────────────────────────────────────────────────────────────────

def print_report(
    all_rows: list[dict],
    classifications: dict[str, str],
    feature_cols: list[str],
) -> None:
    sep = "-" * 100
    print(f"\n{sep}")
    print("  REGIME SENSITIVITY STUDY")
    print(sep)

    # Summary by classification
    from collections import Counter
    counts = Counter(classifications.values())
    for cat in ["Always Useful", "Regime Sensitive", "Mostly Noise", "Potentially Harmful"]:
        print(f"  {cat:<24}: {counts.get(cat, 0)} features")
    print()

    # Per-feature regime table
    by_feature: dict = {}
    for row in all_rows:
        by_feature.setdefault(row["feature_name"], {})[row["regime"]] = row

    print(f"  {'Feature':<32}  {'Class':<22}  " +
          "  ".join(f"{r[:8]:>8}" for r in REGIMES))
    print("  " + "-" * (32 + 22 + len(REGIMES) * 11 + 4))

    for feat in sorted(feature_cols, key=lambda f: classifications.get(f, "z")):
        cls = classifications.get(feat, "?")
        cells = []
        for regime in REGIMES:
            r = by_feature.get(feat, {}).get(regime)
            cells.append(f"{r['mean_ic']:+.3f}" if r else "  n/a ")
        print(f"  {feat:<32}  {cls:<22}  " + "  ".join(cells))

    print()

    # Regime-aware V3 design summary
    print(f"  REGIME-AWARE FEATURE SET V3 DESIGN")
    print("  " + "-" * 70)
    print("  Features to ALWAYS include (Always Useful):")
    always = [f for f in feature_cols if classifications.get(f) == "Always Useful"]
    for f in always:
        print(f"    {f}")
    print()
    print("  Features to include CONDITIONALLY (Regime Sensitive):")
    sensitive = [f for f in feature_cols if classifications.get(f) == "Regime Sensitive"]
    for f in sensitive:
        rows_f = by_feature.get(f, {})
        good_regimes = [r for r, row in rows_f.items()
                        if row["mean_ic"] > IC_USEFUL and row["sign_stability"] > STAB_USEFUL]
        print(f"    {f:<32} -- active in: {', '.join(good_regimes)}")
    print()
    print("  Features to EXCLUDE (Mostly Noise / Potentially Harmful):")
    exclude = [f for f in feature_cols
               if classifications.get(f) in ("Mostly Noise", "Potentially Harmful")]
    for f in exclude:
        print(f"    {f:<32} [{classifications[f]}]")
    print(sep)


# ── DB write ──────────────────────────────────────────────────────────────────

def write_results(db_url: str, rows: list[dict]) -> int:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO feature_regime_performance
                    (feature_name, regime, n_dates, n_observations,
                     mean_ic, ic_std, rank_ic, sign_stability, fold_stability,
                     ic_tstat, classification)
                VALUES
                    (%(feature_name)s, %(regime)s, %(n_dates)s, %(n_observations)s,
                     %(mean_ic)s, %(ic_std)s, %(rank_ic)s, %(sign_stability)s,
                     %(fold_stability)s, %(ic_tstat)s, %(classification)s)
                ON CONFLICT (feature_name, regime) DO UPDATE SET
                    n_dates         = EXCLUDED.n_dates,
                    n_observations  = EXCLUDED.n_observations,
                    mean_ic         = EXCLUDED.mean_ic,
                    ic_std          = EXCLUDED.ic_std,
                    rank_ic         = EXCLUDED.rank_ic,
                    sign_stability  = EXCLUDED.sign_stability,
                    fold_stability  = EXCLUDED.fold_stability,
                    ic_tstat        = EXCLUDED.ic_tstat,
                    classification  = EXCLUDED.classification,
                    computed_at     = now()
            """, rows)
        conn.commit()
    return len(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Feature regime sensitivity study")
    parser.add_argument("--parquet-dir", default=None)
    parser.add_argument("--no-db",       action="store_true")
    parser.add_argument("--min-obs",     type=int, default=20,
                        help="Min observations per date for IC (default 20)")
    parser.add_argument("--min-dates",   type=int, default=30,
                        help="Min regime-dates for regime stats (default 30)")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    parquet_dir = Path(args.parquet_dir) if args.parquet_dir else ROOT / "exports" / "parquet"
    feature_cols = TRAIN_FEATURES_V1

    print(f"\nRegime Sensitivity Study")
    print(f"  Features  : {len(feature_cols)}")
    print(f"  Regimes   : {REGIMES}")
    print(f"  Parquet   : {parquet_dir}")
    print(f"  Target    : {TARGET_COL}")

    # ── Load data ──────────────────────────────────────────────────────────
    print("\nLoading parquet data...")
    df = load_all_parquet(parquet_dir, feature_cols)
    if df.empty:
        sys.exit("[ERROR] No parquet data loaded")
    print(f"  Loaded {len(df):,} rows  ({df['date'].min()} to {df['date'].max()})")
    print(f"  Unique dates: {df['date'].nunique():,}")

    # ── Check regime columns ───────────────────────────────────────────────
    for col in ["market_trend", "spy_above_sma200", "realized_vol_20"]:
        n = df[col].notna().sum() if col in df.columns else 0
        print(f"  {col}: {n:,} non-null rows")

    # ── Assign regime flags ────────────────────────────────────────────────
    print("\nAssigning regime flags...")
    df = assign_regimes(df)
    for regime in REGIMES:
        n_dates = df[df[regime]]["date"].nunique()
        n_rows  = df[regime].sum()
        print(f"  {regime:<16}: {n_rows:>7,} rows  ({n_dates} dates)")

    # ── Compute per-date ICs ───────────────────────────────────────────────
    print(f"\nComputing per-date cross-sectional ICs (min_obs={args.min_obs})...")
    date_ics = compute_date_ics(df, feature_cols, args.min_obs)
    print(f"  {len(date_ics):,} (date, feature) IC observations")

    # ── Aggregate by regime ────────────────────────────────────────────────
    print("\nAggregating by regime...")
    all_regime_rows: list[dict] = []
    for regime in REGIMES:
        rows = aggregate_regime(date_ics, df, regime, feature_cols, args.min_dates)
        all_regime_rows.extend(rows)
        n_feats = len(rows)
        print(f"  {regime:<16}: {n_feats} features computed")

    # ── Classify ───────────────────────────────────────────────────────────
    classifications = classify_features(all_regime_rows, feature_cols)
    for row in all_regime_rows:
        row["classification"] = classifications.get(row["feature_name"], "Mostly Noise")

    # ── Print report ───────────────────────────────────────────────────────
    print_report(all_regime_rows, classifications, feature_cols)

    # ── Write to DB ────────────────────────────────────────────────────────
    if not args.no_db and all_regime_rows:
        n = write_results(db_url, all_regime_rows)
        print(f"  Written {n} rows to feature_regime_performance")

    # ── V3 design summary ──────────────────────────────────────────────────
    always   = [f for f in feature_cols if classifications.get(f) == "Always Useful"]
    sensitive = [f for f in feature_cols if classifications.get(f) == "Regime Sensitive"]
    noise     = [f for f in feature_cols if classifications.get(f) == "Mostly Noise"]
    harmful   = [f for f in feature_cols if classifications.get(f) == "Potentially Harmful"]
    print(f"\n  V3 FEATURE SET DESIGN (regime-aware):")
    print(f"    Always active   : {len(always)} features")
    print(f"    Regime-gated    : {len(sensitive)} features")
    print(f"    Candidates drop : {len(noise)} noise + {len(harmful)} harmful = {len(noise)+len(harmful)}")
    print(f"    V3 base size    : {len(always) + len(sensitive)} features (all gated)")
    print(f"    V3 active min   : {len(always)} features (bear/low-vol regime)")
    print()
    log.info("regime_study.done",
             n_rows=len(all_regime_rows), n_always=len(always),
             n_sensitive=len(sensitive), n_noise=len(noise), n_harmful=len(harmful))


if __name__ == "__main__":
    main()
