#!/usr/bin/env python
"""
analyze_candlestick_aplus.py — iteration 4: the A+ setup test.

Tests whether the convergent trader playbook (mined in TA_RULES_FROM_INFOGRAPHICS.md)
turns the bullish-candlestick coin flip into an edge, using REALISTIC R-multiple
outcomes instead of fixed-horizon returns.

For each liquid ticker (raw_bars, split-safe adjusted OHLC) we compute per bar:
  - EMA 9/21/50/200, SMA 50/150/200, 30-wk MA (=150d)
  - ADX(14), RSI(14), MACD-hist(12,26,9), ATR(14)
  - Weinstein STAGE (1-4), Minervini trend-template pass
  - RS vs SPY (126d), extension (distance from 50EMA in ATRs)
And an R-multiple outcome per bar:
  entry = next bar open; stop = lowest low of prior `swing` bars; R = entry-stop;
  target = entry + 2R; over `horizon` bars: +2R if target hit before stop,
  -1R if stop first, else (final_close-entry)/R (timeout).

Then for BULLISH candlestick events we compare win-rate & expectancy (in R):
  ALL events   vs   each filter   vs   full A+ stack.

Usage:
  python scripts/analyze_candlestick_aplus.py            # full liquid universe
  python scripts/analyze_candlestick_aplus.py --limit 30 # quick validation
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd
from sqlalchemy import text
from atlas_research.db import connection

BULL = ('Hammer', 'Inverted hammer', 'Bullish engulfing', 'Morning star',
        'Tweezer bottom', 'Three white soldiers')

SWING = 10        # bars to define the swing-low stop
TARGET_R = 2.0    # 2R target
HORIZON = 24      # max bars to resolve (≈5 weeks, swing)
ADX_MIN = 25.0
EXT_ATR_MAX = 7.0  # "extended" if close is > 7 ATRs above 50EMA


def ema(s, n):  return s.ewm(span=n, adjust=False).mean()
def sma(s, n):  return s.rolling(n).mean()


def adx(high, low, close, n=14):
    up = high.diff(); dn = -low.diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = pd.concat([(high - low),
                    (high - close.shift()).abs(),
                    (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/n, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=high.index).ewm(alpha=1/n, adjust=False).mean() / atr
    mdi = 100 * pd.Series(minus_dm, index=high.index).ewm(alpha=1/n, adjust=False).mean() / atr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), atr


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100/(1+rs)


def r_at(o, h, l, c, i):
    """2R-vs-swing-low-stop outcome for a single signal bar i. Returns (R, hit)."""
    n = len(c)
    if i < SWING or i >= n - 1:
        return (np.nan, 0)
    entry = o[i+1]
    if not np.isfinite(entry) or entry <= 0:
        return (np.nan, 0)
    stop = np.min(l[i-SWING+1:i+1])
    risk = entry - stop
    if risk <= 0:
        return (np.nan, 0)
    target = entry + TARGET_R * risk
    end = min(i + 1 + HORIZON, n)
    for j in range(i+1, end):
        if l[j] <= stop:            # conservative: stop checked first
            return (-1.0, -1)
        if h[j] >= target:
            return (TARGET_R, 1)
    return ((c[end-1] - entry) / risk, 0)   # timeout: mark-to-market in R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-dvol", type=float, default=1_000_000)
    ap.add_argument("--price-floor", type=float, default=5.0)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    with connection.get_connection() as c:
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars "
                               "WHERE ticker='SPY' ORDER BY date"), c)
        universe = [r[0] for r in c.execute(text("""
            WITH r AS (SELECT ticker, avg(close*volume) dv FROM raw_bars
                       WHERE date >= (SELECT max(date)-120 FROM raw_bars) GROUP BY ticker)
            SELECT ticker FROM r WHERE dv >= :dv ORDER BY dv DESC
        """), {"dv": args.min_dvol}).fetchall()]
    if args.limit:
        universe = universe[:args.limit]
    spy = spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    spy_ret126 = spy / spy.shift(126) - 1.0
    print(f"A+ test | {len(universe):,} liquid tickers | 2R vs swing-low stop, {HORIZON}d horizon")

    # filters to evaluate (name -> predicate on the per-bar context DataFrame)
    filters = {
        "above_200ema":  lambda d: d["c"] > d["ema200"],
        "above_30wk":    lambda d: d["c"] > d["sma150"],
        "stage2":        lambda d: d["stage"] == 2,
        "adx>25":        lambda d: d["adx"] > ADX_MIN,
        "rs>spy":        lambda d: d["rs"] > 0,
        "not_extended":  lambda d: d["ext_atr"] < EXT_ATR_MAX,
        "rsi>50":        lambda d: d["rsi"] > 50,
        "macd>0":        lambda d: d["macdh"] > 0,
        "pullback_zone": lambda d: (d["c"] <= d["ema21"]) & (d["c"] >= d["ema50"]),
    }
    # accumulators: bucket -> [n, sum_R, wins(+2R reached)]
    acc = defaultdict(lambda: [0, 0.0, 0])

    def tally(bucket, Rvals, hits):
        a = acc[bucket]; a[0] += len(Rvals); a[1] += float(np.sum(Rvals)); a[2] += int(np.sum(hits == 1))

    processed = 0
    with connection.get_connection() as conn:
        for tk in universe:
            b = pd.read_sql(text("""SELECT date, open, high, low, close, adjusted_close, volume
                                    FROM raw_bars WHERE ticker=:t ORDER BY date"""),
                            conn, params={"t": tk})
            if len(b) < 220:
                continue
            b["date"] = pd.to_datetime(b["date"]); b = b.set_index("date")
            # split-safe adjusted OHLC
            fac = (b["adjusted_close"] / b["close"]).replace([np.inf, -np.inf], np.nan).fillna(1.0)
            o = (b["open"]*fac).astype(float); h = (b["high"]*fac).astype(float)
            l = (b["low"]*fac).astype(float);  cl = b["adjusted_close"].astype(float)

            ema9, ema21, ema50, ema200 = ema(cl,9), ema(cl,21), ema(cl,50), ema(cl,200)
            sma50, sma150, sma200 = sma(cl,50), sma(cl,150), sma(cl,200)
            adx14, atr14 = adx(h, l, cl)
            rsi14 = rsi(cl)
            macdh = ema(cl,12) - ema(cl,26); macdh = macdh - ema(macdh, 9)
            ext_atr = (cl - ema50) / atr14.replace(0, np.nan)
            sma150_slope = sma150 - sma150.shift(20)
            hh = cl > cl.shift(20)   # crude higher structure

            # Weinstein stage (simplified, robust):
            stage = pd.Series(0, index=cl.index)
            above = cl > sma150
            rising = sma150_slope > 0
            stage[(above) & (rising)] = 2
            stage[(above) & (~rising)] = 3
            stage[(~above) & (rising)] = 1
            stage[(~above) & (~rising)] = 4

            rs = (cl/cl.shift(126) - 1.0) - spy_ret126.reindex(cl.index)

            ctx = pd.DataFrame({
                "c": cl, "ema21": ema21, "ema50": ema50, "ema200": ema200,
                "sma150": sma150, "adx": adx14, "rsi": rsi14, "macdh": macdh,
                "ext_atr": ext_atr, "stage": stage, "rs": rs,
                "tradeable": (b["close"].astype(float) >= args.price_floor) &
                             (b["close"].astype(float)*b["volume"].astype(float) >= args.min_dvol),
            })

            ev = pd.read_sql(text("""SELECT timestamp::date d, candle_name FROM candlestick_outcomes
                                     WHERE ticker=:t"""), conn, params={"t": tk})
            if ev.empty:
                continue
            ev = ev[ev["candle_name"].isin(BULL)]
            if ev.empty:
                continue
            # Compute the R-multiple outcome ONLY at event bars (events are sparse).
            ov, hv, lv, cv = o.values, h.values, l.values, cl.values
            pos = ctx.index.get_indexer(pd.to_datetime(ev["d"].values))
            rows = []
            for p in pos:
                if p < 0:
                    continue
                Rv, hitv = r_at(ov, hv, lv, cv, p)
                if not np.isfinite(Rv):
                    continue
                rec = ctx.iloc[p].to_dict()
                rec["R"] = Rv; rec["hit"] = hitv
                rows.append(rec)
            if not rows:
                continue
            m = pd.DataFrame(rows)
            m = m[m["tradeable"].fillna(False)]
            if m.empty:
                continue

            tally("ALL bullish events", m["R"].values, m["hit"].values)
            for fname, fpred in filters.items():
                sel = m[fpred(m).fillna(False)]
                if len(sel):
                    tally(f"+{fname}", sel["R"].values, sel["hit"].values)
            # full A+ stack (long): trend + stage2 + adx + rs + not extended + momentum
            aplus = m[(m["c"] > m["ema200"]) & (m["stage"] == 2) & (m["adx"] > ADX_MIN) &
                      (m["rs"] > 0) & (m["ext_atr"] < EXT_ATR_MAX) &
                      (m["rsi"] > 50) & (m["macdh"] > 0)]
            if len(aplus):
                tally("A+ (full stack)", aplus["R"].values, aplus["hit"].values)
            processed += 1
            if processed % 500 == 0:
                print(f"  ...{processed}/{len(universe)}", flush=True)

    print(f"\n{'bucket':22}{'n':>10}{'win%(2R)':>10}{'exp(R)':>9}")
    order = (["ALL bullish events"] + [f"+{k}" for k in filters] + ["A+ (full stack)"])
    base = acc["ALL bullish events"]
    base_exp = base[1]/base[0] if base[0] else float('nan')
    for bucket in order:
        n, sR, w = acc[bucket]
        if n:
            print(f"{bucket:22}{n:>10,}{100*w/n:>10.1f}{sR/n:>9.3f}")
    print(f"\nBaseline expectancy = {base_exp:+.3f}R  | win = hit +2R before swing-low stop.")
    print("A+ should lift win% and expectancy materially above baseline to be real.")


if __name__ == "__main__":
    main()
