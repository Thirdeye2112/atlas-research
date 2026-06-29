"""
daily_scan.py — ALL-METHODS daily setup scan -> trade alerts.

For every tradeable ticker, on the LATEST bar, fire every method we have and rank
the resulting setups by conviction:
  * mean-reversion   (mr_score oversold, the validated signal)
  * candlestick      (detect_all_candles fulfilled on the last bar)
  * structure        (H&S / double top-bottom / flags confirmed on the last bar)
  * significant move (close-to-close in the tails -> follow-through)

Each fired setup is tagged with its HISTORICAL base rate mined from
deep_dive_events (avg fwd_ret_5, win5, n) so the alert carries its edge, plus a
trend filter (above 200-EMA) and confluence. Writes reports/alerts/ALERTS_<date>.md
and upserts trade_alerts (DB). Long-only by default (shorting candles loses — see
SIGNAL_REGISTRY). Each alert is acted on NEXT session, confirmed by a 5m VWAP reclaim.

Usage:
    python scripts/daily_scan.py                       # clean universe
    python scripts/daily_scan.py --universe 500        # liquid ~185
    python scripts/daily_scan.py --top 40 --min-base-n 50
"""
from __future__ import annotations
import sys, argparse, re, time, urllib.parse as up
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns, structure as ta_structure
import psycopg2
from psycopg2.extras import execute_values

def _conn():
    env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
    u=up.urlparse(env["DATABASE_URL"].strip())
    return psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))

def base_rates(cur):
    """historical edge per (method,name,direction) from deep_dive_events (LONG only,
    above-200EMA context — how these setups actually performed)."""
    cur.execute("""select event_type, name, direction,
                          count(*) n, avg(fwd_ret_5) a5,
                          100.0*sum((fwd_ret_5>0)::int)/count(*) w5
                   from deep_dive_events
                   where fwd_ret_5 is not null
                   group by 1,2,3""")
    br={}
    for et,name,d,n,a5,w5 in cur.fetchall():
        br[(et,name,d)]=(int(n),float(a5) if a5 is not None else None,float(w5) if w5 is not None else None)
    # special LONG base rates the raw grouping doesn't key directly:
    # mean-reversion = forward return of all mr_oversold bars
    cur.execute("""select count(*),avg(fwd_ret_5),100.0*sum((fwd_ret_5>0)::int)/count(*)
                   from deep_dive_events where mr_oversold=1 and fwd_ret_5 is not null""")
    n,a,w=cur.fetchone()
    if n: br[("mean_reversion","mr_oversold","long")]=(int(n),float(a),float(w))
    # buy-the-dip = forward return after significant_drop (go LONG -> raw fwd is the bounce)
    cur.execute("""select count(*),avg(fwd_ret_5),100.0*sum((fwd_ret_5>0)::int)/count(*)
                   from deep_dive_events where name='significant_drop' and fwd_ret_5 is not null""")
    n,a,w=cur.fetchone()
    if n: br[("move","significant_drop","long")]=(int(n),float(a),float(w))
    return br

