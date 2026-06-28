"""
5-Minute Candle Mutual Exclusivity Study
=========================================
Schema (confirmed from Alpaca IEX parquets):
  ticker | ts (datetime64[us, UTC-08:00]) | timeframe | open | high | low | close | volume | source

Reads local parquet files (one or more per ticker), deduplicates on (ticker,ts),
labels Rise/Drop events, extracts TA features on the 2 candles BEFORE each event,
computes mutual-exclusivity scores, validates statistically, and auto-pushes
results to GitHub.

Usage:
    python scripts/candle_me_study.py [--data-dir PATH] [--tickers AAPL MSFT ...]
                                      [--sample N] [--dry-run] [--schema-check]
"""

from __future__ import annotations
import os, sys, argparse, json, base64, time, warnings
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR      = Path(os.environ.get("CANDLE_DATA_DIR", r"C:\Atlas\data\5m"))
GITHUB_REPO   = "Thirdeye2112/atlas-research"
GITHUB_BRANCH = "main"

# Event labelling — percentile per ticker
USE_PERCENTILE     = True
PERCENTILE_CUTOFF  = 10    # top / bottom 10 % of candle returns → Rise / Drop

# Fallback fixed thresholds (used when USE_PERCENTILE=False)
RISE_PCT_THRESHOLD = 0.40
DROP_PCT_THRESHOLD = 0.40

SESSION_BUCKETS = {
    "open_30m":   (570, 600),   # 09:30 – 10:00  (minutes since midnight)
    "mid_early":  (600, 690),   # 10:00 – 11:30
    "lunch":      (690, 840),   # 11:30 – 14:00
    "power_hour": (900, 960),   # 15:00 – 16:00
}

# ─────────────────────────────────────────────────────────────────────────────
# GitHub helper
# ─────────────────────────────────────────────────────────────────────────────

def github_push_file(path_in_repo: str, content: str | bytes, msg: str) -> bool:
    try:
        import urllib.request
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("  WARN: GITHUB_TOKEN not set — skipping push")
            return False
        api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path_in_repo}"
        hdrs = {
            "Authorization": f"token {token}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
            "User-Agent":    "atlas-research-bot",
        }
        sha = None
        try:
            req = urllib.request.Request(api, headers=hdrs)
            with urllib.request.urlopen(req) as r:
                sha = json.loads(r.read()).get("sha")
        except Exception:
            pass
        if isinstance(content, str):
            content = content.encode("utf-8")
        payload: dict = {"message": msg,
                         "content": base64.b64encode(content).decode("ascii"),
                         "branch":  GITHUB_BRANCH}
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                     headers=hdrs, method="PUT")
        with urllib.request.urlopen(req) as r:
            status = r.status
        print(f"  GitHub → {path_in_repo}  [{status}]")
        return status in (200, 201)
    except Exception as e:
        print(f"  GitHub push FAILED: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Parquet loading — groups multiple files per ticker, deduplicates
# ─────────────────────────────────────────────────────────────────────────────

def discover_files(data_dir: Path) -> dict[str, list[Path]]:
    """Return {ticker: [file, ...]} — groups files by ticker prefix in filename."""
    all_files = sorted(data_dir.glob("*.parquet")) or sorted(data_dir.rglob("*.parquet"))
    groups: dict[str, list[Path]] = defaultdict(list)
    for f in all_files:
        # Stem like AAPL_1782578339692 → ticker = AAPL
        ticker = f.stem.split("_")[0].upper()
        groups[ticker].append(f)
    return dict(groups)


def load_ticker(files: list[Path]) -> pd.DataFrame:
    """Load, concatenate, and deduplicate all files for one ticker."""
    frames = []
    for f in files:
        df = pd.read_parquet(f, engine="pyarrow",
                             columns=["ticker", "ts", "open", "high", "low", "close", "volume"])
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    # Normalise timestamp to tz-naive UTC for consistency
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)

    # Deduplicate (handles duplicate files)
    df = df.drop_duplicates(subset=["ticker", "ts"])
    df = df.sort_values("ts").reset_index(drop=True)

    # Ensure numeric OHLCV
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

