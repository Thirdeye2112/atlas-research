"""
aapl_edge_analysis.py — which AAPL setups are REPEATABLE and PROFITABLE?

For every candlestick + chart-structure pattern (and for significant moves /
TA-confluence), enter at the confirm bar's close in the pattern's direction and
measure forward close-to-close returns at several horizons. Aggregate per setup:
  n (repeatability), win-rate, mean edge, t-stat, vs unconditional baseline drift.

Honest caveats (printed in the report):
  * In-sample over the whole history, NO transaction costs/slippage, NO
    walk-forward. These are historical tendencies / hypotheses, not guarantees.
  * Entry = close of the confirm bar; exit = close H bars later (no stops).

Usage:
    python scripts/aapl_edge_analysis.py --timeframe daily
    python scripts/aapl_edge_analysis.py --timeframe intraday
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import aapl_deep_dive as dd
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns
from atlas_research.ta import structure as ta_structure

DIRSIGN={"long":1,"bullish":1,"short":-1,"bearish":-1,"rise":1,"drop":-1,"neutral":0}

def fwd_returns(close: np.ndarray, horizons) -> dict:
    """close-to-close % return from each bar to bar+h."""
    return {h:(np.r_[close[h:],[np.nan]*h]/close-1.0)*100 for h in horizons}

def agg(records: pd.DataFrame, horizons, baseline: dict, min_n: int) -> pd.DataFrame:
    rows=[]
    for (name,d),g in records.groupby(["name","direction"]):
        sgn=DIRSIGN.get(d,0)
        if sgn==0 or len(g)<min_n: continue
        row={"setup":name,"dir":d,"n":len(g)}
        for h in horizons:
            r=(g[f"fwd{h}"]*sgn).dropna()          # directional return
            if len(r)<min_n:
                row[f"win{h}"]=np.nan; row[f"edge{h}"]=np.nan; row[f"t{h}"]=np.nan; continue
            base=baseline[h]*sgn                    # directional baseline drift
            row[f"win{h}"]=round((r>0).mean()*100,1)
            row[f"edge{h}"]=round(r.mean()-base,4)  # excess over buy&hold drift
            row[f"ret{h}"]=round(r.mean(),4)
            row[f"t{h}"]=round(r.mean()/(r.std()/np.sqrt(len(r))),2) if r.std()>0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--timeframe",choices=["daily","intraday"],default="daily")
    ap.add_argument("--ticker",default="AAPL")
    args=ap.parse_args()
    intraday=args.timeframe=="intraday"
    horizons=[1,3,6,12] if intraday else [1,3,5,10]
    hlabel=("bars" if intraday else "days")
    min_n=120 if intraday else 25

    print(f"=== {args.ticker} edge analysis ({args.timeframe}) ===",flush=True)
    if intraday:
        df=pd.read_parquet(ROOT/"data/intraday_5m/by_ticker"/f"{args.ticker}.parquet")
        df["ts"]=pd.to_datetime(df["ts"],utc=True).dt.tz_localize(None)
    else:
        df=dd.load_daily(args.ticker)
    df=df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): df[cc]=pd.to_numeric(df[cc],errors="coerce")
    df=dd.compute_indicators(df,intraday=intraday)
    o,h,l,c=(df[x].values for x in ("open","high","low","close"))
    N=len(df)
    print(f"  bars {N:,}  {df['ts'].min():%Y-%m-%d} -> {df['ts'].max():%Y-%m-%d}",flush=True)

    fwd=fwd_returns(c,horizons)
    baseline={hh:np.nanmean(fwd[hh]) for hh in horizons}   # unconditional drift

    # ---- patterns ----
    candles=detect_all_candles(o,h,l,c,skip_neutral=True)
    piv=ta_structure.swing_pivots(h,l,width=3)
    structs=ta_patterns.detect_all(piv,h,l,c)
    recs=[]
    for cd in candles:
        i=cd.confirm_idx
        if i>=N-max(horizons): continue
        recs.append({"name":cd.name,"direction":cd.direction,**{f"fwd{hh}":fwd[hh][i] for hh in horizons}})
    for ps in structs:
        i=ps.confirm_idx
        if i>=N-max(horizons): continue
        recs.append({"name":ps.name,"direction":ps.direction,**{f"fwd{hh}":fwd[hh][i] for hh in horizons}})
    rec=pd.DataFrame(recs)
    table=agg(rec,horizons,baseline,min_n)

    # rank by a repeatability*edge score on the mid horizon
    midh=horizons[2]
    table["score"]=table[f"win{midh}"].fillna(0)/100*np.sqrt(table["n"])*table[f"edge{midh}"].fillna(0).clip(lower=0)
    table=table.sort_values(f"t{midh}",ascending=False)

    base_str=", ".join(f"{hh}{hlabel}:{baseline[hh]:+.3f}%" for hh in horizons)
    print(f"\n  Unconditional drift (baseline): {base_str}",flush=True)
    cols=["setup","dir","n"]+[f"{p}{midh}" for p in ("win","ret","edge","t")]
    print("\n  TOP setups by t-stat at "+f"{midh}{hlabel} (n>={min_n}):",flush=True)
    print(table[cols].head(15).to_string(index=False),flush=True)
    print("\n  WORST (fade candidates):",flush=True)
    print(table[cols].tail(8).to_string(index=False),flush=True)

    # ---- significant-move continuation vs reversal ----
    cr=df["candle_ret"].values
    hi=np.nanpercentile(cr,99.5); lo=np.nanpercentile(cr,0.5)
    def move_stats(mask,label):
        idx=np.where(mask)[0]; idx=idx[idx<N-max(horizons)]
        out={"setup":label,"n":len(idx)}
        for hh in horizons:
            r=fwd[hh][idx]; r=r[~np.isnan(r)]
            out[f"mean{hh}"]=round(np.mean(r),4); out[f"win{hh}"]=round((r>0).mean()*100,1)
        return out
    mv=pd.DataFrame([move_stats(cr>=hi,"after BIG UP bar"),move_stats(cr<=lo,"after BIG DOWN bar")])
    print("\n  After significant 1-bar moves (raw fwd return, continuation>0 / reversal<0):",flush=True)
    print(mv.to_string(index=False),flush=True)

    # ---- confluence on significant moves: does more aligned TA -> bigger follow-through? ----
    conf_rows=[]
    for i in np.where((cr>=np.nanpercentile(cr,99))|(cr<=np.nanpercentile(cr,1)))[0]:
        if i>=N-max(horizons) or i<3: continue
        d="rise" if cr[i]>0 else "drop"; sgn=DIRSIGN[d]
        nconf=len(dd.explain_move(df.iloc[i],d,intraday))
        conf_rows.append({"conf":nconf,"dir_fwd":fwd[midh][i]*sgn})
    cf=pd.DataFrame(conf_rows).dropna()
    cf["bucket"]=pd.cut(cf["conf"],[-1,2,4,99],labels=["low(0-2)","mid(3-4)","high(5+)"])
    cfb=cf.groupby("bucket").agg(n=("dir_fwd","size"),mean_dir_fwd=("dir_fwd","mean"),
                                 win=("dir_fwd",lambda s:(s>0).mean()*100)).round(3)
    print(f"\n  Confluence vs directional follow-through at {midh}{hlabel} (continuation in move dir):",flush=True)
    print(cfb.to_string(),flush=True)

    # write report
    out=ROOT/"reports/stocks"/args.ticker/("deep_dive_5m" if intraday else "deep_dive_daily")
    out.mkdir(parents=True,exist_ok=True)
    table.to_csv(out/"edge_by_setup.csv",index=False)
    lines=[f"# {args.ticker} edge analysis ({args.timeframe})","",
           f"Bars {N:,} ({df['ts'].min():%Y-%m-%d}->{df['ts'].max():%Y-%m-%d}). "
           f"Entry=confirm-bar close, exit=+H {hlabel}. In-sample, no costs.","",
           f"Unconditional drift: {base_str}","",
           f"## Most repeatable + profitable setups (ranked by t-stat @ {midh}{hlabel})","",
           table[cols].head(15).to_markdown(index=False),"",
           "## After significant 1-bar moves","",mv.to_markdown(index=False),"",
           f"## Confluence vs follow-through @ {midh}{hlabel}","",cfb.to_markdown(),""]
    (out/"EDGE_ANALYSIS.md").write_text("\n".join(lines),encoding="utf-8")
    print(f"\n  wrote {out/'EDGE_ANALYSIS.md'} + edge_by_setup.csv",flush=True)

if __name__=="__main__":
    main()
