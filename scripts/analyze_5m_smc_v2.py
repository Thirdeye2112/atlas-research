#!/usr/bin/env python
"""
analyze_5m_smc_v2.py — iteration 6: tune the 5m-in-Stage-2 setup for a tradeable edge.

Subsumes v1 (base = trigger + daily Stage-2 gate, target 2R). Adds the levers
that move win-rate AND expectancy, with anti-overfit discipline:
  - 5m CONFLUENCE (at the trigger bar): volume expansion (>1.5x 20-bar avg),
    RSI(14)>50, not-extended (<4 ATR above EMA20).
  - TARGET sweep: 1.5R / 2R / 2.5R (single forward scan resolves all).
  - TRAIN vs OOS split: OOS = last 12 months (reserved; we read it once).
  - Transaction COST: expectancy reported gross and net (-COST_R per trade).

Everything is gated by the daily Stage-2 long context (lookahead-safe, D-1).
Outcome: entry next 5m open; stop = swing-low of last K bars; targets in R.

Usage:
  python scripts/analyze_5m_smc_v2.py --limit 60          # validation
  python scripts/analyze_5m_smc_v2.py --horizon 78 --cost 0.05
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date
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

K = 12
ADX_MIN = 25.0
TARGETS = (1.0, 1.5, 2.0, 2.5)
OOS_START = pd.Timestamp("2025-06-15")   # reserve last ~12 months as OOS
CONFLUENCE = ("base", "+vol", "+vol+rsi+notext")


def ema(s, n): return s.ewm(span=n, adjust=False).mean()
def sma(s, n): return s.rolling(n).mean()


def adx(high, low, close, n=14):
    up = high.diff(); dn = -low.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(high-low), (high-close.shift()).abs(), (low-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100*pd.Series(pdm, index=high.index).ewm(alpha=1/n, adjust=False).mean()/atr
    mdi = 100*pd.Series(mdm, index=high.index).ewm(alpha=1/n, adjust=False).mean()/atr
    dx = 100*(pdi-mdi).abs()/(pdi+mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    return 100 - 100/(1 + up/dn.replace(0, np.nan))


def daily_go(daily, spy_ret126):
    idx = pd.to_datetime(daily["date"].values)
    fac = daily["adjusted_close"].astype(float).values / daily["close"].astype(float).values
    cl = pd.Series(daily["adjusted_close"].astype(float).values, index=idx)
    h = pd.Series(daily["high"].astype(float).values*fac, index=idx)
    l = pd.Series(daily["low"].astype(float).values*fac, index=idx)
    sma150 = sma(cl, 150); slope = sma150 - sma150.shift(20)
    go = ((cl > sma150) & (slope > 0) & (cl > ema(cl, 200)) & (adx(h, l, cl) > ADX_MIN) &
          (((cl/cl.shift(126)-1.0) - spy_ret126.reindex(cl.index)) > 0)).astype(float)
    return go.shift(1)


def r_multi(o, h, l, c, i, horizon):
    """Single forward scan -> {targetR: (R_outcome, win_bool)} for all targets."""
    n = len(c)
    if i < K or i >= n-1:
        return None
    entry = o[i+1]
    if not np.isfinite(entry) or entry <= 0:
        return None
    stop = np.min(l[i-K+1:i+1]); risk = entry - stop
    if risk <= 0:
        return None
    end = min(i+1+horizon, n)
    levels = {t: entry + t*risk for t in TARGETS}
    hit = {t: None for t in TARGETS}
    stop_j = None
    for j in range(i+1, end):
        if l[j] <= stop:
            stop_j = j; break
        for t in TARGETS:
            if hit[t] is None and h[j] >= levels[t]:
                hit[t] = j
    out = {}
    mtm = (c[end-1] - entry) / risk
    for t in TARGETS:
        if hit[t] is not None and (stop_j is None or hit[t] <= stop_j):
            out[t] = (t, True)
        elif stop_j is not None:
            out[t] = (-1.0, False)
        else:
            out[t] = (mtm, False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=78)
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--cost", type=float, default=0.05, help="transaction cost in R per trade")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    H = args.horizon

    with connection.get_connection() as c:
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"), c)
        univ = [r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv FROM raw_bars
                       WHERE date >= (SELECT max(date)-120 FROM raw_bars) GROUP BY ticker)
            SELECT r.ticker FROM r JOIN (SELECT DISTINCT ticker FROM intraday_bars
                 WHERE timeframe='5m' AND source LIKE 'alpaca%') i ON i.ticker=r.ticker
            WHERE r.dv >= :dv ORDER BY r.dv DESC
        """), {"dv": args.min_dvol}).fetchall()]
    if args.limit:
        univ = univ[:args.limit]
    spy = spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_ret126 = spy/spy.shift(126) - 1.0
    print(f"5m SMC v2 | {len(univ):,} tickers | horizon {H} (~{H/78:.1f}d) | cost {args.cost}R | OOS>={OOS_START.date()}")

    # acc[(trigger, conf, targetR, split)] = [n, sumR, wins]
    acc = defaultdict(lambda: [0, 0.0, 0])

    proc = 0
    with connection.get_connection() as conn:
        for tk in univ:
            daily = pd.read_sql(text("SELECT date,open,high,low,close,adjusted_close,volume "
                                     "FROM raw_bars WHERE ticker=:t ORDER BY date"), conn, params={"t": tk})
            if len(daily) < 220:
                continue
            go = daily_go(daily, spy_ret126).to_dict()

            m = pd.read_sql(text("SELECT ts,open,high,low,close,volume FROM intraday_bars "
                                 "WHERE ticker=:t AND timeframe='5m' AND source LIKE 'alpaca%' ORDER BY ts"),
                            conn, params={"t": tk})
            if len(m) < K+H+5:
                continue
            o=m["open"].to_numpy(float); h=m["high"].to_numpy(float)
            l=m["low"].to_numpy(float); c=m["close"].to_numpy(float); v=m["volume"].to_numpy(float)
            cl = pd.Series(c)
            ts_et = pd.to_datetime(m["ts"], utc=True).dt.tz_convert("America/New_York")
            day = ts_et.dt.normalize().dt.tz_localize(None).to_numpy()
            is_oos = (ts_et.dt.tz_localize(None) >= OOS_START).to_numpy()

            lo_prev = pd.Series(l).rolling(K).min().shift(1).to_numpy()
            hi_prev = pd.Series(h).rolling(K).max().shift(1).to_numpy()
            vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
            rsi5 = rsi(cl).to_numpy()
            ema20 = ema(cl, 20).to_numpy()
            tr = pd.concat([pd.Series(h-l), (pd.Series(h)-cl.shift()).abs(), (pd.Series(l)-cl.shift()).abs()],axis=1).max(axis=1)
            atr5 = tr.ewm(alpha=1/14, adjust=False).mean().to_numpy()

            for i in range(K, len(c)-1):
                sweep = (l[i] < lo_prev[i]) and (c[i] > lo_prev[i])
                bos = (c[i] > hi_prev[i])
                if not (sweep or bos):
                    continue
                if go.get(pd.Timestamp(day[i]), np.nan) != 1.0:   # daily Stage-2 gate
                    continue
                # confluence flags at trigger bar
                vol_ok = np.isfinite(vavg[i]) and v[i] > 1.5*vavg[i]
                rsi_ok = rsi5[i] > 50
                notext_ok = np.isfinite(atr5[i]) and atr5[i] > 0 and (c[i]-ema20[i])/atr5[i] < 4.0
                confs = {"base": True, "+vol": vol_ok, "+vol+rsi+notext": (vol_ok and rsi_ok and notext_ok)}
                res = r_multi(o, h, l, c, i, H)
                if res is None:
                    continue
                split = "OOS" if is_oos[i] else "train"
                for trig, on in (("sweep", sweep), ("bos", bos)):
                    if not on:
                        continue
                    for conf, ok in confs.items():
                        if not ok:
                            continue
                        for t in TARGETS:
                            R, win = res[t]
                            a = acc[(trig, conf, t, split)]
                            a[0]+=1; a[1]+=R; a[2]+= 1 if win else 0
            proc += 1
            if proc % 200 == 0:
                print(f"  ...{proc}/{len(univ)}", flush=True)

    cost = args.cost
    print(f"\n{'trigger':8}{'conf':18}{'tgt':>4} | {'n_tr':>8}{'win_tr':>7}{'expN_tr':>8} | {'n_oos':>7}{'win_oos':>8}{'expN_oos':>9}")
    print("-"*90)
    for trig in ("bos", "sweep"):
        for conf in CONFLUENCE:
            for t in TARGETS:
                ntr,sRtr,wtr = acc[(trig,conf,t,"train")]
                noo,sRoo,woo = acc[(trig,conf,t,"OOS")]
                if ntr < 50:
                    continue
                exptr = sRtr/ntr - cost; expoo = (sRoo/noo - cost) if noo else float('nan')
                wintr = 100*wtr/ntr; winoo = (100*woo/noo) if noo else float('nan')
                print(f"{trig:8}{conf:18}{t:>4} | {ntr:>8,}{wintr:>6.1f}%{exptr:>8.3f} | "
                      f"{noo:>7,}{winoo:>7.1f}%{expoo:>9.3f}")
    print(f"\nexpN = expectancy in R NET of {cost}R cost. win% = hit target before stop.")
    print("Look for configs with win% >= ~45 AND expN > 0 on BOTH train and OOS.")


if __name__ == "__main__":
    main()
