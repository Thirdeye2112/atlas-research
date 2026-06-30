"""
forward_read.py — single-ticker, all-layers forward read.

Pulls 5m (from intraday_bars DB, freshest) + daily, computes the full feature stack
on both, and reports the CURRENT state through every validated layer so we can read
what may be coming:
  * snapshot      : price, mr_score, rsi, atr, position-in-range, vwap, ema stack (5m & daily)
  * trend/regime  : daily + weekly trend (run-ability / direction confidence)
  * 5m arc        : recent up-legs since --since — launch velocity, lows-slope channel,
                    arc concavity, apex height/forecast (the thrown-ball read)
  * drop/support  : nearest higher-low support floor; expected retrace if extended (tier)
  * resistance    : nearest overhead 5m & daily wall + its drop-intensity (stall vs break)
  * MTF targets   : daily/weekly S&R ceiling -> which target rung is reachable; confident read

Usage:
    python scripts/forward_read.py --ticker NUAI --since 2026-06-22
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from basket_strategy import zscore_expanding
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from resistance_interaction_study import resistance_peaks


def load_5m_db(tk):
    import daily_scan as ds
    cn = ds._conn(); cur = cn.cursor()
    cur.execute("select ts,open,high,low,close,volume from intraday_bars "
                "where ticker=%s and timeframe='5m' order by ts", (tk,))
    rows = cur.fetchall(); cn.close()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    for c in ("open", "high", "low", "close", "volume"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)


def prep(df, intraday):
    df = dd.compute_indicators(df, intraday=intraday)
    df["mr"] = zscore_expanding(df)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--since", default="2026-06-22")
    ap.add_argument("--width", type=int, default=3)
    a = ap.parse_args()
    tk = a.ticker.upper(); since = pd.Timestamp(a.since)

    f = prep(load_5m_db(tk), intraday=True)
    d = dd.load_daily(tk); d["ts"] = pd.to_datetime(d["ts"])
    for c in ("open", "high", "low", "close", "volume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = prep(d, intraday=False)

    print(f"================ FORWARD READ: {tk} ================", flush=True)
    print(f"5m: {len(f)} bars -> {f['ts'].max()}   daily: {len(d)} bars -> {d['ts'].max().date()}", flush=True)

    # ---- snapshot (latest bars) ----
    L = f.iloc[-1]; D = d.iloc[-1]
    px = float(L["close"])
    print(f"\n[SNAPSHOT] last 5m close ${px:.2f} @ {f['ts'].max()}", flush=True)
    print(f"  5m : mr {L['mr']:+.2f}  rsi {L['rsi']:.0f}  atr% {L['atr_pct']:.2f}  bb_pct {L['bb_pct']:.2f}  "
          f"above_vwap {int(L['above_vwap'])}  emaBull {int(L['ema_stack_bull'])} emaBear {int(L['ema_stack_bear'])}", flush=True)
    print(f"  daily: close ${D['close']:.2f}  mr {D['mr']:+.2f}  rsi {D['rsi']:.0f}  atr% {D['atr_pct']:.2f}  "
          f"bb_pct {D['bb_pct']:.2f}  >200EMA {int(D['above_ema200'])}  macd_hist {D['macd_hist']:+.3f}", flush=True)

    # ---- trend / regime ----
    pv_d = ta_structure.swing_pivots(d["high"].values, d["low"].values, width=3)
    d_trend = ta_structure.classify_trend(pv_d)
    wk = d.set_index("ts").resample("W").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    pv_w = ta_structure.swing_pivots(wk["high"].values, wk["low"].values, width=2)
    w_trend = ta_structure.classify_trend(pv_w)
    print(f"\n[REGIME] daily trend = {d_trend.upper()}   weekly trend = {w_trend.upper()}", flush=True)

    # ---- recent action since --since (daily) ----
    drecent = d[d["ts"] >= since]
    if len(drecent):
        lo = drecent["low"].min(); hi = drecent["high"].max(); o0 = drecent.iloc[0]["open"]
        pos = (px - lo) / (hi - lo) * 100 if hi > lo else np.nan
        print(f"\n[SINCE {since.date()}] daily range ${lo:.2f}-${hi:.2f} (open ${o0:.2f}); "
              f"now ${px:.2f} = {pos:.0f}% of range. move from since-open {100*(px/o0-1):+.1f}%", flush=True)

    # ---- 5m arc: up-legs since --since ----
    fr = f[f["ts"] >= since].reset_index(drop=True)
    print(f"\n[5m ARC] up-legs since {since.date()} (n 5m bars={len(fr)}):", flush=True)
    if len(fr) > 20:
        h = fr["high"].values; l = fr["low"].values; c = fr["close"].values
        atr = fr["atr_pct"].values
        piv = ta_structure.swing_pivots(h, l, width=a.width)
        legs = ta_patterns.swing_legs(piv, h, l, c, min_amp=0.01)
        for lg in legs[-4:]:
            aix, bix = lg["start_idx"], lg["peak_idx"]
            Pa = c[aix]
            v3 = (c[min(aix+3, len(c)-1)] - Pa) / Pa / 3 * 100
            t3 = np.arange(min(4, bix-aix+1), dtype=float)
            losl = np.polyfit(t3, l[aix:aix+len(t3)], 1)[0] / Pa * 100 if len(t3) >= 2 else np.nan
            print(f"  leg {fr['ts'][aix].strftime('%m-%d %H:%M')}->{fr['ts'][bix].strftime('%H:%M')}: "
                  f"amp {lg['leg_amp']*100:+.1f}% in {bix-aix} bars, launch v3 {v3:+.2f}%/bar, "
                  f"lows-slope {losl:+.2f}%/bar, corr_depth {(lg['corr_depth'] or 0)*100:.1f}%", flush=True)

    # ---- support / resistance (daily) ----
    dh = d["high"].values; dl = d["low"].values
    datr_pr = D["atr_pct"]/100*px
    sr = ta_structure.support_resistance(pv_d, px, tol_pct=0.02, min_touches=2)
    res = [x for x in sr if x["side"] == "resistance"][:3]
    sup = [x for x in sr if x["side"] == "support"][:3]
    print(f"\n[DAILY S/R]  (1 daily-ATR ~ ${datr_pr:.2f})", flush=True)
    for x in res:
        print(f"  RES ${x['level']:.2f}  ({x['dist_pct']*100:+.1f}%, {x['dist_pct']*px/datr_pr:+.1f} ATR, {x['touches']} touches)", flush=True)
    for x in sup:
        print(f"  SUP ${x['level']:.2f}  ({x['dist_pct']*100:+.1f}%, {x['dist_pct']*px/datr_pr:+.1f} ATR, {x['touches']} touches)", flush=True)

    # nearest overhead daily wall + its drop-intensity (strong vs weak)
    rp = resistance_peaks(pv_d, dh, dl)
    above = [(i, p, dep) for (i, p, dep, spd) in rp if p > px]
    if above:
        i, p, dep = min(above, key=lambda x: x[1])
        strong = "STRONG" if dep >= D["atr_pct"]/100 else "weak"
        print(f"  nearest overhead daily wall ${p:.2f} (+{(p/px-1)*100:.1f}%); formed by a {dep*100:.1f}% "
              f"drop = {strong} ceiling -> {'likely STALL' if strong=='STRONG' else 'likely BREAKS'}", flush=True)

    # ---- FORMING patterns on the 5m right edge (live projection) ----
    import json as _json
    pe_path = ROOT / "reports/stocks/pattern_edge.json"
    pedge = _json.loads(pe_path.read_text()) if pe_path.exists() else {}
    fr5 = f.tail(120).reset_index(drop=True)
    fh, fl, fc, fv = fr5["high"].values, fr5["low"].values, fr5["close"].values, fr5["volume"].values
    fpiv = ta_structure.swing_pivots(fh, fl, width=a.width)
    forming = ta_patterns.forming_patterns(fpiv, fh, fl, fc, fv, pedge)
    print(f"\n[FORMING 5m PATTERNS] (right edge, live projection):", flush=True)
    if forming:
        for fm in forming:
            print(f"  {fm['name']} -> {fm['direction'].upper()}: breaks @${fm['breakout_level']} in ~{fm['bars_to_breakout']} bars "
                  f"=> target ${fm['target']} (exp-low ${fm['expected_low']}, conf {fm['confidence']}%, rvol {fm['rvol']})", flush=True)
    else:
        print("  none forming on the right edge right now", flush=True)

    # ---- recent candles / structure on daily last bar ----
    from atlas_research.ta.candlesticks import detect_all_candles
    o = d["open"].values; c2 = d["close"].values; lastix = len(d)-1
    cands = [cd.name for cd in detect_all_candles(o, dh, dl, c2, skip_neutral=True) if cd.confirm_idx >= lastix-1]
    pats = [ps.name for ps in ta_patterns.detect_all(pv_d, dh, dl, c2) if ps.confirm_idx >= lastix-2]
    print(f"\n[PATTERNS] recent daily candles: {cands or 'none'} | structures: {pats or 'none'}", flush=True)

    # ---- OPPORTUNITY SCAN: LONG vs SHORT (symmetric) ----
    # mr convention: + = oversold (long), - = overbought/extended-up (short).
    nearest_sup = sup[0]["level"] if sup else np.nan
    nearest_res = res[0]["level"] if res else np.nan
    strong_wall = None
    if above:
        wi, wp, wdep = min(above, key=lambda x: x[1])
        if wdep >= D["atr_pct"]/100:
            strong_wall = wp
    print("\n[OPPORTUNITY SCAN] both sides — entry zone / target / stop / trigger:", flush=True)

    # LONG: buy a dip to support that holds, in a non-downtrend, toward overhead res
    long_conf = ((D["mr"] >= 1.0) or (D["rsi"] < 40)) and d_trend != "down"
    long_tgt = nearest_res if np.isfinite(nearest_res) else px*1.1
    long_stop = sup[1]["level"] if len(sup) > 1 else (nearest_sup*0.95 if np.isfinite(nearest_sup) else px*0.9)
    print(f"  LONG : zone ${nearest_sup:.2f} (support) -> tgt ${long_tgt:.2f} / stop ${long_stop:.2f}"
          f"  | confident={long_conf} (trend {d_trend}); trigger = dip to support + mr oversold holds", flush=True)

    # SHORT: fade a rally into a STRONG overhead wall that rejects, toward support
    short_at = strong_wall if strong_wall else nearest_res
    short_conf = ((D["mr"] <= -1.0) or (D["rsi"] > 70)) and np.isfinite(short_at)
    ctr = " [COUNTER-TREND: daily up]" if d_trend == "up" else ""
    short_tgt = nearest_sup if np.isfinite(nearest_sup) else px*0.9
    short_stop = (short_at*1.03) if np.isfinite(short_at) else px*1.05
    print(f"  SHORT: zone ${short_at:.2f} (strong wall) -> tgt ${short_tgt:.2f} / stop ${short_stop:.2f}"
          f"  | confident={short_conf}{ctr}; trigger = rally into wall + mr overbought rejects", flush=True)

    # which side is actionable NOW?
    dist_sup = abs(px-nearest_sup)/px if np.isfinite(nearest_sup) else 9
    dist_res = abs(px-short_at)/px if np.isfinite(short_at) else 9
    if long_conf and dist_sup < 0.03:
        verdict = "LONG actionable (at support, oversold)"
    elif short_conf and dist_res < 0.03:
        verdict = "SHORT actionable (at wall, overbought)"
    else:
        verdict = (f"NEITHER yet — px ${px:.2f} mid-range; wait for dip to ${nearest_sup:.2f} (long) "
                   f"or rally to ${short_at:.2f} (short)")
    print(f"\n[VERDICT] {verdict}", flush=True)


if __name__ == "__main__":
    main()
