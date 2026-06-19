#!/usr/bin/env python
"""
pattern_backtest.py — Phase C+D: walk every detected chart pattern forward and
learn which patterns + CONTEXTS actually win.

For each pattern (confirmed, no-lookahead) on daily bars in the liquid universe:
  - Walk forward up to HORIZON bars from the confirmation.
  - WIN  = measured-move target reached before the invalidation stop.
    LOSS = stop hit first.  TIMEOUT = neither within horizon.
  - Capture CONTEXT at confirmation: daily trend, trend-alignment, distance to
    200-day SMA, weekly trend, volume confirmation.
Then aggregate the plain win-rate by pattern and by pattern x context, so we can
see which setups clear a target win-rate (the path to selectivity).

Output: reports/ta/pattern_outcomes.parquet + a printed learning table.
Usage: python scripts/pattern_backtest.py [--min-dvol 1e6] [--horizon 60] [--limit N]
"""
from __future__ import annotations
import argparse, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")

import numpy as np, pandas as pd
from sqlalchemy import text
from atlas_research.db import connection
from atlas_research.ta import structure as S, patterns as P

OUT = ROOT / "reports" / "ta" / "pattern_outcomes.parquet"
HORIZON = 60


def sma(a, n): return pd.Series(a).rolling(n).mean().to_numpy()


def walk(p, high, low, close, horizon):
    """Return ('win'/'loss'/'timeout', bars_held)."""
    n = len(close); j0 = p.confirm_idx + 1
    for j in range(j0, min(j0 + horizon, n)):
        if p.direction == "long":
            if low[j] <= p.stop:   return "loss", j - p.confirm_idx
            if high[j] >= p.target: return "win", j - p.confirm_idx
        else:
            if high[j] >= p.stop:  return "loss", j - p.confirm_idx
            if low[j] <= p.target:  return "win", j - p.confirm_idx
    return "timeout", min(horizon, n - 1 - p.confirm_idx)


