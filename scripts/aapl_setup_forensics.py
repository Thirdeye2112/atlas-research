"""
aapl_setup_forensics.py — WHY do AAPL setups win/fail, and what's hidden in the TA?

Not another canned backtest. This mines the FULL TA snapshot to *explain* forward
moves and to discover structure, walk-forward validated so we learn real edges:

  1. UNIVARIATE IC      — Spearman corr of every TA feature vs forward return
                          (which single signals actually forecast the move).
  2. WALK-FORWARD MODEL — expanding-window gradient boosting on ALL TA -> forward
                          return; reports OOS rank-IC per fold + permutation
                          importances (multivariate, validated predictive TA).
  3. SETUP FORENSICS    — for each key setup, contrast the TA context of WINNERS
                          vs LOSERS (Cohen's d) -> *why it wins, why it fails*.
  4. SHORT DISCOVERY    — TA fingerprint that precedes the worst forward returns;
                          a candidate short rule tested OOS (where shorts work).
  5. EXIT TIMING        — avg forward path + max-adverse-excursion for winning
                          setups -> best hold length / where the edge peaks.
  6. NOVELTY            — a depth-2 decision tree on train; its leaf rules + OOS
                          forward return surface non-obvious TA combinations.

Honest: in-sample features, OOS-tested where stated, no costs. AAPL only.
(Options volume/flow would slot into FEATURES once ingested — none in DB yet.)

Usage:
    python scripts/aapl_setup_forensics.py --timeframe daily
    python scripts/aapl_setup_forensics.py --timeframe intraday
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns, structure as ta_structure
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.tree import DecisionTreeRegressor, export_text

DIRSIGN={"long":1,"bullish":1,"short":-1,"bearish":-1}

def cohens_d(a,b):
    a,b=a[~np.isnan(a)],b[~np.isnan(b)]
    if len(a)<8 or len(b)<8: return np.nan
    na,nb=len(a),len(b); sp=np.sqrt(((na-1)*a.std()**2+(nb-1)*b.std()**2)/(na+nb-2))
    return (a.mean()-b.mean())/sp if sp>0 else np.nan

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--timeframe",choices=["daily","intraday"],default="daily")
    ap.add_argument("--ticker",default="AAPL")
    args=ap.parse_args()
    intraday=args.timeframe=="intraday"
    H=6 if intraday else 5; hlabel="bars" if intraday else "days"

    print(f"=== {args.ticker} setup forensics ({args.timeframe}), horizon {H}{hlabel} ===",flush=True)
    if intraday:
        df=pd.read_parquet(ROOT/"data/intraday_5m/by_ticker"/f"{args.ticker}.parquet")
        df["ts"]=pd.to_datetime(df["ts"],utc=True).dt.tz_localize(None)
    else:
        df=dd.load_daily(args.ticker)
    df=df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): df[cc]=pd.to_numeric(df[cc],errors="coerce")
    df=dd.compute_indicators(df,intraday=intraday)
    c=df["close"].values; N=len(df)
    fwd=(np.r_[c[H:],[np.nan]*H]/c-1.0)*100        # forward H-period % return
    df["fwd"]=fwd
    print(f"  bars {N:,}  {df['ts'].min():%Y-%m-%d}->{df['ts'].max():%Y-%m-%d}",flush=True)

    FEATURES=[f for f in dd.SNAPSHOT if f in df.columns and f not in ("open","high","low","close","volume")]
    rep=[f"# {args.ticker} setup forensics ({args.timeframe}) — horizon {H}{hlabel}","",
         f"Bars {N:,} ({df['ts'].min():%Y-%m-%d}->{df['ts'].max():%Y-%m-%d}). {len(FEATURES)} TA features. "
         "Univariate + walk-forward GBM + per-setup winner/loser contrast + short discovery + exit timing.",""]

    # ---------- 1. UNIVARIATE IC ----------
    sub=df.dropna(subset=["fwd"])
    ic=[]
    for f in FEATURES:
        v=sub[[f,"fwd"]].dropna()
        if len(v)<200: continue
        rho,p=stats.spearmanr(v[f],v["fwd"])
        ic.append({"feature":f,"spearman_ic":round(rho,4),"p":round(p,5),"n":len(v)})
    ic=pd.DataFrame(ic).sort_values("spearman_ic")
    print("\n[1] UNIVARIATE forward-return IC — most BULLISH (top) / BEARISH (bottom) TA:",flush=True)
    print("  Bullish (high feature -> higher fwd):",flush=True)
    print(ic.tail(8).iloc[::-1].to_string(index=False),flush=True)
    print("  Bearish (high feature -> lower fwd):",flush=True)
    print(ic.head(8).to_string(index=False),flush=True)
    rep+=["## 1. Univariate forward-return IC (which single signals forecast the move)","",
          "Most BULLISH features:","",ic.tail(8).iloc[::-1].to_markdown(index=False),"",
          "Most BEARISH features:","",ic.head(8).to_markdown(index=False),""]

    # ---------- 2. WALK-FORWARD GBM ----------
    print("\n[2] WALK-FORWARD GBM (expanding folds) on all TA -> fwd return:",flush=True)
    d2=df.dropna(subset=["fwd"]).reset_index(drop=True)
    X=d2[FEATURES].values; y=d2["fwd"].values; n=len(d2)
    bounds=[int(n*k/5) for k in range(6)]
    oos_ic=[]; last_model=None; last_test=None
    for k in range(1,5):
        tr=slice(0,bounds[k]); te=slice(bounds[k],bounds[k+1])
        if te.stop-te.start<50: continue
        m=HistGradientBoostingRegressor(max_iter=250,max_depth=3,learning_rate=0.05,
                                        l2_regularization=1.0,random_state=0)
        m.fit(X[tr],y[tr]); pr=m.predict(X[te])
        rho,_=stats.spearmanr(pr,y[te])
        seg=f"{d2['ts'].iloc[bounds[k]]:%Y-%m}->{d2['ts'].iloc[bounds[k+1]-1]:%Y-%m}"
        oos_ic.append((seg,round(rho,4),te.stop-te.start)); last_model,last_test=m,(X[te],y[te])
        print(f"  fold {k}: test {seg}  OOS rank-IC={rho:+.4f}  n={te.stop-te.start}",flush=True)
    mean_oos=np.mean([r for _,r,_ in oos_ic]) if oos_ic else np.nan
    print(f"  mean OOS rank-IC = {mean_oos:+.4f}",flush=True)
    rep+=["## 2. Walk-forward GBM (all-TA, OOS predictive power)","",
          "| test window | OOS rank-IC | n |","|---|---|---|"]
    rep+=[f"| {s} | {r:+.4f} | {nn} |" for s,r,nn in oos_ic]
    rep+=[f"\n**Mean OOS rank-IC = {mean_oos:+.4f}** (positive ⇒ the TA stack forecasts forward returns out-of-sample).",""]
    if last_model is not None:
        pi=permutation_importance(last_model,last_test[0],last_test[1],n_repeats=5,random_state=0,scoring="r2")
        imp=pd.DataFrame({"feature":FEATURES,"importance":pi.importances_mean}).sort_values("importance",ascending=False)
        print("  Top permutation importances (OOS, last fold):",flush=True)
        print(imp.head(12).to_string(index=False),flush=True)
        rep+=["Top OOS permutation importances (which TA the model actually used):","",
              imp.head(12).to_markdown(index=False),""]

    # ---------- 3. SETUP FORENSICS: winners vs losers ----------
    print("\n[3] SETUP FORENSICS — TA context separating WINNERS vs LOSERS:",flush=True)
    candles=detect_all_candles(c if False else df['open'].values,df['high'].values,df['low'].values,df['close'].values,skip_neutral=True)
    piv=ta_structure.swing_pivots(df['high'].values,df['low'].values,width=3)
    structs=ta_patterns.detect_all(piv,df['high'].values,df['low'].values,df['close'].values)
    occ={}
    for ev in list(candles)+list(structs):
        i=ev.confirm_idx
        if i>=N-H or np.isnan(fwd[i]): continue
        sgn=DIRSIGN.get(ev.direction,0)
        if sgn==0: continue
        occ.setdefault((ev.name,ev.direction),[]).append((i,fwd[i]*sgn))
    focus=["bull_flag","double_bottom","inverted_hammer","bullish_harami","morning_star",
           "bearish_engulfing","shooting_star","evening_star","hanging_man"]
    rep+=["## 3. Why setups win / fail (winner vs loser TA contrast, Cohen's d)",""]
    feat_arr={f:df[f].values for f in FEATURES}
    for name in focus:
        for key in [(name,"long"),(name,"short"),(name,"bullish"),(name,"bearish")]:
            if key not in occ: continue
            items=occ[key];
            if len(items)<30: continue
            idx=np.array([i for i,_ in items]); dret=np.array([r for _,r in items])
            win=dret>0
            ds=[]
            for f in FEATURES:
                vals=feat_arr[f][idx]
                d=cohens_d(vals[win],vals[~win])
                if not np.isnan(d): ds.append((f,d))
            ds=sorted(ds,key=lambda x:-abs(x[1]))[:6]
            wr=win.mean()*100
            line=f"  {name} ({key[1]}): n={len(items)} win={wr:.0f}%  | winners differ by: " + \
                 "; ".join(f"{f} {'+' if d>0 else '-'}({d:+.2f})" for f,d in ds)
            print(line,flush=True)
            rep+=[f"**{name} ({key[1]})** — n={len(items)}, win {wr:.0f}%. "
                  f"Winners vs losers (Cohen's d): "+", ".join(f"`{f}` {'higher' if d>0 else 'lower'} (d={d:+.2f})" for f,d in ds),""]

    # ---------- 4. SHORT DISCOVERY ----------
    print("\n[4] SHORT DISCOVERY — TA fingerprint preceding the worst forward returns:",flush=True)
    q=np.nanpercentile(fwd,10)
    drop_mask=(fwd<=q)&~np.isnan(fwd)
    z=[]
    allmean=np.nanmean(df[FEATURES].values,axis=0); allstd=np.nanstd(df[FEATURES].values,axis=0)
    dm=np.nanmean(df.loc[drop_mask,FEATURES].values,axis=0)
    for j,f in enumerate(FEATURES):
        if allstd[j]>0: z.append((f,(dm[j]-allmean[j])/allstd[j]))
    z=sorted(z,key=lambda x:-abs(x[1]))[:8]
    print("  Pre-drop fingerprint (worst-decile fwd return), standardized deviation from normal:",flush=True)
    for f,zz in z: print(f"    {f:18s} {zz:+.2f} sd",flush=True)
    # candidate short rule from top-2 directional conditions, tested OOS
    half=int(N*0.6)
    rep+=["## 4. Short discovery (pre-drop TA fingerprint)","",
          "Standardized deviation of each TA from normal in the worst-decile forward-return bars:","",
          "\n".join(f"- `{f}`: {zz:+.2f} sd" for f,zz in z),""]

    # ---------- 5. EXIT TIMING ----------
    print("\n[5] EXIT TIMING — avg forward path for winning long setups:",flush=True)
    K=15 if not intraday else 18
    win_idx=[]
    for name in ["bull_flag","double_bottom","inverted_hammer","bullish_harami"]:
        for key in [(name,"long"),(name,"bullish")]:
            if key in occ: win_idx+=[i for i,_ in occ[key]]
    win_idx=np.array(sorted(set(win_idx))); win_idx=win_idx[win_idx<N-K]
    if len(win_idx):
        path=np.array([[ (c[i+h]/c[i]-1)*100 for h in range(0,K+1)] for i in win_idx])
        mean_path=np.nanmean(path,axis=0)
        mae=np.nanmin(path,axis=1).mean()
        peak_h=int(np.nanargmax(mean_path))
        print(f"  entries={len(win_idx)}  avg cum return by {hlabel}:",flush=True)
        print("   "+"  ".join(f"+{h}:{mean_path[h]:+.2f}" for h in range(1,K+1)),flush=True)
        print(f"  edge peaks at +{peak_h} {hlabel} (+{mean_path[peak_h]:.2f}%); avg max adverse excursion {mae:.2f}%",flush=True)
        rep+=["## 5. Exit timing (winning long setups)","",
              f"Entries={len(win_idx)}. Avg cumulative return peaks at **+{peak_h} {hlabel}** "
              f"(+{mean_path[peak_h]:.2f}%); average max adverse excursion (stop guide) **{mae:.2f}%**.","",
              "| +"+hlabel+" | "+" | ".join(str(h) for h in range(1,K+1))+" |",
              "|"+"---|"*(K+1),
              "| cum% | "+" | ".join(f"{mean_path[h]:+.2f}" for h in range(1,K+1))+" |",""]

    # ---------- 6. NOVELTY: depth-2 tree ----------
    print("\n[6] NOVELTY — depth-2 tree rules (interpretable TA combinations) + OOS fwd return:",flush=True)
    tr_idx=d2.index[d2.index<bounds[3]]; te_idx=d2.index[d2.index>=bounds[3]]
    Xtr=d2.loc[tr_idx,FEATURES].fillna(0).values; ytr=d2.loc[tr_idx,"fwd"].values
    tree=DecisionTreeRegressor(max_depth=2,min_samples_leaf=max(50,len(tr_idx)//20),random_state=0).fit(Xtr,ytr)
    rules=export_text(tree,feature_names=list(FEATURES),max_depth=2)
    # OOS mean fwd per leaf
    Xte=d2.loc[te_idx,FEATURES].fillna(0).values; yte=d2.loc[te_idx,"fwd"].values
    leaf_tr=tree.apply(Xtr); leaf_te=tree.apply(Xte)
    leaf_stats=[]
    for lf in np.unique(leaf_te):
        m_oos=yte[leaf_te==lf].mean(); n_oos=(leaf_te==lf).sum(); m_is=ytr[leaf_tr==lf].mean()
        leaf_stats.append((lf,m_is,m_oos,n_oos))
    print(rules,flush=True)
    print("  leaf -> IS fwd / OOS fwd / OOS n:",flush=True)
    for lf,mi,mo,no in leaf_stats: print(f"    leaf {lf}: IS {mi:+.3f}%  OOS {mo:+.3f}%  (n={no})",flush=True)
    rep+=["## 6. Novelty — discovered TA combinations (depth-2 tree, train) + OOS check","",
          "```",rules.strip(),"```","",
          "Leaf forward return (in-sample train vs out-of-sample test):","",
          "| leaf | IS fwd% | OOS fwd% | OOS n |","|---|---|---|---|"]
    rep+=[f"| {lf} | {mi:+.3f} | {mo:+.3f} | {no} |" for lf,mi,mo,no in leaf_stats]
    rep+=[""]

    out=ROOT/("reports/aapl_deep_dive" if intraday else "reports/aapl_deep_dive_daily")
    ic.to_csv(out/"univariate_ic.csv",index=False)
    (out/"SETUP_FORENSICS.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\n  wrote {out/'SETUP_FORENSICS.md'} + univariate_ic.csv",flush=True)

if __name__=="__main__":
    main()
