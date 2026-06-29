"""
universe_arc_study.py — scale the three 5m arc studies to the WHOLE 5m universe
(~5,560 tickers), liquidity-tiered, in ONE pass.

Combines, per up-leg (throw a -> top b -> bounce c), the metrics of:
  * channel_physics_study      (launch velocity/angle, arc parabola fit, apex height/time)
  * arc_drop_support_study     (retrace, footholds/support, drop-target accuracy)
  * resistance_interaction_study (nearest prior WALL: stall/break by drop-intensity)

One indicator computation + swing detection per ticker (the expensive part is shared,
so this is ~3x cheaper than running the three studies separately). OOM-safe: mining is
checkpointed/resumable and STREAMS rows to parquet shards; only one batch is in RAM.

Usage:
    python scripts/universe_arc_study.py                 # mine (resume) then analyze
    python scripts/universe_arc_study.py --mine-only
    python scripts/universe_arc_study.py --analyze-only
    python scripts/universe_arc_study.py --restart
    python scripts/universe_arc_study.py --limit 50      # smoke
"""
from __future__ import annotations
import sys, argparse, json, time
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "src"))
import aapl_deep_dive as dd
from atlas_research.ta import structure as ta_structure, patterns as ta_patterns
from channel_physics_study import _quad_fit
from arc_drop_support_study import supports_on_the_way_up
from resistance_interaction_study import resistance_peaks
from scipy.stats import spearmanr
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

SHARD_DIR = ROOT / "reports/stocks/universe_arc_events"
CKPT = ROOT / "reports/stocks/.universe_arc_checkpoint.json"
REPORT = ROOT / "reports/stocks/UNIVERSE_ARC_STUDY.md"
LOOKUP = ROOT / "reports/stocks/universe_arc_targets.json"
WINSOR = (0.01, 0.99)


def _ticks():
    return sorted(p.stem for p in (ROOT / "data/intraday_5m/by_ticker").glob("*.parquet"))


def collect_ticker(tk, width, min_amp, minbars, lookback, minwall):
    df = pd.read_parquet(ROOT / f"data/intraday_5m/by_ticker/{tk}.parquet")
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    for cc in ("open", "high", "low", "close", "volume"):
        df[cc] = pd.to_numeric(df[cc], errors="coerce")
    if len(df) < 300:
        return []
    df = dd.compute_indicators(df, intraday=True)
    h = df["high"].values; l = df["low"].values; c = df["close"].values
    atrp = df["atr_pct"].values; vol = df["volume"].values
    sess = df["ts"].dt.date.values
    N = len(df)
    dollar_vol = float(np.nanmedian((c * vol)[-5000:])) if N else np.nan
    piv = ta_structure.swing_pivots(h, l, width=width)
    res = resistance_peaks(piv, h, l)
    res_idx = np.array([r[0] for r in res]); res_px = np.array([r[1] for r in res])
    res_dep = np.array([r[2] for r in res]); res_spd = np.array([r[3] for r in res])

    rows = []
    for lg in ta_patterns.swing_legs(piv, h, l, c, min_amp=min_amp):
        a = lg["start_idx"]; b = lg["peak_idx"]; cc = lg["corr_idx"]
        if a < 30 or b - a < minbars or a + 3 >= N:
            continue
        Pa = c[a]; apex_h = h[b]
        if Pa <= 0 or sess[a] != sess[b]:
            continue
        atr_pr = atrp[a] / 100 * Pa if atrp[a] > 0 else np.nan
        if not np.isfinite(atr_pr) or atr_pr <= 0:
            continue

        rec = dict(ticker=tk, dollar_vol=dollar_vol,
                   apex_amp=lg["leg_amp"] * 100, apex_bars=int(b - a), L_atr=atrp[a])
        # ---- physics: launch velocity / channel angle / arc ----
        for k in (1, 2, 3):
            rec[f"v{k}"] = (c[a + k] - Pa) / Pa / k * 100
        rec["accel"] = rec["v2"] - rec["v1"]
        t3 = np.arange(4, dtype=float)
        sh = np.polyfit(t3, h[a:a + 4], 1)[0] / Pa * 100
        sl = np.polyfit(t3, l[a:a + 4], 1)[0] / Pa * 100
        scl = np.polyfit(t3, c[a:a + 4], 1)[0] / Pa * 100
        rec["hi_slope3"] = sh; rec["lo_slope3"] = sl; rec["chan_widen3"] = sh - sl
        rec["angle3"] = np.degrees(np.arctan(scl / atr_pr * Pa / 100))
        _, b2a, r2qa, r2la = _quad_fit(c[a:b + 1])
        rec.update(asc_b2=b2a, asc_r2q=r2qa, asc_r2l=r2la)

        # ---- drop / support (needs a same-session bounce) ----
        same_drop = cc is not None and cc > b and sess[cc] == sess[a]
        if same_drop:
            Pb = h[b]; Pc = l[cc]; run = Pb - Pa
            if run > 0:
                _, b2f, r2qf, r2lf = _quad_fit(c[a:cc + 1])
                sup = supports_on_the_way_up(l, a, b)
                sp_px = np.array([p for _, p in sup]); below = sp_px[sp_px < Pb]
                highest_HL = below.max() if below.size else Pa
                rec.update(
                    retrace=(Pb - Pc) / run, drop_pct=(Pb - Pc) / Pb * 100,
                    run_pct=run / Pa * 100, drop_bars=int(cc - b),
                    n_sup=len(sup), arc_b2=b2f, arc_r2q=r2qf, arc_r2l=r2lf,
                    held_HL=bool(Pc >= highest_HL - 0.10 * run),
                    err_fixed35=abs((Pb - 0.35 * run) - Pc) / run,
                    err_highHL=abs(highest_HL - Pc) / run)
        # ---- resistance: nearest prior WALL >= minwall ATR overhead ----
        lo_px = Pa + minwall * atr_pr; hi_px = Pa + 4.0 * atr_pr
        m = (res_idx >= a - lookback) & (res_idx < a) & (res_px >= lo_px) & (res_px <= hi_px)
        if m.any():
            cpx = res_px[m]; cidx = res_idx[m]; cdep = res_dep[m]; cspd = res_spd[m]
            j = int(np.argmin(cpx)); level = cpx[j]; tol = 0.5 * atr_pr
            rec.update(
                has_res=True, age_bars=int(a - cidx[j]),
                touches=int(np.sum(np.abs(cpx - level) <= tol)),
                res_drop_dep=float(cdep[j]) * 100, res_drop_spd=float(cspd[j]) * 100,
                reached=bool(apex_h >= level - tol), stalled=bool(abs(apex_h - level) <= tol),
                broke=bool(apex_h > level + tol), short=bool(apex_h < level - tol),
                cont_atr=((apex_h - level) / atr_pr if apex_h > level + tol else np.nan))
        else:
            rec["has_res"] = False
        rows.append(rec)
    return rows


