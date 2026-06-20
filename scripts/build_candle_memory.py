#!/usr/bin/env python
"""
build_candle_memory.py — STEP 1b: candlesticks + the 5-min pass into Pattern Memory.

The next pass promised by commit 8aacd83. Logs into the SAME `pattern_memory`
table as build_pattern_memory.py, with the SAME enrichment context, so the 19
named candlestick patterns are queryable alongside the chart patterns.

  daily pass : detect the 19 candlesticks on adjusted daily bars (timeframe='daily').
  5-min pass : detect chart patterns (patterns.detect_all) AND candlesticks on
               5-min bars (timeframe='5m'). Slow daily-scale context (SPY trend,
               RS, SMA stacking, 52-wk distance, weekly trend) is JOINED from the
               stock's DAILY series for that calendar date; fast fields (trend,
               S/R, gap, RSI/MACD/ADX/ATR%, vol, confirm-candle) are intraday.

This is a NEW driver; build_pattern_memory.py is intentionally NOT edited. The
enrichment math here mirrors that file (kept in sync by hand). Recognition +
logging only — no earnings/news (that is the next step).

Usage:
    python scripts/build_candle_memory.py --timeframe daily --limit 5      # validate
    python scripts/build_candle_memory.py --timeframe daily                # scale daily
    python scripts/build_candle_memory.py --timeframe 5m                   # 5-min pass
    python scripts/build_candle_memory.py --timeframe both --limit 5
"""
from __future__ import annotations
import argparse, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env", override=True)

import numpy as np, pandas as pd
from psycopg2.extras import execute_values, Json
from sqlalchemy import text
from atlas_research.db import connection
from atlas_research.ta import structure as S, patterns as P, candlesticks as K
from config import settings

HORIZON = 60
PULLBACK_THR = 0.03

# Same columns/table as build_pattern_memory.py — we append, never DROP.
COLS = ["ticker","timeframe","pattern_type","direction","confirm_date","start_date","end_date",
        "trend","trend_higher","market_trend","rs_spy20","rs_spy60","ret_before","dist_sma50",
        "dist_sma200","sma_stacked","dist_52w_high","dist_52w_low","dist_support","dist_resistance",
        "gap","month","dow","rsi","macd_hist","adx","atr_pct","vol_ratio","confirm_candle",
        "pattern_bars","pattern_height","entry","stop","target","rr","max_run","max_dd","fwd_ret",
        "bars_to_peak","n_pullbacks","reached_target","extra"]

# Slow daily-scale fields joined onto each 5-min instance by calendar date.
SLOW_FIELDS = ["trend_higher","market_trend","rs_spy20","rs_spy60","dist_sma50","dist_sma200",
               "sma_stacked","dist_52w_high","dist_52w_low"]


def _py(v):
    if v is None: return None
    if isinstance(v, np.generic): v = v.item()
    if isinstance(v, float) and math.isnan(v): return None
    return v

def ema(s,n): return s.ewm(span=n,adjust=False).mean()
def sma(s,n): return s.rolling(n).mean()
def rsi(c,n=14):
    d=c.diff(); up=d.clip(lower=0).ewm(alpha=1/n,adjust=False).mean()
    dn=(-d.clip(upper=0)).ewm(alpha=1/n,adjust=False).mean()
    return 100-100/(1+up/dn.replace(0,np.nan))
