#!/usr/bin/env python
"""
extract_5m_events.py — compute the 5m SMC signals ONCE into a compact event table.

Every BOS/sweep trigger that occurs inside the daily Stage-2 long gate is written
to a parquet with: context flags + the full forward PRICE PATH summarised as
  - max_fav_R : highest favorable excursion (in R) reached BEFORE the stop is hit
  - stopped   : did the swing-low stop get hit within the horizon
  - mtm_R     : mark-to-market R at horizon end (for the no-target, no-stop case)
  - mae_R     : worst adverse excursion (in R)
From these three numbers ANY target T is resolved instantly downstream:
    win(T) = max_fav_R >= T  ->  +T ;  elif stopped -> -1 ;  else -> mtm_R
So sweep_5m_events.py can tune target/confluence/win-rate in SECONDS, no re-read.

Run once (full universe ~1h). Output: reports/validity/smc_events.parquet

Usage:
  python scripts/extract_5m_events.py            # full universe
  python scripts/extract_5m_events.py --limit 60 # validation
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
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import text
from atlas_research.db import connection

K = 12
ADX_MIN = 25.0
HORIZON = 78          # 5m bars (~1 trading day)
OUT = ROOT / "reports" / "validity" / "smc_events.parquet"


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
    return go.shift(1)   # D sees D-1


def forward_path(o, h, l, c, i):
    """Single forward scan -> (max_fav_R, stopped, mtm_R, mae_R)."""
    n = len(c)
    if i < K or i >= n-1: return None
    entry = o[i+1]
    if not np.isfinite(entry) or entry <= 0: return None
    stop = np.min(l[i-K+1:i+1]); risk = entry - stop
    if risk <= 0: return None
    end = min(i+1+HORIZON, n)
    max_fav = -1e9; mae = 1e9; stopped = False
    for j in range(i+1, end):
        lo_R = (l[j]-entry)/risk; hi_R = (h[j]-entry)/risk
        if lo_R < mae: mae = lo_R
        if l[j] <= stop:
            stopped = True; break
        if hi_R > max_fav: max_fav = hi_R
    mtm = (c[end-1]-entry)/risk
    return (float(max_fav if max_fav > -1e8 else 0.0), bool(stopped),
            float(mtm), float(mae if mae < 1e8 else 0.0))


SCHEMA = pa.schema([
    ("ticker", pa.string()), ("ts", pa.timestamp("ns")), ("is_oos", pa.bool_()),
    ("trigger", pa.string()),
    ("c_vol", pa.bool_()), ("c_rsi", pa.bool_()), ("c_notext", pa.bool_()),
    ("risk_px", pa.float64()), ("entry", pa.float64()),
    ("max_fav_R", pa.float64()), ("stopped", pa.bool_()),
    ("mtm_R", pa.float64()), ("mae_R", pa.float64()),
])
OOS_START = pd.Timestamp("2025-06-15")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

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
    print(f"extract | {len(univ):,} tickers -> {OUT}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    writer = pq.ParquetWriter(str(OUT), SCHEMA, compression="snappy")
    total = 0; proc = 0
    try:
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
                if len(m) < K+HORIZON+5:
                    continue
                o=m["open"].to_numpy(float); h=m["high"].to_numpy(float)
                l=m["low"].to_numpy(float); c=m["close"].to_numpy(float); v=m["volume"].to_numpy(float)
                cl = pd.Series(c)
                ts_et = pd.to_datetime(m["ts"], utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
                day = ts_et.dt.normalize().to_numpy()
                lo_prev = pd.Series(l).rolling(K).min().shift(1).to_numpy()
                hi_prev = pd.Series(h).rolling(K).max().shift(1).to_numpy()
                vavg = pd.Series(v).rolling(20).mean().shift(1).to_numpy()
                rsi5 = rsi(cl).to_numpy(); ema20 = ema(cl,20).to_numpy()
                tr = pd.concat([pd.Series(h-l),(pd.Series(h)-cl.shift()).abs(),(pd.Series(l)-cl.shift()).abs()],axis=1).max(axis=1)
                atr5 = tr.ewm(alpha=1/14, adjust=False).mean().to_numpy()

                rows = []
                for i in range(K, len(c)-1):
                    sweep = (l[i] < lo_prev[i]) and (c[i] > lo_prev[i])
                    bos = (c[i] > hi_prev[i])
                    if not (sweep or bos):
                        continue
                    if go.get(pd.Timestamp(day[i]), np.nan) != 1.0:
                        continue
                    fp = forward_path(o, h, l, c, i)
                    if fp is None:
                        continue
                    max_fav, stopped, mtm, mae = fp
                    vol_ok = bool(np.isfinite(vavg[i]) and v[i] > 1.5*vavg[i])
                    rsi_ok = bool(rsi5[i] > 50)
                    notext_ok = bool(np.isfinite(atr5[i]) and atr5[i] > 0 and (c[i]-ema20[i])/atr5[i] < 4.0)
                    entry = o[i+1]; risk = entry - np.min(l[i-K+1:i+1])
                    for trig, on in (("sweep", sweep), ("bos", bos)):
                        if not on:
                            continue
                        rows.append((tk, ts_et.iloc[i], bool(ts_et.iloc[i] >= OOS_START), trig,
                                     vol_ok, rsi_ok, notext_ok, float(risk), float(entry),
                                     max_fav, stopped, mtm, mae))
                if rows:
                    cols = list(zip(*rows))
                    tbl = pa.table({SCHEMA.field(k).name: pa.array(cols[k], type=SCHEMA.field(k).type)
                                    for k in range(len(SCHEMA))}, schema=SCHEMA)
                    writer.write_table(tbl)
                    total += len(rows)
                proc += 1
                if proc % 200 == 0:
                    print(f"  ...{proc}/{len(univ)}  events={total:,}", flush=True)
    finally:
        writer.close()
    print(f"\nDONE: {total:,} events -> {OUT}")


if __name__ == "__main__":
    main()
