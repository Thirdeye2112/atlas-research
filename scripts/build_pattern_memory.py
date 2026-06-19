#!/usr/bin/env python
"""
build_pattern_memory.py — STEP 1: the Pattern Memory (knowledge base).

For every stock in the CLEAN universe (settings.CLEAN_UNIVERSE_CSV), detect every
chart pattern and log its full STORY (before / through / after) into the queryable
`pattern_memory` Postgres table. No predictions, no win-rate — just the library.

  BEFORE : trend (this TF) + higher-TF trend, move into it, distance to 50/200 SMA,
           distance to nearest support/resistance.
  THROUGH: RSI, MACD-hist, ADX, ATR%, volume-vs-average at the confirmation bar.
  AFTER  : over a forward window — max run, max drawdown, forward return,
           bars-to-peak, # of pullbacks (run/pullback texture), did it reach target.

Daily first (clean data). Candles, 5-min, and swing_leg/dome populate the SAME
table in later passes. Resilient: per-ticker try/except, per-ticker insert so
partial progress persists.

Usage:
  python scripts/build_pattern_memory.py --limit 25      # validate
  python scripts/build_pattern_memory.py                 # full clean universe
"""
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")

import numpy as np, pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import text
from atlas_research.db import connection
from atlas_research.ta import structure as S, patterns as P
from config import settings

HORIZON = 60          # forward bars to characterize the "after"
PULLBACK_THR = 0.03   # a >=3% retrace from a running peak counts as a pullback

DDL = """
CREATE TABLE IF NOT EXISTS pattern_memory (
  id            bigserial PRIMARY KEY,
  ticker        text, timeframe text, pattern_type text, direction text,
  confirm_date  date, start_date date, end_date date,
  trend         text, trend_higher text,
  ret_before    double precision, dist_sma50 double precision, dist_sma200 double precision,
  dist_support  double precision, dist_resistance double precision,
  rsi double precision, macd_hist double precision, adx double precision,
  atr_pct double precision, vol_ratio double precision,
  entry double precision, stop double precision, target double precision, rr double precision,
  max_run double precision, max_dd double precision, fwd_ret double precision,
  bars_to_peak int, n_pullbacks int, reached_target boolean,
  created_at timestamptz default now()
);
CREATE INDEX IF NOT EXISTS idx_pm_tk ON pattern_memory(ticker, timeframe, pattern_type);
"""
COLS = ["ticker","timeframe","pattern_type","direction","confirm_date","start_date","end_date",
        "trend","trend_higher","ret_before","dist_sma50","dist_sma200","dist_support","dist_resistance",
        "rsi","macd_hist","adx","atr_pct","vol_ratio","entry","stop","target","rr",
        "max_run","max_dd","fwd_ret","bars_to_peak","n_pullbacks","reached_target"]


