"""
build_mr_lookup.py — one-time per (ticker,date) mr_score lookup for the V4
experiment. Trailing-252 z (matches the registered mean_reversion feature),
computed on split-safe ADJUSTED OHLC. Writes exports/parquet/mr_score_lookup.parquet.

Usage: python scripts/build_mr_lookup.py [--limit N]
"""
from __future__ import annotations
import sys, argparse, re, time, urllib.parse as up
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from atlas_research.features import mean_reversion as mr
import psycopg2

NEG=["rsi","bb_pct","dist_ema20","dist_ema200","stoch_k"]; POS=["atr_pct"]; LB=252

def _conn():
    env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
    u=up.urlparse(env["DATABASE_URL"].strip())
    return psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))

def mr_series(o,h,l,c,adj):
    factor=np.where(c>0, adj/c, 1.0)
    comp=mr._components(adj, h*factor, l*factor)          # adjusted-scale OHLC
    score=pd.Series(0.0,index=comp.index);
    for col in NEG+POS:
        s=comp[col]; m=s.rolling(LB,min_periods=200).mean(); sd=s.rolling(LB,min_periods=200).std()
        z=(s-m)/sd; score=score+(-z if col in NEG else z)
    return score/(len(NEG)+len(POS))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    cn=_conn(); cur=cn.cursor()
    cur.execute("select ticker from raw_bars group by ticker having count(*)>=250 order by ticker")
    univ=[r[0] for r in cur.fetchall()]
    if a.limit: univ=univ[:a.limit]
    print(f"building mr_score lookup for {len(univ)} tickers",flush=True)
    out=[]; t0=time.time()
    for i,tk in enumerate(univ,1):
        cur.execute("select date,open,high,low,close,adjusted_close from raw_bars where ticker=%s order by date",(tk,))
        rows=cur.fetchall()
        if len(rows)<250: continue
        d=pd.DataFrame(rows,columns=["date","open","high","low","close","adjusted_close"]).astype(
            {"open":float,"high":float,"low":float,"close":float,"adjusted_close":float})
        s=mr_series(d["open"].values,d["high"].values,d["low"].values,d["close"].values,d["adjusted_close"].values)
        r=pd.DataFrame({"ticker":tk,"date":pd.to_datetime(d["date"]),"mr_score":s.values}).dropna(subset=["mr_score"])
        out.append(r)
        if i%500==0 or i==len(univ):
            print(f"  [{i}/{len(univ)}] {tk} ({i/max(time.time()-t0,1e-9):.1f} tk/s)",flush=True)
    res=pd.concat(out,ignore_index=True)
    p=ROOT/"exports/parquet/mr_score_lookup.parquet"; res.to_parquet(p,index=False)
    print(f"wrote {p}  rows={len(res):,} tickers={res['ticker'].nunique()}",flush=True)

if __name__=="__main__":
    main()