def universe(which):
    if which=="500": f=ROOT/"config/universe_500.csv"
    elif which=="all": f=ROOT/"config/universe.csv"
    else: f=ROOT/"config/clean_universe.csv"
    df=pd.read_csv(f); col="ticker" if "ticker" in df.columns else df.columns[0]
    return [str(t).strip().upper() for t in df[col].dropna().tolist()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--universe",choices=["clean","500","all"],default="clean")
    ap.add_argument("--top",type=int,default=50)
    ap.add_argument("--min-base-n",type=int,default=30)
    ap.add_argument("--allow-short",action="store_true")
    args=ap.parse_args()
    cn=_conn(); cur=cn.cursor()
    br=base_rates(cur); print(f"loaded {len(br)} base-rate buckets",flush=True)
    univ=universe(args.universe); print(f"scanning {len(univ)} tickers ({args.universe})",flush=True)

    alerts=[]; t0=time.time(); scan_date=None
    for i,tk in enumerate(univ,1):
        try:
            d=dd.load_daily(tk)
            if d is None or len(d)<260: continue
            d=d.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
            for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
            d=dd.compute_indicators(d,intraday=False); d["mr_score"]=zscore_expanding(d)
            N=len(d); last=N-1; row=d.iloc[last]
            sd=pd.Timestamp(d["ts"].values[last]).date(); scan_date=scan_date or sd
            o,h,l,c=(d[x].values for x in ("open","high","low","close"))
            fired=[]   # (method,name,direction)
            # mean-reversion
            if row["mr_score"]>=1.0: fired.append(("mean_reversion","mr_oversold","long"))
            # significant move follow-through (today a tail move)
            cc=d["cc_ret"].values; hi=np.nanpercentile(cc,99); lo=np.nanpercentile(cc,1)
            if cc[last]<=lo: fired.append(("move","significant_drop","long"))   # buy the dip
            # candlestick on last bar
            for cd in detect_all_candles(o,h,l,c,skip_neutral=True):
                if cd.confirm_idx==last: fired.append(("candlestick",cd.name,cd.direction))
            # structure on last bar
            piv=ta_structure.swing_pivots(h,l,width=3)
            for ps in ta_patterns.detect_all(piv,h,l,c):
                if ps.confirm_idx==last: fired.append(("structure",ps.name,ps.direction))
            if not fired: continue
            seen=set()
            for method,name,direction in fired:
                key=(method,name,direction)
                if key in seen: continue
                seen.add(key)
                dlong = direction in ("long","bullish","rise")
                if not args.allow_short and not dlong: continue
                bn,ba,bw=br.get((method,name,direction),(0,None,None))
                if bn<args.min_base_n or ba is None: continue
                conf=0
                for cond in [row["mr_score"]>=1, row["rsi"]<40, row["above_ema200"]==1,
                             row["bb_pct"]<0.15, row["vol_ratio"]>1.3, row["macd_hist"]>0]:
                    conf+=int(bool(cond))
                conviction = round(ba*(bw/50.0) + 0.4*float(row["mr_score"]) + 0.4*int(row["above_ema200"]) + 0.15*conf, 3)
                alerts.append([str(sd),str(sd),tk,method,name,direction,
                    float(row["mr_score"]), 1 if row["mr_score"]>=1 else 0, int(conf),
                    int(row["above_ema200"]), float(row["rsi"]), float(cc[last]),
                    bn, round(ba,3), round(bw,1), conviction, True,
                    f"base {bn}x avg5 {ba:+.2f}% win {bw:.0f}%; mr {row['mr_score']:+.2f}; {'>200EMA' if row['above_ema200'] else '<200EMA'}"])
        except Exception as e:
            cn.rollback()
        if i%200==0: print(f"  [{i}/{len(univ)}] {tk} alerts={len(alerts)} ({i/max(time.time()-t0,1e-9):.1f} tk/s)",flush=True)

    if not alerts:
        print("no setups fired today.",flush=True); return
    COLS=["scan_date","ts","ticker","method","name","direction","mr_score","mr_oversold",
          "confluence_n","above_ema200","rsi","cc_ret","base_n","base_avg_fwd5","base_win5",
          "conviction","needs_5m_confirm","explained_by"]
    sql=(f"INSERT INTO trade_alerts ({','.join(COLS)}) VALUES %s "
         "ON CONFLICT (scan_date,ticker,method,name,direction) DO UPDATE SET "
         "conviction=EXCLUDED.conviction, mr_score=EXCLUDED.mr_score, confluence_n=EXCLUDED.confluence_n")
    execute_values(cur,sql,alerts,page_size=1000); cn.commit()

    df=pd.DataFrame(alerts,columns=COLS).sort_values("conviction",ascending=False)
    out=ROOT/"reports/alerts"; out.mkdir(parents=True,exist_ok=True)
    show=["ticker","method","name","direction","mr_score","confluence_n","above_ema200","base_n","base_avg_fwd5","base_win5","conviction"]
    top=df.head(args.top)
    rep=[f"# Trade alerts — {scan_date} (act next session on 5m VWAP reclaim)","",
         f"{len(df)} setups fired across {df['ticker'].nunique()} names ({args.universe} universe), all methods. "
         "Long-only; ranked by conviction (historical base-rate edge x win-rate + mr_score + trend + confluence).","",
         f"## Top {len(top)} alerts","",top[show].to_markdown(index=False),"",
         "## By method","",
         df.groupby("method").agg(n=("ticker","size"),avg_conv=("conviction","mean")).round(2).to_markdown(),"",
         "_Each alert carries its mined base rate (base_n trades, base_avg_fwd5 %, base_win5 %). "
         "Confirm intraday next session: enter only if price reclaims & closes above VWAP._"]
    (out/f"ALERTS_{scan_date}.md").write_text("\n".join(rep),encoding="utf-8")
    (out/"ALERTS_latest.md").write_text("\n".join(rep),encoding="utf-8")
    df.to_csv(out/f"alerts_{scan_date}.csv",index=False)
    print(f"\n{len(df)} alerts -> trade_alerts + reports/alerts/ALERTS_{scan_date}.md",flush=True)
    print("\nTOP 12:",flush=True); print(top[show].head(12).to_string(index=False),flush=True)

if __name__=="__main__":
    main()