# ─────────────────────────────────────────────────────────────────────────────
# Feature computation  (operates on one ticker's sorted df)
# ─────────────────────────────────────────────────────────────────────────────

def add_ema(s: pd.Series, p: int) -> pd.Series:
    return s.ewm(span=p, adjust=False).mean()

def add_rsi(close: pd.Series, p: int = 14) -> pd.Series:
    d = close.diff()
    g = d.clip(lower=0).ewm(com=p-1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=p-1, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def add_vwap_session(df: pd.DataFrame) -> pd.Series:
    """Session VWAP — resets each calendar date."""
    df = df.copy()
    df["_d"]   = df["ts"].dt.date
    df["_tp"]  = (df["high"] + df["low"] + df["close"]) / 3
    cum_tpv = df.groupby("_d").apply(lambda g: (g["_tp"] * g["volume"]).cumsum()).reset_index(level=0, drop=True)
    cum_v   = df.groupby("_d")["volume"].cumsum()
    return cum_tpv / cum_v.replace(0, np.nan)

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    # ── Candle anatomy ────────────────────────────────────────────────────
    df["body_pct"]        = (c - o).abs() / o.replace(0,np.nan) * 100
    df["body_dir"]        = np.sign(c - o).astype(float)          # +1 bull / -1 bear
    df["range"]           = h - l
    df["upper_wick"]      = h - np.maximum(o, c)
    df["lower_wick"]      = np.minimum(o, c) - l
    rng = df["range"].replace(0, np.nan)
    df["upper_wick_pct"]  = df["upper_wick"] / rng * 100
    df["lower_wick_pct"]  = df["lower_wick"] / rng * 100
    df["body_to_range"]   = df["body_pct"] / (rng / c.replace(0,np.nan) * 100)
    df["inside_bar"]      = ((h < h.shift(1)) & (l > l.shift(1))).astype(float)
    df["outside_bar"]     = ((h > h.shift(1)) & (l < l.shift(1))).astype(float)
    df["upper_dom"]       = (df["upper_wick"] > df["lower_wick"] * 1.5).astype(float)
    df["lower_dom"]       = (df["lower_wick"] > df["upper_wick"] * 1.5).astype(float)
    df["hammer"]          = ((df["lower_wick_pct"] > 60) & (df["body_to_range"] < 0.35)).astype(float)
    df["shooting_star"]   = ((df["upper_wick_pct"] > 60) & (df["body_to_range"] < 0.35)).astype(float)

    # Consecutive direction streak (resets across sessions)
    dirs = df["body_dir"].values
    streak = np.zeros(len(dirs))
    s = 0.0
    for i, d in enumerate(dirs):
        if d == np.sign(s) and d != 0:
            s += d
        else:
            s = d
        streak[i] = s
    df["consec_dir"] = streak

    # ── Volume ────────────────────────────────────────────────────────────
    vol_ma20          = v.rolling(20, min_periods=1).mean()
    vol_ma5           = v.rolling(5,  min_periods=1).mean()
    df["vol_ratio_20"] = v / vol_ma20.replace(0, np.nan)
    df["vol_ratio_5"]  = v / vol_ma5.replace(0, np.nan)
    df["vol_expanding"]= (v > v.shift(1)).astype(float)
    df["vol_climax"]   = (df["vol_ratio_20"] > 3.0).astype(float)
    df["vol_dry"]      = (df["vol_ratio_20"] < 0.4).astype(float)

    # ── EMAs ─────────────────────────────────────────────────────────────
    df["ema9"]          = add_ema(c, 9)
    df["ema20"]         = add_ema(c, 20)
    df["ema50"]         = add_ema(c, 50)
    df["above_ema9"]    = (c > df["ema9"]).astype(float)
    df["above_ema20"]   = (c > df["ema20"]).astype(float)
    df["above_ema50"]   = (c > df["ema50"]).astype(float)
    df["above_all_emas"]= ((c > df["ema9"]) & (c > df["ema20"]) & (c > df["ema50"])).astype(float)
    df["below_all_emas"]= ((c < df["ema9"]) & (c < df["ema20"]) & (c < df["ema50"])).astype(float)
    df["ema9_bull_stack"]= (df["ema9"] > df["ema20"]).astype(float)
    df["dist_ema9_pct"] = (c - df["ema9"])  / df["ema9"].replace(0,np.nan) * 100
    df["dist_ema20_pct"]= (c - df["ema20"]) / df["ema20"].replace(0,np.nan) * 100

    # ── RSI ───────────────────────────────────────────────────────────────
    df["rsi"]           = add_rsi(c, 14)
    df["rsi_slope"]     = df["rsi"].diff(2)
    df["rsi_above50"]   = (df["rsi"] > 50).astype(float)
    df["rsi_above70"]   = (df["rsi"] > 70).astype(float)
    df["rsi_below30"]   = (df["rsi"] < 30).astype(float)
    df["rsi_reclaim50"] = ((df["rsi"] > 50) & (df["rsi"].shift(1) < 50)).astype(float)
    df["rsi_lose50"]    = ((df["rsi"] < 50) & (df["rsi"].shift(1) > 50)).astype(float)

    # ── Bollinger Bands ───────────────────────────────────────────────────
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    bb_up  = bb_mid + 2 * bb_std
    bb_lo  = bb_mid - 2 * bb_std
    bb_rng = (bb_up - bb_lo).replace(0, np.nan)
    df["bb_pct"]         = (c - bb_lo) / bb_rng          # 0-1
    df["bb_width"]       = bb_rng / bb_mid.replace(0,np.nan) * 100
    df["bb_squeeze"]     = (df["bb_width"] < df["bb_width"].rolling(20).quantile(0.20)).astype(float)
    df["above_bb_upper"] = (c > bb_up).astype(float)
    df["below_bb_lower"] = (c < bb_lo).astype(float)

    # ── VWAP ─────────────────────────────────────────────────────────────
    try:
        df["vwap"]       = add_vwap_session(df)
        df["above_vwap"] = (c > df["vwap"]).astype(float)
        df["vwap_dist_pct"] = (c - df["vwap"]) / df["vwap"].replace(0,np.nan) * 100
    except Exception:
        df["vwap"] = df["above_vwap"] = df["vwap_dist_pct"] = np.nan

    # ── ATR ───────────────────────────────────────────────────────────────
    tr = pd.concat([(h-l), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"]            = tr.ewm(com=13, adjust=False).mean()
    df["atr_pct"]        = df["atr"] / c.replace(0,np.nan) * 100
    df["atr_expansion"]  = df["atr"] / df["atr"].rolling(5).mean().replace(0,np.nan)

    # ── MACD ─────────────────────────────────────────────────────────────
    macd = add_ema(c,12) - add_ema(c,26)
    sig  = add_ema(macd, 9)
    df["macd_hist"]       = macd - sig
    df["macd_above_sig"]  = (macd > sig).astype(float)
    df["macd_hist_rising"]= (df["macd_hist"] > df["macd_hist"].shift(1)).astype(float)
    df["macd_bull_cross"] = ((macd > sig) & (macd.shift(1) <= sig.shift(1))).astype(float)
    df["macd_bear_cross"] = ((macd < sig) & (macd.shift(1) >= sig.shift(1))).astype(float)

    # ── Session / time ────────────────────────────────────────────────────
    mins = df["ts"].dt.hour * 60 + df["ts"].dt.minute
    df["session_mins"]    = mins
    df["session_bucket"]  = "other"
    for name, (s, e) in SESSION_BUCKETS.items():
        df.loc[(mins >= s) & (mins < e), "session_bucket"] = name
    df["is_power_hour"]   = (df["session_bucket"] == "power_hour").astype(float)
    df["is_open_30m"]     = (df["session_bucket"] == "open_30m").astype(float)
    df["day_of_week"]     = df["ts"].dt.dayofweek.astype(float)  # 0=Mon,4=Fri

    # Opening gap (first bar of each session)
    df["_date"]           = df["ts"].dt.date
    new_session           = df["_date"] != df["_date"].shift(1)
    df["gap_pct"]         = np.where(new_session,
                                (o - c.shift(1)) / c.shift(1).replace(0,np.nan) * 100,
                                np.nan)

    # ── C-2 → C-1 look-back features ─────────────────────────────────────
    df["prev1_body_pct"]  = df["body_pct"].shift(1)
    df["prev1_body_dir"]  = df["body_dir"].shift(1)
    df["prev1_vol_ratio"] = df["vol_ratio_20"].shift(1)
    df["prev1_rsi"]       = df["rsi"].shift(1)
    df["prev1_bb_pct"]    = df["bb_pct"].shift(1)
    df["prev1_upper_wick"]= df["upper_wick_pct"].shift(1)
    df["prev1_lower_wick"]= df["lower_wick_pct"].shift(1)
    df["prev2_body_pct"]  = df["body_pct"].shift(2)
    df["prev2_body_dir"]  = df["body_dir"].shift(2)
    df["prev2_vol_ratio"] = df["vol_ratio_20"].shift(2)
    df["prev2_rsi"]       = df["rsi"].shift(2)

    # Multi-bar transitions
    df["prior2_aligned_bull"] = ((df["prev1_body_dir"] > 0) & (df["prev2_body_dir"] > 0)).astype(float)
    df["prior2_aligned_bear"] = ((df["prev1_body_dir"] < 0) & (df["prev2_body_dir"] < 0)).astype(float)
    df["vol_accel_into"]      = (df["vol_ratio_20"] > df["prev1_vol_ratio"]).astype(float)
    df["range_expanding_into"]= (df["range"] > df["range"].shift(1)).astype(float)

    # C-2 inside → C-1 break = compression + expansion setup
    df["compression_breakout"]= (df["inside_bar"].shift(1) > 0).astype(float)

    # Candle return for event labelling
    df["candle_ret"]      = (c - o) / o.replace(0, np.nan) * 100

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Event labelling
# ─────────────────────────────────────────────────────────────────────────────

def label_events(df: pd.DataFrame) -> pd.DataFrame:
    cr = df["candle_ret"]
    if USE_PERCENTILE:
        r_thresh = np.nanpercentile(cr, 100 - PERCENTILE_CUTOFF)
        d_thresh = np.nanpercentile(cr, PERCENTILE_CUTOFF)
    else:
        r_thresh =  RISE_PCT_THRESHOLD
        d_thresh = -DROP_PCT_THRESHOLD

    df = df.copy()
    df["event"]      = None
    df.loc[cr >= r_thresh, "event"] = "rise"
    df.loc[cr <= d_thresh, "event"] = "drop"

    # Forward-bar context (what happened next)
    for s in [1, 2]:
        df[f"next{s}_ret"] = df["candle_ret"].shift(-s)

    return df, float(r_thresh), float(d_thresh)


# ─────────────────────────────────────────────────────────────────────────────
# ME engine
# ─────────────────────────────────────────────────────────────────────────────

BINARY_FEATURES = [
    "body_dir", "inside_bar", "outside_bar", "upper_dom", "lower_dom",
    "hammer", "shooting_star",
    "vol_expanding", "vol_climax", "vol_dry",
    "above_ema9", "above_ema20", "above_ema50", "above_all_emas", "below_all_emas",
    "ema9_bull_stack",
    "rsi_above50", "rsi_above70", "rsi_below30", "rsi_reclaim50", "rsi_lose50",
    "bb_squeeze", "above_bb_upper", "below_bb_lower",
    "above_vwap",
    "macd_above_sig", "macd_hist_rising", "macd_bull_cross", "macd_bear_cross",
    "is_power_hour", "is_open_30m",
    "prior2_aligned_bull", "prior2_aligned_bear",
    "compression_breakout", "vol_accel_into", "range_expanding_into",
    "prev1_body_dir", "prev2_body_dir",
]

CONTINUOUS_FEATURES = [
    "body_pct", "upper_wick_pct", "lower_wick_pct", "body_to_range",
    "vol_ratio_20", "vol_ratio_5",
    "dist_ema9_pct", "dist_ema20_pct",
    "rsi", "rsi_slope",
    "bb_pct", "bb_width",
    "vwap_dist_pct",
    "atr_pct", "atr_expansion",
    "macd_hist",
    "consec_dir",
    "prev1_body_pct", "prev1_rsi", "prev1_vol_ratio",
    "prev1_upper_wick", "prev1_lower_wick", "prev1_bb_pct",
    "prev2_body_pct", "prev2_rsi",
    "gap_pct",
]


def compute_me_scores(events_df: pd.DataFrame) -> pd.DataFrame:
    rise = events_df[events_df["event"] == "rise"]
    drop = events_df[events_df["event"] == "drop"]

    records = []

    # Binary
    for feat in BINARY_FEATURES:
        if feat not in events_df.columns:
            continue
        def act(df_):
            col = pd.to_numeric(df_[feat], errors="coerce")
            n   = col.notna().sum()
            pos = (col > 0).sum()
            return int(pos), int(n)

        rn, rt = act(rise)
        dn, dt = act(drop)
        bn, bt = act(events_df)
        if bt == 0: continue

        br = bn / bt
        rr = rn / rt if rt else np.nan
        dr = dn / dt if dt else np.nan
        rl = rr / br  if br > 0 else np.nan
        dl = dr / br  if br > 0 else np.nan
        me = rl / dl  if dl and dl > 0 else np.nan

        try:
            ct = np.array([[rn, rt-rn], [dn, dt-dn]])
            chi2, p, _, _ = stats.chi2_contingency(ct, correction=False)
            cv = np.sqrt(chi2 / (ct.sum() * max(1, min(ct.shape)-1)))
        except Exception:
            p, cv = np.nan, np.nan

        records.append(dict(feature=feat, type="binary",
                            rise_rate=_r(rr*100), drop_rate=_r(dr*100), base_rate=_r(br*100),
                            rise_lift=_r(rl), drop_lift=_r(dl), me_score=_r(me),
                            p_value=_r(p,6), effect_size=_r(cv,4), n_rise=rt, n_drop=dt,
                            direction="rise" if (me or 1)>1 else "drop"))

    # Continuous — use Cliff's delta mapped to ME scale
    # Avoids division-by-zero when base mean is near 0 (e.g. macd_hist, rsi_slope)
    # Cliff delta +1 → ME=∞ (perfect rise), 0 → ME=1 (neutral), -1 → ME=0 (perfect drop)
    for feat in CONTINUOUS_FEATURES:
        if feat not in events_df.columns:
            continue
        rv = rise[feat].dropna().values
        dv = drop[feat].dropna().values
        if len(rv) < 10 or len(dv) < 10:
            continue

        try:
            u, p = stats.mannwhitneyu(rv, dv, alternative="two-sided")
            cd   = (2 * u / (len(rv) * len(dv))) - 1
        except Exception:
            p, cd = np.nan, np.nan

        rm = float(np.nanmean(rv))
        dm = float(np.nanmean(dv))
        eps = 1e-6
        if not np.isnan(cd):
            me = (1 + cd + eps) / (1 - cd + eps)
        else:
            me = np.nan

        records.append(dict(feature=feat, type="continuous",
                            rise_mean=_r(rm,4), drop_mean=_r(dm,4),
                            cliff_delta=_r(cd,4) if not np.isnan(cd) else None,
                            rise_lift=None, drop_lift=None, me_score=_r(me),
                            p_value=_r(p,6), effect_size=_r(abs(cd),4) if not np.isnan(cd) else None,
                            n_rise=len(rv), n_drop=len(dv),
                            direction="rise_higher" if rm>dm else "drop_higher"))

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # BH FDR correction
    pv   = df["p_value"].fillna(1.0).values
    n    = len(pv)
    ord_ = np.argsort(pv)
    bh   = np.array([(i+1)/n*0.05 for i in range(n)])
    pass_ = pv[ord_] <= bh
    fdr  = np.zeros(n, dtype=bool)
    if pass_.any():
        fdr[ord_[:np.where(pass_)[0].max()+1]] = True
    df["fdr_pass"] = fdr

    return df.sort_values("me_score", ascending=False).reset_index(drop=True)


def _r(v, d=3):
    if v is None: return None
    try:
        f = float(v)
        return None if np.isnan(f) else round(f, d)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Session stratification
# ─────────────────────────────────────────────────────────────────────────────

def stratify_by_session(events_df: pd.DataFrame, top_feats: list[str]) -> pd.DataFrame:
    # Cap at 2M rows to avoid OOM on full-universe datasets
    if len(events_df) > 2_000_000:
        events_df = events_df.sample(n=2_000_000, random_state=42)
    rows = []
    for bucket in events_df["session_bucket"].unique():
        sub  = events_df[events_df["session_bucket"] == bucket]
        rise = sub[sub["event"] == "rise"]
        drop = sub[sub["event"] == "drop"]
        if len(rise) < 20 or len(drop) < 20:
            continue
        for feat in top_feats:
            if feat not in sub.columns:
                continue
            rv = rise[feat].dropna().values
            dv = drop[feat].dropna().values
            if len(rv) < 5 or len(dv) < 5:
                continue
            try:
                u, p = stats.mannwhitneyu(rv, dv, alternative="two-sided")
                cd   = (2*u/(len(rv)*len(dv))) - 1
            except Exception:
                p, cd = np.nan, np.nan
            rows.append(dict(session=bucket, feature=feat,
                             rise_mean=_r(float(np.nanmean(rv)),4),
                             drop_mean=_r(float(np.nanmean(dv)),4),
                             effect_size=_r(abs(cd),4) if not np.isnan(cd) else None,
                             p_value=_r(p,6), n_rise=len(rv), n_drop=len(dv)))
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Report builder
# ─────────────────────────────────────────────────────────────────────────────

def build_report(me_df: pd.DataFrame, sess_df: pd.DataFrame, meta: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def tbl(df_, cols):
        if df_.empty: return "_None passed filters._\n"
        hdr = "| " + " | ".join(cols) + " |"
        sep = "|" + "|".join(["---"]*len(cols)) + "|"
        rows_ = []
        for _, r in df_.iterrows():
            cells = []
            for c in cols:
                v = r.get(c)
                if isinstance(v, float) and not np.isnan(v): cells.append(f"{v:.4f}")
                elif v is None or (isinstance(v, float) and np.isnan(v)): cells.append("—")
                else: cells.append(str(v))
            rows_.append("| " + " | ".join(cells) + " |")
        return "\n".join([hdr, sep] + rows_) + "\n"

    rc = ["feature","type","rise_lift","drop_lift","me_score","effect_size","p_value","fdr_pass"]

    rise_preds = me_df[(me_df["me_score"] >= 2.0) & me_df["fdr_pass"]].head(20)
    drop_preds = me_df[(me_df["me_score"] <= 0.5) & me_df["fdr_pass"]].sort_values("me_score").head(20)
    neutral    = me_df[(me_df["me_score"]> 0.8) & (me_df["me_score"]<1.25)].head(10)

    top10 = (rise_preds["feature"].tolist()[:5] + drop_preds["feature"].tolist()[:5])
    sess_sub = sess_df[sess_df["feature"].isin(top10)] if not sess_df.empty else pd.DataFrame()

    return "\n".join([
        "# 5-Minute Candle Mutual Exclusivity Report",
        f"",
        f"**Generated:** {ts}  ",
        f"**Tickers:** {meta.get('n_tickers',0):,}  |  "
        f"**Candles:** {meta.get('n_candles',0):,}  |  "
        f"**Date range:** {meta.get('date_range','?')}",
        f"**Rise events:** {meta.get('n_rise',0):,}  |  "
        f"**Drop events:** {meta.get('n_drop',0):,}  |  "
        f"**Labelling:** top/bottom {PERCENTILE_CUTOFF}% candle return per ticker",
        f"",
        "---",
        "## Method",
        "- Features extracted from **C-2** and **C-1** (2 bars before the event candle C-0)",
        "- **ME score** = rise_lift ÷ drop_lift",
        "  - ME ≥ 2 → fires ≥2× more before rises → **Rise signal**",
        "  - ME ≤ 0.5 → fires ≥2× more before drops → **Drop signal**",
        "- Stats: χ² (binary) / Mann-Whitney U (continuous) + BH FDR α=0.05",
        "- Effect size: Cramér's V (binary) / Cliff's δ (continuous)",
        "---",
        "## 1. Rise Predictors (ME ≥ 2.0, FDR pass)",
        tbl(rise_preds, rc),
        "---",
        "## 2. Drop Predictors (ME ≤ 0.5, FDR pass)",
        tbl(drop_preds, rc),
        "---",
        "## 3. Neutral Features (0.8 < ME < 1.25)",
        tbl(neutral, ["feature","type","me_score","p_value"]),
        "---",
        "## 4. Session-of-Day Stratification (top 10 features)",
        tbl(sess_sub, ["session","feature","rise_mean","drop_mean","effect_size","p_value","n_rise","n_drop"]),
        "---",
        "_Full table: `reports/candle_me_full.csv`  |  "
        "Session table: `reports/candle_me_session.csv`_",
        f"",
        "_Generated by `scripts/candle_me_study.py`_",
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir",     default=str(DATA_DIR))
    ap.add_argument("--tickers",      nargs="+", default=None)
    ap.add_argument("--sample",       type=int,  default=None,
                    help="Process only N randomly-chosen tickers (quick test)")
    ap.add_argument("--schema-check", action="store_true")
    ap.add_argument("--dry-run",      action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: directory not found: {data_dir}")
        print("Set CANDLE_DATA_DIR env var or pass --data-dir PATH")
        sys.exit(1)

    # Schema check
    if args.schema_check:
        files = sorted(data_dir.glob("*.parquet")) or sorted(data_dir.rglob("*.parquet"))
        if not files:
            print("No parquet files found.")
            sys.exit(1)
        df = pd.read_parquet(files[0], engine="pyarrow")
        print(f"\n=== {files[0].name} ===  shape={df.shape}")
        print(df.dtypes.to_string())
        print(df.head(3).to_string())
        sys.exit(0)

    groups = discover_files(data_dir)
    if args.tickers:
        groups = {k: v for k, v in groups.items() if k in {t.upper() for t in args.tickers}}
    if args.sample:
        import random; keys = list(groups); random.shuffle(keys)
        groups = {k: groups[k] for k in keys[:args.sample]}

    tickers = sorted(groups)
    print(f"=== 5-Minute Candle ME Study ===")
    print(f"Dir     : {data_dir}")
    print(f"Tickers : {len(tickers):,}")
    print(f"Label   : top/bottom {PERCENTILE_CUTOFF}% candle return")
    print()

    all_events, n_candles, date_min, date_max, errors = [], 0, None, None, []

    for i, ticker in enumerate(tickers, 1):
        try:
            df = load_ticker(groups[ticker])
            if len(df) < 100:
                continue
            df = compute_features(df)
            df, r_thr, d_thr = label_events(df)
            n_candles += len(df)
            dm, dx = df["ts"].min(), df["ts"].max()
            if date_min is None or dm < date_min: date_min = dm
            if date_max is None or dx > date_max: date_max = dx
            all_events.append(df[df["event"].notna()].copy())

            if i % 200 == 0 or i == len(tickers):
                nr = sum((e["event"]=="rise").sum() for e in all_events)
                nd = sum((e["event"]=="drop").sum() for e in all_events)
                print(f"  [{i}/{len(tickers)}] {ticker:8s} "
                      f"candles={len(df):,}  R={nr:,} D={nd:,}"
                      f"  thresholds=[{d_thr:.2f}%,{r_thr:.2f}%]")
        except Exception as e:
            errors.append(f"{ticker}: {e}")
            if len(errors) <= 5:
                print(f"  WARN {ticker}: {e}")

    if not all_events:
        print("No events extracted. Verify --data-dir and parquet schema.")
        sys.exit(1)

    events_df = pd.concat(all_events, ignore_index=True)
    n_rise = int((events_df["event"]=="rise").sum())
    n_drop = int((events_df["event"]=="drop").sum())
    n_tickers = len(tickers) - len(errors)

    print(f"\n=== Summary ===")
    print(f"  Tickers  : {n_tickers:,}   Candles: {n_candles:,}")
    print(f"  Range    : {date_min} -> {date_max}")
    print(f"  Rise     : {n_rise:,}   Drop: {n_drop:,}")
    print(f"  Errors   : {len(errors)}")

    print("\nComputing ME scores ...")
    me_df = compute_me_scores(events_df)
    print(f"  Features  : {len(me_df)}")
    print(f"  FDR pass  : {me_df['fdr_pass'].sum()}")
    n_rise_sigs = int((me_df["me_score"] >= 2.0).sum())
    n_drop_sigs = int((me_df["me_score"] <= 0.5).sum())
    print(f"  Rise sigs : {n_rise_sigs}   Drop sigs: {n_drop_sigs}")

    top_feats = (me_df[me_df["me_score"]>=2.0]["feature"].head(5).tolist() +
                 me_df[me_df["me_score"]<=0.5]["feature"].head(5).tolist())
    sess_df = stratify_by_session(events_df, top_feats)

    meta = dict(n_tickers=n_tickers, n_candles=n_candles, n_rise=n_rise,
                n_drop=n_drop, date_range=f"{date_min} -> {date_max}")
    report_md = build_report(me_df, sess_df, meta)

    # Console preview
    print("\n=== TOP RISE PREDICTORS (ME ≥ 2.0) ===")
    top_r = me_df[me_df["me_score"]>=2.0].head(10)
    if not top_r.empty:
        cols = [c for c in ["feature","me_score","rise_lift","drop_lift","effect_size","p_value"] if c in top_r.columns]
        print(top_r[cols].to_string(index=False))
    else:
        print("  None")

    print("\n=== TOP DROP PREDICTORS (ME ≤ 0.5) ===")
    top_d = me_df[me_df["me_score"]<=0.5].sort_values("me_score").head(10)
    if not top_d.empty:
        cols = [c for c in ["feature","me_score","rise_lift","drop_lift","effect_size","p_value"] if c in top_d.columns]
        print(top_d[cols].to_string(index=False))
    else:
        print("  None")

    ts_tag = datetime.now().strftime("%Y%m%d_%H%M")
    if not args.dry_run:
        print("\n=== Pushing to GitHub ===")
        commit = f"[candle-me] {ts_tag} {n_tickers} tickers {n_candles:,} candles"
        github_push_file("reports/CANDLE_ME_REPORT.md",    report_md,               commit)
        github_push_file("reports/candle_me_full.csv",     me_df.to_csv(index=False), commit)
        github_push_file("reports/candle_me_session.csv",
                         sess_df.to_csv(index=False) if not sess_df.empty else "session,feature\n",
                         commit)
    else:
        out = Path(args.data_dir).parent / "candle_me_results"
        out.mkdir(exist_ok=True)
        (out / "CANDLE_ME_REPORT.md").write_text(report_md, encoding="utf-8")
        (out / "candle_me_full.csv").write_text(me_df.to_csv(index=False), encoding="utf-8")
        print(f"\n[dry-run] Saved to {out}")

    print("\nDone.")

if __name__ == "__main__":
    main()
