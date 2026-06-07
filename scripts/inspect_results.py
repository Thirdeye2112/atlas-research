#!/usr/bin/env python
"""
inspect_results.py — post-training diagnostic tool.

Run after backfill + training to inspect:
  1. Data coverage    — bars, features, labels per date
  2. Parquet health   — file count, size, column coverage
  3. Walk-forward     — Rank IC, Brier, AUC per fold
  4. Decile returns   — top/bottom decile return separation
  5. Feature importance — stability across folds
  6. Prediction coverage — today's predictions written

Usage:
    python scripts/inspect_results.py
    python scripts/inspect_results.py --date 2024-01-15  # inspect specific date
    python scripts/inspect_results.py --folds-only       # only WF metrics
    python scripts/inspect_results.py --features-only    # only feature importance
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from atlas_research.db.connection import check_connection, get_connection
from atlas_research.utils.logging import configure_logging, get_logger
from sqlalchemy import text

configure_logging(level="INFO", fmt="console")
log = get_logger("inspect")


# ── Helpers ───────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print('─' * 60)


def fmt(v, decimals: int = 4) -> str:
    if v is None:
        return "NULL"
    try:
        f = float(v)
        import math
        if math.isnan(f):
            return "nan"
        return f"{f:.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


# ── Section 1: Data coverage ──────────────────────────────────

def inspect_data_coverage() -> None:
    section("DATA COVERAGE")
    with get_connection() as conn:
        # raw_bars
        r = conn.execute(text("""
            SELECT COUNT(*) AS bars,
                   COUNT(DISTINCT ticker) AS tickers,
                   MIN(date) AS first_date,
                   MAX(date) AS last_date
            FROM raw_bars
        """)).fetchone()
        print(f"  raw_bars:          {r[0]:>10,} rows  |  {r[1]} tickers  "
              f"|  {r[2]} → {r[3]}")

        # feature_snapshots
        r2 = conn.execute(text("""
            SELECT COUNT(*) AS rows,
                   COUNT(DISTINCT ticker) AS tickers,
                   COUNT(DISTINCT date) AS dates,
                   COUNT(DISTINCT feature_name) AS features,
                   MIN(date) AS first_date,
                   MAX(date) AS last_date
            FROM feature_snapshots
        """)).fetchone()
        print(f"  feature_snapshots: {r2[0]:>10,} rows  |  {r2[1]} tickers  "
              f"|  {r2[2]} dates  |  {r2[3]} features  |  {r2[4]} → {r2[5]}")

        # labels
        r3 = conn.execute(text("""
            SELECT COUNT(*) AS total,
                   COUNT(return_5d) AS labeled_5d,
                   COUNT(positive_5d) AS labeled_pos5d,
                   MIN(date) AS first_date,
                   MAX(date) AS last_date
            FROM labels
        """)).fetchone()
        coverage = 100 * r3[1] / r3[0] if r3[0] > 0 else 0
        print(f"  labels:            {r3[0]:>10,} rows  |  "
              f"{r3[1]:,} with return_5d ({coverage:.1f}%)  |  {r3[3]} → {r3[4]}")


# ── Section 2: Parquet file health ────────────────────────────

def inspect_parquet_health(snap_date: date | None = None) -> None:
    section("PARQUET FILE HEALTH")
    parquet_dir = settings.PARQUET_OUTPUT_DIR

    if not parquet_dir.exists():
        print(f"  ✗ Parquet directory not found: {parquet_dir}")
        return

    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    if not files:
        print("  ✗ No parquet files found. Run backfill first.")
        return

    total_mb = sum(f.stat().st_size for f in files) / 1_048_576
    print(f"  Files:      {len(files)}")
    print(f"  Date range: {files[0].stem.split('_')[-1]} → {files[-1].stem.split('_')[-1]}")
    print(f"  Total size: {total_mb:.1f} MB  ({total_mb/len(files):.2f} MB/file avg)")

    # Inspect most recent file (or specified date)
    inspect_file = None
    if snap_date:
        candidate = parquet_dir / f"feature_matrix_{snap_date.isoformat()}.parquet"
        if candidate.exists():
            inspect_file = candidate
    if not inspect_file:
        inspect_file = files[-1]

    try:
        import pandas as pd
        df = pd.read_parquet(inspect_file, engine="pyarrow")
        print(f"\n  Sample file: {inspect_file.name}")
        print(f"    Rows (tickers):   {len(df)}")
        print(f"    Columns:          {len(df.columns)}")

        feature_cols = [c for c in df.columns
                        if c not in ("ticker", "date", "data_quality_score",
                                     "data_quality_flags") and not c.startswith("label_")]
        label_cols   = [c for c in df.columns if c.startswith("label_")]

        print(f"    Feature cols:     {len(feature_cols)}")
        print(f"    Label cols:       {len(label_cols)}")

        # NaN rates for key features
        print(f"\n    NaN rates (feature columns):")
        nan_rates = df[feature_cols].isna().mean().sort_values(ascending=False)
        for feat, rate in nan_rates.head(10).items():
            flag = " ← HIGH" if rate > 0.20 else ""
            print(f"      {feat:<30} {rate:.1%}{flag}")

        # Quality score distribution
        if "data_quality_score" in df.columns:
            qs = df["data_quality_score"]
            print(f"\n    data_quality_score:  "
                  f"min={qs.min():.3f}  median={qs.median():.3f}  "
                  f"mean={qs.mean():.3f}  "
                  f"below_0.7={( qs<0.7).mean():.1%}")

        # Label coverage
        if label_cols:
            print(f"\n    Label coverage:")
            for lc in label_cols:
                present = df[lc].notna().mean()
                print(f"      {lc:<30} {present:.1%} non-null")

    except Exception as exc:
        print(f"  ✗ Could not read parquet: {exc}")


# ── Section 3: Walk-forward fold metrics ──────────────────────

def inspect_walk_forward_metrics() -> None:
    section("WALK-FORWARD FOLD METRICS")

    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT model_name, model_version,
                   training_start, training_end,
                   ic AS rank_ic, rank_ic AS spearman_ic,
                   auc, brier, sharpe,
                   train_rows, val_rows,
                   notes, created_at
            FROM model_registry
            ORDER BY created_at ASC
        """)).fetchall()

    if not rows:
        print("  No model_registry rows. Run training first.")
        return

    print(f"  {'Model':<28} {'Train window':<24} {'Rank IC':>8} "
          f"{'AUC':>7} {'Brier':>7} {'Sharpe':>8} {'Rows':>8}")
    print("  " + "─" * 90)

    rank_ics = []
    aucs = []
    briers = []

    for r in rows:
        model = f"{r[0]} {r[1]}"
        window = f"{r[2]} → {r[3]}" if r[2] and r[3] else "—"
        ic  = r[4]
        auc = r[6]
        bri = r[7]
        shr = r[8]
        vr  = r[10]

        if ic is not None:
            rank_ics.append(ic)
        if auc is not None:
            aucs.append(auc)
        if bri is not None:
            briers.append(bri)

        print(f"  {model:<28} {window:<24} {fmt(ic):>8} "
              f"{fmt(auc):>7} {fmt(bri):>7} {fmt(shr):>8} {str(vr or '—'):>8}")

    if rank_ics:
        import statistics
        print()
        print(f"  Summary across {len(rank_ics)} fold(s):")
        print(f"    Mean Rank IC:   {statistics.mean(rank_ics):.4f}  "
              f"(std={statistics.stdev(rank_ics):.4f})"
              if len(rank_ics) > 1 else f"    Rank IC:        {rank_ics[0]:.4f}")
        if aucs:
            print(f"    Mean AUC:       {statistics.mean(aucs):.4f}")
        if briers:
            print(f"    Mean Brier:     {statistics.mean(briers):.4f}  "
                  f"(baseline=0.25)")

        # Interpretation guide
        print()
        print("  Interpretation:")
        mean_ic = statistics.mean(rank_ics) if rank_ics else 0
        if mean_ic > 0.04:
            print("    ✓ Rank IC > 0.04 — meaningful signal for equities")
        elif mean_ic > 0.02:
            print("    ~ Rank IC 0.02–0.04 — weak but present signal")
        else:
            print("    ✗ Rank IC < 0.02 — signal may be too weak or features incomplete")


