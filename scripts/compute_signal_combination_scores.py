"""
Atlas Meta-Signal Engine v1 -- Combo Scorer
============================================
Reads trade_attribution, computes rolling 30/60/90-day performance per
signal combination (combo_key), assigns meta scores and status labels,
then upserts to signal_combination_scores.

Usage:
    python scripts/compute_signal_combination_scores.py
    python scripts/compute_signal_combination_scores.py --date 2026-06-15
    python scripts/compute_signal_combination_scores.py --dry-run

Does NOT modify model weights, signal generation, or live trading state.
"""

from __future__ import annotations

import argparse
import math
import sys
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.meta.combo_key import build_combo_key_vectorized, parse_combo_key


def get_engine():
    return create_engine(os.environ["DATABASE_URL"])

ANALYSIS_ONLY = True  # never touches live trading


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WINDOWS = {"30d": 30, "60d": 60, "90d": 90}

# Status thresholds
PROMOTED_MIN_N   = 30
PROMOTED_MIN_PF  = 1.5
PROMOTED_MIN_WR  = 0.50   # baseline win rate
CANDIDATE_MIN_N  = 15
CANDIDATE_MIN_PF = 1.2

# meta_score raw formula: pf * max(0, expectancy) * log2(n+1)
META_PF_CAP = 5.0          # cap PF to avoid 999-PF combos dominating


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_trade_attribution(engine) -> pd.DataFrame:
    sql = """
    SELECT
        ticker,
        entry_date,
        return_pct,
        conviction_level,
        sector_regime,
        vix_regime,
        quality_tier,
        ml_signal_strength,
        confluence_score,
        jarvis_green,
        predicted_direction
    FROM trade_attribution
    WHERE return_pct IS NOT NULL
    """
    df = pd.read_sql(sql, engine, parse_dates=["entry_date"])
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.normalize()
    return df


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def compute_profit_factor(returns: np.ndarray) -> float:
    wins   = float(returns[returns > 0].sum())
    losses = float(abs(returns[returns <= 0].sum()))
    if losses == 0:
        return META_PF_CAP if wins > 0 else 1.0
    return min(META_PF_CAP, wins / losses)


def score_window(returns: np.ndarray) -> dict:
    n = len(returns)
    if n == 0:
        return dict(n=0, pf=None, expectancy=None, win_rate=None,
                    avg_winner=None, avg_loser=None)
    winners = returns[returns > 0]
    losers  = returns[returns <= 0]
    return dict(
        n          = n,
        pf         = compute_profit_factor(returns),
        expectancy = float(np.mean(returns)),
        win_rate   = float(len(winners) / n),
        avg_winner = float(np.mean(winners)) if len(winners) else None,
        avg_loser  = float(np.mean(losers))  if len(losers)  else None,
    )


def compute_meta_score(pf_60d, expectancy_60d, n_60d) -> float | None:
    if pf_60d is None or expectancy_60d is None or n_60d is None or n_60d == 0:
        return None
    if expectancy_60d <= 0:
        return 0.0
    raw = min(META_PF_CAP, float(pf_60d)) * float(expectancy_60d) * math.log2(float(n_60d) + 1)
    return raw   # normalized later against all combos


def assign_status(n_60d, pf_60d, expectancy_60d, win_rate_60d) -> str:
    if n_60d is None or n_60d < CANDIDATE_MIN_N:
        return "INSUFFICIENT"
    if pf_60d is None or expectancy_60d is None:
        return "INSUFFICIENT"
    if pf_60d < 1.0 or expectancy_60d <= 0:
        return "REJECTED"
    if (n_60d >= PROMOTED_MIN_N and pf_60d >= PROMOTED_MIN_PF
            and expectancy_60d > 0
            and (win_rate_60d or 0) >= PROMOTED_MIN_WR):
        return "PROMOTED"
    if n_60d >= CANDIDATE_MIN_N and pf_60d >= CANDIDATE_MIN_PF and expectancy_60d > 0:
        return "CANDIDATE"
    return "REJECTED"


# ---------------------------------------------------------------------------
# Main scoring
# ---------------------------------------------------------------------------

