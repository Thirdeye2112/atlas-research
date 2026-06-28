"""
candle_window_study.py — 3-before / 3-after candle window study.

For every Rise or Drop event (top/bottom 10% candle return per ticker) we
extract a 7-candle window:  t-3  t-2  t-1  [event]  t+1  t+2  t+3

Two analyses run back-to-back:

1. SETUP FINGERPRINT (ME scores)
   All TA features at each of t-3, t-2, t-1 are scored for Mutual Exclusivity
   vs the event label.  Tells you WHICH combination of pre-event signals most
   reliably precedes a rise vs a drop.

2. WALK-FORWARD BACKTEST
   Top-K setup conditions (by ME score) are combined into a signal.
   Temporal 70/30 split (train fingerprint → test on held-out period).
   For each matching setup bar we record forward returns at t+1, t+2, t+3.
   Output: win-rate, mean return, Sharpe, max drawdown per signal.

Usage:
    python scripts/candle_window_study.py
    python scripts/candle_window_study.py --data-dir "C:/Atlas/atlas-research/data/samples"
    python scripts/candle_window_study.py --sample 50 --dry-run
    python scripts/candle_window_study.py --top-k 5 --horizon 3
"""
from __future__ import annotations
import os, sys, argparse, json, base64, warnings
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ── config ────────────────────────────────────────────────────────────────────
DATA_DIR      = Path(os.environ.get("CANDLE_DATA_DIR",
                     r"C:\Atlas\atlas-research\data\intraday_5m\by_ticker"))
GITHUB_REPO   = "Thirdeye2112/atlas-research"
GITHUB_BRANCH = "main"
PERCENTILE    = 10          # top/bottom 10% candle return = event
WINDOW        = 3           # bars before and after event
TOP_K         = 10          # top ME signals to combine into setup
TRAIN_FRAC    = 0.70        # temporal split for walk-forward
MIN_SETUP_OBS = 30          # minimum matching events to report a setup

# ── GitHub push ───────────────────────────────────────────────────────────────
def github_push(path_in_repo: str, content: str, msg: str) -> None:
    import urllib.request
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("  WARN: GITHUB_TOKEN not set — skipping push")
        return
    api  = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path_in_repo}"
    hdrs = {"Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "atlas-research-bot"}
    sha  = None
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers=hdrs)) as r:
            sha = json.loads(r.read()).get("sha")
    except Exception:
        pass
    payload = {"message": msg,
               "content": base64.b64encode(content.encode()).decode(),
               "branch": GITHUB_BRANCH}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                 headers=hdrs, method="PUT")
    with urllib.request.urlopen(req) as r:
        print(f"  GitHub -> {path_in_repo}  [{r.status}]")

# ── data loading ──────────────────────────────────────────────────────────────
def discover(data_dir: Path) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    files = sorted(data_dir.glob("*.parquet")) or sorted(data_dir.rglob("*.parquet"))
    for f in files:
        groups[f.stem.split("_")[0].upper()].append(f)
    return dict(groups)

