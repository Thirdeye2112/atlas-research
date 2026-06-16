"""
Compute Feature Reliability
============================
For every feature in ALL_FEATURES, compute rolling Spearman IC against
label_return_5d for 30d / 90d / 180d windows.  Assess trend direction,
flag reliable / declining / unreliable features, and write results to
the feature_reliability table.  Also generates FEATURE_RELIABILITY_REPORT.md.

Usage:
    python scripts/compute_feature_reliability.py
    python scripts/compute_feature_reliability.py --date 2026-06-15
    python scripts/compute_feature_reliability.py --report-only
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy import stats as scipy_stats
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

from config.settings import ALL_FEATURES, PARQUET_OUTPUT_DIR, INFERENCE_EXTRA_COLS

REPORT_PATH = _ROOT / "reports" / "FEATURE_RELIABILITY_REPORT.md"

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

IC_RELIABLE     = 0.007    # |IC| >= this → reliable
IC_UNRELIABLE   = 0.003    # |IC| <  this → unreliable
IMPROVING_DELTA = 0.002    # ic_30d > ic_90d + this → improving
DECLINING_DELTA = 0.002    # ic_90d > ic_30d + this → declining
MIN_DATES       = 10       # minimum trading days in window to compute IC


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_parquet_window(
    end_date: date,
    days: int,
    parquet_dir: Path,
    features: list[str],
) -> pd.DataFrame:
    """
    Load all parquets in [end_date - days, end_date], stack them.
    Returns DataFrame with columns: date, feature values, label_return_5d.
    """
    start = end_date - timedelta(days=days + 30)  # buffer for non-trading days
    frames = []

    pq_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    for fpath in pq_files:
        try:
            d = date.fromisoformat(fpath.stem.replace("feature_matrix_", ""))
        except ValueError:
            continue
        if not (start <= d <= end_date):
            continue

        try:
            needed = ["ticker", "date"] + [f for f in features if f not in ("ticker", "date")]
            needed += ["label_return_5d"]
            avail_cols = set(pd.read_parquet(fpath, engine="pyarrow").columns)
            read_cols = [c for c in needed if c in avail_cols]
            df = pd.read_parquet(fpath, engine="pyarrow", columns=read_cols)
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    return combined


def load_regime_context(df: pd.DataFrame) -> pd.DataFrame:
    """Classify each row's regime from market_trend and realized_vol_20."""
    if "market_trend" in df.columns:
        df["regime_market"] = np.where(df["market_trend"] > 0, "bull",
                              np.where(df["market_trend"] < 0, "bear", "range"))
    else:
        df["regime_market"] = "unknown"

    if "realized_vol_20" in df.columns:
        df["regime_vol"] = np.where(df["realized_vol_20"] > 0.30, "high_vol", "low_vol")
    else:
        df["regime_vol"] = "unknown"

    return df


# ---------------------------------------------------------------------------
# IC computation
# ---------------------------------------------------------------------------

def cross_sectional_ic(
    df: pd.DataFrame,
    feature: str,
    label_col: str = "label_return_5d",
    min_dates: int = MIN_DATES,
) -> tuple[float | None, int]:
    """
    Compute mean daily cross-sectional Spearman IC for one feature.
    Returns (mean_ic, n_dates_with_valid_ic).
    """
    if feature not in df.columns or label_col not in df.columns:
        return None, 0

    ics = []
    for _, grp in df.groupby("date"):
        sub = grp[[feature, label_col]].dropna()
        if len(sub) < 10:
            continue
        r, _ = scipy_stats.spearmanr(sub[feature], sub[label_col])
        if not np.isnan(r):
            ics.append(r)

    if len(ics) < min_dates:
        return None, len(ics)
    return float(np.mean(ics)), len(ics)


def regime_ic(
    df: pd.DataFrame,
    feature: str,
    regime_col: str,
    regime_val: str,
    label_col: str = "label_return_5d",
) -> float | None:
    sub = df[df[regime_col] == regime_val]
    ic, n = cross_sectional_ic(sub, feature, label_col, min_dates=5)
    return ic


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_trend(ic_30: float | None, ic_90: float | None, ic_180: float | None) -> str:
    """Classify IC trend from most-recent to longer windows."""
    if ic_30 is None and ic_90 is None:
        return "insufficient_data"
    if ic_30 is None:
        return "declining"
    if ic_90 is None:
        # Only 30d available
        return "stable" if abs(ic_30) >= IC_RELIABLE else "unreliable"

    delta = ic_30 - ic_90
    if abs(ic_30) < IC_UNRELIABLE:
        return "unreliable"
    if delta > IMPROVING_DELTA and abs(ic_30) >= IC_RELIABLE:
        return "improving"
    if delta < -DECLINING_DELTA:
        return "declining"
    return "stable"