def compute_scores(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """
    For each combo_key, compute 30/60/90d rolling stats using trades
    where entry_date is in [as_of - window, as_of).
    """
    print(f"  Building combo keys for {len(df):,} trades...")
    df = df.copy()
    df["combo_key"] = build_combo_key_vectorized(df)

    cutoffs = {
        "30d": pd.Timestamp(as_of) - pd.Timedelta(days=30),
        "60d": pd.Timestamp(as_of) - pd.Timedelta(days=60),
        "90d": pd.Timestamp(as_of) - pd.Timedelta(days=90),
    }

    rows = []
    unique_keys = df["combo_key"].unique()
    print(f"  Unique combo keys: {len(unique_keys):,}")

    for key in unique_keys:
        g = df[df["combo_key"] == key]
        parsed = parse_combo_key(key)

        rec = {
            "combo_key":        key,
            "scored_date":      as_of,
            "conviction_level": parsed.get("conviction"),
            "sector_regime":    parsed.get("regime"),
            "vix_regime":       parsed.get("vix"),
            # decode tier: "T2" -> 2, "T_unk" -> None
            "quality_tier":     _decode_tier(parsed.get("tier")),
            "ml_rank_bucket":   parsed.get("ml"),
            "confluence_bucket": parsed.get("conf"),
            "jarvis_state":     parsed.get("jarvis"),
        }

        for w_label, cutoff_ts in cutoffs.items():
            window_trades = g[g["entry_date"] >= cutoff_ts]
            stats = score_window(window_trades["return_pct"].values)
            pfx   = w_label.replace("d", "")  # "30"
            rec[f"n_{w_label}"]          = stats["n"]
            rec[f"pf_{w_label}"]         = stats["pf"]
            rec[f"expectancy_{w_label}"] = stats["expectancy"]
            rec[f"win_rate_{w_label}"]   = stats["win_rate"]
            rec[f"avg_winner_{w_label}"] = stats["avg_winner"]
            rec[f"avg_loser_{w_label}"]  = stats["avg_loser"]

        rec["meta_score"] = compute_meta_score(
            rec["pf_60d"], rec["expectancy_60d"], rec["n_60d"]
        )
        rec["status"] = assign_status(
            rec["n_60d"], rec["pf_60d"], rec["expectancy_60d"], rec["win_rate_60d"]
        )
        rows.append(rec)

    result = pd.DataFrame(rows)

    # Normalize meta_score to 0-100
    raw_scores = result["meta_score"].dropna()
    if len(raw_scores) > 0:
        max_raw = raw_scores.max()
        if max_raw > 0:
            result["meta_score"] = (result["meta_score"] / max_raw * 100).round(2)

    return result


def _decode_tier(tier_str: str | None) -> int | None:
    if not tier_str:
        return None
    try:
        return int(tier_str.lstrip("T"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

UPSERT_COLS = [
    "combo_key", "scored_date",
    "conviction_level", "sector_regime", "vix_regime",
    "quality_tier", "ml_rank_bucket", "confluence_bucket", "jarvis_state",
    "n_30d", "pf_30d", "expectancy_30d", "win_rate_30d", "avg_winner_30d", "avg_loser_30d",
    "n_60d", "pf_60d", "expectancy_60d", "win_rate_60d", "avg_winner_60d", "avg_loser_60d",
    "n_90d", "pf_90d", "expectancy_90d", "win_rate_90d", "avg_winner_90d", "avg_loser_90d",
    "meta_score", "status",
]

INT_COLS = {"n_30d", "n_60d", "n_90d", "quality_tier"}


def upsert_scores(df: pd.DataFrame, engine, batch_size: int = 500) -> int:
    vals   = ", ".join([f":{c}" for c in UPSERT_COLS])
    update = ", ".join([
        f"{c} = EXCLUDED.{c}"
        for c in UPSERT_COLS
        if c not in ("combo_key", "scored_date")
    ])
    sql = text(f"""
    INSERT INTO signal_combination_scores ({', '.join(UPSERT_COLS)})
    VALUES ({vals})
    ON CONFLICT (combo_key, scored_date) DO UPDATE SET {update}
    """)

    records = df[UPSERT_COLS].to_dict(orient="records")
    cleaned = []
    for row in records:
        clean = {}
        for k, v in row.items():
            if isinstance(v, float) and v != v:
                clean[k] = None
            elif k in INT_COLS:
                clean[k] = None if v is None else int(v)
            elif hasattr(v, "item"):
                clean[k] = v.item()
            else:
                clean[k] = v
        cleaned.append(clean)

    total = 0
    for start in range(0, len(cleaned), batch_size):
        batch = cleaned[start:start + batch_size]
        with engine.begin() as conn:
            conn.execute(sql, batch)
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None,
                        help="Scoring date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute scores but do not write to DB")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date) if args.date else date.today()

    print("=== Atlas Meta-Signal Engine -- Combo Scorer ===")
    print(f"Scoring date: {as_of}  |  dry_run={args.dry_run}")
    print("ANALYSIS ONLY -- no live trading state modified")
    print()

    engine = get_engine()

    print("[1/4] Loading trade_attribution...")
    df = load_trade_attribution(engine)
    print(f"  Loaded {len(df):,} trades  ({df['entry_date'].min().date()} -> {df['entry_date'].max().date()})")

    print("[2/4] Computing combo scores...")
    scores_df = compute_scores(df, as_of)

    print(f"[3/4] Score summary ({len(scores_df):,} combos):")
    status_counts = scores_df["status"].value_counts()
    for s, c in status_counts.items():
        print(f"  {s:<15} {c:>5}")
    promoted = scores_df[scores_df["status"] == "PROMOTED"]
    if len(promoted):
        print(f"\n  Top 10 PROMOTED combos (by meta_score):")
        top = promoted.nlargest(10, "meta_score")[
            ["combo_key", "meta_score", "n_60d", "pf_60d", "expectancy_60d", "win_rate_60d"]
        ]
        for _, r in top.iterrows():
            wr = f"{r.win_rate_60d*100:.1f}%" if r.win_rate_60d else "n/a"
            print(f"    [{r.meta_score:5.1f}] n={r.n_60d:4d}  PF={r.pf_60d:.2f}  "
                  f"Exp={r.expectancy_60d:+.3f}%  WR={wr}  {r.combo_key}")

    if args.dry_run:
        print("\n[4/4] Dry run -- skipping upsert.")
    else:
        print("\n[4/4] Upserting to signal_combination_scores...")
        n = upsert_scores(scores_df, engine)
        print(f"  Upserted {n:,} rows")

    print("\nDone.")


if __name__ == "__main__":
    main()
