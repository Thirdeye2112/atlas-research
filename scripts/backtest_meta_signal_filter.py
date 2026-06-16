"""
Atlas Meta-Signal Engine v1 -- Historical Backtest
====================================================
Compares 6 prediction filter approaches using a look-ahead-free monthly
walk-forward methodology.

Methodology:
  For each calendar month M (starting 3 months after first trade):
    - Train window: all trades in [M - 60d, M)
    - Score window: trades in [M, M+1)
    - Compute rolling combo scores from train window
    - Apply each of 6 filters to score window
    - Aggregate monthly metrics

Filters:
  A: Baseline  -- all trades
  B: ML Q5     -- ml_signal_strength >= 0.8
  C: Conviction HIGH/VH  -- conviction in HIGH, VERY_HIGH
  D: Template  -- long-only, HIGH/VH, known regime, confluence >= 5
  E: Template + PROMOTED  -- Template + combo rolling status = PROMOTED
  F: Template + Meta Top20  -- Template + combo meta_score top 20% for that month

Does NOT modify model weights, signal generation, or live trading state.
"""

from __future__ import annotations

import os
import sys
import math
from datetime import date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.meta.combo_key import build_combo_key_vectorized


def get_engine():
    return create_engine(os.environ["DATABASE_URL"])

REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "reports", "META_SIGNAL_ENGINE_REPORT.md")

META_PF_CAP      = 5.0
PROMOTED_MIN_N   = 30
PROMOTED_MIN_PF  = 1.5
PROMOTED_MIN_EXP = 0.0
PROMOTED_MIN_WR  = 0.50
CANDIDATE_MIN_N  = 15
CANDIDATE_MIN_PF = 1.2


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(engine) -> pd.DataFrame:
    sql = """
    SELECT
        ticker, entry_date, return_pct,
        conviction_level, sector_regime, vix_regime,
        quality_tier, ml_signal_strength, confluence_score,
        jarvis_green, predicted_direction, atr_pct,
        target1_hit, stop_hit
    FROM trade_attribution
    WHERE return_pct IS NOT NULL
    ORDER BY entry_date
    """
    df = pd.read_sql(sql, engine, parse_dates=["entry_date"])
    df["entry_date"] = pd.to_datetime(df["entry_date"]).dt.normalize()
    return df


# ---------------------------------------------------------------------------
# Break-even after T1 return simulation
# ---------------------------------------------------------------------------

ATR_STOP = 1.5

def sim_be_t1(df: pd.DataFrame) -> np.ndarray:
    atr = df["atr_pct"].fillna(0).clip(lower=0).values
    r5  = df["return_pct"].values
    t1h = df["target1_hit"].fillna(False).values.astype(bool)
    sth = df["stop_hit"].fillna(False).values.astype(bool)
    has = atr > 0
    ret = np.where(has & t1h,          np.maximum(0.0, r5),
          np.where(has & sth & ~t1h,   -atr * ATR_STOP, r5))
    return ret.astype(float)


# ---------------------------------------------------------------------------
# Rolling combo scoring (look-ahead free)
# ---------------------------------------------------------------------------

def _pf(returns: np.ndarray) -> float:
    wins   = float(returns[returns > 0].sum())
    losses = float(abs(returns[returns <= 0].sum()))
    if losses == 0:
        return META_PF_CAP if wins > 0 else 1.0
    return min(META_PF_CAP, wins / losses)


def compute_train_combo_scores(train: pd.DataFrame) -> pd.DataFrame:
    """Compute per-combo stats from the training window trades."""
    if len(train) == 0:
        return pd.DataFrame(columns=["combo_key", "n", "pf", "exp", "wr", "status", "meta_raw"])

    rows = []
    for key, g in train.groupby("combo_key"):
        r = g["return_pct"].values
        n = len(r)
        if n == 0:
            continue
        pf_v  = _pf(r)
        exp_v = float(np.mean(r))
        wr_v  = float((r > 0).mean())
        meta_raw = (min(META_PF_CAP, pf_v) * max(0, exp_v) * math.log2(n + 1)
                    if pf_v >= 1.0 and exp_v > 0 else 0.0)

        if n < CANDIDATE_MIN_N:
            status = "INSUFFICIENT"
        elif pf_v < 1.0 or exp_v <= 0:
            status = "REJECTED"
        elif (n >= PROMOTED_MIN_N and pf_v >= PROMOTED_MIN_PF
              and exp_v > PROMOTED_MIN_EXP and wr_v >= PROMOTED_MIN_WR):
            status = "PROMOTED"
        elif n >= CANDIDATE_MIN_N and pf_v >= CANDIDATE_MIN_PF and exp_v > 0:
            status = "CANDIDATE"
        else:
            status = "REJECTED"

        rows.append({"combo_key": key, "n": n, "pf": pf_v, "exp": exp_v,
                     "wr": wr_v, "status": status, "meta_raw": meta_raw})

    result = pd.DataFrame(rows)
    # normalize meta_raw to 0-100
    max_raw = result["meta_raw"].max()
    if max_raw > 0:
        result["meta_score"] = (result["meta_raw"] / max_raw * 100).round(2)
    else:
        result["meta_score"] = 0.0
    return result


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def metrics(returns: np.ndarray) -> dict:
    n = len(returns)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0, avg_win=0.0, avg_loss=0.0)
    wins   = returns[returns > 0]
    losses = returns[returns <= 0]
    return dict(
        n       = n,
        wr      = float((returns > 0).mean()),
        exp     = float(np.mean(returns)),
        pf      = _pf(returns),
        avg_win  = float(np.mean(wins))  if len(wins)   else 0.0,
        avg_loss = float(np.mean(losses)) if len(losses) else 0.0,
    )


