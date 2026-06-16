"""
Atlas Intraday Candidate Watchlist Updater
==========================================
Runs nightly after ingest_intraday_5m.py. Computes walk-forward metrics
for every (setup_type, direction) pair and writes a snapshot to
intraday_candidate_setups with status: collecting / candidate / promoted / rejected.

Status rules (no auto-promotion, analysis only):
  collecting  -- IS n < MIN_SAMPLE_SIZE  (not enough data)
  candidate   -- IS thresholds mostly met but OOS insufficient or borderline
  promoted    -- all IS + OOS thresholds met (still requires manual review)
  rejected    -- OOS expectancy < -0.05% or OOS PF < 0.90 with n >= 30

Usage:
    python scripts/update_intraday_candidates.py
    python scripts/update_intraday_candidates.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

# Promotion thresholds (must match run_intraday_walkforward.py)
MIN_SAMPLE_SIZE   = 30
MIN_WIN_RATE      = 0.50
MIN_EXPECTANCY    = 0.10
MIN_PF            = 1.20
OOS_MIN_N         = 10
OOS_MIN_WR        = 0.47
OOS_MIN_EXP       = 0.05
OOS_MIN_PF        = 1.10
SLIPPAGE_PCT      = 0.05
REJECTION_EXP     = -0.05
REJECTION_PF      = 0.90

ANALYSIS_HORIZON  = 6   # 30 min


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pf(returns: np.ndarray) -> float:
    wins   = float(returns[returns > 0].sum())
    losses = float(abs(returns[returns <= 0].sum()))
    if losses == 0:
        return 5.0 if wins > 0 else 1.0
    return min(5.0, wins / losses)


def compute_metrics(returns: np.ndarray) -> dict:
    r = returns - SLIPPAGE_PCT
    n = len(r)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0, max_dd=0.0)
    cumulative  = np.cumsum(r)
    running_max = np.maximum.accumulate(cumulative)
    dd          = float((running_max - cumulative).max()) if len(cumulative) else 0.0
    return dict(
        n    = n,
        wr   = float((r > 0).mean()),
        exp  = float(np.mean(r)),
        pf   = _pf(r),
        max_dd = dd,
    )


def assign_status(is_m: dict, oos_m: dict) -> tuple[str, str]:
    """Returns (status, notes)."""
    if is_m["n"] < MIN_SAMPLE_SIZE:
        pct = is_m["n"] / MIN_SAMPLE_SIZE * 100
        return "collecting", f"IS n={is_m['n']}/{MIN_SAMPLE_SIZE} ({pct:.0f}% to threshold)"

    is_fails = []
    if is_m["wr"]  < MIN_WIN_RATE:   is_fails.append(f"WR {is_m['wr']:.1%}<{MIN_WIN_RATE:.0%}")
    if is_m["exp"] < MIN_EXPECTANCY: is_fails.append(f"Exp {is_m['exp']:+.2f}%<{MIN_EXPECTANCY}%")
    if is_m["pf"]  < MIN_PF:         is_fails.append(f"PF {is_m['pf']:.2f}<{MIN_PF}")

    if oos_m["n"] >= OOS_MIN_N:
        if oos_m["exp"] < REJECTION_EXP and oos_m["pf"] < REJECTION_PF:
            return "rejected", f"OOS exp={oos_m['exp']:+.2f}%, PF={oos_m['pf']:.2f} (negative performance)"

    oos_fails = []
    if oos_m["n"] < OOS_MIN_N:   oos_fails.append(f"OOS n={oos_m['n']}<{OOS_MIN_N}")
    if oos_m.get("wr", 0) < OOS_MIN_WR:  oos_fails.append(f"OOS WR {oos_m.get('wr',0):.1%}<{OOS_MIN_WR:.0%}")
    if oos_m.get("exp", -9) < OOS_MIN_EXP: oos_fails.append(f"OOS Exp {oos_m.get('exp',0):+.2f}%<{OOS_MIN_EXP}%")
    if oos_m.get("pf", 0) < OOS_MIN_PF:   oos_fails.append(f"OOS PF {oos_m.get('pf',0):.2f}<{OOS_MIN_PF}")

    all_fails = is_fails + oos_fails
    if not all_fails:
        return "promoted", "all thresholds met"
    if not is_fails:
        return "candidate", "IS ok; OOS: " + ", ".join(oos_fails)
    return "collecting", "IS: " + ", ".join(is_fails)


def best_context_slice(grp: pd.DataFrame, returns: np.ndarray) -> tuple[str | None, float | None]:
    """Find which daily context slice has the best expectancy."""
    best_label, best_exp = None, -999.0
    for col in ["daily_conviction", "daily_regime"]:
        if col not in grp.columns:
            continue
        for val in grp[col].dropna().unique():
            mask = (grp[col] == val).values
            r    = returns[mask] - SLIPPAGE_PCT
            if len(r) < 10:
                continue
            exp = float(np.mean(r))
            if exp > best_exp:
                best_exp   = exp
                best_label = f"{col}={val}"
    return best_label, (best_exp if best_label else None)


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def load_outcomes(engine, horizon: int) -> pd.DataFrame:
    sql = f"""
    SELECT
        s.setup_type,
        s.direction,
        s.ts,
        s.daily_conviction,
        s.daily_regime,
        o.future_return
    FROM intraday_setups s
    JOIN intraday_outcomes o ON o.setup_id = s.setup_id AND o.horizon_bars = {horizon}
    WHERE o.future_return IS NOT NULL
    ORDER BY s.ts
    """
    df = pd.read_sql(sql, engine, parse_dates=["ts"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def days_of_data(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    span = (df["ts"].max() - df["ts"].min()).days
    return max(0, int(span))


def compute_candidates(df: pd.DataFrame, as_of: date) -> list[dict]:
    rows = []
    for (st, direction), grp in df.groupby(["setup_type", "direction"]):
        grp     = grp.sort_values("ts")
        returns = grp["future_return"].values.astype(float)
        n_total = len(returns)

        split_idx = int(n_total * 0.70)
        is_r      = returns[:split_idx]
        oos_r     = returns[split_idx:]

        is_m  = compute_metrics(is_r)
        oos_m = compute_metrics(oos_r)
        status, notes = assign_status(is_m, oos_m)

        best_ctx_label, best_ctx_exp = best_context_slice(grp, returns)
        last_seen = grp["ts"].max().date() if not grp.empty else None

        rows.append({
            "setup_type":         st,
            "direction":          direction,
            "timeframe":          "5m",
            "as_of_date":         as_of,
            "sample_size":        is_m["n"],
            "win_rate":           is_m["wr"],
            "expectancy":         is_m["exp"],
            "profit_factor":      is_m["pf"],
            "max_drawdown":       is_m["max_dd"],
            "oos_sample_size":    oos_m["n"],
            "oos_win_rate":       oos_m["wr"],
            "oos_expectancy":     oos_m["exp"],
            "oos_profit_factor":  oos_m["pf"],
            "best_context_label": best_ctx_label,
            "best_context_exp":   best_ctx_exp,
            "last_seen":          last_seen,
            "days_collected":     days_of_data(grp),
            "status":             status,
            "notes":              notes[:200],
        })

    return rows


def upsert_candidates(rows: list[dict], engine) -> int:
    sql = text("""
    INSERT INTO intraday_candidate_setups
        (setup_type, direction, timeframe, as_of_date, sample_size, win_rate,
         expectancy, profit_factor, max_drawdown, oos_sample_size, oos_win_rate,
         oos_expectancy, oos_profit_factor, best_context_label, best_context_exp,
         last_seen, days_collected, status, notes)
    VALUES
        (:setup_type, :direction, :timeframe, :as_of_date, :sample_size, :win_rate,
         :expectancy, :profit_factor, :max_drawdown, :oos_sample_size, :oos_win_rate,
         :oos_expectancy, :oos_profit_factor, :best_context_label, :best_context_exp,
         :last_seen, :days_collected, :status, :notes)
    ON CONFLICT (setup_type, direction, timeframe, as_of_date) DO UPDATE SET
        sample_size        = EXCLUDED.sample_size,
        win_rate           = EXCLUDED.win_rate,
        expectancy         = EXCLUDED.expectancy,
        profit_factor      = EXCLUDED.profit_factor,
        max_drawdown       = EXCLUDED.max_drawdown,
        oos_sample_size    = EXCLUDED.oos_sample_size,
        oos_win_rate       = EXCLUDED.oos_win_rate,
        oos_expectancy     = EXCLUDED.oos_expectancy,
        oos_profit_factor  = EXCLUDED.oos_profit_factor,
        best_context_label = EXCLUDED.best_context_label,
        best_context_exp   = EXCLUDED.best_context_exp,
        last_seen          = EXCLUDED.last_seen,
        days_collected     = EXCLUDED.days_collected,
        status             = EXCLUDED.status,
        notes              = EXCLUDED.notes
    """)

    def _clean(v):
        if v is None:
            return None
        if isinstance(v, float) and v != v:
            return None
        return v

    clean_rows = [{k: _clean(v) for k, v in r.items()} for r in rows]
    with engine.begin() as conn:
        conn.execute(sql, clean_rows)
    return len(clean_rows)


# ---------------------------------------------------------------------------
# Entry point (also called from nightly pipeline)
# ---------------------------------------------------------------------------

def run_candidate_update(engine, as_of: date | None = None) -> dict:
    if as_of is None:
        as_of = date.today()

    df   = load_outcomes(engine, ANALYSIS_HORIZON)
    if df.empty:
        return {"status": "no_data", "rows": 0}

    rows = compute_candidates(df, as_of)
    n    = upsert_candidates(rows, engine)

    by_status: dict[str, int] = {}
    for r in rows:
        s = r["status"]
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "status":    "ok",
        "rows":      n,
        "by_status": by_status,
        "setups":    len(rows),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    as_of  = date.today()

    print("=== Atlas Intraday Candidate Updater ===")
    print(f"As-of: {as_of}")

    df = load_outcomes(engine, ANALYSIS_HORIZON)
    if df.empty:
        print("No outcome data -- run ingest_intraday_5m.py first.")
        return

    rows = compute_candidates(df, as_of)
    by_status: dict[str, int] = {}
    for r in rows:
        s = r["status"]
        by_status[s] = by_status.get(s, 0) + 1

    print(f"  {len(rows)} setup types evaluated")
    for s, n in sorted(by_status.items()):
        print(f"  {s}: {n}")

    if not args.dry_run:
        n = upsert_candidates(rows, engine)
        print(f"  -> {n} rows written to intraday_candidate_setups")
    else:
        print("  dry-run -- not written")

    # Print top candidates
    candidates = [r for r in rows if r["status"] in ("candidate", "promoted")]
    if candidates:
        print()
        print("Top candidates by OOS expectancy:")
        top = sorted(candidates, key=lambda r: r.get("oos_expectancy") or -9, reverse=True)[:10]
        for r in top:
            print(f"  [{r['status'].upper():10}] {r['setup_type']:<26} {r['direction']:<6} "
                  f"IS Exp={r['expectancy']:+.3f}%  OOS Exp={r['oos_expectancy']:+.3f}%  "
                  f"OOS PF={r['oos_profit_factor']:.2f}  n={r['sample_size']}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
