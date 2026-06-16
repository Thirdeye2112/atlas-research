"""
Retrain Trigger Checker
========================
Checks 7 evidence-based triggers and prints a recommendation.

Triggers:
    1. Days since last training > STALE_DAYS (default: 30)
    2. Rolling 20d IC below IC_FLOOR threshold
    3. 3+ features newly unreliable vs last month
    4. Major regime change (market_trend flipped in last 5 days)
    5. >100 new tickers in universe since last training
    6. 30d prediction accuracy below baseline - ACCURACY_DROP_FLOOR
    7. Tier 3/4 or VIX high accuracy drag worsens vs 90d baseline

Default mode: print recommendation, do nothing.
--dry-run:       same as default (explicit)
--explain:       verbose per-trigger explanation
--auto-retrain:  actually invoke run_training.py if RETRAIN flag set

Usage:
    python scripts/check_retrain_needed.py --dry-run --explain
    python scripts/check_retrain_needed.py --auto-retrain
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

STALE_DAYS           = 30      # days since last train
IC_FLOOR             = 0.005   # rolling 20d IC below this = trigger
UNRELIABLE_THRESHOLD = 3       # features newly unreliable = trigger
NEW_TICKER_THRESHOLD = 100     # new tickers since last train = trigger
ACCURACY_DROP_FLOOR  = 0.02    # 30d accuracy drops > 2% below 90d baseline = trigger
TIER_DRAG_FLOOR      = 0.03    # Tier3/4 drag worsens > 3% vs 90d = trigger
RETRAIN_SCORE_NEEDED = 3       # triggers needed to recommend retrain


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _query(engine, sql: str, params=None) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params or {}).fetchall()
        return [dict(r._mapping) for r in rows]


# ---------------------------------------------------------------------------
# Trigger checks
# ---------------------------------------------------------------------------

def check_stale_model(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        SELECT training_end::text AS training_end, created_at::text AS created_at
        FROM model_registry
        ORDER BY created_at DESC
        LIMIT 1
    """)
    if not rows:
        return True, "No model in model_registry — retrain required"

    r = rows[0]
    training_end = r.get("training_end") or r.get("created_at")
    if training_end is None:
        return True, "Cannot determine last training date"

    last_train = date.fromisoformat(str(training_end)[:10])
    days_ago = (date.today() - last_train).days
    triggered = days_ago > STALE_DAYS
    reason = f"Last trained {days_ago}d ago ({last_train}) — threshold {STALE_DAYS}d"
    return triggered, reason


def check_rolling_ic(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        SELECT AVG(ic_30d) AS mean_ic_30d, COUNT(*) AS n
        FROM feature_reliability
        WHERE computed_date = (SELECT MAX(computed_date) FROM feature_reliability)
          AND ic_30d IS NOT NULL
          AND NOT insufficient_data
    """)
    if not rows or rows[0]["n"] == 0:
        return False, "No feature_reliability data available (run compute_feature_reliability.py first)"

    mean_ic = float(rows[0]["mean_ic_30d"] or 0)
    triggered = mean_ic < IC_FLOOR
    reason = f"Mean 30d IC = {mean_ic:.4f} — threshold {IC_FLOOR}"
    return triggered, reason


def check_unreliable_features(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        WITH latest AS (
            SELECT feature_name, unreliable
            FROM feature_reliability
            WHERE computed_date = (SELECT MAX(computed_date) FROM feature_reliability)
        ),
        month_ago AS (
            SELECT feature_name, unreliable
            FROM feature_reliability
            WHERE computed_date = (
                SELECT MAX(computed_date) FROM feature_reliability
                WHERE computed_date <= CURRENT_DATE - INTERVAL '25 days'
            )
        )
        SELECT
            l.feature_name,
            l.unreliable    AS now_unreliable,
            m.unreliable    AS was_unreliable
        FROM latest l
        LEFT JOIN month_ago m ON m.feature_name = l.feature_name
        WHERE l.unreliable = true
          AND (m.unreliable = false OR m.unreliable IS NULL)
    """)
    newly_unreliable = [r["feature_name"] for r in rows]
    n = len(newly_unreliable)
    triggered = n >= UNRELIABLE_THRESHOLD
    reason = (
        f"{n} features newly unreliable: {newly_unreliable[:5]}" if newly_unreliable
        else "No newly unreliable features"
    )
    return triggered, reason


