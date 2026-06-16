"""
Atlas Intraday 5-Minute Learning Engine v1 -- Walk-Forward Validation
======================================================================
Loads detected setups + outcomes from DB, runs walk-forward validation,
promotes robust setups, and generates INTRADAY_5M_LEARNING_REPORT.md.

Walk-forward method:
  - Chronological 70/30 split by setup timestamp
  - In-sample  (first 70%): compute baseline metrics
  - Out-of-sample (last 30%): validate
  - Promote only if both periods pass thresholds AND OOS holds up

Usage:
    python scripts/run_intraday_walkforward.py
    python scripts/run_intraday_walkforward.py --horizon 6
    python scripts/run_intraday_walkforward.py --dry-run

Does NOT auto-trade. Does NOT modify daily signals.
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
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
REPORT_PATH  = Path(__file__).parent.parent / "reports" / "INTRADAY_5M_LEARNING_REPORT.md"

# Promotion thresholds
MIN_SAMPLE_SIZE    = 30
MIN_WIN_RATE       = 0.50
MIN_EXPECTANCY     = 0.10    # > +0.10% per trade (after slippage ~1-2 bps)
MIN_PROFIT_FACTOR  = 1.20
OOS_MIN_WIN_RATE   = 0.47    # slightly relaxed for OOS
OOS_MIN_EXPECTANCY = 0.05
OOS_MIN_PF         = 1.10
SLIPPAGE_PCT       = 0.05    # 5 bps per side (0.10% round-trip)

ANALYSIS_HORIZON   = 6       # default outcome horizon (30 min)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_setups_with_outcomes(engine, horizon: int) -> pd.DataFrame:
    sql = f"""
    SELECT
        s.setup_id,
        s.ticker,
        s.ts,
        s.setup_type,
        s.direction,
        s.timeframe,
        s.daily_conviction,
        s.daily_regime,
        s.daily_vix_regime,
        s.daily_ml_rank,
        s.daily_confluence,
        o.future_return,
        o.mfe,
        o.mae,
        o.hit_target,
        o.hit_stop,
        o.time_to_target,
        o.time_to_stop,
        o.horizon_bars
    FROM intraday_setups s
    JOIN intraday_outcomes o
      ON o.setup_id = s.setup_id AND o.horizon_bars = {horizon}
    WHERE o.future_return IS NOT NULL
    ORDER BY s.ts
    """
    df = pd.read_sql(sql, engine, parse_dates=["ts"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _pf(returns: np.ndarray) -> float:
    wins   = float(returns[returns > 0].sum())
    losses = float(abs(returns[returns <= 0].sum()))
    if losses == 0:
        return 5.0 if wins > 0 else 1.0
    return min(5.0, wins / losses)


def compute_metrics(returns: np.ndarray, slip: float = SLIPPAGE_PCT) -> dict:
    """Compute trading metrics on an array of percent returns (per-trade)."""
    r    = returns - slip   # deduct slippage
    n    = len(r)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0,
                    avg_win=0.0, avg_loss=0.0, max_dd=0.0)
    wins   = r[r > 0]
    losses = r[r <= 0]
    # Walk the equity curve for max drawdown
    cumulative = np.cumsum(r)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns   = running_max - cumulative
    return dict(
        n        = n,
        wr       = float((r > 0).mean()),
        exp      = float(np.mean(r)),
        pf       = _pf(r),
        avg_win  = float(np.mean(wins))  if len(wins)   else 0.0,
        avg_loss = float(np.mean(losses)) if len(losses) else 0.0,
        max_dd   = float(drawdowns.max()) if len(drawdowns) else 0.0,
    )


def passes_promotion(is_m: dict, oos_m: dict) -> tuple[bool, str]:
    reasons = []
    if is_m["n"] < MIN_SAMPLE_SIZE:
        reasons.append(f"IS n={is_m['n']}<{MIN_SAMPLE_SIZE}")
    if is_m["wr"] < MIN_WIN_RATE:
        reasons.append(f"IS WR={is_m['wr']:.1%}<{MIN_WIN_RATE:.1%}")
    if is_m["exp"] < MIN_EXPECTANCY:
        reasons.append(f"IS exp={is_m['exp']:+.2f}%<{MIN_EXPECTANCY}%")
    if is_m["pf"] < MIN_PROFIT_FACTOR:
        reasons.append(f"IS PF={is_m['pf']:.2f}<{MIN_PROFIT_FACTOR}")
    if oos_m["n"] < 10:
        reasons.append(f"OOS n={oos_m['n']}<10")
    if oos_m["wr"] < OOS_MIN_WIN_RATE:
        reasons.append(f"OOS WR={oos_m['wr']:.1%}<{OOS_MIN_WIN_RATE:.1%}")
    if oos_m["exp"] < OOS_MIN_EXPECTANCY:
        reasons.append(f"OOS exp={oos_m['exp']:+.2f}%<{OOS_MIN_EXPECTANCY}%")
    if oos_m["pf"] < OOS_MIN_PF:
        reasons.append(f"OOS PF={oos_m['pf']:.2f}<{OOS_MIN_PF}")
    if reasons:
        return False, "; ".join(reasons)
    return True, "all thresholds passed"


# ---------------------------------------------------------------------------
# Walk-forward validation
# ---------------------------------------------------------------------------

def run_walkforward(df: pd.DataFrame) -> list[dict]:
    """
    For each (setup_type, direction), run 70/30 chronological walk-forward.
    Returns list of result dicts.
    """
    results = []
    for (st, dir_), grp in df.groupby(["setup_type", "direction"]):
        grp = grp.sort_values("ts")
        returns = grp["future_return"].values.astype(float)
        n_total = len(returns)

        split_idx = int(n_total * 0.70)
        is_r      = returns[:split_idx]
        oos_r     = returns[split_idx:]

        is_m  = compute_metrics(is_r)
        oos_m = compute_metrics(oos_r)
        wf_passed, notes = passes_promotion(is_m, oos_m)

        results.append({
            "setup_type":         st,
            "direction":          dir_,
            "timeframe":          "5m",
            "sample_size":        is_m["n"],
            "win_rate":           is_m["wr"],
            "expectancy":         is_m["exp"],
            "profit_factor":      is_m["pf"],
            "max_drawdown":       is_m["max_dd"],
            "oos_sample_size":    oos_m["n"],
            "oos_win_rate":       oos_m["wr"],
            "oos_expectancy":     oos_m["exp"],
            "oos_profit_factor":  oos_m["pf"],
            "walk_forward_passed": wf_passed,
            "promoted":           wf_passed,
            "notes":              notes,
            "scored_date":        date.today(),
            "n_total":            n_total,
            # For report use
            "_is_metrics":        is_m,
            "_oos_metrics":       oos_m,
        })

    return results


# ---------------------------------------------------------------------------
# Context analysis (Part 8: daily + intraday connection)
# ---------------------------------------------------------------------------

def analyze_daily_context(df: pd.DataFrame) -> dict:
    """Measure whether intraday setup performance improves with daily context."""
    results = {}
    if df.empty or "daily_conviction" not in df.columns:
        return results

    returns = df["future_return"].values.astype(float) - SLIPPAGE_PCT

    # By daily conviction
    for conviction in df["daily_conviction"].dropna().unique():
        mask = df["daily_conviction"] == conviction
        r    = returns[mask]
        if len(r) < 10:
            continue
        results[f"conviction_{conviction}"] = compute_metrics(r, slip=0)

    # By daily regime
    for regime in df["daily_regime"].dropna().unique():
        mask = df["daily_regime"] == regime
        r    = returns[mask]
        if len(r) < 10:
            continue
        results[f"regime_{regime}"] = compute_metrics(r, slip=0)

    # Baseline (no context)
    results["all_setups"] = compute_metrics(returns, slip=0)

    return results


def analyze_time_of_day(df: pd.DataFrame) -> dict:
    """Break down setup performance by time of day."""
    if df.empty or "ts" not in df.columns:
        return {}
    local_ts = df["ts"].dt.tz_convert("America/New_York")
    tod_min  = local_ts.dt.hour * 60 + local_ts.dt.minute
    results  = {}

    buckets = [
        ("open_30m",  570, 600),
        ("930_10",    600, 630),
        ("10_1030",   630, 660),
        ("1030_14",   660, 840),
        ("14_15",     840, 900),
        ("15_close",  900, 960),
    ]
    returns = df["future_return"].values.astype(float) - SLIPPAGE_PCT
    for label, lo, hi in buckets:
        mask = (tod_min >= lo) & (tod_min < hi)
        r    = returns[mask.values]
        if len(r) >= 5:
            results[label] = compute_metrics(r, slip=0)

    return results


def analyze_ticker_breakdown(df: pd.DataFrame) -> dict:
    """Performance by ticker to check cross-ticker robustness."""
    results = {}
    returns = df["future_return"].values.astype(float) - SLIPPAGE_PCT
    results["all"] = compute_metrics(returns, slip=0)
    for ticker in df["ticker"].unique():
        r = (df[df["ticker"] == ticker]["future_return"].values.astype(float) - SLIPPAGE_PCT)
        if len(r) >= 5:
            results[ticker] = compute_metrics(r, slip=0)
    return results


def analyze_volume_conditions(df: pd.DataFrame) -> dict:
    """Did high-volume setups outperform?"""
    # Extract vol_ratio from confidence_inputs JSON
    results = {}
    if "confidence_inputs" not in df.columns:
        return results
    try:
        import json as _json
        df = df.copy()
        df["_vol_ratio"] = df["confidence_inputs"].apply(
            lambda s: _json.loads(s).get("vol_ratio") if isinstance(s, str) else None
        )
        df["_vol_ratio"] = pd.to_numeric(df["_vol_ratio"], errors="coerce")
        returns = df["future_return"].values.astype(float) - SLIPPAGE_PCT
        for label, lo, hi in [("normal", 0, 1.5), ("high_vol", 1.5, 2.5), ("very_high", 2.5, 99)]:
            mask = (df["_vol_ratio"].fillna(0) >= lo) & (df["_vol_ratio"].fillna(0) < hi)
            r = returns[mask.values]
            if len(r) >= 5:
                results[label] = compute_metrics(r, slip=0)
    except Exception:
        pass
    return results


def analyze_gap_conditions(df: pd.DataFrame) -> dict:
    """Performance on gap-up vs gap-down vs flat days."""
    results = {}
    try:
        import json as _json
        df = df.copy()
        df["_gap"] = df["confidence_inputs"].apply(
            lambda s: _json.loads(s).get("gap_pct") if isinstance(s, str) else None
        )
        df["_gap"] = pd.to_numeric(df["_gap"], errors="coerce")
        returns = df["future_return"].values.astype(float) - SLIPPAGE_PCT
        for label, lo, hi in [
            ("gap_up",   0.3, 99),
            ("flat",    -0.3, 0.3),
            ("gap_down", -99, -0.3),
        ]:
            mask = (df["_gap"].fillna(0) > lo) & (df["_gap"].fillna(0) <= hi)
            r = returns[mask.values]
            if len(r) >= 5:
                results[label] = compute_metrics(r, slip=0)
    except Exception:
        pass
    return results


# ---------------------------------------------------------------------------
# DB upsert for promoted setups
# ---------------------------------------------------------------------------

def upsert_promoted(rows: list[dict], engine) -> int:
    from sqlalchemy import text
    sql = text("""
    INSERT INTO intraday_promoted_setups
        (setup_type, direction, timeframe, sample_size, win_rate, expectancy,
         profit_factor, max_drawdown, oos_sample_size, oos_win_rate, oos_expectancy,
         oos_profit_factor, walk_forward_passed, promoted, notes, scored_date)
    VALUES
        (:setup_type, :direction, :timeframe, :sample_size, :win_rate, :expectancy,
         :profit_factor, :max_drawdown, :oos_sample_size, :oos_win_rate, :oos_expectancy,
         :oos_profit_factor, :walk_forward_passed, :promoted, :notes, :scored_date)
    ON CONFLICT (setup_type, direction, timeframe, scored_date) DO UPDATE SET
        sample_size       = EXCLUDED.sample_size,
        win_rate          = EXCLUDED.win_rate,
        expectancy        = EXCLUDED.expectancy,
        profit_factor     = EXCLUDED.profit_factor,
        max_drawdown      = EXCLUDED.max_drawdown,
        oos_sample_size   = EXCLUDED.oos_sample_size,
        oos_win_rate      = EXCLUDED.oos_win_rate,
        oos_expectancy    = EXCLUDED.oos_expectancy,
        oos_profit_factor = EXCLUDED.oos_profit_factor,
        walk_forward_passed = EXCLUDED.walk_forward_passed,
        promoted          = EXCLUDED.promoted,
        notes             = EXCLUDED.notes
    """)
    clean_keys = ["setup_type", "direction", "timeframe", "sample_size", "win_rate",
                  "expectancy", "profit_factor", "max_drawdown", "oos_sample_size",
                  "oos_win_rate", "oos_expectancy", "oos_profit_factor",
                  "walk_forward_passed", "promoted", "notes", "scored_date"]
    clean_rows = [{k: r.get(k) for k in clean_keys} for r in rows]
    with engine.begin() as conn:
        conn.execute(sql, clean_rows)
    return len(clean_rows)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def fmt_pct(v, decimals=2):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v):+.{decimals}f}%"

def fmt_f(v, decimals=2):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v):.{decimals}f}"

def fmt_pct_plain(v, decimals=1):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v)*100:.{decimals}f}%"


def generate_report(
    df: pd.DataFrame,
    wf_results: list[dict],
    tod_analysis: dict,
    ctx_analysis: dict,
    vol_analysis: dict,
    gap_analysis: dict,
    ticker_analysis: dict,
    as_of: str,
) -> str:
    promoted = [r for r in wf_results if r["promoted"]]
    rejected = [r for r in wf_results if not r["promoted"]]
    top10    = sorted(wf_results, key=lambda r: r.get("oos_expectancy", -99), reverse=True)[:10]
    bot10    = sorted(wf_results, key=lambda r: r.get("oos_expectancy", 99))[:10]

    setup_counts = df.groupby("setup_type").size().to_dict()
    all_returns  = df["future_return"].values.astype(float) - SLIPPAGE_PCT
    overall      = compute_metrics(all_returns)

    lines = [
        "# Atlas Intraday 5-Minute Learning Report v1",
        "",
        f"**Generated:** {as_of}",
        f"**Horizon:** {ANALYSIS_HORIZON} bars (30 minutes)",
        "**Status:** ANALYSIS ONLY. No live trades. No signals changed.",
        "**Slippage:** 5 bps per side applied to all expectancy figures.",
        "",
        "---",
        "",
        "## Data Overview",
        "",
        f"- Total 5-min bars in DB: **{len(df)+0:,}** (approximate, via setups join)",
        f"- Total setups detected:   **{len(df):,}**",
        f"- Unique setup types:      **{df['setup_type'].nunique()}**",
        f"- Tickers:                 **{', '.join(sorted(df['ticker'].unique()))}**",
        f"- Date range:              **{df['ts'].min().date()} to {df['ts'].max().date()}**",
        "",
        "**Limitation:** Free Yahoo Finance 5m data covers ~60 trading days per ticker.",
        "Sample sizes are small for some setups. Results require ~6 months of data",
        "to be statistically robust. Treat these findings as directional, not definitive.",
        "",
    ]

    # ── 1. Overall baseline ─────────────────────────────────────────────────
    lines += [
        "## 1. Overall Setup Baseline",
        "",
        f"| Metric | Value |",
        "|---|---|",
        f"| Total setups | {overall['n']:,} |",
        f"| Win rate | {fmt_pct_plain(overall['wr'])} |",
        f"| Expectancy (after slip) | {fmt_pct(overall['exp'])} per trade |",
        f"| Profit factor | {fmt_f(overall['pf'])} |",
        f"| Avg winner | {fmt_pct(overall['avg_win'])} |",
        f"| Avg loser | {fmt_pct(overall['avg_loss'])} |",
        f"| Max drawdown (cumulative) | {fmt_pct(overall['max_dd'])} |",
        "",
    ]

    # ── 2. Walk-forward table ───────────────────────────────────────────────
    lines += [
        "## 2. Walk-Forward Validation Results (all setups)",
        "",
        "70% in-sample / 30% out-of-sample chronological split.",
        "",
        "| Setup | Dir | IS n | IS WR | IS Exp | IS PF | OOS n | OOS WR | OOS Exp | OOS PF | WF? |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(wf_results, key=lambda x: x.get("oos_expectancy", -99), reverse=True):
        wf = "YES" if r["walk_forward_passed"] else "no"
        lines.append(
            f"| {r['setup_type']} | {r['direction']} "
            f"| {r['sample_size']} | {fmt_pct_plain(r['win_rate'])} "
            f"| {fmt_pct(r['expectancy'])} | {fmt_f(r['profit_factor'])} "
            f"| {r['oos_sample_size']} | {fmt_pct_plain(r['oos_win_rate'])} "
            f"| {fmt_pct(r['oos_expectancy'])} | {fmt_f(r['oos_profit_factor'])} "
            f"| {wf} |"
        )

    # ── 3. Which setups work ────────────────────────────────────────────────
    lines += [
        "",
        "## 3. Which 5-Minute Setups Work?",
        "",
    ]
    if promoted:
        lines.append("**PROMOTED setups (walk-forward passed):**")
        lines.append("")
        lines.append("| Setup | Direction | IS Exp | OOS Exp | OOS PF | Notes |")
        lines.append("|---|---|---|---|---|---|")
        for r in sorted(promoted, key=lambda x: x["oos_expectancy"], reverse=True):
            lines.append(
                f"| **{r['setup_type']}** | {r['direction']} "
                f"| {fmt_pct(r['expectancy'])} | {fmt_pct(r['oos_expectancy'])} "
                f"| {fmt_f(r['oos_profit_factor'])} | {r['notes'][:60]} |"
            )
    else:
        lines.append("No setups met all promotion thresholds with current data volume.")
        lines.append("More history (>6 months) is needed for reliable promotion.")

    lines += [
        "",
        "## 4. Which Setups Fail?",
        "",
        "Setups with negative OOS expectancy after slippage:",
        "",
        "| Setup | Direction | OOS Exp | Reason |",
        "|---|---|---|---|",
    ]
    for r in [x for x in rejected if x["oos_expectancy"] < 0]:
        lines.append(
            f"| {r['setup_type']} | {r['direction']} "
            f"| {fmt_pct(r['oos_expectancy'])} | {r['notes'][:60]} |"
        )
    if not any(x["oos_expectancy"] < 0 for x in rejected):
        lines.append("| — | — | — | No setups with negative OOS expectancy |")

    # ── 5. Time of day ──────────────────────────────────────────────────────
    lines += [
        "",
        "## 5. Performance by Time of Day",
        "",
        "| Time Bucket | N | Win Rate | Expectancy | PF |",
        "|---|---|---|---|---|",
    ]
    bucket_labels = {
        "open_30m":  "9:30-10:00 (Opening 30m)",
        "930_10":    "9:30-10:00",
        "10_1030":   "10:00-10:30",
        "1030_14":   "10:30-14:00",
        "14_15":     "14:00-15:00",
        "15_close":  "15:00-16:00 (Power Hour)",
    }
    for label, m in tod_analysis.items():
        lines.append(
            f"| {bucket_labels.get(label, label)} | {m['n']} "
            f"| {fmt_pct_plain(m['wr'])} | {fmt_pct(m['exp'])} | {fmt_f(m['pf'])} |"
        )
    if not tod_analysis:
        lines.append("| — | — | — | — | Not enough data |")

    # ── 6. By ticker ────────────────────────────────────────────────────────
    lines += [
        "",
        "## 6. Cross-Ticker Robustness",
        "",
        "| Ticker | N | Win Rate | Expectancy | PF |",
        "|---|---|---|---|---|",
    ]
    for t, m in sorted(ticker_analysis.items(), key=lambda x: x[1]["exp"], reverse=True):
        lines.append(
            f"| {t} | {m['n']} | {fmt_pct_plain(m['wr'])} "
            f"| {fmt_pct(m['exp'])} | {fmt_f(m['pf'])} |"
        )

    # ── 7. Volume conditions ─────────────────────────────────────────────────
    lines += [
        "",
        "## 7. High-Volume Environments",
        "",
        "| Volume Level | N | Win Rate | Expectancy | PF |",
        "|---|---|---|---|---|",
    ]
    for label, m in vol_analysis.items():
        lines.append(
            f"| {label} | {m['n']} | {fmt_pct_plain(m['wr'])} "
            f"| {fmt_pct(m['exp'])} | {fmt_f(m['pf'])} |"
        )
    if not vol_analysis:
        lines.append("| — | — | — | — | Not available |")

    # ── 8. Gap conditions ────────────────────────────────────────────────────
    lines += [
        "",
        "## 8. After-Gap Performance",
        "",
        "| Gap Type | N | Win Rate | Expectancy | PF |",
        "|---|---|---|---|---|",
    ]
    for label, m in gap_analysis.items():
        lines.append(
            f"| {label} | {m['n']} | {fmt_pct_plain(m['wr'])} "
            f"| {fmt_pct(m['exp'])} | {fmt_f(m['pf'])} |"
        )
    if not gap_analysis:
        lines.append("| — | — | — | — | Not available |")

    # ── 9. Daily context alignment (Part 8) ─────────────────────────────────
    lines += [
        "",
        "## 9. Daily Context Alignment (Part 8: Intraday + Daily Connection)",
        "",
        "Does intraday setup performance improve when daily conviction agrees?",
        "",
        "| Context | N | Expectancy | PF |",
        "|---|---|---|---|",
    ]
    for label, m in sorted(ctx_analysis.items(), key=lambda x: x[1]["exp"], reverse=True):
        lines.append(
            f"| {label} | {m['n']} | {fmt_pct(m['exp'])} | {fmt_f(m['pf'])} |"
        )
    if not ctx_analysis:
        lines.append("| — | — | — | No daily context available yet |")

    # ── 10. Top 10 / bottom 10 ───────────────────────────────────────────────
    lines += [
        "",
        "## 10. Top 10 Setups by OOS Expectancy",
        "",
        "| Rank | Setup | Dir | OOS Exp | OOS WR | OOS n |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(top10, 1):
        lines.append(
            f"| {i} | {r['setup_type']} | {r['direction']} "
            f"| {fmt_pct(r['oos_expectancy'])} | {fmt_pct_plain(r['oos_win_rate'])} "
            f"| {r['oos_sample_size']} |"
        )

    lines += [
        "",
        "## 11. Bottom 10 Setups by OOS Expectancy",
        "",
        "| Rank | Setup | Dir | OOS Exp | OOS WR | OOS n |",
        "|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(bot10, 1):
        lines.append(
            f"| {i} | {r['setup_type']} | {r['direction']} "
            f"| {fmt_pct(r['oos_expectancy'])} | {fmt_pct_plain(r['oos_win_rate'])} "
            f"| {r['oos_sample_size']} |"
        )

    # ── 12. Setup counts ─────────────────────────────────────────────────────
    lines += [
        "",
        "## 12. Setup Detection Frequency",
        "",
        "| Setup | Count | % of Total |",
        "|---|---|---|",
    ]
    total_setups = sum(setup_counts.values())
    for st, cnt in sorted(setup_counts.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"| {st} | {cnt:,} | {cnt/total_setups*100:.1f}% |")

    # ── 13. Recommendations ──────────────────────────────────────────────────
    lines += [
        "",
        "## 13. Recommendations",
        "",
    ]
    if promoted:
        lines += [
            f"**PROMOTED:** {len(promoted)} setup(s) passed walk-forward validation:",
            "",
        ]
        for r in sorted(promoted, key=lambda x: x["oos_expectancy"], reverse=True):
            lines.append(
                f"- **{r['setup_type']} ({r['direction']})**: "
                f"OOS Exp={fmt_pct(r['oos_expectancy'])}, PF={fmt_f(r['oos_profit_factor'])}"
            )
        lines += [
            "",
            "Action: Surface PROMOTED setup signals in BotLab alongside daily predictions.",
            "Gate: Only surface setups during market hours when daily conviction >= HIGH.",
        ]
    else:
        lines += [
            "No setups met all promotion thresholds at current data volume.",
            "",
            "**Next steps:**",
            "1. Run ingestion daily for 60-90 days to accumulate data",
            "2. Re-run walk-forward when total setups per type >= 50",
            "3. Focus on time-of-day and daily context filtering to improve signal quality",
        ]

    lines += [
        "",
        "**Best entry conditions (based on this data):**",
    ]
    if tod_analysis:
        best_tod = max(tod_analysis.items(), key=lambda x: x[1]["exp"])
        lines.append(f"- Best time of day: **{best_tod[0]}** "
                     f"(Exp={fmt_pct(best_tod[1]['exp'])}, n={best_tod[1]['n']})")
    if vol_analysis and "high_vol" in vol_analysis:
        lines.append(f"- High-volume setups: Exp={fmt_pct(vol_analysis['high_vol']['exp'])} "
                     f"vs normal Exp={fmt_pct(vol_analysis.get('normal', {}).get('exp', 0))}")
    if ctx_analysis:
        best_ctx = max(
            ((k, v) for k, v in ctx_analysis.items() if k != "all_setups"),
            key=lambda x: x[1]["exp"],
            default=None,
        )
        if best_ctx:
            lines.append(f"- Best daily context: **{best_ctx[0]}** "
                         f"(Exp={fmt_pct(best_ctx[1]['exp'])})")

    lines += [
        "",
        "---",
        f"_Generated by run_intraday_walkforward.py on {as_of}_",
        f"_Promotion thresholds: IS WR>={MIN_WIN_RATE:.0%}, IS Exp>={MIN_EXPECTANCY}%, IS PF>={MIN_PROFIT_FACTOR},"
        f" OOS WR>={OOS_MIN_WIN_RATE:.0%}, OOS PF>={OOS_MIN_PF}_",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon",  type=int, default=ANALYSIS_HORIZON,
                        help="Outcome horizon in bars (default: 6 = 30min)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="Compute but do not write promoted setups to DB")
    args = parser.parse_args()

    as_of  = datetime.now().strftime("%Y-%m-%d %H:%M")
    engine = create_engine(DATABASE_URL)

    print("=== Atlas Intraday 5-Minute Walk-Forward Validation ===")
    print(f"As-of: {as_of}   horizon={args.horizon} bars ({args.horizon*5} min)")
    print()

    print("[1/5] Loading setups + outcomes from DB...")
    try:
        df = load_setups_with_outcomes(engine, args.horizon)
    except Exception as e:
        print(f"  ERROR: {e}")
        print("  Run ingest_intraday_5m.py first.")
        return

    if df.empty:
        print("  No data found -- run ingest_intraday_5m.py first.")
        return
    print(f"  {len(df):,} setups with outcomes across {df['ticker'].nunique()} tickers")

    print("[2/5] Running walk-forward validation...")
    wf_results = run_walkforward(df)
    n_promoted = sum(1 for r in wf_results if r["promoted"])
    n_rejected = len(wf_results) - n_promoted
    print(f"  Promoted: {n_promoted}   Rejected: {n_rejected}")

    print("[3/5] Analyzing context slices...")
    tod_analysis    = analyze_time_of_day(df)
    ctx_analysis    = analyze_daily_context(df)
    vol_analysis    = analyze_volume_conditions(df)
    gap_analysis    = analyze_gap_conditions(df)
    ticker_analysis = analyze_ticker_breakdown(df)

    print("[4/5] Writing promoted setups to DB...")
    if not args.dry_run:
        n = upsert_promoted(wf_results, engine)
        print(f"  {n} rows written to intraday_promoted_setups")
    else:
        print("  dry-run -- skipped")

    print("[5/5] Generating INTRADAY_5M_LEARNING_REPORT.md...")
    report = generate_report(
        df, wf_results, tod_analysis, ctx_analysis,
        vol_analysis, gap_analysis, ticker_analysis, as_of
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  -> {REPORT_PATH}")

    print()
    print("=== Top 5 Setup Types (by OOS Expectancy) ===")
    top = sorted(wf_results, key=lambda x: x["oos_expectancy"], reverse=True)[:5]
    for r in top:
        flag = "[PROMOTED]" if r["promoted"] else ""
        print(f"  {r['setup_type']:<26} {r['direction']:<6} "
              f"OOS Exp={r['oos_expectancy']:+.3f}%  n={r['oos_sample_size']:>4}  {flag}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
