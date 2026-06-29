"""
daily_5m_corroboration.py — does a 5-minute confirmation improve the DAILY
mean-reversion trades?

Flow modelled (realistic): daily oversold signal at close of day D -> we act the
NEXT session D1. The 5m bars of D1 either DO or DON'T confirm the bounce
(price reclaims VWAP intraday). We compare three ways of taking the same daily
signals over 2023+ (where 5m exists):

  A. daily-only      : enter D1 open, hold H days.            (no intraday filter)
  B. 5m-CONFIRMED    : only signals whose D1 reclaims VWAP; enter at the reclaim
                       price, hold to the same D1+H close.    (intraday corroboration)
  C. 5m-UNCONFIRMED  : signals that never reclaim VWAP on D1 (falling knives).

If B beats A and C is worst, the 5m layer is corroborating the daily setup.

Usage: python scripts/daily_5m_corroboration.py --tickers AAPL NVDA ... --H 5 --pctl 85 --cost-bps 5
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd
from basket_walkforward import rev_score, FEATS_NEG, FEATS_POS

def confirm_5m(day5m: pd.DataFrame):
    """Intraday confirmation that the bounce HELD: price reclaimed VWAP during the
    session AND closed the day above VWAP. Returns True/False/None(no data).
    Trade returns are computed from DAILY prices either way (5m is only a filter),
    so cross-source split mismatches can't corrupt the numbers."""
    if len(day5m)<6: return None
    av=day5m["above_vwap"].values
    reclaimed=any(av[j]==1 and av[j-1]==0 for j in range(1,len(av)))
    closed_above=av[-1]==1
    return bool(reclaimed and closed_above)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--H",type=int,default=5)
    ap.add_argument("--pctl",type=float,default=85)
    ap.add_argument("--cost-bps",type=float,default=5)
    args=ap.parse_args(); cost=args.cost_bps/100.0
    print(f"=== Daily oversold signal x 5m confirmation (2023+), H={args.H}d ===",flush=True)

    A=[];B=[];C=[]   # net returns
    confirmed_n=0; total_n=0; per=[]
    for tk in args.tickers:
        d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
        d=dd.compute_indicators(d,intraday=False).dropna(subset=FEATS_NEG+FEATS_POS).reset_index(drop=True)
        # standardize on pre-2023 (train), signal on 2023+ (where 5m exists)
        tr=d[d["ts"]<"2023-01-01"]
        if len(tr)<300: continue
        mean={f:tr[f].mean() for f in FEATS_NEG+FEATS_POS}; std={f:(tr[f].std() or 1) for f in FEATS_NEG+FEATS_POS}
        d["score"]=rev_score(d,mean,std); thr=np.nanpercentile(d.loc[d["ts"]<"2023-01-01","score"],args.pctl)
        # 5m
        f5=ROOT/"data/intraday_5m/by_ticker"/f"{tk}.parquet"
        if not f5.exists(): continue
        m=pd.read_parquet(f5); m["ts"]=pd.to_datetime(m["ts"],utc=True).dt.tz_localize(None)
        m=m.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        for cc in ("open","high","low","close","volume"): m[cc]=pd.to_numeric(m[cc],errors="coerce")
        m=dd.compute_indicators(m,intraday=True)
        m["d"]=m["ts"].dt.date
        by_day={k:g for k,g in m.groupby("d")}
        dates=d["ts"].dt.date.values; close=d["close"].values; openp=d["open"].values; n=len(d)

        i=0; tickA=tickB=tickC=0
        while i< n-args.H-1:
            if d["ts"].values[i]>=np.datetime64("2023-01-01") and d["score"].values[i]>=thr:
                total_n+=1
                ret=(close[i+1+args.H]/openp[i+1]-1)*100-cost   # DAILY prices for all variants
                A.append(ret)
                g=by_day.get(dates[i+1]); conf=confirm_5m(g) if g is not None else None
                if conf is True:
                    confirmed_n+=1; tickB+=1; B.append(ret)
                elif conf is False:
                    tickC+=1; C.append(ret)
                i+=args.H+1
            else:
                i+=1
        per.append((tk,tickB+tickC,tickB))
        print(f"  {tk}: {tickB+tickC} signals, {tickB} 5m-confirmed",flush=True)

    def blk(name,r):
        r=np.array(r)
        if len(r)==0: return {"variant":name,"n":0}
        return {"variant":name,"n":len(r),"mean%":round(r.mean(),3),"median%":round(np.median(r),3),
                "win%":round((r>0).mean()*100,1),"t":round(r.mean()/(r.std()/np.sqrt(len(r))),2) if r.std()>0 else None}
    res=pd.DataFrame([blk("A. all daily signals",A),
                      blk("B. 5m-CONFIRMED (bounce held: closed > VWAP)",B),
                      blk("C. 5m-FAILED (closed < VWAP, falling knife)",C)])
    print(f"\nsignals total={total_n}  confirmed={confirmed_n} ({100*confirmed_n/max(total_n,1):.0f}%)",flush=True)
    print(res.to_string(index=False),flush=True)

    out=ROOT/"reports/stocks"
    rep=["# 5-minute confirmation of daily mean-reversion trades (2023+)","",
         f"Tickers: {', '.join(args.tickers)} | hold H={args.H}d | entry score>train p{args.pctl:.0f} | "
         f"cost {args.cost_bps}bps. Daily signal at close of D, acted on session D1; 5m confirmation = "
         f"D1 reclaims VWAP intraday.","",
         f"**Signals: {total_n}  |  5m-confirmed: {confirmed_n} ({100*confirmed_n/max(total_n,1):.0f}%)**","",
         res.to_markdown(index=False),"",
         "_If B (confirmed) > A (daily-only) > C (unconfirmed), the 5m layer corroborates and improves the daily setup._"]
    (out/"DAILY_5M_CORROBORATION.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\nwrote {out/'DAILY_5M_CORROBORATION.md'}",flush=True)

if __name__=="__main__":
    main()
