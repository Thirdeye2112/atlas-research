#!/usr/bin/env python
"""
extract_5m_events_v3.py — iter 8: scale-out exits + regime tag.

Target tuning, confluence, VCP, and retest are exhausted (iter 6-7). The last
untested win-rate lever is EXIT design. Per BOS market entry (Stage-2 gated) we
simulate, inside one forward scan, the realized R of three exits:
  - fixed targets (via max_fav_R/stopped/mtm_R, resolved downstream)
  - r_be_runner : full size; at +1R move stop to breakeven, then trail giving
                  back 1R from the peak; exit on trail-stop or at horizon close.
  - r_partial   : take HALF off at +1R, trail the other half (BE then give-back-1R).
Plus spy_up = was SPY above its 50d SMA at D-1 (to split bull vs non-bull regime).

Output: reports/validity/smc_events_v3.parquet
Usage: python scripts/extract_5m_events_v3.py [--limit N]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")
import numpy as np, pandas as pd
import pyarrow as pa, pyarrow.parquet as pq
from sqlalchemy import text
from atlas_research.db import connection

K=12; ADX_MIN=25.0; HORIZON=78
OOS_START=pd.Timestamp("2025-06-15")
OUT=ROOT/"reports"/"validity"/"smc_events_v3.parquet"

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def sma(s,n): return s.rolling(n).mean()
def adx(high,low,close,n=14):
    up=high.diff(); dn=-low.diff()
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([(high-low),(high-close.shift()).abs(),(low-close.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(pdm,index=high.index).ewm(alpha=1/n,adjust=False).mean()/atr
    mdi=100*pd.Series(mdm,index=high.index).ewm(alpha=1/n,adjust=False).mean()/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean()
def rsi(close,n=14):
    d=close.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn.replace(0,np.nan))

def daily_go(daily,spy_ret126):
    idx=pd.to_datetime(daily["date"].values)
    fac=daily["adjusted_close"].astype(float).values/daily["close"].astype(float).values
    cl=pd.Series(daily["adjusted_close"].astype(float).values,index=idx)
    h=pd.Series(daily["high"].astype(float).values*fac,index=idx)
    l=pd.Series(daily["low"].astype(float).values*fac,index=idx)
    sma150=sma(cl,150); slope=sma150-sma150.shift(20)
    go=((cl>sma150)&(slope>0)&(cl>ema(cl,200))&(adx(h,l,cl)>ADX_MIN)&
        (((cl/cl.shift(126)-1.0)-spy_ret126.reindex(cl.index))>0)).astype(float)
    return go.shift(1)

def simulate(o,h,l,c,entry,stop,start,end,mtm):
    """Return (max_fav_R, stopped, mae_R, r_be_runner, r_partial)."""
    risk=entry-stop
    max_fav=-1e9; mae=1e9; stopped=False
    for j in range(start,end):
        loR=(l[j]-entry)/risk; hiR=(h[j]-entry)/risk
        if loR<mae: mae=loR
        if l[j]<=stop: stopped=True; break
        if hiR>max_fav: max_fav=hiR
    def trail(partial):
        stopR=-1.0; peak=-1e9; hit1=False; locked=0.0; size=1.0
        for j in range(start,end):
            loR=(l[j]-entry)/risk; hiR=(h[j]-entry)/risk
            if loR<=stopR:
                return locked+size*stopR
            if hiR>peak: peak=hiR
            if (not hit1) and peak>=1.0:
                hit1=True
                if partial: locked+=0.5; size=0.5
                stopR=0.0
            if hit1: stopR=max(stopR,peak-1.0)
        return locked+size*mtm
    return (float(max_fav if max_fav>-1e8 else 0.0), bool(stopped),
            float(mae if mae<1e8 else 0.0), float(trail(False)), float(trail(True)))

SCHEMA=pa.schema([
    ("ticker",pa.string()),("ts",pa.timestamp("ns")),("is_oos",pa.bool_()),
    ("c_vol",pa.bool_()),("c_rsi",pa.bool_()),("c_notext",pa.bool_()),("c_vcp",pa.bool_()),("spy_up",pa.bool_()),
    ("max_fav_R",pa.float64()),("stopped",pa.bool_()),("mtm_R",pa.float64()),("mae_R",pa.float64()),
    ("r_be_runner",pa.float64()),("r_partial",pa.float64()),
])

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--min-dvol",type=float,default=1_000_000)
    ap.add_argument("--limit",type=int,default=None); args=ap.parse_args()
    with connection.get_connection() as c:
        spy=pd.read_sql(text("SELECT date,adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"),c)
        univ=[r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv FROM raw_bars
                       WHERE date>=(SELECT max(date)-120 FROM raw_bars) GROUP BY ticker)
            SELECT r.ticker FROM r JOIN (SELECT DISTINCT ticker FROM intraday_bars
                 WHERE timeframe='5m' AND source LIKE 'alpaca%') i ON i.ticker=r.ticker
            WHERE r.dv>=:dv ORDER BY r.dv DESC"""),{"dv":args.min_dvol}).fetchall()]
    if args.limit: univ=univ[:args.limit]
    spy=spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_ret126=spy/spy.shift(126)-1.0
    spy_up=(spy>sma(spy,50)).shift(1)               # SPY above 50d SMA, D-1
    spy_up_map=spy_up.to_dict()
    print(f"extract v3 | {len(univ):,} tickers -> {OUT}")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    writer=pq.ParquetWriter(str(OUT),SCHEMA,compression="snappy")
    total=0; proc=0
    try:
        with connection.get_connection() as conn:
            for tk in univ:
                daily=pd.read_sql(text("SELECT date,open,high,low,close,adjusted_close,volume "
                    "FROM raw_bars WHERE ticker=:t ORDER BY date"),conn,params={"t":tk})
                if len(daily)<220: continue
                go=daily_go(daily,spy_ret126).to_dict()
                m=pd.read_sql(text("SELECT ts,open,high,low,close,volume FROM intraday_bars "
                    "WHERE ticker=:t AND timeframe='5m' AND source LIKE 'alpaca%' ORDER BY ts"),
                    conn,params={"t":tk})
                if len(m)<2*K+HORIZON+5: continue
                o=m["open"].to_numpy(float); h=m["high"].to_numpy(float)
                l=m["low"].to_numpy(float); c=m["close"].to_numpy(float); v=m["volume"].to_numpy(float)
                cl=pd.Series(c); n=len(c)
                ts_et=pd.to_datetime(m["ts"],utc=True).dt.tz_convert("America/New_York").dt.tz_localize(None)
                day=ts_et.dt.normalize().to_numpy()
                hi_prev=pd.Series(h).rolling(K).max().shift(1).to_numpy()
                vavg=pd.Series(v).rolling(20).mean().shift(1).to_numpy()
                rsi5=rsi(cl).to_numpy(); ema20=ema(cl,20).to_numpy()
                tr=pd.concat([pd.Series(h-l),(pd.Series(h)-cl.shift()).abs(),(pd.Series(l)-cl.shift()).abs()],axis=1).max(axis=1)
                atr5=tr.ewm(alpha=1/14,adjust=False).mean().to_numpy()
                rng=pd.Series(h-l)
                rec_rng=rng.rolling(K).sum().shift(1).to_numpy()
                pri_rng=rng.rolling(K).sum().shift(1+K).to_numpy()
                rows=[]
                for i in range(2*K,n-1):
                    if c[i]<=hi_prev[i]: continue
                    if go.get(pd.Timestamp(day[i]),np.nan)!=1.0: continue
                    entry=o[i+1]; stop=np.min(l[i-K+1:i+1])
                    if entry-stop<=0: continue
                    end=min(i+1+HORIZON,n); mtm=(c[end-1]-entry)/(entry-stop)
                    sim=simulate(o,h,l,c,entry,stop,i+1,end,mtm)
                    flags=(bool(np.isfinite(vavg[i]) and v[i]>1.5*vavg[i]),
                           bool(rsi5[i]>50),
                           bool(np.isfinite(atr5[i]) and atr5[i]>0 and (c[i]-ema20[i])/atr5[i]<4.0),
                           bool(np.isfinite(rec_rng[i]) and np.isfinite(pri_rng[i]) and rec_rng[i]<pri_rng[i]),
                           bool(spy_up_map.get(pd.Timestamp(day[i]),False)))
                    rows.append((tk,ts_et.iloc[i],bool(ts_et.iloc[i]>=OOS_START),*flags,
                                 sim[0],sim[1],mtm,sim[2],sim[3],sim[4]))
                if rows:
                    cols=list(zip(*rows))
                    tbl=pa.table({SCHEMA.field(k).name:pa.array(cols[k],type=SCHEMA.field(k).type)
                                  for k in range(len(SCHEMA))},schema=SCHEMA)
                    writer.write_table(tbl); total+=len(rows)
                proc+=1
                if proc%200==0: print(f"  ...{proc}/{len(univ)}  events={total:,}",flush=True)
    finally:
        writer.close()
    print(f"\nDONE: {total:,} events -> {OUT}")

if __name__=="__main__":
    main()
