"""
arc_drop_support_study.py — the WHOLE arc: throw -> top -> bounce(drop) -> next rise.

Follow-up to channel_physics_study. We stop trying to *forecast* the pullback from
launch dynamics (that was ~R^2 0.13) and instead ask two practical questions about
the full arc:

  1. DROP-DISTANCE TARGETS we can PROPOSE. Characterise where the bounce actually
     lands (retrace fraction of the run) — unconditional and bucketed by run size —
     so we can place a rebuy bid with a band.

  2. SUPPORT LEVELS on the way up. Detect the footholds (higher-lows / local bases)
     built during the ascent and test whether the DROP STOPS AT SUPPORT:
       - does the bounce low land on a support made on the way up?
       - is "the last higher-low support" a better drop target than a blind % retrace?
       - does MORE support built on the way up (more/closer footholds) correlate with a
         SHALLOWER total drop (it gets caught sooner)?

Arc = swing low a (throw) -> swing high b (apex) -> correction low c (bounce), all in
ONE session (5m, 2023+, finest data). "next rise" is the leg off c.

Usage:
    python scripts/arc_drop_support_study.py                      # 10-name basket
    python scripts/arc_drop_support_study.py --tickers AAPL NVDA
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from scipy.signal import argrelextrema
from scipy.stats import spearmanr

BASKET = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "WMT"]


def _load(tk):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def supports_on_the_way_up(low, a, b, order=2):
    """Footholds built during the ascent a->b: the launch low, plus local minima of
    `low` strictly inside (a,b). Returns sorted list of (idx, price)."""
    sup = [(a, float(low[a]))]
    if b - a > 2 * order + 2:
        loc = argrelextrema(low[a + 1:b], np.less_equal, order=order)[0] + (a + 1)
        # collapse near-equal consecutive indices
        prev = None
        for i in loc:
            if prev is None or i - prev > order:
                sup.append((int(i), float(low[i]))); prev = i
    return sup


def collect(tk, width, min_amp, minbars):
    df = _load(tk)
    if len(df) < 250:
        return []
    df = dd.compute_indicators(df, intraday=True)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = df["atr_pct"].values
    sess = df["ts"].dt.date.values
    N = len(df); rows = []
    piv = ta_structure.swing_pivots(h, l, width=width)
    for lg in ta_patterns.swing_legs(piv, h, l, c, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]; cc = lg["corr_idx"]
        if a < 20 or b - a < minbars or cc is None:
            continue
        # one-session arc through the bounce
        if sess[a] != sess[b] or sess[b] != sess[cc] or cc <= b:
            continue
        Pa, Pb, Pc = c[a], h[b], l[cc]
        run = Pb - Pa
        if run <= 0 or Pa <= 0:
            continue
        drop = Pb - Pc
        retrace = drop / run                      # bounce low as fraction of the run
        run_pct = run / Pa * 100
        drop_pct = drop / Pb * 100

        # supports built on the way up
        sup = supports_on_the_way_up(l, a, b)
        sup_prices = np.array([p for _, p in sup])
        below = sup_prices[sup_prices < Pb]
        # candidate drop targets (price levels to bid)
        highest_HL = below.max() if below.size else Pa       # nearest support below the top
        recent_HL = sup[-1][1] if len(sup) > 1 else Pa        # most recent foothold by time
        n_sup = len(sup)
        # vertical room from peak down to the nearest support, as % of the run
        room_to_sup = (Pb - highest_HL) / run

        # did the bounce STOP at a support? nearest support to the actual bounce low
        nearest_gap = np.min(np.abs(sup_prices - Pc)) / run   # |Pc - closest support|, frac of run
        held_highest_HL = Pc >= highest_HL - 0.10 * run       # landed at/above nearest HL (tol 10% of run)

        # target-accuracy: |target - actual bounce| as fraction of the run (lower=better)
        def err(level):
            return abs(level - Pc) / run
        rows.append(dict(
            ticker=tk, date=str(sess[a]),
            run_pct=run_pct, drop_pct=drop_pct, retrace=retrace,
            run_bars=int(b - a), drop_bars=int(cc - b), L_atr=atr[a],
            n_sup=n_sup, room_to_sup=room_to_sup, nearest_gap=nearest_gap,
            held_highest_HL=bool(held_highest_HL),
            err_fixed35=err(Pb - 0.35 * run),
            err_fixed50=err(Pb - 0.50 * run),
            err_highHL=err(highest_HL),
            err_recentHL=err(recent_HL),
            err_launch=err(Pa),
        ))
    return rows


def pct(s, qs=(.1, .25, .5, .75, .9)):
    return {f"p{int(q*100)}": round(float(s.quantile(q)), 3) for q in qs}


def sp(d, x, y):
    s = d[[x, y]].dropna()
    if len(s) < 100:
        return None
    return round(spearmanr(s[x], s[y])[0], 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=BASKET)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp", type=float, default=0.01)
    ap.add_argument("--minbars", type=int, default=6)
    a = ap.parse_args()

    rows = []
    for tk in a.tickers:
        try:
            rows += collect(tk, a.width, a.min_amp, a.minbars)
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
    S = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
    S = S.dropna(subset=["retrace"])
    S = S[(S["retrace"] > 0) & (S["retrace"] < 3)]          # drop pathological
    n = len(S)
    print(f"=== {n} full arcs (throw->top->bounce, one session), {S['ticker'].nunique()} names ===", flush=True)

    # 1. drop-distance targets ---------------------------------------------------
    rt = S["retrace"]
    print(f"\n[1] DROP distance as fraction of the run (retrace):", flush=True)
    print(f"    {pct(rt)}", flush=True)
    print(f"    median drop = {S['drop_pct'].median():.2f}% from the top, over {S['drop_bars'].median():.0f} bars", flush=True)
    print("    by run size:", flush=True)
    S["run_bkt"] = pd.qcut(S["run_pct"], 4, labels=["small", "medium", "big", "huge"])
    bist = S.groupby("run_bkt", observed=True).agg(n=("retrace", "size"),
            med_retrace=("retrace", "median"), med_drop_pct=("drop_pct", "median"))
    print(bist.round(3).to_string(), flush=True)

    # 2. support on the way up ---------------------------------------------------
    print(f"\n[2] SUPPORT on the way up vs the drop:", flush=True)
    print(f"    avg footholds built on the way up: {S['n_sup'].mean():.1f}", flush=True)
    print(f"    corr(#supports, retrace) = {sp(S,'n_sup','retrace')}   "
          f"corr(#supports, drop %) = {sp(S,'n_sup','drop_pct')}", flush=True)
    print(f"    corr(room to nearest support, drop %) = {sp(S,'room_to_sup','drop_pct')}", flush=True)
    held = S["held_highest_HL"].mean()
    near = (S["nearest_gap"] <= 0.10).mean()
    print(f"    bounce landed at/above the nearest higher-low (held it): {held:.0%}", flush=True)
    print(f"    bounce low within 10% of the run of SOME support level: {near:.0%}", flush=True)

    # 3. which drop TARGET is closest to the actual bounce? ----------------------
    errs = {"fixed 35% retrace": "err_fixed35", "fixed 50% retrace": "err_fixed50",
            "nearest higher-low support": "err_highHL", "most-recent foothold": "err_recentHL",
            "full retrace to launch": "err_launch"}
    print(f"\n[3] DROP-TARGET accuracy — median |target - actual bounce| as % of run (lower=better):", flush=True)
    acc = {lbl: (round(S[col].median(), 3), round((S[col] <= 0.10).mean(), 3)) for lbl, col in errs.items()}
    for lbl, (med, within) in sorted(acc.items(), key=lambda x: x[1][0]):
        print(f"    {lbl:30s} med_err={med:<6} within-10%-of-run={within:.0%}", flush=True)

    # ---- report ----
    out = ROOT / "reports/stocks"
    rep = [f"# Arc drop-target & support study — 5m ({S['ticker'].nunique()} names, {n:,} arcs)", "",
           "The whole arc as one object: **throw → top → bounce → next rise**. We don't forecast the "
           "pullback from launch dynamics (that was ~R²0.13); instead we (1) propose drop-distance "
           "**targets** from where the bounce actually lands, and (2) test whether **support built on "
           "the way up** is where the drop stops.", "",
           "## 1. Proposable drop-distance targets", "",
           f"Drop (peak→bounce low) as a fraction of the run — **retrace** percentiles:", "",
           "| p10 | p25 | median | p75 | p90 |", "|---|---|---|---|---|",
           f"| {pct(rt)['p10']} | {pct(rt)['p25']} | {pct(rt)['p50']} | {pct(rt)['p75']} | {pct(rt)['p90']} |",
           "", f"Typical drop ≈ **{S['drop_pct'].median():.2f}%** off the top over ~{S['drop_bars'].median():.0f} bars. "
           f"By run size (bigger run → shallower retrace):", "",
           "| run size | n | median retrace | median drop % |", "|---|---|---|---|"]
    for idx, r in bist.iterrows():
        rep.append(f"| {idx} | {int(r['n'])} | {r['med_retrace']:.2f} | {r['med_drop_pct']:.2f}% |")
    rep += ["", "**Bid rule:** target ≈ peak − retrace×run; use ~0.30 for big/huge runs, ~0.45 for "
            "small/medium. Band the bid between p25 and p75 retrace.", "",
            "## 2. Does the drop stop at support built on the way up?", "",
            f"- Avg footholds (higher-lows/local bases) built during the ascent: **{S['n_sup'].mean():.1f}**.",
            f"- The bounce lands **at/above the nearest higher-low** (holds the last support) in "
            f"**{held:.0%}** of arcs; within 10%-of-run of *some* support level in **{near:.0%}**.",
            f"- More support built on the way up → shallower drop: corr(#supports, drop%) = "
            f"**{sp(S,'n_sup','drop_pct')}**, corr(#supports, retrace) = **{sp(S,'n_sup','retrace')}**.",
            f"- Vertical room down to the nearest support tracks the drop: "
            f"corr(room-to-support, drop%) = **{sp(S,'room_to_sup','drop_pct')}**.", "",
            "## 3. Which drop target lands closest to the actual bounce?", "",
            "Median |target − actual bounce| as % of the run (lower = sharper), and how often the "
            "target is within 10%-of-run of the real bounce:", "",
            "| drop target | median error | within 10% of run |", "|---|---|---|"]
    for lbl, (med, within) in sorted(acc.items(), key=lambda x: x[1][0]):
        rep.append(f"| {lbl} | {med} | {within:.0%} |")
    rep += ["", "_5m only (2023+). Survivorship: arcs are confirmed swing highs with a same-session "
            "bounce; in real time gate the rebuy with oversold/VWAP confirmation._"]
    (out / "ARC_DROP_SUPPORT_STUDY.md").write_text("\n".join(rep), encoding="utf-8")
    S.to_csv(out / "arc_drop_support.csv", index=False)
    print(f"\nwrote {out/'ARC_DROP_SUPPORT_STUDY.md'}", flush=True)


if __name__ == "__main__":
    main()