def adx(h,l,c,n=14):
    up=h.diff(); dn=-l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    a=tr.ewm(alpha=1/n,adjust=False).mean()
    pdi=100*pd.Series(pdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    mdi=100*pd.Series(mdm,index=h.index).ewm(alpha=1/n,adjust=False).mean()/a
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return dx.ewm(alpha=1/n,adjust=False).mean(), a


def after_story(direction, entry, target, high, low, close, ci):
    n=len(close); end=min(ci+1+HORIZON,n)
    if entry<=0 or end<=ci+1: return (None,)*6
    seg_h=high[ci+1:end]; seg_l=low[ci+1:end]; seg_c=close[ci+1:end]
    if direction=="short":
        run=float((entry-seg_l.min())/entry); dd=float((entry-seg_h.max())/entry)
        btp=int(np.argmin(seg_l))+1; fwd=float((entry-seg_c[-1])/entry)
        reached=bool(target is not None and seg_l.min()<=target)
        trough=entry; pulls=0
        for lo,hi in zip(seg_l,seg_h):
            if lo<trough: trough=lo
            if trough>0 and (hi-trough)/trough>=PULLBACK_THR: pulls+=1; trough=hi
    else:
        run=float((seg_h.max()-entry)/entry); dd=float((seg_l.min()-entry)/entry)
        btp=int(np.argmax(seg_h))+1; fwd=float((seg_c[-1]-entry)/entry)
        reached=bool(target is not None and seg_h.max()>=target)
        peak=entry; pulls=0
        for hi,lo in zip(seg_h,seg_l):
            if hi>peak: peak=hi
            if peak>0 and (peak-lo)/peak>=PULLBACK_THR: pulls+=1; peak=lo
    return run,dd,fwd,btp,pulls,reached


class Frame:
    """Per-ticker OHLC bundle + enrichment, for either daily or intraday bars."""
    def __init__(self, dates, o, h, l, cl, vol, width,
                 spy20=None, spy60=None, mkt=None, wk_tr=None):
        # utc=True normalizes both tz-naive daily dates and tz-aware 5-min ts.
        self.dates=pd.to_datetime(pd.Series(list(dates)), utc=True).reset_index(drop=True)
        self.o=o; self.h=h; self.l=l; self.cl=cl; self.vol=vol
        cls=pd.Series(cl)
        self.r=rsi(cls).to_numpy()
        mh=(ema(cls,12)-ema(cls,26)); self.mh=(mh-ema(mh,9)).to_numpy()
        ax,atr=adx(pd.Series(h),pd.Series(l),cls); self.ax=ax.to_numpy(); self.atr=atr.to_numpy()
        self.s50=sma(cls,50).to_numpy(); self.s150=sma(cls,150).to_numpy(); self.s200=sma(cls,200).to_numpy()
        self.vavg=sma(pd.Series(vol),20).to_numpy()
        self.hi52=cls.rolling(252).max().to_numpy(); self.lo52=cls.rolling(252).min().to_numpy()
        self.ret20=(cls/cls.shift(20)-1).to_numpy(); self.ret60=(cls/cls.shift(60)-1).to_numpy()
        self.spy20=spy20; self.spy60=spy60; self.mkt=mkt; self.wk_tr=wk_tr
        self.piv=S.swing_pivots(h,l,width=width)

    def ctx(self, ci, start_idx, height):
        o,h,l,cl=self.o,self.h,self.l,self.cl
        price=cl[ci]; recent=[q for q in self.piv if q.idx<=ci]
        lv=S.support_resistance(recent, price)
        sup=[x["level"] for x in lv if x["level"]<=price]; res=[x["level"] for x in lv if x["level"]>=price]
        def fin(a,i): return np.isfinite(a[i])
        return dict(
            trend=S.classify_trend(recent),
            trend_higher=(str(self.wk_tr[ci]) if self.wk_tr is not None else None),
            market_trend=(str(self.mkt[ci]) if self.mkt is not None else None),
            rs_spy20=(float(self.ret20[ci]-self.spy20[ci]) if self.spy20 is not None
                      and fin(self.ret20,ci) and np.isfinite(self.spy20[ci]) else None),
            rs_spy60=(float(self.ret60[ci]-self.spy60[ci]) if self.spy60 is not None
                      and fin(self.ret60,ci) and np.isfinite(self.spy60[ci]) else None),
            ret_before=float(price/cl[start_idx]-1) if cl[start_idx]>0 else None,
            dist_sma50=(float(price/self.s50[ci]-1) if fin(self.s50,ci) else None),
            dist_sma200=(float(price/self.s200[ci]-1) if fin(self.s200,ci) else None),
            sma_stacked=(bool(self.s50[ci]>self.s150[ci]>self.s200[ci])
                         if fin(self.s150,ci) and fin(self.s200,ci) else None),
            dist_52w_high=(float(price/self.hi52[ci]-1) if fin(self.hi52,ci) and self.hi52[ci]>0 else None),
            dist_52w_low=(float(price/self.lo52[ci]-1) if fin(self.lo52,ci) and self.lo52[ci]>0 else None),
            dist_support=((price-max(sup))/price if sup else None),
            dist_resistance=((min(res)-price)/price if res else None),
            gap=(float((o[ci]-cl[ci-1])/cl[ci-1]) if ci>0 and cl[ci-1]>0 else None),
            month=int(self.dates.iloc[ci].month), dow=int(self.dates.iloc[ci].dayofweek),
            rsi=(float(self.r[ci]) if fin(self.r,ci) else None),
            macd_hist=(float(self.mh[ci]) if fin(self.mh,ci) else None),
            adx=(float(self.ax[ci]) if fin(self.ax,ci) else None),
            atr_pct=(float(self.atr[ci]/price) if fin(self.atr,ci) and price>0 else None),
            vol_ratio=(float(self.vol[ci]/self.vavg[ci]) if fin(self.vavg,ci) and self.vavg[ci]>0 else None),
            confirm_candle=S.candle_label(o[ci],h[ci],l[ci],cl[ci]),
            pattern_bars=int(ci-start_idx), pattern_height=float(height),
        )


def _row(tk, tf, name, direction, cdate, sdate, edate, cx, entry, stop, target, rr, story, extra):
    run,dd,fwd,btp,pulls,reached = story
    return [tk,tf,name,direction,cdate,sdate,edate,
            cx["trend"],cx["trend_higher"],cx["market_trend"],cx["rs_spy20"],cx["rs_spy60"],
            cx["ret_before"],cx["dist_sma50"],cx["dist_sma200"],cx["sma_stacked"],
            cx["dist_52w_high"],cx["dist_52w_low"],cx["dist_support"],cx["dist_resistance"],
            cx["gap"],cx["month"],cx["dow"],cx["rsi"],cx["macd_hist"],cx["adx"],cx["atr_pct"],
            cx["vol_ratio"],cx["confirm_candle"],cx["pattern_bars"],cx["pattern_height"],
            entry,stop,target,rr,run,dd,fwd,btp,pulls,reached,Json(extra)]


def _flush(eng, rows):
    if not rows: return 0
    rawc=eng.raw_connection()
    try:
        cur=rawc.cursor()
        safe=[[_py(v) for v in row[:-1]]+[row[-1]] for row in rows]
        execute_values(cur, f"INSERT INTO pattern_memory ({','.join(COLS)}) VALUES %s", safe)
        rawc.commit()
    finally:
        rawc.close()
    return len(rows)


# ---------------------------------------------------------------- daily -------
def daily_frame(tk, conn, spy_ctx, width):
    df=pd.read_sql(text("SELECT date,open,high,low,close,adjusted_close,volume "
                        "FROM raw_bars WHERE ticker=:t ORDER BY date"),conn,params={"t":tk})
    if len(df)<260: return None
    fac=(df["adjusted_close"]/df["close"]).replace([np.inf,-np.inf],np.nan).fillna(1.0)
    o=(df["open"]*fac).to_numpy(); h=(df["high"]*fac).to_numpy(); l=(df["low"]*fac).to_numpy()
    cl=df["adjusted_close"].to_numpy(); vol=df["volume"].to_numpy(); dates=pd.to_datetime(df["date"])
    spy_r20,spy_r60,spy_trend=spy_ctx
    wk=pd.Series(cl,index=dates).resample("W-FRI").last()
    wk_tr=pd.Series(np.where(wk>wk.rolling(30).mean(),"up","down"),index=wk.index).reindex(dates,method="ffill").to_numpy()
    F=Frame(dates,o,h,l,cl,vol,width,
            spy20=spy_r20.reindex(dates,method="ffill").to_numpy(),
            spy60=spy_r60.reindex(dates,method="ffill").to_numpy(),
            mkt=spy_trend.reindex(dates,method="ffill").to_numpy(),
            wk_tr=wk_tr)
    return F


def candles_to_rows(tk, tf, F, candles, slow_override=None):
    rows=[]
    o,h,l,cl=F.o,F.h,F.l,F.cl; dates=F.dates
    for cd in candles:
        ci=cd.confirm_idx; si=cd.start_idx
        if ci<60 or not np.isfinite(F.s200[ci]) if slow_override is None else ci<60:
            continue
        height=(np.max(h[si:ci+1])-np.min(l[si:ci+1]))/cl[ci] if cl[ci]>0 else 0.0
        cx=F.ctx(ci,si,height)
        if slow_override is not None:
            so=slow_override(dates.iloc[ci])
            if so is None:   # no daily backdrop for this date -> skip
                continue
            cx.update(so)
        sdir="short" if cd.direction=="short" else "long"
        story=after_story(sdir,float(cd.entry),None,h,l,cl,ci)
        extra=dict(cd.extra); extra["shape_dir"]=cd.direction
        rows.append(_row(tk,tf,cd.name,cd.direction,dates.iloc[ci].date(),
                         dates.iloc[si].date(),dates.iloc[ci].date(),cx,
                         float(cd.entry),float(cd.stop),None,None,story,extra))
    return rows


def chartpat_to_rows(tk, tf, F, slow_override):
    rows=[]; h,l,cl=F.h,F.l,F.cl; dates=F.dates
    for p in P.detect_all(F.piv,h,l,cl):
        ci=p.confirm_idx
        if ci<60: continue
        si=min(pt[0] for pt in p.points)
        ph=[pt[1] for pt in p.points]; height=(max(ph)-min(ph))/cl[ci] if cl[ci]>0 else 0.0
        cx=F.ctx(ci,si,height)
        so=slow_override(dates.iloc[ci]) if slow_override else {}
        if so is None: continue
        cx.update(so or {})
        story=after_story(p.direction,cl[ci],p.target,h,l,cl,ci)
        rows.append(_row(tk,tf,p.name,p.direction,dates.iloc[ci].date(),
                         dates.iloc[si].date(),dates.iloc[ci].date(),cx,
                         float(p.entry),float(p.stop),float(p.target),float(p.rr),story,{}))
    return rows


# ---------------------------------------------------------------- 5-min -------
def intraday_frame(tk, conn, width):
    df=pd.read_sql(text("SELECT ts,open,high,low,close,volume FROM intraday_bars "
                        "WHERE ticker=:t AND timeframe='5m' ORDER BY ts"),conn,params={"t":tk})
    if len(df)<260: return None
    o=df["open"].to_numpy(float); h=df["high"].to_numpy(float); l=df["low"].to_numpy(float)
    cl=df["close"].to_numpy(float); vol=df["volume"].to_numpy(float)
    return Frame(df["ts"],o,h,l,cl,vol,width)


def slow_map_from_daily(F):
    """date -> {slow fields} from the daily frame, for joining onto 5-min rows."""
    dates=F.dates.dt.date.to_numpy()
    recs={}
    for i in range(len(dates)):
        if i<60 or not np.isfinite(F.s200[i]):
            continue
        cx=F.ctx(i,i,0.0)
        recs[dates[i]]={k:cx[k] for k in SLOW_FIELDS}
    keys=sorted(recs.keys())
    def lookup(ts):
        d=pd.Timestamp(ts).date()
        # exact, else most recent prior trading day
        import bisect
        j=bisect.bisect_right(keys,d)-1
        if j<0: return None
        return recs[keys[j]]
    return lookup if keys else (lambda ts: None)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--timeframe",choices=["daily","5m","both"],default="daily")
    ap.add_argument("--limit",type=int,default=None)
    ap.add_argument("--tickers",nargs="+",default=None)
    ap.add_argument("--width",type=int,default=5)
    args=ap.parse_args()

    clean=pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"].astype(str).str.upper().tolist()
    clean_set=set(clean)
    eng=connection.get_raw_engine()

    # SPY daily context (shared).
    with connection.get_connection() as c:
        spy=pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"),c)
    spy=spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_ctx=(spy/spy.shift(20)-1, spy/spy.shift(60)-1,
             pd.Series(np.where(spy>sma(spy,50),"up","down"),index=spy.index))

    counts={}  # (timeframe, pattern_type) -> n
    def tally(rows):
        for r in rows: counts[(r[1],r[2])]=counts.get((r[1],r[2]),0)+1

    # -------- daily candlesticks --------
    if args.timeframe in ("daily","both"):
        tickers=args.tickers or clean
        if args.limit: tickers=tickers[:args.limit]
        print(f"[daily] {len(tickers)} tickers -> candlesticks into pattern_memory")
        total=errors=proc=0
        with connection.get_connection() as conn:
            for tk in tickers:
                try:
                    F=daily_frame(tk,conn,spy_ctx,args.width)
                    if F is None: continue
                    candles=K.detect_all_candles(F.o,F.h,F.l,F.cl)
                    rows=candles_to_rows(tk,"daily",F,candles)
                    tally(rows); total+=_flush(eng,rows); proc+=1
                    if proc%200==0: print(f"  ...{proc}/{len(tickers)} logged={total:,} errs={errors}",flush=True)
                except Exception as e:
                    errors+=1
                    if errors<=5: print(f"  err {tk}: {repr(e)[:120]}",flush=True)
        print(f"[daily] DONE logged={total:,} errors={errors}")

    # -------- 5-min chart patterns + candlesticks --------
    if args.timeframe in ("5m","both"):
        with connection.get_connection() as conn:
            it=[r[0] for r in conn.execute(text(
                "SELECT DISTINCT ticker FROM intraday_bars WHERE timeframe='5m' ORDER BY ticker"))]
        it=[t for t in it if t.upper() in clean_set]   # clean-universe filter
        if args.tickers: it=[t for t in it if t in args.tickers]
        if args.limit: it=it[:args.limit]
        print(f"[5m] {len(it)} clean-universe tickers with 5m bars")
        total=errors=proc=0
        with connection.get_connection() as conn:
            for tk in it:
                try:
                    DF=daily_frame(tk,conn,spy_ctx,args.width)     # for the slow backdrop
                    slow=slow_map_from_daily(DF) if DF is not None else (lambda ts: {})
                    IF=intraday_frame(tk,conn,args.width)
                    if IF is None: continue
                    # 5m denoise: tighter tweezer tolerance + drop doji/spinning_top
                    # (they fire on most 5-min bars; low signal, huge volume).
                    rows =candles_to_rows(tk,"5m",IF,
                                          K.detect_all_candles(IF.o,IF.h,IF.l,IF.cl,
                                              eq_tol=0.0008, skip_neutral=True),
                                          slow_override=slow)
                    rows+=chartpat_to_rows(tk,"5m",IF,slow_override=slow)
                    tally(rows); total+=_flush(eng,rows); proc+=1
                    if proc%50==0: print(f"  ...{proc}/{len(it)} logged={total:,} errs={errors}",flush=True)
                except Exception as e:
                    errors+=1
                    if errors<=5: print(f"  err {tk}: {repr(e)[:120]}",flush=True)
        print(f"[5m] DONE logged={total:,} errors={errors}")

    # -------- report --------
    print("\n=== instance counts by (timeframe, pattern_type) ===")
    for (tf,pt) in sorted(counts, key=lambda k:(k[0],-counts[k])):
        print(f"  {tf:6} {pt:22} {counts[(tf,pt)]:,}")
    print(f"\nTOTAL logged this run: {sum(counts.values()):,}")


if __name__=="__main__":
    main()
