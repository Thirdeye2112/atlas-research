"""
Compute Prediction Outcomes
============================
Retroactively scores every parquet date, joins actual forward returns from labels,
and stores resolved outcomes in the `prediction_outcomes` table.

Sources:
  - Parquet files:  features + ML model scoring
  - Labels DB:      actual 5d / 10d / 20d forward returns

Populates: prediction_outcomes (upsert)

Usage:
    python scripts/compute_prediction_outcomes.py
    python scripts/compute_prediction_outcomes.py --start-date 2020-01-01
    python scripts/compute_prediction_outcomes.py --start-date 2023-01-01 --end-date 2024-12-31
"""
from __future__ import annotations

import argparse
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

load_dotenv(_ROOT / ".env")

from run_confluence_backtest import (
    load_static_stats,
    build_model_map,
    compute_forward_returns,
    MIN_SAMPLE,
    WEIGHTS,
)
from run_conviction_backtest import add_conviction
from run_edge_hierarchy import load_and_score_extended
from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR
from atlas_research.utils.logging import get_logger

log = get_logger("prediction_outcomes")

MIN_LABEL_HORIZON = 5   # days; predictions without at least 5d outcome are skipped
BATCH_SIZE        = 5_000
MODEL_VERSION     = "v1"
FEAT_VERSION      = "v1"


# ── VIX-regime proxy from individual stock realized vol ─────────────────────

def _vix_regime(rv20: np.ndarray) -> np.ndarray:
    """Classify each row's VIX regime from realized_vol_20 (annualized)."""
    return np.where(rv20 > 0.40, "high",
           np.where(rv20 > 0.20, "moderate", "low"))


# ── Cross-sectional quintile ranking ────────────────────────────────────────

def _quintile_rank(series: pd.Series) -> pd.Series:
    """
    Rank values within a group to quintiles 1-5.
    NaN values stay NaN.
    """
    return series.rank(pct=True).apply(
        lambda x: int(min(5, max(1, np.ceil(x * 5)))) if pd.notna(x) else np.nan
    )


# ── Build outcome rows from scored DataFrame ─────────────────────────────────

def build_outcomes(scored: pd.DataFrame) -> pd.DataFrame:
    """
    Convert scored + forward-return DataFrame into prediction_outcomes rows.
    Only rows with direction != 0 and fwd_5d not NaN are written.
    """
    # Only process rows with directional predictions and resolved 5d labels
    mask = (scored["dominant_dir"] != 0) & scored["fwd_5d"].notna()
    df = scored[mask].copy()
    if df.empty:
        return pd.DataFrame()

    n = len(df)

    # ── Predicted fields ──────────────────────────────────────────────────────
    df["predicted_rank"]      = df["ml_rank"].astype(float)
    df["predicted_prob"]      = df["ml_prob"].astype(float)
    df["predicted_direction"] = df["dominant_dir"].astype(int)
    # Estimated return: rank-deviation scaled to historical mean
    df["predicted_return"]    = (df["ml_rank"].astype(float) - 0.5) * 0.02

    # ── Actual outcomes ───────────────────────────────────────────────────────
    df["actual_return_5d"]  = df["fwd_5d"].astype(float)
    df["actual_return_10d"] = df.get("fwd_10d", pd.Series(np.nan, index=df.index)).astype(float)
    df["actual_return_20d"] = df.get("fwd_20d", pd.Series(np.nan, index=df.index)).astype(float)

    # ── Direction correct ──────────────────────────────────────────────────────
    dir_arr = df["dominant_dir"].to_numpy(dtype=int)
    for col, fwd_col in [("direction_correct_5d", "actual_return_5d"),
                          ("direction_correct_10d", "actual_return_10d"),
                          ("direction_correct_20d", "actual_return_20d")]:
        fwd = df[fwd_col].to_numpy(dtype=float)
        df[col] = np.where(
            np.isnan(fwd), None,
            (dir_arr * fwd > 0).astype(object),
        )

    # ── Cross-sectional quintile ranks (per prediction_date) ──────────────────
    df["rank_quintile"]    = np.nan
    df["outcome_quintile"] = np.nan
    df["rank_hit"]         = np.nan

    for d, grp in df.groupby("date"):
        idx = grp.index
        df.loc[idx, "rank_quintile"]    = _quintile_rank(grp["predicted_rank"])
        df.loc[idx, "outcome_quintile"] = _quintile_rank(grp["actual_return_5d"])

    # rank_hit: top predicted rank AND top-2 actual quintile
    df["rank_hit"] = (
        (df["rank_quintile"] == 5) & (df["outcome_quintile"] >= 4)
    ).where(df["rank_quintile"].notna() & df["outcome_quintile"].notna())

    # ── Context columns ──────────────────────────────────────────────────────
    jarvis_raw = df.get("jarvis_quality_adjusted", pd.Series(np.nan, index=df.index))
    df["jarvis_green"] = np.where(jarvis_raw.isna(), None,
                                  (jarvis_raw > 0).astype(object))

    qt_raw = df.get("quality_tier", pd.Series(np.nan, index=df.index))
    df["quality_tier_out"] = qt_raw.where(qt_raw.notna()).astype("Int64")

    sma200_raw = df.get("above_sma200", pd.Series(np.nan, index=df.index))
    df["above_sma200_out"] = np.where(sma200_raw.isna(), None,
                                       (sma200_raw > 0.5).astype(object))

    df["sector_regime"] = df["market_regime"]   # bull / bear / range

    rv20 = df.get("realized_vol_20", pd.Series(np.nan, index=df.index)).to_numpy(float)
    df["vix_regime"] = np.where(np.isnan(rv20), "unknown", _vix_regime(rv20))

    df["model_version"]       = MODEL_VERSION
    df["feature_set_version"] = FEAT_VERSION
    df["ml_signal_strength"]  = df["ml_str"].astype(float)

    return df