# ----------------------------------------------------------------------------- mine
def mine(args):
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    universe = _ticks()
    if args.limit:
        universe = universe[:args.limit]
    if args.restart:
        for p in SHARD_DIR.glob("shard_*.parquet"):
            p.unlink()
        done = set()
    else:
        done = set(json.loads(CKPT.read_text())) if CKPT.exists() else set()
    todo = [t for t in universe if t not in done]
    print(f"universe={len(universe)} done={len(done)} todo={len(todo)}", flush=True)

    t0 = time.time(); buf = []; nrows = 0
    shard_i = len(list(SHARD_DIR.glob("shard_*.parquet")))

    def flush():
        nonlocal buf, shard_i
        if not buf:
            return
        pd.DataFrame(buf).to_parquet(SHARD_DIR / f"shard_{shard_i:05d}.parquet", index=False)
        shard_i += 1; buf = []; CKPT.write_text(json.dumps(sorted(done)))

    for i, tk in enumerate(todo, 1):
        try:
            buf.extend(collect_ticker(tk, args.width, args.min_amp, args.minbars,
                                      args.lookback, args.minwall))
            nrows = nrows  # noqa
        except Exception as e:
            print(f"  !! {tk}: {str(e)[:90]}", flush=True)
        done.add(tk)
        if len(buf) >= args.batch_rows:
            nrows += len(buf); flush()
        if i % 200 == 0 or i == len(todo):
            rate = i / max(time.time() - t0, 1e-9)
            print(f"  [{i}/{len(todo)}] {tk} ~rows={nrows+len(buf):,} ({rate:.1f} tk/s, "
                  f"eta {(len(todo)-i)/max(rate,1e-9)/60:.0f}m)", flush=True)
    nrows += len(buf); flush()
    print(f"MINE DONE: ~{nrows:,} rows / {shard_i} shards", flush=True)


# -------------------------------------------------------------------------- analyze
def _winsor(d, cols):
    d = d.copy()
    for col in cols:
        if col in d:
            lo, hi = d[col].quantile(WINSOR)
            if np.isfinite(lo) and np.isfinite(hi) and hi > lo:
                d[col] = d[col].clip(lo, hi)
    return d


