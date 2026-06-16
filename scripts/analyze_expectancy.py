#!/usr/bin/env python
"""
analyze_expectancy.py — Atlas Trade Attribution Engine v1, Parts 3–5.

Loads trade_attribution and computes:
  - Expectancy / win rate / profit factor by context slice
  - Component attribution: top/bottom 25 signal combinations
  - Exit study: 5d vs 10d vs 20d vs ATR-stop vs signal-flip

ANALYSIS ONLY. No trading. No signal changes. No model mutations.

Usage:
    python scripts/analyze_expectancy.py
    python scripts/analyze_expectancy.py --min-n 30
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
EXPECTANCY_REPORT = Path("reports/EXPECTANCY_REPORT.md")
EXIT_STUDY_REPORT = Path("reports/EXIT_STUDY_REPORT.md")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _metrics(series: pd.Series) -> dict:
    """Compute expectancy metrics for a return series (values in %)."""
    s = series.dropna()
    if len(s) < 5:
        return None
    wins   = s[s > 0]
    losses = s[s < 0]
    n      = len(s)
    wr     = len(wins) / n * 100
    exp    = s.mean()
    avg_w  = wins.mean()  if len(wins)  > 0 else 0.0
    avg_l  = losses.mean() if len(losses) > 0 else 0.0
    pf     = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    return {
        "n":         n,
        "win_rate":  round(wr, 1),
        "expectancy": round(exp, 3),
        "avg_winner": round(avg_w, 3),
        "avg_loser":  round(avg_l, 3),
        "profit_factor": round(pf, 3),
    }


def _fmt_row(label: str, m: dict) -> str:
    if m is None:
        return f"| {label} | — | — | — | — | — | — |"
    pf = f"{m['profit_factor']:.3f}" if m["profit_factor"] != np.inf else "∞"
    return (f"| {label} | {m['n']:,} | {m['win_rate']:.1f}% | "
            f"{m['expectancy']:+.3f}% | {m['avg_winner']:+.3f}% | "
            f"{m['avg_loser']:+.3f}% | {pf} |")


TABLE_HEADER = "| Context | N | Win Rate | Expectancy | Avg Winner | Avg Loser | Profit Factor |\n|---|---|---|---|---|---|---|"


# ──────────────────────────────────────────────────────────────────────────────
# Load
# ──────────────────────────────────────────────────────────────────────────────

def load_trades(engine) -> pd.DataFrame:
    sql = """
    SELECT
        ticker, entry_date, return_pct, return_pct_10d, return_pct_20d,
        max_favorable_excursion, max_adverse_excursion, profit_factor,
        stop_hit, target1_hit, target2_hit, target3_hit, signal_flip_exit,
        atr_stop_return_pct, atr_pct,
        prediction_rank, prediction_prob, calibrated_confidence,
        predicted_direction, jarvis_green, quality_tier,
        sector_regime, vix_regime, confluence_score, conviction_level,
        ml_signal_strength
    FROM trade_attribution
    WHERE return_pct IS NOT NULL
    ORDER BY entry_date
    """
    df = pd.read_sql(sql, engine, parse_dates=["entry_date"])
    print(f"  Loaded {len(df):,} trades from trade_attribution")
    return df


# ──────────────────────────────────────────────────────────────────────────────
# Context slicing
# ──────────────────────────────────────────────────────────────────────────────

def context_table(df: pd.DataFrame, col: str, values: list, labels: list = None) -> list[str]:
    rows = [TABLE_HEADER]
    labels = labels or [str(v) for v in values]
    for v, lbl in zip(values, labels):
        m = _metrics(df.loc[df[col] == v, "return_pct"])
        rows.append(_fmt_row(lbl, m))
    return rows


def bool_context_table(df: pd.DataFrame, col: str, label_true: str, label_false: str) -> list[str]:
    rows = [TABLE_HEADER]
    rows.append(_fmt_row(label_true,  _metrics(df.loc[df[col] == True,  "return_pct"])))
    rows.append(_fmt_row(label_false, _metrics(df.loc[df[col] == False, "return_pct"])))
    return rows


def confluence_bucket_table(df: pd.DataFrame) -> list[str]:
    rows = [TABLE_HEADER]
    buckets = [(0, 1, "0"), (1, 2, "1"), (2, 3, "2"), (3, 4, "3"), (4, 5, "4"), (5, 99, "5+")]
    for lo, hi, lbl in buckets:
        mask = (df["confluence_score"] >= lo) & (df["confluence_score"] < hi)
        m = _metrics(df.loc[mask, "return_pct"])
        rows.append(_fmt_row(f"Confluence = {lbl}", m))
    return rows


def ml_bucket_table(df: pd.DataFrame) -> list[str]:
    rows = [TABLE_HEADER]
    pcts = [0, 20, 40, 60, 80, 100]
    quantiles = np.nanpercentile(df["ml_signal_strength"].dropna(), pcts)
    labels = ["0–20%", "20–40%", "40–60%", "60–80%", "80–100%"]
    for i, lbl in enumerate(labels):
        mask = (df["ml_signal_strength"] >= quantiles[i]) & (df["ml_signal_strength"] < quantiles[i + 1])
        m = _metrics(df.loc[mask, "return_pct"])
        rows.append(_fmt_row(f"ML Strength {lbl}", m))
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Component attribution
# ──────────────────────────────────────────────────────────────────────────────

def build_combinations(df: pd.DataFrame, min_n: int = 50) -> pd.DataFrame:
    """All pairwise signal combination metrics sorted by expectancy."""
    df = df.copy()

    # Bucketed columns
    df["jarvis"] = df["jarvis_green"].map({True: "jarvis_green", False: "jarvis_red"})
    df["tier_label"] = df["quality_tier"].apply(lambda x: f"tier_{int(x)}" if pd.notna(x) else None)
    df["regime"] = df["sector_regime"]
    df["vix"] = df["vix_regime"]
    df["conf"] = df["confluence_score"].apply(
        lambda x: "conf>=3" if pd.notna(x) and x >= 3 else ("conf<3" if pd.notna(x) else None))
    df["conviction"] = df["conviction_level"]
    df["ml"] = df["ml_signal_strength"].apply(
        lambda x: f"ml_high" if pd.notna(x) and x >= 0.7 else ("ml_low" if pd.notna(x) and x < 0.4 else ("ml_mid" if pd.notna(x) else None)))

    factors = ["jarvis", "tier_label", "regime", "vix", "conf", "conviction", "ml"]
    combos = []
    for i, f1 in enumerate(factors):
        for j, f2 in enumerate(factors):
            if j <= i:
                continue
            grp_cols = [f1, f2]
            grouped = df.dropna(subset=grp_cols).groupby(grp_cols)["return_pct"].apply(list)
            for keys, rets in grouped.items():
                s = pd.Series(rets).dropna()
                if len(s) < min_n:
                    continue
                m = _metrics(s)
                if m is None:
                    continue
                combos.append({
                    "combination": f"{keys[0]} + {keys[1]}",
                    **m
                })

    if not combos:
        return pd.DataFrame()
    return pd.DataFrame(combos).sort_values("expectancy", ascending=False)


# ──────────────────────────────────────────────────────────────────────────────
# Exit study
# ──────────────────────────────────────────────────────────────────────────────

def _exit_metrics(df: pd.DataFrame, ret_col: str, label: str) -> dict:
    s = df[ret_col].dropna()
    if len(s) < 10:
        return {"label": label, "n": 0}
    wins   = s[s > 0]
    losses = s[s < 0]
    wr     = len(wins) / len(s) * 100
    exp    = s.mean()
    pf     = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    dd     = s.cumsum().cummax().sub(s.cumsum()).max() * -1
    return {
        "label": label,
        "n":     len(s),
        "win_rate": round(wr, 1),
        "expectancy": round(exp, 3),
        "profit_factor": round(pf, 3),
        "max_drawdown": round(float(dd), 2),
    }


def exit_study(df: pd.DataFrame) -> list[dict]:
    """Compare all exit strategies."""
    results = []

    # Base hold periods (from prediction_outcomes actual returns)
    results.append(_exit_metrics(df, "return_pct",      "5d Hold"))
    results.append(_exit_metrics(df, "return_pct_10d",  "10d Hold"))
    results.append(_exit_metrics(df, "return_pct_20d",  "20d Hold"))

    # ATR stop: if stop hit, use stop return; else use 5d return
    atr_df = df.copy()
    mask   = atr_df["stop_hit"] & atr_df["atr_stop_return_pct"].notna()
    atr_df["atr_exit_return"] = atr_df["return_pct"]
    atr_df.loc[mask, "atr_exit_return"] = atr_df.loc[mask, "atr_stop_return_pct"]
    results.append(_exit_metrics(atr_df, "atr_exit_return", "ATR Stop (1.5R) + 5d"))

    # Signal flip: use 5d return only for flipped trades
    flip = df[df["signal_flip_exit"] == True]
    noflip = df[df["signal_flip_exit"] == False]
    results.append(_exit_metrics(flip,   "return_pct", "5d Hold (signal-flipped)"))
    results.append(_exit_metrics(noflip, "return_pct", "5d Hold (no flip)"))

    # Target 1 hit: if T1 hit, cap return at +atr_pct; else 5d return
    t1_df = df.copy()
    t1_mask = t1_df["target1_hit"] & t1_df["atr_pct"].notna()
    t1_df["t1_exit_return"] = t1_df["return_pct"]
    t1_df.loc[t1_mask, "t1_exit_return"] = t1_df.loc[t1_mask, "atr_pct"]   # +1R
    results.append(_exit_metrics(t1_df, "t1_exit_return", "Exit at T1 (1R) when hit"))

    # Target 2 hit: +2R when hit
    t2_df = df.copy()
    t2_mask = t2_df["target2_hit"] & t2_df["atr_pct"].notna()
    t2_df["t2_exit_return"] = t2_df["return_pct"]
    t2_df.loc[t2_mask, "t2_exit_return"] = t2_df.loc[t2_mask, "atr_pct"] * 2
    results.append(_exit_metrics(t2_df, "t2_exit_return", "Exit at T2 (2R) when hit"))

    # Target 3 hit: +3R when hit
    t3_df = df.copy()
    t3_mask = t3_df["target3_hit"] & t3_df["atr_pct"].notna()
    t3_df["t3_exit_return"] = t3_df["return_pct"]
    t3_df.loc[t3_mask, "t3_exit_return"] = t3_df.loc[t3_mask, "atr_pct"] * 3
    results.append(_exit_metrics(t3_df, "t3_exit_return", "Exit at T3 (3R) when hit"))

    return results


def exit_study_by_regime(df: pd.DataFrame) -> list[str]:
    """Exit study per sector regime."""
    rows = ["| Exit | 5d Exp | 10d Exp | 20d Exp |", "|---|---|---|---|"]
    for regime in ["bull", "bear", "range"]:
        g = df[df["sector_regime"] == regime]
        if len(g) < 20:
            continue
        e5  = g["return_pct"].mean()
        e10 = g["return_pct_10d"].mean()
        e20 = g["return_pct_20d"].mean()
        rows.append(f"| {regime.title()} | {e5:+.3f}% | {e10:+.3f}% | {e20:+.3f}% |")
    return rows


# ──────────────────────────────────────────────────────────────────────────────
# Discovery questions
# ──────────────────────────────────────────────────────────────────────────────

def answer_discovery_questions(df: pd.DataFrame, combos: pd.DataFrame) -> list[str]:
    """Auto-answer the 7 standard Atlas trade attribution discovery questions."""
    lines = []

    # Q1: Where does Atlas make money?
    lines.append("### Q1: Where does Atlas make money?")
    top = combos.nlargest(5, "expectancy") if not combos.empty else pd.DataFrame()
    if not top.empty:
        for _, r in top.iterrows():
            lines.append(f"- **{r['combination']}**: {r['expectancy']:+.3f}% expectancy, {r['win_rate']:.0f}% WR, PF={r['profit_factor']:.2f} (n={r['n']:,})")
    else:
        best_tier = df.groupby("quality_tier")["return_pct"].mean().idxmax()
        lines.append(f"- Top context: Quality Tier {best_tier} by mean expectancy")
    lines.append("")

    # Q2: Where does Atlas lose money?
    lines.append("### Q2: Where does Atlas lose money?")
    bot = combos.nsmallest(5, "expectancy") if not combos.empty else pd.DataFrame()
    if not bot.empty:
        for _, r in bot.iterrows():
            lines.append(f"- **{r['combination']}**: {r['expectancy']:+.3f}% expectancy, {r['win_rate']:.0f}% WR, PF={r['profit_factor']:.2f} (n={r['n']:,})")
    lines.append("")

    # Q3: Best signal combinations
    lines.append("### Q3: Best signal combinations by profit factor?")
    best_pf = combos[combos["n"] >= 100].nlargest(5, "profit_factor") if not combos.empty else pd.DataFrame()
    if not best_pf.empty:
        for _, r in best_pf.iterrows():
            lines.append(f"- **{r['combination']}**: PF={r['profit_factor']:.2f}, {r['expectancy']:+.3f}% exp (n={r['n']:,})")
    lines.append("")

    # Q4: Worst signal combinations
    lines.append("### Q4: Worst signal combinations by profit factor?")
    worst_pf = combos[combos["n"] >= 100].nsmallest(5, "profit_factor") if not combos.empty else pd.DataFrame()
    if not worst_pf.empty:
        for _, r in worst_pf.iterrows():
            lines.append(f"- **{r['combination']}**: PF={r['profit_factor']:.3f}, {r['expectancy']:+.3f}% exp (n={r['n']:,})")
    lines.append("")

    # Q5: Which exit improves profitability?
    lines.append("### Q5: Which exit strategy improves profitability?")
    r5  = df["return_pct"].dropna()
    r10 = df["return_pct_10d"].dropna()
    r20 = df["return_pct_20d"].dropna()
    best_hold = "5d"
    best_exp  = r5.mean()
    if r10.mean() > best_exp:
        best_hold, best_exp = "10d", r10.mean()
    if r20.mean() > best_exp:
        best_hold, best_exp = "20d", r20.mean()
    lines.append(f"- Best hold period: **{best_hold}** ({best_exp:+.3f}% expectancy)")
    t1_hit_pct = df["target1_hit"].mean() * 100
    stop_pct   = df["stop_hit"].mean() * 100
    lines.append(f"- T1 target hit rate: {t1_hit_pct:.1f}% — using T1 exits captures winners early")
    lines.append(f"- ATR stop triggered: {stop_pct:.1f}% of trades — stops protect capital on losers")
    lines.append("")

    # Q6: Which exits destroy profitability?
    lines.append("### Q6: Which exits destroy profitability?")
    if stop_pct > 40:
        lines.append(f"- WARNING: ATR stop rate {stop_pct:.0f}% is very high — stops may be too tight")
    if t1_hit_pct < 15:
        lines.append(f"- WARNING: T1 hit rate {t1_hit_pct:.0f}% is low — targets may be too ambitious")
    flip_trades = df[df["signal_flip_exit"] == True]
    flip_exp = flip_trades["return_pct"].mean() if len(flip_trades) > 0 else 0
    noflip_exp = df[df["signal_flip_exit"] == False]["return_pct"].mean()
    if flip_exp < noflip_exp - 0.1:
        lines.append(f"- Signal-flipped trades underperform: {flip_exp:+.3f}% vs {noflip_exp:+.3f}% (no flip)")
    lines.append("")

    # Q7: Where should focus go?
    lines.append("### Q7: Where should focus go next?")
    pf5 = r5[r5 > 0].sum() / abs(r5[r5 < 0].sum()) if (r5 < 0).sum() > 0 else np.inf
    if pf5 < 1.0:
        lines.append(f"- URGENT: Profit factor {pf5:.3f} < 1.0 — system is net LOSING. Review worst-performing contexts immediately.")
    elif pf5 < 1.3:
        lines.append(f"- Profit factor {pf5:.3f} is marginal. Tighten entry filters and eliminate negative-expectancy contexts.")
    else:
        lines.append(f"- Profit factor {pf5:.3f} is acceptable. Leverage best-performing combinations for higher capital allocation.")

    if not combos.empty:
        best_combo = combos.nlargest(1, "expectancy").iloc[0]
        worst_combo = combos.nsmallest(1, "expectancy").iloc[0]
        lines.append(f"- **Scale up**: {best_combo['combination']} ({best_combo['expectancy']:+.3f}% exp, {best_combo['n']:,} trades)")
        lines.append(f"- **Avoid**: {worst_combo['combination']} ({worst_combo['expectancy']:+.3f}% exp)")
    lines.append("")

    return lines


# ──────────────────────────────────────────────────────────────────────────────
# Report builders
# ──────────────────────────────────────────────────────────────────────────────

def build_expectancy_report(df: pd.DataFrame, combos: pd.DataFrame, as_of: str) -> str:
    total = len(df)
    m_all = _metrics(df["return_pct"])
    discovery = answer_discovery_questions(df, combos)

    top25 = combos.head(25) if not combos.empty else pd.DataFrame()
    bot25 = combos.tail(25) if not combos.empty else pd.DataFrame()

    def combo_table(frame: pd.DataFrame) -> list[str]:
        hdr = "| # | Combination | N | Win Rate | Expectancy | Profit Factor |"
        sep = "|---|---|---|---|---|---|"
        rows = [hdr, sep]
        for i, (_, r) in enumerate(frame.iterrows(), 1):
            pf = f"{r['profit_factor']:.3f}" if r["profit_factor"] != np.inf else "∞"
            rows.append(f"| {i} | {r['combination']} | {r['n']:,} | {r['win_rate']:.1f}% | "
                        f"{r['expectancy']:+.3f}% | {pf} |")
        return rows

    by_tier    = context_table(df, "quality_tier",   [1, 2, 3, 4], ["Tier 1", "Tier 2", "Tier 3", "Tier 4"])
    by_jarvis  = bool_context_table(df, "jarvis_green", "Jarvis Green", "Jarvis Red")
    by_regime  = context_table(df, "sector_regime",  ["bull", "bear", "range"], ["Bull", "Bear", "Range"])
    by_vix     = context_table(df, "vix_regime",     ["low", "moderate", "high"], ["VIX Low", "VIX Moderate", "VIX High"])
    by_conf    = confluence_bucket_table(df)
    by_conv    = context_table(df, "conviction_level", ["VERY_HIGH", "HIGH", "MODERATE", "LOW"])
    by_ml      = ml_bucket_table(df)
    by_dir     = context_table(df, "predicted_direction", [1, -1], ["Long", "Short"])

    lines = [
        "# Expectancy Report",
        "",
        f"**Generated:** {as_of}  ",
        f"**Total trades analyzed:** {total:,}  ",
        f"**Date range:** {df['entry_date'].min().date()} → {df['entry_date'].max().date()}  ",
        f"**Status:** ANALYSIS ONLY.",
        "",
        "---",
        "",
        "## Overall Performance",
        "",
        TABLE_HEADER,
        _fmt_row("All trades (5d hold)", m_all),
        "",
        "---",
        "",
        "## By Trade Direction",
        "",
    ] + by_dir + [
        "",
        "---",
        "",
        "## By Quality Tier",
        "",
    ] + by_tier + [
        "",
        "---",
        "",
        "## By Jarvis Status",
        "",
    ] + by_jarvis + [
        "",
        "---",
        "",
        "## By Sector Regime",
        "",
    ] + by_regime + [
        "",
        "---",
        "",
        "## By VIX Regime",
        "",
    ] + by_vix + [
        "",
        "---",
        "",
        "## By Confluence Score",
        "",
    ] + by_conf + [
        "",
        "---",
        "",
        "## By Conviction Level",
        "",
    ] + by_conv + [
        "",
        "---",
        "",
        "## By ML Signal Strength",
        "",
    ] + by_ml + [
        "",
        "---",
        "",
        "## Top 25 Signal Combinations",
        "",
        f"*(min {25} trades per combination)*",
        "",
    ] + combo_table(top25) + [
        "",
        "---",
        "",
        "## Bottom 25 Signal Combinations (Worst Destroyers of Value)",
        "",
    ] + combo_table(bot25) + [
        "",
        "---",
        "",
        "## Discovery Questions",
        "",
    ] + discovery

    return "\n".join(lines)


def build_exit_study_report(df: pd.DataFrame, as_of: str) -> str:
    results = exit_study(df)
    regime_rows = exit_study_by_regime(df)

    hdr = "| Exit Strategy | N | Win Rate | Expectancy | Profit Factor | Max Drawdown |"
    sep = "|---|---|---|---|---|---|"
    rows = [hdr, sep]
    best_exp  = -999
    best_label = ""
    best_pf   = -999
    best_pf_label = ""
    for r in results:
        if r["n"] == 0:
            continue
        pf_str = f"{r['profit_factor']:.3f}" if r.get("profit_factor") != np.inf else "∞"
        dd_str = f"{r['max_drawdown']:.2f}%" if "max_drawdown" in r else "—"
        rows.append(
            f"| {r['label']} | {r['n']:,} | {r['win_rate']:.1f}% | "
            f"{r['expectancy']:+.3f}% | {pf_str} | {dd_str} |"
        )
        if r.get("expectancy", -999) > best_exp:
            best_exp = r["expectancy"]
            best_label = r["label"]
        if r.get("profit_factor", -999) != np.inf and r.get("profit_factor", -999) > best_pf:
            best_pf = r["profit_factor"]
            best_pf_label = r["label"]

    lines = [
        "# Exit Study Report",
        "",
        f"**Generated:** {as_of}  ",
        f"**Status:** ANALYSIS ONLY. Simulated exits only. No trades executed.",
        "",
        "---",
        "",
        "## Exit Strategy Comparison",
        "",
        "**Parameters:**",
        "- ATR Stop: 1.5× ATR (risk-per-trade R-unit)",
        "- T1 = +1R, T2 = +2R, T3 = +3R",
        "- Signal flip = next prediction has opposing direction",
        "",
    ] + rows + [
        "",
        "---",
        "",
        "## Recommendation",
        "",
        f"- **Best expectancy**: {best_label} ({best_exp:+.3f}%)",
        f"- **Best profit factor**: {best_pf_label} (PF={best_pf:.3f})",
        "",
        "---",
        "",
        "## Expectancy by Regime and Hold Period",
        "",
    ] + regime_rows + [
        "",
        "---",
        "",
        "## Key Takeaways",
        "",
        "1. **Hold period matters per regime**: Bull markets often reward patience (20d > 5d), bear markets often benefit from faster exits",
        "2. **ATR stops protect capital** on adverse excursions but may cut winners short in trending markets",
        "3. **Target ladder (T1/T2/T3)** allows partial profit-taking while running winners — most effective for high-conviction trades",
        "4. **Signal flip exits** deserve investigation: if flipped trades significantly underperform, the model is reversing correctly and early exit is valuable",
        "5. **Combine best exit with best context**: apply the optimal exit strategy specifically within the top-performing signal combinations",
        "",
        f"*Run `python scripts/reconstruct_trades.py` first to refresh trade data before this study.*",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-n", type=int, default=50, help="Min trades per context slice")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    as_of  = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("\n=== Atlas Expectancy Analysis ===")
    print(f"As-of: {as_of}")

    print("\n[1/4] Loading trade_attribution...")
    df = load_trades(engine)
    if df.empty:
        print("No trades found. Run reconstruct_trades.py first.")
        return

    print("\n[2/4] Computing component combinations...")
    combos = build_combinations(df, min_n=args.min_n)
    print(f"  Found {len(combos):,} combinations with n>={args.min_n}")

    print("\n[3/4] Building EXPECTANCY_REPORT...")
    EXPECTANCY_REPORT.parent.mkdir(exist_ok=True)
    text_exp = build_expectancy_report(df, combos, as_of)
    EXPECTANCY_REPORT.write_text(text_exp, encoding="utf-8")
    print(f"  -> {EXPECTANCY_REPORT}")

    print("\n[4/4] Building EXIT_STUDY_REPORT...")
    text_exit = build_exit_study_report(df, as_of)
    EXIT_STUDY_REPORT.write_text(text_exit, encoding="utf-8")
    print(f"  -> {EXIT_STUDY_REPORT}")

    # Print headline metrics
    m = _metrics(df["return_pct"])
    if m:
        print(f"\nHeadline:")
        print(f"  Win rate:      {m['win_rate']:.1f}%")
        print(f"  Expectancy:    {m['expectancy']:+.3f}%")
        print(f"  Profit factor: {m['profit_factor']:.3f}")
        print(f"  Avg winner:    {m['avg_winner']:+.3f}%")
        print(f"  Avg loser:     {m['avg_loser']:+.3f}%")

    print("\nDone.")


if __name__ == "__main__":
    main()