def classify_reliability(
    ic_30: float | None,
    ic_90: float | None,
    n_30: int,
    trend: str,
) -> dict[str, bool]:
    reliable    = ic_30 is not None and abs(ic_30) >= IC_RELIABLE and trend in ("stable", "improving")
    declining   = trend == "declining"
    unreliable  = trend == "unreliable" or (ic_30 is not None and abs(ic_30) < IC_UNRELIABLE)
    insuf       = trend == "insufficient_data" or n_30 < MIN_DATES
    return dict(
        currently_reliable=reliable,
        declining=declining,
        unreliable=unreliable,
        insufficient_data=insuf,
    )


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_reliability(
    as_of: date,
    parquet_dir: Path,
    features: list[str],
) -> pd.DataFrame:
    """
    Compute reliability stats for all features on `as_of` date.
    Returns DataFrame of results, one row per feature.
    """
    print("Loading parquet windows...")
    df_180 = load_parquet_window(as_of, 180, parquet_dir, features)
    df_180 = load_regime_context(df_180) if not df_180.empty else df_180

    if df_180.empty:
        print("No parquet data found.")
        return pd.DataFrame()

    # Filter to only rows with valid labels
    df_180 = df_180[df_180["label_return_5d"].notna()].copy()
    if df_180.empty:
        print("No labeled rows found in 180d window.")
        return pd.DataFrame()

    # Compute date cutoffs
    dates_sorted = sorted(df_180["date"].unique())
    cutoff_30  = dates_sorted[-30]  if len(dates_sorted) >= 30  else dates_sorted[0]
    cutoff_90  = dates_sorted[-90]  if len(dates_sorted) >= 90  else dates_sorted[0]

    df_30  = df_180[df_180["date"] >= cutoff_30]
    df_90  = df_180[df_180["date"] >= cutoff_90]

    print(f"  180d: {len(dates_sorted)} dates, {len(df_180):,} rows")
    print(f"   90d: {(df_180['date'] >= cutoff_90).sum()} rows")
    print(f"   30d: {(df_180['date'] >= cutoff_30).sum()} rows")

    results = []
    for feat in features:
        ic_30,  n_30  = cross_sectional_ic(df_30,  feat)
        ic_90,  n_90  = cross_sectional_ic(df_90,  feat)
        ic_180, n_180 = cross_sectional_ic(df_180, feat)

        # Regime ICs
        ic_bull = regime_ic(df_180, feat, "regime_market", "bull")   if "regime_market" in df_180.columns else None
        ic_bear = regime_ic(df_180, feat, "regime_market", "bear")   if "regime_market" in df_180.columns else None
        ic_hvol = regime_ic(df_180, feat, "regime_vol",    "high_vol") if "regime_vol" in df_180.columns else None

        trend = classify_trend(ic_30, ic_90, ic_180)
        flags = classify_reliability(ic_30, ic_90, n_30, trend)

        results.append({
            "feature_name":     feat,
            "computed_date":    as_of,
            "ic_30d":           ic_30,
            "ic_90d":           ic_90,
            "ic_180d":          ic_180,
            "n_dates_30d":      n_30,
            "n_dates_90d":      n_90,
            "n_dates_180d":     n_180,
            "ic_bull":          ic_bull,
            "ic_bear":          ic_bear,
            "ic_high_vol":      ic_hvol,
            "ic_trend":         trend,
            "trend_delta":      (ic_30 - ic_90) if (ic_30 is not None and ic_90 is not None) else None,
            **flags,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def upsert_reliability(df: pd.DataFrame, engine) -> int:
    if df.empty:
        return 0

    sql = text("""
        INSERT INTO feature_reliability (
            feature_name, computed_date,
            ic_30d, ic_90d, ic_180d,
            n_dates_30d, n_dates_90d, n_dates_180d,
            ic_bull, ic_bear, ic_high_vol,
            ic_trend, trend_delta,
            currently_reliable, declining, unreliable, insufficient_data
        ) VALUES (
            :feature_name, :computed_date,
            :ic_30d, :ic_90d, :ic_180d,
            :n_dates_30d, :n_dates_90d, :n_dates_180d,
            :ic_bull, :ic_bear, :ic_high_vol,
            :ic_trend, :trend_delta,
            :currently_reliable, :declining, :unreliable, :insufficient_data
        )
        ON CONFLICT (feature_name, computed_date) DO UPDATE SET
            ic_30d             = EXCLUDED.ic_30d,
            ic_90d             = EXCLUDED.ic_90d,
            ic_180d            = EXCLUDED.ic_180d,
            n_dates_30d        = EXCLUDED.n_dates_30d,
            n_dates_90d        = EXCLUDED.n_dates_90d,
            n_dates_180d       = EXCLUDED.n_dates_180d,
            ic_bull            = EXCLUDED.ic_bull,
            ic_bear            = EXCLUDED.ic_bear,
            ic_high_vol        = EXCLUDED.ic_high_vol,
            ic_trend           = EXCLUDED.ic_trend,
            trend_delta        = EXCLUDED.trend_delta,
            currently_reliable = EXCLUDED.currently_reliable,
            declining          = EXCLUDED.declining,
            unreliable         = EXCLUDED.unreliable,
            insufficient_data  = EXCLUDED.insufficient_data
    """)

    rows = df.to_dict("records")
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def build_report(df: pd.DataFrame, as_of: date) -> str:
    lines = []
    lines.append("# Feature Reliability Report")
    lines.append(f"\n**Generated:** {as_of}")
    lines.append(f"**Features evaluated:** {len(df)}")
    lines.append("")

    n_reliable   = df["currently_reliable"].sum()
    n_declining  = df["declining"].sum()
    n_unreliable = df["unreliable"].sum()
    n_insuf      = df["insufficient_data"].sum()

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Status | Count |")
    lines.append(f"|---|---|")
    lines.append(f"| Reliable | {n_reliable} |")
    lines.append(f"| Declining | {n_declining} |")
    lines.append(f"| Unreliable | {n_unreliable} |")
    lines.append(f"| Insufficient data | {n_insuf} |")
    lines.append("")

    def ic_str(v):
        return f"{v:+.4f}" if v is not None else "n/a"

    def flag_str(row):
        flags = []
        if row["currently_reliable"]:  flags.append("RELIABLE")
        if row["declining"]:           flags.append("DECLINING")
        if row["unreliable"]:          flags.append("UNRELIABLE")
        if row["insufficient_data"]:   flags.append("INSUF")
        return ", ".join(flags) or "stable"

    sorted_df = df.sort_values("ic_30d", ascending=False, na_position="last")

    lines.append("## Full Feature IC Table")
    lines.append("")
    lines.append("| Feature | Trend | IC 30d | IC 90d | IC 180d | IC Bull | IC Bear | Flags |")
    lines.append("|---|---|---|---|---|---|---|---|")

    for _, row in sorted_df.iterrows():
        lines.append(
            f"| {row['feature_name']} "
            f"| {row['ic_trend']} "
            f"| {ic_str(row['ic_30d'])} "
            f"| {ic_str(row['ic_90d'])} "
            f"| {ic_str(row['ic_180d'])} "
            f"| {ic_str(row['ic_bull'])} "
            f"| {ic_str(row['ic_bear'])} "
            f"| {flag_str(row)} |"
        )

    lines.append("")
    lines.append("## Declining Features — Action Required")
    lines.append("")
    declining = df[df["declining"]].sort_values("trend_delta")
    if declining.empty:
        lines.append("_None_")
    else:
        for _, row in declining.iterrows():
            lines.append(f"- **{row['feature_name']}**: IC 30d={ic_str(row['ic_30d'])}, 90d={ic_str(row['ic_90d'])} (delta={ic_str(row['trend_delta'])})")

    lines.append("")
    lines.append("## Unreliable Features")
    lines.append("")
    unreliable = df[df["unreliable"]].sort_values("ic_30d", na_position="last")
    if unreliable.empty:
        lines.append("_None_")
    else:
        for _, row in unreliable.iterrows():
            lines.append(f"- **{row['feature_name']}**: IC 30d={ic_str(row['ic_30d'])}, 90d={ic_str(row['ic_90d'])}")

    lines.append("")
    lines.append("## Regime Contrast (Bull vs Bear IC)")
    lines.append("")
    lines.append("| Feature | IC Bull | IC Bear | Delta |")
    lines.append("|---|---|---|---|")
    regime_df = df[df["ic_bull"].notna() & df["ic_bear"].notna()].copy()
    regime_df["regime_delta"] = regime_df["ic_bull"] - regime_df["ic_bear"]
    for _, row in regime_df.sort_values("regime_delta", ascending=False).iterrows():
        lines.append(
            f"| {row['feature_name']} "
            f"| {ic_str(row['ic_bull'])} "
            f"| {ic_str(row['ic_bear'])} "
            f"| {ic_str(row['regime_delta'])} |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",        default=str(date.today()), help="Compute as-of date")
    parser.add_argument("--report-only", action="store_true", help="Only write report, skip DB write")
    args = parser.parse_args()

    as_of       = date.fromisoformat(args.date)
    parquet_dir = Path(PARQUET_OUTPUT_DIR)
    features    = ALL_FEATURES

    print(f"\nFeature Reliability Computation — {as_of}")
    print(f"Features: {len(features)}")
    print("-" * 60)

    df = compute_reliability(as_of, parquet_dir, features)
    if df.empty:
        print("No results computed.")
        return 1

    # Summary
    print(f"\n--- Results ---")
    print(f"  Reliable:           {df['currently_reliable'].sum()}")
    print(f"  Declining:          {df['declining'].sum()}")
    print(f"  Unreliable:         {df['unreliable'].sum()}")
    print(f"  Insufficient data:  {df['insufficient_data'].sum()}")

    if not args.report_only:
        engine = create_engine(os.environ["DATABASE_URL"])
        n = upsert_reliability(df, engine)
        print(f"  Upserted:           {n} rows to feature_reliability")

    report = build_report(df, as_of)
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"  Report written:     {REPORT_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