# ── Section 4: Decile return separation ───────────────────────

def inspect_decile_returns(snap_date: date | None = None) -> None:
    section("DECILE RETURN SEPARATION (latest predictions)")

    with get_connection() as conn:
        # Find most recent prediction date
        r = conn.execute(text("""
            SELECT MAX(date) FROM predictions
        """)).scalar()
        if r is None:
            print("  No predictions found. Run training then --predict-only.")
            return

        pred_date = r
        print(f"  Prediction date: {pred_date}")

        rows = conn.execute(text("""
            SELECT p.ticker,
                   p.probability_positive,
                   p.expected_return,
                   p.rank_percentile,
                   l.return_5d AS actual_return_5d,
                   l.positive_5d AS actual_positive_5d
            FROM predictions p
            LEFT JOIN labels l ON l.ticker = p.ticker AND l.date = p.date
            WHERE p.date = :d
            ORDER BY p.rank_percentile DESC
        """), {"d": pred_date}).fetchall()

    if not rows:
        print("  No predictions for this date.")
        return

    import pandas as pd
    df = pd.DataFrame(rows, columns=[
        "ticker", "probability_positive", "expected_return",
        "rank_percentile", "actual_return_5d", "actual_positive_5d"
    ])

    print(f"  Tickers predicted: {len(df)}")
    has_actual = df["actual_return_5d"].notna().any()

    if has_actual:
        df["decile"] = pd.qcut(df["rank_percentile"], 10, labels=False) + 1
        decile_stats = df.groupby("decile").agg(
            n=("ticker", "count"),
            mean_pred_prob=("probability_positive", "mean"),
            mean_actual_ret=("actual_return_5d", "mean"),
            pct_positive=("actual_positive_5d", "mean"),
        ).round(4)

        print(f"\n  {'Decile':>7} {'N':>5} {'Pred P(+)':>10} "
              f"{'Actual Ret 5d':>14} {'Actual P(+)':>12}")
        print("  " + "─" * 52)
        for dec, row in decile_stats.iterrows():
            marker = " ←" if dec in (1, 10) else ""
            print(f"  {dec:>7} {int(row['n']):>5} {row['mean_pred_prob']:>10.4f} "
                  f"{row['mean_actual_ret']:>14.4f} {row['pct_positive']:>12.4f}{marker}")

        top = decile_stats.loc[10]
        bot = decile_stats.loc[1]
        spread = top["mean_actual_ret"] - bot["mean_actual_ret"]
        print(f"\n  Top-bottom decile spread: {spread:.4f}  "
              f"({'✓ positive' if spread > 0 else '✗ negative'})")
    else:
        print("\n  ⚠ No actual returns available yet (labels not yet computed")
        print("    for this future date). Distribution of predictions:")
        prob = df["probability_positive"]
        print(f"    mean={prob.mean():.3f}  std={prob.std():.3f}  "
              f"min={prob.min():.3f}  max={prob.max():.3f}")
        print(f"    % predicted positive (>0.5): {(prob>0.5).mean():.1%}")


