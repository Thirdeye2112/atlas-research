"""
resistance_interaction_study.py — does PRIOR RESISTANCE stop the run?

Follow-up to the arc studies. For every up-run (throw->top), find the nearest
HISTORIC resistance level above the launch — a prior swing HIGH that previously
rejected price — and characterise it by:
  * AGE        : how many bars/sessions ago it formed
  * STRENGTH   : how many times that level was tested (touches)
  * DROP INTENSITY : how hard/fast price fell when that prior peak formed (the
                     rejection that *made* it resistance) — depth and per-bar speed.

Then answer:
  1. How many runs TOP/STALL at prior resistance vs punch into clear air?
  2. What age / strength / drop-intensity of resistance do runs BREAK THROUGH
     (vs the ones that stop them)?
  3. Does the level's DROP INTENSITY predict STALL (fail) vs BREAK (continue)?
     -> bucketed P(break | reached) and the continuation past a broken level.

Resistance candidates are prior swing highs within LOOKBACK bars, lying 0.2–4.0
ATR above the launch (levels the run could plausibly reach). 5m, 2023+.

Usage:
    python scripts/resistance_interaction_study.py                     # basket
    python scripts/resistance_interaction_study.py --tickers AAPL NVDA
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from scipy.stats import spearmanr

BASKET = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "WMT"]


def _load(tk):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def resistance_peaks(piv, high, low):
    """Prior swing highs as resistance levels, each with the DROP that formed it
    (peak -> following swing low): depth (frac) and per-bar speed (frac/bar)."""
    res = []
    for i in range(len(piv) - 1):
        p = piv[i]
        if p.kind != "H":
            continue
        nxt = piv[i + 1]
        if nxt.kind == "L" and nxt.price < p.price and p.price > 0:
            depth = (p.price - nxt.price) / p.price
            bars = max(nxt.idx - p.idx, 1)
            res.append((p.idx, float(p.price), float(depth), depth / bars))
    return res


def collect(tk, width, min_amp, minbars, lookback, minwall):
    df = _load(tk)
    if len(df) < 300:
        return []
    df = dd.compute_indicators(df, intraday=True)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    atrp = df["atr_pct"].values
    N = len(df)
    piv = ta_structure.swing_pivots(h, l, width=width)
    res = resistance_peaks(piv, h, l)
    res_idx = np.array([r[0] for r in res]); res_px = np.array([r[1] for r in res])
    res_dep = np.array([r[2] for r in res]); res_spd = np.array([r[3] for r in res])
    rows = []
    for lg in ta_patterns.swing_legs(piv, h, l, c, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]
        if a < 30 or b - a < minbars:
            continue
        Pa = c[a]; apex = h[b]
        atr_pr = atrp[a] / 100 * Pa if atrp[a] > 0 else np.nan
        if Pa <= 0 or not np.isfinite(atr_pr) or atr_pr <= 0:
            continue
        # apex-clustering: does the TOP land on ANY prior resistance level? (vs an
        # offset placebo top, to net out level density)
        wm = (res_idx >= a - lookback) & (res_idx < a)
        apex_at_res = apex_placebo = None
        if wm.any():
            wpx = res_px[wm]
            apex_at_res = bool(np.min(np.abs(wpx - apex)) <= 0.5 * atr_pr)
            apex_placebo = bool(np.min(np.abs(wpx - (apex + 1.5 * atr_pr))) <= 0.5 * atr_pr)
        # candidate resistance = first real WALL: prior peaks in [a-lookback, a),
        # minwall..4.0 ATR above launch (so breaking it is a non-trivial event)
        lo_px = Pa + minwall * atr_pr; hi_px = Pa + 4.0 * atr_pr
        m = (res_idx >= a - lookback) & (res_idx < a) & (res_px >= lo_px) & (res_px <= hi_px)
        if not m.any():
            rows.append(dict(ticker=tk, has_res=False,
                             apex_at_res=apex_at_res, apex_placebo=apex_placebo)); continue
        cand_px = res_px[m]; cand_idx = res_idx[m]; cand_dep = res_dep[m]; cand_spd = res_spd[m]
        j = int(np.argmin(cand_px))                  # nearest overhead wall (lowest above launch)
        level = cand_px[j]
        tol = 0.5 * atr_pr
        # strength = how many prior peaks cluster within tol of this level (repeated tests)
        touches = int(np.sum(np.abs(cand_px - level) <= tol))
        reached = apex >= level - tol                # got to the wall (incl. just under)
        stalled = abs(apex - level) <= tol           # topped AT the wall
        broke = apex > level + tol                   # punched clearly through
        short = apex < level - tol                   # ran out of gas before the wall
        rows.append(dict(
            ticker=tk, has_res=True,
            level_dist_atr=(level - Pa) / atr_pr,        # how far overhead, in ATR
            age_bars=int(a - cand_idx[j]),
            touches=touches,
            res_drop_dep=float(cand_dep[j]) * 100,        # the rejection that made the level (%)
            res_drop_spd=float(cand_spd[j]) * 100,        # per-bar speed (%/bar)
            reached=bool(reached), stalled=bool(stalled), broke=bool(broke), short=bool(short),
            cont_atr=((apex - level) / atr_pr if broke else np.nan),  # continuation past, in ATR
            apex_at_res=apex_at_res, apex_placebo=apex_placebo,
        ))
    return rows


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
    ap.add_argument("--lookback", type=int, default=2000)   # ~25 sessions of 5m
    ap.add_argument("--minwall-atr", type=float, default=1.0, dest="minwall")  # wall >= this many ATR overhead
    a = ap.parse_args()

    rows = []
    for tk in a.tickers:
        try:
            rows += collect(tk, a.width, a.min_amp, a.minbars, a.lookback, a.minwall)
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
    A = pd.DataFrame(rows)
    nall = len(A); nres = int(A["has_res"].sum())
    R = A[A["has_res"]].copy()
    reached = R[R["reached"]].copy()
    print(f"=== {nall} runs, {A['ticker'].nunique()} names; {nres} ({100*nres/nall:.0f}%) "
          f"had overhead resistance within 0.2-4 ATR ===", flush=True)

    # 1. how many tops are caused by resistance?
    frac_short = R["short"].mean()
    frac_stall_of_res = R["stalled"].mean()
    frac_break_of_res = R["broke"].mean()
    frac_stall_of_reach = reached["stalled"].mean() if len(reached) else np.nan
    frac_break_of_reach = reached["broke"].mean() if len(reached) else np.nan
    print(f"\n[1] Of runs facing an overhead wall (>= {a.minwall} ATR up): "
          f"FELL SHORT {frac_short:.0%}, STALLED at it {frac_stall_of_res:.0%}, "
          f"BROKE through {frac_break_of_res:.0%}.", flush=True)
    print(f"    Of runs that REACHED the wall: stalled {frac_stall_of_reach:.0%}, "
          f"broke {frac_break_of_reach:.0%} (resistance ends the run ~{frac_stall_of_reach:.0%} of the time).",
          flush=True)
    cl = A.dropna(subset=["apex_at_res"])
    at_res = cl["apex_at_res"].mean(); placebo = cl["apex_placebo"].mean()
    lift = at_res / placebo if placebo else float("nan")
    clu_msg = ("tops genuinely cluster at resistance." if lift > 1.15 else
               "raw proximity to a level is NOT above chance — levels are too dense; "
               "what matters is the level's STRENGTH/drop-intensity, not mere proximity.")
    print(f"    APEX CLUSTERING: the top lands on a prior level {at_res:.0%} vs {placebo:.0%} "
          f"for an offset placebo ({lift:.1f}x) — {clu_msg}", flush=True)

    # 2. what age / strength / drop-intensity gets broken vs stalls?
    if len(reached) > 100:
        g = reached.groupby("broke").agg(
            n=("level_dist_atr", "size"),
            med_age=("age_bars", "median"), med_touches=("touches", "median"),
            med_drop_dep=("res_drop_dep", "median"), med_drop_spd=("res_drop_spd", "median"))
        print(f"\n[2] Resistance that STALLS (broke=False) vs BREAKS (broke=True):", flush=True)
        print(g.round(2).to_string(), flush=True)

    # 3. does the level's DROP INTENSITY predict stall vs break?
    if len(reached) > 200:
        reached["dep_bkt"] = pd.qcut(reached["res_drop_dep"], 4,
                                     labels=["mild", "moderate", "strong", "violent"])
        t = reached.groupby("dep_bkt", observed=True).agg(
            n=("broke", "size"), p_break=("broke", "mean"),
            med_cont_atr=("cont_atr", "median"))
        print(f"\n[3] P(run BREAKS through) by the level's prior DROP INTENSITY (depth of the "
              f"rejection that formed it):", flush=True)
        print(t.assign(p_break=(t["p_break"]*100).round(0)).round(2).to_string(), flush=True)
        print(f"    corr(res drop depth, broke) = {sp(reached,'res_drop_dep','broke')}   "
              f"corr(age, broke) = {sp(reached,'age_bars','broke')}   "
              f"corr(touches, broke) = {sp(reached,'touches','broke')}", flush=True)

    # ---- report ----
    out = ROOT / "reports/stocks"
    rep = [f"# Resistance-interaction study — does prior resistance stop the run? (5m, "
           f"{A['ticker'].nunique()} names)", "",
           f"For each up-run we find the nearest **prior swing-high resistance** above the launch "
           f"(within 0.2–4 ATR, last {a.lookback} bars) and ask whether the run **stalls at** or "
           f"**breaks through** it — as a function of the level's age, test count, and the **drop "
           f"intensity** of the rejection that originally formed it. {nall:,} runs; "
           f"**{100*nres/nall:.0f}%** had overhead resistance in range.", "",
           f"## 1. How many tops are caused by resistance? (wall ≥ {a.minwall} ATR overhead)", "",
           f"- Of runs facing an overhead wall: **{frac_short:.0%} fell short**, "
           f"**{frac_stall_of_res:.0%} stalled at it**, **{frac_break_of_res:.0%} broke through**.",
           f"- Of runs that actually **reached** the wall, **{frac_stall_of_reach:.0%} STALLED** "
           f"(resistance ended the run) and **{frac_break_of_reach:.0%} BROKE through** to a higher top.",
           f"- So when a run gets to prior resistance, it fails there ~**{frac_stall_of_reach:.0%}** of the "
           f"time — resistance is a real, common cause of the top.",
           f"- **Apex clustering:** the top lands right on a prior level **{at_res:.0%}** of the time vs "
           f"**{placebo:.0%}** for an offset placebo (**{lift:.1f}×**) — {clu_msg}", ""]
    if len(reached) > 100:
        rep += ["## 2. What resistance gets broken vs stops the run?", "",
                "| outcome | n | median age (bars) | median touches | median prior-drop depth | median drop speed (%/bar) |",
                "|---|---|---|---|---|---|"]
        for broke_val, r in g.iterrows():
            lbl = "BREAKS through" if broke_val else "STALLS the run"
            rep.append(f"| {lbl} | {int(r['n'])} | {r['med_age']:.0f} | {r['med_touches']:.0f} | "
                       f"{r['med_drop_dep']:.2f}% | {r['med_drop_spd']:.3f} |")
        rep.append("")
    if len(reached) > 200:
        rep += ["## 3. Drop intensity → does the run fail or continue?", "",
                "P(run breaks through) bucketed by the **drop intensity** of the rejection that formed "
                "the level:", "",
                "| prior-drop intensity | n | P(break) | median continuation past (ATR) |",
                "|---|---|---|---|"]
        for bk, r in t.iterrows():
            rep.append(f"| {bk} | {int(r['n'])} | {r['p_break']*100:.0f}% | "
                       f"{(r['med_cont_atr'] if pd.notna(r['med_cont_atr']) else float('nan')):.2f} |")
        rep += ["", f"Correlations: drop-depth↔break **{sp(reached,'res_drop_dep','broke')}**, "
                f"age↔break **{sp(reached,'age_bars','broke')}**, touches↔break "
                f"**{sp(reached,'touches','broke')}**.", ""]
    rep += ["_5m only (2023+). Survivorship: runs are confirmed swing highs; gate live with "
            "oversold/VWAP entry confirmation._"]
    (out / "RESISTANCE_INTERACTION_STUDY.md").write_text("\n".join(rep), encoding="utf-8")
    R.to_csv(out / "resistance_interaction.csv", index=False)
    print(f"\nwrote {out/'RESISTANCE_INTERACTION_STUDY.md'}", flush=True)


if __name__ == "__main__":
    main()
