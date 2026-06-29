"""
bull_flag_study.py — the bull-flag pullback, entry, run-to-top, and the next leg.

For every CONFIRMED bull flag (pole low a -> pole high b -> flag low c -> breakout):
  * flag pullback depth (b->c) and retrace fraction of the pole  -> "the usual pullback"
  * entry comparisons: at the FLAG LOW c ("right above the bottom") vs at the BREAKOUT
  * run to the next swing high (the "top"), and the TA at that top (exit signal)
  * the next pullback depth + resume rate + leg-2 size (rebuy guidance)

Caveat: conditioned on flags that CONFIRMED (breakout happened) — real-time entry
at the flag low needs the oversold/5m confirmation to avoid falling knives.

Usage: python scripts/bull_flag_study.py --tickers AAPL NVDA ... --width 5 --cost-bps 5
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=5)
    ap.add_argument("--cost-bps",type=float,default=5)
    a=ap.parse_args(); cost=a.cost_bps/100.0
    rows=[]
    for tk in a.tickers:
        d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
        d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
        h=d["high"].values; l=d["low"].values; c=d["close"].values; rsi=d["rsi"].values; mr=d["mr"].values; N=len(d)
        piv=ta_structure.swing_pivots(h,l,width=a.width)
        H=[p for p in piv if p.kind=="H"]; Lo=[p for p in piv if p.kind=="L"]
        for pat in ta_patterns.flags(piv,h,l,c):
            if pat.name!="bull_flag": continue
            pts=pat.points
            (ai,ap_),(bi,bp),(ci,cp)=pts[0],pts[1],pts[2]
            conf=pat.confirm_idx
            if not (ai<bi<ci<conf<N): continue
            pole=(bp-ap_)/ap_*100; flag_depth=(bp-cp)/bp*100; retr=(bp-cp)/(bp-ap_) if bp>ap_ else np.nan
            flag_bars=ci-bi
            # run to next swing high after the breakout
            tops=[p for p in H if p.idx>conf]
            if not tops: continue
            top=tops[0]; run_to_top_brk=(top.price/c[conf]-1)*100-cost
            run_to_top_flag=(top.price/cp-1)*100-cost
            # next pullback after the top + resume
            lows_after=[p for p in Lo if p.idx>top.idx]
            nl=lows_after[0] if lows_after else None
            next_pb=( (top.price-nl.price)/top.price*100 ) if nl else np.nan
            highs_after=[p for p in H if nl and p.idx>nl.idx]
            resume=int(bool(highs_after and highs_after[0].price>top.price)) if nl else 0
            leg2=((highs_after[0].price/nl.price-1)*100) if (nl and highs_after) else np.nan
            # fixed-horizon fwd from breakout
            f10=(c[conf+10]/c[conf]-1)*100 if conf+10<N else np.nan
            rows.append(dict(ticker=tk,pole=pole,flag_depth=flag_depth,retrace=retr,flag_bars=flag_bars,
                run_to_top_brk=run_to_top_brk,run_to_top_flag=run_to_top_flag,
                rsi_at_top=rsi[top.idx],mr_at_top=mr[top.idx],
                next_pb=next_pb,resume=resume,leg2=leg2,fwd10=f10,
                entry_brk=c[conf],top_px=top.price,
                nl_px=(nl.price if nl else np.nan),
                leg2top_px=(highs_after[0].price if (nl and highs_after) else np.nan)))
    R=pd.DataFrame(rows)
    if R.empty: print("no confirmed bull flags found."); return
    q=R["flag_depth"].quantile([.25,.5,.75])
    print(f"=== Bull-flag study: {len(R)} confirmed flags, {R['ticker'].nunique()} names ===\n",flush=True)
    print("THE USUAL BULL-FLAG PULLBACK:",flush=True)
    print(f"  pole gain      : median {R['pole'].median():.1f}%",flush=True)
    print(f"  flag depth     : Q1 {q[.25]:.1f}%  MEDIAN {q[.5]:.1f}%  Q3 {q[.75]:.1f}%  (drop from pole high)",flush=True)
    print(f"  retrace of pole: median {R['retrace'].median():.2f}  | flag length: median {R['flag_bars'].median():.0f} bars",flush=True)
    print("\nENTRY (forward to the run top, net cost):",flush=True)
    print(f"  enter at FLAG LOW : mean {R['run_to_top_flag'].mean():.1f}%  median {R['run_to_top_flag'].median():.1f}%  win {(R['run_to_top_flag']>0).mean()*100:.0f}%",flush=True)
    print(f"  enter at BREAKOUT : mean {R['run_to_top_brk'].mean():.1f}%  median {R['run_to_top_brk'].median():.1f}%  win {(R['run_to_top_brk']>0).mean()*100:.0f}%",flush=True)
    print(f"\nAT THE RUN TOP (exit signal): RSI median {R['rsi_at_top'].median():.0f}, mr_score median {R['mr_at_top'].median():+.2f}",flush=True)
    print(f"NEXT PULLBACK after top: median {R['next_pb'].median():.1f}%  | run resumes higher {100*R['resume'].mean():.0f}%  | leg-2 median {R['leg2'].median():.1f}%",flush=True)

    # exit-at-first-top vs swing(sell top/rebuy dip) vs HOLD-through, entering at breakout
    S=R.dropna(subset=["entry_brk","top_px","nl_px","leg2top_px"]).copy()
    S=S[(S["entry_brk"]>0)&(S["nl_px"]>0)]
    e=S["entry_brk"].values; tp=S["top_px"].values; nl=S["nl_px"].values; l2=S["leg2top_px"].values
    exit_top=(tp/e-1)*100-cost
    hold_thru=(l2/e-1)*100-cost
    swing=((tp/e)*(l2/nl)-1)*100-2*cost
    comp=pd.DataFrame({"strategy":["EXIT at first top","HOLD through pullback (to leg-2 top)","SWING (sell top/rebuy dip)"],
                       "mean%":[exit_top.mean(),hold_thru.mean(),swing.mean()],
                       "median%":[np.median(exit_top),np.median(hold_thru),np.median(swing)],
                       "win%":[(exit_top>0).mean()*100,(hold_thru>0).mean()*100,(swing>0).mean()*100]}).round(2)
    print(f"\nSTRATEGY after a bull flag (n={len(S)} with a 2nd leg), enter at breakout:",flush=True)
    print(comp.to_string(index=False),flush=True)
    print(f"  HOLD-through beats EXIT-at-first-top in {(hold_thru>exit_top).mean()*100:.0f}% of cases; "
          f"SWING beats HOLD in {(swing>hold_thru).mean()*100:.0f}%",flush=True)

    out=ROOT/"reports/stocks"
    rep=[f"# Bull-flag pullback / entry / leg study ({len(R)} confirmed flags, {R['ticker'].nunique()} names)","",
         f"swing_pivots(width={a.width}); net of {a.cost_bps}bps. Conditioned on flags that confirmed.","",
         "## The usual bull-flag pullback","",
         f"- Pole gain: median **{R['pole'].median():.1f}%**",
         f"- **Flag depth (drop from pole high): Q1 {q[.25]:.1f}% / median {q[.5]:.1f}% / Q3 {q[.75]:.1f}%**",
         f"- Retrace of the pole: median **{R['retrace'].median():.2f}**; flag length median {R['flag_bars'].median():.0f} bars",
         f"- => place the entry just above ~the median flag low (≈ {q[.5]:.1f}% below the pole high).","",
         "## Entry: flag low vs breakout (forward to run top)","",
         pd.DataFrame({"entry":["at FLAG LOW (anticipate bottom)","at BREAKOUT (confirmed)"],
             "mean%":[round(R['run_to_top_flag'].mean(),1),round(R['run_to_top_brk'].mean(),1)],
             "median%":[round(R['run_to_top_flag'].median(),1),round(R['run_to_top_brk'].median(),1)],
             "win%":[round((R['run_to_top_flag']>0).mean()*100,0),round((R['run_to_top_brk']>0).mean()*100,0)]}).to_markdown(index=False),"",
         f"## Exit / re-entry","",
         f"- **Run top signature** (where to exit): RSI median **{R['rsi_at_top'].median():.0f}**, mr_score median **{R['mr_at_top'].median():+.2f}** (overbought/extended).",
         f"- **Next pullback** after the top: median **{R['next_pb'].median():.1f}%**, run resumes higher **{100*R['resume'].mean():.0f}%** of the time, leg-2 median **{R['leg2'].median():.1f}%** => rebuy the dip if shallow.","",
         f"## Exit at first top vs HOLD through vs swing (n={len(S)} flags with a 2nd leg)","",
         comp.to_markdown(index=False),"",
         f"HOLD-through beats exit-at-first-top in **{(hold_thru>exit_top).mean()*100:.0f}%** of cases; "
         f"SWING (perfect) beats HOLD in **{(swing>hold_thru).mean()*100:.0f}%** (but needs perfect timing).","",
         "_Entering at the flag low captures more but assumes you call the bottom; in real time gate it with oversold/5m-VWAP confirmation, or take the safer breakout entry._"]
    (out/"BULL_FLAG_STUDY.md").write_text("\n".join(rep),encoding="utf-8"); R.to_csv(out/"bull_flags.csv",index=False)
    print(f"\nwrote {out/'BULL_FLAG_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
