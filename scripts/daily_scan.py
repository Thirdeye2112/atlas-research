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
import sys, argparse, re, time, json, urllib.parse as up
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts")); sys.path.insert(0,str(ROOT/"src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns, structure as ta_structure
import psycopg2
from psycopg2.extras import execute_values

# Per-liquidity-tier forecast targets from the whole-universe forecast study (Step 1).
_TGT_PATH=ROOT/"reports/stocks/universe_forecast_targets.json"
TARGETS=json.loads(_TGT_PATH.read_text()) if _TGT_PATH.exists() else None
# Per-tier 5m-arc drop context (throw->top->bounce) from the whole-universe arc study.
_ARC_PATH=ROOT/"reports/stocks/universe_arc_targets.json"
ARC_TARGETS=json.loads(_ARC_PATH.read_text()) if _ARC_PATH.exists() else None

# DATA-DRIVEN pattern direction + projected target/low/duration (pattern_outcomes_study).
# Per pattern: the historically PROFITABLE side (may flip the textbook direction),
# avg favorable move %, avg adverse %, and median bars to fulfillment.
_PEDGE_PATH=ROOT/"reports/stocks/pattern_edge.json"
PATTERN_EDGE=json.loads(_PEDGE_PATH.read_text()) if _PEDGE_PATH.exists() else {}
def _pattern_dir(name, textbook):
    """Data-driven direction for a chart/candle pattern; falls back to textbook."""
    e=PATTERN_EDGE.get(name)
    return e["direction"] if e else textbook

# Liquidity floor + conviction normalisation. The universe-wide base rates are huge
# for microcaps (T4 avg5 ~14-46% = penny-stock noise), so raw conviction over-ranks
# illiquid junk. We (a) drop tiers below --min-tier by default (T4 out) and (b) CAP
# the base-rate term so a fat microcap base rate can't dominate the ranking.
_TIER_RANK={"T1":1,"T2":2,"T3":3,"T4":4}
CONV_BASE_CAP=3.0   # % — base_avg_fwd5 contribution to conviction is capped here
def _tier_ok(tier, floor):
    if floor is None or tier is None: return True
    return _TIER_RANK.get(tier,99) <= _TIER_RANK.get(floor,99)

def _conn():
    env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
    u=up.urlparse(env["DATABASE_URL"].strip())
    return psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))

def _tier_sql_case():
    """SQL CASE that maps a per-ticker median $-volume to T1..T4 using the EXACT
    upper edges the Step-1 study quantiled into universe_forecast_targets.json,
    so live tiering matches the tiers the base rates/targets were computed on."""
    e=TARGETS["tier_dollar_vol_max"]
    return (f"case when dv <= {e['T4']} then 'T4' when dv <= {e['T3']} then 'T3' "
            f"when dv <= {e['T2']} then 'T2' else 'T1' end")

