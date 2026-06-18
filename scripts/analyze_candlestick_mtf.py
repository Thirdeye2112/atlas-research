#!/usr/bin/env python
"""
analyze_candlestick_mtf.py — iteration 3: multi-timeframe confirmation.

Tests the core hypothesis the naive analysis couldn't (prior_trend was a dead
constant): do daily candlestick reversal/continuation patterns gain a real edge
once we CONFIRM them against the higher-timeframe trend?

Timeframe stack (built from raw_bars, no new ingestion):
  WEEKLY  primary trend  = sign of ~10-week return on weekly (W-FRI) closes
  DAILY   intermediate   = sign of 20-day return
Both use adjusted_close (split-safe — the unadjusted close is what produced the
+2.5M% contamination). Events are restricted to the tradeable universe
(close >= $5 and dollar-volume >= $1M at the signal bar).

Directional win @12d: bullish pattern -> fwd>0, bearish -> fwd<0.
Headline: win-rate when the pattern direction AGREES with the weekly trend
vs AGAINST it.

Usage:
    python scripts/analyze_candlestick_mtf.py
    python scripts/analyze_candlestick_mtf.py --min-dvol 1000000 --price-floor 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd
from sqlalchemy import text
from atlas_research.db import connection

BULL = {'Hammer', 'Inverted hammer', 'Bullish engulfing', 'Morning star',
        'Tweezer bottom', 'Three white soldiers'}
BEAR = {'Shooting star', 'Hanging man', 'Bearish engulfing', 'Evening star',
        'Tweezer top', 'Three black crows'}

DAILY_BAND = 0.02    # +/-2% over 20d => up/down, else flat
WEEKLY_BAND = 0.05   # +/-5% over ~10wk => up/down, else flat


def trend_bucket(x, band):
    if pd.isna(x):
        return "na"
    return "up" if x > band else ("down" if x < -band else "flat")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--price-floor", type=float, default=5.0)
    ap.add_argument("--horizon", type=int, default=12)
    args = ap.parse_args()
    H = args.horizon

    with connection.get_connection() as c:
        universe = [r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv, max(close) mx
                       FROM raw_bars WHERE date >= (SELECT max(date)-120 FROM raw_bars)
                       GROUP BY ticker)
            SELECT ticker FROM r WHERE dv >= :dv ORDER BY dv DESC
        """), {"dv": args.min_dvol}).fetchall()]

    print(f"MTF analysis | {len(universe):,} liquid tickers | horizon {H}d | "
          f"price>=${args.price_floor} dvol>=${args.min_dvol:,.0f}")

    # Accumulators: keyed by (pool, weekly_trend, daily_trend) -> [wins, n, sum_ret]
    from collections import defaultdict
    acc = defaultdict(lambda: [0, 0, 0.0])
    aligned = defaultdict(lambda: [0, 0])   # (pool, 'with'/'against'/'flat') -> [wins,n]

    eng = connection.get_connection
    processed = 0
    with connection.get_connection() as c:
        for i, tk in enumerate(universe):
            bars = pd.read_sql(text("""
                SELECT date, close, adjusted_close, volume FROM raw_bars
                WHERE ticker = :t ORDER BY date
            """), c, params={"t": tk})
            if len(bars) < 60:
                continue
            bars["date"] = pd.to_datetime(bars["date"])
            bars = bars.set_index("date")
            adj = bars["adjusted_close"].astype(float)

            # daily trend = 20-day return on adjusted close
            d_ret20 = adj / adj.shift(20) - 1.0
            daily_tr = d_ret20.map(lambda v: trend_bucket(v, DAILY_BAND))

            # weekly trend = ~10-week return on weekly closes, mapped back to days
            wk = adj.resample("W-FRI").last()
            w_ret10 = wk / wk.shift(10) - 1.0
            w_bucket = w_ret10.map(lambda v: trend_bucket(v, WEEKLY_BAND))
            weekly_tr = w_bucket.reindex(adj.index, method="ffill")

            # tradeable mask at the signal bar
            dvol = bars["close"].astype(float) * bars["volume"].astype(float)
            tradeable = (bars["close"].astype(float) >= args.price_floor) & (dvol >= args.min_dvol)

            ev = pd.read_sql(text(f"""
                SELECT timestamp::date AS d, candle_name, return_{H} AS ret
                FROM candlestick_outcomes
                WHERE ticker = :t AND return_{H} IS NOT NULL
            """), c, params={"t": tk})
            if ev.empty:
                continue
            ev["d"] = pd.to_datetime(ev["d"])
            ev = ev.set_index("d")
            ev["wt"] = weekly_tr.reindex(ev.index)
            ev["dt"] = daily_tr.reindex(ev.index)
            ev["ok"] = tradeable.reindex(ev.index).fillna(False)
            ev = ev[ev["ok"]]

            for _, row in ev.iterrows():
                name = row["candle_name"]
                pool = "bull" if name in BULL else ("bear" if name in BEAR else None)
                if pool is None:
                    continue
                ret = row["ret"]
                win = (ret > 0) if pool == "bull" else (ret < 0)
                key = (pool, row["wt"], row["dt"])
                a = acc[key]; a[0] += int(win); a[1] += 1; a[2] += float(ret)
                # alignment vs weekly trend
                wt = row["wt"]
                if wt in ("up", "down"):
                    rel = ("with" if (pool == "bull" and wt == "up") or
                                     (pool == "bear" and wt == "down") else "against")
                else:
                    rel = "flat"
                al = aligned[(pool, rel)]; al[0] += int(win); al[1] += 1
            processed += 1
            if processed % 500 == 0:
                print(f"  ...{processed}/{len(universe)} tickers")

    # ---- report ----
    print(f"\n=== HEADLINE: pattern vs WEEKLY trend (clean, {H}d) ===")
    print(f"{'pool':5}{'rel':9}{'n':>10}{'win%':>8}")
    for pool in ("bull", "bear"):
        for rel in ("with", "against", "flat"):
            w, n = aligned[(pool, rel)]
            if n:
                print(f"{pool:5}{rel:9}{n:>10,}{100*w/n:>8.1f}")

    print(f"\n=== win% by (weekly x daily) trend, {H}d ===")
    rows = []
    for (pool, wt, dt), (w, n, s) in acc.items():
        if n >= 200:
            rows.append((pool, wt, dt, n, 100*w/n, 100*s/n))
    rows.sort(key=lambda r: (r[0], -r[4]))
    print(f"{'pool':5}{'weekly':8}{'daily':7}{'n':>9}{'win%':>8}{'meanret%':>10}")
    for pool, wt, dt, n, win, mr in rows:
        print(f"{pool:5}{wt:8}{dt:7}{n:>9,}{win:>8.1f}{mr:>10.3f}")


if __name__ == "__main__":
    main()
