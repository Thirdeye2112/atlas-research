#!/usr/bin/env python
"""
run_v3_v4_experiment.py — does adding the validated mean-reversion feature
(`mr_score`) to the V3 set lift the model OOS edge?

Same embargoed walk-forward harness as run_v1_v3_experiment (identical folds,
trading-day purge, cross-sectional normalisation, leak-free calibration). V4 =
V3 + mr_score. mr_score is merged per (ticker,date) from
exports/parquet/mr_score_lookup.parquet (build_mr_lookup.py).

Usage:
    python scripts/run_v3_v4_experiment.py --oos-feature-set v4
    python scripts/run_v3_v4_experiment.py --max-folds 2     # smoke
"""
from __future__ import annotations
import argparse, json, math, sys, warnings, glob
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT/"src")); sys.path.insert(0,str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT/".env"); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy import stats
from config import settings
from atlas_research.models.dataset import apply_purge_gap, cross_sectional_normalize, load_date_range, to_arrays
from atlas_research.models.train import train_regressor, train_classifier, predict_classifier
from atlas_research.models.evaluate import roc_auc, brier_score
from atlas_research.models.walk_forward import generate_folds, oos_window
from atlas_research.utils.logging import configure_logging, get_logger
configure_logging(); log=get_logger("v3_v4_experiment")

REG_TARGET="label_return_5d"; CLF_TARGET="label_positive_5d"
OUT=ROOT/"reports"/"validity"/"v3_v4_experiment.json"
MRLOOK=ROOT/"exports/parquet/mr_score_lookup.parquet"
_MR=None
def mr_lookup():
    global _MR
    if _MR is None:
        _MR=pd.read_parquet(MRLOOK); _MR["date"]=pd.to_datetime(_MR["date"])
    return _MR

def add_mr(df):
    """merge mr_score onto a loaded fold frame by (ticker,date)."""
    m=mr_lookup(); d=df.copy(); d["date"]=pd.to_datetime(d["date"])
    d=d.merge(m,on=["ticker","date"],how="left")
    return d

def per_day_ic(dates,y,p):
    f=pd.DataFrame({"d":dates,"y":y,"p":p}); out=[]
    for _,g in f.groupby("d"):
        if len(g)<5 or g["p"].nunique()<2 or g["y"].nunique()<2: continue
        ic,_=stats.spearmanr(g["p"],g["y"])
        if ic==ic: out.append(float(ic))
    return out

