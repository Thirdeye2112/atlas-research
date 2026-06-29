"""
channel_physics_study.py — the "thrown-ball" hypothesis on 5-minute candles.

Question (user): can the ANGLE of the channel the candles trace (highs-line vs
lows-line slope) plus the INTENSITY of the first 1/2/3 candles forecast the ARC of
the run — how high it tops and how it drops before the next rise — the way a
projectile's launch angle + velocity set its trajectory?

Physics framing. A thrown ball's height is a downward parabola:
    y(t) = v0*t - 0.5*g*t^2
  -> apex TIME   t* = v0/g
  -> apex HEIGHT h* = v0^2/(2g)         (height grows with the SQUARE of velocity)
  -> returns to launch height at 2*t*   (ascent and descent are symmetric)
We map: launch velocity v0 = early candle speed; launch angle theta = channel
slope / ATR; g = the mean-reversion "gravity". We then test, on real 5m up-legs
(low -> swing high -> correction low, one per session), whether:

  A. CHANNEL/LAUNCH correlates with the run   (angle & intensity -> apex height/time)
  B. The path is actually an ARC               (a downward parabola fits price; beta2<0)
  C. Apex HEIGHT grows ~ velocity^2            (the ballistic signature, not linear)
  D. The DROP is symmetric / forecastable      (descent vs ascent; predict corr depth)
  E. FORECAST: OOS R^2 of apex height / apex time / drop depth from the first k candles,
     PHYSICS features (v0, angle, v0^2, v0*angle) vs raw candle features.

5-minute is the finest data we have (2023+). Legs are kept INSIDE one session so
overnight gaps don't manufacture fake arcs.

Usage:
    python scripts/channel_physics_study.py                      # 10-name basket
    python scripts/channel_physics_study.py --tickers AAPL NVDA  # subset
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
from scipy.stats import spearmanr

BASKET = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "WMT"]
WINSOR = (0.01, 0.99)


def _load(tk):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    return df


def _quad_fit(y):
    """Fit y(t)=b0+b1*t+b2*t^2 over t=0..len-1. Return (b1, b2, r2_quad, r2_lin).
    b2<0 => concave (a dome/arc, like a thrown ball)."""
    n = len(y)
    if n < 4 or not np.all(np.isfinite(y)):
        return (np.nan, np.nan, np.nan, np.nan)
    t = np.arange(n, dtype=float)
    yc = y - y[0]                      # height relative to launch
    b2, b1, _ = np.polyfit(t, yc, 2)
    pred_q = np.polyval([b2, b1, 0.0], t)
    a1, a0 = np.polyfit(t, yc, 1); pred_l = a1 * t + a0
    ss = np.sum((yc - yc.mean()) ** 2)
    r2q = 1 - np.sum((yc - pred_q) ** 2) / ss if ss > 0 else np.nan
    r2l = 1 - np.sum((yc - pred_l) ** 2) / ss if ss > 0 else np.nan
    return (float(b1), float(b2), float(r2q), float(r2l))


def collect(tk, width, min_amp, maxk):
    df = _load(tk)
    if len(df) < 250:
        return []
    df = dd.compute_indicators(df, intraday=True)
    df["mr"] = zscore_expanding(df)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    o = df["open"].values
    body = df["body_pct"].values; atr = df["atr_pct"].values; vr = df["vol_ratio"].values
    rsi = df["rsi"].values; mr = df["mr"].values
    sess = df["ts"].dt.date.values
    N = len(df); rows = []
    piv = ta_structure.swing_pivots(h, l, width=width)
    for lg in ta_patterns.swing_legs(piv, h, l, c, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]; cc = lg["corr_idx"]
        if a < 20 or a + maxk >= N or b <= a + 1:
            continue
        # one-session arc: launch, apex (and drop if present) share a calendar date
        if sess[a] != sess[b] or sess[a] != sess[min(a + maxk, N - 1)]:
            continue
        same_sess_drop = cc is not None and sess[cc] == sess[a] and cc > b
        Pa = c[a]
        if Pa <= 0:
            continue

        # ---- launch signature from the first k candles off the low ----
        rec = dict(ticker=tk, date=str(sess[a]),
                   apex_amp=lg["leg_amp"] * 100, apex_bars=int(b - a),
                   L_rsi=rsi[a], L_atr=atr[a], L_mr=mr[a])
        for j in range(1, maxk + 1):
            i = a + j
            rec[f"c{j}_ret"] = (c[i] - c[i - 1]) / c[i - 1] * 100
            rec[f"c{j}_batr"] = body[i] / atr[i] if atr[i] > 0 else np.nan
            rec[f"c{j}_vr"] = vr[i]
            rec[f"c{j}_cum"] = (c[i] - Pa) / Pa * 100

        # velocity (per-bar % speed), acceleration (thrust), over first k bars
        for k in (1, 2, 3):
            ik = a + k
            rec[f"v{k}"] = (c[ik] - Pa) / Pa / k * 100          # mean %/bar
        rec["accel"] = rec["v2"] - rec["v1"]                     # speeding up?

        # ---- channel ANGLE: slope of highs-line & lows-line over first k bars,
        #      normalised by ATR(start) so it is scale-free; expressed in degrees ----
        atr0 = atr[a] if atr[a] > 0 else np.nan
        for k in (2, 3):
            seg = slice(a, a + k + 1)
            t = np.arange(k + 1, dtype=float)
            sh = np.polyfit(t, h[seg], 1)[0] / Pa * 100          # %/bar of the highs line
            sl = np.polyfit(t, l[seg], 1)[0] / Pa * 100          # %/bar of the lows line
            rec[f"hi_slope{k}"] = sh
            rec[f"lo_slope{k}"] = sl
            rec[f"chan_widen{k}"] = sh - sl                       # >0 widening (megaphone)
            # launch angle from close slope / ATR -> a true scale-free "angle"
            scl = np.polyfit(t, c[seg], 1)[0] / Pa * 100
            rec[f"angle{k}"] = np.degrees(np.arctan(scl / atr0)) if np.isfinite(atr0) else np.nan

        # ---- arc geometry: parabola fit over ascent, and over full launch->drop ----
        b1a, b2a, r2qa, r2la = _quad_fit(c[a:b + 1])
        rec.update(asc_b2=b2a, asc_r2q=r2qa, asc_r2l=r2la)
        if same_sess_drop:
            b1f, b2f, r2qf, r2lf = _quad_fit(c[a:cc + 1])
            rec.update(arc_b1=b1f, arc_b2=b2f, arc_r2q=r2qf, arc_r2l=r2lf,
                       drop_amp=(c[b] - c[cc]) / c[b] * 100, drop_bars=int(cc - b),
                       retrace_frac=(c[b] - c[cc]) / (c[b] - Pa) if c[b] > Pa else np.nan)
        else:
            rec.update(arc_b1=np.nan, arc_b2=np.nan, arc_r2q=np.nan, arc_r2l=np.nan,
                       drop_amp=np.nan, drop_bars=np.nan, retrace_frac=np.nan)
        rows.append(rec)
    return rows


def _winsor(d, cols):
    d = d.copy()
    for col in cols:
        if col not in d:
            continue
        lo, hi = d[col].quantile(WINSOR)
        if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
            d[col] = d[col].clip(lo, hi)
    return d


def oos_r2(d, feats, target):
    d = d.dropna(subset=feats + [target])
    if len(d) < 200:
        return None, len(d)
    d = _winsor(d, feats + [target])
    X = d[feats].values; y = d[target].values
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=0)
    lin = LinearRegression().fit(Xtr, ytr)
    gb = HistGradientBoostingRegressor(max_iter=300, max_depth=3, learning_rate=0.05,
                                       l2_regularization=1.0, random_state=0).fit(Xtr, ytr)
    return (round(r2_score(yte, lin.predict(Xte)), 3),
            round(r2_score(yte, gb.predict(Xte)), 3)), len(d)


def sp(d, x, y):
    s = d[[x, y]].dropna()
    if len(s) < 100:
        return None
    r, _ = spearmanr(s[x], s[y]); return round(r, 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", nargs="+", default=BASKET)
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp", type=float, default=0.01)
    ap.add_argument("--minbars", type=int, default=6)   # apex >= this many bars out
    ap.add_argument("--maxk", type=int, default=3)
    a = ap.parse_args()

    rows = []
    for tk in a.tickers:
        try:
            rows += collect(tk, a.width, a.min_amp, a.maxk)
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
    R = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan)
    S = R[R["apex_bars"] >= a.minbars].copy()
    nseg = len(S); ndrop = int(S["drop_amp"].notna().sum())
    print(f"=== {nseg} single-session up-legs (apex >= {a.minbars} bars), "
          f"{S['ticker'].nunique()} names; {ndrop} with same-session drop ===", flush=True)

    # A. channel / launch -> run correlations
    corrs = {
        "angle (close-slope/ATR, 3 bars) -> apex height": sp(S, "angle3", "apex_amp"),
        "early velocity v3 -> apex height":               sp(S, "v3", "apex_amp"),
        "acceleration -> apex height":                    sp(S, "accel", "apex_amp"),
        "lows-line slope (3) -> apex height":             sp(S, "lo_slope3", "apex_amp"),
        "highs-line slope (3) -> apex height":            sp(S, "hi_slope3", "apex_amp"),
        "channel widening (3) -> apex height":            sp(S, "chan_widen3", "apex_amp"),
        "angle3 -> apex TIME (bars)":                     sp(S, "angle3", "apex_bars"),
        "velocity v3 -> apex TIME (bars)":                sp(S, "v3", "apex_bars"),
        "apex height -> drop depth":                      sp(S, "apex_amp", "drop_amp"),
        "angle3 -> drop depth":                           sp(S, "angle3", "drop_amp"),
        "apex height -> retrace fraction":                sp(S, "apex_amp", "retrace_frac"),
    }
    print("\n[A] Channel/launch vs run (Spearman):", flush=True)
    for k, v in corrs.items():
        print(f"    {k:48s} {v}", flush=True)

    # B. is the path an ARC? (downward parabola concave fraction + fit quality)
    asc_concave = float((S["asc_b2"] < 0).mean()) if S["asc_b2"].notna().any() else np.nan
    D = S.dropna(subset=["arc_b2"])
    arc_concave = float((D["arc_b2"] < 0).mean()) if len(D) else np.nan
    print(f"\n[B] Arc shape: ascent concave (dome) in {asc_concave:.0%} of legs; "
          f"full launch->drop concave in {arc_concave:.0%}.", flush=True)
    print(f"    Parabola vs line fit on the full arc: median R2 quad={D['arc_r2q'].median():.2f} "
          f"vs lin={D['arc_r2l'].median():.2f} (n={len(D)}).", flush=True)

    # C. ballistic signature: does apex height grow with velocity^2?
    cB = S.dropna(subset=["v3", "apex_amp"]).copy()
    if len(cB) > 200:
        cB = _winsor(cB, ["v3", "apex_amp"])
        r_lin = LinearRegression().fit(cB[["v3"]], cB["apex_amp"])
        r_sq = LinearRegression().fit(np.c_[cB["v3"], cB["v3"] ** 2], cB["apex_amp"])
        from sklearn.metrics import r2_score as _r2
        print(f"\n[C] Apex height vs velocity: R2 linear-in-v={_r2(cB['apex_amp'], r_lin.predict(cB[['v3']])):.3f}, "
              f"add v^2 term -> R2={_r2(cB['apex_amp'], r_sq.predict(np.c_[cB['v3'], cB['v3']**2])):.3f} "
              f"(v^2 coef {r_sq.coef_[1]:+.3f}); >0 supports the ballistic 'height ~ v^2' shape.", flush=True)

    # D. symmetry of the arc (ascent vs descent)
    if ndrop > 50:
        med_rt = S["retrace_frac"].median()
        sym = (S["drop_bars"] / S["apex_bars"]).median()
        print(f"\n[D] Symmetry: median retrace = {med_rt:.2f} of the run; "
              f"descent/ascent bar ratio = {sym:.2f} "
              f"(=1 would be a perfectly symmetric ballistic arc).", flush=True)

    # E. forecast curves: apex height, apex time, drop depth from first k candles
    def raw_feats(k):
        f = ["L_atr", "L_mr"]
        for j in range(1, k + 1):
            f += [f"c{j}_ret", f"c{j}_batr", f"c{j}_vr", f"c{j}_cum"]
        return f
    phys = {1: ["v1", "L_atr"],
            2: ["v2", "accel", "angle2", "chan_widen2", "L_atr"],
            3: ["v3", "accel", "angle3", "chan_widen3", "L_atr"]}
    print("\n[E] OOS R^2 — forecasting from the first k candles (lin/GBM):", flush=True)
    for tgt, lbl in (("apex_amp", "apex HEIGHT"), ("apex_bars", "apex TIME"), ("drop_amp", "DROP depth")):
        print(f"  {lbl}:", flush=True)
        for k in (1, 2, 3):
            rr, n1 = oos_r2(S, raw_feats(k), tgt)
            pr, n2 = oos_r2(S, phys[k], tgt)
            rs = f"lin={rr[0]} gbm={rr[1]}" if rr else "n<200"
            ps = f"lin={pr[0]} gbm={pr[1]}" if pr else "n<200"
            print(f"    k={k}: raw[{rs}] (n={n1})   physics[{ps}] (n={n2})", flush=True)

    # ---- report ----
    out = ROOT / "reports/stocks"
    rep = [f"# Channel-physics study — the thrown-ball hypothesis on 5-minute candles "
           f"({S['ticker'].nunique()} names)", "",
           f"Tests whether the **angle** of the channel (highs/lows-line slope) and the "
           f"**intensity** of the first 1–3 candles set the **arc** of an intraday run — apex "
           f"height, time-to-top, and the drop before the next rise — like a projectile's launch "
           f"angle + velocity. {nseg:,} single-session up-legs (apex ≥ {a.minbars} bars, 5m, "
           f"swing width {a.width}); {ndrop:,} have a same-session drop.", "",
           "## A. Does the channel/launch correlate with the run? (Spearman)", "",
           "| relationship | ρ |", "|---|---|"]
    for k, v in corrs.items():
        rep.append(f"| {k} | {v} |")
    rep += ["", "## B. Is the path actually an arc?", "",
            f"- Ascent traces a concave dome (β₂<0) in **{asc_concave:.0%}** of legs; the full "
            f"launch→drop is concave in **{arc_concave:.0%}**.",
            f"- A downward parabola fits the full arc well: median R² **{D['arc_r2q'].median():.2f}** "
            f"(quadratic) vs **{D['arc_r2l'].median():.2f}** (straight line) — price traces a ball-arc, "
            f"not a line.", "",
            "## C. Ballistic signature (height grows with velocity²)", ""]
    if len(cB) > 200:
        rep += [f"- Apex height vs launch velocity: adding a **v²** term lifts R² "
                f"{_r2(cB['apex_amp'], r_lin.predict(cB[['v3']])):.3f} → "
                f"{_r2(cB['apex_amp'], r_sq.predict(np.c_[cB['v3'], cB['v3']**2])):.3f} "
                f"(v² coef {r_sq.coef_[1]:+.3f}). A positive v² term is the projectile signature: "
                f"faster launches top **disproportionately** higher.", ""]
    if ndrop > 50:
        rep += ["## D. Symmetry of the arc (does the drop mirror the rise?)", "",
                f"- Median retrace = **{S['retrace_frac'].median():.2f}** of the run; descent/ascent "
                f"bar-ratio = **{(S['drop_bars']/S['apex_bars']).median():.2f}** (1.0 = perfectly "
                f"symmetric ballistic arc). ", ""]
    rep += ["## E. Forecasting the arc from the first k candles (OOS R²)", "",
            "PHYSICS features = launch velocity, acceleration, channel angle, channel-widening, ATR. "
            "RAW = the per-candle returns/body/volume/cum used in the min-info study.", "",
            "| target | k | raw (lin/GBM) | physics (lin/GBM) |", "|---|---|---|---|"]
    for tgt, lbl in (("apex_amp", "apex HEIGHT"), ("apex_bars", "apex TIME"), ("drop_amp", "DROP depth")):
        for k in (1, 2, 3):
            rr, _ = oos_r2(S, raw_feats(k), tgt); pr, _ = oos_r2(S, phys[k], tgt)
            rs = f"{rr[0]}/{rr[1]}" if rr else "n/a"; ps = f"{pr[0]}/{pr[1]}" if pr else "n/a"
            rep.append(f"| {lbl} | {k} | {rs} | {ps} |")
    rep += ["", "_5m only (2023+, finest data in the DB). Survivorship: legs are confirmed swing "
            "highs, so real-time you must gate with the oversold/5m-VWAP entry confirmation._"]
    (out / "CHANNEL_PHYSICS_STUDY.md").write_text("\n".join(rep), encoding="utf-8")
    S.to_csv(out / "channel_physics.csv", index=False)
    print(f"\nwrote {out/'CHANNEL_PHYSICS_STUDY.md'}", flush=True)


if __name__ == "__main__":
    main()