def build_tiers_and_base_rates(cur):
    """Build a temp _tiered(ticker,tier) table (median $-vol over the last ~1y, same
    as Step 1), return (tier_map, br_pooled, br_tier). Base rates are mined from
    deep_dive_events both pooled and PER TIER so a live alert can use the base rate
    of names in its own liquidity bucket, not the microcap-polluted pooled one."""
    if TARGETS is not None:
        cur.execute(f"""create temp table _tiered as
            with recent as (
              select ticker, close*volume dv,
                     row_number() over (partition by ticker order by date desc) rn
              from raw_bars),
            liq as (select ticker, percentile_cont(0.5) within group (order by dv) dv
                    from recent where rn<=252 group by ticker)
            select ticker, {_tier_sql_case()} as tier from liq""")
        cur.execute("create index on _tiered(ticker)")
        cur.execute("select ticker,tier from _tiered")
        tier_map={tk:t for tk,t in cur.fetchall()}
    else:
        tier_map={}

    def _rec(n,a,w):
        return (int(n),float(a) if a is not None else None,float(w) if w is not None else None)

    def _grouped(extra_where, base_key=None):
        """return (pooled,tier) {key:(n,a5,w5)}. Pooled is ALWAYS computed (no tier
        join) for fallback; tier is added when the targets/tiers are available."""
        pooled={}; tier={}
        if base_key is None:                       # group by (event_type,name,direction)
            cur.execute(f"""select event_type,name,direction,
                              count(*),avg(fwd_ret_5),100.0*sum((fwd_ret_5>0)::int)/count(*)
                            from deep_dive_events where fwd_ret_5 is not null {extra_where}
                            group by 1,2,3""")
            for et,name,d,n,a,w in cur.fetchall(): pooled[(et,name,d)]=_rec(n,a,w)
            if TARGETS is not None:
                cur.execute(f"""select event_type,name,direction,t.tier,
                                  count(*),avg(fwd_ret_5),100.0*sum((fwd_ret_5>0)::int)/count(*)
                                from deep_dive_events e join _tiered t using(ticker)
                                where fwd_ret_5 is not null {extra_where} group by 1,2,3,4""")
                for et,name,d,tr,n,a,w in cur.fetchall():
                    if tr is not None: tier[(et,name,d,tr)]=_rec(n,a,w)
        else:                                      # one special LONG bucket
            cur.execute(f"""select count(*),avg(fwd_ret_5),100.0*sum((fwd_ret_5>0)::int)/count(*)
                            from deep_dive_events where fwd_ret_5 is not null {extra_where}""")
            n,a,w=cur.fetchone()
            if n: pooled[base_key]=_rec(n,a,w)
            if TARGETS is not None:
                cur.execute(f"""select t.tier,count(*),avg(fwd_ret_5),
                                  100.0*sum((fwd_ret_5>0)::int)/count(*)
                                from deep_dive_events e join _tiered t using(ticker)
                                where fwd_ret_5 is not null {extra_where} group by 1""")
                for tr,n,a,w in cur.fetchall():
                    if tr is not None and n: tier[base_key+(tr,)]=_rec(n,a,w)
        return pooled,tier

    br_pooled={}; br_tier={}
    for ew,key in [("", None),
                   ("and mr_oversold=1", ("mean_reversion","mr_oversold","long")),
                   ("and name='significant_drop'", ("move","significant_drop","long")),
                   # SHORT-side base rates (same mined fwd_ret_5; a short has edge when fwd_ret_5<0)
                   ("and mr_score<=-1", ("mean_reversion","mr_overbought","short")),
                   ("and name='significant_rise'", ("move","significant_rise","short"))]:
        p,t=_grouped(ew,key); br_pooled.update(p); br_tier.update(t)
    return tier_map, br_pooled, br_tier

