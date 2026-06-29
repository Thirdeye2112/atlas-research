"""
swing_pullback_study.py — first run -> first pullback, measured properly.

For each up-leg (first run = swing low -> swing high), measure the FIRST pullback
as a TRUE % OF THE RUN (retrace fraction):
    retrace_frac = (peak - pullback_low) / (peak - start)      # 0.5 = gave back half the run
plus the run's speed/size and the TIMING (bars to the peak = when the pullback
begins, and pullback duration). Then test whether leg-1 speed + rise predict:
    (a) how DEEP the first pullback is  (retrace_frac)
    (b) WHEN it comes               (run_bars to peak)
If predictable -> compute the add-to-position level: peak - retrace_frac*(peak-start).

Usage: python scripts/swing_pullback_study.py --tickers AAPL NVDA ... --width 3 --min-amp 0.03 --early 5
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

def legs(tk,width,min_amp,early):
    d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
    d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
    h=d["high"].values;l=d["low"].values;c=d["close"].values;o=d["open"].values
    atr=d["atr_pct"].values; vr=d["vol_ratio"].values; rsi=d["rsi"].values; de20=d["dist_ema20"].values; mr=d["mr"].values; N=len(d)
    piv=ta_structure.swing_pivots(h,l,width=width)
    out=[]
    for lg in ta_patterns.swing_legs(piv,h,l,c,min_amp=min_amp,early_n=early):
        a=lg["start_idx"]; b=lg["peak_idx"]; ci=lg["corr_idx"]
        if ci is None or not (a<b<ci) or a+early>=N: continue
        sp=l[a]; pk=h[b]; pb=l[ci]                       # swing extremes
        run=pk-sp
        if run<=0 or sp<=0: continue
        run_pct=run/sp*100; run_bars=b-a
        retrace_frac=(pk-pb)/run                          # *** pullback as % OF THE RUN ***
        drop_from_high=(pk-pb)/pk*100
        e1=min(a+early,b); early_slope=((c[e1]-c[a])/c[a]*100)/max(e1-a,1)
        speed=run_pct/max(run_bars,1)
        out.append(dict(ticker=tk,run_pct=run_pct,run_bars=run_bars,speed=speed,early_slope=early_slope,
            retrace_frac=retrace_frac,drop_from_high=drop_from_high,pb_bars=ci-b,
            start_atr=atr[a],start_rsi=rsi[a],start_de20=de20[a],start_mr=mr[a],early_vol=np.nanmean(vr[a:e1+1])))
    return out

def fit(df,cols,target):
    d=df.dropna(subset=cols+[target])
    if len(d)<200: return None
    X=d[cols].values; y=d[target].values
    Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=0)
    m=LinearRegression().fit(Xtr,ytr); r2=r2_score(yte,m.predict(Xte))
    beta=dict(zip(cols,np.round(m.coef_*d[cols].std().values/y.std(),3)))
    return r2,beta

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=3); ap.add_argument("--min-amp",type=float,default=0.03)
    ap.add_argument("--early",type=int,default=5); a=ap.parse_args()
    R=pd.DataFrame(sum((legs(tk,a.width,a.min_amp,a.early) for tk in a.tickers),[]))
    R=R.replace([np.inf,-np.inf],np.nan)
    # clip extreme retrace (full reversals) for the depth view but keep a reversal flag
    R["reversal"]=(R["retrace_frac"]>1.0).astype(int)
    Rc=R[(R["retrace_frac"]>0)&(R["retrace_frac"]<=1.5)]
    print(f"=== First run -> first pullback: {len(R)} legs, {R['ticker'].nunique()} names ===\n",flush=True)
    q=Rc["retrace_frac"].quantile([.25,.5,.75])
    print(f"PULLBACK AS % OF THE RUN (retrace_frac): Q1 {q[.25]:.2f}  MEDIAN {q[.5]:.2f}  Q3 {q[.75]:.2f}",flush=True)
    print(f"  full reversals (retrace>100% of run): {100*R['reversal'].mean():.0f}% of legs",flush=True)
    print(f"  drop from high: median {Rc['drop_from_high'].median():.1f}% | pullback duration median {Rc['pb_bars'].median():.0f} bars",flush=True)

    print("\nCORRELATIONS (Spearman) — leg-1 speed/rise vs pullback depth & timing:",flush=True)
    cm=Rc[["speed","run_pct","early_slope","run_bars","start_atr","start_mr",
           "retrace_frac","pb_bars"]].corr(method="spearman")
    print("  speed       vs retrace_frac:",round(cm.loc["speed","retrace_frac"],3),
          " | run_pct vs retrace_frac:",round(cm.loc["run_pct","retrace_frac"],3),
          " | early_slope vs retrace_frac:",round(cm.loc["early_slope","retrace_frac"],3),flush=True)
    print("  speed vs run_bars(when peak):",round(cm.loc["speed","run_bars"],3),
          " | run_pct vs pb_bars:",round(cm.loc["run_pct","pb_bars"],3),flush=True)

    print("\nBUCKETS — by leg-1 SPEED: avg retrace, run_bars, reversal%:",flush=True)
    Rc=Rc.copy(); Rc["sp_b"]=pd.qcut(Rc["speed"].rank(method="first"),4,labels=["slow","med","fast","v.fast"])
    print(Rc.groupby("sp_b").agg(n=("retrace_frac","size"),retrace=("retrace_frac","median"),
        run_bars=("run_bars","median"),reversal=("reversal","mean")).round(3).to_string(),flush=True)
    print("\nBUCKETS — by leg-1 RUN SIZE: avg retrace, reversal%:",flush=True)
    Rc["rn_b"]=pd.qcut(Rc["run_pct"].rank(method="first"),4,labels=["small","med","big","huge"])
    print(Rc.groupby("rn_b").agg(n=("retrace_frac","size"),retrace=("retrace_frac","median"),
        reversal=("reversal","mean")).round(3).to_string(),flush=True)

    fd=fit(Rc,["speed","run_pct","early_slope","start_atr","start_mr","early_vol"],"retrace_frac")
    ft=fit(Rc,["speed","early_slope","run_pct","start_atr"],"run_bars")
    print("\nPREDICTABILITY:",flush=True)
    if fd: print(f"  pullback DEPTH (retrace_frac) OOS R^2={fd[0]:.3f}  drivers: "
                 +", ".join(f"{k} {v:+.2f}" for k,v in sorted(fd[1].items(),key=lambda x:-abs(x[1]))[:5]),flush=True)
    if ft: print(f"  pullback TIMING (bars to peak) OOS R^2={ft[0]:.3f}  drivers: "
                 +", ".join(f"{k} {v:+.2f}" for k,v in sorted(ft[1].items(),key=lambda x:-abs(x[1]))[:5]),flush=True)

    out=ROOT/"reports/stocks"
    rep=[f"# First run → first pullback ({len(R)} legs, {R['ticker'].nunique()} names)","",
         f"Pullback measured as a TRUE % OF THE RUN: retrace_frac = (peak−pullback_low)/(peak−start).","",
         "## How deep is the first pullback (as % of the first run)?","",
         f"- **Q1 {q[.25]:.2f} / median {q[.5]:.2f} / Q3 {q[.75]:.2f}** of the run.",
         f"- Full reversals (gives back >100% of the run): **{100*R['reversal'].mean():.0f}%** of legs.",
         f"- Drop from high: median {Rc['drop_from_high'].median():.1f}%; pullback lasts ~{Rc['pb_bars'].median():.0f} bars.","",
         "## Does leg-1 speed/rise predict the pullback?","",
         f"- speed → retrace_frac: **{cm.loc['speed','retrace_frac']:+.3f}** | run_pct → retrace: **{cm.loc['run_pct','retrace_frac']:+.3f}** "
         f"| early_slope → retrace: {cm.loc['early_slope','retrace_frac']:+.3f}",
         f"- speed → bars-to-peak (timing): **{cm.loc['speed','run_bars']:+.3f}**","",
         "### By leg-1 speed","",Rc.groupby("sp_b").agg(n=("retrace_frac","size"),median_retrace=("retrace_frac","median"),
            median_run_bars=("run_bars","median"),reversal_rate=("reversal","mean")).round(3).to_markdown(),"",
         "### By leg-1 run size","",Rc.groupby("rn_b").agg(n=("retrace_frac","size"),median_retrace=("retrace_frac","median"),
            reversal_rate=("reversal","mean")).round(3).to_markdown(),"",
         "## Predictability (OOS R²)",""]
    if fd: rep+=[f"- pullback **DEPTH** retrace_frac: R²={fd[0]:.3f} — drivers "+", ".join(f"`{k}` {v:+.2f}" for k,v in sorted(fd[1].items(),key=lambda x:-abs(x[1]))[:5])]
    if ft: rep+=[f"- pullback **TIMING** bars-to-peak: R²={ft[0]:.3f} — drivers "+", ".join(f"`{k}` {v:+.2f}" for k,v in sorted(ft[1].items(),key=lambda x:-abs(x[1]))[:5])]
    rep+=["","_Add-to-position level ≈ peak − retrace_frac × (peak − start). Reliable only as far as R² allows._"]
    (out/"SWING_PULLBACK_STUDY.md").write_text("\n".join(rep),encoding="utf-8"); R.to_csv(out/"swing_pullback.csv",index=False)
    print(f"\nwrote {out/'SWING_PULLBACK_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