# ---------------------------------------------------------------------------
# Walk-forward backtest
# ---------------------------------------------------------------------------

TEMPLATE_REGIMES = {"bull", "bear", "range"}

def template_mask(df: pd.DataFrame) -> pd.Series:
    return (
        (df["predicted_direction"] == 1) &
        df["conviction_level"].isin(["HIGH", "VERY_HIGH"]) &
        df["sector_regime"].isin(TEMPLATE_REGIMES) &
        (df["confluence_score"].fillna(0) >= 5)
    )


def run_backtest(df: pd.DataFrame) -> dict:
    """
    Monthly walk-forward backtest returning per-filter aggregated metrics.
    """
    df = df.copy()
    df = df.sort_values("entry_date").reset_index(drop=True)
    df["combo_key"] = build_combo_key_vectorized(df)

    # Compute BE-T1 return for every trade
    df["ret_be"] = sim_be_t1(df)

    min_date   = df["entry_date"].min()
    max_date   = df["entry_date"].max()
    # Start 3 months in to have meaningful training data
    start_month = min_date + pd.DateOffset(months=3)
    months = pd.date_range(start=start_month, end=max_date, freq="MS")

    filter_records = {label: [] for label in ["A", "B", "C", "D", "E", "F"]}
    monthly_rows   = []

    print(f"  Walk-forward: {len(months)} months  ({months[0].date()} -> {months[-1].date()})")

    for i, m_start in enumerate(months):
        m_end  = m_start + pd.DateOffset(months=1)
        train_start = m_start - pd.Timedelta(days=60)

        train = df[(df["entry_date"] >= train_start) & (df["entry_date"] < m_start)]
        test  = df[(df["entry_date"] >= m_start)     & (df["entry_date"] < m_end)]

        if len(test) == 0:
            continue

        combo_scores = compute_train_combo_scores(train)
        score_map    = dict(zip(combo_scores["combo_key"], combo_scores["status"]))
        meta_map     = dict(zip(combo_scores["combo_key"], combo_scores["meta_score"]))

        test = test.copy()
        test["combo_status_hist"] = test["combo_key"].map(score_map).fillna("INSUFFICIENT")
        test["combo_meta_hist"]   = test["combo_key"].map(meta_map).fillna(0.0)

        # Promoted combos set
        promoted_keys = set(combo_scores[combo_scores["status"] == "PROMOTED"]["combo_key"])

        # Meta top-20 threshold for this month
        meta_vals = combo_scores[combo_scores["meta_score"] > 0]["meta_score"]
        meta_thresh = meta_vals.quantile(0.80) if len(meta_vals) >= 5 else 0.0

        tmask = template_mask(test)

        filters = {
            "A": test,
            "B": test[test["ml_signal_strength"] >= 0.8],
            "C": test[test["conviction_level"].isin(["HIGH", "VERY_HIGH"])],
            "D": test[tmask],
            "E": test[tmask & test["combo_key"].isin(promoted_keys)],
            "F": test[tmask & (test["combo_meta_hist"] >= meta_thresh)],
        }

        month_row = {"month": m_start.date()}
        for label, subset in filters.items():
            if len(subset) == 0:
                m = dict(n=0, wr=0.0, exp=0.0, pf=0.0, avg_win=0.0, avg_loss=0.0)
            else:
                m = metrics(subset["ret_be"].values)
            month_row[f"{label}_n"]   = m["n"]
            month_row[f"{label}_exp"] = m["exp"]
            month_row[f"{label}_pf"]  = m["pf"]
            month_row[f"{label}_wr"]  = m["wr"]
            for r in subset["ret_be"].values:
                filter_records[label].append(r)

        monthly_rows.append(month_row)

        if (i + 1) % 12 == 0:
            print(f"    Processed {i+1}/{len(months)} months...")

    monthly_df = pd.DataFrame(monthly_rows)

    # Aggregate overall metrics per filter
    overall = {}
    for label in filter_records:
        r = np.array(filter_records[label], dtype=float)
        overall[label] = metrics(r)

    return {"overall": overall, "monthly": monthly_df}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

