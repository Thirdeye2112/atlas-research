"""
mine_universe.py — populate deep_dive_events across the daily universe so the
deep-dive examination is MINABLE from the DB (atlas-research + atlas-alpha).

Per ticker (>=250 daily bars): compute the full TA stack + look-ahead-free
mr_score, detect every significant move (close-to-close tails), candlestick, and
chart-structure fulfillment, and upsert one row per event with the decision-bar
TA snapshot, mr_score, confluence, and forward outcomes.

Checkpointed + resumable (reports/stocks/.mine_checkpoint.json). Idempotent upsert.

Usage:
    python scripts/mine_universe.py                 # full universe, resume
    python scripts/mine_universe.py --tickers AAPL NVDA   # subset
    python scripts/mine_universe.py --restart       # ignore checkpoint
    python scripts/mine_universe.py --limit 50      # first N (smoke)
"""
from __future__ import annotations
import sys, argparse, json, re, time, urllib.parse as up
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns, structure as ta_structure
import psycopg2
from psycopg2.extras import execute_values

CKPT=ROOT/"reports/stocks/.mine_checkpoint.json"
SNAP=["rsi","rsi_slope","macd_hist","stoch_k","williams_r","bb_pct","bb_width","atr_pct",
      "vol_ratio","vol_z","mfi","dist_ema20","dist_ema50","dist_ema200","above_ema200",
      "ema_stack_bull","ema_stack_bear","dist_hi_20","dist_lo_20","roc_10","consec_dir"]
COLS=(["ticker","ts","timeframe","event_type","name","direction","cc_ret","gap_pct",
       "mr_score","mr_oversold"]+SNAP+["fwd_ret_1","fwd_ret_3","fwd_ret_5","fwd_ret_10",
       "confluence_n","explained_by"])

def _conn():
    env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
    u=up.urlparse(env["DATABASE_URL"].strip())
    return psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))

def confluence(row, rise: bool):
    """lightweight aligned-signal count + text from a snapshot dict."""
    g=lambda k: row.get(k,np.nan); R=[]
    if rise:
        if g("rsi")<35: R.append("RSI oversold")
        if g("bb_pct")<0.1: R.append("below lower BB")
        if g("macd_hist")>0: R.append("MACD hist+")
        if g("vol_ratio")>1.5: R.append("high volume")
        if g("above_ema200"): R.append("above 200EMA")
        if g("dist_ema20")< -5: R.append("extended below EMA20")
        if g("stoch_k")<20: R.append("stoch oversold")
        if g("mr_score")>=1: R.append("mr_score oversold")
    else:
        if g("rsi")>65: R.append("RSI overbought")
        if g("bb_pct")>0.9: R.append("above upper BB")
        if g("macd_hist")<0: R.append("MACD hist-")
        if g("vol_ratio")>1.5: R.append("high volume")
        if not g("above_ema200"): R.append("below 200EMA")
        if g("dist_ema20")>5: R.append("extended above EMA20")
        if g("stoch_k")>80: R.append("stoch overbought")
    return len(R),"; ".join(R)