def load_ticker(files: list[Path]) -> pd.DataFrame:
    frames = [pd.read_parquet(f, engine="pyarrow",
                              columns=["ticker","ts","open","high","low","close","volume"])
              for f in files]
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.drop_duplicates(subset=["ticker","ts"]).sort_values("ts").reset_index(drop=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

# ── TA features ───────────────────────────────────────────────────────────────
def ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def rsi(c: pd.Series, p: int = 14) -> pd.Series:
    d = c.diff()
    g = d.clip(lower=0).ewm(com=p-1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=p-1, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    # candle anatomy
    df["body_pct"]      = (c - o).abs() / o.replace(0, np.nan) * 100
    df["body_dir"]      = np.sign(c - o).astype(float)
    rng                 = (h - l).replace(0, np.nan)
    df["upper_wick_pct"]= (h - np.maximum(o, c)) / rng * 100
    df["lower_wick_pct"]= (np.minimum(o, c) - l) / rng * 100
    df["body_to_range"] = df["body_pct"] / (rng / c.replace(0, np.nan) * 100)
    df["inside_bar"]    = ((h < h.shift(1)) & (l > l.shift(1))).astype(float)
    df["outside_bar"]   = ((h > h.shift(1)) & (l < l.shift(1))).astype(float)
    df["hammer"]        = ((df["lower_wick_pct"] > 60) & (df["body_to_range"] < 0.35)).astype(float)
    df["shooting_star"] = ((df["upper_wick_pct"] > 60) & (df["body_to_range"] < 0.35)).astype(float)
    df["doji"]          = (df["body_to_range"] < 0.10).astype(float)

    # volume
    vol_ma20           = v.rolling(20, min_periods=1).mean()
    df["vol_ratio"]    = v / vol_ma20.replace(0, np.nan)
    df["vol_climax"]   = (df["vol_ratio"] > 3.0).astype(float)
    df["vol_dry"]      = (df["vol_ratio"] < 0.4).astype(float)
    df["vol_up"]       = (v > v.shift(1)).astype(float)

    # EMAs
    e9  = ema(c, 9);  e20 = ema(c, 20);  e50 = ema(c, 50)
    df["above_ema9"]   = (c > e9).astype(float)
    df["above_ema20"]  = (c > e20).astype(float)
    df["above_ema50"]  = (c > e50).astype(float)
    df["above_all_emas"]= ((c>e9)&(c>e20)&(c>e50)).astype(float)
    df["below_all_emas"]= ((c<e9)&(c<e20)&(c<e50)).astype(float)
    df["ema_bull_stack"]= (e9 > e20).astype(float)
    df["dist_ema9_pct"] = (c - e9)  / e9.replace(0, np.nan) * 100
    df["dist_ema20_pct"]= (c - e20) / e20.replace(0, np.nan) * 100

    # RSI
    r14                = rsi(c, 14)
    df["rsi"]          = r14
    df["rsi_slope"]    = r14.diff(2)
    df["rsi_above50"]  = (r14 > 50).astype(float)
    df["rsi_above70"]  = (r14 > 70).astype(float)
    df["rsi_below30"]  = (r14 < 30).astype(float)
    df["rsi_reclaim50"]= ((r14 > 50) & (r14.shift(1) < 50)).astype(float)
    df["rsi_lose50"]   = ((r14 < 50) & (r14.shift(1) > 50)).astype(float)

    # Bollinger Bands
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_up  = bb_mid + 2*bb_std;  bb_lo = bb_mid - 2*bb_std
    bb_rng = (bb_up - bb_lo).replace(0, np.nan)
    df["bb_pct"]         = (c - bb_lo) / bb_rng
    df["bb_width"]       = bb_rng / bb_mid.replace(0, np.nan) * 100
    df["bb_squeeze"]     = (df["bb_width"] < df["bb_width"].rolling(20).quantile(0.20)).astype(float)
    df["above_bb_upper"] = (c > bb_up).astype(float)
    df["below_bb_lower"] = (c < bb_lo).astype(float)

    # VWAP
    df["_d"]  = df["ts"].dt.date
    tp        = (h + l + c) / 3
    cum_tpv   = df.groupby("_d").apply(lambda g: (tp.loc[g.index] * v.loc[g.index]).cumsum()).reset_index(level=0, drop=True)
    cum_v     = df.groupby("_d")["volume"].cumsum()
    vwap      = cum_tpv / cum_v.replace(0, np.nan)
    df["above_vwap"]   = (c > vwap).astype(float)
    df["vwap_dist_pct"]= (c - vwap) / vwap.replace(0, np.nan) * 100
    df.drop(columns=["_d"], inplace=True)

    # ATR
    tr = pd.concat([(h-l), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(com=13, adjust=False).mean()
    df["atr_pct"]     = atr / c.replace(0, np.nan) * 100
    df["atr_expand"]  = atr / atr.rolling(5).mean().replace(0, np.nan)

    # MACD
    macd = ema(c,12) - ema(c,26);  sig = ema(macd, 9)
    df["macd_hist"]       = macd - sig
    df["macd_above_sig"]  = (macd > sig).astype(float)
    df["macd_hist_up"]    = (df["macd_hist"] > df["macd_hist"].shift(1)).astype(float)
    df["macd_bull_cross"] = ((macd > sig) & (macd.shift(1) <= sig.shift(1))).astype(float)
    df["macd_bear_cross"] = ((macd < sig) & (macd.shift(1) >= sig.shift(1))).astype(float)

    # Stochastic
    lo14 = l.rolling(14).min();  hi14 = h.rolling(14).max()
    stoch_k = (c - lo14) / (hi14 - lo14).replace(0, np.nan) * 100
    df["stoch_k"]        = stoch_k
    df["stoch_above80"]  = (stoch_k > 80).astype(float)
    df["stoch_below20"]  = (stoch_k < 20).astype(float)
    df["stoch_bull_cross"]= ((stoch_k > 20) & (stoch_k.shift(1) <= 20)).astype(float)

    # consecutive direction
    dirs  = df["body_dir"].values
    streak = np.zeros(len(dirs))
    s = 0.0
    for i, d in enumerate(dirs):
        s = s + d if d == np.sign(s) and d != 0 else d
        streak[i] = s
    df["consec_dir"] = streak

    # session
    mins = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    df["is_open_30m"]  = ((mins >= 570) & (mins < 600)).astype(float)
    df["is_power_hour"]= ((mins >= 900) & (mins < 960)).astype(float)
    df["day_of_week"]  = df["ts"].dt.dayofweek.astype(float)

    # candle return (for event labelling)
    df["candle_ret"] = (c - o) / o.replace(0, np.nan) * 100

    return df

# ── base feature column names ─────────────────────────────────────────────────
BASE_FEATS = [
    "body_pct","body_dir","upper_wick_pct","lower_wick_pct","body_to_range",
    "inside_bar","outside_bar","hammer","shooting_star","doji",
    "vol_ratio","vol_climax","vol_dry","vol_up",
    "above_ema9","above_ema20","above_ema50","above_all_emas","below_all_emas",
    "ema_bull_stack","dist_ema9_pct","dist_ema20_pct",
    "rsi","rsi_slope","rsi_above50","rsi_above70","rsi_below30",
    "rsi_reclaim50","rsi_lose50",
    "bb_pct","bb_width","bb_squeeze","above_bb_upper","below_bb_lower",
    "above_vwap","vwap_dist_pct",
    "atr_pct","atr_expand",
    "macd_hist","macd_above_sig","macd_hist_up","macd_bull_cross","macd_bear_cross",
    "stoch_k","stoch_above80","stoch_below20","stoch_bull_cross",
    "consec_dir","is_open_30m","is_power_hour","day_of_week",
]

# ── window extraction ─────────────────────────────────────────────────────────
def extract_windows(df: pd.DataFrame, w: int = WINDOW) -> pd.DataFrame:
    """
    For each event row (rise/drop), build a flat feature vector containing
    the TA features at each of the w bars before and w bars after the event.

    Columns are prefixed:  tm3_<feat>, tm2_<feat>, tm1_<feat>,
                           t0_<feat>,
                           tp1_<feat>, tp2_<feat>, tp3_<feat>

    Also includes forward returns:  fwd_ret_1, fwd_ret_2, fwd_ret_3
    """
    events = df[df["event"].notna()].copy()
    if events.empty:
        return pd.DataFrame()

    rows = []
    close = df["close"].values
    ts    = df["ts"].values
    idx   = df.index.values

    feat_arr = {f: df[f].values for f in BASE_FEATS if f in df.columns}

    for pos in events.index:
        loc = df.index.get_loc(pos)
        if loc < w or loc + w >= len(df):
            continue

        row: dict = {
            "ticker": df.at[pos, "ticker"],
            "ts":     df.at[pos, "ts"],
            "event":  df.at[pos, "event"],
        }

        # window features
        for offset in range(-w, w+1):
            wloc = loc + offset
            widx = idx[wloc]
            if offset < 0:
                prefix = f"tm{abs(offset)}_"
            elif offset == 0:
                prefix = "t0_"
            else:
                prefix = f"tp{offset}_"
            for f, arr in feat_arr.items():
                row[prefix + f] = arr[wloc]

        # forward returns (t+1, t+2, t+3 open-to-close)
        for fh in range(1, w+1):
            floc = loc + fh
            if floc < len(df):
                o_fwd = df["open"].iloc[floc]
                c_fwd = df["close"].iloc[floc]
                row[f"fwd_ret_{fh}"] = (c_fwd - o_fwd) / o_fwd * 100 if o_fwd else np.nan
            else:
                row[f"fwd_ret_{fh}"] = np.nan

        rows.append(row)

    return pd.DataFrame(rows)

# ── ME scoring ────────────────────────────────────────────────────────────────
def _r(x, d=4):
    try: return round(float(x), d)
    except: return None

def me_score_features(win_df: pd.DataFrame, feat_cols: list[str]) -> pd.DataFrame:
    """Compute ME score for each feature column vs rise/drop label."""
    rise = win_df[win_df["event"] == "rise"]
    drop = win_df[win_df["event"] == "drop"]
    rows = []
    for f in feat_cols:
        rv = rise[f].dropna()
        dv = drop[f].dropna()
        if len(rv) < 10 or len(dv) < 10:
            continue
        try:
            u, p = stats.mannwhitneyu(rv, dv, alternative="two-sided")
            n    = len(rv) * len(dv)
            auc  = u / n
            # continuous: Cliff's delta; binary: lift
            is_binary = set(win_df[f].dropna().unique()).issubset({0.0, 1.0})
            if is_binary:
                r_rate = rv.mean(); d_rate = dv.mean()
                rise_lift = r_rate / d_rate if d_rate > 1e-9 else np.nan
                drop_lift = d_rate / r_rate if r_rate > 1e-9 else np.nan
                me = rise_lift / drop_lift if (not np.isnan(rise_lift) and not np.isnan(drop_lift) and drop_lift > 0) else np.nan
                effect = _r(rise_lift - 1, 4)   # excess lift
            else:
                rise_lift = drop_lift = np.nan
                cd = (2*u / n) - 1
                me = np.exp(abs(cd) * 3) * np.sign(cd) if not np.isnan(cd) else np.nan
                effect = _r(cd, 4)
        except Exception:
            continue

        rows.append({
            "feature":    f,
            "me_score":   _r(me, 4),
            "rise_lift":  _r(rise_lift, 4),
            "drop_lift":  _r(drop_lift, 4),
            "effect_size":effect,
            "p_value":    _r(p, 6),
            "n_rise":     len(rv),
            "n_drop":     len(dv),
        })
    df = pd.DataFrame(rows).dropna(subset=["me_score"])
    return df.sort_values("me_score", ascending=False)

# ── walk-forward backtest ─────────────────────────────────────────────────────
def wf_backtest(win_train: pd.DataFrame, win_test: pd.DataFrame,
                top_k: int = TOP_K, min_obs: int = MIN_SETUP_OBS) -> pd.DataFrame:
    """
    1. On train: find top_k pre-event features for rise and drop.
    2. On test:  for each setup condition, record forward returns.
    3. Return summary per signal.
    """
    # only pre-event features (tm1, tm2, tm3)
    pre_feats = [c for c in win_train.columns
                 if c.startswith(("tm1_","tm2_","tm3_"))]

    # score on train
    me = me_score_features(win_train, pre_feats)
    if me.empty:
        return pd.DataFrame()

    rise_signals = me[me["me_score"] >= 2.0].head(top_k)["feature"].tolist()
    drop_signals = me[me["me_score"] <= 0.5].sort_values("me_score").head(top_k)["feature"].tolist()

    records = []
    for direction, signals in [("rise", rise_signals), ("drop", drop_signals)]:
        for feat in signals:
            if feat not in win_test.columns:
                continue
            # binary signals: feature == 1.0; continuous: above median
            feat_vals = win_test[feat]
            if set(feat_vals.dropna().unique()).issubset({0.0, 1.0}):
                mask = feat_vals == 1.0
            else:
                median = feat_vals.median()
                mask   = feat_vals > median if direction == "rise" else feat_vals < median

            matched = win_test[mask]
            if len(matched) < min_obs:
                continue

            for fh in [1, 2, 3]:
                col = f"fwd_ret_{fh}"
                if col not in matched.columns:
                    continue
                rets = matched[col].dropna()
                if direction == "rise":
                    wins  = (rets > 0).mean()
                    mean  = rets.mean()
                else:
                    # drop signal: we'd short, so flip sign
                    wins  = (rets < 0).mean()
                    mean  = -rets.mean()
                sharpe = (rets.mean() / rets.std() * (252*78)**0.5
                          if rets.std() > 0 else 0)
                records.append({
                    "signal":     feat,
                    "direction":  direction,
                    "horizon":    fh,
                    "n_events":   len(rets),
                    "win_rate":   _r(wins, 4),
                    "mean_ret_pct": _r(mean, 4),
                    "sharpe_ann": _r(sharpe, 3),
                })

    return pd.DataFrame(records)

# ── report builder ────────────────────────────────────────────────────────────
def build_report(me_pre: pd.DataFrame, me_post: pd.DataFrame,
                 wf: pd.DataFrame, meta: dict) -> str:
    lines = [
        "# Candle Window Study — 3 Before / 3 After",
        "",
        f"**Tickers:** {meta['n_tickers']:,}  |  "
        f"**Events:** {meta['n_events']:,}  |  "
        f"**Date range:** {meta['date_min']} -> {meta['date_max']}",
        "",
        "## Pre-Event Setup Fingerprint (t-1 / t-2 / t-3 features)",
        "",
        "### Top 10 Rise Predictors (ME >= 2.0)",
        "",
    ]
    top_r = me_pre[me_pre["me_score"] >= 2.0].head(10)
    if top_r.empty:
        lines.append("_None found_")
    else:
        lines.append(top_r[["feature","me_score","rise_lift","drop_lift","effect_size","p_value"]].to_markdown(index=False))
    lines += ["", "### Top 10 Drop Predictors (ME <= 0.5)", ""]
    top_d = me_pre[me_pre["me_score"] <= 0.5].sort_values("me_score").head(10)
    if top_d.empty:
        lines.append("_None found_")
    else:
        lines.append(top_d[["feature","me_score","rise_lift","drop_lift","effect_size","p_value"]].to_markdown(index=False))

    lines += ["", "## Post-Event Fingerprint (t+1 / t+2 / t+3 features)", "",
              "Shows what the 3 candles AFTER an event typically look like — useful for continuation vs reversal detection.",
              "", "### Features most associated with post-rise continuation", ""]
    post_r = me_post[me_post["me_score"] >= 2.0].head(10)
    lines.append(post_r[["feature","me_score","effect_size"]].to_markdown(index=False) if not post_r.empty else "_None_")

    lines += ["", "## Walk-Forward Backtest", "",
              f"Train: first {int(meta['train_frac']*100)}% of events  |  "
              f"Test: last {int((1-meta['train_frac'])*100)}% of events",
              ""]
    if wf.empty:
        lines.append("_No signals met minimum observation threshold_")
    else:
        best = wf.sort_values("sharpe_ann", ascending=False).head(15)
        lines.append(best.to_markdown(index=False))

    lines += ["", "---", f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_"]
    return "\n".join(lines)

# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir",  default=str(DATA_DIR))
    ap.add_argument("--tickers",   nargs="*")
    ap.add_argument("--sample",    type=int, default=0)
    ap.add_argument("--top-k",     type=int, default=TOP_K)
    ap.add_argument("--horizon",   type=int, default=3)
    ap.add_argument("--dry-run",   action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    groups   = discover(data_dir)
    tickers  = args.tickers or sorted(groups.keys())
    if args.sample and args.sample < len(tickers):
        import random; random.seed(42)
        tickers = random.sample(tickers, args.sample)

    print(f"\n=== Candle Window Study (window={WINDOW}) ===")
    print(f"Dir     : {data_dir}")
    print(f"Tickers : {len(tickers):,}")

    # Streaming accumulators — we never hold all windows in RAM.
    # For ME scoring: collect per-feature (rise_vals, drop_vals) in chunks.
    # For walk-forward: store only (ts, event, pre-feat values, fwd_rets) — a
    # slim slice, not the full window.
    CHUNK = 50_000          # flush accumulated rows every N events
    pre_feats_order = [f"{pfx}_{b}" for pfx in ("tm3","tm2","tm1")
                        for b in BASE_FEATS]
    post_feats_order = [f"{pfx}_{b}" for pfx in ("tp1","tp2","tp3")
                        for b in BASE_FEATS]
    slim_cols = ["ts","event"] + pre_feats_order + [f"fwd_ret_{h}" for h in (1,2,3)]

    # running Mann-Whitney accumulators: {feat: {"rise": [], "drop": []}}
    pre_acc:  dict[str, dict[str, list]] = {f: {"rise":[],"drop":[]} for f in pre_feats_order}
    post_acc: dict[str, dict[str, list]] = {f: {"rise":[],"drop":[]} for f in post_feats_order}

    # slim rows for walk-forward (keep in RAM — one float per pre-feat per event)
    slim_rows: list[dict] = []

    errors    = []
    n_events  = 0
    date_min  = "9999-12-31"
    date_max  = "0001-01-01"

    for i, ticker in enumerate(tickers, 1):
        try:
            df = load_ticker(groups[ticker])
            df = compute_features(df)

            # label events
            hi = df["candle_ret"].quantile(1 - PERCENTILE/100)
            lo = df["candle_ret"].quantile(PERCENTILE/100)
            df["event"] = pd.Series(None, index=df.index, dtype=object)
            df.loc[df["candle_ret"] >= hi, "event"] = "rise"
            df.loc[df["candle_ret"] <= lo, "event"] = "drop"

            win = extract_windows(df, w=WINDOW)
            if win.empty:
                continue

            n_events += len(win)
            ts_min = str(win["ts"].min())[:10]
            ts_max = str(win["ts"].max())[:10]
            if ts_min < date_min: date_min = ts_min
            if ts_max > date_max: date_max = ts_max

            # stream into accumulators
            for feat in pre_feats_order:
                if feat not in win.columns:
                    continue
                r = win.loc[win["event"]=="rise", feat].dropna().tolist()
                d = win.loc[win["event"]=="drop", feat].dropna().tolist()
                pre_acc[feat]["rise"].extend(r)
                pre_acc[feat]["drop"].extend(d)

            for feat in post_feats_order:
                if feat not in win.columns:
                    continue
                r = win.loc[win["event"]=="rise", feat].dropna().tolist()
                d = win.loc[win["event"]=="drop", feat].dropna().tolist()
                post_acc[feat]["rise"].extend(r)
                post_acc[feat]["drop"].extend(d)

            # slim rows for walk-forward
            for _, row in win.iterrows():
                slim: dict = {"ts": row["ts"], "event": row["event"]}
                for f in pre_feats_order:
                    slim[f] = row.get(f, np.nan)
                for h in (1,2,3):
                    slim[f"fwd_ret_{h}"] = row.get(f"fwd_ret_{h}", np.nan)
                slim_rows.append(slim)

            if i % 200 == 0 or i == len(tickers):
                print(f"  [{i}/{len(tickers)}] {ticker:8s}  events={n_events:,}", flush=True)

        except Exception as e:
            errors.append((ticker, str(e)))

    if n_events == 0:
        print("No windows extracted. Check --data-dir and parquet schema.")
        sys.exit(1)

    print(f"\n=== Summary ===")
    n_rise = sum(1 for r in slim_rows if r["event"]=="rise")
    n_drop = sum(1 for r in slim_rows if r["event"]=="drop")
    print(f"  Total events : {n_events:,}  (rise={n_rise:,}  drop={n_drop:,})")
    print(f"  Tickers OK   : {len(tickers) - len(errors):,}   Errors: {len(errors)}")
    print(f"  Date range   : {date_min} -> {date_max}")

    # build ME score tables from accumulators
    def acc_to_me(acc: dict[str, dict[str, list]]) -> pd.DataFrame:
        rows = []
        for feat, buckets in acc.items():
            rv = np.array(buckets["rise"], dtype=float)
            dv = np.array(buckets["drop"], dtype=float)
            if len(rv) < 10 or len(dv) < 10:
                continue
            try:
                u, p = stats.mannwhitneyu(rv, dv, alternative="two-sided")
                n    = len(rv) * len(dv)
                is_binary = set(np.unique(np.concatenate([rv,dv]))).issubset({0.0,1.0})
                if is_binary:
                    r_rate = rv.mean(); d_rate = dv.mean()
                    rise_lift = r_rate/d_rate if d_rate>1e-9 else np.nan
                    drop_lift = d_rate/r_rate if r_rate>1e-9 else np.nan
                    me  = rise_lift/drop_lift if (not np.isnan(rise_lift) and not np.isnan(drop_lift) and drop_lift>0) else np.nan
                    eff = _r(rise_lift-1, 4)
                else:
                    rise_lift = drop_lift = np.nan
                    cd  = (2*u/n)-1
                    me  = np.exp(abs(cd)*3)*np.sign(cd)
                    eff = _r(cd, 4)
                rows.append({"feature":feat,"me_score":_r(me,4),"rise_lift":_r(rise_lift,4),
                             "drop_lift":_r(drop_lift,4),"effect_size":eff,"p_value":_r(p,6),
                             "n_rise":len(rv),"n_drop":len(dv)})
            except Exception:
                continue
        df = pd.DataFrame(rows).dropna(subset=["me_score"])
        return df.sort_values("me_score", ascending=False)

    print("\nScoring pre-event setup features (tm1/tm2/tm3) ...")
    me_pre = acc_to_me(pre_acc)
    print(f"  Pre-event features scored: {len(me_pre)}")

    print("Scoring post-event features (tp1/tp2/tp3) ...")
    me_post = acc_to_me(post_acc)
    print(f"  Post-event features scored: {len(me_post)}")

    # walk-forward backtest on slim_rows
    print(f"Walk-forward backtest (top {args.top_k} signals) ...")
    win_df = pd.DataFrame(slim_rows).sort_values("ts")
    split  = int(len(win_df) * TRAIN_FRAC)
    train  = win_df.iloc[:split]
    test   = win_df.iloc[split:]
    print(f"  Train events : {len(train):,}   Test events: {len(test):,}")
    wf = wf_backtest(train, test, top_k=args.top_k)
    print(f"  Signal/horizon rows: {len(wf)}")

    # console preview
    print("\n=== TOP RISE SETUP SIGNALS (pre-event, ME >= 2.0) ===")
    top_r = me_pre[me_pre["me_score"] >= 2.0].head(10)
    if not top_r.empty:
        cols = [c for c in ["feature","me_score","effect_size","p_value"] if c in top_r.columns]
        print(top_r[cols].to_string(index=False))
    else:
        print("  None")

    print("\n=== TOP DROP SETUP SIGNALS (pre-event, ME <= 0.5) ===")
    top_d = me_pre[me_pre["me_score"] <= 0.5].sort_values("me_score").head(10)
    if not top_d.empty:
        cols = [c for c in ["feature","me_score","effect_size","p_value"] if c in top_d.columns]
        print(top_d[cols].to_string(index=False))
    else:
        print("  None")

    if not wf.empty:
        print("\n=== WALK-FORWARD BACKTEST — Top 10 by Sharpe ===")
        best = wf.sort_values("sharpe_ann", ascending=False).head(10)
        print(best.to_string(index=False))

    meta = dict(n_tickers=len(tickers)-len(errors), n_events=len(win_df),
                date_min=date_min, date_max=date_max, train_frac=TRAIN_FRAC)
    report = build_report(me_pre, me_post, wf, meta)

    ts_tag = datetime.now().strftime("%Y%m%d_%H%M")
    out_base = data_dir.parent / "candle_window_results"
    out_base.mkdir(exist_ok=True)

    (out_base / "CANDLE_WINDOW_REPORT.md").write_text(report, encoding="utf-8")
    me_pre.to_csv(out_base / "window_me_pre.csv",  index=False)
    me_post.to_csv(out_base / "window_me_post.csv", index=False)
    if not wf.empty:
        wf.to_csv(out_base / "window_wf_backtest.csv", index=False)

    if not args.dry_run:
        commit = f"[candle-window] {ts_tag} {len(tickers)} tickers {len(win_df):,} events"
        github_push("reports/CANDLE_WINDOW_REPORT.md",    report,                    commit)
        github_push("reports/window_me_pre.csv",          me_pre.to_csv(index=False), commit)
        github_push("reports/window_me_post.csv",         me_post.to_csv(index=False),commit)
        if not wf.empty:
            github_push("reports/window_wf_backtest.csv", wf.to_csv(index=False),    commit)
    else:
        print(f"\n[dry-run] Saved to {out_base}")

    print("\nDone.")

if __name__ == "__main__":
    main()
