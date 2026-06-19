#!/usr/bin/env python
"""
build_pattern_memory.py — STEP 1: the Pattern Memory (knowledge base), enriched.

For every clean-universe stock (daily), log every detected pattern's full STORY
into the queryable `pattern_memory` table. Now with the full price-action context:

  BEFORE : trend (this TF) + higher-TF (weekly) trend, market trend (SPY),
           relative strength vs SPY (20/60d), move into it, distance to 50/200 SMA,
           SMA stacking (50>150>200), distance to 52-wk high/low, distance to
           nearest support/resistance, the gap on the confirmation bar, and the
           calendar month / day-of-week (seasonality).
  THROUGH: RSI, MACD-hist, ADX, ATR%, volume-vs-average, the confirmation candle
           type, the pattern's duration (bars) and height (%).
  AFTER  : max run, max drawdown, forward return, bars-to-peak, # pullbacks,
           reached-target.
  extra  : pattern-specific JSON (e.g. swing-leg early-signature + leg/correction).

Patterns logged: chart patterns (double bottom/top, bull/bear flag, H&S +inverse)
AND swing_leg/"dome" (rise from support -> peak -> correction, with the first-N-bar
early signature). Candlesticks (19) + 5-min are the next pass into the SAME table.

NOTE: an earnings/news flag is NOT logged — we have no fundamentals/earnings-date
source in the DB. Flagged as a known gap (would need an external feed).

Usage: python scripts/build_pattern_memory.py [--limit N] [--reset]
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")

import numpy as np, pandas as pd
from psycopg2.extras import execute_values, Json
from sqlalchemy import text
from atlas_research.db import connection
from atlas_research.ta import structure as S, patterns as P
from config import settings

HORIZON = 60
PULLBACK_THR = 0.03

DDL = """
CREATE TABLE IF NOT EXISTS pattern_memory (
  id bigserial PRIMARY KEY,
  ticker text, timeframe text, pattern_type text, direction text,
  confirm_date date, start_date date, end_date date,
  trend text, trend_higher text, market_trend text,
  rs_spy20 double precision, rs_spy60 double precision,
  ret_before double precision, dist_sma50 double precision, dist_sma200 double precision,
  sma_stacked boolean, dist_52w_high double precision, dist_52w_low double precision,
  dist_support double precision, dist_resistance double precision, gap double precision,
  month int, dow int,
  rsi double precision, macd_hist double precision, adx double precision,
  atr_pct double precision, vol_ratio double precision, confirm_candle text,
  pattern_bars int, pattern_height double precision,
  entry double precision, stop double precision, target double precision, rr double precision,
  max_run double precision, max_dd double precision, fwd_ret double precision,
  bars_to_peak int, n_pullbacks int, reached_target boolean,
  extra jsonb, created_at timestamptz default now()
);
CREATE INDEX IF NOT EXISTS idx_pm_tk ON pattern_memory(ticker, timeframe, pattern_type);
CREATE INDEX IF NOT EXISTS idx_pm_pat ON pattern_memory(pattern_type, direction);
"""
COLS = ["ticker","timeframe","pattern_type","direction","confirm_date","start_date","end_date",
        "trend","trend_higher","market_trend","rs_spy20","rs_spy60","ret_before","dist_sma50",
        "dist_sma200","sma_stacked","dist_52w_high","dist_52w_low","dist_support","dist_resistance",
        "gap","month","dow","rsi","macd_hist","adx","atr_pct","vol_ratio","confirm_candle",
        "pattern_bars","pattern_height","entry","stop","target","rr","max_run","max_dd","fwd_ret",
        "bars_to_peak","n_pullbacks","reached_target","extra"]


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
    if direction=="long":
        run=float((seg_h.max()-entry)/entry); dd=float((seg_l.min()-entry)/entry)
        btp=int(np.argmax(seg_h))+1; fwd=float((seg_c[-1]-entry)/entry)
        reached=bool(target is not None and seg_h.max()>=target)
        peak=entry; pulls=0
        for hi,lo in zip(seg_h,seg_l):
            if hi>peak: peak=hi
            if peak>0 and (peak-lo)/peak>=PULLBACK_THR: pulls+=1; peak=lo
    else:
        run=float((entry-seg_l.min())/entry); dd=float((entry-seg_h.max())/entry)
        btp=int(np.argmin(seg_l))+1; fwd=float((entry-seg_c[-1])/entry)
        reached=bool(target is not None and seg_l.min()<=target)
        trough=entry; pulls=0
        for lo,hi in zip(seg_l,seg_h):
            if lo<trough: trough=lo
            if trough>0 and (hi-trough)/trough>=PULLBACK_THR: pulls+=1; trough=hi
    return run,dd,fwd,btp,pulls,reached


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=None)
    ap.add_argument("--width",type=int,default=5); ap.add_argument("--reset",action="store_true")
    args=ap.parse_args()

    clean=pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"].tolist()
    if args.limit: clean=clean[:args.limit]
    with connection.get_connection() as c:
        if args.reset: c.execute(text("DROP TABLE IF EXISTS pattern_memory"))
        for stmt in DDL.strip().split(";"):
            if stmt.strip(): c.execute(text(stmt))
        spy=pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"),c)
    spy=spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_r20=spy/spy.shift(20)-1; spy_r60=spy/spy.shift(60)-1
    spy_trend=np.where(spy>sma(spy,50),"up","down")
    spy_trend=pd.Series(spy_trend,index=spy.index)
    print(f"pattern_memory build (enriched) | {len(clean):,} clean tickers | daily")

    total=0; errors=0; proc=0
    eng=connection.get_raw_engine()
    with connection.get_connection() as conn:
        for tk in clean:
          try:
            df=pd.read_sql(text("SELECT date,open,high,low,close,adjusted_close,volume "
                                "FROM raw_bars WHERE ticker=:t ORDER BY date"),conn,params={"t":tk})
            if len(df)<260: continue
            fac=(df["adjusted_close"]/df["close"]).replace([np.inf,-np.inf],np.nan).fillna(1.0)
            o=(df["open"]*fac).to_numpy(); h=(df["high"]*fac).to_numpy(); l=(df["low"]*fac).to_numpy()
            cl=df["adjusted_close"].to_numpy(); vol=df["volume"].to_numpy(); dates=pd.to_datetime(df["date"])
            cls=pd.Series(cl)
            r=rsi(cls).to_numpy(); mh=(ema(cls,12)-ema(cls,26)); mh=(mh-ema(mh,9)).to_numpy()
            ax,atr=adx(pd.Series(h),pd.Series(l),cls); ax=ax.to_numpy(); atr=atr.to_numpy()
            s50=sma(cls,50).to_numpy(); s150=sma(cls,150).to_numpy(); s200=sma(cls,200).to_numpy()
            vavg=sma(pd.Series(vol),20).to_numpy()
            hi52=cls.rolling(252).max().to_numpy(); lo52=cls.rolling(252).min().to_numpy()
            ret20=(cls/cls.shift(20)-1).to_numpy(); ret60=(cls/cls.shift(60)-1).to_numpy()
            wk=pd.Series(cl,index=dates).resample("W-FRI").last()
            wk_tr=pd.Series(np.where(wk>wk.rolling(30).mean(),"up","down"),index=wk.index).reindex(dates,method="ffill").to_numpy()
            spy20=spy_r20.reindex(dates,method="ffill").to_numpy()
            spy60=spy_r60.reindex(dates,method="ffill").to_numpy()
            mkt=spy_trend.reindex(dates,method="ffill").to_numpy()
            piv=S.swing_pivots(h,l,width=args.width)

            def ctx(ci, start_idx, height):
                price=cl[ci]; recent=[q for q in piv if q.idx<=ci]
                lv=S.support_resistance(recent, price)
                sup=[x["level"] for x in lv if x["level"]<=price]; res=[x["level"] for x in lv if x["level"]>=price]
                return dict(
                    trend=S.classify_trend(recent), trend_higher=str(wk_tr[ci]), market_trend=str(mkt[ci]),
                    rs_spy20=(float(ret20[ci]-spy20[ci]) if np.isfinite(ret20[ci]) and np.isfinite(spy20[ci]) else None),
                    rs_spy60=(float(ret60[ci]-spy60[ci]) if np.isfinite(ret60[ci]) and np.isfinite(spy60[ci]) else None),
                    ret_before=float(price/cl[start_idx]-1) if cl[start_idx]>0 else None,
                    dist_sma50=(float(price/s50[ci]-1) if np.isfinite(s50[ci]) else None),
                    dist_sma200=(float(price/s200[ci]-1) if np.isfinite(s200[ci]) else None),
                    sma_stacked=(bool(s50[ci]>s150[ci]>s200[ci]) if np.isfinite(s150[ci]) and np.isfinite(s200[ci]) else None),
                    dist_52w_high=(float(price/hi52[ci]-1) if np.isfinite(hi52[ci]) and hi52[ci]>0 else None),
                    dist_52w_low=(float(price/lo52[ci]-1) if np.isfinite(lo52[ci]) and lo52[ci]>0 else None),
                    dist_support=((price-max(sup))/price if sup else None),
                    dist_resistance=((min(res)-price)/price if res else None),
                    gap=(float((o[ci]-cl[ci-1])/cl[ci-1]) if ci>0 and cl[ci-1]>0 else None),
                    month=int(dates.iloc[ci].month), dow=int(dates.iloc[ci].dayofweek),
                    rsi=(float(r[ci]) if np.isfinite(r[ci]) else None),
                    macd_hist=(float(mh[ci]) if np.isfinite(mh[ci]) else None),
                    adx=(float(ax[ci]) if np.isfinite(ax[ci]) else None),
                    atr_pct=(float(atr[ci]/price) if np.isfinite(atr[ci]) and price>0 else None),
                    vol_ratio=(float(vol[ci]/vavg[ci]) if np.isfinite(vavg[ci]) and vavg[ci]>0 else None),
                    confirm_candle=S.candle_label(o[ci],h[ci],l[ci],cl[ci]),
                    pattern_bars=int(ci-start_idx), pattern_height=float(height),
                )

            rows=[]
            # --- chart patterns ---
            for p in P.detect_all(piv,h,l,cl):
                ci=p.confirm_idx
                if ci<60 or not np.isfinite(s200[ci]): continue
                start_idx=min(pt[0] for pt in p.points)
                ph=[pt[1] for pt in p.points]; height=(max(ph)-min(ph))/cl[ci] if cl[ci]>0 else 0.0
                cx=ctx(ci,start_idx,height)
                run,dd,fwd,btp,pulls,reached=after_story(p.direction,cl[ci],p.target,h,l,cl,ci)
                rows.append([tk,"daily",p.name,p.direction,dates.iloc[ci].date(),
                    dates.iloc[start_idx].date(),dates.iloc[ci].date(),
                    cx["trend"],cx["trend_higher"],cx["market_trend"],cx["rs_spy20"],cx["rs_spy60"],
                    cx["ret_before"],cx["dist_sma50"],cx["dist_sma200"],cx["sma_stacked"],
                    cx["dist_52w_high"],cx["dist_52w_low"],cx["dist_support"],cx["dist_resistance"],
                    cx["gap"],cx["month"],cx["dow"],cx["rsi"],cx["macd_hist"],cx["adx"],cx["atr_pct"],
                    cx["vol_ratio"],cx["confirm_candle"],cx["pattern_bars"],cx["pattern_height"],
                    float(p.entry),float(p.stop),float(p.target),float(p.rr),
                    run,dd,fwd,btp,pulls,reached, Json({})])
            # --- swing legs (the dome) ---
            for sl in P.swing_legs(piv,h,l,cl):
                ci=sl["peak_idx"]
                if ci<60 or not np.isfinite(s200[ci]): continue
                cx=ctx(ci, sl["start_idx"], sl["leg_amp"])
                extra={k:sl[k] for k in ("leg_amp","leg_bars","corr_depth","corr_bars","early_gain","early_slope","early_n")}
                end_date=dates.iloc[sl["corr_idx"]].date() if sl["corr_idx"] else dates.iloc[ci].date()
                rows.append([tk,"daily","swing_leg","long",dates.iloc[ci].date(),
                    dates.iloc[sl["start_idx"]].date(),end_date,
                    cx["trend"],cx["trend_higher"],cx["market_trend"],cx["rs_spy20"],cx["rs_spy60"],
                    sl["early_gain"],cx["dist_sma50"],cx["dist_sma200"],cx["sma_stacked"],
                    cx["dist_52w_high"],cx["dist_52w_low"],cx["dist_support"],cx["dist_resistance"],
                    cx["gap"],cx["month"],cx["dow"],cx["rsi"],cx["macd_hist"],cx["adx"],cx["atr_pct"],
                    cx["vol_ratio"],cx["confirm_candle"],sl["leg_bars"],sl["leg_amp"],
                    None,None,None,None,
                    sl["leg_amp"], (-sl["corr_depth"] if sl["corr_depth"] is not None else None),
                    (-sl["corr_depth"] if sl["corr_depth"] is not None else None),
                    sl["leg_bars"], None, None, Json(extra)])
            if rows:
                rawc=eng.raw_connection()
                try:
                    cur=rawc.cursor()
                    safe=[[_py(v) for v in row[:-1]]+[row[-1]] for row in rows]  # keep Json() as-is
                    execute_values(cur, f"INSERT INTO pattern_memory ({','.join(COLS)}) VALUES %s", safe)
                    rawc.commit()
                finally:
                    rawc.close()
                total+=len(rows)
            proc+=1
            if proc%300==0: print(f"  ...{proc}/{len(clean)}  logged={total:,} errs={errors}",flush=True)
          except Exception as e:
            errors+=1
            if errors<=5: print(f"  err {tk}: {repr(e)[:110]}",flush=True)
    print(f"\nDONE: logged {total:,} instances (errors {errors}). Table: pattern_memory")


if __name__=="__main__":
    main()
