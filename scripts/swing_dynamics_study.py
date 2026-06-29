"""
swing_dynamics_study.py — what predicts the RUN and the PULLBACK?

Using swing pivots as the (hindsight) tops/bottoms, for every up-leg we measure a
rich set of EARLY/observable features (speed, volume, candle-size-per-volatility,
acceleration, launch conditions) and correlate them with the leg's eventual
amplitude, velocity, whether it goes parabolic, and the depth of the following
pullback (and that pullback as a % of the run). Then we fit a simple formula to
predict the leg target + the pullback rebuy level from the early signature.

Questions answered:
  * does SPEED (early slope) predict the eventual RISE?
  * does a LONG CANDLE (big body / ATR) early predict more run — or exhaustion?
  * is the PULLBACK a stable % of the run (-> a rebuy target)?
  * parabolic (accelerating) legs -> deeper pullbacks / reversals?
  * a fitted target-exit formula (expected leg %, expected pullback %) with R^2.

Usage: python scripts/swing_dynamics_study.py --tickers AAPL NVDA ... --width 3 --min-amp 0.03 --early 5
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

EARLY_FEATS=["early_slope","early_gain","early_vol_ratio","early_body_atr","early_accel",
             "early_green_frac","start_rsi","start_atr_pct","start_dist_ema20","start_mr","early_volz"]

def build_legs(tk, width, min_amp, early):
    d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
    d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
    o=d["open"].values;h=d["high"].values;l=d["low"].values;c=d["close"].values;v=d["volume"].values
    body=d["body_pct"].values; atr=d["atr_pct"].values; vr=d["vol_ratio"].values; volz=d["vol_z"].values
    rsi=d["rsi"].values; de20=d["dist_ema20"].values; mr=d["mr"].values; N=len(d)
    piv=ta_structure.swing_pivots(h,l,width=width)
    legs=ta_patterns.swing_legs(piv,h,l,c,min_amp=min_amp,early_n=early)
    rows=[]
    for lg in legs:
        a=lg["start_idx"]; b=lg["peak_idx"]; ci=lg["corr_idx"]
        if b-a<2 or a+early>=N: continue
        e0,e1=a, min(a+early,b)
        seg=slice(e0,e1+1)
        leg_amp=(c[b]-c[a])/c[a]*100; leg_bars=b-a; vel=leg_amp/leg_bars
        # early/observable
        eg=(c[e1]-c[a])/c[a]*100; eb=e1-e0; eslope=eg/eb if eb else 0
        evr=np.nanmean(vr[seg]); evolz=np.nanmean(volz[seg])
        ebody_atr=np.nanmax(body[seg]/np.where(atr[seg]>0,atr[seg],np.nan))  # biggest early candle / ATR
        green=np.mean((c[seg]>o[seg]).astype(float))
        # acceleration: slope of 2nd half of early window minus 1st half
        mid=(e0+e1)//2
        s1=(c[mid]-c[e0])/c[e0]/max(mid-e0,1) if mid>e0 else 0
        s2=(c[e1]-c[mid])/c[mid]/max(e1-mid,1) if e1>mid else 0
        accel=(s2-s1)*100
        # parabolic: last third of the leg faster than first third
        t=a+max(1,(b-a)//3); u=b-max(1,(b-a)//3)
        g_first=(c[t]-c[a])/c[a]/max(t-a,1); g_last=(c[b]-c[u])/c[u]/max(b-u,1)
        parabolic=int(g_last>1.5*g_first and g_first>0)
        # pullback
        corr_depth=((c[b]-c[ci])/c[b]*100) if ci is not None else np.nan
        pb_frac=(corr_depth/leg_amp) if (ci is not None and leg_amp>0) else np.nan
        rows.append(dict(ticker=tk,
            early_slope=eslope,early_gain=eg,early_vol_ratio=evr,early_body_atr=ebody_atr,
            early_accel=accel,early_green_frac=green,start_rsi=rsi[a],start_atr_pct=atr[a],
            start_dist_ema20=de20[a],start_mr=mr[a],early_volz=evolz,
            leg_amp=leg_amp,leg_bars=leg_bars,leg_velocity=vel,parabolic=parabolic,
            corr_depth=corr_depth,pb_frac=pb_frac))
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=3)
    ap.add_argument("--min-amp",type=float,default=0.03)
    ap.add_argument("--early",type=int,default=5)
    a=ap.parse_args()
    R=pd.DataFrame(sum((build_legs(tk,a.width,a.min_amp,a.early) for tk in a.tickers),[]))
    R=R.replace([np.inf,-np.inf],np.nan)
    print(f"=== Swing dynamics: {len(R)} up-legs, {R['ticker'].nunique()} names ===\n",flush=True)

    # 1) correlations: early features vs outcomes
    tgts=["leg_amp","leg_velocity","corr_depth","pb_frac"]
    corr=R[EARLY_FEATS+tgts].corr(method="spearman").loc[EARLY_FEATS,tgts].round(3)
    print("SPEARMAN corr — early features vs outcomes:",flush=True); print(corr.to_string(),flush=True)

    # 2) does the rise predict the pullback? is pullback a stable % of the run?
    cc=R.dropna(subset=["leg_amp","corr_depth","pb_frac"])
    print(f"\nRISE -> PULLBACK: corr(leg_amp, corr_depth)={cc['leg_amp'].corr(cc['corr_depth']):+.3f}",flush=True)
    print(f"  pullback as % OF THE RUN (pb_frac): median {cc['pb_frac'].median():.2f}  "
          f"mean {cc['pb_frac'].mean():.2f}  IQR {cc['pb_frac'].quantile(.25):.2f}-{cc['pb_frac'].quantile(.75):.2f}",flush=True)

    # 3) long-candle bucket -> run & pullback & parabolic
    R["lc_bucket"]=pd.cut(R["early_body_atr"],[0,1,2,3,99],labels=["<1x","1-2x","2-3x",">3x"])
    g=R.groupby("lc_bucket").agg(n=("leg_amp","size"),avg_leg=("leg_amp","mean"),
        avg_pull=("corr_depth","mean"),parab=("parabolic",lambda s:s.mean()*100)).round(2)
    print("\nLONG CANDLE (early max body / ATR) -> outcome:",flush=True); print(g.to_string(),flush=True)

    # 4) speed bucket -> run
    R["sp_bucket"]=pd.qcut(R["early_slope"].rank(method="first"),4,labels=["slow","med","fast","v.fast"])
    gs=R.groupby("sp_bucket").agg(n=("leg_amp","size"),avg_leg=("leg_amp","mean"),avg_vel=("leg_velocity","mean"),
        avg_pull=("corr_depth","mean")).round(2)
    print("\nEARLY SPEED -> outcome:",flush=True); print(gs.to_string(),flush=True)

    # 5) parabolic vs not -> pullback/reversal
    gp=R.groupby("parabolic").agg(n=("leg_amp","size"),avg_leg=("leg_amp","mean"),avg_pull=("corr_depth","mean"),
        pb_frac=("pb_frac","mean")).round(2)
    print("\nPARABOLIC (accelerating into top) vs not:",flush=True); print(gp.to_string(),flush=True)

    # 6) fitted formula: predict leg_amp from early features (OOS R^2), and pullback from leg_amp+speed
    def fit(cols,target,df):
        d=df.dropna(subset=cols+[target]);
        if len(d)<200: return None
        X=d[cols].values; y=d[target].values
        Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=0.3,random_state=0)
        m=LinearRegression().fit(Xtr,ytr); r2=r2_score(yte,m.predict(Xte))
        sd=d[cols].std().values; beta=m.coef_*sd/y.std()    # standardized betas
        return r2,m.intercept_,dict(zip(cols,np.round(m.coef_,4))),dict(zip(cols,np.round(beta,3)))
    f1=fit(EARLY_FEATS,"leg_amp",R)
    f2=fit(["leg_amp","early_slope","early_vol_ratio","parabolic"],"corr_depth",R)
    print("\nFORMULA 1 — predict LEG SIZE (target) from early signature:",flush=True)
    if f1: print(f"  OOS R^2={f1[0]:.3f}  intercept={f1[1]:.2f}\n  std-betas (impact): "
                 +", ".join(f"{k} {v:+.2f}" for k,v in sorted(f1[3].items(),key=lambda x:-abs(x[1]))[:6]),flush=True)
    print("FORMULA 2 — predict PULLBACK depth from leg size + speed:",flush=True)
    if f2: print(f"  OOS R^2={f2[0]:.3f}  coefs: "+", ".join(f"{k} {v:+.3f}" for k,v in f2[2].items()),flush=True)

    out=ROOT/"reports/stocks"
    rep=[f"# Swing dynamics — speed/volume/candle vs run & pullback ({len(R)} up-legs, {R['ticker'].nunique()} names)","",
         "## Early features vs outcomes (Spearman)","",corr.to_markdown(),"",
         f"## Rise -> pullback","",
         f"- corr(leg_amp, pullback depth) = **{cc['leg_amp'].corr(cc['corr_depth']):+.3f}**",
         f"- **pullback is ~{cc['pb_frac'].median():.0%} of the run** (median pb_frac {cc['pb_frac'].median():.2f}, "
         f"IQR {cc['pb_frac'].quantile(.25):.2f}-{cc['pb_frac'].quantile(.75):.2f}) -> rebuy target.","",
         "## Long candle (early body / ATR) -> run / pullback / parabolic %","",g.to_markdown(),"",
         "## Early speed -> run","",gs.to_markdown(),"",
         "## Parabolic vs not","",gp.to_markdown(),"",
         "## Fitted formulas",""]
    if f1: rep+=[f"**Target (leg size)** OOS R^2 = {f1[0]:.3f}. Strongest drivers (std-beta): "
                 +", ".join(f"`{k}` {v:+.2f}" for k,v in sorted(f1[3].items(),key=lambda x:-abs(x[1]))[:6])+".",""]
    if f2: rep+=[f"**Pullback depth** OOS R^2 = {f2[0]:.3f}; coefs "+", ".join(f"`{k}` {v:+.3f}" for k,v in f2[2].items())+".",""]
    rep+=["_Target exit ≈ entry × (1 + predicted leg%); rebuy level ≈ peak × (1 − pb_frac×leg%). "
          "R^2 shows how much of the run/pullback is actually predictable from the early signature._"]
    (out/"SWING_DYNAMICS_STUDY.md").write_text("\n".join(rep),encoding="utf-8"); R.to_csv(out/"swing_dynamics.csv",index=False)
    print(f"\nwrote {out/'SWING_DYNAMICS_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