# ── Section 5: Feature importance stability ───────────────────

def inspect_feature_importance() -> None:
    section("FEATURE IMPORTANCE STABILITY ACROSS FOLDS")

    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT feature_name,
                   COUNT(*) AS n_folds,
                   AVG(spearman_ic) AS mean_ic,
                   STDDEV(spearman_ic) AS std_ic,
                   AVG(lgbm_gain) AS mean_gain,
                   STDDEV(lgbm_gain) AS std_gain
            FROM feature_performance
            WHERE target = 'label_return_5d'
            GROUP BY feature_name
            ORDER BY ABS(AVG(spearman_ic)) DESC NULLS LAST
        """)).fetchall()

    if not rows:
        print("  No feature_performance rows. Run walk-forward first.")
        return

    print(f"  {'Feature':<32} {'Folds':>5} {'Mean IC':>9} {'Std IC':>8} "
          f"{'IC/Std':>8} {'Mean Gain':>10}")
    print("  " + "─" * 76)

    for r in rows[:25]:
        feat, n, mean_ic, std_ic, mean_gain, std_gain = r
        ir = (mean_ic / std_ic) if (std_ic and std_ic > 0 and mean_ic) else None
        stable_flag = " ✓" if (ir and abs(ir) > 0.5) else ""
        print(f"  {feat:<32} {n:>5} {fmt(mean_ic):>9} {fmt(std_ic):>8} "
              f"{fmt(ir):>8} {fmt(mean_gain, 0):>10}{stable_flag}")

    print(f"\n  ✓ = IC/Std > 0.5 (consistent signal across folds)")


# ── Section 6: Today's prediction coverage ────────────────────

def inspect_today_predictions() -> None:
    section("TODAY'S PREDICTION COVERAGE")

    with get_connection() as conn:
        today_rows = conn.execute(text("""
            SELECT model_name, model_version, COUNT(*) AS n_preds,
                   AVG(probability_positive) AS mean_prob,
                   AVG(confidence) AS mean_conf,
                   MIN(rank_percentile) AS min_rank,
                   MAX(rank_percentile) AS max_rank
            FROM predictions
            WHERE date = CURRENT_DATE
            GROUP BY model_name, model_version
        """)).fetchall()

    if not today_rows:
        print(f"  No predictions for today ({date.today()}).")
        print("  Run: python scripts/run_training.py --predict-only")
        return

    for r in today_rows:
        print(f"  Model:  {r[0]} v{r[1]}")
        print(f"    Predictions:  {r[2]}")
        print(f"    Mean P(+):    {fmt(r[3])}")
        print(f"    Mean conf:    {fmt(r[4])}")
        print(f"    Rank range:   {fmt(r[5])} → {fmt(r[6])}")


# ── Main ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect atlas-research training results")
    parser.add_argument("--date",           default=None, help="Inspect specific date YYYY-MM-DD")
    parser.add_argument("--folds-only",     action="store_true")
    parser.add_argument("--features-only",  action="store_true")
    parser.add_argument("--parquet-only",   action="store_true")
    args = parser.parse_args()

    if not check_connection():
        print("✗ Cannot connect to database. Check DATABASE_URL.")
        sys.exit(1)

    snap_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else None
    )

    if args.folds_only:
        inspect_walk_forward_metrics()
        return
    if args.features_only:
        inspect_feature_importance()
        return
    if args.parquet_only:
        inspect_parquet_health(snap_date)
        return

    # Full inspection
    inspect_data_coverage()
    inspect_parquet_health(snap_date)
    inspect_walk_forward_metrics()
    inspect_decile_returns(snap_date)
    inspect_feature_importance()
    inspect_today_predictions()

    print("\n" + "─" * 60)
    print("  Inspection complete.")
    print("─" * 60)


if __name__ == "__main__":
    main()