def retest(p, high, low, close, horizon, wait=15):
    """
    Better entry: after confirmation, wait for price to pull back to the neckline
    and enter there, with a TIGHTER stop just beyond the pattern's structure
    extreme. Bigger reward:risk. Returns (outcome, rr) where outcome is
    'win'/'loss'/'timeout'/'nofill'. Only for neckline patterns.
    """
    if p.neckline is None:
        return ("na", float("nan"))
    N = p.neckline; ci = p.confirm_idx; n = len(close)
    pts = [pt[1] for pt in p.points]
    if p.direction == "long":
        stop = min(pts) * 0.995
        fill = next((j for j in range(ci+1, min(ci+1+wait, n)) if low[j] <= N), None)
        if fill is None or N - stop <= 0:
            return ("nofill", float("nan"))
        rr = (p.target - N) / (N - stop)
        for j in range(fill+1, min(fill+1+horizon, n)):
            if low[j] <= stop:    return ("loss", rr)
            if high[j] >= p.target: return ("win", rr)
        return ("timeout", rr)
    else:
        stop = max(pts) * 1.005
        fill = next((j for j in range(ci+1, min(ci+1+wait, n)) if high[j] >= N), None)
        if fill is None or stop - N <= 0:
            return ("nofill", float("nan"))
        rr = (N - p.target) / (stop - N)
        for j in range(fill+1, min(fill+1+horizon, n)):
            if high[j] >= stop:   return ("loss", rr)
            if low[j] <= p.target: return ("win", rr)
        return ("timeout", rr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--horizon", type=int, default=HORIZON)
    ap.add_argument("--width", type=int, default=5)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    with connection.get_connection() as c:
        univ = [r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv FROM raw_bars
                       WHERE date >= (SELECT max(date)-120 FROM raw_bars) GROUP BY ticker)
            SELECT ticker FROM r WHERE dv >= :dv ORDER BY dv DESC
        """), {"dv": args.min_dvol}).fetchall()]
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"), c)
    if args.limit: univ = univ[:args.limit]
    print(f"pattern backtest | {len(univ):,} tickers | horizon {args.horizon}d")

    rows = []; errors = 0
    with connection.get_connection() as conn:
        for ti, tk in enumerate(univ):
          try:
            df = pd.read_sql(text("SELECT date,high,low,close,adjusted_close,volume "
                                  "FROM raw_bars WHERE ticker=:t ORDER BY date"), conn, params={"t": tk})
            if len(df) < 260: continue
            fac = (df["adjusted_close"]/df["close"]).replace([np.inf,-np.inf],np.nan).fillna(1.0)
            h=(df["high"]*fac).to_numpy(); l=(df["low"]*fac).to_numpy(); cl=df["adjusted_close"].to_numpy()
            vol=df["volume"].to_numpy(); dates=pd.to_datetime(df["date"])
            sma200=sma(cl,200); vavg=sma(vol,20)
            wk=pd.Series(cl, index=dates).resample("W-FRI").last()
            wk_up=(wk>wk.rolling(30).mean()).reindex(dates, method="ffill").to_numpy()
            piv=S.swing_pivots(h,l,width=args.width)
            pats=P.detect_all(piv,h,l,cl)
            for p in pats:
                ci=p.confirm_idx
                if ci>=len(cl)-2 or not np.isfinite(sma200[ci]): continue
                outcome, held = walk(p, h, l, cl, args.horizon)
                rt_out, rt_rr = retest(p, h, l, cl, args.horizon)
                # context
                recent=[q for q in piv if q.idx<=ci]
                dtrend=S.classify_trend(recent)
                aligned = (p.direction=="long" and dtrend=="up") or (p.direction=="short" and dtrend=="down")
                rows.append(dict(ticker=tk, date=dates.iloc[ci], name=p.name, direction=p.direction,
                    outcome=outcome, win=int(outcome=="win"), held=held, rr=p.rr,
                    retest_outcome=rt_out, retest_win=int(rt_out=="win"),
                    retest_filled=bool(rt_out in ("win","loss","timeout")), retest_rr=float(rt_rr),
                    daily_trend=dtrend, aligned=bool(aligned),
                    above_200=bool(cl[ci]>sma200[ci]), weekly_up=bool(wk_up[ci]),
                    vol_confirm=bool(np.isfinite(vavg[ci]) and vol[ci]>1.3*vavg[ci])))
            if (ti+1)%300==0: print(f"  ...{ti+1}/{len(univ)}  patterns={len(rows):,} errs={errors}", flush=True)
          except Exception as e:
            errors += 1
            if errors <= 5: print(f"  err {tk}: {repr(e)[:90]}", flush=True)

    df=pd.DataFrame(rows)
    print(f"(per-ticker errors handled: {errors})")
    OUT.parent.mkdir(parents=True, exist_ok=True); df.to_parquet(OUT, index=False)
    print(f"\n{len(df):,} patterns -> {OUT}\n")

    def wr(d):
        resolved=d[d.outcome!="timeout"]
        return len(d), 100*d["win"].mean(), 100*(resolved["win"].mean() if len(resolved) else float('nan')), 100*(d.outcome=="timeout").mean()
    print(f"{'pattern':14}{'n':>7}{'win%(all)':>11}{'win%(resolved)':>15}{'timeout%':>10}")
    for nm in sorted(df["name"].unique()):
        n,wa,wrr,to=wr(df[df.name==nm]); print(f"{nm:14}{n:>7,}{wa:>10.1f}%{wrr:>14.1f}%{to:>9.1f}%")
    print("\n=== best pattern x context (resolved win%, n>=300) ===")
    res=[]
    for nm in df["name"].unique():
        for al in (True,False):
            for vc in (True,False):
                d=df[(df.name==nm)&(df.aligned==al)&(df.vol_confirm==vc)]
                r=d[d.outcome!="timeout"]
                if len(r)>=300:
                    res.append((nm, f"aligned={al},vol={vc}", len(r), 100*r["win"].mean()))
    for nm,ctx,n,w in sorted(res,key=lambda x:-x[3])[:12]:
        print(f"  {nm:13} {ctx:24} n={n:>6,}  win={w:.1f}%")
    print("\nwin = measured-move target hit before invalidation stop (plain win rate).")


if __name__ == "__main__":
    main()
