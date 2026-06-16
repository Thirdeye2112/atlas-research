"""
Build intraday_behavior_events and market_behavior_concepts
============================================================
Step 1 of the behavior-aware similarity v2 pipeline.

  1. Seeds market_behavior_concepts from behavior_definitions
     (adds intraday_weight and feature_index).
  2. Syncs intraday_behavior_events from detected_behaviors
     (fast bridge table for candle-to-behavior lookup).

Usage:
    python scripts/build_intraday_behavior_events.py
    python scripts/build_intraday_behavior_events.py --since 2026-01-01
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Intraday relevance weights per category
# Gap/volume behaviors are highly intraday-relevant; cross events less so
_CAT_WEIGHTS = {
    "gap":        2.0,
    "volume":     2.0,
    "volatility": 1.75,
    "trend":      1.5,
    "momentum":   1.5,
}

# Alphabetical sort determines feature_index (must match features_v2.py BEHAVIOR_IDS)
_SORTED_BEHAVIOR_IDS = sorted([
    "ABOVE_ALL_EMAS", "ATR_EXPANSION", "ATR_SQUEEZE", "BELOW_ALL_EMAS",
    "DEATH_CROSS", "GAP_DOWN_LARGE", "GAP_DOWN_SMALL", "GAP_UP_LARGE",
    "GAP_UP_SMALL", "GOLDEN_CROSS", "INSIDE_DAY", "LARGE_DAILY_RANGE",
    "LOW_VOL_DRIFT_UP", "MACD_BEAR_CROSS", "MACD_BULL_CROSS",
    "NEAR_52W_HIGH", "RSI_OVERBOUGHT", "RSI_OVERSOLD_RECLAIM",
    "VOL_SURGE_BEAR", "VOL_SURGE_BULL",
])


def seed_market_behavior_concepts(engine) -> int:
    """Upsert market_behavior_concepts from behavior_definitions."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT behavior_id, category, direction, description, active "
            "FROM behavior_definitions ORDER BY behavior_id"
        )).fetchall()

    if not rows:
        print("  No behavior_definitions found.")
        return 0

    concepts = []
    for idx, bid in enumerate(_SORTED_BEHAVIOR_IDS):
        match = next((r for r in rows if r[0] == bid), None)
        if match is None:
            continue
        cat = match[1]
        concepts.append({
            "behavior_id":         bid,
            "category":            cat,
            "direction":           match[2],
            "description":         match[3],
            "intraday_weight":     _CAT_WEIGHTS.get(cat, 1.5),
            "is_daily_persistent": True,
            "feature_index":       idx,
            "active":              bool(match[4]),
        })

    sql = text("""
        INSERT INTO market_behavior_concepts (
            behavior_id, category, direction, description,
            intraday_weight, is_daily_persistent, feature_index, active
        ) VALUES (
            :behavior_id, :category, :direction, :description,
            :intraday_weight, :is_daily_persistent, :feature_index, :active
        )
        ON CONFLICT (behavior_id) DO UPDATE SET
            intraday_weight     = EXCLUDED.intraday_weight,
            feature_index       = EXCLUDED.feature_index,
            active              = EXCLUDED.active
    """)
    with engine.begin() as conn:
        conn.execute(sql, concepts)
    return len(concepts)


def sync_behavior_events(engine, since: date | None = None) -> int:
    """Sync detected_behaviors -> intraday_behavior_events."""
    where = ""
    params: dict = {}
    if since:
        where = "WHERE detection_date >= :since"
        params["since"] = since

    df = pd.read_sql(
        text(f"""
            SELECT ticker, detection_date, behavior_id, intensity
            FROM detected_behaviors {where}
            ORDER BY detection_date, ticker, behavior_id
        """),
        engine,
        params=params,
    )
    if df.empty:
        print("  No detections to sync.")
        return 0

    rows = [
        {
            "ticker":     r["ticker"],
            "event_date": r["detection_date"],
            "behavior_id": r["behavior_id"],
            "intensity":   float(r["intensity"]),
        }
        for _, r in df.iterrows()
    ]

    sql = text("""
        INSERT INTO intraday_behavior_events (ticker, event_date, behavior_id, intensity)
        VALUES (:ticker, :event_date, :behavior_id, :intensity)
        ON CONFLICT (ticker, event_date, behavior_id) DO UPDATE SET
            intensity = EXCLUDED.intensity
    """)
    BATCH = 2000
    total = 0
    with engine.begin() as conn:
        for start in range(0, len(rows), BATCH):
            conn.execute(sql, rows[start: start + BATCH])
            total += len(rows[start: start + BATCH])
    return total


def main():
    parser = argparse.ArgumentParser(description="Build intraday behavior event bridge table")
    parser.add_argument("--since", default=None,
                        help="Only sync events from this date (YYYY-MM-DD). Default: all.")
    args = parser.parse_args()

    since = date.fromisoformat(args.since) if args.since else None
    engine = create_engine(os.environ["DATABASE_URL"])

    print("Seeding market_behavior_concepts...")
    n_concepts = seed_market_behavior_concepts(engine)
    print(f"  {n_concepts} behavior concepts seeded/updated.")

    print(f"Syncing intraday_behavior_events{f' since {since}' if since else ''}...")
    n_events = sync_behavior_events(engine, since)
    print(f"  {n_events} events written.")

    # Summary
    with engine.connect() as conn:
        r = conn.execute(text(
            "SELECT COUNT(*), COUNT(DISTINCT ticker), MIN(event_date), MAX(event_date) "
            "FROM intraday_behavior_events"
        )).fetchone()
        print(f"\nintraday_behavior_events: {r[0]:,} rows, "
              f"{r[1]} tickers, {r[2]} to {r[3]}")


if __name__ == "__main__":
    main()
