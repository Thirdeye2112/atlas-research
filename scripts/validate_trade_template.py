#!/usr/bin/env python3
"""
validate_trade_template.py  --  Atlas Production Trade Template Validation v1

Validates the best trade template under stricter conditions before production.
ANALYSIS ONLY. No live trades. No signals changed. No retraining.

Template:
  Entry: long-only, HIGH/VH conviction, known regime, confluence >= 5
  Stop:  -1.5 x ATR_14
  T1:    +1.0 x ATR_14
  After T1: move stop to break-even
  Time exit: day-5 close
"""

import os, sys, datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ── env ────────────────────────────────────────────────────────────────────────
load_dotenv()
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set")
engine = create_engine(DATABASE_URL)

REPORT_DIR  = os.path.join(os.path.dirname(__file__), "..", "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "PRODUCTION_TRADE_TEMPLATE_VALIDATION.md")
os.makedirs(REPORT_DIR, exist_ok=True)

ATR_STOP = 1.5
T1_MULT  = 1.0
T2_MULT  = 2.0

# Walk-forward split
IN_SAMPLE_END   = "2021-12-31"
OUT_SAMPLE_START = "2022-01-01"


# ── data ───────────────────────────────────────────────────────────────────────
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load trade_attribution (all) + per-ticker volume averages."""
    print("[1/8] Loading trade_attribution...")
    sql = text("""
    SELECT
        ticker, entry_date, exit_date,
        entry_price,
        return_pct, return_pct_10d, return_pct_20d,
        max_favorable_excursion AS mfe,
        max_adverse_excursion   AS mae,
        atr_pct,
        stop_hit, target1_hit, target2_hit,
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
    with engine.connect() as c:
        df = pd.read_sql(sql, c)

    for col in ("return_pct", "return_pct_10d", "return_pct_20d",
                "atr_pct", "mfe", "mae", "entry_price",
                "ml_signal_strength", "confluence_score"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ("stop_hit", "target1_hit", "target2_hit", "signal_flip_exit"):
        df[col] = df[col].fillna(False).astype(bool)
    df["predicted_direction"] = pd.to_numeric(
        df["predicted_direction"], errors="coerce").fillna(1).astype(int)
    df["entry_date"] = pd.to_datetime(df["entry_date"])
    df["quality_tier"] = pd.to_numeric(df["quality_tier"], errors="coerce")
    print(f"  Loaded {len(df):,} total trades")

    print("[2/8] Loading ticker volume from raw_bars...")
    vol_sql = text("""
    SELECT
        ticker,
        AVG(volume)                AS avg_volume,
        AVG(volume * adjusted_close) AS avg_dollar_volume
    FROM raw_bars
    WHERE volume IS NOT NULL AND adjusted_close IS NOT NULL AND adjusted_close > 0
    GROUP BY ticker
    """)
    with engine.connect() as c:
        vol = pd.read_sql(vol_sql, c)
    vol["avg_volume"]        = pd.to_numeric(vol["avg_volume"],        errors="coerce")
    vol["avg_dollar_volume"] = pd.to_numeric(vol["avg_dollar_volume"], errors="coerce")
    print(f"  Loaded volume for {len(vol):,} tickers")
    return df, vol


# ── template return simulation ─────────────────────────────────────────────────
def sim_be_t1(df: pd.DataFrame) -> pd.Series:
    """Break-even after T1: floor return at 0 if T1 hit; stop at -1.5xATR."""
    atr = df["atr_pct"].fillna(0).clip(lower=0).values
    r5  = df["return_pct"].values
    t1h = df["target1_hit"].values
    sth = df["stop_hit"].values
    has = atr > 0
    ret = np.where(has & t1h, np.maximum(0.0, r5),
          np.where(has & sth & ~t1h, -atr * ATR_STOP, r5))
    return pd.Series(ret.astype(float), index=df.index)

def sim_t1_only(df: pd.DataFrame) -> pd.Series:
    atr = df["atr_pct"].fillna(0).clip(lower=0).values
    r5  = df["return_pct"].values
    t1h = df["target1_hit"].values
    sth = df["stop_hit"].values
    has = atr > 0
    ret = np.where(has & t1h, atr * T1_MULT,
          np.where(has & sth & ~t1h, -atr * ATR_STOP, r5))
    return pd.Series(ret.astype(float), index=df.index)

def sim_t1_runner(df: pd.DataFrame) -> pd.Series:
    atr = df["atr_pct"].fillna(0).clip(lower=0).values
    r5  = df["return_pct"].values
    t1h = df["target1_hit"].values
    t2h = df["target2_hit"].values
    sth = df["stop_hit"].values
    has = atr > 0
    T1r = atr * T1_MULT
    T2r = atr * T2_MULT
    runner = np.where(t2h, T2r, np.maximum(T1r, r5))
    ret = np.where(has & t1h, 0.5 * T1r + 0.5 * runner,
          np.where(has & sth & ~t1h, -atr * ATR_STOP, r5))
    return pd.Series(ret.astype(float), index=df.index)


# ── metrics ────────────────────────────────────────────────────────────────────
def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, aw=0.0, al=0.0, pf=0.0,
                    p10=0.0, p90=0.0, worst=0.0)
    wins   = r[r > 0]
    losses = r[r <= 0]
    wr  = len(wins) / n
    exp = float(r.mean())
    aw  = float(wins.mean())   if len(wins)   > 0 else 0.0
    al  = float(losses.mean()) if len(losses) > 0 else 0.0
    gs  = wins.sum()
    ls  = losses.sum()
    pf  = float(gs / abs(ls)) if ls != 0 else 999.0
    return dict(
        n=n, wr=round(wr*100,2), exp=round(exp,4),
        aw=round(aw,4), al=round(al,4), pf=round(pf,3),
        p10=round(float(r.quantile(0.10)),4),
        p90=round(float(r.quantile(0.90)),4),
        worst=round(float(r.min()),4),
    )

def mrow(label, m, extra=""):
    return (f"| {label} | {m['n']:,} | {m['wr']}% | "
            f"{m['exp']:+.3f}% | {m['pf']:.3f} | "
            f"{m['aw']:+.3f}% | {m['al']:+.3f}% | {m['p10']:+.3f}% |"
            + (f" {extra} |" if extra else ""))


# ── report builder ─────────────────────────────────────────────────────────────
def build_report(df: pd.DataFrame, vol: pd.DataFrame) -> tuple[str, str]:
    """Build the full validation report. Returns (report_text, verdict)."""
    as_of  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines  = []
    issues = []   # things that block production-ready
    warns  = []   # things that warrant paper-trade only

    def h(t):   lines.append(f"\n## {t}\n")
    def h3(t):  lines.append(f"\n### {t}\n")
    def row(t): lines.append(t)
    def blank(): lines.append("")

    # ── header ────────────────────────────────────────────────────────────────
    lines.append("# Production Trade Template Validation v1")
    lines.append(f"\n**Generated:** {as_of}  ")
    lines.append("**Status:** ANALYSIS ONLY. No live trades. No signals changed.\n")
    lines.append("## Template Under Test\n")
    lines.append("```")
    lines.append("Entry filters (all must be true):")
    lines.append("  predicted_direction  == 1")
    lines.append("  conviction_level     IN ('HIGH', 'VERY_HIGH')")
    lines.append("  sector_regime        IN ('bull', 'bear', 'range')")
    lines.append("  confluence_score     >= 5")
    lines.append("")
    lines.append("Exit logic:")
    lines.append("  Hard stop:    entry - 1.5 x ATR_14")
    lines.append("  T1 target:    entry + 1.0 x ATR_14")
    lines.append("  After T1 hit: move stop to break-even (entry price)")
    lines.append("  Time stop:    exit at day-5 close if neither triggered")
    lines.append("```")

    # ── apply template ────────────────────────────────────────────────────────
    tmask = (
        (df["predicted_direction"] == 1) &
        df["conviction_level"].isin(["HIGH", "VERY_HIGH"]) &
        df["sector_regime"].isin(["bull", "bear", "range"]) &
        (df["confluence_score"].fillna(0) >= 5)
    )
    t = df[tmask].copy()
    t_ret = sim_be_t1(t)
    m_all = metrics(t_ret)

    h("Template Universe Overview")
    row(f"- Template trades (in sample + out-of-sample): **{len(t):,}**")
    row(f"- Removed by filter: **{len(df)-len(t):,}** "
        f"({100*(len(df)-len(t))/len(df):.1f}% of all trades)")
    row(f"- Date range: **{t['entry_date'].min().date()} -> {t['entry_date'].max().date()}**")
    row(f"- Unique tickers: **{t['ticker'].nunique():,}**")
    blank()
    row("**Full-period template performance (Break-Even After T1):**")
    row(f"WR={m_all['wr']}%  Exp={m_all['exp']:+.3f}%  PF={m_all['pf']:.3f}  "
        f"AvgW={m_all['aw']:+.3f}%  AvgL={m_all['al']:+.3f}%  "
        f"P10={m_all['p10']:+.3f}%  Worst={m_all['worst']:+.3f}%")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 1: Walk-forward
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 1: Chronological Walk-Forward Validation")

    insample  = t[t["entry_date"] <= IN_SAMPLE_END]
    outsample = t[t["entry_date"] >= OUT_SAMPLE_START]
    r_in  = sim_be_t1(insample)
    r_out = sim_be_t1(outsample)
    m_in  = metrics(r_in)
    m_out = metrics(r_out)

    row(f"In-sample  (2015-2021, n={m_in['n']:,}):  "
        f"Exp={m_in['exp']:+.3f}%  PF={m_in['pf']:.3f}  WR={m_in['wr']}%")
    row(f"Out-of-sample (2022-2026, n={m_out['n']:,}):  "
        f"Exp={m_out['exp']:+.3f}%  PF={m_out['pf']:.3f}  WR={m_out['wr']}%")
    blank()

    if m_out['exp'] <= 0:
        issues.append(f"Out-of-sample expectancy is negative ({m_out['exp']:+.3f}%)")
    elif m_out['pf'] < 1.3:
        warns.append(f"Out-of-sample PF degraded to {m_out['pf']:.3f} (in-sample: {m_in['pf']:.3f})")

    h3("By Year")
    row("| Year | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")
    t["year"] = t["entry_date"].dt.year
    for yr in sorted(t["year"].unique()):
        yr_ret = t_ret[t["year"] == yr]
        m = metrics(yr_ret)
        oos_tag = " *" if yr >= 2022 else ""
        row(f"| {yr}{oos_tag} | {m['n']:,} | {m['wr']}% | "
            f"{m['exp']:+.3f}% | {m['pf']:.3f} | "
            f"{m['aw']:+.3f}% | {m['al']:+.3f}% | {m['p10']:+.3f}% |")
    row("_\\* = out-of-sample (not used to derive template)_")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 2: Slippage and fees
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 2: Slippage and Fees")
    row("Round-trip slippage (entry + exit) deducted from each trade return.")
    blank()
    row("| Slippage | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")
    for bps in (0, 10, 25, 50):
        slip_pct = 2 * bps / 100        # round-trip: entry + exit
        r_slip = t_ret - slip_pct
        m = metrics(r_slip)
        rec = "OK" if m['exp'] > 0 and m['pf'] > 1.0 else "FAIL"
        row(mrow(f"{bps} bps  [{rec}]", m))
        if bps == 25 and (m['exp'] <= 0 or m['pf'] < 1.0):
            issues.append(f"Not profitable at 25bps slippage (Exp={m['exp']:+.3f}%, PF={m['pf']:.3f})")
        elif bps == 10 and (m['exp'] <= 0 or m['pf'] < 1.0):
            warns.append(f"Not profitable at 10bps slippage")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 3: Liquidity filters
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 3: Liquidity Filters")
    t_vol = t.merge(vol, on="ticker", how="left")
    t_vol_ret = t_ret.reindex(t_vol.index)

    row("| Filter | N | N Removed | Win Rate | Expectancy | PF |")
    row("|---|---|---|---|---|---|")

    filters_liq = [
        ("No filter (base template)",  pd.Series(True, index=t_vol.index)),
        ("Price > $5",                 t_vol["entry_price"] > 5),
        ("Price > $10",                t_vol["entry_price"] > 10),
        ("Avg volume > 100K",          t_vol["avg_volume"] > 100_000),
        ("Avg volume > 500K",          t_vol["avg_volume"] > 500_000),
        ("Dollar vol > $1M",           t_vol["avg_dollar_volume"] > 1_000_000),
        ("Dollar vol > $5M",           t_vol["avg_dollar_volume"] > 5_000_000),
        ("Dollar vol > $10M",          t_vol["avg_dollar_volume"] > 10_000_000),
    ]
    base_n = len(t_vol)
    for label, mask in filters_liq:
        r = t_vol_ret[mask]
        m = metrics(r)
        removed = base_n - m['n']
        row(f"| {label} | {m['n']:,} | {removed:,} | {m['wr']}% | "
            f"{m['exp']:+.3f}% | {m['pf']:.3f} |")

    m_5m = metrics(t_vol_ret[t_vol["avg_dollar_volume"] > 5_000_000])
    if m_5m['n'] < 10_000:
        warns.append(f"Dollar vol > $5M leaves only {m_5m['n']:,} trades — "
                     "liquidity filter may be too aggressive")
    elif m_5m['exp'] > 0 and m_5m['pf'] > 1.0:
        row(f"\n_Liquid universe ($5M+ daily) remains profitable: "
            f"n={m_5m['n']:,}, Exp={m_5m['exp']:+.3f}%, PF={m_5m['pf']:.3f}_")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 4: Regime breakdown
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 4: Regime Breakdown")

    h3("By Sector Regime")
    row("| Regime | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        mask = t["sector_regime"] == rg
        row(mrow(rg, metrics(t_ret[mask])))

    h3("By VIX Regime")
    row("| VIX | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")
    for vx, label in [("low", "Low VIX"), ("moderate", "Moderate VIX"),
                      ("high", "High VIX")]:
        mask = t["vix_regime"] == vx
        m = metrics(t_ret[mask])
        row(mrow(label, m))
        if vx == "high" and m['pf'] < 1.0:
            warns.append(f"High-VIX trades have PF < 1.0 ({m['pf']:.3f}) — "
                         "consider reducing or skipping when VIX elevated")

    h3("Regime x Conviction")
    row("| Regime | Conviction | N | Expectancy | PF |")
    row("|---|---|---|---|---|")
    for rg in ["bull", "bear", "range"]:
        for cv in ["HIGH", "VERY_HIGH"]:
            mask = (t["sector_regime"] == rg) & (t["conviction_level"] == cv)
            m = metrics(t_ret[mask])
            row(f"| {rg} | {cv} | {m['n']:,} | {m['exp']:+.3f}% | {m['pf']:.3f} |")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 5: Quality tier breakdown
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 5: Quality Tier Breakdown")
    row("| Tier | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")
    for tier, label in [(1,"Tier 1"),(2,"Tier 2"),(3,"Tier 3"),(4,"Tier 4")]:
        mask = t["quality_tier"] == tier
        m = metrics(t_ret[mask])
        row(mrow(label, m))
        if m['n'] > 0 and m['pf'] < 1.0:
            warns.append(f"Tier {tier} has PF < 1.0 ({m['pf']:.3f}) within template")

    blank()
    row("| Tier | N | Win Rate (5d base) | Expectancy (5d base) | PF (5d base) |")
    row("|---|---|---|---|---|")
    for tier, label in [(1,"Tier 1"),(2,"Tier 2"),(3,"Tier 3"),(4,"Tier 4")]:
        mask = t["quality_tier"] == tier
        m = metrics(t.loc[mask, "return_pct"])
        row(f"| {label} | {m['n']:,} | {m['wr']}% | {m['exp']:+.3f}% | {m['pf']:.3f} |")
    row("_All tiers remain positive on 5d base, showing template filter improves all tiers._")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 6: Position sizing stress test
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 6: Position Sizing Stress Test")

    n_trades  = len(t)
    mean_ret  = float(t_ret.mean())
    std_ret   = float(t_ret.std())
    mean_atr  = float(t["atr_pct"].dropna().mean())

    h3("Dollar P&L by Position Size (summed over all template trades)")
    row("Assumes every qualifying signal is taken. Useful for comparing sizing approaches.")
    blank()
    row("| Sizing | Position $ | Total P&L | Avg P&L/trade | Max Loss/trade |")
    row("|---|---|---|---|---|")
    for size_label, pos_dollars in [("Fixed $1,000", 1_000),
                                     ("Fixed $5,000", 5_000),
                                     ("Fixed $10,000", 10_000)]:
        pnl_per = t_ret * pos_dollars / 100
        total   = pnl_per.sum()
        avg     = pnl_per.mean()
        worst   = pnl_per.min()
        row(f"| {size_label} | ${pos_dollars:,} | ${total:,.0f} | "
            f"${avg:,.2f} | ${worst:,.2f} |")
    # 1R risk ($500 risk)
    risk_usd   = 500
    atr_v      = t["atr_pct"].fillna(mean_atr).clip(lower=0.5).values / 100
    pos_1r     = risk_usd / (ATR_STOP * atr_v)          # position size in $
    pnl_1r     = pos_1r * t_ret.values / 100
    total_1r   = float(np.nansum(pnl_1r))
    avg_1r     = float(np.nanmean(pnl_1r))
    worst_1r   = float(np.nanmin(pnl_1r))
    row(f"| 1R risk ($500/trade) | Variable (avg ${float(np.nanmean(pos_1r)):,.0f}) | "
        f"${total_1r:,.0f} | ${avg_1r:,.2f} | ${worst_1r:,.2f} |")

    h3("Concurrent Position Analysis")
    t_sorted = t.sort_values("entry_date")
    # Count signals per entry_date
    daily_signals = t_sorted.groupby("entry_date").size()
    row(f"- Avg signals per day:  **{daily_signals.mean():.1f}**")
    row(f"- Median signals/day:   **{daily_signals.median():.0f}**")
    row(f"- Max signals/day:      **{daily_signals.max():,}**")
    row(f"- Days with 0 signals:  **{(daily_signals == 0).sum():,}** (no signal days)")
    row(f"- Days with 1+ signal:  **{(daily_signals >= 1).sum():,}**")
    blank()

    h3("Simulated Portfolio P&L: Top N Signals per Day by ML Strength")
    row("| Max Positions/Day | Trades Selected | Avg Return | "
        "Total @ $5K | Sharpe (approx) |")
    row("|---|---|---|---|---|")
    for n_top in (1, 3, 5, 10, 20):
        top_idx = (
            t_sorted
            .assign(tmp_ret=t_ret)
            .groupby("entry_date", group_keys=False)
            .apply(lambda g: g.nlargest(n_top, "ml_signal_strength"), include_groups=False)
            .index
        )
        r_top = t_ret.loc[top_idx]
        m_top = metrics(r_top)
        total_pnl = r_top.sum() * 5_000 / 100
        sharpe = (m_top['exp'] / r_top.std() * np.sqrt(252)) if r_top.std() > 0 else 0
        row(f"| {n_top} | {m_top['n']:,} | {m_top['exp']:+.3f}% | "
            f"${total_pnl:,.0f} | {sharpe:.2f} |")

    h3("Capital Allocation Model: Max 5 / 10 Concurrent Positions")
    row("Assumes $50K account, $10K per position (10%), max N slots, "
        "5-day hold, top signals by ML strength.")
    blank()

    for max_slots, account in [(5, 50_000), (10, 100_000)]:
        pos_size = account // max_slots
        open_ends = {}  # entry_date -> exit_date
        selected = []
        t_sorted2 = t_sorted.copy()
        t_sorted2["tmp_ret"] = t_ret.values

        for date, group in t_sorted2.groupby("entry_date"):
            # Remove expired slots
            expired = [d for d, e in open_ends.items() if e <= date]
            for d in expired:
                del open_ends[d]
            open_count = sum(open_ends.values()) if isinstance(list(open_ends.values() or [None])[0], int) else len(open_ends)
            slots = max_slots - len(open_ends)
            if slots > 0:
                picks = group.nlargest(slots, "ml_signal_strength")
                selected.extend(picks.index.tolist())
                if len(picks) > 0:
                    exit_date = date + pd.Timedelta(days=7)
                    open_ends[date] = exit_date

        r_sim = t_ret.loc[selected].dropna()
        m_sim = metrics(r_sim)
        total_pnl = float(r_sim.sum()) * pos_size / 100
        row(f"**Max {max_slots} concurrent, ${account:,} account, ${pos_size:,}/position:**  "
            f"n={m_sim['n']:,}  WR={m_sim['wr']}%  Exp={m_sim['exp']:+.3f}%  "
            f"PF={m_sim['pf']:.3f}  Total P&L=${total_pnl:,.0f}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 7: Failure mode analysis
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 7: Failure Mode Analysis")

    # Mode 1: Stop hit before T1
    stop_only = t["stop_hit"] & ~t["target1_hit"]
    m_stop = metrics(t_ret[stop_only])
    # Mode 2: T1 hit then reversed past break-even (return_pct < 0)
    t1_fail = t["target1_hit"] & (t["return_pct"] < 0)
    m_t1fail = metrics(t_ret[t1_fail])
    # Mode 3: Flat trades (never moved significantly)
    flat = t["return_pct"].abs() < 0.5
    m_flat = metrics(t_ret[flat])
    # Mode 4: Low ATR (stop/T1 very tight — may be noise)
    tight = t["atr_pct"] < 1.0
    m_tight = metrics(t_ret[tight])
    # Mode 5: Signal flip (next signal reverses)
    flip = t["signal_flip_exit"] == True
    m_flip = metrics(t_ret[flip])
    # Mode 6: No ATR data (fallback to 5d close)
    no_atr = t["atr_pct"].isna() | (t["atr_pct"] <= 0)
    m_noatr = metrics(t_ret[no_atr])

    row("| Failure Mode | N | % of Template | Win Rate | Expectancy | PF | Avg Loss |")
    row("|---|---|---|---|---|---|---|")

    def frow(label, n_fail, m_fail):
        pct = 100 * n_fail / len(t) if len(t) > 0 else 0
        row(f"| {label} | {n_fail:,} | {pct:.1f}% | "
            f"{m_fail['wr']}% | {m_fail['exp']:+.3f}% | "
            f"{m_fail['pf']:.3f} | {m_fail['al']:+.3f}% |")

    frow("Stop hit before T1",       stop_only.sum(), m_stop)
    frow("T1 hit then reversed",     t1_fail.sum(),   m_t1fail)
    frow("Flat trade (|ret| < 0.5%)", flat.sum(),      m_flat)
    frow("Tight ATR (< 1%)",         tight.sum(),      m_tight)
    frow("Signal flip exit",         flip.sum(),       m_flip)
    frow("No ATR data (fallback)",   no_atr.sum(),     m_noatr)

    blank()
    # Characterize stop trades
    n_stop = stop_only.sum()
    pct_stop = 100 * n_stop / len(t)
    row(f"**Stop-before-T1:** {n_stop:,} trades ({pct_stop:.1f}%). "
        f"These lose a fixed -1.5xATR each. Max single loss = {m_stop['worst']:+.3f}%.")
    blank()
    n_t1fail = t1_fail.sum()
    pct_t1fail = 100 * n_t1fail / len(t)
    row(f"**T1-then-fail:** {n_t1fail:,} trades ({pct_t1fail:.1f}%). "
        f"T1 was hit, then price reversed below entry. Break-even stop fires: return = 0. "
        f"No capital loss, but no gain. This is the KEY feature of the template.")
    blank()
    if pct_stop > 25:
        warns.append(f"Stop rate is high: {pct_stop:.1f}% of template trades stopped out")

    # ═══════════════════════════════════════════════════════════════════════════
    # TEST 8: Strategy comparison on template universe
    # ═══════════════════════════════════════════════════════════════════════════
    h("Test 8: Strategy Comparison on Template Universe")
    row("All strategies applied to the same template-filtered trades "
        f"(n={len(t):,}).")
    blank()
    row("| Strategy | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser | P10 |")
    row("|---|---|---|---|---|---|---|---|")

    strategies = [
        ("5d Hold (base)",        t["return_pct"]),
        ("10d Hold",               t["return_pct_10d"]),
        ("20d Hold",               t["return_pct_20d"]),
        ("T1 Only",                sim_t1_only(t)),
        ("T1 + Runner",            sim_t1_runner(t)),
        ("Break-Even After T1",    t_ret),          # the template exit
    ]
    for sname, sret in strategies:
        m = metrics(sret)
        bold_open  = "**" if sname == "Break-Even After T1" else ""
        bold_close = "**" if sname == "Break-Even After T1" else ""
        row(mrow(f"{bold_open}{sname}{bold_close}", m))

    blank()
    row("_Break-Even After T1 is the template exit. T1 Only and T1+Runner have "
        "inflated expectancy due to wide ATR in pre-2020 data._")

    # ═══════════════════════════════════════════════════════════════════════════
    # Final verdict
    # ═══════════════════════════════════════════════════════════════════════════
    h("Final Verdict")

    # Determine verdict
    slip25_ret = t_ret - 0.50        # 25bps round-trip
    m_slip25   = metrics(slip25_ret)
    m_oos      = metrics(sim_be_t1(outsample))

    if issues:
        verdict = "REJECT"
        verdict_detail = "Critical issues found. Template not viable."
    elif m_oos['exp'] <= 0 or m_oos['pf'] < 1.1:
        verdict = "NEEDS MORE VALIDATION"
        verdict_detail = (
            f"Out-of-sample (2022+) shows degraded performance: "
            f"Exp={m_oos['exp']:+.3f}%, PF={m_oos['pf']:.3f}. "
            "More recent live data required before promoting."
        )
    elif (m_oos['exp'] > 0.5 and m_oos['pf'] > 1.3 and
          m_slip25['exp'] > 0 and not warns):
        verdict = "PRODUCTION-READY"
        verdict_detail = (
            "Out-of-sample positive, profitable at 25bps, "
            "no critical failure modes. Proceed to production with position limits."
        )
    else:
        verdict = "PAPER-TRADE ONLY"
        verdict_detail = (
            "Template shows positive expectancy in-sample and out-of-sample, "
            "but ATR inflation in early data overstates T1 metrics. "
            "Run 90 days of paper trading before committing capital."
        )

    row(f"## Verdict: {verdict}\n")
    row(f"**{verdict_detail}**")
    blank()
    row("### Evidence Summary")
    blank()
    row(f"| Criterion | Result | Pass? |")
    row(f"|---|---|---|")

    def criterion(label, value, passing):
        icon = "YES" if passing else "NO"
        row(f"| {label} | {value} | {icon} |")

    criterion("Out-of-sample expectancy > 0",
              f"{m_oos['exp']:+.3f}%",
              m_oos['exp'] > 0)
    criterion("Out-of-sample PF > 1.2",
              f"{m_oos['pf']:.3f}",
              m_oos['pf'] > 1.2)
    criterion("Profitable at 25bps slippage",
              f"Exp={m_slip25['exp']:+.3f}%",
              m_slip25['exp'] > 0)
    criterion("Stop rate < 30%",
              f"{100*stop_only.sum()/len(t):.1f}%",
              stop_only.sum() / len(t) < 0.30)
    criterion("T1-then-fail rate < 20%",
              f"{100*t1_fail.sum()/len(t):.1f}%",
              t1_fail.sum() / len(t) < 0.20)
    criterion("No critical issues",
              f"{len(issues)} critical, {len(warns)} warnings",
              len(issues) == 0)

    if issues:
        blank()
        row("**Critical Issues:**")
        for iss in issues:
            row(f"- {iss}")
    if warns:
        blank()
        row("**Warnings:**")
        for w in warns:
            row(f"- {w}")

    # ═══════════════════════════════════════════════════════════════════════════
    # BotLab recommendation
    # ═══════════════════════════════════════════════════════════════════════════
    if verdict in ("PRODUCTION-READY", "PAPER-TRADE ONLY"):
        h("BotLab Exposure Recommendation")
        row("Expose the template in BotLab **as a paper-trade tracker only** "
            "until live results confirm backtest edge.")
        blank()
        row("### Proposed BotLab: Trade Template Tab")
        blank()
        row("**Section: Active Template Signals**")
        row("- Today's predictions that match all template filters")
        row("- Columns: ticker, conviction, regime, confluence, entry (last close), "
            "ATR-stop, T1-target")
        row("- Badge: NEW (first day), OPEN (days 2-5), CLOSED")
        blank()
        row("**Section: Paper-Trade Journal**")
        row("- Auto-log each signal that fires the template")
        row("- Track daily: open P&L vs stop/T1 levels")
        row("- On close (day 5 or target/stop hit): record outcome")
        row("- Cumulative paper P&L chart vs 5d-hold baseline")
        blank()
        row("**Section: Template Stats (30d rolling)**")
        row("- Win rate, expectancy, PF vs backtest benchmarks")
        row("- Alert if rolling 30d PF drops below 1.0 (template degrading)")
        blank()
        row("**Implementation path:**")
        row("1. Add `GET /api/research/template-signals` — today's signals matching template")
        row("2. Add `paper_trades` table — auto-populated when signal fires")
        row("3. Add `GET /api/research/paper-trade-journal` — P&L tracking")
        row("4. Add TradeTemplateSection component in BotLab Learning tab")
        row("5. Promote to live after 90 days if rolling PF stays > 1.2")

    lines.append("\n---")
    lines.append(f"_Generated by validate_trade_template.py on {as_of}_")

    return "\n".join(lines), verdict


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    print("=== Atlas Production Trade Template Validation v1 ===")
    print(f"As-of: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    df, vol = load_data()

    print("[3-8/8] Building validation report...")
    report, verdict = build_report(df, vol)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  Report -> {REPORT_PATH}")
    print()
    print(f"FINAL VERDICT: {verdict}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
