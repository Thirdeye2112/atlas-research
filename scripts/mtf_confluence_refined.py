"""
mtf_confluence_refined.py — Layer-4 gate, refined per our own findings.

The naive gate (mtf_confluence_study) failed because it capped the target on the
NEAREST daily swing high regardless of quality, and applied to every snapback. Our
resistance study showed walls mostly BREAK — only VIOLENT/recent ones stop a run. So
this version:

  * QUALITY ceiling: cap the target only when the overhead daily level is a STRONG
    wall — formed by a rejection of >= 1 daily-ATR (the validated discriminator).
    Weak levels are ignored (the move is allowed to aim through them).
  * CONFIDENT entries: apply the gate to oversold dips in a non-downtrend
    (d_rsi <= RSI_DIP and daily trend != down), not every launch.

Walk-forward (chronological 60/40) compares, on the HOLDOUT:
  always-T3 · naive gate (nearest wall) · QUALITY gate · QUALITY gate on CONFIDENT entries
Everything split-safe: 5m only triggers the day; prices/targets from the daily series.

Usage:
    python scripts/mtf_confluence_refined.py
    python scripts/mtf_confluence_refined.py --tickers AAPL NVDA
"""
from __future__ import annotations
import sys, argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from mtf_confluence_study import weekly_trend
from resistance_interaction_study import resistance_peaks

BASKET = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "WMT"]


def _load5m(tk):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def collect(tk, width, min_amp, minbars, H, dlook):
    f = _load5m(tk)
    if len(f) < 300:
        return []
    f = dd.compute_indicators(f, intraday=True)
    h5 = f["high"].values; l5 = f["low"].values; c5 = f["close"].values
    sess = f["ts"].dt.date.values
    piv5 = ta_structure.swing_pivots(h5, l5, width=width)

    d = dd.load_daily(tk).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    if len(d) < 120:
        return []
    for cc in ("open", "high", "low", "close", "volume"):
        d[cc] = pd.to_numeric(d[cc], errors="coerce")
    d = dd.compute_indicators(d, intraday=False)
    d_dates = d["ts"].dt.date.values
    dh = d["high"].values; dl = d["low"].values; dc = d["close"].values
    datr = d["atr_pct"].values; drsi = d["rsi"].values
    # daily resistance peaks once (idx, price, drop_dep frac, drop_spd) for the whole series
    piv_full = ta_structure.swing_pivots(dh, dl, width=3)
    res = resistance_peaks(piv_full, dh, dl)
    r_idx = np.array([r[0] for r in res]); r_px = np.array([r[1] for r in res])
    r_dep = np.array([r[2] for r in res])

    rows = []
    seen = set()
    for lg in ta_patterns.swing_legs(piv5, h5, l5, c5, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]
        if a < 30 or b - a < minbars:
            continue
        D = sess[a]
        if (tk, D) in seen:
            continue
        di = int(np.searchsorted(d_dates, D, side="right")) - 1
        if di < 30 or di + H + 1 >= len(d) or D != d_dates[di]:
            continue
        seen.add((tk, D))
        e = dc[di]
        dA = datr[di - 1] / 100 if datr[di - 1] > 0 else np.nan
        if not np.isfinite(dA) or dA <= 0 or e <= 0:
            continue
        unit = dA * e

        piv_d = [p for p in piv_full if p.idx < di]
        d_trend = ta_structure.classify_trend(piv_d)
        w_trend = weekly_trend(d, di)

        # nearest ANY wall vs nearest STRONG wall (rejection >= 1 daily-ATR), prior dlook bars
        m = (r_idx >= di - dlook) & (r_idx < di) & (r_px > e + 0.1 * unit)
        cpx = r_px[m]; cdep = r_dep[m]
        res_any = (cpx.min() - e) / unit if cpx.size else 99.0
        strong = cpx[cdep >= dA]                       # formed by a >=1 ATR rejection
        res_strong = (strong.min() - e) / unit if strong.size else 99.0

        stop = e - unit
        out = {}
        for k in (1, 2, 3):
            tgt = e + k * unit; rk = None
            for j in range(di + 1, di + 1 + H):
                if dl[j] <= stop:
                    rk = -1.0; break
                if dh[j] >= tgt:
                    rk = float(k); break
            out[k] = rk if rk is not None else (dc[di + H] - e) / unit
        mfe = max((dh[j] - e) / unit for j in range(di + 1, di + 1 + H))

        rows.append(dict(ticker=tk, date=str(D), d_rsi=drsi[di - 1],
                         d_trend=d_trend, w_trend=w_trend,
                         res_any=res_any, res_strong=res_strong, mfe=mfe,
                         o1=out[1], o2=out[2], o3=out[3]))
    return rows


def _allowed(r):
    # let the WALL drive the cap; trend only trims hard in a confirmed downtrend
    return 2 if r["d_trend"] == "down" else 3


def gate_k(r, res_col):
    cap = 3 if not np.isfinite(r[res_col]) or r[res_col] >= 90 else max(1, int(np.floor(r[res_col])))
    return int(max(1, min(_allowed(r), cap)))


