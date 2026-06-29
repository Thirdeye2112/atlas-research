"""
min_info_study.py — fewest candles needed to forecast the run height A.

Fix the sample to runs whose peak is >=MINBARS bars out (so prediction is real,
not leakage). Then predict the FULL run size A (= leg_amp, low->peak) using only
the first k candles off the low, for k = 1..5, and watch OOS R^2 grow. The "knee"
= the fewest candles that capture most of the predictable signal.

Per candle j we use: that bar's return, body/ATR (long-candle), volume ratio,
range, wick; plus cumulative gain through candle k; plus the launch context known
at the low (RSI, ATR%, dist-EMA20, mr_score). Reports R^2(k), the incremental
gain per candle, top features, and a simple linear formula at the knee.

Usage: python scripts/min_info_study.py --tickers AAPL NVDA ... --minbars 6 --maxk 5
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

def collect(tk,width,min_amp,maxk):
    d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
    d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
    o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values
    body=d["body_pct"].values; atr=d["atr_pct"].values; vr=d["vol_ratio"].values
    rsi=d["rsi"].values; de20=d["dist_ema20"].values; mr=d["mr"].values; N=len(d)
    rows=[]
    for lg in ta_patterns.swing_legs(piv:=ta_structure.swing_pivots(h,l,width=width),h,l,c,min_amp=min_amp):
        a=lg["start_idx"]; b=lg["peak_idx"]
        if a+maxk>=N or b<=a: continue
        rec=dict(ticker=tk,leg_amp=(c[b]-c[a])/c[a]*100,leg_bars=b-a,
                 L_rsi=rsi[a],L_atr=atr[a],L_de20=de20[a],L_mr=mr[a])
        for j in range(1,maxk+1):
            i=a+j
            rec[f"c{j}_ret"]=(c[i]-c[i-1])/c[i-1]*100
            rec[f"c{j}_batr"]=body[i]/atr[i] if atr[i]>0 else np.nan
            rec[f"c{j}_vr"]=vr[i]
            rec[f"c{j}_rng"]=(h[i]-l[i])/c[i]*100
            rec[f"c{j}_cum"]=(c[i]-c[a])/c[a]*100
        rows.append(rec)
    return rows

def feats_for_k(k):
    f=["L_rsi","L_atr","L_de20","L_mr"]
    for j in range(1,k+1): f+=[f"c{j}_ret",f"c{j}_batr",f"c{j}_vr",f"c{j}_rng",f"c{j}_cum"]
    return f

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=3); ap.add_argument("--min-amp",type=float,default=0.03)
    ap.add_argument("--minbars",type=int,default=6); ap.add_argument("--maxk",type=int,default=5)
    a=ap.parse_args()
    R=pd.DataFrame(sum((collect(tk,a.width,a.min_amp,a.maxk) for tk in a.tickers),[])).replace([np.inf,-np.inf],np.nan)
    S=R[R["leg_bars"]>=a.minbars].copy()                       # fixed sample: peak >= minbars out
    print(f"=== Min-info: {len(S)} runs with peak >= {a.minbars} bars out, {S['ticker'].nunique()} names ===",flush=True)
    print(f"  target A = full run %; median {S['leg_amp'].median():.1f}%, mean {S['leg_amp'].mean():.1f}%\n",flush=True)

    y=S["leg_amp"].values
    res=[]; prev=0.0
    for k in range(1,a.maxk+1):
        cols=feats_for_k(k); d=S.dropna(subset=cols)
        X=d[cols].values; yy=d["leg_amp"].values
        Xtr,Xte,ytr,yte=train_test_split(X,yy,test_size=0.3,random_state=0)
        gb=HistGradientBoostingRegressor(max_iter=300,max_depth=3,learning_rate=0.05,l2_regularization=1.0,random_state=0).fit(Xtr,ytr)
        r2=r2_score(yte,gb.predict(Xte))
        lin=LinearRegression().fit(Xtr,ytr); r2l=r2_score(yte,lin.predict(Xte))
        res.append((k,len(d),round(r2,3),round(r2l,3),round(r2-prev,3))); prev=r2
        print(f"  candles 1..{k}: GBM R^2={r2:.3f}  linear R^2={r2l:.3f}  (+{res[-1][4]:+.3f} vs prev)",flush=True)

    # which single features matter most at k=1 and k=2 (correlation with A)
    print("\nMOST PREDICTIVE EARLY FEATURES (|spearman| with A):",flush=True)
    cand=[c for c in S.columns if c.startswith(("c1_","c2_","L_"))]
    ic=S[cand+["leg_amp"]].corr(method="spearman")["leg_amp"].drop("leg_amp").abs().sort_values(ascending=False)
    print(ic.head(8).round(3).to_string(),flush=True)

    # simple interpretable formula at the knee (k=2)
    k=min(2,a.maxk); cols=feats_for_k(k); d=S.dropna(subset=cols)
    lin=LinearRegression().fit(d[cols].values,d["leg_amp"].values)
    beta=dict(zip(cols,lin.coef_)); sbeta=dict(zip(cols,lin.coef_*d[cols].std().values/d["leg_amp"].std()))
    top=sorted(sbeta.items(),key=lambda x:-abs(x[1]))[:5]
    print(f"\nSIMPLE FORMULA (candles 1..{k}, linear): A ≈ {lin.intercept_:.2f} + " +
          " + ".join(f"{beta[k_]:+.2f}·{k_}" for k_,_ in top),flush=True)
    print("  (top standardized drivers: "+", ".join(f"{k_} {v:+.2f}" for k_,v in top)+")",flush=True)

    out=ROOT/"reports/stocks"
    rep=[f"# Fewest candles to forecast the run height A ({len(S)} runs, peak ≥{a.minbars} bars out, {S['ticker'].nunique()} names)","",
         f"Target A = full run % (low→peak); median {S['leg_amp'].median():.1f}%. Fixed sample, vary how many early candles we feed.","",
         "## Predictive power vs candles used","",
         "| candles | n | GBM R² | linear R² | Δ vs prev |","|---|---|---|---|---|"]
    rep+=[f"| 1..{k} | {n} | {g} | {ln} | {dd_:+.3f} |" for (k,n,g,ln,dd_) in res]
    rep+=["","## Most predictive early features (|Spearman| with A)","",ic.head(8).round(3).to_markdown(),"",
          f"## Simple formula (candles 1..{k})","",
          f"`A ≈ {lin.intercept_:.2f} + "+" + ".join(f"{beta[k_]:+.2f}·{k_}" for k_,_ in top)+"`","",
          "Top standardized drivers: "+", ".join(f"`{k_}` {v:+.2f}" for k_,v in top)+".","",
          "_Knee = the candle count after which extra candles add little R²: that's the fewest you need._"]
    (out/"MIN_INFO_STUDY.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\nwrote {out/'MIN_INFO_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
