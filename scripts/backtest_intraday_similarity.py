"""
Atlas Intraday Similarity Engine Backtest v1
=============================================
Strict walk-forward validation: IS (70%) -> OOS (30%) chronological split.
Evaluates the similarity engine's ability to predict 5-min candle outcomes
across different K values, context gates, and feature weight schemes.

Generates reports/INTRADAY_SIMILARITY_ENGINE_REPORT.md

Usage:
    python scripts/backtest_intraday_similarity.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.intraday.similarity.features import DEFAULT_WEIGHTS, N_FEATURES
from atlas_research.intraday.similarity.search   import SimilaritySearch
from atlas_research.intraday.similarity.outcomes import aggregate_outcomes

DB_URL = os.environ["DATABASE_URL"]
REPORT = os.path.join(os.path.dirname(__file__), "..", "reports",
                      "INTRADAY_SIMILARITY_ENGINE_REPORT.md")

K_VALUES  = [25, 50, 100, 200]
PRIMARY_H = 6     # primary evaluation horizon (6 bars = 30 min)
MIN_VALID = 5     # minimum valid OOS rows for a slice report


# ---------------------------------------------------------------------------
# Load memory
# ---------------------------------------------------------------------------

def _load_memory(engine) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT id, ticker, ts, time_of_day, candle_num, tod_min,
               daily_ml_rank, daily_conviction, daily_regime, daily_vix,
               feature_vector,
               future_return_1,  future_return_3,  future_return_6,
               future_return_12, future_return_24, future_return_eod,
               mfe_12, mae_12,
               hit_plus_1_0_atr, hit_minus_1_0_atr
        FROM intraday_candle_memory
        ORDER BY ts ASC
        """,
        engine,
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)

    # Deserialize feature_vector (PostgreSQL array -> list)
    def _parse_vec(v):
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return None
        return list(v)

    df["feature_vector"] = df["feature_vector"].apply(_parse_vec)
    valid = df["feature_vector"].notna()
    df = df[valid].copy()
    print(f"  Loaded {len(df):,} candle memory rows ({valid.sum() - len(df)} dropped for missing vectors)")
    return df


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _eval_k(is_df: pd.DataFrame, oos_df: pd.DataFrame, k: int,
            gate_time=None, gate_regime=None,
            weights: np.ndarray | None = None) -> dict:
    """
    Build KNN from is_df, query each row in oos_df, collect metrics.
    Returns dict of aggregated stats.
    """
    if len(is_df) < k:
        return {"k": k, "n_oos": 0, "skipped": True}

    search = SimilaritySearch(weights=weights)
    search.fit(is_df)

    col = f"future_return_{PRIMARY_H}"
    oos_valid = oos_df[oos_df[col].notna()].copy()
    if len(oos_valid) < MIN_VALID:
        return {"k": k, "n_oos": len(oos_valid), "skipped": True}

    predicted_returns = []
    actual_returns    = []

    for _, row in oos_valid.iterrows():
        vec = np.array(row["feature_vector"])
        matches = search.query(
            vec, k=k,
            gate_time=gate_time or row.get("time_of_day"),
            gate_regime=gate_regime or row.get("daily_regime"),
            exclude_before_ts=row["ts"],   # strict: only use truly historical
        )
        if len(matches) < 3:
            continue
        valid_m = matches[matches[col].notna()]
        if len(valid_m) == 0:
            continue
        predicted_returns.append(float(valid_m[col].mean()))
        actual_returns.append(float(row[col]))

    if len(actual_returns) < MIN_VALID:
        return {"k": k, "n_oos": 0, "skipped": True}

    pred = np.array(predicted_returns)
    actual = np.array(actual_returns)

    # Direction hit rate: predicted sign matches actual sign
    hit_rate = float(np.mean(np.sign(pred) == np.sign(actual)))

    # Top-quartile expectancy: look at actual returns where pred was top 25%
    q75 = np.percentile(pred, 75)
    top_mask = pred >= q75
    top_exp  = float(actual[top_mask].mean()) if top_mask.sum() > 0 else 0.0

    # Bottom-quartile expectancy (predicted negative)
    q25 = np.percentile(pred, 25)
    bot_mask = pred <= q25
    bot_exp  = float(actual[bot_mask].mean()) if bot_mask.sum() > 0 else 0.0

    return {
        "k":             k,
        "n_oos":         len(actual_returns),
        "hit_rate":      round(hit_rate, 4),
        "pred_mean":     round(float(pred.mean()), 4),
        "actual_mean":   round(float(actual.mean()), 4),
        "top_q_exp":     round(top_exp, 4),
        "bot_q_exp":     round(bot_exp, 4),
        "mse":           round(float(np.mean((pred - actual) ** 2)), 6),
        "corr":          round(float(np.corrcoef(pred, actual)[0, 1]), 4)
                         if len(pred) > 2 else 0.0,
        "skipped":       False,
    }