FILTER_NAMES = {
    "A": "All Predictions (Baseline)",
    "B": "ML Q5 Only (strength >= 0.8)",
    "C": "Conviction HIGH/VERY_HIGH",
    "D": "Trade Template (long+HIGH/VH+regime+conf)",
    "E": "Template + Combo PROMOTED",
    "F": "Template + Meta Top 20%",
}


def write_report(results: dict, as_of: str) -> str:
    overall  = results["overall"]
    monthly  = results["monthly"]

    lines = [
        "# Atlas Meta-Signal Engine Report v1",
        "",
        f"**Generated:** {as_of}",
        "**Status:** ANALYSIS ONLY. No live trades. No signals changed.",
        "",
        "## Overview",
        "",
        "Compares 6 prediction filter strategies using look-ahead-free monthly walk-forward scoring.",
        "Training window: 60 calendar days before each test month.",
        "Exit strategy: Break-Even After T1 (production template exit).",
        "",
        "## Filter Definitions",
        "",
    ]
    for lbl, name in FILTER_NAMES.items():
        lines.append(f"- **{lbl}:** {name}")

    lines += [
        "",
        "## Overall Backtest Results (Full Walk-Forward Period)",
        "",
        "| Filter | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser |",
        "|---|---|---|---|---|---|---|",
    ]
    for lbl in ["A", "B", "C", "D", "E", "F"]:
        m = overall[lbl]
        name = FILTER_NAMES[lbl]
        lines.append(
            f"| **{lbl}** {name} | {m['n']:,} | {m['wr']*100:.1f}% | "
            f"{m['exp']:+.3f}% | {m['pf']:.3f} | "
            f"{m['avg_win']:+.3f}% | {m['avg_loss']:+.3f}% |"
        )

    # vs baseline
    base_exp = overall["A"]["exp"]
    base_pf  = overall["A"]["pf"]
    lines += [
        "",
        "## Improvement vs Baseline (Filter A)",
        "",
        "| Filter | Exp Delta | PF Delta | N Reduction |",
        "|---|---|---|---|",
    ]
    base_n = overall["A"]["n"]
    for lbl in ["B", "C", "D", "E", "F"]:
        m = overall[lbl]
        exp_delta = m["exp"] - base_exp
        pf_delta  = m["pf"]  - base_pf
        n_pct     = (1 - m["n"] / base_n) * 100 if base_n > 0 else 0
        lines.append(
            f"| **{lbl}** | {exp_delta:+.3f}% | {pf_delta:+.3f} | "
            f"-{n_pct:.1f}% ({m['n']:,} trades) |"
        )

    # Monthly time series for key filters
    lines += [
        "",
        "## Monthly PF by Filter (Selective Months)",
        "",
        "_Full monthly table omitted for brevity. Shows first 24 and last 12 months._",
        "",
        "| Month | A PF | D PF | E PF | F PF | D n | E n | F n |",
        "|---|---|---|---|---|---|---|---|",
    ]
    show_rows = pd.concat([monthly.head(24), monthly.tail(12)]).drop_duplicates("month")
    for _, row in show_rows.iterrows():
        def _pf_fmt(v):
            return f"{float(v):.3f}" if not (v != v) and v is not None else "n/a"
        lines.append(
            f"| {row['month']} | {_pf_fmt(row.get('A_pf'))} | "
            f"{_pf_fmt(row.get('D_pf'))} | {_pf_fmt(row.get('E_pf'))} | "
            f"{_pf_fmt(row.get('F_pf'))} | "
            f"{int(row.get('D_n',0))} | {int(row.get('E_n',0))} | {int(row.get('F_n',0))} |"
        )

    # Monthly win-rate chart (text)
    lines += [
        "",
        "## Key Findings",
        "",
    ]

    e_m = overall["E"]
    f_m = overall["F"]
    d_m = overall["D"]

    best_filter = max(["D", "E", "F"], key=lambda x: overall[x]["exp"])
    best = overall[best_filter]

    lines += [
        f"1. **Best single filter by expectancy:** Filter {best_filter} ({FILTER_NAMES[best_filter]})",
        f"   - Expectancy: {best['exp']:+.3f}%  PF: {best['pf']:.3f}  WR: {best['wr']*100:.1f}%",
        f"   - Trades: {best['n']:,} (vs baseline {base_n:,})",
        "",
        f"2. **Meta PROMOTED (E) vs Template (D):**",
        f"   - D: Exp={d_m['exp']:+.3f}%  PF={d_m['pf']:.3f}  n={d_m['n']:,}",
        f"   - E: Exp={e_m['exp']:+.3f}%  PF={e_m['pf']:.3f}  n={e_m['n']:,}",
        f"   - PROMOTED filter selects {e_m['n']/d_m['n']*100:.1f}% of template trades",
        "",
        f"3. **Meta Top-20% (F) vs Template (D):**",
        f"   - D: Exp={d_m['exp']:+.3f}%  PF={d_m['pf']:.3f}",
        f"   - F: Exp={f_m['exp']:+.3f}%  PF={f_m['pf']:.3f}  n={f_m['n']:,}",
        "",
        "## Recommendation",
        "",
    ]

    # Determine recommendation
    if e_m["exp"] > d_m["exp"] and e_m["pf"] > d_m["pf"] and e_m["n"] >= 1000:
        lines += [
            "**DEPLOY META FILTER E (PROMOTED)** as an additional gate on production signals.",
            "",
            f"PROMOTED filter improves expectancy from {d_m['exp']:+.3f}% to {e_m['exp']:+.3f}% "
            f"({e_m['exp']-d_m['exp']:+.3f}%) with {e_m['n']:,} qualifying trades.",
            "",
            "**Proposed gate:** Surface a prediction in BotLab only if:",
            "1. Passes production template (filter D)",
            "2. combo_status = PROMOTED or CANDIDATE in latest signal_combination_scores",
            "",
            "**Still needs:** 30+ days live validation before suppressing non-PROMOTED predictions.",
        ]
    elif f_m["exp"] > d_m["exp"] and f_m["pf"] > d_m["pf"] and f_m["n"] >= 1000:
        lines += [
            "**DEPLOY META FILTER F (TOP 20% META SCORE)** as an additional gate.",
            "",
            f"Top-20% meta-score filter improves expectancy from {d_m['exp']:+.3f}% to "
            f"{f_m['exp']:+.3f}% ({f_m['exp']-d_m['exp']:+.3f}%).",
        ]
    else:
        lines += [
            "**RETAIN TEMPLATE ONLY (filter D) for now.** Meta filters do not show consistent ",
            "improvement in this backtest. Attach meta scores to predictions for monitoring, ",
            "but do not suppress signals based on combo_status yet.",
            "",
            "**Next step:** Run 90 days live, then re-evaluate whether PROMOTED combos outperform.",
        ]

    lines += [
        "",
        "## Implementation Notes",
        "",
        "- Meta scores are updated nightly by `compute_signal_combination_scores.py`",
        "- Scores are attached to predictions via the nightly pipeline meta-tagging step",
        "- BotLab displays current combo status and meta score per prediction",
        "- Status tiers: PROMOTED (n>=30, PF>=1.5, WR>=50%, exp>0) | CANDIDATE (n>=15, PF>=1.2)",
        "  | REJECTED (PF<1.0 or exp<=0) | INSUFFICIENT (n<15)",
        "",
        "---",
        f"_Generated by backtest_meta_signal_filter.py on {as_of}_",
    ]

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    return REPORT_PATH


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    from datetime import datetime
    as_of = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("=== Atlas Meta-Signal Engine -- Historical Backtest ===")
    print(f"As-of: {as_of}")
    print("ANALYSIS ONLY -- no live trading state modified")
    print()

    engine = get_engine()

    print("[1/3] Loading trade_attribution...")
    df = load_data(engine)
    print(f"  Loaded {len(df):,} trades  ({df['entry_date'].min().date()} -> {df['entry_date'].max().date()})")

    print("[2/3] Running walk-forward backtest (6 filters x monthly)...")
    results = run_backtest(df)

    print("[3/3] Writing META_SIGNAL_ENGINE_REPORT.md...")
    path = write_report(results, as_of)
    print(f"  -> {path}")

    print("\n=== Overall Results ===")
    for lbl in ["A", "B", "C", "D", "E", "F"]:
        m = results["overall"][lbl]
        name = FILTER_NAMES[lbl][:40]
        print(f"  {lbl} {name:<42}  n={m['n']:>7,}  Exp={m['exp']:+.3f}%  PF={m['pf']:.3f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