def _sp(d, x, y):
    s = d[[x, y]].dropna()
    return round(spearmanr(s[x], s[y])[0], 3) if len(s) >= 200 else None


def _v2lift(d):
    """R2 of apex height from velocity, linear vs +v^2 (the ballistic signature)."""
    s = d.dropna(subset=["v3", "apex_amp"])
    if len(s) < 300:
        return None
    s = _winsor(s, ["v3", "apex_amp"])
    rl = LinearRegression().fit(s[["v3"]], s["apex_amp"])
    rq = LinearRegression().fit(np.c_[s["v3"], s["v3"] ** 2], s["apex_amp"])
    return (round(r2_score(s["apex_amp"], rl.predict(s[["v3"]])), 3),
            round(r2_score(s["apex_amp"], rq.predict(np.c_[s["v3"], s["v3"] ** 2])), 3),
            round(float(rq.coef_[1]), 2))


def _phys_row(d, label):
    asc = d["asc_b2"].dropna(); fa = d.dropna(subset=["arc_b2"])
    conc = (asc < 0).mean() if len(asc) else np.nan
    arcc = (fa["arc_b2"] < 0).mean() if len(fa) else np.nan
    q = fa["arc_r2q"].median() if len(fa) else np.nan
    li = fa["arc_r2l"].median() if len(fa) else np.nan
    v = _v2lift(d)
    vtxt = f"{v[0]}→{v[1]} ({v[2]:+})" if v else "n/a"
    return (f"| {label} | {len(d):,} | {arcc:.0%} | {q:.2f}/{li:.2f} | {vtxt} | "
            f"{_sp(d,'lo_slope3','apex_amp')} | {_sp(d,'v3','apex_amp')} |")


def _drop_row(d, label):
    dd_ = d.dropna(subset=["retrace"])
    dd_ = dd_[(dd_["retrace"] > 0) & (dd_["retrace"] < 3)]
    if len(dd_) < 100:
        return None
    rb = dd_.copy()
    rb["bkt"] = pd.qcut(rb["run_pct"].rank(method="first"), 4, labels=["sm", "md", "big", "huge"])
    by = rb.groupby("bkt", observed=True)["retrace"].median()
    return (f"| {label} | {len(dd_):,} | {dd_['retrace'].median():.2f} | "
            f"{by.get('sm', float('nan')):.2f}/{by.get('huge', float('nan')):.2f} | "
            f"{dd_['held_HL'].mean():.0%} | {dd_['err_fixed35'].median():.2f}/{dd_['err_highHL'].median():.2f} |")


def _res_row(d, label):
    r = d[d["has_res"] == True]
    reached = r[r["reached"] == True]
    if len(reached) < 100:
        return None, None
    row = (f"| {label} | {len(r):,} | {reached['stalled'].mean():.0%} | "
           f"{reached['broke'].mean():.0%} | {_sp(reached,'res_drop_dep','broke')} |")
    # drop-intensity buckets (pooled only)
    bucket = None
    if len(reached) > 400:
        rr = reached.copy()
        rr["bkt"] = pd.qcut(rr["res_drop_dep"].rank(method="first"), 4,
                            labels=["mild", "moderate", "strong", "violent"])
        t = rr.groupby("bkt", observed=True).agg(n=("broke", "size"), pbreak=("broke", "mean"),
                                                 cont=("cont_atr", "median"))
        bucket = t
    return row, bucket


def _money(x):
    if x is None or not np.isfinite(x):
        return "n/a"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div:
            return f"${x/div:,.1f}{suf}"
    return f"${x:,.0f}"