def check_regime_change(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        SELECT
            feature_value,
            date::text AS date
        FROM feature_snapshots
        WHERE feature_name = 'market_trend'
          AND date >= CURRENT_DATE - INTERVAL '10 days'
          AND ticker = 'SPY'
        ORDER BY date DESC
        LIMIT 10
    """)
    if len(rows) < 5:
        return False, "Insufficient market_trend history for regime check"

    vals = [float(r["feature_value"] or 0) for r in rows]
    signs = [1 if v > 0 else (-1 if v < 0 else 0) for v in vals]
    recent_sign = signs[0]
    prior_signs = signs[3:8]

    had_flip = any(s != recent_sign and s != 0 for s in prior_signs if s != 0)
    triggered = had_flip
    reason = (
        f"Regime flip detected in last 10 days: current={recent_sign}, prior={prior_signs}"
        if had_flip
        else f"No regime flip (current market_trend sign: {recent_sign})"
    )
    return triggered, reason


def check_new_tickers(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        WITH last_train AS (
            SELECT training_end FROM model_registry ORDER BY created_at DESC LIMIT 1
        )
        SELECT COUNT(DISTINCT s.ticker) AS new_tickers
        FROM securities s
        CROSS JOIN last_train lt
        WHERE s.active = true
          AND s.created_at::date >= lt.training_end
    """)
    if not rows:
        return False, "Cannot determine new ticker count"
    n = int(rows[0]["new_tickers"] or 0)
    triggered = n >= NEW_TICKER_THRESHOLD
    reason = f"{n} new tickers added since last training — threshold {NEW_TICKER_THRESHOLD}"
    return triggered, reason


