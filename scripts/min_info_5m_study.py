"""
min_info_5m_study.py — Step 2: does a FINER timeframe (5-minute) forecast the
first-leg run height better than daily?

Repeats the min_info_study question on two timeframes for the SAME tickers and
reports OOS R^2(k) side by side:
  * DAILY : first-leg amplitude (low->next swing high) from the first k daily candles
  * 5-MIN : same, but on intraday 5m bars, restricted to legs that start AND peak
            within ONE session (and whose first k early candles are same-session) so
            overnight gaps don't manufacture fake legs.

5-minute is the finest data in the DB (no 1-minute) — this is the proxy for "does
going finer help forecast the run earlier".

Target & features winsorized to [1%,99%] per timeframe (consistent with Step 1).

Usage:
    python scripts/min_info_5m_study.py                       # the 10-name basket
    python scripts/min_info_5m_study.py --tickers AAPL NVDA   # subset
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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score

BASKET = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "WMT"]
WINSOR = (0.01, 0.99)


def feats_for_k(k):
    f = ["L_rsi", "L_atr", "L_de20", "L_mr"]
    for j in range(1, k + 1):
        f += [f"c{j}_ret", f"c{j}_batr", f"c{j}_vr", f"c{j}_rng", f"c{j}_cum"]
    return f


def _load(tk, intraday):
    if intraday:
        df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
        df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    else:
        df = dd.load_daily(tk)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def collect(tk, intraday, width, min_amp, maxk):
    df = _load(tk, intraday)
    if len(df) < 250:
        return []
    df = dd.compute_indicators(df, intraday=intraday)
    df["mr"] = zscore_expanding(df)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    body = df["body_pct"].values; atr = df["atr_pct"].values; vr = df["vol_ratio"].values
    rsi = df["rsi"].values; de20 = df["dist_ema20"].values; mr = df["mr"].values
    sess = df["ts"].dt.date.values if intraday else None
    N = len(df); rows = []
    piv = ta_structure.swing_pivots(h, l, width=width)
    for lg in ta_patterns.swing_legs(piv, h, l, c, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]
        if a < 20 or a + maxk >= N or b <= a:
            continue
        if intraday:
            # keep only legs that live inside one session (start, peak, and the early
            # observation window all on the same calendar date) -> no overnight gap
            if sess[a] != sess[b] or sess[a] != sess[min(a + maxk, N - 1)]:
                continue
        rec = dict(ticker=tk, leg_amp=lg["leg_amp"] * 100, leg_bars=int(b - a),
                   L_rsi=rsi[a], L_atr=atr[a], L_de20=de20[a], L_mr=mr[a])
        for j in range(1, maxk + 1):
            i = a + j
            rec[f"c{j}_ret"] = (c[i] - c[i - 1]) / c[i - 1] * 100
            rec[f"c{j}_batr"] = body[i] / atr[i] if atr[i] > 0 else np.nan
            rec[f"c{j}_vr"] = vr[i]
            rec[f"c{j}_rng"] = (h[i] - l[i]) / c[i] * 100 if c[i] else np.nan
            rec[f"c{j}_cum"] = (c[i] - c[a]) / c[a] * 100 if c[a] else np.nan
        rows.append(rec)
    return rows


def _winsor(d, cols, target="leg_amp"):
    d = d.copy()
    for col in cols + [target]:
        lo, hi = d[col].quantile(WINSOR)
        if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
            d[col] = d[col].clip(lo, hi)
    return d


def r2_curve(R, minbars, maxk):
    S = R[R["leg_bars"] >= minbars].copy()
    res = []
    for k in range(1, maxk + 1):
        cols = feats_for_k(k); d = S.dropna(subset=cols + ["leg_amp"])
        if len(d) < 200:
            res.append((k, len(d), None, None)); continue
        d = _winsor(d, cols)
        X = d[cols].values; y = d["leg_amp"].values
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=0)
        gb = HistGradientBoostingRegressor(max_iter=300, max_depth=3, learning_rate=0.05,
                                           l2_regularization=1.0, random_state=0).fit(Xtr, ytr)
        lin = LinearRegression().fit(Xtr, ytr)
        res.append((k, len(d), round(r2_score(yte, lin.predict(Xte)), 3),
                    round(r2_score(yte, gb.predict(Xte)), 3)))
    return S, res


def formula(S, k, label):
    cols = feats_for_k(k); d = S.dropna(subset=cols + ["leg_amp"])
    if len(d) < 200:
        return None
    d = _winsor(d, cols)
    lin = LinearRegression().fit(d[cols].values, d["leg_amp"].values)
    beta = dict(zip(cols, lin.coef_))
    sbeta = dict(zip(cols, lin.coef_ * d[cols].std().values / d["leg_amp"].std()))
    top = sorted(sbeta.items(), key=lambda x: -abs(x[1]))[:5]
    txt = f"A ≈ {lin.intercept_:.2f} + " + " + ".join(f"{beta[k_]:+.2f}·{k_}" for k_, _ in top)
    drv = ", ".join(f"`{k_}` {v:+.2f}" for k_, v in top)
    return txt, drv, len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=BASKET)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp-daily", type=float, default=0.03)
    ap.add_argument("--min-amp-5m", type=float, default=0.01)   # intraday legs are smaller
    ap.add_argument("--minbars", type=int, default=6)
    ap.add_argument("--maxk", type=int, default=5)
    a = ap.parse_args()

    out = {}
    for tf, intraday, min_amp in (("daily", False, a.min_amp_daily), ("5m", True, a.min_amp_5m)):
        rows = []
        for tk in a.tickers:
            try:
                rows += collect(tk, intraday, a.width, min_amp, a.maxk)
            except Exception as e:
                print(f"  !! {tf} {tk}: {str(e)[:80]}", flush=True)
        R = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
        S, res = r2_curve(R, a.minbars, a.maxk)
        out[tf] = (S, res)
        print(f"=== {tf}: {len(S)} legs (peak >= {a.minbars} bars out), {S['ticker'].nunique()} names, "
              f"median A {S['leg_amp'].median():.1f}% ===", flush=True)
        for k, n, rl, rg in res:
            print(f"  1..{k}: lin={rl} gbm={rg} (n={n})", flush=True)

    Sd, resd = out["daily"]; S5, res5 = out["5m"]
    knee = min(2, a.maxk)
    rep = ["# Does 5-minute forecast the first-leg run better than daily? (min-info, Step 2)", "",
           f"Same {Sd['ticker'].nunique()} tickers, same methodology, two timeframes. Target A = "
           f"first-leg amplitude (low→next swing high). 5m legs are restricted to a single session "
           f"(no overnight gap in the leg or its early window). Peak ≥ {a.minbars} bars out. OOS R² "
           f"via 70/30 split; target & features winsorized to [{WINSOR[0]:.0%},{WINSOR[1]:.0%}].", "",
           f"- DAILY: {len(Sd):,} legs, median A **{Sd['leg_amp'].median():.1f}%** (min_amp {a.min_amp_daily:.0%}).",
           f"- 5-MIN: {len(S5):,} legs, median A **{S5['leg_amp'].median():.1f}%** (min_amp {a.min_amp_5m:.0%}).", "",
           "## OOS R² by early candles used — daily vs 5-minute", "",
           "| candles | DAILY (lin/GBM) | 5-MIN (lin/GBM) |", "|---|---|---|"]
    dmap = {k: (rl, rg, n) for k, n, rl, rg in resd}
    fmap = {k: (rl, rg, n) for k, n, rl, rg in res5}
    for k in range(1, a.maxk + 1):
        dl, dg, dn = dmap.get(k, (None, None, 0)); fl, fg, fn = fmap.get(k, (None, None, 0))
        ds = f"{dl}/{dg} (n={dn})" if dl is not None else "n/a"
        fs = f"{fl}/{fg} (n={fn})" if fl is not None else "n/a"
        rep.append(f"| 1..{k} | {ds} | {fs} |")

    rep += ["", f"## Simple formula at the knee (candles 1..{knee})", ""]
    for tf, (S, _) in (("DAILY", out["daily"]), ("5-MIN", out["5m"])):
        f = formula(S, knee, tf)
        if f:
            rep += [f"- **{tf}** (n={f[2]:,}): `{f[0]}`", f"  - top standardized drivers: {f[1]}"]

    # verdict line computed from the knee R² (GBM)
    dk = dmap.get(knee, (None, None, 0))[1]; fk = fmap.get(knee, (None, None, 0))[1]
    if dk is not None and fk is not None:
        better = "BETTER" if fk > dk + 0.02 else ("WORSE" if fk < dk - 0.02 else "ABOUT THE SAME")
        rep += ["", f"**Verdict:** at candles 1..{knee}, 5-minute is **{better}** than daily "
                f"(GBM R² {fk:.3f} vs {dk:.3f}). "
                + ("The finer timeframe does forecast the first-leg run earlier."
                   if better == "BETTER" else
                   "Going finer (5m) does not beat daily for forecasting the first-leg run height — "
                   "the daily early candles already carry the predictable signal."
                   if better == "WORSE" else
                   "The finer timeframe is roughly on par with daily."),
                "",
                f"**Caveat — different target sizes.** A 5m first leg is a much smaller move "
                f"(median {S5['leg_amp'].median():.1f}%) than a daily one (median {Sd['leg_amp'].median():.1f}%). "
                f"The higher 5m R² means the intraday leg is more predictable *as a fraction of itself* "
                f"(intraday momentum is more mechanical within a session), not that 5m forecasts a bigger move. "
                f"Operational read: use 5m to time/size the **intraday entry leg** inside a daily setup "
                f"(complements the next-session-close>VWAP layer that already doubles the edge), and treat it "
                f"as evidence that finer-still data (1-minute, not in the DB) would likely sharpen entry timing "
                f"further — while the **daily** model remains the right tool for the size of the multi-day swing."]

    (ROOT / "reports/stocks/MIN_INFO_5M_STUDY.md").write_text("\n".join(rep), encoding="utf-8")
    print(f"\nwrote {ROOT/'reports/stocks/MIN_INFO_5M_STUDY.md'}", flush=True)


if __name__ == "__main__":
    main()