def mine_ticker(tk, cur):
    df=dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    if len(df)<250: return 0
    for cc in ("open","high","low","close","volume"): df[cc]=pd.to_numeric(df[cc],errors="coerce")
    df=dd.compute_indicators(df,intraday=False)
    df["mr_score"]=zscore_expanding(df)
    N=len(df); c=df["close"].values
    fwd={k:(np.r_[c[k:],[np.nan]*k]/c-1)*100 for k in (1,3,5,10)}
    arr={col:df[col].values for col in SNAP if col in df.columns}
    ccr=df["cc_ret"].values; gap=df["gap_pct"].values; mrs=df["mr_score"].values
    ts=df["ts"].dt.date.values
    o,h,l=(df[x].values for x in ("open","high","low"))

    events=[]   # (loc, event_type, name, direction)
    hi=np.nanpercentile(ccr,99.5); lo=np.nanpercentile(ccr,0.5)
    for loc in np.where((ccr>=hi)|(ccr<=lo))[0]:
        events.append((int(loc),"move","significant_rise" if ccr[loc]>0 else "significant_drop",
                       "rise" if ccr[loc]>0 else "drop"))
    for cd in detect_all_candles(o,h,l,c,skip_neutral=True):
        events.append((cd.confirm_idx,"candlestick",cd.name,cd.direction))
    piv=ta_structure.swing_pivots(h,l,width=3)
    for ps in ta_patterns.detect_all(piv,h,l,c):
        events.append((ps.confirm_idx,"structure",ps.name,ps.direction))

    rows=[]
    for loc,etype,name,direction in events:
        if loc<200 or loc>=N or np.isnan(mrs[loc]): continue
        rise=direction in ("rise","long","bullish")
        snap={col:(float(arr[col][loc]) if not np.isnan(arr[col][loc]) else None) for col in arr}
        snap["mr_score"]=float(mrs[loc]); snap["above_ema200"]=int(arr["above_ema200"][loc]) if "above_ema200" in arr else None
        nconf,txt=confluence({**snap},rise)
        row=[tk, ts[loc], "1d", etype, name, direction,
             float(ccr[loc]) if not np.isnan(ccr[loc]) else None,
             float(gap[loc]) if not np.isnan(gap[loc]) else None,
             float(mrs[loc]), 1 if mrs[loc]>=1 else 0]
        for col in SNAP:
            v=arr[col][loc] if col in arr else np.nan
            row.append(None if (v is None or (isinstance(v,float) and np.isnan(v))) else float(v))
        for k in (1,3,5,10):
            v=fwd[k][loc]; row.append(None if np.isnan(v) else float(v))
        row += [nconf, (txt if etype=="move" else None)]
        rows.append(row)
    if not rows: return 0
    # dedupe on the unique key (structure detectors can confirm same pattern at same bar)
    uniq={tuple(r[0:6]): r for r in rows}; rows=list(uniq.values())
    # cast int-ish snapshot cols stored as float -> keep float; above/stack are 0/1 floats ok
    sql=f"INSERT INTO deep_dive_events ({','.join(COLS)}) VALUES %s ON CONFLICT (ticker,ts,timeframe,event_type,name,direction) DO UPDATE SET mr_score=EXCLUDED.mr_score, fwd_ret_5=EXCLUDED.fwd_ret_5, confluence_n=EXCLUDED.confluence_n"
    execute_values(cur,sql,rows,page_size=2000)
    return len(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="*")
    ap.add_argument("--restart",action="store_true")
    ap.add_argument("--limit",type=int,default=0)
    args=ap.parse_args()
    cn=_conn(); cur=cn.cursor()
    if args.tickers:
        universe=args.tickers
    else:
        cur.execute("select ticker from raw_bars group by ticker having count(*)>=250 order by ticker")
        universe=[r[0] for r in cur.fetchall()]
    if args.limit: universe=universe[:args.limit]
    done=set() if (args.restart or args.tickers) else set(json.loads(CKPT.read_text())) if CKPT.exists() else set()
    todo=[t for t in universe if t not in done]
    print(f"universe={len(universe)} done={len(done)} todo={len(todo)}",flush=True)
    t0=time.time(); total=0
    for i,tk in enumerate(todo,1):
        try:
            n=mine_ticker(tk,cur); cn.commit(); total+=n; done.add(tk)
        except Exception as e:
            cn.rollback(); print(f"  !! {tk}: {str(e)[:80]}",flush=True); done.add(tk)
        if i%50==0 or i==len(todo):
            CKPT.write_text(json.dumps(sorted(done)))
            rate=i/max(time.time()-t0,1e-9)
            print(f"  [{i}/{len(todo)}] {tk} rows+={total:,} ({rate:.1f} tk/s)",flush=True)
    CKPT.write_text(json.dumps(sorted(done)))
    cur.execute("select count(*),count(distinct ticker) from deep_dive_events"); print("deep_dive_events:",cur.fetchone(),flush=True)
    cn.close(); print("DONE",flush=True)

if __name__=="__main__":
    main()
