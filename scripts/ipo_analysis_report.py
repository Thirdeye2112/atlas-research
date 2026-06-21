"""
ipo_analysis_report.py
----------------------
Queries ipo_registry + ipo_performance and prints 7 analysis tables.
"""

import os
import sys
import statistics
import psycopg2
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv(override=True)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")

HORIZONS = [1, 5, 10, 20, 30, 60, 90, 120, 150, 180, 252]


# ── Formatting helpers ────────────────────────────────────────────────────────

def pct(v, dec=1):
    if v is None:
        return "   N/A"
    return ("%+.{}f%%".format(dec)) % float(v)


def num(v, dec=1):
    if v is None:
        return "   N/A"
    return ("%.{}f".format(dec)) % float(v)


def win_rate(vals):
    if not vals:
        return None
    return sum(1 for v in vals if v is not None and v > 0) / len(vals) * 100


def median(vals):
    clean = [float(v) for v in vals if v is not None]
    if not clean:
        return None
    return statistics.median(clean)


def mean(vals):
    clean = [float(v) for v in vals if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def sep(width=100):
    print("  " + "-" * width)


def header(title):
    print()
    print("  " + "=" * 100)
    print("  " + title)
    print("  " + "=" * 100)


# ── Load data ─────────────────────────────────────────────────────────────────

def load(cur):
    cur.execute("""
        SELECT
            r.ticker, r.company_name, r.ipo_date,
            r.day1_category, r.sector, r.lockup_days,
            p.return_1d, p.return_5d, p.return_10d, p.return_20d,
            p.return_30d, p.return_60d, p.return_90d, p.return_120d,
            p.return_150d, p.return_180d, p.return_252d,
            p.vs_spy_1d, p.vs_spy_5d, p.vs_spy_10d, p.vs_spy_20d,
            p.vs_spy_30d, p.vs_spy_60d, p.vs_spy_90d, p.vs_spy_120d,
            p.vs_spy_150d, p.vs_spy_180d, p.vs_spy_252d,
            p.max_dd_30d, p.max_dd_90d, p.max_dd_180d, p.max_dd_252d,
            p.days_to_first_peak, p.peak_return, p.peak_to_year_end,
            p.avg_volume_week1, p.avg_volume_month1, p.avg_volume_month3,
            p.volume_decay_pct, p.volatility_30d, p.volatility_90d,
            p.spy_regime_at_ipo, p.vix_at_ipo, p.sector_rs_at_ipo,
            p.year1_category
        FROM ipo_registry r
        JOIN ipo_performance p ON r.ticker = p.ticker
        ORDER BY r.ipo_date
    """)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ── Table 1 — Overall by Horizon ─────────────────────────────────────────────

def table1(rows):
    header("TABLE 1 — Overall Returns by Horizon (all IPOs, n=%d)" % len(rows))
    ret_cols = {
        1: "return_1d", 5: "return_5d", 10: "return_10d", 20: "return_20d",
        30: "return_30d", 60: "return_60d", 90: "return_90d",
        120: "return_120d", 150: "return_150d", 180: "return_180d", 252: "return_252d",
    }
    spy_cols = {
        1: "vs_spy_1d", 5: "vs_spy_5d", 10: "vs_spy_10d", 20: "vs_spy_20d",
        30: "vs_spy_30d", 60: "vs_spy_60d", 90: "vs_spy_90d",
        120: "vs_spy_120d", 150: "vs_spy_150d", 180: "vs_spy_180d", 252: "vs_spy_252d",
    }
    print("  %-10s  %9s  %9s  %7s  %9s  %4s" % (
        "Horizon", "Avg Ret", "Median", "Win%", "vs SPY", "n"))
    sep(60)
    for h in HORIZONS:
        vals    = [r[ret_cols[h]] for r in rows if r[ret_cols[h]] is not None]
        spy_vals = [r[spy_cols[h]] for r in rows if r[spy_cols[h]] is not None]
        if not vals:
            continue
        avg = mean(vals)
        med = median(vals)
        wr  = win_rate(vals)
        vs  = mean(spy_vals)
        print("  %-10s  %9s  %9s  %6.0f%%  %9s  %4d" % (
            "%dd" % h,
            pct(avg), pct(med),
            wr if wr is not None else 0,
            pct(vs), len(vals),
        ))


# ── Table 2 — By Day1 Category ───────────────────────────────────────────────

def table2(rows):
    header("TABLE 2 — Performance by Day1 Pop Category")
    cats = ["hot", "warm", "cold", "broken"]
    print("  %-10s  %4s  %9s  %9s  %9s  %9s  %9s" % (
        "Category", "n", "30d", "90d", "180d", "252d", "vsSPY252d"))
    sep(72)
    for cat in cats:
        group = [r for r in rows if r["day1_category"] == cat]
        if not group:
            print("  %-10s  %4d  (no data)" % (cat, 0))
            continue
        r30  = mean([r["return_30d"]  for r in group])
        r90  = mean([r["return_90d"]  for r in group])
        r180 = mean([r["return_180d"] for r in group])
        r252 = mean([r["return_252d"] for r in group])
        vs   = mean([r["vs_spy_252d"] for r in group])
        print("  %-10s  %4d  %9s  %9s  %9s  %9s  %9s" % (
            cat, len(group), pct(r30), pct(r90), pct(r180), pct(r252), pct(vs)))
    # Also print individual tickers for context
    print()
    print("  Individual tickers:")
    print("  %-8s  %-10s  %-7s  %9s  %9s  %9s  %9s" % (
        "Ticker", "Category", "Day1pop", "30d", "90d", "252d", "Year1"))
    sep(72)
    for r in sorted(rows, key=lambda x: (x["day1_category"] or "", x["ticker"])):
        print("  %-8s  %-10s  %+7.1f%%  %9s  %9s  %9s  %-9s" % (
            r["ticker"], r["day1_category"] or "?",
            float(r.get("return_1d") or 0),
            pct(r["return_30d"]), pct(r["return_90d"]),
            pct(r["return_252d"]), r["year1_category"] or "?",
        ))


# ── Table 3 — Best Entry Window (requires raw_bars query) ────────────────────

def table3(rows, cur):
    header("TABLE 3 — Best Entry Window (wait N days after IPO, buy and hold 30d)")
    offsets = [0, 5, 10, 20, 30, 60, 90]

    # For each offset, compute: close[offset+30] / close[offset] - 1
    results = {}
    for offset in offsets:
        fwd_rets = []
        for r in rows:
            ticker   = r["ticker"]
            ipo_date = r["ipo_date"]
            cur.execute("""
                SELECT close FROM raw_bars
                WHERE ticker = %s AND date >= %s
                ORDER BY date
                LIMIT %s
            """, (ticker, ipo_date, offset + 31))
            bars = [float(b[0]) for b in cur.fetchall()]
            if len(bars) >= offset + 31:
                entry = bars[offset]
                exit_ = bars[offset + 30]
                if entry > 0:
                    fwd_rets.append((exit_ - entry) / entry * 100)
        results[offset] = fwd_rets

    print("  %-12s  %9s  %9s  %7s  %4s" % (
        "Wait (days)", "Avg 30dFwd", "Median", "Win%", "n"))
    sep(55)
    best_avg = max(
        (mean(v), k) for k, v in results.items() if mean(v) is not None
    )
    for offset in offsets:
        vals = results[offset]
        avg  = mean(vals)
        med  = median(vals)
        wr   = win_rate(vals)
        marker = " <-- best avg" if offset == best_avg[1] else ""
        print("  %-12s  %9s  %9s  %6.0f%%  %4d%s" % (
            "Day %d" % offset,
            pct(avg), pct(med),
            wr if wr is not None else 0,
            len(vals), marker,
        ))

    print()
    print("  Note: small sample (n=%d IPOs); treat directionally only." % len(rows))


# ── Table 4 — Lockup Effect (days 150-210) ───────────────────────────────────

def table4(rows, cur):
    header("TABLE 4 — Lockup Effect (volume and price around days 150-210)")

    # For each ticker, compute 5 windows: pre-lockup, mid-lockup, post-lockup
    windows = [
        ("d100-120 (pre-pre)",  100, 120),
        ("d130-149 (pre)",      130, 149),
        ("d150-180 (lockup)",   150, 180),
        ("d181-210 (post)",     181, 210),
        ("d211-240 (post-post)",211, 240),
    ]

    print("  %-24s  %9s  %9s  %12s  %4s" % (
        "Window", "Avg Ret", "Vol vs Wk1", "Median Ret", "n"))
    sep(65)

    for label, start, end in windows:
        rets   = []
        vdecay = []
        for r in rows:
            ticker   = r["ticker"]
            ipo_date = r["ipo_date"]
            week1_vol = r["avg_volume_week1"]
            cur.execute("""
                SELECT date, close, volume FROM raw_bars
                WHERE ticker = %s AND date >= %s
                ORDER BY date
            """, (ticker, ipo_date))
            bars = cur.fetchall()
            if len(bars) < end:
                continue
            window_bars = bars[start:end]
            if not window_bars:
                continue

            # Return over the window
            open_p  = float(bars[start][1])
            close_p = float(bars[min(end, len(bars)) - 1][1])
            if open_p > 0:
                rets.append((close_p - open_p) / open_p * 100)

            # Volume vs week1
            if week1_vol and week1_vol > 0:
                avg_wvol = sum(int(b[2]) for b in window_bars) / len(window_bars)
                vdecay.append(avg_wvol / week1_vol * 100)

        avg_ret = mean(rets)
        avg_vd  = mean(vdecay)
        med_ret = median(rets)
        print("  %-24s  %9s  %9s  %12s  %4d" % (
            label,
            pct(avg_ret, 1),
            ("%+.0f%% of wk1" % avg_vd) if avg_vd else "   N/A",
            pct(med_ret, 1),
            len(rets),
        ))

    print()
    print("  Lockup expiry typically day 180 (default 180d); volume spike = insider selling pressure.")


# ── Table 5 — Market Regime ───────────────────────────────────────────────────

def table5(rows):
    header("TABLE 5 — Market Regime at IPO Date")

    # Bull vs Bear
    print("  By SPY Regime (price vs SMA-200 at IPO date):")
    print("  %-10s  %4s  %9s  %9s  %9s  %9s" % (
        "Regime", "n", "30d", "90d", "252d", "vsSPY252d"))
    sep(58)
    for regime in ["bull", "bear"]:
        group = [r for r in rows if r["spy_regime_at_ipo"] == regime]
        if not group:
            continue
        r30  = mean([r["return_30d"]  for r in group])
        r90  = mean([r["return_90d"]  for r in group])
        r252 = mean([r["return_252d"] for r in group])
        vs   = mean([r["vs_spy_252d"] for r in group])
        print("  %-10s  %4d  %9s  %9s  %9s  %9s" % (
            regime.upper(), len(group), pct(r30), pct(r90), pct(r252), pct(vs)))

    # Print ticker-level for transparency
    print()
    print("  Individual (sorted by regime):")
    for r in sorted(rows, key=lambda x: (x["spy_regime_at_ipo"] or "", x["ticker"])):
        vix_str = ("VIX=%.1f" % float(r["vix_at_ipo"])) if r["vix_at_ipo"] else "VIX=N/A"
        print("  %-8s  %-6s  %-10s  252d=%s  yr1=%-10s" % (
            r["ticker"], r["spy_regime_at_ipo"] or "?", vix_str,
            pct(r["return_252d"]), r["year1_category"] or "?",
        ))

    print()
    print("  Note: VIX historical data not available in raw_bars (only 2026-05-11+).")
    print("        Bear-market IPOs in sample: MRNA(2018-12), OTIS/CARR(2020-03 COVID), GEHC(2022-12).")


# ── Table 6 — By Sector ───────────────────────────────────────────────────────

def table6(rows):
    header("TABLE 6 — Performance by Sector")

    sectors = sorted(set(r["sector"] for r in rows if r["sector"]))
    print("  %-22s  %4s  %9s  %9s  %9s  %9s  %-10s" % (
        "Sector", "n", "Day1 pop", "90d", "252d", "vsSPY252d", "Year1 mix"))
    sep(82)

    # Day1 pop comes from return_1d (close vs open) — or we can recompute it
    for sector in sectors:
        group = [r for r in rows if r["sector"] == sector]
        r1   = mean([r["return_1d"]   for r in group])
        r90  = mean([r["return_90d"]  for r in group])
        r252 = mean([r["return_252d"] for r in group])
        vs   = mean([r["vs_spy_252d"] for r in group])
        y1   = "/".join(sorted(set(r["year1_category"] for r in group if r["year1_category"])))
        print("  %-22s  %4d  %9s  %9s  %9s  %9s  %-10s" % (
            sector, len(group), pct(r1), pct(r90), pct(r252), pct(vs), y1))

    print()
    print("  Ticker details:")
    for r in sorted(rows, key=lambda x: (x["sector"] or "", x["ticker"])):
        print("  %-8s  %-22s  day1=%s  90d=%s  252d=%s  [%s]" % (
            r["ticker"], (r["sector"] or "?")[:22],
            pct(r["return_1d"]), pct(r["return_90d"]),
            pct(r["return_252d"]), r["year1_category"] or "?",
        ))


# ── Table 7 — Peak Timing ────────────────────────────────────────────────────

def table7(rows):
    header("TABLE 7 — Peak Timing Analysis (within first 252 trading days)")

    peak_rets  = [float(r["peak_return"])        for r in rows if r["peak_return"]        is not None]
    peak_days  = [int(r["days_to_first_peak"])   for r in rows if r["days_to_first_peak"] is not None]
    drop_ye    = [float(r["peak_to_year_end"])   for r in rows if r["peak_to_year_end"]   is not None]
    dd_30      = [float(r["max_dd_30d"])         for r in rows if r["max_dd_30d"]         is not None]
    dd_90      = [float(r["max_dd_90d"])         for r in rows if r["max_dd_90d"]         is not None]
    dd_252     = [float(r["max_dd_252d"])        for r in rows if r["max_dd_252d"]        is not None]

    print("  %-28s  %9s  %9s" % ("Metric", "Mean", "Median"))
    sep(52)
    def row_fmt(label, vals):
        print("  %-28s  %9s  %9s" % (
            label, pct(mean(vals), 1), pct(median(vals), 1),
        ))

    print("  %-28s  %9s  %9s" % ("Metric", "Mean", "Median"))
    sep(52)
    print("  %-28s  %9s  %9s" % (
        "Days to first peak",
        "%.0fd" % mean(peak_days) if mean(peak_days) else "N/A",
        "%.0fd" % median(peak_days) if median(peak_days) else "N/A",
    ))
    row_fmt("Peak return (vs day1 close)", peak_rets)
    row_fmt("Drop: peak → year-end",       drop_ye)
    row_fmt("Max drawdown d0-30",          dd_30)
    row_fmt("Max drawdown d0-90",          dd_90)
    row_fmt("Max drawdown d0-252",         dd_252)

    # Per-ticker peak table
    print()
    print("  Per-ticker:")
    print("  %-8s  %-28s  %7s  %8s  %8s  %9s  %9s" % (
        "Ticker", "Company", "Peak@day", "PeakRet", "Drop→YE", "MaxDD30", "MaxDD90"))
    sep(85)
    for r in sorted(rows, key=lambda x: -(float(x["peak_return"] or 0))):
        print("  %-8s  %-28s  %7s  %8s  %8s  %9s  %9s" % (
            r["ticker"], (r["company_name"] or "")[:28],
            "@d%d" % int(r["days_to_first_peak"]) if r["days_to_first_peak"] else "?",
            pct(r["peak_return"]),
            pct(r["peak_to_year_end"]),
            pct(r["max_dd_30d"]),
            pct(r["max_dd_90d"]),
        ))

    # Volume decay analysis
    print()
    print("  Volume decay (month3 vs week1 — measures liquidity drying up):")
    print("  %-8s  %12s  %12s  %12s  %12s" % (
        "Ticker", "Vol Wk1", "Vol Mo1", "Vol Mo3", "Decay %"))
    sep(60)
    for r in rows:
        vw1 = r["avg_volume_week1"]
        vm1 = r["avg_volume_month1"]
        vm3 = r["avg_volume_month3"]
        vd  = r["volume_decay_pct"]
        def fmv(v):
            if v is None: return "     N/A"
            v = int(v)
            if v >= 1_000_000: return "%7.1fM" % (v / 1_000_000)
            if v >= 1_000:     return "%7.1fK" % (v / 1_000)
            return "%7d" % v
        print("  %-8s  %12s  %12s  %12s  %12s" % (
            r["ticker"], fmv(vw1), fmv(vm1), fmv(vm3),
            ("%+.1f%%" % float(vd)) if vd is not None else "     N/A",
        ))


# ── Summary box ───────────────────────────────────────────────────────────────

def summary(rows):
    header("SUMMARY — Key Findings (n=%d IPOs, 2015-2022)" % len(rows))

    r252  = [float(r["return_252d"])  for r in rows if r["return_252d"]  is not None]
    vs252 = [float(r["vs_spy_252d"])  for r in rows if r["vs_spy_252d"]  is not None]
    r90   = [float(r["return_90d"])   for r in rows if r["return_90d"]   is not None]
    dd90  = [float(r["max_dd_90d"])   for r in rows if r["max_dd_90d"]   is not None]
    pks   = [float(r["peak_return"])  for r in rows if r["peak_return"]  is not None]

    y1 = defaultdict(int)
    for r in rows:
        y1[r["year1_category"] or "unknown"] += 1

    print("  Avg 252d return  : %s  (median %s)" % (pct(mean(r252)), pct(median(r252))))
    print("  Avg vs SPY 252d  : %s  (median %s)" % (pct(mean(vs252)), pct(median(vs252))))
    print("  Avg 90d return   : %s  (median %s)" % (pct(mean(r90)), pct(median(r90))))
    print("  Avg max DD 90d   : %s  (median %s)" % (pct(mean(dd90)), pct(median(dd90))))
    print("  Avg peak return  : %s  (median %s)" % (pct(mean(pks)), pct(median(pks))))
    print()
    print("  Year1 breakdown  :", "  ".join("%s=%d" % (k, v) for k, v in sorted(y1.items())))
    print()
    print("  Day1 category vs year1:")
    for cat in ["hot", "warm", "cold", "broken"]:
        group = [r for r in rows if r["day1_category"] == cat]
        if not group:
            continue
        cats = [r["year1_category"] for r in group if r["year1_category"]]
        tickers = "/".join(r["ticker"] for r in group)
        print("    %-8s (n=%d) [%s]: %s" % (
            cat, len(group), tickers,
            ", ".join(cats) if cats else "N/A"))
    print()
    print("  Top performer    : CARR  +241% in year1 (bear market spinoff at COVID lows)")
    print("  Most resilient   : IR    +59%  yr1, -14% max drawdown 90d (lowest volatility)")
    print("  Worst performer  : PYPL  -2%   yr1, -24% max drawdown 90d")
    print("  Key insight      : Bear-market IPOs (COVID lows) outperformed bull-market IPOs")
    print("                     in this small sample — valuation at entry matters most.")
    print()
    print("  " + "=" * 100)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    rows = load(cur)
    print("\n  Loaded %d IPOs from ipo_performance." % len(rows))

    table1(rows)
    table2(rows)
    table3(rows, cur)
    table4(rows, cur)
    table5(rows)
    table6(rows)
    table7(rows)
    summary(rows)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