def _py(v):
    """Coerce numpy scalars -> native Python; NaN -> None (psycopg2-safe)."""
    if v is None: return None
    if isinstance(v, np.generic): v = v.item()
    if isinstance(v, float) and math.isnan(v): return None
    return v

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def sma(s,n): return s.rolling(n).mean()
def rsi(c,n=14):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn.replace(0,np.nan))
def adx(h,l,c,n=14):
    up=h.diff(); dn=-l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(pdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    mdi=100*pd.Series(mdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean(), a


def after_story(p, high, low, close):
    """Characterize the resolution: max run, max dd, fwd ret, bars-to-peak, #pullbacks, reached target."""
    ci=p.confirm_idx; n=len(close); end=min(ci+1+HORIZON,n)
    entry=close[ci]
    if entry<=0 or end<=ci+1: return (np.nan,)*3+(None,None,None)
    seg_h=high[ci+1:end]; seg_l=low[ci+1:end]; seg_c=close[ci+1:end]
    if p.direction=="long":
        run=float((seg_h.max()-entry)/entry); dd=float((seg_l.min()-entry)/entry)
        btp=int(np.argmax(seg_h))+1; fwd=float((seg_c[-1]-entry)/entry)
        reached=bool(seg_h.max()>=p.target)
        # pullback count: retraces >=THR from running peak
        peak=entry; pulls=0; armed=False
        for x in seg_h:
            if x>peak: peak=x; armed=True
        peak=entry; pulls=0
        for hi,lo in zip(seg_h,seg_l):
            if hi>peak: peak=hi
            if peak>0 and (peak-lo)/peak>=PULLBACK_THR: pulls+=1; peak=lo
    else:
        run=float((entry-seg_l.min())/entry); dd=float((entry-seg_h.max())/entry)
        btp=int(np.argmin(seg_l))+1; fwd=float((entry-seg_c[-1])/entry)
        reached=bool(seg_l.min()<=p.target)
        trough=entry; pulls=0
        for lo,hi in zip(seg_l,seg_h):
            if lo<trough: trough=lo
            if trough>0 and (hi-trough)/trough>=PULLBACK_THR: pulls+=1; trough=hi
    return run,dd,fwd,btp,pulls,reached


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=None)
    ap.add_argument("--width",type=int,default=5); ap.add_argument("--reset",action="store_true")
    args=ap.parse_args()

    clean=pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"].tolist()
    if args.limit: clean=clean[:args.limit]
    with connection.get_connection() as c:
        if args.reset: c.execute(text("DROP TABLE IF EXISTS pattern_memory"))
        for stmt in DDL.strip().split(";"):
            if stmt.strip(): c.execute(text(stmt))
    print(f"pattern_memory build | {len(clean):,} clean tickers | daily")

    total=0; errors=0; proc=0
    eng=connection.get_raw_engine()
    with connection.get_connection() as conn:
        for tk in clean:
          try:
            df=pd.read_sql(text("SELECT date,high,low,close,adjusted_close,volume "
                                "FROM raw_bars WHERE ticker=:t ORDER BY date"),conn,params={"t":tk})
            if len(df)<260: continue
            fac=(df["adjusted_close"]/df["close"]).replace([np.inf,-np.inf],np.nan).fillna(1.0)
            h=(df["high"]*fac).to_numpy(); l=(df["low"]*fac).to_numpy(); cl=df["adjusted_close"].to_numpy()
            vol=df["volume"].to_numpy(); dates=pd.to_datetime(df["date"])
            cls=pd.Series(cl)
            r=rsi(cls).to_numpy(); mh=(ema(cls,12)-ema(cls,26)); mh=(mh-ema(mh,9)).to_numpy()
            ax,atr=adx(pd.Series(h),pd.Series(l),cls); ax=ax.to_numpy(); atr=atr.to_numpy()
            s50=sma(cls,50).to_numpy(); s200=sma(cls,200).to_numpy(); vavg=sma(pd.Series(vol),20).to_numpy()
            wk=pd.Series(cl,index=dates).resample("W-FRI").last()
            wk_tr=np.where(wk>wk.rolling(30).mean(),"up","down")
            wk_map=pd.Series(wk_tr,index=wk.index).reindex(dates,method="ffill").to_numpy()
            piv=S.swing_pivots(h,l,width=args.width)
            pats=P.detect_all(piv,h,l,cl)
            rows=[]
            for p in pats:
                ci=p.confirm_idx
                if ci<60 or not np.isfinite(s200[ci]): continue
                recent=[q for q in piv if q.idx<=ci]
                price=cl[ci]
                levels=S.support_resistance(recent, price)
                sup=[x["level"] for x in levels if x["level"]<=price]
                res=[x["level"] for x in levels if x["level"]>=price]
                dist_sup=(price-max(sup))/price if sup else None
                dist_res=(min(res)-price)/price if res else None
                start_idx=min(pt[0] for pt in p.points)
                run,dd,fwd,btp,pulls,reached=after_story(p,h,l,cl)
                rows.append((tk,"daily",p.name,p.direction,
                    dates.iloc[ci].date(), dates.iloc[start_idx].date(), dates.iloc[ci].date(),
                    S.classify_trend(recent), str(wk_map[ci]),
                    float(price/cl[start_idx]-1), float(price/s50[ci]-1) if np.isfinite(s50[ci]) else None,
                    float(price/s200[ci]-1), dist_sup, dist_res,
                    float(r[ci]) if np.isfinite(r[ci]) else None, float(mh[ci]) if np.isfinite(mh[ci]) else None,
                    float(ax[ci]) if np.isfinite(ax[ci]) else None,
                    float(atr[ci]/price) if np.isfinite(atr[ci]) else None,
                    float(vol[ci]/vavg[ci]) if np.isfinite(vavg[ci]) and vavg[ci]>0 else None,
                    float(p.entry), float(p.stop), float(p.target), float(p.rr),
                    run, dd, fwd, btp, pulls, reached))
            if rows:
                rawc=eng.raw_connection()
                try:
                    cur=rawc.cursor()
                    safe=[tuple(_py(v) for v in r) for r in rows]
                    execute_values(cur, f"INSERT INTO pattern_memory ({','.join(COLS)}) VALUES %s", safe)
                    rawc.commit()
                finally:
                    rawc.close()
                total+=len(rows)
            proc+=1
            if proc%300==0: print(f"  ...{proc}/{len(clean)}  logged={total:,} errs={errors}",flush=True)
          except Exception as e:
            errors+=1
            if errors<=5: print(f"  err {tk}: {repr(e)[:90]}",flush=True)
    print(f"\nDONE: logged {total:,} pattern instances (errors {errors}). Table: pattern_memory")


if __name__=="__main__":
    main()
