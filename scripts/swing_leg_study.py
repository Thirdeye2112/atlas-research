"""
swing_leg_study.py — pullback / multi-leg swing analysis.

Question: in an up-run that has a pullback (low -> leg1 peak -> pullback low ->
leg2 peak), is it better to SELL the first-leg top and REBUY the pullback bottom
to ride leg 2, vs just HOLDING through? And how deep/short are pullbacks, how
often does the run resume to a higher high?

Detects up-legs with ta.patterns.swing_legs (consecutive legs chain: a leg's
pullback low is the next leg's start). For every leg that has a pullback AND a
following leg, we measure:
  HOLD          : buy leg-start low, hold to leg-2 peak (rides through the dip)
  SWING-perfect : sell leg-1 peak, rebuy pullback low, sell leg-2 peak (hindsight)
  SIGNAL-timed  : within the run, exit on overbought/extended (RSI>70 or mr_score
                  very negative), rebuy on oversold (mr_score>=1) — what's ACHIEVABLE
All net of round-trip cost; the extra legs in SWING/SIGNAL pay extra cost.

Also: pullback depth / duration distribution, and resume-rate + leg-2 size by
pullback-depth bucket (shallow vs deep dips).

Usage: python scripts/swing_leg_study.py --tickers AAPL NVDA ... --width 5 --min-amp 0.05 --cost-bps 5
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns

def signal_timed(close, rsi, mr, a, bp, cost):
    """within [a, bp] enter long at a, sell on overbought/extended, rebuy on
    oversold, close at bp. Return net % (compounded long segments)."""
    eq=1.0; in_pos=True; entry=close[a]
    for i in range(a+1, bp+1):
        if in_pos and (rsi[i]>70 or mr[i]<=-1.0):           # sell strength
            eq*=(close[i]/entry)*(1-cost/100); in_pos=False
        elif (not in_pos) and mr[i]>=1.0:                    # buy weakness
            entry=close[i]; in_pos=True
    if in_pos: eq*=(close[bp]/entry)*(1-cost/100)
    return (eq-1)*100

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    ap.add_argument("--width",type=int,default=5)
    ap.add_argument("--min-amp",type=float,default=0.05)
    ap.add_argument("--cost-bps",type=float,default=5)
    args=ap.parse_args(); cost=args.cost_bps/100.0
    legs=[]; rows=[]
    for tk in args.tickers:
        d=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
        for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
        d=dd.compute_indicators(d,intraday=False); d["mr"]=zscore_expanding(d)
        h=d["high"].values; l=d["low"].values; c=d["close"].values; rsi=d["rsi"].values; mr=d["mr"].values
        piv=ta_structure.swing_pivots(h,l,width=args.width)
        L=ta_patterns.swing_legs(piv,h,l,c,min_amp=args.min_amp)
        # chain consecutive legs: leg k's corr low == leg k+1's start
        by_start={lg["start_idx"]:lg for lg in L}
        for lg in L:
            ci=lg["corr_idx"]
            if ci is None or ci not in by_start: continue
            nxt=by_start[ci]
            a=lg["start_idx"]; b=lg["peak_idx"]; cc_=ci; bp=nxt["peak_idx"]
            if not (a<b<cc_<bp): continue
            pa=c[a]; pb=c[b]; pc=c[cc_]; pbp=c[bp]
            if pa<=0 or pc<=0: continue
            leg1=(pb-pa)/pa; pull=(pb-pc)/pb; leg2=(pbp-pc)/pc
            hold=(pbp-pa)/pa*100 - cost                      # 1 round trip
            swing=((1+leg1)*(1+leg2)-1)*100 - 2*cost          # 2 round trips
            sig=signal_timed(c,rsi,mr,a,bp,cost)
            resume_higher = pbp>pb
            legs.append(dict(ticker=tk,leg1=leg1*100,pull=pull*100,leg2=leg2*100,
                             corr_bars=lg["corr_bars"],resume=int(resume_higher),
                             hold=hold,swing=swing,sig=sig,
                             rsi_at_peak=rsi[b],mr_at_peak=mr[b],mr_at_corr=mr[cc_]))
    L=pd.DataFrame(legs)
    if L.empty: print("no chained legs found."); return
    print(f"=== Swing-leg study: {len(L)} run->pullback->run sequences, {L['ticker'].nunique()} names ===\n",flush=True)

    print("PULLBACK STATS (median / mean):",flush=True)
    for col,lab in [("leg1","leg-1 gain %"),("pull","pullback depth %"),("corr_bars","pullback bars"),("leg2","leg-2 gain %")]:
        print(f"  {lab:18s} median {L[col].median():6.2f}  mean {L[col].mean():6.2f}",flush=True)
    print(f"  run resumes to higher high: {100*L['resume'].mean():.0f}% of the time",flush=True)
    print(f"  typical setup at leg-1 peak: RSI {L['rsi_at_peak'].median():.0f}, mr_score {L['mr_at_peak'].median():+.2f} "
          f"(overbought/extended) ; at pullback low: mr_score {L['mr_at_corr'].median():+.2f} (oversold)",flush=True)

    print("\nSTRATEGY (mean % per sequence, net of cost):",flush=True)
    comp=pd.DataFrame({"strategy":["HOLD through","SWING perfect (sell top/rebuy dip)","SIGNAL-timed swing"],
                       "mean%":[L["hold"].mean(),L["swing"].mean(),L["sig"].mean()],
                       "median%":[L["hold"].median(),L["swing"].median(),L["sig"].median()],
                       "win%":[(L["hold"]>0).mean()*100,(L["swing"]>0).mean()*100,(L["sig"]>0).mean()*100]}).round(2)
    print(comp.to_string(index=False),flush=True)
    beat=(L["sig"]>L["hold"]).mean()*100
    print(f"\n  SIGNAL-timed beat HOLD in {beat:.0f}% of sequences; "
          f"avg edge {L['sig'].mean()-L['hold'].mean():+.2f}% per sequence",flush=True)

    print("\nRESUME RATE & LEG-2 by PULLBACK DEPTH:",flush=True)
    L["pb_bucket"]=pd.cut(L["pull"],[0,5,10,20,200],labels=["0-5%","5-10%","10-20%",">20%"])
    g=L.groupby("pb_bucket").agg(n=("leg2","size"),resume_rate=("resume",lambda s:round(s.mean()*100,0)),
                                 avg_leg2=("leg2","mean")).round(2)
    print(g.to_string(),flush=True)

    out=ROOT/"reports/stocks"
    rep=[f"# Swing-leg / pullback study ({L['ticker'].nunique()} names, {len(L)} run→pullback→run sequences)","",
         f"Up-legs via swing_pivots(width={args.width}), min leg {args.min_amp:.0%}. Net of {args.cost_bps}bps/round-trip.","",
         "## Pullback statistics","",
         f"- Leg-1 gain: median {L['leg1'].median():.1f}% | Pullback depth: median {L['pull'].median():.1f}% "
         f"({L['corr_bars'].median():.0f} bars) | Leg-2 gain: median {L['leg2'].median():.1f}%",
         f"- Run resumes to a higher high **{100*L['resume'].mean():.0f}%** of the time",
         f"- At leg-1 peak: RSI ~{L['rsi_at_peak'].median():.0f}, mr_score {L['mr_at_peak'].median():+.2f} (overbought); "
         f"at pullback low: mr_score {L['mr_at_corr'].median():+.2f} (oversold)","",
         "## Sell-the-top / rebuy-the-dip vs hold","",comp.to_markdown(index=False),"",
         f"SIGNAL-timed beat HOLD in **{beat:.0f}%** of sequences (avg {L['sig'].mean()-L['hold'].mean():+.2f}%/seq).","",
         "## Resume rate & leg-2 by pullback depth","",g.to_markdown(),"",
         "_SWING-perfect is hindsight (upper bound). SIGNAL-timed exits on overbought/extended "
         "(RSI>70 or mr_score<=-1) and rebuys on oversold (mr_score>=1) — what the validated signals achieve._"]
    (out/"SWING_LEG_STUDY.md").write_text("\n".join(rep),encoding="utf-8")
    L.to_csv(out/"swing_legs.csv",index=False)
    print(f"\nwrote {out/'SWING_LEG_STUDY.md'}",flush=True)

if __name__=="__main__":
    main()
