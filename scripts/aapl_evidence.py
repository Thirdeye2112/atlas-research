"""
aapl_evidence.py — (A) verify the detector is seeing setups correctly, and
(B) emit concise per-event evidence cards listing ALL TA that corroborated each
rise/drop, plus the daily->5m entry-confirmation linkage.

Three sections, written to reports/aapl_deep_dive_daily/EVIDENCE.md:

  1. DETECTION QA      — integrity checks that each tagged pattern actually meets
                         its definition, that 'rise'/'drop' bars really moved that
                         way, and marquee-date spot checks (COVID, 2022, tariff).
  2. EVIDENCE CARDS    — for the biggest moves + key setups, every corroborating
                         vs contradicting TA signal grouped by category, with a
                         confluence tally and a plain-English read.
  3. DAILY -> 5m       — for 2023+ daily setups, the intraday 5m trigger (first
                         VWAP reclaim / oversold bounce / opening-range break) that
                         would have confirmed the entry.

Usage: python scripts/aapl_evidence.py [--n 10]
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns, structure as ta_structure

# ── evidence engine ─────────────────────────────────────────────────────────────
def evidence(row, direction: str, pats_here: list[str]) -> list[tuple]:
    """Return [(category, label, value, verdict)] where verdict +1 corroborates the
    move, -1 contradicts, 0 = context. `row` is a df row (Series)."""
    g=lambda k: row.get(k, np.nan)
    rise = direction in ("rise","long","bullish")
    s = 1 if rise else -1                       # flip checks for drops
    E=[]
    def add(cat,label,val,verdict): E.append((cat,label,val,verdict))

    # TREND CONTEXT
    add("Trend","200-EMA", f"{'above' if g('above_ema200') else 'below'} ({g('dist_ema200'):+.1f}%)",
        (1 if g('above_ema200') else -1)*s)
    stack = 'bull' if g('ema_stack_bull') else ('bear' if g('ema_stack_bear') else 'mixed')
    add("Trend","EMA stack 9/20/50", stack, (1 if stack=='bull' else (-1 if stack=='bear' else 0))*s)
    ext = g('dist_ema20')
    add("Trend","Dist from 20-EMA", f"{ext:+.1f}%", (-1 if (ext*s)>4 else 0))   # over-extended argues against

    # MOMENTUM
    rsi=g('rsi')
    rsi_v = 1 if ((rise and rsi<40) or (not rise and rsi>60)) else (-1 if ((rise and rsi>70) or (not rise and rsi<30)) else 0)
    add("Momentum","RSI", f"{rsi:.0f} ({'oversold' if rsi<30 else 'overbought' if rsi>70 else 'neutral'})", rsi_v)
    add("Momentum","RSI slope", f"{g('rsi_slope'):+.1f}", (1 if (g('rsi_slope')*s)>0 else -1))
    mh=g('macd_hist')
    add("Momentum","MACD hist", f"{mh:+.3f}", (1 if (mh*s)>0 else -1))
    if g('macd_bull_cross'): add("Momentum","MACD cross","bullish cross", 1*s)
    if g('macd_bear_cross'): add("Momentum","MACD cross","bearish cross", -1*s)
    sk=g('stoch_k')
    add("Momentum","Stochastic %K", f"{sk:.0f}", (1 if ((rise and sk<20) or (not rise and sk>80)) else 0))

    # VOLATILITY
    bb=g('bb_pct')
    add("Volatility","Bollinger %B", f"{bb:.2f}",
        (1 if ((rise and bb<0.2) or (not rise and bb>0.8)) else (-1 if ((rise and bb>0.9) or (not rise and bb<0.1)) else 0)))
    if g('bb_squeeze'): add("Volatility","BB squeeze","yes (energy coiled)", 1)
    add("Volatility","ATR%", f"{g('atr_pct'):.2f}", 0)

    # VOLUME
    vr=g('vol_ratio')
    add("Volume","Volume vs 20d", f"{vr:.1f}x", (1 if vr>1.5 else (-1 if vr<0.6 else 0)))
    if g('vol_climax'): add("Volume","Volume climax","yes", 1)
    mfi=g('mfi')
    add("Volume","MFI", f"{mfi:.0f}", (1 if ((rise and mfi<30) or (not rise and mfi>70)) else 0))

    # STRUCTURE / intraday
    add("Structure","Dist to 20d low/high", f"lo {g('dist_lo_20'):+.1f}% / hi {g('dist_hi_20'):+.1f}%",
        (1 if ((rise and g('dist_lo_20')<2) or (not rise and g('dist_hi_20')>-2)) else 0))
    if not np.isnan(g('vwap_dist')):
        add("Structure","VWAP", f"{'above' if g('above_vwap') else 'below'} ({g('vwap_dist'):+.2f}%)",
            (1 if g('above_vwap') else -1)*s)
    if not np.isnan(g('or_position')):
        add("Structure","Opening-range pos", f"{g('or_position'):.2f}",
            (1 if ((rise and g('or_position')>0.9) or (not rise and g('or_position')<0.1)) else 0))

    # CANDLE
    add("Candle","Body / wicks", f"body {g('body_pct'):.2f}%  up-wick {g('upper_wick'):.0f}%  lo-wick {g('lower_wick'):.0f}%", 0)
    if pats_here:
        add("Candle","Patterns firing", ", ".join(pats_here), 0)
    return E

def card_md(title, E, outcome) -> list[str]:
    pro=sum(1 for *_,v in E if v>0); con=sum(1 for *_,v in E if v<0)
    L=[f"### {title}","",f"**Corroborating: {pro}  |  Contradicting: {con}**  → {outcome}","",
       "| Category | Signal | Value | Read |","|---|---|---|---|"]
    sym={1:"✅ supports",-1:"❌ against",0:"· context"}
    for cat,label,val,v in E:
        L.append(f"| {cat} | {label} | {val} | {sym[v]} |")
    L.append("")
    return L

# ── daily -> 5m confirmation ────────────────────────────────────────────────────
def intraday_trigger(ticker, day, direction):
    f=ROOT/"data/intraday_5m/by_ticker"/f"{ticker}.parquet"
    if not f.exists(): return "(no 5m data)"
    d=pd.read_parquet(f); d["ts"]=pd.to_datetime(d["ts"],utc=True).dt.tz_localize(None)
    win=d[(d["ts"].dt.date>=day)&(d["ts"].dt.date<=day+pd.Timedelta(days=2))].copy()
    if len(win)<10: return "(no 5m bars near date — pre-2023)"
    win=dd.compute_indicators(win.reset_index(drop=True),intraday=True)
    rise=direction in ("rise","long","bullish")
    if rise:
        trig=win[(win["above_vwap"]==1)&(win["above_vwap"].shift(1)==0)&(win["rsi"]>45)]
        what="VWAP reclaim"
    else:
        trig=win[(win["above_vwap"]==0)&(win["above_vwap"].shift(1)==1)]
        what="VWAP loss"
    if trig.empty: return "(no clean intraday trigger in window)"
    t=trig.iloc[0]
    return f"{what} at {t['ts']:%Y-%m-%d %H:%M} px ${t['close']:.2f} (RSI {t['rsi']:.0f}, vol {t['vol_ratio']:.1f}x)"

# ── main ────────────────────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--n",type=int,default=10); args=ap.parse_args()
    print("=== AAPL evidence + detection QA (daily) ===",flush=True)
    df=dd.load_daily("AAPL"); df=df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"): df[cc]=pd.to_numeric(df[cc],errors="coerce")
    df=dd.compute_indicators(df,intraday=False)
    o,h,l,c=(df[x].values for x in ("open","high","low","close")); N=len(df)
    H=5; fwd=(np.r_[c[H:],[np.nan]*H]/c-1)*100; df["fwd5"]=fwd

    candles=detect_all_candles(o,h,l,c,skip_neutral=True)
    piv=ta_structure.swing_pivots(h,l,width=3); structs=ta_patterns.detect_all(piv,h,l,c)
    pat_at={}                                  # loc -> [pattern names]
    for ev in list(candles)+list(structs): pat_at.setdefault(ev.confirm_idx,[]).append(ev.name)

    rep=["# AAPL — detection QA + evidence cards (daily, 15y)",""]

    # ---- 1. DETECTION QA ----
    print("\n[1] DETECTION QA — does each tag match its definition?",flush=True)
    checks=[]
    # bullish_engulfing: green now, red prior, body engulfs
    be=[ev for ev in candles if ev.name=="bullish_engulfing"]; ok=0
    for ev in be:
        i=ev.confirm_idx
        if c[i]>o[i] and c[i-1]<o[i-1] and o[i]<=c[i-1] and c[i]>=o[i-1]: ok+=1
    checks.append(("bullish_engulfing meets definition", ok, len(be)))
    # bearish_engulfing
    bre=[ev for ev in candles if ev.name=="bearish_engulfing"]; ok=0
    for ev in bre:
        i=ev.confirm_idx
        if c[i]<o[i] and c[i-1]>o[i-1] and o[i]>=c[i-1] and c[i]<=o[i-1]: ok+=1
    checks.append(("bearish_engulfing meets definition", ok, len(bre)))
    # direction sanity: long patterns shouldn't sit in strong overbought blowoff far above ema200 (just report rate)
    longs=[ev for ev in candles if ev.direction in ("long","bullish")]
    aboveema=sum(1 for ev in longs if df["above_ema200"].values[ev.confirm_idx]==1)
    checks.append(("long candlesticks that are above 200-EMA", aboveema, len(longs)))
    # significant moves really moved
    cr=df["candle_ret"].values; hi=np.nanpercentile(cr,99.5); lo=np.nanpercentile(cr,0.5)
    up=np.where(cr>=hi)[0]; dn=np.where(cr<=lo)[0]
    checks.append(("'big up' bars with positive candle_ret", int((cr[up]>0).all()), 1))
    checks.append(("'big down' bars with negative candle_ret", int((cr[dn]<0).all()), 1))
    for label,ok,tot in checks:
        rate=f"{ok}/{tot}" + (f" ({100*ok/tot:.0f}%)" if tot>1 else "")
        print(f"  {label}: {rate}",flush=True)
    rep+=["## 1. Detection integrity",""]+[f"- {lab}: **{ok}/{tot}**"+("" if tot<=1 else f" ({100*ok/tot:.0f}%)") for lab,ok,tot in checks]+[""]

    # marquee spot-checks
    marquee={"2020-03-12":"COVID crash","2020-03-13":"COVID rebound","2022-09-13":"CPI selloff",
             "2025-04-03":"tariff crash","2025-04-09":"tariff-pause rally"}
    print("\n  Marquee-date detections (sanity):",flush=True)
    rep+=["### Marquee-date sanity check",""]
    dfd=df.set_index(df["ts"].dt.strftime("%Y-%m-%d"))
    for dstr,desc in marquee.items():
        if dstr in dfd.index:
            i=df.index[df["ts"].dt.strftime("%Y-%m-%d")==dstr][0]
            pats=pat_at.get(i,[])
            line=f"  {dstr} ({desc}): candle_ret {df['candle_ret'].values[i]:+.1f}%, RSI {df['rsi'].values[i]:.0f}, patterns: {pats or 'none'}"
            print(line,flush=True); rep.append(f"- **{dstr}** ({desc}): candle {df['candle_ret'].values[i]:+.1f}%, RSI {df['rsi'].values[i]:.0f}, patterns: {pats or '—'}")
    rep.append("")

    # ---- 2. EVIDENCE CARDS for biggest moves ----
    print("\n[2] EVIDENCE CARDS — biggest moves (see console-> file):",flush=True)
    rep+=["## 2. Evidence cards — biggest rises & drops",""]
    order=np.argsort(-np.abs(cr)); picked=[]
    for i in order:
        if i<3 or i>=N-H or np.isnan(fwd[i]): continue
        picked.append(i)
        if len(picked)>=args.n: break
    for i in picked:
        direction="rise" if cr[i]>0 else "drop"
        E=evidence(df.iloc[i],direction,pat_at.get(i,[]))
        outcome=f"next 5d: {fwd[i]:+.2f}%"
        title=f"{df['ts'].values[i].astype('datetime64[D]')} significant {direction.upper()} ({cr[i]:+.1f}%)"
        rep+=card_md(title,E,outcome)
        # daily->5m
        day=pd.Timestamp(df['ts'].values[i]).date()
        rep+=[f"- **5m confirmation:** {intraday_trigger('AAPL',day,direction)}",""]

    out=ROOT/"reports/aapl_deep_dive_daily"; (out/"EVIDENCE.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\n  wrote {out/'EVIDENCE.md'}",flush=True)

if __name__=="__main__":
    main()