def per_day_deciles(dates,y,p):
    f=pd.DataFrame({"d":dates,"y":y,"p":p}); tops=[];bots=[];dec={k:[] for k in range(10)}
    for _,g in f.groupby("d"):
        n=len(g)
        if n<20: continue
        o=np.argsort(g["p"].to_numpy()); yv=g["y"].to_numpy()[o]; e=np.linspace(0,n,11).astype(int)
        for k in range(10):
            seg=yv[e[k]:e[k+1]]
            if len(seg): dec[k].append(float(np.mean(seg)))
        kt=max(1,n//10); tops.append(float(np.mean(yv[-kt:]))); bots.append(float(np.mean(yv[:kt])))
    dm=[float(np.mean(dec[k])) if dec[k] else float("nan") for k in range(10)]
    return (float(np.mean(tops)) if tops else float("nan"),
            float(np.mean(bots)) if bots else float("nan"), dm)

def ic_summary(ics):
    a=np.array(ics,float); n=len(a)
    if n<2: return {"mean_ic":float("nan"),"ic_std":float("nan"),"ic_tstat":float("nan"),"n_days":n}
    m=float(a.mean()); s=float(a.std(ddof=1)); t=m/(s/math.sqrt(n)) if s>0 else float("nan")
    return {"mean_ic":m,"ic_std":s,"ic_tstat":t,"n_days":n}

def mono(dm):
    v=[x for x in dm if x==x]
    if len(v)<3: return float("nan")
    r,_=stats.spearmanr(range(len(v)),v); return float(r)

def run_fold(fold,v3,v4,coll):
    tr=add_mr(load_date_range(fold.train_start,fold.train_end,v3,REG_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    va=add_mr(load_date_range(fold.val_start,fold.val_end,v3,REG_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    trc=add_mr(load_date_range(fold.train_start,fold.train_end,v3,CLF_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    vac=add_mr(load_date_range(fold.val_start,fold.val_end,v3,CLF_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    if tr.empty or va.empty: log.warning("fold_skip",fold=fold.number); return
    tr,va=apply_purge_gap(tr,va,settings.WF_PURGE_DAYS); trc,vac=apply_purge_gap(trc,vac,settings.WF_PURGE_DAYS)
    tr=cross_sectional_normalize(tr,v4); va=cross_sectional_normalize(va,v4)
    trc=cross_sectional_normalize(trc,v4); vac=cross_sectional_normalize(vac,v4)
    for name,cols in [("v3",v3),("v4",v4)]:
        Xtr,ytr,_,_=to_arrays(tr,cols,REG_TARGET); Xva,yva,_,dva=to_arrays(va,cols,REG_TARGET)
        reg,_=train_regressor(Xtr,ytr,Xva,yva,cols); pred=reg.predict(Xva)
        ics=per_day_ic(dva.to_numpy(),yva,pred); top,bot,dm=per_day_deciles(dva.to_numpy(),yva,pred)
        Xtrc,ytrc,_,_=to_arrays(trc,cols,CLF_TARGET); Xvac,yvac,_,_=to_arrays(vac,cols,CLF_TARGET)
        clf,platt,_=train_classifier(Xtrc,ytrc,Xvac,yvac,cols); prob=predict_classifier(clf,platt,Xvac)
        c=coll[name]; c["ics"].extend(ics); c["tops"].append(top); c["bots"].append(bot)
        c["dec"].append(dm); c["auc"].append(roc_auc(yvac,prob)); c["brier"].append(brier_score(yvac,prob))
        c["reg_trees"].append(int(reg.num_trees()))
        log.info("fold_set_done",fold=fold.number,set=name,n_ic_days=len(ics))

def score_oos(name,ds,os_,oe,v3,v4):
    cols=v3 if name=="v3" else v4
    tr=add_mr(load_date_range(ds,os_,v3,REG_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    oo=add_mr(load_date_range(os_,oe,v3,REG_TARGET,settings.PARQUET_OUTPUT_DIR,settings.TRAIN_MIN_QUALITY_SCORE))
    tr,oo=apply_purge_gap(tr,oo,settings.WF_PURGE_DAYS)
    tr=cross_sectional_normalize(tr,v4); oo=cross_sectional_normalize(oo,v4)
    Xtr,ytr,_,_=to_arrays(tr,cols,REG_TARGET); Xoo,yoo,_,doo=to_arrays(oo,cols,REG_TARGET)
    reg,_=train_regressor(Xtr,ytr,Xoo,yoo,cols); pred=reg.predict(Xoo)
    ics=per_day_ic(doo.to_numpy(),yoo,pred); top,bot,dm=per_day_deciles(doo.to_numpy(),yoo,pred)
    o=ic_summary(ics); o.update({"decile_spread":top-bot,"decile_monotonicity":mono(dm),"feature_set":name,"n_rows":int(len(yoo))})
    print(f"  OOS {name}: mean_ic={o['mean_ic']:+.4f} t={o['ic_tstat']:+.2f} n_days={o['n_days']} spread={o['decile_spread']:+.4f}",flush=True)
    return o

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--oos-feature-set",choices=["v3","v4"],default="v4")
    ap.add_argument("--max-folds",type=int,default=None); a=ap.parse_args()
    files=sorted(glob.glob(str(settings.PARQUET_OUTPUT_DIR/"feature_matrix_*.parquet")))
    ds=date.fromisoformat(files[0].split("feature_matrix_")[1][:10]); de=date.fromisoformat(files[-1].split("feature_matrix_")[1][:10])
    os_,oe=oos_window(de,settings.WF_OOS_MONTHS)
    v3=list(settings.TRAIN_FEATURES_V3); v4=v3+["mr_score"]
    folds=generate_folds(ds,de,settings.WF_MIN_TRAIN_YEARS,settings.WF_VAL_MONTHS,settings.WF_OOS_MONTHS)
    if a.max_folds: folds=folds[:a.max_folds]
    print(f"V3 vs V4 (+mr_score) | data {ds}->{de} | OOS {os_}->{oe} | {len(folds)} folds",flush=True)
    coll={n:{"ics":[],"tops":[],"bots":[],"dec":[],"auc":[],"brier":[],"reg_trees":[]} for n in ("v3","v4")}
    for fold in folds:
        log.info("fold_start",fold=fold.number); run_fold(fold,v3,v4,coll)
    res={"data_start":str(ds),"data_end":str(de),"oos_start":str(os_),"oos_end":str(oe),"n_folds":len(folds),"sets":{}}
    for name in ("v3","v4"):
        c=coll[name]; s=ic_summary(c["ics"])
        dm=np.nanmean(np.array(c["dec"],float),axis=0).tolist() if c["dec"] else []
        s.update({"auc_mean":float(np.nanmean(c["auc"])),"brier_mean":float(np.nanmean(c["brier"])),
                  "decile_spread":float(np.nanmean(c["tops"])-np.nanmean(c["bots"])),"decile_monotonicity":mono(dm),
                  "reg_trees":c["reg_trees"]})
        res["sets"][name]=s
    if a.oos_feature_set:
        res["oos"]=score_oos(a.oos_feature_set,ds,os_,oe,v3,v4)
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(res,indent=2))
    print(f"\nWrote {OUT}",flush=True)
    for name in ("v3","v4"):
        s=res["sets"][name]
        print(f"  {name}: WF mean_ic={s['mean_ic']:+.4f} t={s['ic_tstat']:+.2f} AUC={s['auc_mean']:.4f} "
              f"spread={s['decile_spread']:+.4f} mono={s['decile_monotonicity']:+.2f}",flush=True)

if __name__=="__main__":
    main()
