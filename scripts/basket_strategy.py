"""
basket_strategy.py — turn the mean-reversion signal into a real equity curve
with stops, position sizing, and a horizon/stop grid. Look-ahead-free:
standardization uses an EXPANDING window (stats strictly before each bar), entry
on a fixed z-score threshold, so no per-fold fitting / no peeking.

Portfolio model: 10 equal-weight slots (10% each, rest cash). For each name, when
flat and reversion z-score >= THR, enter next open; exit on stop (intraday low
<= entry*(1-stop)) or after H days at close. Daily portfolio return = mean of the
10 names' in-position returns. Reports CAGR / vol / Sharpe / maxDD vs basket
buy & hold, across a grid of (H, stop), and saves the best equity curve PNG.

Usage: python scripts/basket_strategy.py --tickers AAPL NVDA ... --thr 1.0
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd
from basket_walkforward import FEATS_NEG, FEATS_POS

def zscore_expanding(df):
    """expanding z (mean/std of all bars strictly before t) -> reversion score."""
    sc=np.zeros(len(df))
    for f in FEATS_NEG+FEATS_POS:
        x=df[f]
        m=x.expanding(min_periods=200).mean().shift(1)
        s=x.expanding(min_periods=200).std().shift(1)
        z=((x-m)/s).values
        sc += (-z if f in FEATS_NEG else z)
    return sc/(len(FEATS_NEG)+len(FEATS_POS))

def name_daily_returns(df, thr, H, stop, cost):
    """per-name daily return series (in position) + trade list."""
    o=df["open"].values; h=df["high"].values; lo=df["low"].values; c=df["close"].values
    sc=df["score"].values; n=len(df)
    ret=np.zeros(n); i=0; trades=[]
    while i<n-1:
        if sc[i]>=thr and not np.isnan(sc[i]):
            entry=o[i+1]                              # enter next open
            j=i+1; exit_px=None; bars=0
            while j<n and bars<H:
                if stop and lo[j]<=entry*(1-stop):   # stop hit intraday
                    exit_px=entry*(1-stop); break
                j+=1; bars+=1
            if exit_px is None:
                j=min(j,n-1); exit_px=c[j]
            # distribute the trade P&L as daily marks from i+1..j
            seg=df.iloc[i+1:j+1]
            if len(seg)>0:
                prev=entry
                for k,(idx,row) in enumerate(seg.iterrows()):
                    px=exit_px if (idx==seg.index[-1]) else row["close"]
                    ret[idx]=px/prev-1; prev=px
                ret[seg.index[-1]]-=cost/100         # cost on exit bar
            trades.append((exit_px/entry-1)*100-cost)
            i=j+1
        else:
            i+=1
    return ret, trades

def metrics(port_ret, dates):
    eq=np.cumprod(1+port_ret);
    yrs=(pd.Timestamp(dates[-1])-pd.Timestamp(dates[0])).days/365.25
    cagr=(eq[-1])**(1/yrs)-1 if yrs>0 else np.nan
    vol=port_ret.std()*np.sqrt(252); shp=port_ret.mean()/port_ret.std()*np.sqrt(252) if port_ret.std()>0 else np.nan
    dd_=eq/np.maximum.accumulate(eq)-1; mdd=dd_.min()
    expo=(port_ret!=0).mean()
    return dict(cagr=cagr,vol=vol,sharpe=shp,maxdd=mdd,exposure=expo,final=eq[-1]),eq

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--thr",type=float,default=1.0)
    ap.add_argument("--cost-bps",type=float,default=5)
    args=ap.parse_args(); cost=args.cost_bps/100.0

    # load + score each name, align on common date index
    data={}
    for tk in args.tickers:
        d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
        d=dd.compute_indicators(d,intraday=False)
        d["score"]=zscore_expanding(d)
        data[tk]=d.set_index("ts")
    alldates=sorted(set().union(*[set(d.index) for d in data.values()]))
    idx=pd.DatetimeIndex(alldates)

    print(f"=== Basket strategy grid (thr z>={args.thr}, {len(args.tickers)} names) ===",flush=True)
    grid=[]; best=None
    for H in (5,10):
        for stop in (None,0.05,0.035):
            per=[]
            for tk,d in data.items():
                d2=d.reset_index().rename(columns={"index":"ts"})
                r,_=name_daily_returns(d2.assign(ts=d.index),args.thr,H,stop,cost)
                s=pd.Series(r,index=d.index).reindex(idx).fillna(0.0)
                per.append(s)
            port=pd.concat(per,axis=1).mean(axis=1).values          # equal-weight 10 slots
            m,eq=metrics(port,idx.values)
            row={"H":H,"stop":("none" if not stop else f"{stop:.1%}"),**{k:round(v,3) for k,v in m.items()}}
            grid.append(row)
            sc=m["sharpe"]
            if best is None or sc>best[0]: best=(sc,H,stop,eq,port)
            print(f"  H={H} stop={row['stop']}: CAGR {m['cagr']:.1%} Sharpe {m['sharpe']:.2f} "
                  f"maxDD {m['maxdd']:.1%} expo {m['exposure']:.0%}",flush=True)

    # benchmark: equal-weight buy&hold of the basket
    bh=[]
    for tk,d in data.items():
        rr=d["close"].pct_change().reindex(idx).fillna(0.0); bh.append(rr)
    bhport=pd.concat(bh,axis=1).mean(axis=1).values
    bm,bheq=metrics(bhport,idx.values)
    print(f"  buy&hold basket: CAGR {bm['cagr']:.1%} Sharpe {bm['sharpe']:.2f} maxDD {bm['maxdd']:.1%}",flush=True)

    gdf=pd.DataFrame(grid)
    # equity curve PNG for best config + benchmark
    _,H,stop,eq,_=best
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(11,5))
        ax.plot(idx,eq,label=f"Mean-reversion (H={H}, stop={'none' if not stop else f'{stop:.1%}'})",lw=1.3)
        ax.plot(idx,bheq,label="Basket buy & hold",lw=1.0,alpha=0.8)
        ax.set_yscale("log"); ax.set_title("Mean-reversion strategy vs basket buy & hold (equal-weight, 10 names)")
        ax.legend(); ax.grid(alpha=0.3)
        fig.savefig(ROOT/"reports/stocks/equity_curve.png",dpi=130,bbox_inches="tight"); plt.close(fig)
    except Exception as e: print("  chart failed:",e)

    out=ROOT/"reports/stocks"
    rep=["# Mean-reversion strategy — equity curve, stops & sizing","",
         f"Equal-weight 10-slot portfolio (10% each, rest cash). Entry: expanding-z reversion "
         f"score >= {args.thr}; exit on stop or after H days. Look-ahead-free; cost {args.cost_bps}bps RT.","",
         "## Grid (horizon x stop)","",gdf.to_markdown(index=False),"",
         f"## Benchmark — basket buy & hold","",
         f"CAGR {bm['cagr']:.1%} | Sharpe {bm['sharpe']:.2f} | maxDD {bm['maxdd']:.1%}","",
         "![equity](equity_curve.png)","",
         "_Strategy is in cash when no signal (see `exposure`), so lower vol/DD is expected; "
         "compare Sharpe and drawdown, not just CAGR._"]
    (out/"STRATEGY_EQUITY.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\nwrote {out/'STRATEGY_EQUITY.md'} + equity_curve.png",flush=True)

if __name__=="__main__":
    main()
