#!/usr/bin/env python
"""
analyze_5m_smc.py — iteration 5: 5-minute SMC trigger inside a daily Stage-2 gate.

The daily layer proved to be context, not trigger (iter 1-4). This tests the
real thesis: a 5-MINUTE entry trigger, taken ONLY when the daily timeframe is in
a Stage-2 uptrend, labeled with realistic R-multiples.

Daily context (raw_bars, split-safe adj close): Weinstein Stage (1-4),
above-200EMA, ADX>25, RS-vs-SPY. "daily_go" = Stage 2 AND above 200EMA AND ADX>25.
To avoid lookahead, a 5-min bar on day D uses the daily context as of D-1 (the
last completed daily bar).

5-min long triggers on intraday_bars (alpaca 5m):
  - SWEEP+RECLAIM (bullish): bar's low takes out the prior K-bar swing low but the
    bar CLOSES back above it (sell-side liquidity grab + reclaim). SMC primitive.
  - BOS_UP: close breaks above the prior K-bar swing high (break of structure).

R-multiple outcome (per trigger bar): entry = next 5m open; stop = the swing low
of the last K bars (the swept low); R = entry - stop; target = entry + 2R;
resolve over HORIZON 5-min bars (stop checked first, conservative).

Compare win%(2R) and expectancy(R) for each trigger:
  ALL triggers  vs  daily Stage-2 gate  vs  NOT Stage-2  (does the daily gate help?)

Usage:
  python scripts/analyze_5m_smc.py --limit 40        # validation
  python scripts/analyze_5m_smc.py --horizon 78      # 1 day; 156 = 2 days
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
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

K = 12            # 5m bars (~1h) for swing-low/high lookback
TARGET_R = 2.0
ADX_MIN = 25.0


def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def sma(s, n): return s.rolling(n).mean()


def adx(high, low, close, n=14):
    up = high.diff(); dn = -low.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pd.Series(pdm, index=high.index).ewm(alpha=1/n, adjust=False).mean()/atr
    mdi = 100*pd.Series(mdm, index=high.index).ewm(alpha=1/n, adjust=False).mean()/atr
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def daily_context(daily, spy_ret126):
    """Return a per-date Series 'go' (Stage-2 long context), shifted +1 day (no lookahead)."""
    idx = pd.to_datetime(daily["date"].values)          # date-index everything so
    fac = daily["adjusted_close"].astype(float).values / daily["close"].astype(float).values
    cl = pd.Series(daily["adjusted_close"].astype(float).values, index=idx)
    h = pd.Series(daily["high"].astype(float).values * fac, index=idx)
    l = pd.Series(daily["low"].astype(float).values * fac, index=idx)
    ema200 = ema(cl, 200)
    sma150 = sma(cl, 150); slope = sma150 - sma150.shift(20)
    adx14 = adx(h, l, cl)
    rs = (cl/cl.shift(126) - 1.0) - spy_ret126.reindex(cl.index)   # now aligns on dates
    stage2 = (cl > sma150) & (slope > 0)
    go = (stage2 & (cl > ema200) & (adx14 > ADX_MIN) & (rs > 0)).astype(float)
    return go.shift(1)   # day D sees D-1's completed daily context


def r_at_5m(o, h, l, c, i, horizon):
    n = len(c)
    if i < K or i >= n-1: return (np.nan, 0)
    entry = o[i+1]
    if not np.isfinite(entry) or entry <= 0: return (np.nan, 0)
    stop = np.min(l[i-K+1:i+1])
    risk = entry - stop
    if risk <= 0: return (np.nan, 0)
    target = entry + TARGET_R*risk
    end = min(i+1+horizon, n)
    for j in range(i+1, end):
        if l[j] <= stop: return (-1.0, -1)
        if h[j] >= target: return (TARGET_R, 1)
    return ((c[end-1]-entry)/risk, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=78, help="5m bars to resolve (78≈1 day)")
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    H = args.horizon

    with connection.get_connection() as c:
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"), c)
        # tickers that have 5m alpaca data, ordered by daily liquidity
        univ = [r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv FROM raw_bars
                       WHERE date >= (SELECT max(date)-120 FROM raw_bars) GROUP BY ticker)
            SELECT r.ticker FROM r
            JOIN (SELECT DISTINCT ticker FROM intraday_bars WHERE timeframe='5m' AND source LIKE 'alpaca%') i
              ON i.ticker = r.ticker
            WHERE r.dv >= :dv ORDER BY r.dv DESC
        """), {"dv": args.min_dvol}).fetchall()]
    if args.limit:
        univ = univ[:args.limit]
    spy = spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_ret126 = spy/spy.shift(126) - 1.0
    print(f"5m SMC test | {len(univ):,} tickers w/ 5m | horizon {H} bars (~{H/78:.1f}d) | gate=daily Stage-2")

    acc = defaultdict(lambda: [0, 0.0, 0])   # bucket -> [n, sumR, wins]
    def tally(b, R, hit):
        a = acc[b]; a[0]+=1; a[1]+=R; a[2]+= 1 if hit==1 else 0

    processed = 0
    with connection.get_connection() as conn:
        for tk in univ:
            daily = pd.read_sql(text("SELECT date, open, high, low, close, adjusted_close, volume "
                                     "FROM raw_bars WHERE ticker=:t ORDER BY date"), conn, params={"t": tk})
            if len(daily) < 220:
                continue
            go = daily_context(daily, spy_ret126)   # date -> 0/1 (shifted)

            m = pd.read_sql(text("SELECT ts, open, high, low, close FROM intraday_bars "
                                 "WHERE ticker=:t AND timeframe='5m' AND source LIKE 'alpaca%' ORDER BY ts"),
                            conn, params={"t": tk})
            if len(m) < K+H+5:
                continue
            o = m["open"].to_numpy(float); h = m["high"].to_numpy(float)
            l = m["low"].to_numpy(float);  c = m["close"].to_numpy(float)
            # tz-aware UTC -> ET trading date (naive) to match the daily index
            ts_et = pd.to_datetime(m["ts"], utc=True).dt.tz_convert("America/New_York")
            day = ts_et.dt.normalize().dt.tz_localize(None).to_numpy()
            go_map = go.to_dict()

            # rolling prior swing low/high over last K bars (exclusive of current)
            lo_prev = pd.Series(l).rolling(K).min().shift(1).to_numpy()
            hi_prev = pd.Series(h).rolling(K).max().shift(1).to_numpy()

            for i in range(K, len(c)-1):
                sweep = (l[i] < lo_prev[i]) and (c[i] > lo_prev[i])   # bullish sweep+reclaim
                bos   = (c[i] > hi_prev[i])                            # break of structure up
                if not (sweep or bos):
                    continue
                gctx = go_map.get(pd.Timestamp(day[i]), np.nan)
                for trig, on in (("sweep", sweep), ("bos", bos)):
                    if not on:
                        continue
                    R, hit = r_at_5m(o, h, l, c, i, H)
                    if not np.isfinite(R):
                        continue
                    tally(f"{trig}: ALL", R, hit)
                    if gctx == 1.0:
                        tally(f"{trig}: daily Stage-2", R, hit)
                    elif gctx == 0.0:
                        tally(f"{trig}: NOT Stage-2", R, hit)
            processed += 1
            if processed % 200 == 0:
                print(f"  ...{processed}/{len(univ)}", flush=True)

    print(f"\n{'bucket':26}{'n':>10}{'win%(2R)':>10}{'exp(R)':>9}")
    for trig in ("sweep", "bos"):
        for suf in ("ALL", "daily Stage-2", "NOT Stage-2"):
            n, sR, w = acc[f"{trig}: {suf}"]
            if n:
                print(f"{trig+': '+suf:26}{n:>10,}{100*w/n:>10.1f}{sR/n:>9.3f}")
    print("\nThesis: 'daily Stage-2' should beat 'ALL' and 'NOT Stage-2' on expectancy.")


if __name__ == "__main__":
    main()