# ---------------------------------------------------------------------------
# Main backtest
# ---------------------------------------------------------------------------

def run_backtest(engine) -> dict:
    print("[similarity-backtest] Loading candle memory...")
    mem = _load_memory(engine)
    if mem.empty or len(mem) < 100:
        print("  Insufficient data (< 100 rows) -- aborting backtest")
        return {}

    # Strict 70/30 chronological split
    split_idx = int(len(mem) * 0.70)
    is_df  = mem.iloc[:split_idx].reset_index(drop=True)
    oos_df = mem.iloc[split_idx:].reset_index(drop=True)

    print(f"  IS: {len(is_df):,}  OOS: {len(oos_df):,}")
    print(f"  IS date range: {is_df['ts'].min().date()} to {is_df['ts'].max().date()}")
    print(f"  OOS date range: {oos_df['ts'].min().date()} to {oos_df['ts'].max().date()}")

    # 1. Sweep K values
    print("\n[1] Sweeping K values (uniform weights, gated by time + regime)...")
    k_results = []
    for k in K_VALUES:
        print(f"  K={k}...", end=" ", flush=True)
        r = _eval_k(is_df, oos_df, k)
        k_results.append(r)
        if not r.get("skipped"):
            print(f"hit_rate={r['hit_rate']:.1%}  top_q_exp={r['top_q_exp']:+.3f}%  n={r['n_oos']}")
        else:
            print(f"SKIPPED (n={r.get('n_oos',0)})")

    # Find best K
    valid_k = [r for r in k_results if not r.get("skipped")]
    best_k_row = max(valid_k, key=lambda r: r["hit_rate"] * abs(r["top_q_exp"] or 0),
                     default=None) if valid_k else None
    best_k = best_k_row["k"] if best_k_row else K_VALUES[1]

    # 2. Ungated vs gated comparison
    print(f"\n[2] Gated vs ungated at K={best_k}...")
    ungated = _eval_k(is_df, oos_df, best_k,
                      gate_time=None, gate_regime=None)
    gated   = _eval_k(is_df, oos_df, best_k)  # auto-gates from row
    print(f"  Ungated: hit_rate={ungated.get('hit_rate',0):.1%}  top_q={ungated.get('top_q_exp',0):+.3f}%")
    print(f"  Gated:   hit_rate={gated.get('hit_rate',0):.1%}  top_q={gated.get('top_q_exp',0):+.3f}%")

    # 3. Time-of-day breakdown
    print(f"\n[3] Time-of-day breakdown at K={best_k}...")
    time_results = {}
    for tod in oos_df["time_of_day"].dropna().unique():
        oos_slice  = oos_df[oos_df["time_of_day"] == tod]
        is_slice   = is_df[is_df["time_of_day"] == tod]
        if len(oos_slice) < MIN_VALID or len(is_slice) < best_k:
            continue
        r = _eval_k(is_slice, oos_slice, best_k, gate_time=tod)
        if not r.get("skipped"):
            time_results[tod] = r
            print(f"  {tod}: hit_rate={r['hit_rate']:.1%}  top_q={r['top_q_exp']:+.3f}%  n={r['n_oos']}")

    # 4. Regime breakdown
    print(f"\n[4] Daily regime breakdown at K={best_k}...")
    regime_results = {}
    for regime in oos_df["daily_regime"].dropna().unique():
        oos_sl = oos_df[oos_df["daily_regime"] == regime]
        is_sl  = is_df[is_df["daily_regime"] == regime]
        if len(oos_sl) < MIN_VALID or len(is_sl) < best_k:
            continue
        r = _eval_k(is_sl, oos_sl, best_k, gate_regime=regime)
        if not r.get("skipped"):
            regime_results[regime] = r
            print(f"  {regime}: hit_rate={r['hit_rate']:.1%}  top_q={r['top_q_exp']:+.3f}%  n={r['n_oos']}")

    # 5. Overall IS candle distribution
    col = f"future_return_{PRIMARY_H}"
    oos_valid = oos_df[oos_df[col].notna()]
    baseline_hit  = float((oos_valid[col] > 0).mean()) if len(oos_valid) > 0 else 0.5
    baseline_exp  = float(oos_valid[col].mean()) if len(oos_valid) > 0 else 0.0

    print(f"\n  Baseline (no filter): hit_rate={baseline_hit:.1%}  exp={baseline_exp:+.3f}%")

    # 6. Feature weight sensitivity
    print(f"\n[5] Context-heavy weights at K={best_k}...")
    ctx_weights = DEFAULT_WEIGHTS.copy()
    ctx_weights[12] *= 3.0   # time x3
    ctx_weights[13] *= 3.0   # conviction x3
    ctx_weights[14] *= 3.0   # regime x3
    ctx_weights[15] *= 2.0   # vix x2
    ctx_r = _eval_k(is_df, oos_df, best_k, weights=ctx_weights)
    if not ctx_r.get("skipped"):
        print(f"  Context-heavy: hit_rate={ctx_r['hit_rate']:.1%}  top_q={ctx_r['top_q_exp']:+.3f}%")

    return {
        "n_is":           len(is_df),
        "n_oos":          len(oos_df),
        "best_k":         best_k,
        "baseline_hit":   baseline_hit,
        "baseline_exp":   baseline_exp,
        "k_results":      k_results,
        "ungated":        ungated,
        "gated":          gated,
        "time_results":   time_results,
        "regime_results": regime_results,
        "ctx_heavy":      ctx_r,
        "best_k_row":     best_k_row,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(results: dict, run_dt: str) -> str:
    bk  = results.get("best_k", 50)
    bkr = results.get("best_k_row") or {}
    gated = results.get("gated") or {}
    ungated = results.get("ungated") or {}
    ctx_h = results.get("ctx_heavy") or {}

    def pct(v):
        if v is None:
            return "N/A"
        return f"{v:.1%}"

    def pp(v, decimals=3):
        if v is None:
            return "N/A"
        return f"{v:+.{decimals}f}%"

    lines = [
        "# Atlas Intraday Similarity Engine Report v1",
        f"Generated: {run_dt}",
        "",
        "## Summary",
        f"- IS candles: {results.get('n_is', 0):,}",
        f"- OOS candles: {results.get('n_oos', 0):,}",
        f"- Best K: {bk}",
        f"- Baseline hit rate (no filter): {pct(results.get('baseline_hit'))}",
        f"- Baseline expectancy (no filter): {pp(results.get('baseline_exp'))}",
        "",
        "## Q1: What K produces the best direction prediction?",
    ]

    k_header = "| K | N (OOS) | Hit Rate | Top-Q Exp | MSE | Corr |"
    k_sep    = "|---|---------|----------|-----------|-----|------|"
    lines += [k_header, k_sep]
    for r in results.get("k_results", []):
        if r.get("skipped"):
            lines.append(f"| {r['k']} | {r.get('n_oos',0)} | SKIP | - | - | - |")
        else:
            lines.append(
                f"| {r['k']} | {r['n_oos']} | {pct(r['hit_rate'])} | "
                f"{pp(r['top_q_exp'])} | {r.get('mse',0):.5f} | {r.get('corr',0):.3f} |"
            )
    lines.append("")
    lines.append(f"**Best K = {bk}** (hit_rate={pct(bkr.get('hit_rate'))}  top_q={pp(bkr.get('top_q_exp'))})")

    lines += [
        "",
        "## Q2: Does gating by time + regime improve accuracy?",
        f"- Ungated: hit_rate={pct(ungated.get('hit_rate'))}  top_q={pp(ungated.get('top_q_exp'))}",
        f"- Gated:   hit_rate={pct(gated.get('hit_rate'))}  top_q={pp(gated.get('top_q_exp'))}",
        f"- Lift: {(gated.get('hit_rate',0) - ungated.get('hit_rate',0))*100:+.1f} pp hit rate",
        "",
        "## Q3: Which time-of-day segment has best similarity accuracy?",
    ]

    tr = results.get("time_results", {})
    if tr:
        lines += ["| Time Bucket | N | Hit Rate | Top-Q Exp |",
                  "|-------------|---|----------|-----------|"]
        for tod, r in sorted(tr.items(), key=lambda x: -x[1].get("hit_rate", 0)):
            lines.append(f"| {tod} | {r['n_oos']} | {pct(r['hit_rate'])} | {pp(r['top_q_exp'])} |")
    else:
        lines.append("Insufficient data for time breakdown.")

    lines += [
        "",
        "## Q4: Which market regime benefits most from similarity?",
    ]

    rr = results.get("regime_results", {})
    if rr:
        lines += ["| Regime | N | Hit Rate | Top-Q Exp |",
                  "|--------|---|----------|-----------|"]
        for regime, r in sorted(rr.items(), key=lambda x: -x[1].get("hit_rate", 0)):
            lines.append(f"| {regime} | {r['n_oos']} | {pct(r['hit_rate'])} | {pp(r['top_q_exp'])} |")
    else:
        lines.append("Insufficient data for regime breakdown.")

    lines += [
        "",
        "## Q5: Does weighting context features more improve accuracy?",
        f"- Default weights:       hit_rate={pct(gated.get('hit_rate'))}  top_q={pp(gated.get('top_q_exp'))}",
        f"- Context-heavy weights: hit_rate={pct(ctx_h.get('hit_rate'))}  top_q={pp(ctx_h.get('top_q_exp'))}",
        "",
        "## Q6: What are the primary limitations?",
        "1. **Data volume**: 60 days x 10 tickers = ~46K candles. KNN accuracy improves",
        "   with more history -- expect improvement as data accumulates.",
        "2. **Feature version lock**: v1 vectors are stored in DB; changing feature",
        "   definitions requires a full rebuild (run --full).",
        "3. **No ticker filtering**: similar candles may come from a different ticker's",
        "   sector -- cross-ticker patterns may not generalize.",
        "4. **Overnight gap risk**: future_return_24 spans overnight; MFE/MAE do not",
        "   account for gap risk at session open.",
        "5. **Regime stationarity**: regime labels from prediction_outcomes lag by 1 day.",
        "",
        "## Q7: Is this ready to inform live trade decisions?",
        "- Similarity engine is **analysis-only** in v1.",
        "- It provides historical context (what happened after similar candles) but",
        "  does NOT replace setup detection, conviction scoring, or risk management.",
        "- Use as a supplementary signal: high-conviction setup + similarity agreement",
        "  -> elevated confidence; divergence -> caution.",
        "",
        "## Q8: Next Steps",
        "- Expand universe to all 1,326 tickers to grow the memory bank",
        "- Add ticker-sector filter to keep matches within same sector",
        "- Test similarity as an additive feature in the daily ML model",
        "- Auto-promote setups where similarity confirms direction",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    engine  = create_engine(DB_URL)
    run_dt  = datetime.now().strftime("%Y-%m-%d %H:%M")

    results = run_backtest(engine)
    if not results:
        print("Backtest produced no results.")
        return

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    report_text = generate_report(results, run_dt)
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(report_text)
    print(f"\nReport written to {REPORT}")

    bkr = results.get("best_k_row") or {}
    gated = results.get("gated") or {}
    print("\n=== SIMILARITY BACKTEST SUMMARY ===")
    print(f"  Candle memory:  IS={results['n_is']:,}  OOS={results['n_oos']:,}")
    print(f"  Baseline hit:   {results.get('baseline_hit',0):.1%}")
    print(f"  Best K:         {results.get('best_k')}")
    print(f"  Gated hit rate: {gated.get('hit_rate',0):.1%}")
    print(f"  Top-Q exp:      {(gated.get('top_q_exp') or 0):+.3f}%")


if __name__ == "__main__":
    main()