def analyze(args):
    shards = sorted(SHARD_DIR.glob("shard_*.parquet"))
    if not shards:
        print("no shards — mine first", flush=True); return
    R = pd.concat((pd.read_parquet(p) for p in shards), ignore_index=True)
    R = R.replace([np.inf, -np.inf], np.nan)
    if "has_res" in R:
        R["has_res"] = R["has_res"].fillna(False)
    print(f"loaded {len(R):,} legs / {R['ticker'].nunique()} tickers from {len(shards)} shards", flush=True)

    perticker = R.groupby("ticker")["dollar_vol"].first()
    q = pd.qcut(perticker.rank(method="first"), args.tiers, labels=[f"T{i+1}" for i in range(args.tiers)])
    lab = {f"T{i+1}": f"T{args.tiers - i}" for i in range(args.tiers)}     # T1 = most liquid
    tier = q.map(lab).astype(str)
    R["tier"] = R["ticker"].map(tier)
    tier_dv = {t: (perticker[tier == t].min(), perticker[tier == t].max()) for t in sorted(set(tier))}
    tiers = sorted(set(R["tier"]))

    rep = [f"# Whole-universe 5m arc study — physics · drop/support · resistance "
           f"({R['ticker'].nunique():,} tickers)", "",
           f"Scales the three basket studies to every 5m ticker, liquidity-tiered. "
           f"{len(R):,} single-session up-legs. 5m, 2023+ (finest data in the DB).", "",
           "## Liquidity tiers (median daily $-volume)", "",
           "| tier | n tickers | $-vol range |", "|---|---|---|"]
    for t in tiers:
        lo, hi = tier_dv[t]
        rep.append(f"| {t} | {(tier == t).sum()} | {_money(lo)} – {_money(hi)} |")

    # 1. PHYSICS ----------------------------------------------------------------
    rep += ["", "## 1. Thrown-ball physics (arc shape & ballistic signature)", "",
            "| group | n legs | full-arc concave | arc R² quad/lin | apex-height v→+v² (coef) | "
            "ρ lows-slope→apex | ρ velocity→apex |", "|---|---|---|---|---|---|---|",
            _phys_row(R, "POOLED")]
    for t in tiers:
        rep.append(_phys_row(R[R["tier"] == t], t))

    # 2. DROP / SUPPORT ---------------------------------------------------------
    rep += ["", "## 2. Drop targets & support (whole arc throw→bounce)", "",
            "| group | n arcs | median retrace | retrace small/huge | bounce holds nearest HL | "
            "target err 35%/HL |", "|---|---|---|---|---|---|"]
    pr = _drop_row(R, "POOLED")
    if pr:
        rep.append(pr)
    for t in tiers:
        r = _drop_row(R[R["tier"] == t], t)
        if r:
            rep.append(r)

    # 3. RESISTANCE -------------------------------------------------------------
    rep += ["", "## 3. Resistance interaction (does the prior wall stop the run?)", "",
            "| group | n with wall | stall@wall (reached) | break (reached) | ρ drop-depth→break |",
            "|---|---|---|---|---|"]
    prow, pbucket = _res_row(R, "POOLED")
    if prow:
        rep.append(prow)
    for t in tiers:
        rr, _ = _res_row(R[R["tier"] == t], t)
        if rr:
            rep.append(rr)
    if pbucket is not None:
        rep += ["", "### P(run breaks through) by the wall's prior DROP INTENSITY (pooled)", "",
                "| prior-drop intensity | n | P(break) | median continuation past (ATR) |",
                "|---|---|---|---|"]
        for bk, r in pbucket.iterrows():
            cont = r["cont"] if pd.notna(r["cont"]) else float("nan")
            rep.append(f"| {bk} | {int(r['n'])} | {r['pbreak']*100:.0f}% | {cont:.2f} |")

    rep += ["", "_Survivorship: legs are confirmed swing highs; gate live with oversold/VWAP entry "
            "confirmation. Winsorized [1%,99%] where fit._"]
    REPORT.write_text("\n".join(rep), encoding="utf-8")
    print(f"wrote {REPORT}", flush=True)

    # operational lookup for daily_scan: per-tier drop target + resistance break rate
    lookup = {"winsor": list(WINSOR), "tier_dollar_vol_max": {}, "tiers": {}}
    for t in tiers:
        st = R[R["tier"] == t]; dd_ = st.dropna(subset=["retrace"])
        dd_ = dd_[(dd_["retrace"] > 0) & (dd_["retrace"] < 3)]
        reached = st[(st["has_res"] == True) & (st["reached"] == True)]
        lookup["tier_dollar_vol_max"][t] = float(tier_dv[t][1])
        lookup["tiers"][t] = {
            "median_retrace": round(float(dd_["retrace"].median()), 3) if len(dd_) else None,
            "median_drop_pct": round(float(dd_["drop_pct"].median()), 3) if len(dd_) else None,
            "wall_break_rate": round(float(reached["broke"].mean()), 3) if len(reached) else None,
            "n_arcs": int(len(dd_))}
    LOOKUP.write_text(json.dumps(lookup, indent=2))
    print(f"wrote {LOOKUP}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--min-amp", type=float, default=0.01)
    ap.add_argument("--minbars", type=int, default=6)
    ap.add_argument("--lookback", type=int, default=2000)
    ap.add_argument("--minwall", type=float, default=1.0)
    ap.add_argument("--tiers", type=int, default=4)
    ap.add_argument("--batch-rows", type=int, default=80000)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--restart", action="store_true")
    ap.add_argument("--mine-only", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()
    if not args.analyze_only:
        mine(args)
    if not args.mine_only:
        analyze(args)


if __name__ == "__main__":
    main()
