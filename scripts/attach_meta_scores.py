"""
Atlas Meta-Signal Engine v1 -- Meta Score Tagger
==================================================
Attaches combo_key, meta_score, and combo_status to today's predictions.

Approach:
  1. Load today's predictions (from predictions table)
  2. Get most recent context per ticker from prediction_outcomes
  3. Compute combo_key for each prediction
  4. Look up meta score from latest signal_combination_scores
  5. UPDATE predictions table with combo columns

Run AFTER predict (Step 10) and AFTER compute_signal_combination_scores (Step 16.5).
Called nightly from nightly_pipeline.py as Step 10.5 (uses yesterday's combo scores).

Does NOT modify model weights, signal generation, or live trading state.
"""

from __future__ import annotations

import os
import sys
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.meta.combo_key import build_combo_key_vectorized


def get_engine():
    return create_engine(os.environ["DATABASE_URL"])


def load_todays_predictions(pred_date: date, engine) -> pd.DataFrame:
    sql = """
    SELECT ticker, date
    FROM predictions
    WHERE date = %(d)s
    """
    return pd.read_sql(sql, engine, params={"d": pred_date})


def load_ticker_context(engine) -> pd.DataFrame:
    """Most recent context per ticker from prediction_outcomes."""
    sql = """
    SELECT DISTINCT ON (ticker)
        ticker,
        conviction_level,
        sector_regime,
        vix_regime,
        quality_tier,
        ml_signal_strength,
        confluence_score,
        jarvis_green
    FROM prediction_outcomes
    ORDER BY ticker, prediction_date DESC
    """
    return pd.read_sql(sql, engine)


def load_latest_combo_scores(engine) -> pd.DataFrame:
    """Latest signal combination scores (most recent scored_date per combo_key)."""
    sql = """
    SELECT DISTINCT ON (combo_key)
        combo_key,
        meta_score,
        status      AS combo_status,
        pf_60d      AS combo_pf_60d,
        expectancy_60d AS combo_expectancy_60d,
        n_60d       AS combo_sample_size
    FROM signal_combination_scores
    ORDER BY combo_key, scored_date DESC
    """
    return pd.read_sql(sql, engine)


def attach_meta_scores(pred_date: date, engine, dry_run: bool = False) -> int:
    """
    Attach meta scores to predictions for pred_date.
    Returns number of predictions updated.
    """
    preds = load_todays_predictions(pred_date, engine)
    if preds.empty:
        print(f"  No predictions for {pred_date}")
        return 0

    context = load_ticker_context(engine)
    if context.empty:
        print("  No prediction_outcomes context available — skipping meta-tagging")
        return 0

    combo_scores = load_latest_combo_scores(engine)
    if combo_scores.empty:
        print("  No signal_combination_scores available — skipping meta-tagging")
        return 0

    # Merge predictions with context
    merged = preds.merge(context, on="ticker", how="left")

    # Build combo_key
    merged["combo_key"] = build_combo_key_vectorized(merged)

    # Join meta scores
    merged = merged.merge(combo_scores, on="combo_key", how="left")

    if dry_run:
        n_tagged = int(merged["meta_score"].notna().sum())
        print(f"  [dry-run] Would update {len(merged):,} predictions, "
              f"{n_tagged:,} with valid combo scores")
        return n_tagged

    # Update predictions table
    update_sql = text("""
    UPDATE predictions SET
        combo_key             = :combo_key,
        meta_score            = :meta_score,
        combo_status          = :combo_status,
        combo_pf_60d          = :combo_pf_60d,
        combo_expectancy_60d  = :combo_expectancy_60d,
        combo_sample_size     = :combo_sample_size
    WHERE ticker = :ticker AND date = :date
    """)

    rows = []
    for _, row in merged.iterrows():
        def _sf(v):
            import math
            if v is None:
                return None
            try:
                f = float(v)
                return None if math.isnan(f) else f
            except (TypeError, ValueError):
                return None

        def _ss(v):  # NaN/empty-safe string (a float NaN is truthy, so `or None` fails)
            if v is None:
                return None
            if isinstance(v, float):
                import math
                if math.isnan(v):
                    return None
            s = str(v).strip()
            return s if s and s.lower() != "nan" else None

        _css = _sf(row.get("combo_sample_size"))  # _sf maps NaN/None -> None
        rows.append({
            "ticker":               row["ticker"],
            "date":                 row["date"],
            "combo_key":            _ss(row.get("combo_key")),
            "meta_score":           _sf(row.get("meta_score")),
            "combo_status":         _ss(row.get("combo_status")),
            "combo_pf_60d":         _sf(row.get("combo_pf_60d")),
            "combo_expectancy_60d": _sf(row.get("combo_expectancy_60d")),
            "combo_sample_size":    int(_css) if _css is not None else None,
        })

    BATCH = 500
    total = 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        with engine.begin() as conn:
            for r in batch:
                conn.execute(update_sql, r)
        total += len(batch)

    return total


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    pred_date = date.fromisoformat(args.date) if args.date else date.today()

    print("=== Atlas Meta-Signal Engine -- Score Tagger ===")
    print(f"Prediction date: {pred_date}  dry_run={args.dry_run}")
    print("ANALYSIS ONLY -- no live trading state modified")
    print()

    engine = get_engine()

    print("[1/1] Attaching meta scores to predictions...")
    n = attach_meta_scores(pred_date, engine, dry_run=args.dry_run)
    print(f"  Updated {n:,} predictions")
    print("\nDone.")


if __name__ == "__main__":
    main()
