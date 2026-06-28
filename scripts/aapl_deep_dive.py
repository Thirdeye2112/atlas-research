"""
aapl_deep_dive.py — forensic, all-TA single-stock study on 5-minute candles.

Goal (per request): take ONE big stock (AAPL), layer EVERY TA we have on the
5-minute chart, then for
  (a) every SIGNIFICANT rise/drop  -> list all TA + news that explain the move,
  (b) every FULFILLED pattern (candlestick + chart structure) -> capture the
      full TA picture from t-2 .. t+2 around the pattern,
and render annotated charts for the 10 richest examples.

TA layers stacked here:
  * Continuous indicators (this file): candle anatomy, EMA 9/20/50/200 + slopes/
    stacking, SMA20/50, RSI(+slope/zones), MACD(+crosses), Stochastic, ROC,
    Williams%R, ATR%, Bollinger(+squeeze/breaks), Keltner, volume ratio/zscore,
    OBV, MFI, VWAP(+dist), opening-range position, swing-high/low distance,
    consecutive-direction streak, session/time-of-day.
  * Candlestick patterns: src/atlas_research/ta/candlesticks.detect_all_candles
    (engulfing, harami, stars, hammer family, marubozu, tweezers, 3-soldiers...).
  * Chart-structure patterns: src/atlas_research/ta/patterns.detect_all
    (head & shoulders, double top/bottom, flags) over swing pivots.
  * News: news_events (DB), joined by symbol + time to each event window.

Outputs -> reports/aapl_deep_dive/
  all_events.csv            every event with its flat t-2..t+2 TA window
  significant_moves.csv     all significant rises/drops + confluence explanation
  fulfilled_patterns.csv    all candlestick/structure pattern fulfillments
  AAPL_DEEP_DIVE.md         written summary + the 10 charted examples explained
  charts/NN_*.png           10 annotated candlestick charts (best examples)

Usage:
    python scripts/aapl_deep_dive.py
    python scripts/aapl_deep_dive.py --ticker AAPL --parquet data/samples/AAPL.parquet
    python scripts/aapl_deep_dive.py --n-charts 10 --move-pctl 0.5 --no-news
"""
from __future__ import annotations
import os, sys, re, argparse, warnings, urllib.parse as up
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# repo pattern detectors
from atlas_research.ta.candlesticks import detect_all_candles
from atlas_research.ta import patterns as ta_patterns
from atlas_research.ta import structure as ta_structure

WINDOW = 2   # candles before/after each event to capture

# ── indicators ──────────────────────────────────────────────────────────────────
def ema(s, p):  return s.ewm(span=p, adjust=False).mean()
def sma(s, p):  return s.rolling(p).mean()

def rsi(c, p=14):
    d = c.diff()
    g = d.clip(lower=0).ewm(com=p-1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=p-1, adjust=False).mean()
    return 100 - 100/(1 + g/l.replace(0, np.nan))