def _retrace_for(pct):
    """Expected first-pullback retrace of the run, by run size (SWING_PULLBACK_STUDY:
    small ~0.87, med ~0.78, big ~0.62, huge ~0.49; overall median ~0.70)."""
    if pct is None: return 0.70
    if pct < 8: return 0.87
    if pct < 15: return 0.78
    if pct < 30: return 0.62
    return 0.49

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
    ap.add_argument("--min-tier",default="T3",help="liquidity floor: keep tiers >= this (T1>T2>T3>T4). Use T4 to keep all.")
    ap.add_argument("--side",choices=["both","long","short"],default="both",
                    help="which opportunities to surface (default both — short edge is learned from its mined base rate)")
    args=ap.parse_args()
    cn=_conn(); cur=cn.cursor()
    tier_map,br,br_tier=build_tiers_and_base_rates(cur)
    print(f"loaded {len(br)} pooled + {len(br_tier)} tiered base-rate buckets; "
          f"{len(tier_map)} tickers tiered"+("" if TARGETS else " (NO targets json — run universe_forecast_study.py)"),flush=True)
    univ=universe(args.universe); print(f"scanning {len(univ)} tickers ({args.universe})",flush=True)

    alerts=[]; t0=time.time(); scan_date=None
    skipped_liq=0
    for i,tk in enumerate(univ,1):
        try:
            # liquidity floor: drop sub-threshold tiers before the expensive load
            if not _tier_ok(tier_map.get(tk), args.min_tier):
                skipped_liq+=1; continue
            d=dd.load_daily(tk)
            if d is None or len(d)<260: continue
            d=d.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
            for cc in ("open","high","low","close","volume"): d[cc]=pd.to_numeric(d[cc],errors="coerce")
            d=dd.compute_indicators(d,intraday=False); d["mr_score"]=zscore_expanding(d)
            N=len(d); last=N-1; row=d.iloc[last]
            sd=pd.Timestamp(d["ts"].values[last]).date(); scan_date=scan_date or sd
            o,h,l,c=(d[x].values for x in ("open","high","low","close"))
            fired=[]   # (method,name,direction)
            # mean-reversion (both sides): mr_score + = oversold (long), - = overbought (short)
            if row["mr_score"]>=1.0: fired.append(("mean_reversion","mr_oversold","long"))
            if row["mr_score"]<=-1.0: fired.append(("mean_reversion","mr_overbought","short"))
            # significant move follow-through (today a tail move)
            cc=d["cc_ret"].values; hi=np.nanpercentile(cc,99); lo=np.nanpercentile(cc,1)
            if cc[last]<=lo: fired.append(("move","significant_drop","long"))   # buy the dip
            if cc[last]>=hi: fired.append(("move","significant_rise","short"))  # fade the spike
            # candlestick on last bar (direction is DATA-DRIVEN from pattern_edge)
            for cd in detect_all_candles(o,h,l,c,skip_neutral=True):
                if cd.confirm_idx==last: fired.append(("candlestick",cd.name,_pattern_dir(cd.name,cd.direction)))
            # structure on last bar (direction is DATA-DRIVEN — may flip the textbook side)
            piv=ta_structure.swing_pivots(h,l,width=3)
            for ps in ta_patterns.detect_all(piv,h,l,c):
                if ps.confirm_idx==last: fired.append(("structure",ps.name,_pattern_dir(ps.name,ps.direction)))
            if not fired: continue
            d_trend=ta_structure.classify_trend(piv)
            # forecast magnitudes for this ticker's liquidity tier (Step 1 study)
            tier=tier_map.get(tk)
            tinfo=(TARGETS["tiers"].get(tier) if (TARGETS and tier) else None)
            arc_tinfo=(ARC_TARGETS["tiers"].get(tier) if (ARC_TARGETS and tier) else None)
            arc_retrace=(arc_tinfo or {}).get("median_retrace")
            arc_drop_pct=(arc_tinfo or {}).get("median_drop_pct")
            wall_break=(arc_tinfo or {}).get("wall_break_rate")
            entry=float(c[last])
            exp_leg=(tinfo or {}).get("firstleg_median_pct"); exp_whole=(tinfo or {}).get("wholerun_median_pct")
            exp_bars=(tinfo or {}).get("firstleg_median_bars")
            rfrac=_retrace_for(exp_leg)
            seen=set()
            for method,name,direction in fired:
                key=(method,name,direction)
                if key in seen: continue
                seen.add(key)
                side = "long" if direction in ("long","bullish","rise") else "short"
                if args.side!="both" and args.side!=side: continue
                # prefer the tier-specific base rate; fall back to pooled
                scope="tier"; bn,ba,bw=(br_tier.get(key+(tier,),(0,None,None)) if tier else (0,None,None))
                if bn<args.min_base_n or ba is None:
                    scope="pooled"; bn,ba,bw=br.get(key,(0,None,None))
                if bn<args.min_base_n or ba is None: continue
                # SIDE-AWARE edge: long wants fwd5>0; short has edge when fwd5<0 (edge=-ba,
                # win=% down). So a short only ranks if its MINED base rate says price fell —
                # the data teaches which shorts work. Raw ba/bw are stored for learning.
                if side=="long":
                    edge=ba; win=bw; trend_term=int(row["above_ema200"]); mr_term=float(row["mr_score"])
                    confident=bool(((row["mr_score"]>=1.0) or (row["rsi"]<45)) and d_trend!="down")
                    cconds=[row["mr_score"]>=1,row["rsi"]<40,row["above_ema200"]==1,row["bb_pct"]<0.15,row["vol_ratio"]>1.3,row["macd_hist"]>0]
                    target=round(entry*(1+exp_leg/100),4) if exp_leg else None
                    add_dip=round(target-rfrac*(target-entry),4) if target else None
                else:
                    edge=-ba; win=100.0-bw; trend_term=int(row["above_ema200"]==0); mr_term=-float(row["mr_score"])
                    confident=bool(((row["mr_score"]<=-1.0) or (row["rsi"]>70)) and d_trend!="up")
                    cconds=[row["mr_score"]<=-1,row["rsi"]>60,row["above_ema200"]==0,row["bb_pct"]>0.85,row["vol_ratio"]>1.3,row["macd_hist"]<0]
                    target=round(entry*(1-exp_leg/100),4) if exp_leg else None     # short target = down
                    add_dip=round(target+rfrac*(entry-target),4) if target else None # bounce to add the short
                conf=sum(int(bool(x)) for x in cconds)
                # +0.5 for confident entries (Layer-4 edge). Base-rate term CAPPED so microcaps don't dominate.
                conviction = round(min(edge,CONV_BASE_CAP)*(win/50.0) + 0.4*mr_term + 0.4*trend_term + 0.15*conf + (0.5 if confident else 0.0), 3)
                tgt_txt=(f"; tier {tier} {side} tgt {exp_leg:+.1f}% (~{exp_bars}b)" if tinfo else "")
                arc_txt=(f"; 5m arc move ~{arc_drop_pct:.1f}% (retrace {arc_retrace:.0%})" if arc_tinfo else "")
                # DATA-DRIVEN pattern projection: profitable side + target/low/duration.
                # For chart/candle patterns this OVERRIDES the tier target with the learned one.
                pe=PATTERN_EDGE.get(name)
                pat_txt=""
                if pe:
                    pt=pe.get("avg_target_pct"); pl=pe.get("avg_low_pct"); pbar=pe.get("median_bars_to_target")
                    target=round(entry*(1+pt/100),4) if pt is not None else target
                    add_dip=round(entry*(1+pl/100),4) if pl is not None else add_dip   # expected low / bid zone
                    flip=" FLIPPED" if pe.get("flipped") else ""
                    pat_txt=(f"; pattern[{side}{flip}] tgt {pt:+.1f}% / exp-low {pl:+.1f}% / ~{pbar}b "
                             f"(win {pe.get('win_rate')}%, n={pe.get('n')})")
                conf_txt=(" [CONFIDENT]" if confident else "")+(" SHORT" if side=="short" else "")
                alerts.append([str(sd),str(sd),tk,method,name,direction,
                    float(row["mr_score"]), 1 if row["mr_score"]>=1 else 0, int(conf),
                    int(row["above_ema200"]), float(row["rsi"]), float(cc[last]),
                    bn, round(ba,3), round(bw,1), conviction, True,
                    f"[{scope}/{side}] base {bn}x avg5 {ba:+.2f}% (edge {edge:+.2f}) win {win:.0f}%; mr {row['mr_score']:+.2f}{tgt_txt}{arc_txt}{pat_txt}{conf_txt}",
                    tier, entry, exp_leg, target, exp_bars, rfrac, add_dip, exp_whole, scope,
                    confident, arc_retrace, arc_drop_pct, wall_break])
        except Exception as e:
            cn.rollback()
        if i%200==0: print(f"  [{i}/{len(univ)}] {tk} alerts={len(alerts)} ({i/max(time.time()-t0,1e-9):.1f} tk/s)",flush=True)

    if not alerts:
        print("no setups fired today.",flush=True); return
    COLS=["scan_date","ts","ticker","method","name","direction","mr_score","mr_oversold",
          "confluence_n","above_ema200","rsi","cc_ret","base_n","base_avg_fwd5","base_win5",
          "conviction","needs_5m_confirm","explained_by",
          "liq_tier","entry_px","exp_firstleg_pct","target_px","exp_firstleg_bars",
          "retrace_frac","add_dip_px","exp_wholerun_pct","base_scope",
          "confident","arc_retrace_frac","arc_drop_pct","wall_break_rate"]
    sql=(f"INSERT INTO trade_alerts ({','.join(COLS)}) VALUES %s "
         "ON CONFLICT (scan_date,ticker,method,name,direction) DO UPDATE SET "
         "conviction=EXCLUDED.conviction, mr_score=EXCLUDED.mr_score, confluence_n=EXCLUDED.confluence_n, "
         "liq_tier=EXCLUDED.liq_tier, entry_px=EXCLUDED.entry_px, exp_firstleg_pct=EXCLUDED.exp_firstleg_pct, "
         "target_px=EXCLUDED.target_px, exp_firstleg_bars=EXCLUDED.exp_firstleg_bars, "
         "retrace_frac=EXCLUDED.retrace_frac, add_dip_px=EXCLUDED.add_dip_px, "
         "exp_wholerun_pct=EXCLUDED.exp_wholerun_pct, base_scope=EXCLUDED.base_scope, "
         "confident=EXCLUDED.confident, arc_retrace_frac=EXCLUDED.arc_retrace_frac, "
         "arc_drop_pct=EXCLUDED.arc_drop_pct, wall_break_rate=EXCLUDED.wall_break_rate")
    execute_values(cur,sql,alerts,page_size=1000); cn.commit()

    print(f"liquidity floor (min-tier {args.min_tier}) skipped {skipped_liq} sub-threshold tickers",flush=True)
    df=pd.DataFrame(alerts,columns=COLS).sort_values("conviction",ascending=False)
    out=ROOT/"reports/alerts"; out.mkdir(parents=True,exist_ok=True)
    show=["ticker","method","name","direction","liq_tier","confident","mr_score","entry_px","target_px",
          "exp_firstleg_pct","add_dip_px","arc_drop_pct","base_scope","base_avg_fwd5","base_win5","conviction"]
    show=[c for c in show if c in df.columns]
    top=df.head(args.top)
    n_conf=int(df["confident"].sum()) if "confident" in df.columns else 0
    n_long=int((df["direction"].isin(["long","bullish","rise"])).sum())
    n_short=len(df)-n_long
    rep=[f"# Trade alerts — {scan_date} (act next session on 5m VWAP reclaim)","",
         f"{len(df)} setups fired across {df['ticker'].nunique()} names ({args.universe} universe), all methods, "
         f"**both sides ({n_long} long / {n_short} short)**. **{n_conf} are CONFIDENT** (the +63% Layer-4 edge; "
         "ranked to the top). Ranked by SIDE-AWARE conviction (long edge = base avg5 > 0; short edge = base "
         "avg5 < 0 — a short only ranks if its mined base rate says price fell, so the data teaches which "
         f"shorts work). Liquidity floor: tiers >= {args.min_tier}; base-rate term capped at {CONV_BASE_CAP:.0f}%.","",
         "Each alert carries a forecast plan from the deep-dive studies: a liquidity-tier first-leg "
         "**target_px** (`exp_firstleg_pct` over ~`exp_firstleg_bars` bars), and an **add_dip_px** to "
         "add into the first pullback (retraces ~`retrace_frac` of the run). Base rates are tier-specific "
         "where available (`base_scope`).","",
         f"## Top {len(top)} alerts","",top[show].to_markdown(index=False),"",
         "## By method","",
         df.groupby("method").agg(n=("ticker","size"),avg_conv=("conviction","mean")).round(2).to_markdown(),"",
         "_Plan per alert: enter near entry_px next session only if price reclaims & closes above VWAP; "
         "first-leg target = target_px; on the first pullback, add near add_dip_px; base_avg_fwd5/base_win5 "
         "are the historical 5-day edge for this setup in this liquidity tier._"]
    (out/f"ALERTS_{scan_date}.md").write_text("\n".join(rep),encoding="utf-8")
    (out/"ALERTS_latest.md").write_text("\n".join(rep),encoding="utf-8")
    df.to_csv(out/f"alerts_{scan_date}.csv",index=False)
    print(f"\n{len(df)} alerts -> trade_alerts + reports/alerts/ALERTS_{scan_date}.md",flush=True)
    print("\nTOP 12:",flush=True); print(top[show].head(12).to_string(index=False),flush=True)

if __name__=="__main__":
    main()
