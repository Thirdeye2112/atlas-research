"""
Atlas Behavior Analysis - Step 1: Seed Behavior Definitions
=============================================================
Seeds behavior_definitions with 20 named daily-bar market behaviors.
Safe to re-run: uses INSERT ... ON CONFLICT DO UPDATE.

Usage:
    python scripts/python/seed_behaviors.py
"""

from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BEHAVIORS = [
    # ── GAP behaviors ──────────────────────────────────────────────────────────
    {
        "behavior_id":    "GAP_UP_LARGE",
        "description":    "Price gapped up more than 2% from prior close at open",
        "category":       "gap",
        "direction":      "long",
        "parameter_json": {"min_gap_pct": 2.0},
    },
    {
        "behavior_id":    "GAP_UP_SMALL",
        "description":    "Price gapped up 0.5-2% from prior close at open",
        "category":       "gap",
        "direction":      "long",
        "parameter_json": {"min_gap_pct": 0.5, "max_gap_pct": 2.0},
    },
    {
        "behavior_id":    "GAP_DOWN_LARGE",
        "description":    "Price gapped down more than 2% from prior close at open",
        "category":       "gap",
        "direction":      "short",
        "parameter_json": {"min_gap_pct": 2.0},
    },
    {
        "behavior_id":    "GAP_DOWN_SMALL",
        "description":    "Price gapped down 0.5-2% from prior close at open",
        "category":       "gap",
        "direction":      "short",
        "parameter_json": {"min_gap_pct": 0.5, "max_gap_pct": 2.0},
    },
    # ── TREND behaviors ───────────────────────────────────────────────────────
    {
        "behavior_id":    "ABOVE_ALL_EMAS",
        "description":    "Price closed above EMA20, EMA50, and EMA200 -- strong uptrend alignment",
        "category":       "trend",
        "direction":      "long",
        "parameter_json": {},
    },
    {
        "behavior_id":    "BELOW_ALL_EMAS",
        "description":    "Price closed below EMA20, EMA50, and EMA200 -- strong downtrend alignment",
        "category":       "trend",
        "direction":      "short",
        "parameter_json": {},
    },
    {
        "behavior_id":    "GOLDEN_CROSS",
        "description":    "EMA50 crossed above EMA200 today (bullish long-term signal)",
        "category":       "trend",
        "direction":      "long",
        "parameter_json": {},
    },
    {
        "behavior_id":    "DEATH_CROSS",
        "description":    "EMA50 crossed below EMA200 today (bearish long-term signal)",
        "category":       "trend",
        "direction":      "short",
        "parameter_json": {},
    },
    {
        "behavior_id":    "NEAR_52W_HIGH",
        "description":    "Price within 3% of 52-week high (52 x 5 trading days)",
        "category":       "trend",
        "direction":      "long",
        "parameter_json": {"within_pct": 3.0},
    },
    {
        "behavior_id":    "INSIDE_DAY",
        "description":    "Todays range fully contained within prior days range (consolidation)",
        "category":       "trend",
        "direction":      "neutral",
        "parameter_json": {},
    },
    # ── MOMENTUM behaviors ────────────────────────────────────────────────────
    {
        "behavior_id":    "RSI_OVERSOLD_RECLAIM",
        "description":    "RSI was below 30 in the last 3 days and closed back above 40 today",
        "category":       "momentum",
        "direction":      "long",
        "parameter_json": {"oversold": 30, "reclaim": 40, "lookback": 3},
    },
    {
        "behavior_id":    "RSI_OVERBOUGHT",
        "description":    "RSI above 70 for 2+ consecutive days (extended momentum)",
        "category":       "momentum",
        "direction":      "short",
        "parameter_json": {"threshold": 70, "min_days": 2},
    },
    {
        "behavior_id":    "MACD_BULL_CROSS",
        "description":    "MACD line crossed above signal line today (12/26/9 settings)",
        "category":       "momentum",
        "direction":      "long",
        "parameter_json": {"fast": 12, "slow": 26, "signal": 9},
    },
    {
        "behavior_id":    "MACD_BEAR_CROSS",
        "description":    "MACD line crossed below signal line today (12/26/9 settings)",
        "category":       "momentum",
        "direction":      "short",
        "parameter_json": {"fast": 12, "slow": 26, "signal": 9},
    },
    # ── VOLUME behaviors ──────────────────────────────────────────────────────
    {
        "behavior_id":    "VOL_SURGE_BULL",
        "description":    "Volume > 2.5x 20-day average AND close > open (accumulation signal)",
        "category":       "volume",
        "direction":      "long",
        "parameter_json": {"vol_ratio": 2.5},
    },
    {
        "behavior_id":    "VOL_SURGE_BEAR",
        "description":    "Volume > 2.5x 20-day average AND close < open (distribution signal)",
        "category":       "volume",
        "direction":      "short",
        "parameter_json": {"vol_ratio": 2.5},
    },
    {
        "behavior_id":    "LOW_VOL_DRIFT_UP",
        "description":    "Price up >0.5% on volume below 70% of 20-day average (quiet grind)",
        "category":       "volume",
        "direction":      "neutral",
        "parameter_json": {"min_return": 0.5, "max_vol_ratio": 0.7},
    },
    # ── VOLATILITY behaviors ──────────────────────────────────────────────────
    {
        "behavior_id":    "ATR_SQUEEZE",
        "description":    "ATR(14) below 70% of its 20-day average (volatility compression)",
        "category":       "volatility",
        "direction":      "neutral",
        "parameter_json": {"atr_pct": 0.70},
    },
    {
        "behavior_id":    "ATR_EXPANSION",
        "description":    "ATR(14) above 150% of its 20-day average (volatility expansion)",
        "category":       "volatility",
        "direction":      "neutral",
        "parameter_json": {"atr_pct": 1.50},
    },
    {
        "behavior_id":    "LARGE_DAILY_RANGE",
        "description":    "Intraday range > 3% (high - low > 3% of open) -- heightened activity",
        "category":       "volatility",
        "direction":      "neutral",
        "parameter_json": {"min_range_pct": 3.0},
    },
]


def seed(engine) -> int:
    sql = text("""
        INSERT INTO behavior_definitions (behavior_id, description, category, direction, parameter_json, active)
        VALUES (:behavior_id, :description, :category, :direction, CAST(:parameter_json AS jsonb), :active)
        ON CONFLICT (behavior_id) DO UPDATE SET
            description    = EXCLUDED.description,
            category       = EXCLUDED.category,
            direction      = EXCLUDED.direction,
            parameter_json = EXCLUDED.parameter_json,
            active         = EXCLUDED.active
    """)
    rows = [
        {**b, "parameter_json": json.dumps(b["parameter_json"]), "active": True}
        for b in BEHAVIORS
    ]
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    n = seed(engine)
    print(f"Seeded {n} behavior definitions.")
    # Print summary table
    from tabulate import tabulate
    table = [[b["behavior_id"], b["category"], b["direction"], b["description"][:60]]
             for b in BEHAVIORS]
    print(tabulate(table, headers=["ID", "Category", "Dir", "Description"]))


if __name__ == "__main__":
    main()