def compute_indicators(df: pd.DataFrame, intraday: bool = True) -> pd.DataFrame:
    o,h,l,c,v = (df[x] for x in ("open","high","low","close","volume"))
    rng = (h-l).replace(0, np.nan)

    # candle anatomy
    df["candle_ret"]   = (c-o)/o.replace(0,np.nan)*100
    df["body_pct"]     = (c-o).abs()/o.replace(0,np.nan)*100
    df["body_dir"]     = np.sign(c-o)
    df["range_pct"]    = rng/c*100
    df["upper_wick"]   = (h-np.maximum(o,c))/rng*100
    df["lower_wick"]   = (np.minimum(o,c)-l)/rng*100
    df["body_to_range"]= (c-o).abs()/rng
    df["gap_pct"]      = (o-c.shift(1))/c.shift(1)*100

    # trend / moving averages
    for p in (9,20,50,200):
        e = ema(c,p); df[f"ema{p}"]=e
        df[f"dist_ema{p}"]=(c-e)/e*100
        df[f"above_ema{p}"]=(c>e).astype(int)
    df["ema9_slope"]   = df["ema9"].diff()/df["ema9"]*100
    df["ema20_slope"]  = df["ema20"].diff()/df["ema20"]*100
    df["ema_stack_bull"]=((df["ema9"]>df["ema20"])&(df["ema20"]>df["ema50"])).astype(int)
    df["ema_stack_bear"]=((df["ema9"]<df["ema20"])&(df["ema20"]<df["ema50"])).astype(int)
    df["sma20"]=sma(c,20); df["sma50"]=sma(c,50)

    # momentum
    r=rsi(c,14); df["rsi"]=r
    df["rsi_slope"]=r.diff(2)
    df["rsi_oversold"]=(r<30).astype(int); df["rsi_overbought"]=(r>70).astype(int)
    df["rsi_reclaim50"]=((r>50)&(r.shift(1)<=50)).astype(int)
    df["rsi_lose50"]=((r<50)&(r.shift(1)>=50)).astype(int)
    macd=ema(c,12)-ema(c,26); sig=ema(macd,9)
    df["macd"]=macd; df["macd_signal"]=sig; df["macd_hist"]=macd-sig
    df["macd_bull_cross"]=((macd>sig)&(macd.shift(1)<=sig.shift(1))).astype(int)
    df["macd_bear_cross"]=((macd<sig)&(macd.shift(1)>=sig.shift(1))).astype(int)
    lo14=l.rolling(14).min(); hi14=h.rolling(14).max()
    df["stoch_k"]=(c-lo14)/(hi14-lo14).replace(0,np.nan)*100
    df["stoch_d"]=df["stoch_k"].rolling(3).mean()
    df["williams_r"]=(hi14-c)/(hi14-lo14).replace(0,np.nan)*-100
    df["roc_10"]=c.pct_change(10)*100

    # volatility
    tr=pd.concat([(h-l),(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    atr=tr.ewm(com=13,adjust=False).mean()
    df["atr"]=atr; df["atr_pct"]=atr/c*100
    bb_mid=sma(c,20); bb_std=c.rolling(20).std()
    bb_up=bb_mid+2*bb_std; bb_lo=bb_mid-2*bb_std
    df["bb_pct"]=(c-bb_lo)/(bb_up-bb_lo).replace(0,np.nan)
    df["bb_width"]=(bb_up-bb_lo)/bb_mid*100
    df["bb_squeeze"]=(df["bb_width"]<df["bb_width"].rolling(50).quantile(0.2)).astype(int)
    df["bb_break_up"]=(c>bb_up).astype(int); df["bb_break_dn"]=(c<bb_lo).astype(int)
    df["kc_up"]=bb_mid+1.5*atr; df["kc_lo"]=bb_mid-1.5*atr

    # volume
    vma=v.rolling(20,min_periods=1).mean()
    df["vol_ratio"]=v/vma.replace(0,np.nan)
    df["vol_z"]=(v-vma)/v.rolling(20).std().replace(0,np.nan)
    df["vol_climax"]=(df["vol_ratio"]>3).astype(int)
    df["obv"]=(np.sign(c.diff()).fillna(0)*v).cumsum()
    tp=(h+l+c)/3
    mf=tp*v; pos=mf.where(tp>tp.shift(1),0).rolling(14).sum()
    neg=mf.where(tp<tp.shift(1),0).rolling(14).sum()
    df["mfi"]=100-100/(1+pos/neg.replace(0,np.nan))

    if intraday:
        # VWAP (session) — intraday-only concept
        d=df["ts"].dt.date
        df["vwap"]=(tp*v).groupby(d).cumsum()/v.groupby(d).cumsum().replace(0,np.nan)
        df["vwap_dist"]=(c-df["vwap"])/df["vwap"]*100
        df["above_vwap"]=(c>df["vwap"]).astype(int)
        # opening-range position (first 30m = 6 bars) + session
        mins=df["ts"].dt.hour*60+df["ts"].dt.minute
        df["tod_min"]=mins
        df["is_open_30m"]=((mins>=570)&(mins<600)).astype(int)
        df["is_power_hour"]=((mins>=900)&(mins<960)).astype(int)
        orh=h.groupby(d).transform(lambda s:s.iloc[:6].max())
        orl=l.groupby(d).transform(lambda s:s.iloc[:6].min())
        df["or_position"]=(c-orl)/(orh-orl).replace(0,np.nan)

    # swing structure distance + streak
    df["dist_hi_20"]=(c-h.rolling(20).max())/c*100
    df["dist_lo_20"]=(c-l.rolling(20).min())/c*100
    streak=np.zeros(len(df)); s=0.0
    for i,bd in enumerate(df["body_dir"].fillna(0).values):
        s=s+bd if bd==np.sign(s) and bd!=0 else bd; streak[i]=s
    df["consec_dir"]=streak

    # forward returns (open->close at +1..+6 and cumulative)
    for k in (1,3,6,12):
        df[f"fwd_ret_{k}"]=(c.shift(-k)-c)/c*100
    return df

# columns that constitute the "TA snapshot" captured per window bar
SNAPSHOT = ["open","high","low","close","volume","candle_ret","body_pct","body_dir",
    "range_pct","upper_wick","lower_wick","gap_pct","dist_ema9","dist_ema20","dist_ema50",
    "dist_ema200","above_ema200","ema9_slope","ema_stack_bull","ema_stack_bear","rsi","rsi_slope",
    "rsi_oversold","rsi_overbought","macd_hist","macd_bull_cross","macd_bear_cross",
    "stoch_k","williams_r","roc_10","atr_pct","bb_pct","bb_width","bb_squeeze",
    "bb_break_up","bb_break_dn","vol_ratio","vol_z","vol_climax","mfi","vwap_dist",
    "above_vwap","or_position","dist_hi_20","dist_lo_20","consec_dir","tod_min"]

# ── explain a move with converging TA ───────────────────────────────────────────
def explain_move(row, direction: str, intraday: bool = True) -> list[str]:
    """Return the list of TA signals that align with a rise/drop at this bar.
    `row.get(...)` keeps it safe when intraday-only cols (VWAP/OR) are absent."""
    g=lambda k: row.get(k,0) if hasattr(row,"get") else row[k]
    R=[]
    if direction=="rise":
        if g("rsi_oversold"):     R.append("RSI<30 oversold bounce")
        if g("rsi_reclaim50"):    R.append("RSI reclaimed 50")
        if g("macd_bull_cross"):  R.append("MACD bullish cross")
        if g("macd_hist")>0:      R.append("MACD histogram positive")
        if g("bb_break_dn") or g("bb_pct")<0.1: R.append("snap-back off lower BB")
        if g("vol_climax"):       R.append("volume climax")
        elif g("vol_ratio")>1.5:  R.append(f"elevated volume ({g('vol_ratio'):.1f}x)")
        if intraday and g("above_vwap"): R.append("reclaimed/above VWAP")
        if g("ema_stack_bull"):   R.append("bullish EMA stack (9>20>50)")
        if g("above_ema200"):     R.append("above 200-EMA (uptrend)")
        if g("stoch_k") and g("stoch_k")<20: R.append("Stoch oversold")
        if intraday and g("or_position")>0.9: R.append("breakout above opening range")
        if g("consec_dir")>=3:    R.append(f"{int(g('consec_dir'))} up-bars in a row")
    else:
        if g("rsi_overbought"):   R.append("RSI>70 overbought rollover")
        if g("rsi_lose50"):       R.append("RSI lost 50")
        if g("macd_bear_cross"):  R.append("MACD bearish cross")
        if g("macd_hist")<0:      R.append("MACD histogram negative")
        if g("bb_break_up") or g("bb_pct")>0.9: R.append("rejection off upper BB")
        if g("vol_climax"):       R.append("volume climax (distribution)")
        elif g("vol_ratio")>1.5:  R.append(f"elevated volume ({g('vol_ratio'):.1f}x)")
        if intraday and not g("above_vwap"): R.append("lost VWAP")
        if g("ema_stack_bear"):   R.append("bearish EMA stack (9<20<50)")
        if not g("above_ema200"): R.append("below 200-EMA (downtrend)")
        if g("stoch_k")>80:       R.append("Stoch overbought")
        if intraday and g("or_position") and g("or_position")<0.1: R.append("breakdown below opening range")
        if g("consec_dir")<=-3:   R.append(f"{int(abs(g('consec_dir')))} down-bars in a row")
    return R

# ── news (fast: searchsorted over a sorted int64 timeline) ──────────────────────
class News:
    """Holds AAPL headlines and answers 'any news near [t0,t1]?' in O(log n)."""
    def __init__(self, df: pd.DataFrame):
        self.n = len(df)
        if self.n:
            df = df.sort_values("ts").reset_index(drop=True)
            self.ts_i64 = df["ts"].values.astype("datetime64[ns]").view("int64")
            self.labels = [f"{r.ts:%Y-%m-%d %H:%M} [{r.source}] {r.headline}" for r in df.itertuples()]
        else:
            self.ts_i64 = np.empty(0, "int64"); self.labels = []
    def near(self, t0_i64: int, t1_i64: int, pad_ns: int = 2*3600*10**9) -> list[str]:
        if self.n == 0: return []
        lo = np.searchsorted(self.ts_i64, t0_i64 - pad_ns, "left")
        hi = np.searchsorted(self.ts_i64, t1_i64 + pad_ns, "right")
        return self.labels[lo:hi][:4]

def _connect():
    import psycopg2
    env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
    u=up.urlparse(env["DATABASE_URL"].strip())
    return psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))

def load_daily(ticker: str) -> pd.DataFrame:
    """Full ~15y daily OHLCV from raw_bars."""
    cn=_connect(); cur=cn.cursor(); cur.execute("set statement_timeout='40s'")
    cur.execute("""select date, open, high, low, close, volume from raw_bars
                   where ticker=%s order by date""",(ticker,))
    rows=cur.fetchall(); cn.close()
    df=pd.DataFrame(rows,columns=["ts","open","high","low","close","volume"])
    df["ts"]=pd.to_datetime(df["ts"])
    return df

def load_news(ticker: str) -> pd.DataFrame:
    try:
        import psycopg2
        env=dict(re.findall(r'^([A-Z_]+)=(.*)$',(ROOT/".env").read_text(),re.M))
        u=up.urlparse(env["DATABASE_URL"].strip())
        cn=psycopg2.connect(host=u.hostname,port=u.port,user=u.username,
                            password=up.unquote(u.password or ""),dbname=u.path.lstrip("/"))
        cur=cn.cursor(); cur.execute("set statement_timeout='30s'")
        cur.execute("""select created_at, headline, source from news_events
                       where symbol=%s order by created_at""",(ticker,))
        rows=cur.fetchall(); cn.close()
        if not rows: return pd.DataFrame(columns=["ts","headline","source"])
        nd=pd.DataFrame(rows,columns=["ts","headline","source"])
        nd["ts"]=pd.to_datetime(nd["ts"],utc=True).dt.tz_localize(None)
        return nd
    except Exception as e:
        print(f"  [news] unavailable ({str(e)[:60]}) — proceeding without news",flush=True)
        return pd.DataFrame(columns=["ts","headline","source"])

# ── window capture (fast: index a prebuilt numpy matrix) ────────────────────────
TAGS={-2:"tm2",-1:"tm1",0:"t0",1:"tp1",2:"tp2"}
def window_row(snap: np.ndarray, loc: int, cols: list[str], w: int = WINDOW) -> dict:
    out={}
    for off in range(-w,w+1):
        j=loc+off
        if j<0 or j>=snap.shape[0]: continue
        tag=TAGS[off]; rowj=snap[j]
        for k,col in enumerate(cols):
            out[f"{tag}_{col}"]=rowj[k]
    return out

# ── charting ────────────────────────────────────────────────────────────────────
def render_chart(df, loc, title, subtitle, news_lines, out_path, pad=26):
    import matplotlib; matplotlib.use("Agg")
    import mplfinance as mpf
    import matplotlib.pyplot as plt
    a=max(0,loc-pad); b=min(len(df),loc+pad+1)
    sl=df.iloc[a:b].copy()
    sl.index=pd.DatetimeIndex(sl["ts"])
    ev_t=df.iloc[loc]["ts"]
    w0=df.iloc[max(0,loc-WINDOW)]["ts"]; w1=df.iloc[min(len(df)-1,loc+WINDOW)]["ts"]
    aps=[
        mpf.make_addplot(sl["ema9"],  color="#1f77b4",width=0.8),
        mpf.make_addplot(sl["ema20"], color="#ff7f0e",width=0.8),
        mpf.make_addplot(sl["ema50"], color="#9467bd",width=0.8),
    ]
    if "vwap" in sl.columns and sl["vwap"].notna().any():
        aps.append(mpf.make_addplot(sl["vwap"],color="#2ca02c",width=0.9,linestyle="--"))
    elif "ema200" in sl.columns:
        aps.append(mpf.make_addplot(sl["ema200"],color="#2ca02c",width=0.9,linestyle="--"))
    aps+=[
        mpf.make_addplot(sl["rsi"],   panel=2,color="#d62728",width=0.9,ylabel="RSI",
                         ylim=(0,100),secondary_y=False),
        mpf.make_addplot([70]*len(sl),panel=2,color="grey",width=0.5,linestyle=":",secondary_y=False),
        mpf.make_addplot([30]*len(sl),panel=2,color="grey",width=0.5,linestyle=":",secondary_y=False),
        mpf.make_addplot(sl["macd_hist"],panel=3,type="bar",color="#7f7f7f",ylabel="MACD",secondary_y=False),
    ]
    style=mpf.make_mpf_style(base_mpf_style="yahoo",gridstyle=":",rc={"font.size":8})
    fig,axes=mpf.plot(sl,type="candle",style=style,addplot=aps,volume=True,
                      panel_ratios=(6,2,2,2),figsize=(13,9),returnfig=True,
                      vlines=dict(vlines=[w0,w1],colors="#888",linewidths=0.8,alpha=0.6),
                      tight_layout=True,xrotation=15)
    axes[0].axvspan(sl.index.get_loc(w0),sl.index.get_loc(w1),color="gold",alpha=0.10)
    axes[0].set_title(title,fontsize=11,fontweight="bold",loc="left")
    txt=subtitle
    if news_lines:
        txt+="\nNEWS: "+news_lines[0]
    axes[0].text(0.005,0.97,txt,transform=axes[0].transAxes,va="top",ha="left",
                 fontsize=7.5,bbox=dict(boxstyle="round",fc="white",ec="grey",alpha=0.85))
    fig.savefig(out_path,dpi=130,bbox_inches="tight"); plt.close(fig)

# ── main ────────────────────────────────────────────────────────────────────────
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ticker",default="AAPL")
    ap.add_argument("--parquet",default=str(ROOT/"data/samples/AAPL.parquet"))
    ap.add_argument("--n-charts",type=int,default=10)
    ap.add_argument("--move-pctl",type=float,default=0.5,
                    help="single-bar |return| percentile (each tail) that counts as 'significant'")
    ap.add_argument("--no-news",action="store_true")
    ap.add_argument("--timeframe",choices=["intraday","daily"],default="intraday",
                    help="intraday=5m parquet (2023+); daily=raw_bars full ~15y")
    args=ap.parse_args()
    intraday = args.timeframe=="intraday"
    tflabel  = "5-minute" if intraday else "daily"

    out=ROOT/("reports/aapl_deep_dive" if intraday else "reports/aapl_deep_dive_daily")
    (out/"charts").mkdir(parents=True,exist_ok=True)
    for old in (out/"charts").glob("*.png"): old.unlink()   # clear stale charts

    print(f"=== {args.ticker} deep dive ({tflabel}) ===",flush=True)
    if intraday:
        df=pd.read_parquet(args.parquet)
        df["ts"]=pd.to_datetime(df["ts"],utc=True).dt.tz_localize(None)
    else:
        df=load_daily(args.ticker)
    df=df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open","high","low","close","volume"):
        df[cc]=pd.to_numeric(df[cc],errors="coerce")
    print(f"  bars: {len(df):,}  {df['ts'].min():%Y-%m-%d} -> {df['ts'].max():%Y-%m-%d}",flush=True)
    df=compute_indicators(df,intraday=intraday)

    news_df=pd.DataFrame(columns=["ts","headline","source"]) if args.no_news else load_news(args.ticker)
    news=News(news_df)
    print(f"  news headlines: {news.n:,}",flush=True)

    # fast-access arrays (avoid slow df.iloc in hot loops)
    o,h,l,c=(df[x].values for x in ("open","high","low","close"))
    N=len(df)
    snap_cols=[col for col in SNAPSHOT if col in df.columns]   # drops intraday-only cols in daily mode
    snap=df[snap_cols].to_numpy(dtype="float64")              # N x len(snap_cols)
    ts_i64=df["ts"].values.astype("datetime64[ns]").view("int64")
    ts_list=df["ts"].tolist()
    fwd6=df["fwd_ret_6"].values
    NEWS_PAD = (2*3600*10**9) if intraday else (36*3600*10**9)   # 2h intraday, 36h daily
    def wnews(loc):                                           # news in the [-2,+2] window
        return news.near(ts_i64[max(0,loc-WINDOW)], ts_i64[min(N-1,loc+WINDOW)], NEWS_PAD)

    # ---- (1) fulfilled patterns: candlestick + structure ----
    print("  detecting candlestick + structure patterns ...",flush=True)
    candles=detect_all_candles(o,h,l,c,skip_neutral=True)
    piv=ta_structure.swing_pivots(h,l,width=3)
    structs=ta_patterns.detect_all(piv,h,l,c)
    pat_rows=[]
    for cd in candles:
        loc=cd.confirm_idx
        if loc<WINDOW or loc>=N-WINDOW: continue
        pat_rows.append({"event_type":"candlestick","name":cd.name,"direction":cd.direction,
                         "loc":int(loc),"ts":ts_list[loc],"outcome_fwd6_pct":float(fwd6[loc])})
    for ps in structs:
        loc=ps.confirm_idx
        if loc<WINDOW or loc>=N-WINDOW: continue
        pat_rows.append({"event_type":"structure","name":ps.name,"direction":ps.direction,
                         "loc":int(loc),"ts":ts_list[loc],"outcome_fwd6_pct":float(fwd6[loc])})
    pat_df=pd.DataFrame(pat_rows)

    # ---- (2) significant moves ----
    print("  flagging significant moves ...",flush=True)
    cr=df["candle_ret"].values
    atrp=df["atr_pct"].values
    hi_thr=np.nanpercentile(cr,100-args.move_pctl); lo_thr=np.nanpercentile(cr,args.move_pctl)
    mv_rows=[]
    for loc in np.where((cr>=hi_thr)|(cr<=lo_thr))[0]:
        if loc<WINDOW or loc>=N-WINDOW: continue
        direction="rise" if cr[loc]>=hi_thr else "drop"
        row=df.iloc[loc]                                   # only ~few thousand moves
        reasons=explain_move(row,direction,intraday)
        mv_rows.append({"event_type":"move","name":f"significant_{direction}","direction":direction,
                        "loc":int(loc),"ts":ts_list[loc],"candle_ret_pct":float(cr[loc]),
                        "atr_mult":abs(cr[loc])/(atrp[loc] if atrp[loc] else np.nan),
                        "confluence":len(reasons),"explained_by":"; ".join(reasons),
                        "outcome_fwd6_pct":float(fwd6[loc])})
    mv_df=pd.DataFrame(mv_rows)
    n_cs=int((pat_df['event_type']=='candlestick').sum()) if not pat_df.empty else 0
    n_st=int((pat_df['event_type']=='structure').sum()) if not pat_df.empty else 0
    print(f"  candlestick={n_cs:,}  structure={n_st:,}  significant_moves={len(mv_df):,}",flush=True)

    # ---- assemble all_events with t-2..t+2 windows + news (numpy-fast) ----
    print("  building t-2..t+2 windows + news join ...",flush=True)
    all_rows=[]
    for src_df in (mv_df,pat_df):
        if src_df.empty: continue
        cols=list(src_df.columns)
        for r in src_df.itertuples(index=False):
            loc=r.loc
            base={k:getattr(r,k) for k in cols}
            base["news"]=" || ".join(wnews(loc))
            base.update(window_row(snap,loc,snap_cols))
            all_rows.append(base)
    all_df=pd.DataFrame(all_rows)

    # ---- write data artifacts (parquet for the big windowed table) ----
    print(f"  writing {len(all_df):,} windowed events ...",flush=True)
    all_df.to_parquet(out/"all_events.parquet",index=False)
    if not mv_df.empty:  mv_df.sort_values("confluence",ascending=False).to_csv(out/"significant_moves.csv",index=False)
    if not pat_df.empty: pat_df.sort_values("outcome_fwd6_pct",key=lambda s:s.abs(),ascending=False).to_csv(out/"fulfilled_patterns.csv",index=False)

    # ---- pick the 10 richest examples for charting ----
    # blend: significant moves with most converging TA (+ news bonus), and the
    # cleanest pattern fulfillments (largest |forward outcome|).
    picks=[]
    if not mv_df.empty:
        mm=mv_df.copy()
        mm["has_news"]=[1 if wnews(loc) else 0 for loc in mm["loc"]]
        mm["score"]=mm["confluence"]+1.5*mm["has_news"]+0.2*mm["outcome_fwd6_pct"].abs()
        picks+= [("move",r) for r in mm.sort_values("score",ascending=False).head(args.n_charts).itertuples(index=False)]
    if not pat_df.empty:
        pp=pat_df.copy(); pp["abs_out"]=pp["outcome_fwd6_pct"].abs()
        picks+= [("pattern",r) for r in pp.sort_values("abs_out",ascending=False).head(args.n_charts).itertuples(index=False)]

    # interleave moves & patterns, keep best n
    picks_sorted=[]
    mv_picks=[p for p in picks if p[0]=="move"]; pt_picks=[p for p in picks if p[0]=="pattern"]
    for i in range(max(len(mv_picks),len(pt_picks))):
        if i<len(mv_picks): picks_sorted.append(mv_picks[i])
        if i<len(pt_picks): picks_sorted.append(pt_picks[i])
    picks_sorted=picks_sorted[:args.n_charts]

    print(f"  rendering {len(picks_sorted)} charts ...",flush=True)
    report=[f"# {args.ticker} — Deep TA Dive ({tflabel} candles)","",
            f"**Bars:** {len(df):,} ({df['ts'].min():%Y-%m-%d} -> {df['ts'].max():%Y-%m-%d})  |  "
            f"**News headlines:** {news.n:,}","",
            f"TA layered per candle: {len(snap_cols)} continuous indicators + "
            f"19 candlestick patterns + chart-structure (H&S / double top-bottom / flags).","",
            "## What was found","",
            f"- Significant moves (|1-bar return| in the {args.move_pctl}% tails): "
            f"**{len(mv_df):,}**",
            f"- Candlestick fulfillments: **{0 if pat_df.empty else int((pat_df['event_type']=='candlestick').sum()):,}**",
            f"- Structure fulfillments: **{0 if pat_df.empty else int((pat_df['event_type']=='structure').sum()):,}**","",
            "Full records (with t-2..t+2 TA windows): `all_events.parquet`, "
            "`significant_moves.csv`, `fulfilled_patterns.csv`.","",
            "## The 10 charted examples",""]

    for i,(kind,r) in enumerate(picks_sorted,1):
        loc=r.loc; row=df.iloc[loc]
        nl=wnews(loc)
        tfmt="%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"
        if kind=="move":
            direction=r.direction
            title=f"{i:02d}. {args.ticker} significant {direction.upper()} {row['ts']:{tfmt}}  ({r.candle_ret_pct:+.2f}%, {r.atr_mult:.1f}x ATR)"
            reasons=explain_move(row,direction,intraday)
            subtitle=f"Confluence ({len(reasons)}): "+"; ".join(reasons) if reasons else "Confluence: (none aligned)"
            fname=f"{i:02d}_move_{direction}_{row['ts']:%Y%m%d_%H%M}.png"
        else:
            title=f"{i:02d}. {args.ticker} {r.name.upper()} ({r.direction}) {row['ts']:{tfmt}}  -> fwd6 {r.outcome_fwd6_pct:+.2f}%"
            vwap_bit=(f"VWAPdist {row['vwap_dist']:+.2f}% | {'above' if row['above_vwap'] else 'below'} VWAP | "
                      if intraday and 'vwap_dist' in row else "")
            subtitle=(f"RSI {row['rsi']:.0f} | MACDh {row['macd_hist']:+.3f} | vol {row['vol_ratio']:.1f}x | "
                      f"BB% {row['bb_pct']:.2f} | {vwap_bit}"
                      f"{'above' if row['above_ema200'] else 'below'} 200EMA | EMA stack "
                      f"{'bull' if row['ema_stack_bull'] else ('bear' if row['ema_stack_bear'] else 'mixed')}")
            fname=f"{i:02d}_{r.event_type}_{r.name}_{row['ts']:%Y%m%d_%H%M}.png"
        try:
            render_chart(df,loc,title,subtitle,nl,out/"charts"/fname)
        except Exception as e:
            print(f"    chart {i} failed: {str(e)[:80]}"); continue
        report+= [f"### {title}","",f"![chart](charts/{fname})","",
                  f"- **TA read:** {subtitle}",
                  (f"- **News:** {nl[0]}" if nl else "- **News:** (none in window)"),
                  f"- **Outcome (next 6 bars):** {row['fwd_ret_6']:+.2f}%",""]

    (out/"AAPL_DEEP_DIVE.md").write_text("\n".join(report),encoding="utf-8")
    print(f"\nDone. Report + charts in {out}")

if __name__=="__main__":
    main()