def check_accuracy_drop(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        SELECT
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND direction_correct_5d IS NOT NULL
            ) AS acc_30d,
            COUNT(*) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND direction_correct_5d IS NOT NULL
            ) AS n_30d,
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND prediction_date < CURRENT_DATE - INTERVAL '30 days'
                  AND direction_correct_5d IS NOT NULL
            ) AS acc_prior_90d,
            COUNT(*) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND prediction_date < CURRENT_DATE - INTERVAL '30 days'
                  AND direction_correct_5d IS NOT NULL
            ) AS n_prior
        FROM prediction_outcomes
    """)
    if not rows:
        return False, "No prediction_outcomes data"

    r = rows[0]
    acc_30  = r["acc_30d"]
    acc_90  = r["acc_prior_90d"]
    n_30    = r["n_30d"] or 0
    n_prior = r["n_prior"] or 0

    if acc_30 is None or n_30 < 500:
        return False, f"Insufficient recent outcomes (n={n_30}) — need 500+ to assess"
    if acc_90 is None:
        return False, "No prior 90d baseline available"

    acc_30  = float(acc_30)
    acc_90  = float(acc_90)
    drop    = acc_90 - acc_30
    triggered = drop > ACCURACY_DROP_FLOOR
    reason = (
        f"30d accuracy {acc_30:.3f} vs prior-90d {acc_90:.3f} — drop {drop:+.3f} "
        f"(threshold -{ACCURACY_DROP_FLOOR})"
    )
    return triggered, reason


def check_tier_drag_worsening(engine) -> tuple[bool, str]:
    rows = _query(engine, """
        SELECT
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND quality_tier >= 3
                  AND direction_correct_5d IS NOT NULL
            ) AS drag_30d,
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND prediction_date < CURRENT_DATE - INTERVAL '30 days'
                  AND quality_tier >= 3
                  AND direction_correct_5d IS NOT NULL
            ) AS drag_90d,
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '30 days'
                  AND vix_regime = 'high'
                  AND direction_correct_5d IS NOT NULL
            ) AS vix_drag_30d,
            AVG(direction_correct_5d::int) FILTER (
                WHERE prediction_date >= CURRENT_DATE - INTERVAL '90 days'
                  AND prediction_date < CURRENT_DATE - INTERVAL '30 days'
                  AND vix_regime = 'high'
                  AND direction_correct_5d IS NOT NULL
            ) AS vix_drag_90d
        FROM prediction_outcomes
    """)
    if not rows:
        return False, "No prediction_outcomes data"

    r = rows[0]
    msgs = []
    triggered = False

    if r["drag_30d"] is not None and r["drag_90d"] is not None:
        d30 = float(r["drag_30d"])
        d90 = float(r["drag_90d"])
        worsening = d90 - d30  # positive = getting worse
        if worsening > TIER_DRAG_FLOOR:
            triggered = True
            msgs.append(f"Tier3/4 accuracy fell {worsening:+.3f} (30d={d30:.3f}, prior-90d={d90:.3f})")

    if r["vix_drag_30d"] is not None and r["vix_drag_90d"] is not None:
        v30 = float(r["vix_drag_30d"])
        v90 = float(r["vix_drag_90d"])
        worsening = v90 - v30
        if worsening > TIER_DRAG_FLOOR:
            triggered = True
            msgs.append(f"VIX-high accuracy fell {worsening:+.3f} (30d={v30:.3f}, prior-90d={v90:.3f})")

    reason = "; ".join(msgs) if msgs else "Tier3/4 and VIX-high drag stable"
    return triggered, reason


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

TRIGGERS = [
    ("stale_model",         check_stale_model,          "Model not retrained in >30 days"),
    ("low_rolling_ic",      check_rolling_ic,            "Rolling 20d IC below threshold"),
    ("unreliable_features", check_unreliable_features,   "3+ features newly unreliable"),
    ("regime_change",       check_regime_change,         "Major market regime change"),
    ("new_tickers",         check_new_tickers,           "100+ new tickers since last train"),
    ("accuracy_drop",       check_accuracy_drop,         "30d accuracy drops >2% below 90d baseline"),
    ("tier_drag_worsening", check_tier_drag_worsening,   "Tier3/4 or VIX-high drag worsening"),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",      action="store_true", help="Print recommendation only (default)")
    parser.add_argument("--explain",      action="store_true", help="Print per-trigger explanation")
    parser.add_argument("--auto-retrain", action="store_true", help="Run training scripts if retrain needed")
    args = parser.parse_args()

    print(f"\nAtlas Retrain Checker — {date.today()}")
    print("-" * 60)

    engine = create_engine(os.environ["DATABASE_URL"])

    triggered_list = []
    results = []

    for name, fn, description in TRIGGERS:
        try:
            fired, reason = fn(engine)
        except Exception as exc:
            fired, reason = False, f"ERROR: {exc}"
        triggered_list.append(fired)
        results.append((name, description, fired, reason))

    n_triggered = sum(triggered_list)
    recommend_retrain = n_triggered >= RETRAIN_SCORE_NEEDED

    # Print results
    for name, description, fired, reason in results:
        status = "FIRED" if fired else "pass "
        print(f"  [{status}] {description}")
        if args.explain or fired:
            print(f"           {reason}")

    print()
    print(f"Triggers fired: {n_triggered} / {len(TRIGGERS)} (threshold: {RETRAIN_SCORE_NEEDED})")
    print()

    if recommend_retrain:
        print("RECOMMENDATION: RETRAIN NEEDED")
        fired_names = [r[0] for r in results if r[2]]
        print(f"  Reasons: {', '.join(fired_names)}")
    else:
        print("RECOMMENDATION: NO RETRAIN NEEDED")
        if n_triggered > 0:
            print(f"  Note: {n_triggered} trigger(s) fired but below threshold ({RETRAIN_SCORE_NEEDED})")

    # Auto-retrain
    if args.auto_retrain and recommend_retrain:
        print("\nAuto-retrain enabled — launching training pipeline...")
        scripts_dir = _ROOT / "scripts"
        for script in ["run_training.py"]:
            script_path = scripts_dir / script
            if script_path.exists():
                print(f"  Running: python {script_path}")
                ret = subprocess.call(
                    [sys.executable, str(script_path)],
                    cwd=str(_ROOT),
                )
                print(f"  Exit code: {ret}")
            else:
                print(f"  Script not found: {script_path}")
    elif args.auto_retrain and not recommend_retrain:
        print("\nAuto-retrain enabled but no retrain needed — skipping.")

    return 0 if not recommend_retrain else 1


if __name__ == "__main__":
    sys.exit(main())
