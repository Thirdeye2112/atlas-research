"""
compute_ipo_performance.py
--------------------------
For each ticker in ipo_registry, computes comprehensive performance metrics
and stores them in ipo_performance.

Metrics computed:
  - Returns vs day1 close at 11 horizons (1,5,10,20,30,60,90,120,150,180,252d)
  - Alpha vs SPY at each horizon
  - Max drawdown in 4 windows (30,90,180,252d)
  - Peak analysis: days_to_peak, peak_return, peak_to_year_end
  - Volume profile: week1, month1, month3 averages; volume_decay
  - Volatility: 30d and 90d annualised std
  - Market context: SPY regime (vs SMA200), VIX close, sector RS
  - Year1 category: winner/moderate/loser/disaster
"""

import os
import numpy as np
import psycopg2

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:Postnat74%3F@localhost:5432/atlas_research")

HORIZONS = [1, 5, 10, 20, 30, 60, 90, 120, 150, 180, 252]

# Map ipo_registry.sector -> sector_relative_strength.sector_ticker
SECTOR_TO_ETF = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Basic Materials": "XLB",
    "Communication Services": "XLC",
}

def classify_year1(ret_252d):
    if ret_252d is None:
        return None
    if ret_252d >= 50:
        return "winner"
    if ret_252d >= 0:
        return "moderate"
    if ret_252d >= -50:
        return "loser"
    return "disaster"


def compute_sma(prices, period):
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def annualised_vol(returns):
    if len(returns) < 5:
        return None
    return float(np.std(returns, ddof=1) * np.sqrt(252) * 100)