# ── DB upsert ─────────────────────────────────────────────────────────────────

def upsert_outcomes(df: pd.DataFrame, engine) -> int:
    """Upsert rows to prediction_outcomes. Returns count inserted/updated."""
    from sqlalchemy import text

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "ticker":               str(r["ticker"]),
            "prediction_date":      r["date"],
            "model_version":        r.get("model_version", MODEL_VERSION),
            "feature_set_version":  r.get("feature_set_version", FEAT_VERSION),
            "predicted_rank":       _f(r.get("predicted_rank")),
            "predicted_prob":       _f(r.get("predicted_prob")),
            "predicted_return":     _f(r.get("predicted_return")),
            "predicted_direction":  _i(r.get("predicted_direction")),
            "actual_return_5d":     _f(r.get("actual_return_5d")),
            "actual_return_10d":    _f(r.get("actual_return_10d")),
            "actual_return_20d":    _f(r.get("actual_return_20d")),
            "direction_correct_5d": _b(r.get("direction_correct_5d")),
            "direction_correct_10d":_b(r.get("direction_correct_10d")),
            "direction_correct_20d":_b(r.get("direction_correct_20d")),
            "rank_quintile":        _i(r.get("rank_quintile")),
            "outcome_quintile":     _i(r.get("outcome_quintile")),
            "rank_hit":             _b(r.get("rank_hit")),
            "jarvis_green":         _b(r.get("jarvis_green")),
            "quality_tier":         _i(r.get("quality_tier_out")),
            "above_sma200":         _b(r.get("above_sma200_out")),
            "sector_regime":        r.get("sector_regime") or None,
            "vix_regime":           r.get("vix_regime") or None,
            "confluence_score":     _f(r.get("confluence_score")),
            "conviction_level":     r.get("conviction_level") or None,
            "ml_signal_strength":   _f(r.get("ml_signal_strength")),
        })

    if not rows:
        return 0

    sql = text("""
        INSERT INTO prediction_outcomes (
            ticker, prediction_date, model_version, feature_set_version,
            predicted_rank, predicted_prob, predicted_return, predicted_direction,
            actual_return_5d, actual_return_10d, actual_return_20d,
            direction_correct_5d, direction_correct_10d, direction_correct_20d,
            rank_quintile, outcome_quintile, rank_hit,
            jarvis_green, quality_tier, above_sma200,
            sector_regime, vix_regime,
            confluence_score, conviction_level, ml_signal_strength
        ) VALUES (
            :ticker, :prediction_date, :model_version, :feature_set_version,
            :predicted_rank, :predicted_prob, :predicted_return, :predicted_direction,
            :actual_return_5d, :actual_return_10d, :actual_return_20d,
            :direction_correct_5d, :direction_correct_10d, :direction_correct_20d,
            :rank_quintile, :outcome_quintile, :rank_hit,
            :jarvis_green, :quality_tier, :above_sma200,
            :sector_regime, :vix_regime,
            :confluence_score, :conviction_level, :ml_signal_strength
        )
        ON CONFLICT (ticker, prediction_date, model_version) DO UPDATE SET
            feature_set_version  = EXCLUDED.feature_set_version,
            predicted_rank       = EXCLUDED.predicted_rank,
            predicted_prob       = EXCLUDED.predicted_prob,
            predicted_return     = EXCLUDED.predicted_return,
            predicted_direction  = EXCLUDED.predicted_direction,
            actual_return_5d     = EXCLUDED.actual_return_5d,
            actual_return_10d    = EXCLUDED.actual_return_10d,
            actual_return_20d    = EXCLUDED.actual_return_20d,
            direction_correct_5d = EXCLUDED.direction_correct_5d,
            direction_correct_10d= EXCLUDED.direction_correct_10d,
            direction_correct_20d= EXCLUDED.direction_correct_20d,
            rank_quintile        = EXCLUDED.rank_quintile,
            outcome_quintile     = EXCLUDED.outcome_quintile,
            rank_hit             = EXCLUDED.rank_hit,
            jarvis_green         = EXCLUDED.jarvis_green,
            quality_tier         = EXCLUDED.quality_tier,
            above_sma200         = EXCLUDED.above_sma200,
            sector_regime        = EXCLUDED.sector_regime,
            vix_regime           = EXCLUDED.vix_regime,
            confluence_score     = EXCLUDED.confluence_score,
            conviction_level     = EXCLUDED.conviction_level,
            ml_signal_strength   = EXCLUDED.ml_signal_strength
    """)

    with engine.begin() as conn:
        for i in range(0, len(rows), BATCH_SIZE):
            conn.execute(sql, rows[i:i + BATCH_SIZE])

    return len(rows)


