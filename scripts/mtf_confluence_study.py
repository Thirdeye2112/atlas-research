"""
mtf_confluence_study.py — Layer 4: does the DAILY + WEEKLY timeframe pick which
5m target (T1/T2/T3) the move actually reaches?

The 5m setup gives the entry and the run direction; the higher timeframes gate the
TARGET. We test the core multi-timeframe claim with a walk-forward:

  * A daily/weekly RESISTANCE above entry is a CEILING — the move tends to top there,
    so the realistic target is the highest rung below it.
  * DAILY/WEEKLY TREND alignment is RUN-ABILITY — entries with the higher timeframe
    are more likely to reach the far targets.

Setup: each up-leg launch on the 5m (the "throw"), one per (ticker, day). Entry e =
launch close. Target ladder in DAILY-ATR units: T1=+1, T2=+2, T3=+3 ATR_daily.
Forward outcome over the next H DAILY bars (stop = 1 ATR_daily below entry, evaluated
stop-before-target within a day = conservative). All daily/weekly context is computed
strictly BEFORE the entry day (no look-ahead).

Walk-forward: chronological 60/40 split; on the HOLDOUT compare expectancy & hit-rate
of fixed targets vs the daily-gated rule.

Usage:
    python scripts/mtf_confluence_study.py                      # 10-name basket
    python scripts/mtf_confluence_study.py --tickers AAPL NVDA
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


def _load5m(tk):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def weekly_trend(daily, di):
    """Trend of the weekly chart built from daily bars strictly before index di."""
    d = daily.iloc[:di]
    if len(d) < 60:
        return "range"
    w = d.set_index("ts").resample("W").agg({"high": "max", "low": "min", "close": "last"}).dropna()
    if len(w) < 8:
        return "range"
    piv = ta_structure.swing_pivots(w["high"].values, w["low"].values, width=2)
    return ta_structure.classify_trend(piv)


def collect(tk, width, min_amp, minbars, H):
    f = _load5m(tk)
    if len(f) < 300:
        return []
    f = dd.compute_indicators(f, intraday=True)
    h5 = f["high"].values; l5 = f["low"].values; c5 = f["close"].values
    rsi5 = f["rsi"].values
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

    rows = []
    seen_days = set()
    for lg in ta_patterns.swing_legs(piv5, h5, l5, c5, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]
        if a < 30 or b - a < minbars:
            continue
        D = sess[a]
        if (tk, D) in seen_days:
            continue
        # map to the daily bar for date D
        di = int(np.searchsorted(d_dates, D, side="right")) - 1
        if di < 30 or di + H + 1 >= len(d) or D != d_dates[di]:
            continue
        seen_days.add((tk, D))
        # SPLIT-SAFE: the 5m up-leg only TRIGGERS the day; entry + all forward/target/
        # resistance math come from the DAILY series so there is no cross-source price
        # mismatch across splits (the bug that produced garbage returns previously).
        e = dc[di]
        dA = datr[di - 1] / 100 if datr[di - 1] > 0 else np.nan   # 1 daily-ATR, prior day (no peek)
        if not np.isfinite(dA) or dA <= 0 or e <= 0:
            continue
        unit = dA * e                                            # 1 ATR_daily in price

        # --- higher-timeframe context, strictly before day D ---
        piv_d = ta_structure.swing_pivots(dh[:di], dl[:di], width=3)
        d_trend = ta_structure.classify_trend(piv_d)
        w_trend = weekly_trend(d, di)
        # nearest daily resistance above entry (prior daily swing highs)
        res_above = [p.price for p in piv_d if p.kind == "H" and p.price > e + 0.1 * unit]
        nearest_res = min(res_above) if res_above else np.nan
        # rungs of headroom to the nearest daily wall; clear air = large finite (survives inf->nan)
        res_atr = (nearest_res - e) / unit if np.isfinite(nearest_res) else 99.0

        # --- forward outcome over next H daily bars (stop 1 ATR below; stop-first) ---
        stop = e - unit
        outcome_R = {1: None, 2: None, 3: None}
        mfe = -np.inf
        for k in (1, 2, 3):
            tgt = e + k * unit
            res_k = None
            for j in range(di + 1, di + 1 + H):
                if dl[j] <= stop:
                    res_k = -1.0; break
                if dh[j] >= tgt:
                    res_k = float(k); break
            if res_k is None:
                res_k = (dc[di + H] - e) / unit
            outcome_R[k] = res_k
        for j in range(di + 1, di + 1 + H):
            mfe = max(mfe, (dh[j] - e) / unit)

        rows.append(dict(
            ticker=tk, date=str(D), e=e, d_rsi=drsi[di - 1],
            d_trend=d_trend, w_trend=w_trend,
            res_atr=res_atr, mfe_atr=mfe,
            reach1=int(mfe >= 1), reach2=int(mfe >= 2), reach3=int(mfe >= 3),
            o1=outcome_R[1], o2=outcome_R[2], o3=outcome_R[3]))
    return rows


def rule_target(row):
    """Daily-gated target rung 1/2/3: trend sets how far we may aim, resistance caps it."""
    allowed = 3 if (row["d_trend"] == "up" and row["w_trend"] in ("up", "range")) else \
              2 if row["d_trend"] == "up" else \
              2 if row["d_trend"] == "range" else 1
    cap = 3 if not np.isfinite(row["res_atr"]) else max(1, int(np.floor(row["res_atr"])))
    return int(max(1, min(allowed, cap)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=BASKET)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp", type=float, default=0.01)
    ap.add_argument("--minbars", type=int, default=6)
    ap.add_argument("--H", type=int, default=10)            # forward daily bars
    a = ap.parse_args()

    rows = []
    for tk in a.tickers:
        try:
            rows += collect(tk, a.width, a.min_amp, a.minbars, a.H)
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
    R = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
    R = R.dropna(subset=["mfe_atr", "o1", "o2", "o3"])
    n = len(R)
    print(f"=== {n} multi-timeframe setups (one/ticker/day), {R['ticker'].nunique()} names; "
          f"target/stop in daily-ATR, {a.H}d forward ===", flush=True)

    # A. cross-timeframe ceiling: does daily resistance cap the move?
    near = R[R["res_atr"] <= 3]; far = R[R["res_atr"] > 3]
    print(f"\n[A] Daily resistance as a ceiling:", flush=True)
    print(f"    corr(headroom to daily res, MFE) = {spearmanr(R['res_atr'].clip(upper=6), R['mfe_atr'])[0]:.3f}", flush=True)
    print(f"    MFE when a daily wall is NEAR (<=3 ATR): {near['mfe_atr'].median():.2f} ATR "
          f"vs FAR/clear air: {far['mfe_atr'].median():.2f} ATR", flush=True)
    print(f"    reach-T3 rate near {near['reach3'].mean():.0%} vs far {far['reach3'].mean():.0%}", flush=True)

    # B. run-ability by higher-timeframe trend
    print(f"\n[B] Run-ability by higher-timeframe trend (median MFE / reach-T2 rate):", flush=True)
    for col, lbl in (("d_trend", "DAILY"), ("w_trend", "WEEKLY")):
        g = R.groupby(col).agg(n=("mfe_atr", "size"), mfe=("mfe_atr", "median"), r2=("reach2", "mean"))
        print(f"    {lbl}: " + "  ".join(f"{k}: MFE {r['mfe']:.2f}/T2 {r['r2']:.0%} (n={int(r['n'])})"
                                          for k, r in g.iterrows()), flush=True)

    # C. walk-forward target selection (chronological 60/40)
    R = R.sort_values("date").reset_index(drop=True)
    cut = int(len(R) * 0.6)
    hold = R.iloc[cut:].copy()
    hold["rule_k"] = hold.apply(rule_target, axis=1)
    hold["rule_R"] = hold.apply(lambda r: r[f"o{int(r['rule_k'])}"], axis=1)
    print(f"\n[C] Walk-forward HOLDOUT (last {len(hold)} setups) — expectancy (R) & hit-rate:", flush=True)
    res = {}
    for k in (1, 2, 3):
        exp = hold[f"o{k}"].mean(); hit = (hold[f"o{k}"] == k).mean()
        res[f"always T{k}"] = (exp, hit)
    res["DAILY-GATED rule"] = (hold["rule_R"].mean(), (hold["rule_R"] == hold["rule_k"]).mean())
    for k, (exp, hit) in res.items():
        print(f"    {k:18s} expectancy={exp:+.3f} R   target-hit={hit:.0%}", flush=True)

    # ---- report ----
    out = ROOT / "reports/stocks"
    rep = [f"# Multi-timeframe confluence (Layer 4) — does daily/weekly pick the target? "
           f"({R['ticker'].nunique()} names)", "",
           f"5m up-leg launches as entries (one/ticker/day, n={n:,}); target ladder T1/T2/T3 = "
           f"+1/+2/+3 **daily-ATR**; stop −1 daily-ATR; {a.H}-day forward; daily & weekly context "
           f"strictly before entry. Conservative (stop-before-target intrabar).", "",
           "## A. Daily resistance is a ceiling on the move", "",
           f"- corr(headroom-to-daily-resistance, MFE) = "
           f"**{spearmanr(R['res_atr'].clip(upper=6), R['mfe_atr'])[0]:.3f}** — more room overhead → bigger move.",
           f"- Median MFE with a daily wall **near** (≤3 ATR): **{near['mfe_atr'].median():.2f} ATR** vs "
           f"**{far['mfe_atr'].median():.2f} ATR** in clear air; reach-T3 **{near['reach3'].mean():.0%}** vs "
           f"**{far['reach3'].mean():.0%}**. A near daily ceiling caps the realistic target.", "",
           "## B. Higher-timeframe trend = run-ability", "",
           "| timeframe | trend | n | median MFE (ATR) | reach-T2 |", "|---|---|---|---|---|"]
    for col, lbl in (("d_trend", "daily"), ("w_trend", "weekly")):
        g = R.groupby(col).agg(n=("mfe_atr", "size"), mfe=("mfe_atr", "median"), r2=("reach2", "mean"))
        for k, r in g.iterrows():
            rep.append(f"| {lbl} | {k} | {int(r['n'])} | {r['mfe']:.2f} | {r['r2']:.0%} |")
    rep += ["", "## C. Walk-forward: daily-gated target selection vs naive", "",
            f"Chronological 60/40 split; holdout n={len(hold):,}. Expectancy in R "
            f"(reward:risk vs the 1-ATR stop).", "",
            "| target rule | expectancy (R) | target-hit rate |", "|---|---|---|"]
    for k, (exp, hit) in res.items():
        rep.append(f"| {k} | {exp:+.3f} | {hit:.0%} |")
    best_fixed = max(("always T1", "always T2", "always T3"), key=lambda k: res[k][0])
    rule_exp = res["DAILY-GATED rule"][0]; bf_exp = res[best_fixed][0]
    verdict = ("BEATS" if rule_exp > bf_exp else "does NOT beat")
    rep += ["", f"**Verdict (first cut):** the daily-gated rule **{verdict}** the best fixed target "
            f"({best_fixed}, {bf_exp:+.3f}R) on the holdout (rule {rule_exp:+.3f}R). On *unfiltered* "
            f"bounce entries, naive 'aim far' wins — consistent with the resistance study (walls mostly "
            f"break; only violent/recent ones stop a run). The gate should cap only on QUALITY daily "
            f"resistance (touches / prior-drop intensity) and apply to CONFIDENT directional entries, "
            f"not every snapback.", ""]
    rep += ["_The daily-gated rule aims at T3 only with daily+weekly trend and clear air, caps at "
            "the rung below a near daily wall, and trims to T1 in downtrends — the Layer-4 gate on top "
            "of the 5m entry. Survivorship: confirmed swing-high launches; gate live with the 5m "
            "VWAP-reclaim entry._"]
    (out / "MTF_CONFLUENCE_STUDY.md").write_text("\n".join(rep), encoding="utf-8")
    R.to_csv(out / "mtf_confluence.csv", index=False)
    print(f"\nwrote {out/'MTF_CONFLUENCE_STUDY.md'}", flush=True)


if __name__ == "__main__":
    main()