def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True   # commit each ticker independently; failures don't abort others
    cur  = conn.cursor()

    cur.execute("""
        SELECT ticker, ipo_date, day1_close, sector
        FROM ipo_registry
        ORDER BY ipo_date
    """)
    ipos = cur.fetchall()
    print("IPOs to process: %d" % len(ipos))

    # Preload SPY bars once
    cur.execute("""
        SELECT date, close, volume
        FROM raw_bars
        WHERE ticker = 'SPY'
        ORDER BY date
    """)
    spy_rows = cur.fetchall()
    spy_dates  = [r[0] for r in spy_rows]
    spy_closes = np.array([float(r[1]) for r in spy_rows])
    spy_date_idx = {d: i for i, d in enumerate(spy_dates)}
    print("SPY bars loaded: %d" % len(spy_dates))

    # Preload VIX bars
    cur.execute("""
        SELECT date, close FROM raw_bars WHERE ticker = '^VIX' ORDER BY date
    """)
    vix_rows = cur.fetchall()
    vix_map = {r[0]: float(r[1]) for r in vix_rows}
    print("VIX bars: %d" % len(vix_map))

    computed = 0
    year1_counts = {"winner": 0, "moderate": 0, "loser": 0, "disaster": 0, "insufficient_data": 0}

    for ticker, ipo_date, day1_close, sector in ipos:
        if day1_close is None:
            print("  %s: no day1_close, skipping" % ticker)
            continue
        day1_close = float(day1_close)

        # Load ticker bars from ipo_date onward
        cur.execute("""
            SELECT date, open, high, low, close, volume
            FROM raw_bars
            WHERE ticker = %s AND date >= %s
            ORDER BY date
        """, (ticker, ipo_date))
        bars = cur.fetchall()

        if len(bars) < 5:
            print("  %s: insufficient bars (%d), skipping" % (ticker, len(bars)))
            year1_counts["insufficient_data"] += 1
            continue

        closes = np.array([float(r[4]) for r in bars])
        vols   = np.array([int(r[5]) if r[5] else 0 for r in bars])

        n = len(closes)

        # ── Returns at each horizon ───────────────────────────────────────────
        rets = {}
        for h in HORIZONS:
            if n > h:
                rets[h] = (closes[h] - day1_close) / day1_close * 100
            else:
                rets[h] = None

        # ── SPY returns at each horizon ───────────────────────────────────────
        spy_rets = {}
        spy_day0_idx = spy_date_idx.get(ipo_date)
        for h in HORIZONS:
            if spy_day0_idx is not None and spy_day0_idx + h < len(spy_closes):
                spy_ret = (spy_closes[spy_day0_idx + h] - spy_closes[spy_day0_idx]) / spy_closes[spy_day0_idx] * 100
                spy_rets[h] = spy_ret
                rets_vs_spy = (rets[h] - spy_ret) if rets[h] is not None else None
            else:
                spy_rets[h] = None
                rets_vs_spy = None

        # Build vs_spy dict
        vs_spy = {}
        for h in HORIZONS:
            if rets[h] is not None and spy_rets[h] is not None:
                vs_spy[h] = rets[h] - spy_rets[h]
            else:
                vs_spy[h] = None

        # ── Max drawdown per window ───────────────────────────────────────────
        max_dd = {}
        for w in [30, 90, 180, 252]:
            window_closes = closes[:min(w, n)]
            if len(window_closes) < 2:
                max_dd[w] = None
                continue
            running_max = np.maximum.accumulate(window_closes)
            dd = (window_closes - running_max) / running_max * 100
            max_dd[w] = float(np.min(dd))

        # ── Peak analysis ─────────────────────────────────────────────────────
        window_252 = closes[:min(252, n)]
        if len(window_252) > 1:
            peak_idx    = int(np.argmax(window_252))
            peak_close  = float(window_252[peak_idx])
            peak_return = (peak_close - day1_close) / day1_close * 100
            days_to_peak = peak_idx

            # Drop from peak to last available bar in year1 window
            last_idx = min(252, n) - 1
            last_close = float(closes[last_idx])
            peak_to_ye = (last_close - peak_close) / peak_close * 100
        else:
            days_to_peak = None
            peak_return  = None
            peak_to_ye   = None

        # ── Volume profile ────────────────────────────────────────────────────
        def avg_vol(start, end):
            segment = vols[start:min(end, n)]
            return int(np.mean(segment)) if len(segment) > 0 else None

        avg_vol_week1  = avg_vol(0, 5)
        avg_vol_month1 = avg_vol(0, 20)
        avg_vol_month3 = avg_vol(40, 60)

        if avg_vol_week1 and avg_vol_week1 > 0 and avg_vol_month3:
            vol_decay = (avg_vol_month3 - avg_vol_week1) / avg_vol_week1 * 100
        else:
            vol_decay = None

        # ── Volatility ────────────────────────────────────────────────────────
        daily_rets = np.diff(closes) / closes[:-1] * 100
        vol_30d = annualised_vol(daily_rets[:30])  if len(daily_rets) >= 30 else None
        vol_90d = annualised_vol(daily_rets[:90])  if len(daily_rets) >= 90 else None

        # ── Market context at IPO ─────────────────────────────────────────────
        # SPY regime: SPY close vs SMA200 at ipo_date
        spy_regime = None
        if spy_day0_idx is not None and spy_day0_idx >= 200:
            spy_sma200 = float(np.mean(spy_closes[spy_day0_idx - 200:spy_day0_idx]))
            spy_regime = "bull" if spy_closes[spy_day0_idx] > spy_sma200 else "bear"

        vix_at_ipo = vix_map.get(ipo_date)

        # Sector RS: latest available before ipo_date from sector_relative_strength
        sector_rs = None
        etf = SECTOR_TO_ETF.get(sector or "")
        if etf:
            try:
                cur.execute("""
                    SELECT rs_vs_spy_20d FROM sector_relative_strength
                    WHERE sector_ticker = %s AND date <= %s
                    ORDER BY date DESC LIMIT 1
                """, (etf, ipo_date))
                sr = cur.fetchone()
                if sr:
                    sector_rs = float(sr[0]) if sr[0] else None
            except Exception as e:
                print("    sector_rs failed (%s): %s" % (ticker, e))

        # ── Year1 classification ──────────────────────────────────────────────
        year1_ret = rets.get(252)
        year1_cat = classify_year1(year1_ret)
        if year1_cat is None:
            year1_counts["insufficient_data"] += 1
        else:
            year1_counts[year1_cat] += 1

        # Print one-liner
        ret_str = ("%.1f%%" % year1_ret) if year1_ret is not None else "N/A"
        print("  %-8s  bars=%-4d  peak=+%.1f%%@d%d  yr1=%s  [%s]" % (
            ticker, n,
            peak_return or 0, days_to_peak or 0,
            ret_str, year1_cat or "?"))

        # Cast all values to Python native types for psycopg2 compatibility
        def f(v):
            return float(v) if v is not None else None
        def i(v):
            return int(v) if v is not None else None

        # ── UPSERT into ipo_performance ───────────────────────────────────────
        cur.execute("""
            INSERT INTO ipo_performance (
              ticker, computed_at,
              return_1d, return_5d, return_10d, return_20d, return_30d,
              return_60d, return_90d, return_120d, return_150d, return_180d, return_252d,
              vs_spy_1d, vs_spy_5d, vs_spy_10d, vs_spy_20d, vs_spy_30d,
              vs_spy_60d, vs_spy_90d, vs_spy_120d, vs_spy_150d, vs_spy_180d, vs_spy_252d,
              max_dd_30d, max_dd_90d, max_dd_180d, max_dd_252d,
              days_to_first_peak, peak_return, peak_to_year_end,
              avg_volume_week1, avg_volume_month1, avg_volume_month3, volume_decay_pct,
              volatility_30d, volatility_90d,
              spy_regime_at_ipo, vix_at_ipo, sector_rs_at_ipo,
              year1_category
            ) VALUES (
              %s, NOW(),
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
              %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
              %s,%s,%s,%s,
              %s,%s,%s,
              %s,%s,%s,%s,
              %s,%s,
              %s,%s,%s,
              %s
            )
            ON CONFLICT (ticker) DO UPDATE SET
              computed_at       = NOW(),
              return_1d         = EXCLUDED.return_1d,
              return_5d         = EXCLUDED.return_5d,
              return_10d        = EXCLUDED.return_10d,
              return_20d        = EXCLUDED.return_20d,
              return_30d        = EXCLUDED.return_30d,
              return_60d        = EXCLUDED.return_60d,
              return_90d        = EXCLUDED.return_90d,
              return_120d       = EXCLUDED.return_120d,
              return_150d       = EXCLUDED.return_150d,
              return_180d       = EXCLUDED.return_180d,
              return_252d       = EXCLUDED.return_252d,
              vs_spy_1d         = EXCLUDED.vs_spy_1d,
              vs_spy_5d         = EXCLUDED.vs_spy_5d,
              vs_spy_10d        = EXCLUDED.vs_spy_10d,
              vs_spy_20d        = EXCLUDED.vs_spy_20d,
              vs_spy_30d        = EXCLUDED.vs_spy_30d,
              vs_spy_60d        = EXCLUDED.vs_spy_60d,
              vs_spy_90d        = EXCLUDED.vs_spy_90d,
              vs_spy_120d       = EXCLUDED.vs_spy_120d,
              vs_spy_150d       = EXCLUDED.vs_spy_150d,
              vs_spy_180d       = EXCLUDED.vs_spy_180d,
              vs_spy_252d       = EXCLUDED.vs_spy_252d,
              max_dd_30d        = EXCLUDED.max_dd_30d,
              max_dd_90d        = EXCLUDED.max_dd_90d,
              max_dd_180d       = EXCLUDED.max_dd_180d,
              max_dd_252d       = EXCLUDED.max_dd_252d,
              days_to_first_peak= EXCLUDED.days_to_first_peak,
              peak_return       = EXCLUDED.peak_return,
              peak_to_year_end  = EXCLUDED.peak_to_year_end,
              avg_volume_week1  = EXCLUDED.avg_volume_week1,
              avg_volume_month1 = EXCLUDED.avg_volume_month1,
              avg_volume_month3 = EXCLUDED.avg_volume_month3,
              volume_decay_pct  = EXCLUDED.volume_decay_pct,
              volatility_30d    = EXCLUDED.volatility_30d,
              volatility_90d    = EXCLUDED.volatility_90d,
              spy_regime_at_ipo = EXCLUDED.spy_regime_at_ipo,
              vix_at_ipo        = EXCLUDED.vix_at_ipo,
              sector_rs_at_ipo  = EXCLUDED.sector_rs_at_ipo,
              year1_category    = EXCLUDED.year1_category
        """, (
            ticker,
            f(rets[1]), f(rets[5]), f(rets[10]), f(rets[20]), f(rets[30]),
            f(rets[60]), f(rets[90]), f(rets[120]), f(rets[150]), f(rets[180]), f(rets[252]),
            f(vs_spy[1]), f(vs_spy[5]), f(vs_spy[10]), f(vs_spy[20]), f(vs_spy[30]),
            f(vs_spy[60]), f(vs_spy[90]), f(vs_spy[120]), f(vs_spy[150]), f(vs_spy[180]), f(vs_spy[252]),
            f(max_dd[30]), f(max_dd[90]), f(max_dd[180]), f(max_dd[252]),
            i(days_to_peak), f(peak_return), f(peak_to_ye),
            i(avg_vol_week1), i(avg_vol_month1), i(avg_vol_month3), f(vol_decay),
            f(vol_30d), f(vol_90d),
            spy_regime, f(vix_at_ipo), f(sector_rs),
            year1_cat,
        ))

        # Also update year1_category in ipo_registry
        cur.execute("""
            UPDATE ipo_registry SET year1_category = %s WHERE ticker = %s
        """, (year1_cat, ticker))

        computed += 1

    cur.close()
    conn.close()

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  IPO PERFORMANCE COMPUTATION COMPLETE")
    print("  Computed: %d" % computed)
    print("\n  Year1 category breakdown:")
    for cat in ["winner", "moderate", "loser", "disaster", "insufficient_data"]:
        cnt = year1_counts.get(cat, 0)
        if cnt:
            bar = "#" * cnt
            print("    %-20s: %2d  %s" % (cat, cnt, bar))
    print("="*60)

    # Print the full results table
    conn3 = psycopg2.connect(DB_URL)
    cur3 = conn3.cursor()
    cur3.execute("""
        SELECT r.ticker, r.company_name, r.ipo_date, r.day1_category,
               p.return_30d, p.return_90d, p.return_252d,
               p.vs_spy_252d, p.peak_return, p.days_to_first_peak,
               p.max_dd_90d, p.volatility_30d, p.year1_category
        FROM ipo_registry r
        JOIN ipo_performance p ON r.ticker = p.ticker
        ORDER BY r.ipo_date
    """)
    rows = cur3.fetchall()
    cur3.close()
    conn3.close()

    if rows:
        print("\n  FULL RESULTS:")
        print("  %-6s  %-26s  %-10s  %-7s  %7s  %7s  %8s  %8s  %8s  %5s  %8s  %-12s" % (
            "Ticker","Company","IPO Date","Day1","30d","90d","252d","vsSPY","Peak","@Day","MaxDD90","Year1"))
        print("  " + "-"*130)
        for r in rows:
            ticker, name, ipo_date, d1cat, r30, r90, r252, vs252, pk, pk_d, dd90, vol30, y1cat = r
            def fmt(v):
                return ("%+.1f%%" % float(v)) if v is not None else "  N/A "
            print("  %-6s  %-26s  %-10s  %-7s  %7s  %7s  %8s  %8s  %8s  %5s  %8s  %-12s" % (
                ticker, (name or "")[:26], str(ipo_date), d1cat or "?",
                fmt(r30), fmt(r90), fmt(r252), fmt(vs252),
                fmt(pk), str(pk_d or "?"), fmt(dd90), y1cat or "?"))


if __name__ == "__main__":
    main()