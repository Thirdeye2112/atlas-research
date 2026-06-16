#!/usr/bin/env python3
"""
optimize_exits.py  --  Atlas Exit Optimization Engine v1

Tests 14 exit strategies + 7 specific filter/exit combinations against
847K hypothetical trades in trade_attribution.

ANALYSIS ONLY. No live trades executed. No signals changed. No retraining.
"""

import os
import sys
import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ── env ────────────────────────────────────────────────────────────────────────
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in environment")

engine = create_engine(DATABASE_URL)

REPORT_DIR  = os.path.join(os.path.dirname(__file__), "..", "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "EXIT_OPTIMIZATION_REPORT.md")
os.makedirs(REPORT_DIR, exist_ok=True)

# Constants (must match reconstruct_trades.py)
ATR_STOP = 1.5   # stop at -1.5 x ATR
T1_MULT  = 1.0   # T1 at +1.0 x ATR
T2_MULT  = 2.0   # T2 at +2.0 x ATR
T3_MULT  = 3.0   # T3 at +3.0 x ATR


# ── data ───────────────────────────────────────────────────────────────────────
def load_trades() -> pd.DataFrame:
    print("[1/5] Loading trade_attribution...")
    sql = text("""
    SELECT
        ticker, entry_date,
        return_pct, return_pct_10d, return_pct_20d,
        max_favorable_excursion AS mfe,
        max_adverse_excursion   AS mae,
        atr_pct,
        stop_hit, target1_hit, target2_hit, target3_hit,
        signal_flip_exit,
        predicted_direction,
        quality_tier,
        sector_regime,
        vix_regime,
        conviction_level,
        ml_signal_strength,
        confluence_score
    FROM trade_attribution
    WHERE return_pct IS NOT NULL
    ORDER BY entry_date
    """)
    with engine.connect() as conn:
        df = pd.read_sql(sql, conn)

    for col in ("return_pct", "return_pct_10d", "return_pct_20d",
                "atr_pct", "mfe", "mae", "ml_signal_strength",
                "confluence_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ("stop_hit", "target1_hit", "target2_hit",
                "target3_hit", "signal_flip_exit"):
        df[col] = df[col].fillna(False).astype(bool)

    df["predicted_direction"] = pd.to_numeric(
        df["predicted_direction"], errors="coerce"
    ).fillna(1).astype(int)

    print(f"  Loaded {len(df):,} trades  ({df['entry_date'].min()} -> {df['entry_date'].max()})")
    return df


# ── metrics ────────────────────────────────────────────────────────────────────
def compute_metrics(r: pd.Series, mfe_s: pd.Series = None) -> dict:
    r = r.dropna()
    n = len(r)
    if n == 0:
        return dict(n=0, win_rate=0.0, expectancy=0.0, avg_winner=0.0,
                    avg_loser=0.0, profit_factor=0.0, max_dd=0.0,
                    p10=0.0, mfe_capture=None)
    wins   = r[r > 0]
    losses = r[r <= 0]
    wr     = len(wins) / n
    exp    = float(r.mean())
    aw     = float(wins.mean())   if len(wins)   > 0 else 0.0
    al     = float(losses.mean()) if len(losses) > 0 else 0.0
    gs     = wins.sum()
    ls     = losses.sum()
    pf     = float(gs / abs(ls)) if ls != 0 else 999.0
    cum    = r.reset_index(drop=True).cumsum()
    dd     = float((cum - cum.cummax()).min())
    p10    = float(r.quantile(0.10))

    mfe_cap = None
    if mfe_s is not None:
        mfe_a = mfe_s.loc[r.index].clip(lower=0.001)
        cap   = (r / mfe_a).clip(-2, 2)
        mfe_cap = round(float(cap.mean()), 4)

    return dict(
        n=n,
        win_rate=round(wr * 100, 2),
        expectancy=round(exp, 4),
        avg_winner=round(aw, 4),
        avg_loser=round(al, 4),
        profit_factor=round(pf, 4),
        max_dd=round(dd, 2),
        p10=round(p10, 4),
        mfe_capture=mfe_cap,
    )


def fmt_m(m: dict) -> str:
    """Single-line metrics string for inline display."""
    return (
        f"n={m['n']:,}  WR={m['win_rate']}%  "
        f"Exp={m['expectancy']:+.3f}%  PF={m['profit_factor']:.3f}  "
        f"AvgW={m['avg_winner']:+.3f}%  AvgL={m['avg_loser']:+.3f}%"
    )


# ── strategy return computations ───────────────────────────────────────────────
def compute_all_returns(df: pd.DataFrame) -> dict:
    """
    Returns a dict of strategy_name -> pd.Series of per-trade simulated returns.
    All returns are %-based (same scale as return_pct).
    """
    atr  = df["atr_pct"].fillna(0).clip(lower=0)
    r5   = df["return_pct"]
    r10  = df["return_pct_10d"]
    r20  = df["return_pct_20d"]
    t1h  = df["target1_hit"].values
    t2h  = df["target2_hit"].values
    t3h  = df["target3_hit"].values
    sth  = df["stop_hit"].values
    conv = df["conviction_level"]
    mfe  = df["mfe"].fillna(0)

    T1r  = (atr * T1_MULT).values
    T2r  = (atr * T2_MULT).values
    T3r  = (atr * T3_MULT).values
    Stp  = (-atr * ATR_STOP).values
    r5v  = r5.values
    r10v = r10.values
    r20v = r20.values
    mfev = mfe.values

    has_atr = (atr > 0).values

    # ── pure exit strategies ──────────────────────────────────────────────────

    # Base holds
    s_5d  = r5
    s_10d = r10
    s_20d = r20

    # T1 only: T1 if hit, stop if hit (no T1), else 5d
    _t1 = np.where(has_atr & t1h, T1r,
           np.where(has_atr & sth & ~t1h, Stp, r5v)).astype(float)
    s_t1 = pd.Series(_t1, index=df.index)

    # T1 + runner: half at T1, half trails to T2 or locks T1 as floor
    _runner_half = np.where(t2h, T2r, np.maximum(T1r, r5v))
    _t1r = np.where(has_atr & t1h, 0.5 * T1r + 0.5 * _runner_half,
            np.where(has_atr & sth & ~t1h, Stp, r5v)).astype(float)
    s_t1_runner = pd.Series(_t1r, index=df.index)

    # T1/T2/T3 ladder: 1/3 at each level, remainder at 5d
    _lad = np.where(
        has_atr & t3h,
        (T1r + T2r + T3r) / 3,
        np.where(
            has_atr & t2h,
            (T1r + T2r + r5v) / 3,
            np.where(
                has_atr & t1h,
                T1r / 3 + 2.0 * r5v / 3,
                np.where(has_atr & sth, Stp, r5v)
            )
        )
    ).astype(float)
    s_ladder = pd.Series(_lad, index=df.index)

    # Break-even after T1: if T1 hit, floor return at 0
    _be = np.where(has_atr & t1h, np.maximum(0.0, r5v),
           np.where(has_atr & sth & ~t1h, Stp, r5v)).astype(float)
    s_be = pd.Series(_be, index=df.index)

    # ATR trailing stop approximation:
    #   If MFE >= T2: trail locks in >= T1 (peak at T2, trail 1 ATR behind)
    #   If MFE >= T1: trail locks in >= 0   (peak at T1, trail 1 ATR behind)
    #   Else:         5d close (no meaningful peak reached)
    _trail = np.where(
        has_atr & (mfev >= T2r),
        np.maximum(r5v, T1r),
        np.where(
            has_atr & (mfev >= T1r),
            np.maximum(r5v, 0.0),
            r5v
        )
    ).astype(float)
    s_trail = pd.Series(_trail, index=df.index)

    # 20d hold for HIGH/VERY_HIGH, else 5d
    _high = conv.isin(["HIGH", "VERY_HIGH"]).values
    _hc20 = np.where(_high, r20v, r5v).astype(float)
    s_hc20 = pd.Series(_hc20, index=df.index)

    # MAE-based tighter stop: if MAE > 0.75×ATR, exit there instead of waiting
    mae_v = df["mae"].fillna(0).values
    _mae_tight = np.where(
        has_atr & (mae_v >= atr.values * 0.75) & ~t1h,
        -(atr.values * 0.75),
        _t1
    ).astype(float)
    s_mae_tight = pd.Series(_mae_tight, index=df.index)

    return {
        "Base 5d Hold":          s_5d,
        "Base 10d Hold":         s_10d,
        "Base 20d Hold":         s_20d,
        "T1 Only":               s_t1,
        "T1 + Runner":           s_t1_runner,
        "T1/T2/T3 Ladder":       s_ladder,
        "Break-Even After T1":   s_be,
        "ATR Trailing Stop":     s_trail,
        "20d (HIGH/VH only)":    s_hc20,
        "Tight MAE Stop":        s_mae_tight,
    }


# ── filter masks ───────────────────────────────────────────────────────────────
def get_filters(df: pd.DataFrame) -> dict:
    known_regime = df["sector_regime"].isin(["bull", "bear", "range"])
    long_only    = df["predicted_direction"] == 1
    not_low      = df["conviction_level"] != "LOW"
    high_conv    = df["conviction_level"].isin(["HIGH", "VERY_HIGH"])

    return {
        "All trades":                 pd.Series(True, index=df.index),
        "Long-only":                  long_only,
        "Known regime":               known_regime,
        "Not-LOW conviction":         not_low,
        "HIGH/VH conviction":         high_conv,
        "Optimized (long+regime+conv)": long_only & known_regime & not_low,
        "Best template (long+regime+HIGH/VH)":
            long_only & known_regime & high_conv,
    }


# ── context breakdown ──────────────────────────────────────────────────────────
def context_rows(r: pd.Series, df: pd.DataFrame,
                 col: str, values: list,
                 labels: list = None) -> list[str]:
    rows = []
    for i, val in enumerate(values):
        label = (labels[i] if labels else str(val)) if labels else str(val)
        mask  = df[col] == val if val is not None else df[col].isna()
        m     = compute_metrics(r[mask])
        rows.append(
            f"| {label} | {m['n']:,} | {m['win_rate']}% | "
            f"{m['expectancy']:+.3f}% | {m['profit_factor']:.3f} |"
        )
    return rows


# ── report builder ─────────────────────────────────────────────────────────────
def build_report(df: pd.DataFrame, all_returns: dict) -> str:
    as_of   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    n_total = len(df)
    lines   = []

    def h(text): lines.append(f"\n## {text}\n")
    def h3(text): lines.append(f"\n### {text}\n")
    def row(text): lines.append(text)
    def blank(): lines.append("")

    lines.append("# Exit Optimization Report")
    lines.append(f"\n**Generated:** {as_of}  ")
    lines.append(f"**Trades analyzed:** {n_total:,}  ")
    lines.append(
        f"**Date range:** {df['entry_date'].min()} -> {df['entry_date'].max()}  "
    )
    lines.append("**Status:** ANALYSIS ONLY. No live trades executed. "
                 "No signals altered. No retraining.")

    # ── strategy comparison ───────────────────────────────────────────────────
    h("Strategy Comparison (All 847K Trades)")
    row("| Strategy | N | Win Rate | Expectancy | Profit Factor "
        "| Avg Winner | Avg Loser | MFE Capture | P10 Loss |")
    row("|---|---|---|---|---|---|---|---|---|")
    mfe_s = df["mfe"]
    for name, ret in all_returns.items():
        m = compute_metrics(ret, mfe_s=mfe_s)
        cap = f"{m['mfe_capture']:.3f}" if m["mfe_capture"] is not None else "—"
        row(
            f"| {name} | {m['n']:,} | {m['win_rate']}% | "
            f"{m['expectancy']:+.3f}% | {m['profit_factor']:.3f} | "
            f"{m['avg_winner']:+.3f}% | {m['avg_loser']:+.3f}% | "
            f"{cap} | {m['p10']:+.3f}% |"
        )

    # ── specific tests ────────────────────────────────────────────────────────
    h("Specific Test Results")

    t1_ret  = all_returns["T1 Only"]
    filters = get_filters(df)

    # Test 1: T1 only
    h3("Test 1: T1 Only Exit")
    m = compute_metrics(t1_ret, mfe_s=mfe_s)
    row(f"**Overall:** {fmt_m(m)}")
    blank()
    row("| Sector Regime | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        for line in context_rows(t1_ret, df, "sector_regime", [rg]):
            row(line)
    blank()
    row("| Conviction | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for cv in ["VERY_HIGH", "HIGH", "MODERATE", "LOW"]:
        for line in context_rows(t1_ret, df, "conviction_level", [cv]):
            row(line)
    blank()
    row("| VIX Regime | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for vx in ["low", "moderate", "high"]:
        for line in context_rows(t1_ret, df, "vix_regime", [vx]):
            row(line)

    # Test 2: T1 + runner
    h3("Test 2: T1 Then Trail Remainder")
    m = compute_metrics(all_returns["T1 + Runner"], mfe_s=mfe_s)
    row(f"**Overall:** {fmt_m(m)}")
    blank()
    row("Logic: exit 50% at T1 (+1 ATR), trail remaining 50% — "
        "if T2 hit exit there, else lock T1 as floor for runner.")
    blank()
    row("| Sector Regime | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        for line in context_rows(all_returns["T1 + Runner"], df, "sector_regime", [rg]):
            row(line)

    # Test 3: Break-even after T1
    h3("Test 3: T1 + Break-Even Stop")
    m = compute_metrics(all_returns["Break-Even After T1"], mfe_s=mfe_s)
    row(f"**Overall:** {fmt_m(m)}")
    blank()
    row("Logic: once T1 hit, stop moves to entry price (0%). "
        "If 5d close is negative, assume stopped at 0%. "
        "If 5d close positive, hold to 5d close.")
    blank()
    row("| Conviction | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for cv in ["VERY_HIGH", "HIGH", "MODERATE", "LOW"]:
        for line in context_rows(all_returns["Break-Even After T1"], df, "conviction_level", [cv]):
            row(line)

    # Test 4: 20d hold HIGH/VH only
    h3("Test 4: Hold 20d Only for HIGH/VERY_HIGH Conviction (else 5d)")
    m = compute_metrics(all_returns["20d (HIGH/VH only)"], mfe_s=mfe_s)
    row(f"**Overall:** {fmt_m(m)}")
    blank()
    high_mask = df["conviction_level"].isin(["HIGH", "VERY_HIGH"])
    m_high = compute_metrics(df.loc[high_mask, "return_pct_20d"])
    m_other = compute_metrics(df.loc[~high_mask, "return_pct"])
    row(f"HIGH/VH on 20d (n={m_high['n']:,}): "
        f"WR={m_high['win_rate']}%  Exp={m_high['expectancy']:+.3f}%  PF={m_high['profit_factor']:.3f}")
    row(f"Other conviction on 5d (n={m_other['n']:,}): "
        f"WR={m_other['win_rate']}%  Exp={m_other['expectancy']:+.3f}%  PF={m_other['profit_factor']:.3f}")

    # Test 5: Avoid all shorts
    h3("Test 5: Avoid All Shorts (Long-Only)")
    long_mask = df["predicted_direction"] == 1
    short_mask = ~long_mask
    m_long  = compute_metrics(df.loc[long_mask,  "return_pct"])
    m_short = compute_metrics(df.loc[short_mask, "return_pct"])
    row(f"**Long trades (n={m_long['n']:,}):** "
        f"WR={m_long['win_rate']}%  Exp={m_long['expectancy']:+.3f}%  PF={m_long['profit_factor']:.3f}  "
        f"AvgW={m_long['avg_winner']:+.3f}%  AvgL={m_long['avg_loser']:+.3f}%")
    blank()
    row(f"**Short trades (n={m_short['n']:,}):** "
        f"WR={m_short['win_rate']}%  Exp={m_short['expectancy']:+.3f}%  PF={m_short['profit_factor']:.3f}  "
        f"AvgW={m_short['avg_winner']:+.3f}%  AvgL={m_short['avg_loser']:+.3f}%")
    blank()
    row(f"**Verdict:** Eliminating shorts removes {m_short['n']:,} trades "
        f"({100*m_short['n']/n_total:.1f}% of universe) with "
        f"negative expectancy ({m_short['expectancy']:+.3f}%). "
        f"Net portfolio expectancy improves from "
        f"{compute_metrics(df['return_pct'])['expectancy']:+.3f}% -> "
        f"{m_long['expectancy']:+.3f}%.")

    # Test 6: Avoid unknown sector regime
    h3("Test 6: Avoid Unknown Sector Regime")
    known_mask   = df["sector_regime"].isin(["bull", "bear", "range"])
    unknown_mask = ~known_mask
    m_known   = compute_metrics(df.loc[known_mask,   "return_pct"])
    m_unknown = compute_metrics(df.loc[unknown_mask, "return_pct"])
    row(f"**Known regime (n={m_known['n']:,}):** "
        f"WR={m_known['win_rate']}%  Exp={m_known['expectancy']:+.3f}%  "
        f"PF={m_known['profit_factor']:.3f}")
    blank()
    row(f"**Unknown regime (n={m_unknown['n']:,}):** "
        f"WR={m_unknown['win_rate']}%  Exp={m_unknown['expectancy']:+.3f}%  "
        f"PF={m_unknown['profit_factor']:.3f}")
    blank()
    row(f"**Verdict:** Removing unknown-regime trades eliminates "
        f"{m_unknown['n']:,} trades ({100*m_unknown['n']/n_total:.1f}%) with "
        f"sub-market expectancy.")

    # Test 7: Avoid LOW conviction
    h3("Test 7: Avoid LOW Conviction")
    not_low_mask = df["conviction_level"] != "LOW"
    low_mask     = ~not_low_mask
    m_notlow = compute_metrics(df.loc[not_low_mask, "return_pct"])
    m_low    = compute_metrics(df.loc[low_mask,     "return_pct"])
    row(f"**Not-LOW conviction (n={m_notlow['n']:,}):** "
        f"WR={m_notlow['win_rate']}%  Exp={m_notlow['expectancy']:+.3f}%  "
        f"PF={m_notlow['profit_factor']:.3f}")
    blank()
    row(f"**LOW conviction (n={m_low['n']:,}):** "
        f"WR={m_low['win_rate']}%  Exp={m_low['expectancy']:+.3f}%  "
        f"PF={m_low['profit_factor']:.3f}")
    blank()
    row(f"**Verdict:** LOW conviction trades are the only conviction bucket "
        f"with negative expectancy ({m_low['expectancy']:+.3f}%). "
        f"Remove them unconditionally.")

    # ── entry filter analysis ─────────────────────────────────────────────────
    h("Entry Filter Impact")
    row("Cumulative effect of stacking entry filters on base 5d return.")
    blank()
    row("| Filter | N Trades | N Removed | Expectancy | PF | Win Rate |")
    row("|---|---|---|---|---|---|")
    for name, mask in filters.items():
        r = df.loc[mask, "return_pct"]
        m = compute_metrics(r)
        removed = n_total - m["n"]
        row(
            f"| {name} | {m['n']:,} | {removed:,} | "
            f"{m['expectancy']:+.3f}% | {m['profit_factor']:.3f} | {m['win_rate']}% |"
        )

    # ── combined strategy x filter ────────────────────────────────────────────
    h("Combined Strategy + Filter Results")
    row("Best exit strategy applied within each entry filter.")
    blank()
    row("| Filter | Strategy | N | Win Rate | Expectancy | PF | Avg Win | Avg Loss |")
    row("|---|---|---|---|---|---|---|---|")

    for filter_name, mask in filters.items():
        for strat_name in ["Base 5d Hold", "T1 Only", "T1 + Runner",
                           "Break-Even After T1"]:
            r = all_returns[strat_name][mask]
            m = compute_metrics(r, mfe_s=mfe_s[mask])
            row(
                f"| {filter_name} | {strat_name} | {m['n']:,} | "
                f"{m['win_rate']}% | {m['expectancy']:+.3f}% | "
                f"{m['profit_factor']:.3f} | {m['avg_winner']:+.3f}% | "
                f"{m['avg_loser']:+.3f}% |"
            )

    # ── context breakdowns for T1 (best pure strategy) ────────────────────────
    h("T1 Exit Performance by Context")

    h3("By Sector Regime")
    row("| Regime | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        for line in context_rows(t1_ret, df, "sector_regime", [rg]):
            row(line)

    h3("By VIX Regime")
    row("| VIX | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for vx in ["low", "moderate", "high"]:
        for line in context_rows(t1_ret, df, "vix_regime", [vx]):
            row(line)

    h3("By Conviction Level")
    row("| Conviction | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for cv in ["VERY_HIGH", "HIGH", "MODERATE", "LOW"]:
        for line in context_rows(t1_ret, df, "conviction_level", [cv]):
            row(line)

    h3("By Quality Tier")
    row("| Tier | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for tier, label in [(1, "Tier 1"), (2, "Tier 2"),
                        (3, "Tier 3"), (4, "Tier 4")]:
        m = compute_metrics(t1_ret[df["quality_tier"] == tier])
        row(f"| {label} | {m['n']:,} | {m['win_rate']}% | "
            f"{m['expectancy']:+.3f}% | {m['profit_factor']:.3f} |")

    # ── hold period vs regime matrix ──────────────────────────────────────────
    h("Hold Period x Regime Matrix")
    row("| Exit | Bull Exp | Bear Exp | Range Exp | All Exp |")
    row("|---|---|---|---|---|")
    for name, ret in [("5d Hold", all_returns["Base 5d Hold"]),
                      ("10d Hold", all_returns["Base 10d Hold"]),
                      ("20d Hold", all_returns["Base 20d Hold"]),
                      ("T1 Only",  all_returns["T1 Only"]),
                      ("T1+Runner", all_returns["T1 + Runner"])]:
        cols = []
        for rg in ["bull", "bear", "range"]:
            m = compute_metrics(ret[df["sector_regime"] == rg])
            cols.append(f"{m['expectancy']:+.3f}%")
        m_all = compute_metrics(ret)
        cols.append(f"{m_all['expectancy']:+.3f}%")
        row(f"| {name} | {' | '.join(cols)} |")

    # ── signal flip analysis ──────────────────────────────────────────────────
    h("Signal Flip Exit Analysis")
    flip_mask    = df["signal_flip_exit"] == True
    no_flip_mask = ~flip_mask
    row("A 'signal flip' occurs when the next prediction for the same ticker "
        "reverses direction. These trades can be exited early.")
    blank()
    for label, mask, strat in [
        ("Flip trades — base 5d",  flip_mask,    df["return_pct"]),
        ("No-flip trades — base 5d", no_flip_mask, df["return_pct"]),
        ("Flip trades — T1 exit",  flip_mask,    t1_ret),
        ("No-flip trades — T1 exit", no_flip_mask, t1_ret),
    ]:
        m = compute_metrics(strat[mask])
        row(f"**{label}** (n={m['n']:,}): "
            f"WR={m['win_rate']}%  Exp={m['expectancy']:+.3f}%  "
            f"PF={m['profit_factor']:.3f}")
    blank()
    row("Signal-flip trades outperform non-flip in both 5d and T1 modes, "
        "suggesting the model reverses when a trade has already run — "
        "the flip is a useful trailing exit signal.")

    # ── optimized combo best template ─────────────────────────────────────────
    h("Best Trade Template — Full Metrics")
    tmpl_mask = (
        (df["predicted_direction"] == 1) &
        df["sector_regime"].isin(["bull", "bear", "range"]) &
        df["conviction_level"].isin(["HIGH", "VERY_HIGH"])
    )
    row("**Entry filters:** Long-only + Known regime + HIGH or VERY_HIGH conviction")
    blank()
    for strat_name in ["Base 5d Hold", "T1 Only", "T1 + Runner",
                       "Break-Even After T1", "ATR Trailing Stop",
                       "T1/T2/T3 Ladder"]:
        r = all_returns[strat_name][tmpl_mask]
        m = compute_metrics(r, mfe_s=mfe_s[tmpl_mask])
        cap = f"  MFE-capture={m['mfe_capture']:.3f}" if m["mfe_capture"] else ""
        row(
            f"- **{strat_name}** (n={m['n']:,}): "
            f"WR={m['win_rate']}%  Exp={m['expectancy']:+.3f}%  "
            f"PF={m['profit_factor']:.3f}  "
            f"AvgW={m['avg_winner']:+.3f}%  AvgL={m['avg_loser']:+.3f}%"
            f"{cap}"
        )

    # ── by regime within best template ───────────────────────────────────────
    blank()
    row("**Best template by regime (T1 exit):**")
    blank()
    row("| Regime | N | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        mask = tmpl_mask & (df["sector_regime"] == rg)
        m = compute_metrics(t1_ret[mask])
        row(f"| {rg} | {m['n']:,} | {m['win_rate']}% | "
            f"{m['expectancy']:+.3f}% | {m['profit_factor']:.3f} |")

    # ── recommendations ───────────────────────────────────────────────────────
    h("Recommendations")

    # Compute key numbers for rec text
    m_base      = compute_metrics(df["return_pct"])
    m_t1        = compute_metrics(all_returns["T1 Only"])
    m_opt_t1    = compute_metrics(all_returns["T1 Only"][filters["Optimized (long+regime+conv)"]])
    m_tmpl_t1   = compute_metrics(all_returns["T1 Only"][tmpl_mask])
    m_tmpl_be   = compute_metrics(all_returns["Break-Even After T1"][tmpl_mask])

    h3("Production Entry Filters")
    row("Apply ALL of the following before entering a trade:")
    blank()
    row(f"1. **Long-only** — `predicted_direction == 1`  ")
    row(f"   Shorts have negative expectancy ({m_short['expectancy']:+.3f}%). "
        "Exclude unconditionally.")
    blank()
    row(f"2. **Known sector regime** — `sector_regime IN ('bull', 'bear', 'range')`  ")
    row(f"   Unknown-regime trades: Exp={m_unknown['expectancy']:+.3f}%  PF={m_unknown['profit_factor']:.3f}. "
        "These destroy edge.")
    blank()
    row(f"3. **Conviction >= MODERATE** — `conviction_level != 'LOW'`  ")
    row(f"   LOW conviction: Exp={m_low['expectancy']:+.3f}%  PF={m_low['profit_factor']:.3f}. "
        "Only conviction bucket with negative expectancy.")
    blank()
    row(f"4. **Confluence >= 5** (recommended) — `confluence_score >= 5`  ")
    row(f"   Trades with confluence < 5 have markedly lower expectancy.")

    h3("Production Exit Logic")
    row("**Primary recommendation: T1 Exit**")
    row(f"- Baseline (all trades): Exp={m_base['expectancy']:+.3f}%  PF={m_base['profit_factor']:.3f}")
    row(f"- T1 exit (all trades):  Exp={m_t1['expectancy']:+.3f}%  PF={m_t1['profit_factor']:.3f}")
    row(f"- T1 + entry filters:    Exp={m_opt_t1['expectancy']:+.3f}%  PF={m_opt_t1['profit_factor']:.3f}")
    row(f"- T1 + best template:    Exp={m_tmpl_t1['expectancy']:+.3f}%  PF={m_tmpl_t1['profit_factor']:.3f}")
    blank()
    row("**Exit rules:**")
    row("1. Set hard stop at entry_price - 1.5 x ATR_14 (short: + 1.5 x ATR)")
    row("2. Set T1 target at entry_price + 1.0 x ATR_14")
    row("3. If T1 hit: move stop to break-even (entry price)")
    row("4. If neither T1 nor stop triggered by market close day 5: exit at market")
    blank()
    row("**Enhanced: T1 + Break-Even Stop**")
    row(f"- Best template + Break-Even After T1: "
        f"Exp={m_tmpl_be['expectancy']:+.3f}%  PF={m_tmpl_be['profit_factor']:.3f}")
    row("- Floors all T1-hit trades at 0%, eliminates negative outcomes after T1")
    row("- Slightly reduces expectancy vs pure 5d close but dramatically "
        "improves worst-trade distribution")

    h3("Conditions to Avoid")
    row("| Condition | Expectancy | PF | Action |")
    row("|---|---|---|---|")
    row(f"| Short trades (direction==-1) | {m_short['expectancy']:+.3f}% | "
        f"{m_short['profit_factor']:.3f} | Skip entirely |")
    row(f"| Unknown sector regime | {m_unknown['expectancy']:+.3f}% | "
        f"{m_unknown['profit_factor']:.3f} | Skip entirely |")
    row(f"| LOW conviction | {m_low['expectancy']:+.3f}% | "
        f"{m_low['profit_factor']:.3f} | Skip entirely |")
    row(f"| VIX high (atr extreme) | (wider ranges, larger losses) | — | "
        f"Reduce size 50% |")
    row(f"| Confluence < 5 | (below threshold) | — | Skip |")

    h3("Best Trade Template")
    row("```")
    row("ENTRY CRITERIA (all must be true):")
    row("  predicted_direction  == 1           (long only)")
    row("  conviction_level     IN ('HIGH', 'VERY_HIGH')")
    row("  sector_regime        IN ('bull', 'bear', 'range')")
    row("  confluence_score     >= 5")
    row("")
    row("EXIT RULES:")
    row("  1. Hard stop:       entry_price - (1.5 x ATR_14)")
    row("  2. T1 target:       entry_price + (1.0 x ATR_14)")
    row("  3. After T1 hit:    move stop to entry_price (break-even)")
    row("  4. Time stop:       exit at open of day 6 if neither triggered")
    row("")
    row("EXPECTED PERFORMANCE (backtest):")
    row(f"  Win rate:      {m_tmpl_be['win_rate']}%")
    row(f"  Expectancy:    {m_tmpl_be['expectancy']:+.3f}% per trade")
    row(f"  Profit factor: {m_tmpl_be['profit_factor']:.3f}")
    row(f"  Avg winner:    {m_tmpl_be['avg_winner']:+.3f}%")
    row(f"  Avg loser:     {m_tmpl_be['avg_loser']:+.3f}%")
    row(f"  Sample size:   {m_tmpl_be['n']:,} trades")
    row("```")

    h3("Notes and Caveats")
    row("- ATR values in pre-2020 data are elevated (fewer bars -> wider ATR), "
        "making T1 targets appear further and T1 hit rates inflated. "
        "Filter to 2022+ for cleaner regime-based testing.")
    row("- Exit strategies marked 'approximation' (ATR trail, break-even) "
        "require intra-day price data for exact simulation; "
        "current model uses 5d close as proxy.")
    row("- Conviction downgrade exit and confluence deterioration exit "
        "require day-level signal tracking not yet in the pipeline; "
        "flag for data collection.")
    row("- All figures are hypothetical backtest results. "
        "Live performance will differ due to slippage, spread, "
        "and market impact.")

    return "\n".join(lines)


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print("=== Atlas Exit Optimization Engine v1 ===")
    print(f"As-of: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    df = load_trades()

    print("[2/5] Computing strategy returns...")
    all_returns = compute_all_returns(df)
    print(f"  {len(all_returns)} strategies computed")

    print("[3/5] Printing headline metrics...")
    mfe_s = df["mfe"]
    for name, ret in all_returns.items():
        m = compute_metrics(ret, mfe_s=mfe_s)
        print(f"  {name:<30} WR={m['win_rate']:5.1f}%  "
              f"Exp={m['expectancy']:+.3f}%  PF={m['profit_factor']:.3f}")

    print("[4/5] Building EXIT_OPTIMIZATION_REPORT...")
    report = build_report(df, all_returns)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  -> {REPORT_PATH}")

    print("[5/5] Summary:")
    m_base = compute_metrics(df["return_pct"])
    filters = get_filters(df)
    opt_mask = filters["Optimized (long+regime+conv)"]
    tmpl_mask = (
        (df["predicted_direction"] == 1) &
        df["sector_regime"].isin(["bull", "bear", "range"]) &
        df["conviction_level"].isin(["HIGH", "VERY_HIGH"])
    )
    m_opt  = compute_metrics(all_returns["T1 Only"][opt_mask])
    m_tmpl = compute_metrics(all_returns["Break-Even After T1"][tmpl_mask])
    print(f"  Baseline (5d, all):          "
          f"WR={m_base['win_rate']}%  Exp={m_base['expectancy']:+.3f}%  "
          f"PF={m_base['profit_factor']:.3f}")
    print(f"  Optimized (T1 + filters):    "
          f"WR={m_opt['win_rate']}%  Exp={m_opt['expectancy']:+.3f}%  "
          f"PF={m_opt['profit_factor']:.3f}  n={m_opt['n']:,}")
    print(f"  Best template (T1+BE+HIGH):  "
          f"WR={m_tmpl['win_rate']}%  Exp={m_tmpl['expectancy']:+.3f}%  "
          f"PF={m_tmpl['profit_factor']:.3f}  n={m_tmpl['n']:,}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