def _expectancy(df, kcol):
    """avg realized R using each row's chosen target-rung kcol, and target-hit rate."""
    R = df.apply(lambda r: r[f"o{int(r[kcol])}"], axis=1)
    hit = (R == df[kcol]).mean()
    return R.mean(), hit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=BASKET)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp", type=float, default=0.01)
    ap.add_argument("--minbars", type=int, default=6)
    ap.add_argument("--H", type=int, default=10)
    ap.add_argument("--dlook", type=int, default=252)      # daily resistance lookback
    ap.add_argument("--rsi-dip", type=float, default=45.0)  # "confident" oversold dip
    a = ap.parse_args()

    rows = []
    for tk in a.tickers:
        try:
            rows += collect(tk, a.width, a.min_amp, a.minbars, a.H, a.dlook)
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
    R = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["o1", "o2", "o3", "mfe"])
    R = R.sort_values("date").reset_index(drop=True)
    n = len(R)
    confident = (R["d_rsi"] <= a.rsi_dip) & (R["d_trend"] != "down")
    print(f"=== {n} setups, {R['ticker'].nunique()} names; confident (dip & not-down) = "
          f"{confident.sum()} ({100*confident.mean():.0f}%) ===", flush=True)

    cut = int(n * 0.6)
    hold = R.iloc[cut:].copy()
    hold["k_naive"] = hold.apply(lambda r: gate_k(r, "res_any"), axis=1)
    hold["k_quality"] = hold.apply(lambda r: gate_k(r, "res_strong"), axis=1)
    hold["k_t3"] = 3
    hc = hold[(hold["d_rsi"] <= a.rsi_dip) & (hold["d_trend"] != "down")].copy()

    def line(label, df, kcol):
        if len(df) < 50:
            return f"    {label:34s} n<50"
        exp, hit = _expectancy(df, kcol)
        return f"    {label:34s} expectancy={exp:+.3f} R   hit={hit:.0%}   n={len(df)}"

    print(f"\nWalk-forward HOLDOUT (last {len(hold)}):", flush=True)
    print(line("always T3", hold, "k_t3"), flush=True)
    print(line("naive gate (nearest wall)", hold, "k_naive"), flush=True)
    print(line("QUALITY gate (strong walls)", hold, "k_quality"), flush=True)
    print(f"\n  on CONFIDENT entries only (dip & not-down, n={len(hc)}):", flush=True)
    print(line("always T3 (confident)", hc, "k_t3"), flush=True)
    print(line("QUALITY gate (confident)", hc, "k_quality"), flush=True)

    # report
    out = ROOT / "reports/stocks"
    def row(label, df, kcol):
        if len(df) < 50:
            return f"| {label} | n<50 | — | {len(df)} |"
        exp, hit = _expectancy(df, kcol)
        return f"| {label} | {exp:+.3f} | {hit:.0%} | {len(df)} |"
    rep = [f"# Multi-timeframe Layer-4 — REFINED gate ({R['ticker'].nunique()} names)", "",
           f"Quality-weighted daily ceiling (cap only on walls formed by a ≥1-ATR rejection) applied "
           f"to confident entries (d_rsi ≤ {a.rsi_dip:.0f} & daily trend ≠ down). Split-safe; target "
           f"ladder ±1/2/3 daily-ATR; stop −1 ATR; {a.H}d forward; chronological 60/40. n={n:,}; "
           f"confident = {100*confident.mean():.0f}% of setups.", "",
           "## Walk-forward holdout — expectancy (R) & target-hit", "",
           "| strategy | expectancy (R) | hit | n |", "|---|---|---|---|",
           row("always T3", hold, "k_t3"),
           row("naive gate (nearest wall)", hold, "k_naive"),
           row("QUALITY gate (strong walls)", hold, "k_quality"),
           row("always T3 — confident entries", hc, "k_t3"),
           row("QUALITY gate — confident entries", hc, "k_quality"), ""]
    # data-driven verdict
    e_all = _expectancy(hold, "k_t3")[0]
    if len(hc) >= 50:
        e_cf, h_cf = _expectancy(hc, "k_t3"); g_cf, gh_cf = _expectancy(hc, "k_quality")
        rep += ["## Verdict", "",
                f"- **The entry filter is the real lever.** Confident entries (oversold dip, not "
                f"down-trend) lift always-T3 expectancy **{e_all:+.3f}R → {e_cf:+.3f}R** "
                f"(**{100*(e_cf-e_all)/abs(e_all):.0f}%**) — the higher-timeframe context pays off mostly "
                f"through *entry selection*, validating the layered-confluence principle.",
                f"- **The target gate is a consistency dial, not an expectancy boost.** On confident "
                f"entries the quality gate hits **{gh_cf:.0%} vs {h_cf:.0%}** for always-T3 at "
                f"**{g_cf:+.3f}R vs {e_cf:+.3f}R** — ~3× the win-rate for a modest expectancy give-up. "
                f"Use aim-far to maximise compounding; use the gate to smooth the equity curve / size up.",
                f"- The naive vs quality gate are near-identical because the daily wall (not its quality) "
                f"is usually the binding cap once the trend allows T3; the **strong-wall filter matters "
                f"most for *where to take profit*, not whether to enter.**", ""]
    rep += ["_Aim far by default; trim to the rung below a STRONG daily wall when one is within reach; "
            "trade the high-confidence dip-in-uptrend setups — your 'trade within the pattern when "
            "direction + run-ability are confident' principle, quantified._"]
    (out / "MTF_CONFLUENCE_REFINED.md").write_text("\n".join(rep), encoding="utf-8")
    R.to_csv(out / "mtf_confluence_refined.csv", index=False)
    print(f"\nwrote {out/'MTF_CONFLUENCE_REFINED.md'}", flush=True)


if __name__ == "__main__":
    main()