def _f(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _b(v):
    if v is None:
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date",   default=str(date.today()))
    parser.add_argument("--dry-run",    action="store_true",
                        help="Score and compute but do not write to DB")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date   = date.fromisoformat(args.end_date)

    print("\nAtlas Prediction Outcomes — Compute")
    print(f"Period: {start_date} to {end_date}")
    print("-" * 60)

    print("Loading DB stats and models...")
    pattern_stats, calib_stats, regime_stats = load_static_stats()
    model_map   = build_model_map(Path(MODEL_DIR))
    parquet_dir = Path(PARQUET_OUTPUT_DIR)

    print("Scoring all parquet dates (extended)...")
    scored = load_and_score_extended(
        start_date, end_date, parquet_dir, model_map,
        pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("No scored rows. Aborting.")
        return 1
    print(f"  Scored rows: {len(scored):,}")

    print("Computing forward returns (5d / 10d / 20d)...")
    scored = compute_forward_returns(scored)
    scored = add_conviction(scored)

    # Count mature vs immature predictions
    has_5d  = scored["fwd_5d"].notna()
    has_10d = scored.get("fwd_10d", pd.Series(False, index=scored.index)).notna()
    has_20d = scored.get("fwd_20d", pd.Series(False, index=scored.index)).notna()
    directional = (scored["dominant_dir"] != 0)

    mature  = (directional & has_5d).sum()
    immature = (directional & ~has_5d).sum()
    print(f"  Mature predictions (5d resolved, directional): {mature:,}")
    print(f"  Skipped (no 5d label yet): {immature:,}")

    print("Building outcome rows...")
    outcomes = build_outcomes(scored)
    print(f"  Outcome rows built: {len(outcomes):,}")

    if outcomes.empty:
        print("No outcomes to write.")
        return 0

    # Summary stats
    dir5 = outcomes["direction_correct_5d"].dropna()
    dir10 = outcomes["direction_correct_10d"].dropna()
    dir20 = outcomes["direction_correct_20d"].dropna()
    rank_hit = outcomes["rank_hit"].dropna()

    print(f"\n--- Summary ---")
    print(f"  5d accuracy:    {dir5.mean():.3f}  (n={len(dir5):,})")
    print(f"  10d accuracy:   {dir10.mean():.3f}  (n={len(dir10):,})")
    print(f"  20d accuracy:   {dir20.mean():.3f}  (n={len(dir20):,})")
    print(f"  Rank hit rate:  {rank_hit.mean():.3f}  (n={len(rank_hit):,})")

    if args.dry_run:
        print("\nDry run — no DB writes.")
        return 0

    print("\nConnecting to DB and upserting...")
    import os
    from sqlalchemy import create_engine
    engine = create_engine(os.environ["DATABASE_URL"])

    n_written = upsert_outcomes(outcomes, engine)
    print(f"  Upserted: {n_written:,} rows")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
