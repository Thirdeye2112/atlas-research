"""
basket_walkforward.py — embargoed walk-forward validation of the cross-stock
MEAN-REVERSION signal, net of costs, across the 10-stock basket.

Signal (from the cross-stock consensus): a long is favoured when price is
oversold / extended-DOWN / high-vol. We build a standardized reversion score
from the consensus features, fit the standardization + entry threshold on TRAIN
ONLY, then trade it on the embargoed TEST block:

  reversion_score = -z(rsi) - z(bb_pct) - z(dist_ema20) - z(dist_ema200)
                    - z(stoch_k) + z(atr_pct)        (higher = more oversold/extended-down)

Method (V3-style):
  * expanding walk-forward, EMBARGO = H days between train end and test start
    (train rows whose H-day label overlaps the test region are purged).
  * z-means/stds and the entry threshold (TRAIN score percentile) come from train.
  * non-overlapping long trades: enter at close when score>=threshold, exit +H, cost
    deducted round-trip.
  * report OOS net return / win / t-stat per fold, per stock, vs same-horizon
    baseline drift, and cost sensitivity. Also the inverse (overbought) bucket.

Usage:
  python scripts/basket_walkforward.py --tickers AAPL NVDA ... --H 5 --cost-bps 5 --pctl 85
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd

FEATS_NEG=["rsi","bb_pct","dist_ema20","dist_ema200","stoch_k"]  # lower = more oversold
FEATS_POS=["atr_pct"]                                            # higher = more vol

def rev_score(df, mean, std):
    sc=np.zeros(len(df))
    for f in FEATS_NEG: sc += -((df[f].values-mean[f])/std[f])
    for f in FEATS_POS: sc +=  ((df[f].values-mean[f])/std[f])
    return sc/(len(FEATS_NEG)+len(FEATS_POS))

def trades_in(score, close, ts, thr, H, cost):
    """non-overlapping long trades when score>=thr; return list of net returns."""
    out=[]; i=0; n=len(close)
    while i < n-H:
        if score[i]>=thr and not np.isnan(score[i]):
            r=(close[i+H]/close[i]-1)*100 - cost
            out.append((ts[i], r)); i+=H            # lock out for H bars (non-overlap)
        else:
            i+=1
    return out

def run_ticker(tk, H, pctl, cost, folds):
    df=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): df[cc]=pd.to_numeric(df[cc],errors="coerce")
    df=dd.compute_indicators(df,intraday=False).dropna(subset=FEATS_NEG+FEATS_POS).reset_index(drop=True)
    close=df["close"].values; ts=df["ts"].values; n=len(df)
    bnd=[int(n*k/(folds+1)) for k in range(folds+2)]   # folds+1 segments; test on last `folds`
    long_tr=[]; fade_tr=[]; base=[]; perfold=[]
    for k in range(1,folds+1):
        a=bnd[k+0]; b=bnd[k+1]                # test block [a,b)
        tr_end=max(0,a-H)                     # EMBARGO: purge last H train rows
        if tr_end<200: continue
        tr=df.iloc[:tr_end]
        mean={f:tr[f].mean() for f in FEATS_NEG+FEATS_POS}
        std ={f:(tr[f].std() or 1.0) for f in FEATS_NEG+FEATS_POS}
        sc_tr=rev_score(tr,mean,std); thr=np.nanpercentile(sc_tr,pctl); thr_lo=np.nanpercentile(sc_tr,100-pctl)
        te=df.iloc[a:b].reset_index(drop=True)
        sc_te=rev_score(te,mean,std)
        L=trades_in(sc_te,te["close"].values,te["ts"].values,thr,H,cost)        # oversold longs
        F=trades_in(-sc_te,te["close"].values,te["ts"].values,-thr_lo,H,cost)   # overbought "longs" (momentum) — sc<=thr_lo
        # baseline: all non-overlapping H-day holds in test
        cl=te["close"].values; B=[(cl[i+H]/cl[i]-1)*100-cost for i in range(0,len(cl)-H,H)]
        long_tr+=L; fade_tr+=F; base+=B
        if L:
            rr=np.array([r for _,r in L]); seg=f"{pd.Timestamp(te['ts'].values[0]):%Y-%m}->{pd.Timestamp(te['ts'].values[-1]):%Y-%m}"
            perfold.append((tk,seg,len(L),round(rr.mean(),3),round((rr>0).mean()*100,1)))
    return long_tr,fade_tr,base,perfold

def stat_block(name,trades,base,cost):
    r=np.array([x for _,x in trades]) if trades else np.array([])
    b=np.array(base)
    if len(r)==0: return {"strategy":name,"n":0}
    t=r.mean()/(r.std()/np.sqrt(len(r))) if r.std()>0 else np.nan
    return {"strategy":name,"n":len(r),"mean_net%":round(r.mean(),3),"median%":round(np.median(r),3),
            "win%":round((r>0).mean()*100,1),"t":round(t,2),
            "baseline%":round(b.mean(),3) if len(b) else np.nan,
            "excess%":round(r.mean()-(b.mean() if len(b) else 0),3),
            "ann_sharpe~":round(r.mean()/r.std()*np.sqrt(252/ (len(b) and 1) ),2) if r.std()>0 else np.nan}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--H",type=int,default=5)
    ap.add_argument("--pctl",type=float,default=85)
    ap.add_argument("--cost-bps",type=float,default=5)
    ap.add_argument("--folds",type=int,default=5)
    args=ap.parse_args()
    cost=args.cost_bps/100.0   # bps -> % (round trip)
    print(f"=== Basket walk-forward: mean-reversion long, H={args.H}d, entry top {100-args.pctl:.0f}% score, "
          f"cost {args.cost_bps}bps RT, {args.folds} embargoed folds ===",flush=True)

    allL=[]; allF=[]; allB=[]; fold_rows=[]; per_stock=[]
    for tk in args.tickers:
        L,F,B,pf=run_ticker(tk,args.H,args.pctl,cost,args.folds)
        allL+=L; allF+=F; allB+=B; fold_rows+=pf
        if L:
            rr=np.array([r for _,r in L])
            per_stock.append({"ticker":tk,"n_trades":len(L),"mean_net%":round(rr.mean(),3),
                              "win%":round((rr>0).mean()*100,1),
                              "excess%":round(rr.mean()-np.mean(B),3)})
        print(f"  {tk}: {len(L)} OOS reversion trades, mean {np.mean([r for _,r in L]) if L else 0:+.3f}%",flush=True)

    pooled=pd.DataFrame([stat_block("mean-reversion LONG (oversold)",allL,allB,cost),
                         stat_block("inverse: momentum LONG (overbought)",allF,allB,cost),
                         stat_block("baseline: any H-day hold",[(0,x) for x in allB],allB,cost)])
    ps=pd.DataFrame(per_stock).sort_values("excess%",ascending=False)
    ff=pd.DataFrame(fold_rows,columns=["ticker","window","n","mean_net%","win%"])
    foldagg=ff.groupby("window").agg(trades=("n","sum"),mean_net=("mean_net%","mean"),win=("win%","mean")).round(3)

    print("\n--- POOLED OOS (net of costs) ---"); print(pooled.to_string(index=False),flush=True)
    print("\n--- PER STOCK (mean-reversion long, OOS) ---"); print(ps.to_string(index=False),flush=True)
    print("\n--- BY TEST WINDOW (stability) ---"); print(foldagg.to_string(),flush=True)

    # cost sensitivity on pooled longs
    rr=np.array([r for _,r in allL])
    cs=[]
    for bps in [0,5,10,20]:
        adj=rr-(bps/100.0)+(cost)   # rr already had `cost` removed; re-apply at bps
        cs.append({"cost_bps":bps,"mean_net%":round(adj.mean(),3),"win%":round((adj>0).mean()*100,1)})
    cost_df=pd.DataFrame(cs)
    print("\n--- COST SENSITIVITY (pooled reversion long) ---"); print(cost_df.to_string(index=False),flush=True)

    out=ROOT/"reports/stocks"
    rep=["# Embargoed walk-forward — mean-reversion signal across the basket","",
         f"Tickers: {', '.join(args.tickers)}  |  hold H={args.H}d  |  entry: reversion score in top "
         f"{100-args.pctl:.0f}% (threshold fit on TRAIN)  |  cost {args.cost_bps}bps round-trip  |  "
         f"{args.folds} expanding folds, {args.H}-day embargo.","",
         "## Pooled OOS (net of costs)","",pooled.to_markdown(index=False),"",
         "## Per stock — does the reversion edge generalize OOS?","",ps.to_markdown(index=False),"",
         "## Stability by test window","",foldagg.to_markdown(),"",
         "## Cost sensitivity (pooled reversion long)","",cost_df.to_markdown(index=False),"",
         "_Note: long-only; the inverse (overbought) bucket is shown for contrast. "
         "Non-overlapping trades, close-to-close, in-sample standardization is per-fold train-only._"]
    (out/"WALKFORWARD_VALIDATION.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\nwrote {out/'WALKFORWARD_VALIDATION.md'}",flush=True)

if __name__=="__main__":
    main()
