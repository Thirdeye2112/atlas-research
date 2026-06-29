"""
run_forecast_study.py — forecast the WHOLE-RUN high A from the fewest candles.

A = highest point of the entire move, riding through pullbacks until a REVERSAL
(a lower swing high / trend break) — not just the first leg. Runs are taken from a
swing low; optionally filtered to those launching out of a CONSOLIDATION with a
volume+range breakout (your setup). For each run we measure:
  * what % of the total run each candle contributes (front-loaded?)
  * how well candle 1, candles 1-2, 1-3 predict A (OOS R^2), ALL vs breakout-only
  * the minimal candles before a tradeable target is forecastable.

Finest data available is 5-minute; 1-minute is NOT in the DB (would need ingest).

Usage: python scripts/run_forecast_study.py --tickers AAPL NVDA ... --width 3 --min-run 5 --maxk 3
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

def whole_runs(piv, h, l, c, start_px_arr):
    """Non-overlapping runs: from a swing low, ride higher-highs until a lower high
    (reversal). Returns list of (a_idx, peak_idx)."""
    out=[]; i=0; n=len(piv)
    while i<n:
        if piv[i].kind!="L": i+=1; continue
        a=piv[i].idx; ult=None; prevH=-1; j=i+1; broke=False
        while j<n:
            p=piv[j]
            if p.kind=="H":
                if p.price>prevH: ult=p; prevH=p.price
                else: break                      # lower high -> reversal
            else:
                if p.price < l[a]: break          # structure broken below start
            j+=1
        if ult is not None and ult.idx>a:
            out.append((a,ult.idx))
            # continue after the peak
            while i<n and piv[i].idx<=ult.idx: i+=1
        else:
            i+=1
    return out

def collect(tk,width,min_run,maxk):
    d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
    d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
    o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values
    body=d["body_pct"].values; atr=d["atr_pct"].values; vr=d["vol_ratio"].values
    rng=d["range_pct"].values; sq=d["bb_squeeze"].values
    rsi=d["rsi"].values; de20=d["dist_ema20"].values; mr=d["mr"].values; N=len(d)
    piv=ta_structure.swing_pivots(h,l,width=width)
    rows=[]
    for a,b in whole_runs(piv,h,l,c,l):
        if a<20 or a+maxk>=N or b<=a: continue
        A_px=h[b]; start=l[a]; run_pct=(A_px-start)/start*100
        if run_pct<min_run or (b-a)<maxk+1: continue          # need peak beyond obs window
        # consolidation-breakout context
        prior_sq=int(np.nanmax(sq[max(0,a-15):a]) if a>0 else 0)
        prior_rng=np.nanmean(rng[max(0,a-15):a])
        brk_vol=vr[a+1] if a+1<N else np.nan
        rec=dict(ticker=tk,run_pct=run_pct,run_bars=b-a,A_px=A_px,start=start,
                 prior_sq=prior_sq,prior_rng=prior_rng,brk_vol=brk_vol,
                 consol_breakout=int(prior_sq==1 and (brk_vol or 0)>1.2),
                 L_atr=atr[a],L_rsi=rsi[a],L_mr=mr[a],L_de20=de20[a])
        for j in range(1,maxk+1):
            i=a+j
            rec[f"c{j}_ret"]=(c[i]-c[i-1])/c[i-1]*100
            rec[f"c{j}_batr"]=body[i]/atr[i] if atr[i]>0 else np.nan
            rec[f"c{j}_vr"]=vr[i]; rec[f"c{j}_rng"]=rng[i]
            rec[f"c{j}_cum"]=(c[i]-start)/start*100
            rec[f"c{j}_contrib"]=(c[i]-start)/(A_px-start) if A_px>start else np.nan  # % of total run by candle j
        rows.append(rec)
    return rows

def feats(k):
    f=["L_atr","L_rsi","L_mr","L_de20","prior_sq","prior_rng","brk_vol"]
    for j in range(1,k+1): f+=[f"c{j}_ret",f"c{j}_batr",f"c{j}_vr",f"c{j}_rng",f"c{j}_cum"]
    return f

def r2_at(df,k,target="run_pct"):
    cols=feats(k); d=df.dropna(subset=cols+[target])
    if len(d)<150: return None
    X=d[cols].values; y=d[target].values
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=0)
    lin=LinearRegression().fit(Xtr,ytr); rl=r2_score(yte,lin.predict(Xte))
    gb=HistGradientBoostingRegressor(max_iter=300,max_depth=3,learning_rate=0.05,l2_regularization=1.0,random_state=0).fit(Xtr,ytr)
    rg=r2_score(yte,gb.predict(Xte))
    return len(d),round(rl,3),round(rg,3),lin

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=3); ap.add_argument("--min-run",type=float,default=5)
    ap.add_argument("--maxk",type=int,default=3); a=ap.parse_args()
    R=pd.DataFrame(sum((collect(tk,a.width,a.min_run,a.maxk) for tk in a.tickers),[])).replace([np.inf,-np.inf],np.nan)
    B=R[R["consol_breakout"]==1]
    print(f"=== Whole-run forecast: {len(R)} runs (>= {a.min_run}% , peak >{a.maxk} bars out), {R['ticker'].nunique()} names ===",flush=True)
    print(f"  whole-run A: median {R['run_pct'].median():.1f}%, mean {R['run_pct'].mean():.1f}%, over median {R['run_bars'].median():.0f} bars",flush=True)
    print(f"  consolidation-breakout subset: {len(B)} runs (median {B['run_pct'].median():.1f}%)" if len(B) else "  (no breakout subset)",flush=True)

    print("\n% OF TOTAL RUN CONTRIBUTED BY EACH CANDLE (median):",flush=True)
    for j in range(1,a.maxk+1):
        col=f"c{j}_contrib"
        print(f"  by candle {j}: {100*R[col].median():.0f}% of the run realized "
              f"(this candle alone ~{100*(R[col].median()-(R[f'c{j-1}_contrib'].median() if j>1 else 0)):.0f}%)",flush=True)

    print("\nPREDICTING WHOLE-RUN A — OOS R^2 by candles used:",flush=True)
    print(f"  {'candles':8s} {'ALL (lin/GBM)':16s} {'BREAKOUT (lin/GBM)':18s}",flush=True)
    rowsout=[]
    for k in range(1,a.maxk+1):
        ra=r2_at(R,k); rb=r2_at(B,k) if len(B)>200 else None
        sa=f"{ra[1]:.3f}/{ra[2]:.3f} (n={ra[0]})" if ra else "n/a"
        sb=f"{rb[1]:.3f}/{rb[2]:.3f} (n={rb[0]})" if rb else "n/a"
        print(f"  1..{k:<5d} {sa:16s} {sb}",flush=True); rowsout.append((k,sa,sb))

    out=ROOT/"reports/stocks"
    rep=[f"# Whole-run forecast from fewest candles ({len(R)} runs, {R['ticker'].nunique()} names)","",
         f"A = ultimate high, riding pullbacks until a lower-high reversal. Runs >= {a.min_run}%, peak > {a.maxk} bars out. "
         f"Daily candles (finest data = 5m; no 1-min in DB).","",
         f"- Whole-run A: median **{R['run_pct'].median():.1f}%** over ~{R['run_bars'].median():.0f} bars.",
         f"- Consolidation-breakout runs: {len(B)} (median {B['run_pct'].median():.1f}%).","",
         "## % of the total run each candle contributes (median)",""]
    for j in range(1,a.maxk+1):
        col=f"c{j}_contrib"; inc=R[col].median()-(R[f'c{j-1}_contrib'].median() if j>1 else 0)
        rep.append(f"- by candle {j}: **{100*R[col].median():.0f}%** of A realized (candle {j} ≈ {100*inc:.0f}%)")
    rep+=["","## Predicting the whole-run A — OOS R² by candles used","",
          "| candles | ALL (lin/GBM) | consolidation-breakout (lin/GBM) |","|---|---|---|"]
    rep+=[f"| 1..{k} | {sa} | {sb} |" for k,sa,sb in rowsout]
    rep+=["","_Fewest candles for a tradeable target = where R² is usefully > 0 and stops climbing. "
          "Compare ALL vs breakout to see if the consolidation context is the cleaner, more forecastable setup._"]
    (out/"RUN_FORECAST_STUDY.md").write_text("\n".join(rep),encoding="utf-8"); R.to_csv(out/"run_forecast.csv",index=False)
    print(f"\nwrote {out/'RUN_FORECAST_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
