"""
5-Minute Candle Mutual Exclusivity Study
=========================================
Reads local parquet files, labels Rise/Drop events, extracts TA features on
the 2 candles BEFORE each event, computes mutual-exclusivity scores, validates
statistically, and auto-pushes results to GitHub.

Usage:
    python scripts/candle_me_study.py [--data-dir PATH] [--tickers AAPL MSFT ...]
                                      [--sample N] [--dry-run]

First run (schema detection):
    python scripts/candle_me_study.py --schema-check
"""

from __future__ import annotations
import os, sys, argparse, json, base64, time, warnings
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG  — edit these to match your local setup
# ─────────────────────────────────────────────────────────────────────────────
DATA_DIR     = Path(os.environ.get("CANDLE_DATA_DIR", r"C:\Atlas\data\5m"))
GITHUB_REPO  = "Thirdeye2112/atlas-research"
GITHUB_BRANCH = "main"
RESULTS_DIR  = Path(__file__).parent.parent / "reports"

# Event thresholds
RISE_PCT_THRESHOLD = 0.40   # candle body % ≥ this → Rise event
DROP_PCT_THRESHOLD = 0.40   # candle body % ≥ this → Drop event (absolute)
# Alternative: set USE_PERCENTILE=True to use per-ticker percentile labeling
USE_PERCENTILE     = True
PERCENTILE_CUTOFF  = 10     # top/bottom 10% of 5m candle returns

# Session buckets (Eastern time strings "HH:MM")
SESSION_BUCKETS = {
    "open_30m":   ("09:30", "10:00"),
    "mid_early":  ("10:00", "11:30"),
    "lunch":      ("11:30", "14:00"),
    "power_hour": ("15:00", "16:00"),
}

# Column name map — adjust if your parquets use different names
# Keys are canonical names used by this script; values are your actual column names
COLUMN_MAP = {
    "ticker":    "ticker",       # or None if filename is the ticker
    "datetime":  "datetime",     # timestamp column
    "open":      "open",
    "high":      "high",
    "low":       "low",
    "close":     "close",
    "volume":    "volume",
}
# If each file IS one ticker and has no ticker column, set:
# COLUMN_MAP["ticker"] = None   and ticker will be inferred from filename

# ─────────────────────────────────────────────────────────────────────────────
# GitHub push helper
# ─────────────────────────────────────────────────────────────────────────────

def github_push_file(path_in_repo: str, content: str | bytes, commit_msg: str) -> bool:
    """Push a single file to GitHub via REST API. Returns True on success."""
    try:
        import urllib.request
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("  WARN: GITHUB_TOKEN not set — skipping push")
            return False

        api_base = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path_in_repo}"
        headers  = {
            "Authorization": f"token {token}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
            "User-Agent":    "atlas-research-bot",
        }

        # Check if file already exists (need SHA for update)
        sha = None
        try:
            req = urllib.request.Request(api_base, headers=headers)
            with urllib.request.urlopen(req) as resp:
                existing = json.loads(resp.read())
                sha = existing.get("sha")
        except Exception:
            pass

        if isinstance(content, str):
            content = content.encode("utf-8")

        payload = {
            "message": commit_msg,
            "content": base64.b64encode(content).decode("ascii"),
            "branch":  GITHUB_BRANCH,
        }
        if sha:
            payload["sha"] = sha

        data = json.dumps(payload).encode("utf-8")
        req  = urllib.request.Request(api_base, data=data, headers=headers, method="PUT")
        with urllib.request.urlopen(req) as resp:
            status = resp.status
        print(f"  GitHub push → {path_in_repo}  [{status}]")
        return status in (200, 201)
    except Exception as e:
        print(f"  GitHub push FAILED: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Parquet loading
# ─────────────────────────────────────────────────────────────────────────────

def detect_schema(data_dir: Path) -> dict:
    """Read first parquet, print columns, suggest mapping."""
    files = sorted(data_dir.glob("*.parquet"))
    if not files:
        files = sorted(data_dir.rglob("*.parquet"))
    if not files:
        print(f"No parquet files found under {data_dir}")
        sys.exit(1)

    sample = files[0]
    df = pd.read_parquet(sample, engine="pyarrow")
    print(f"\n=== Schema detected from: {sample.name} ===")
    print(f"Rows in sample file : {len(df):,}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print(f"\nFirst 3 rows:")
    print(df.head(3).to_string())
    print(f"\nDate range: {df.iloc[0,0]} → {df.iloc[-1,0]}")
    return {"file": str(sample), "columns": list(df.columns), "nrows": len(df)}


def load_parquet(fpath: Path, col_map: dict) -> pd.DataFrame:
    """Load one parquet, rename columns to canonical names, return sorted df."""
    df = pd.read_parquet(fpath, engine="pyarrow")

    # Reverse map: actual_name → canonical_name
    rename = {}
    for canonical, actual in col_map.items():
        if actual and actual in df.columns and actual != canonical:
            rename[actual] = canonical
    if rename:
        df = df.rename(columns=rename)

    # Infer ticker from filename if no ticker column
    if "ticker" not in df.columns:
        ticker_name = fpath.stem.split("_")[0].upper()
        df["ticker"] = ticker_name

    # Parse datetime
    dt_col = "datetime"
    if dt_col not in df.columns:
        # Try common alternatives
        for alt in ["timestamp", "date", "time", "ts", "Date", "Datetime"]:
            if alt in df.columns:
                df = df.rename(columns={alt: "datetime"})
                break

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)

    # Ensure OHLCV columns are numeric
    for c in ["open", "high", "low", "close", "volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

# ─────────────────────────────────────────────────────────────────────────────
# Feature computation
# ─────────────────────────────────────────────────────────────────────────────

def add_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def add_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=period-1, adjust=False).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period-1, adjust=False).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_bb(close: pd.Series, period: int = 20) -> tuple[pd.Series, pd.Series, pd.Series]:
    ma  = close.rolling(period).mean()
    std = close.rolling(period).std()
    return ma + 2*std, ma, ma - 2*std

def add_vwap(df: pd.DataFrame) -> pd.Series:
    """Session VWAP — resets each day."""
    df = df.copy()
    df["_date"] = df["datetime"].dt.date
    df["_tp"]   = (df["high"] + df["low"] + df["close"]) / 3
    df["_cum_tp_vol"] = df.groupby("_date").apply(
        lambda g: (g["_tp"] * g["volume"]).cumsum()
    ).reset_index(level=0, drop=True)
    df["_cum_vol"] = df.groupby("_date")["volume"].cumsum()
    return df["_cum_tp_vol"] / df["_cum_vol"].replace(0, np.nan)

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all TA features needed for the study."""
    o, h, l, c, v = df["open"], df["high"], df["low"], df["close"], df["volume"]

    # --- Candle anatomy ---
    df["body_pct"]       = (c - o).abs() / c * 100
    df["body_dir"]       = np.sign(c - o)                    # +1 bull, -1 bear
    df["upper_wick"]     = h - np.maximum(o, c)
    df["lower_wick"]     = np.minimum(o, c) - l
    df["range"]          = h - l
    df["upper_wick_pct"] = df["upper_wick"] / df["range"].replace(0, np.nan) * 100
    df["lower_wick_pct"] = df["lower_wick"] / df["range"].replace(0, np.nan) * 100
    df["body_to_range"]  = df["body_pct"] / (df["range"] / c * 100).replace(0, np.nan)
    df["inside_bar"]     = (h < h.shift(1)) & (l > l.shift(1))
    df["outside_bar"]    = (h > h.shift(1)) & (l < l.shift(1))

    # Wick dominance: which wick is larger?
    df["upper_dom"]      = df["upper_wick"] > df["lower_wick"] * 1.5
    df["lower_dom"]      = df["lower_wick"] > df["upper_wick"] * 1.5

    # Consecutive candle direction streak
    streak = []
    s = 0
    for d in df["body_dir"]:
        if d == s:
            s += int(d)
        else:
            s = int(d)
        streak.append(s)
    df["consec_dir"] = streak

    # --- Volume ---
    df["vol_ma20"]        = v.rolling(20).mean()
    df["vol_ratio_20"]    = v / df["vol_ma20"].replace(0, np.nan)
    df["vol_ratio_5"]     = v / v.rolling(5).mean().replace(0, np.nan)
    df["vol_expanding"]   = (v > v.shift(1)).astype(int)
    df["vol_climax"]      = (df["vol_ratio_20"] > 3.0).astype(int)

    # --- EMAs ---
    df["ema9"]            = add_ema(c, 9)
    df["ema20"]           = add_ema(c, 20)
    df["ema50"]           = add_ema(c, 50)
    df["above_ema9"]      = (c > df["ema9"]).astype(int)
    df["above_ema20"]     = (c > df["ema20"]).astype(int)
    df["above_ema50"]     = (c > df["ema50"]).astype(int)
    df["above_all_emas"]  = ((c > df["ema9"]) & (c > df["ema20"]) & (c > df["ema50"])).astype(int)
    df["below_all_emas"]  = ((c < df["ema9"]) & (c < df["ema20"]) & (c < df["ema50"])).astype(int)
    df["ema9_vs_ema20"]   = (df["ema9"] > df["ema20"]).astype(int)   # golden cross state

    # Distance from ema9/20 as %
    df["dist_ema9_pct"]   = (c - df["ema9"])  / df["ema9"].replace(0, np.nan) * 100
    df["dist_ema20_pct"]  = (c - df["ema20"]) / df["ema20"].replace(0, np.nan) * 100

    # --- RSI ---
    df["rsi"]             = add_rsi(c, 14)
    df["rsi_slope"]       = df["rsi"].diff(2)                 # 2-bar RSI slope
    df["rsi_above50"]     = (df["rsi"] > 50).astype(int)
    df["rsi_above70"]     = (df["rsi"] > 70).astype(int)
    df["rsi_below30"]     = (df["rsi"] < 30).astype(int)
    # RSI reclaim: was below 50, now above
    df["rsi_reclaim50"]   = ((df["rsi"] > 50) & (df["rsi"].shift(1) < 50)).astype(int)
    df["rsi_lose50"]      = ((df["rsi"] < 50) & (df["rsi"].shift(1) > 50)).astype(int)

    # --- Bollinger Bands ---
    bb_up, bb_mid, bb_lo  = add_bb(c, 20)
    df["bb_pct"]          = (c - bb_lo) / (bb_up - bb_lo).replace(0, np.nan)  # 0–1
    df["bb_width"]        = (bb_up - bb_lo) / bb_mid.replace(0, np.nan) * 100
    df["bb_squeeze"]      = (df["bb_width"] < df["bb_width"].rolling(20).quantile(0.20)).astype(int)
    df["above_bb_upper"]  = (c > bb_up).astype(int)
    df["below_bb_lower"]  = (c < bb_lo).astype(int)

    # --- VWAP ---
    try:
        df["vwap"]        = add_vwap(df)
        df["above_vwap"]  = (c > df["vwap"]).astype(int)
        df["vwap_dist_pct"] = (c - df["vwap"]) / df["vwap"].replace(0, np.nan) * 100
    except Exception:
        df["vwap"]        = np.nan
        df["above_vwap"]  = np.nan
        df["vwap_dist_pct"] = np.nan

    # --- ATR (14-bar) ---
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr"]             = tr.ewm(com=13, adjust=False).mean()
    df["atr_pct"]         = df["atr"] / c * 100
    df["atr_expansion"]   = df["atr"] / df["atr"].rolling(5).mean().replace(0, np.nan)  # > 1 = expanding

    # --- MACD ---
    ema12 = add_ema(c, 12)
    ema26 = add_ema(c, 26)
    macd  = ema12 - ema26
    sig   = add_ema(macd, 9)
    df["macd_hist"]       = macd - sig
    df["macd_above_sig"]  = (macd > sig).astype(int)
    df["macd_hist_rising"] = (df["macd_hist"] > df["macd_hist"].shift(1)).astype(int)

    # --- Session info ---
    df["hour"]            = df["datetime"].dt.hour
    df["minute"]          = df["datetime"].dt.minute
    df["hhmm"]            = df["hour"] * 100 + df["minute"]
    df["session_bucket"]  = "other"
    for bucket, (start, end) in SESSION_BUCKETS.items():
        sh, sm = int(start[:2]), int(start[3:])
        eh, em = int(end[:2]),   int(end[3:])
        mask = (
            (df["hour"] * 60 + df["minute"] >= sh * 60 + sm) &
            (df["hour"] * 60 + df["minute"] <  eh * 60 + em)
        )
        df.loc[mask, "session_bucket"] = bucket
    df["is_power_hour"]   = (df["session_bucket"] == "power_hour").astype(int)
    df["is_open_30m"]     = (df["session_bucket"] == "open_30m").astype(int)
    df["day_of_week"]     = df["datetime"].dt.dayofweek   # 0=Mon, 4=Fri

    # --- Gap from prior close ---
    # A new session starts when date changes
    df["_date"]           = df["datetime"].dt.date
    df["date_changed"]    = df["_date"] != df["_date"].shift(1)
    df["gap_pct"]         = np.where(
        df["date_changed"],
        (o - c.shift(1)) / c.shift(1).replace(0, np.nan) * 100,
        np.nan
    )

    # --- C-2 → C-1 transition features (shift-based) ---
    df["prev1_body_pct"]   = df["body_pct"].shift(1)
    df["prev1_body_dir"]   = df["body_dir"].shift(1)
    df["prev1_vol_ratio"]  = df["vol_ratio_20"].shift(1)
    df["prev1_rsi"]        = df["rsi"].shift(1)
    df["prev1_bb_pct"]     = df["bb_pct"].shift(1)
    df["prev2_body_pct"]   = df["body_pct"].shift(2)
    df["prev2_body_dir"]   = df["body_dir"].shift(2)
    df["prev2_vol_ratio"]  = df["vol_ratio_20"].shift(2)
    df["prev2_rsi"]        = df["rsi"].shift(2)

    # Range expanding / contracting into the event
    df["range_expanding_into"] = (df["range"] < df["range"].shift(1)).astype(int)  # prior bar bigger
    df["vol_accel_into"]       = (df["vol_ratio_20"] > df["prev1_vol_ratio"]).astype(int)

    # Momentum alignment: both C-2 and C-1 same direction
    df["prior2_aligned_bull"]  = ((df["prev1_body_dir"] > 0) & (df["prev2_body_dir"] > 0)).astype(int)
    df["prior2_aligned_bear"]  = ((df["prev1_body_dir"] < 0) & (df["prev2_body_dir"] < 0)).astype(int)

    # C-2 inside → C-1 breakout (compression → expansion)
    inside_2bars_ago = df["inside_bar"].shift(1)
    not_inside_prev  = ~df["inside_bar"].shift(0).astype(bool)  # C-1 not inside
    df["compression_breakout"] = (inside_2bars_ago.astype(bool) & not_inside_prev).astype(int)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Event labeling
# ─────────────────────────────────────────────────────────────────────────────

def label_events(df: pd.DataFrame) -> pd.DataFrame:
    """Add 'event' column: 'rise', 'drop', or None."""
    # raw candle return (open→close)
    candle_return = (df["close"] - df["open"]) / df["open"] * 100

    if USE_PERCENTILE:
        # Per-ticker percentile (computed on full history)
        rise_thresh = np.nanpercentile(candle_return, 100 - PERCENTILE_CUTOFF)
        drop_thresh = np.nanpercentile(candle_return, PERCENTILE_CUTOFF)
    else:
        rise_thresh =  RISE_PCT_THRESHOLD
        drop_thresh = -DROP_PCT_THRESHOLD

    df = df.copy()
    df["candle_ret"] = candle_return
    df["event"]      = None
    df.loc[candle_return >= rise_thresh, "event"] = "rise"
    df.loc[candle_return <= drop_thresh, "event"] = "drop"

    # Label next-2-bar continuation / reversal
    for shift in [1, 2]:
        df[f"next{shift}_ret"] = candle_return.shift(-shift)

    return df


# ─────────────────────────────────────────────────────────────────────────────
# Mutual exclusivity engine
# ─────────────────────────────────────────────────────────────────────────────

BINARY_FEATURES = [
    "body_dir",         # +1 bull / -1 bear (will be binarised as >0)
    "inside_bar", "outside_bar",
    "upper_dom", "lower_dom",
    "vol_expanding", "vol_climax",
    "above_ema9", "above_ema20", "above_ema50",
    "above_all_emas", "below_all_emas", "ema9_vs_ema20",
    "rsi_above50", "rsi_above70", "rsi_below30",
    "rsi_reclaim50", "rsi_lose50",
    "bb_squeeze", "above_bb_upper", "below_bb_lower",
    "above_vwap",
    "macd_above_sig", "macd_hist_rising",
    "is_power_hour", "is_open_30m",
    "prior2_aligned_bull", "prior2_aligned_bear",
    "compression_breakout",
    "vol_accel_into",
    "range_expanding_into",
    # Prev-bar direction
    "prev1_body_dir",   # binarised as >0
    "prev2_body_dir",
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
    "prev1_body_pct", "prev1_rsi", "prev1_vol_ratio",
    "prev2_body_pct", "prev2_rsi",
    "consec_dir",
    "gap_pct",
]


def compute_me_scores(events_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each feature, compute:
      rise_lift  = P(feature_active | rise)  / P(feature_active | baseline)
      drop_lift  = P(feature_active | drop)  / P(feature_active | baseline)
      me_score   = rise_lift / drop_lift   (>> 1 = rise-only, << 1 = drop-only)
      p_value    = statistical test
      effect_size
    """
    rise = events_df[events_df["event"] == "rise"]
    drop = events_df[events_df["event"] == "drop"]
    base = events_df  # all candles (including non-events) for base rates

    records = []

    # --- Binary features ---
    for feat in BINARY_FEATURES:
        if feat not in events_df.columns:
            continue

        # Binarise: anything > 0 → True
        def active(df_):
            col = df_[feat]
            return (col > 0).sum(), len(col.dropna())

        rise_n, rise_tot = active(rise)
        drop_n, drop_tot = active(drop)
        base_n, base_tot = active(base)

        if base_tot == 0:
            continue

        base_rate  = base_n / base_tot
        rise_rate  = rise_n / rise_tot if rise_tot > 0 else np.nan
        drop_rate  = drop_n / drop_tot if drop_tot > 0 else np.nan
        rise_lift  = rise_rate / base_rate if base_rate > 0 else np.nan
        drop_lift  = drop_rate / base_rate if base_rate > 0 else np.nan
        me_score   = rise_lift / drop_lift  if (drop_lift and drop_lift > 0) else np.nan

        # Chi-square: rise vs drop contingency
        try:
            ct = np.array([
                [rise_n,        rise_tot - rise_n],
                [drop_n,        drop_tot - drop_n],
            ])
            chi2, p_val, _, _ = stats.chi2_contingency(ct, correction=False)
            cramers_v = np.sqrt(chi2 / (ct.sum() * (min(ct.shape) - 1)))
        except Exception:
            p_val, cramers_v = np.nan, np.nan

        records.append({
            "feature":      feat,
            "type":         "binary",
            "rise_rate":    round(rise_rate * 100, 2) if not np.isnan(rise_rate) else None,
            "drop_rate":    round(drop_rate * 100, 2) if not np.isnan(drop_rate) else None,
            "base_rate":    round(base_rate * 100, 2),
            "rise_lift":    round(rise_lift,  3) if not np.isnan(rise_lift)  else None,
            "drop_lift":    round(drop_lift,  3) if not np.isnan(drop_lift)  else None,
            "me_score":     round(me_score,   3) if not np.isnan(me_score)   else None,
            "p_value":      round(p_val,      6) if not np.isnan(p_val)      else None,
            "effect_size":  round(cramers_v,  4) if not np.isnan(cramers_v)  else None,
            "n_rise":       int(rise_tot),
            "n_drop":       int(drop_tot),
        })

    # --- Continuous features ---
    for feat in CONTINUOUS_FEATURES:
        if feat not in events_df.columns:
            continue

        r_vals = rise[feat].dropna().values
        d_vals = drop[feat].dropna().values

        if len(r_vals) < 5 or len(d_vals) < 5:
            continue

        # Mann-Whitney U
        try:
            u_stat, p_val = stats.mannwhitneyu(r_vals, d_vals, alternative="two-sided")
            n1, n2        = len(r_vals), len(d_vals)
            cliffs_delta  = (2 * u_stat / (n1 * n2)) - 1   # range [-1, 1]
        except Exception:
            p_val, cliffs_delta = np.nan, np.nan

        rise_mean = float(np.nanmean(r_vals))
        drop_mean = float(np.nanmean(d_vals))
        base_mean = float(events_df[feat].dropna().mean())

        # "lift" analogue for continuous: mean ratio vs base
        rise_lift = rise_mean / base_mean if base_mean != 0 else np.nan
        drop_lift = drop_mean / base_mean if base_mean != 0 else np.nan
        me_score  = rise_lift / drop_lift  if (drop_lift and drop_lift != 0) else np.nan

        records.append({
            "feature":      feat,
            "type":         "continuous",
            "rise_mean":    round(rise_mean, 4),
            "drop_mean":    round(drop_mean, 4),
            "base_mean":    round(base_mean, 4),
            "rise_lift":    round(rise_lift,  3) if not np.isnan(rise_lift)  else None,
            "drop_lift":    round(drop_lift,  3) if not np.isnan(drop_lift)  else None,
            "me_score":     round(me_score,   3) if not np.isnan(me_score)   else None,
            "p_value":      round(p_val,      6) if not np.isnan(p_val)      else None,
            "effect_size":  round(abs(cliffs_delta), 4) if not np.isnan(cliffs_delta) else None,
            "direction":    "rise_higher" if rise_mean > drop_mean else "drop_higher",
            "n_rise":       int(len(r_vals)),
            "n_drop":       int(len(d_vals)),
        })

    result = pd.DataFrame(records)
    if len(result) == 0:
        return result

    # --- FDR correction (Benjamini-Hochberg) ---
    pvals = result["p_value"].fillna(1.0).values
    n     = len(pvals)
    order = np.argsort(pvals)
    bh_thresh = np.array([(i + 1) / n * 0.05 for i in range(n)])
    passed    = pvals[order] <= bh_thresh
    # All below last passing rank pass
    if passed.any():
        last = np.where(passed)[0].max()
        fdr_mask = np.zeros(n, dtype=bool)
        fdr_mask[order[:last + 1]] = True
    else:
        fdr_mask = np.zeros(n, dtype=bool)

    result["fdr_pass"] = fdr_mask
    result = result.sort_values("me_score", ascending=False)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Time-of-day stratification
# ─────────────────────────────────────────────────────────────────────────────

def stratify_by_session(events_df: pd.DataFrame, top_features: list[str]) -> pd.DataFrame:
    """Run ME analysis per session bucket for top features."""
    buckets = events_df["session_bucket"].unique()
    rows = []
    for bucket in buckets:
        sub = events_df[events_df["session_bucket"] == bucket]
        rise = sub[sub["event"] == "rise"]
        drop = sub[sub["event"] == "drop"]
        if len(rise) < 20 or len(drop) < 20:
            continue
        for feat in top_features:
            if feat not in sub.columns:
                continue
            r_vals = rise[feat].dropna().values
            d_vals = drop[feat].dropna().values
            if len(r_vals) < 5 or len(d_vals) < 5:
                continue
            try:
                _, p = stats.mannwhitneyu(r_vals, d_vals, alternative="two-sided")
                cliffs = (2 * stats.mannwhitneyu(r_vals, d_vals)[0] / (len(r_vals) * len(d_vals))) - 1
            except Exception:
                p, cliffs = np.nan, np.nan
            rows.append({
                "session": bucket,
                "feature": feat,
                "rise_mean": float(np.nanmean(r_vals)),
                "drop_mean": float(np.nanmean(d_vals)),
                "effect_size": round(abs(cliffs), 4) if not np.isnan(cliffs) else None,
                "p_value": round(p, 6) if not np.isnan(p) else None,
                "n_rise": len(r_vals),
                "n_drop": len(d_vals),
            })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

def build_report(me_df: pd.DataFrame, session_df: pd.DataFrame,
                 meta: dict) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n_tickers   = meta.get("n_tickers", "?")
    n_candles   = meta.get("n_candles", "?")
    n_rise      = meta.get("n_rise", "?")
    n_drop      = meta.get("n_drop", "?")
    date_range  = meta.get("date_range", "?")

    # Top rise-predictors (ME > 2.0, FDR pass)
    rise_preds = me_df[
        (me_df["me_score"] >= 2.0) & me_df["fdr_pass"]
    ].head(15)

    # Top drop-predictors (ME < 0.5, FDR pass)
    drop_preds = me_df[
        (me_df["me_score"] <= 0.5) & me_df["fdr_pass"]
    ].sort_values("me_score").head(15)

    # Neutral / noise (0.8 < ME < 1.2)
    neutral = me_df[
        (me_df["me_score"] > 0.8) & (me_df["me_score"] < 1.2)
    ].head(10)

    def tbl(df_, cols):
        if df_.empty:
            return "_No features passed filters._\n"
        header = "| " + " | ".join(cols) + " |"
        sep    = "|" + "|".join(["---"] * len(cols)) + "|"
        rows   = []
        for _, r in df_.iterrows():
            vals = []
            for c in cols:
                v = r.get(c)
                if isinstance(v, float):
                    vals.append(f"{v:.3f}" if not np.isnan(v) else "—")
                elif v is None:
                    vals.append("—")
                else:
                    vals.append(str(v))
            rows.append("| " + " | ".join(vals) + " |")
        return "\n".join([header, sep] + rows) + "\n"

    rise_cols = ["feature", "type", "rise_lift", "drop_lift", "me_score", "effect_size", "p_value", "fdr_pass"]
    drop_cols = rise_cols

    session_tbl = ""
    if not session_df.empty:
        top_feats = rise_preds["feature"].tolist()[:5] + drop_preds["feature"].tolist()[:5]
        sub = session_df[session_df["feature"].isin(top_feats)]
        session_tbl = tbl(sub, ["session", "feature", "rise_mean", "drop_mean", "effect_size", "p_value", "n_rise", "n_drop"])

    lines = [
        "# 5-Minute Candle Mutual Exclusivity Report",
        f"",
        f"**Generated:** {ts}  ",
        f"**Tickers analysed:** {n_tickers:,}  " if isinstance(n_tickers, int) else f"**Tickers analysed:** {n_tickers}  ",
        f"**Total 5m candles:** {n_candles:,}  " if isinstance(n_candles, int) else f"**Total 5m candles:** {n_candles}  ",
        f"**Date range:** {date_range}  ",
        f"**Rise events:** {n_rise:,}  " if isinstance(n_rise, int) else f"**Rise events:** {n_rise}  ",
        f"**Drop events:** {n_drop:,}  " if isinstance(n_drop, int) else f"**Drop events:** {n_drop}  ",
        f"**Labelling method:** {'Top/bottom ' + str(PERCENTILE_CUTOFF) + '% candle return per ticker' if USE_PERCENTILE else f'Fixed ±{RISE_PCT_THRESHOLD}% body threshold'}  ",
        f"",
        f"---",
        f"",
        f"## Method",
        f"",
        f"For each 5m candle labelled as Rise or Drop:",
        f"- Features extracted from **C-2** and **C-1** (2 candles before the event)",
        f"- Mutual exclusivity score = rise_lift ÷ drop_lift",
        f"  - **ME > 2.0** → feature fires ≥2× more before rises than drops → **Rise signal**",
        f"  - **ME < 0.5** → feature fires ≥2× more before drops than rises → **Drop signal**",
        f"  - **ME ≈ 1.0** → feature is neutral / noise",
        f"- Statistical validation: chi-square (binary) / Mann-Whitney U (continuous)",
        f"- Multiple comparison correction: Benjamini-Hochberg FDR (α=0.05)",
        f"- Effect size: Cramér's V (binary) / Cliff's delta (continuous)",
        f"",
        f"---",
        f"",
        f"## 1. Rise Predictors (ME ≥ 2.0, FDR-corrected)",
        f"",
        f"_Features present before RISES significantly more than before DROPS._",
        f"",
        tbl(rise_preds, rise_cols),
        f"---",
        f"",
        f"## 2. Drop Predictors (ME ≤ 0.5, FDR-corrected)",
        f"",
        f"_Features present before DROPS significantly more than before RISES._",
        f"",
        tbl(drop_preds, drop_cols),
        f"---",
        f"",
        f"## 3. Neutral / Noise Features",
        f"",
        f"_These features do not discriminate between rises and drops._",
        f"",
        tbl(neutral, ["feature", "type", "me_score", "p_value"]),
        f"---",
        f"",
        f"## 4. Time-of-Day Stratification (top 10 features)",
        f"",
        f"_Does the same feature work differently in different session windows?_",
        f"",
        session_tbl,
        f"---",
        f"",
        f"## 5. Full Feature Table",
        f"",
        f"See `reports/candle_me_full.csv` for all features with complete statistics.",
        f"",
        f"---",
        f"_Generated by `scripts/candle_me_study.py`_",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir",     default=str(DATA_DIR))
    parser.add_argument("--tickers",      nargs="+", default=None,
                        help="Process only these tickers (stem of parquet filename)")
    parser.add_argument("--sample",       type=int,  default=None,
                        help="Randomly sample N parquet files (for quick test)")
    parser.add_argument("--schema-check", action="store_true",
                        help="Print schema info from first file and exit")
    parser.add_argument("--dry-run",      action="store_true",
                        help="Run analysis but do not push to GitHub")
    parser.add_argument("--no-push",      action="store_true",
                        help="Same as --dry-run")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        print(f"Set CANDLE_DATA_DIR env var or pass --data-dir PATH")
        sys.exit(1)

    # Schema check mode
    if args.schema_check:
        detect_schema(data_dir)
        print("\nIf column names differ from expected, edit COLUMN_MAP at top of script.")
        sys.exit(0)

    # Discover parquet files
    files = sorted(data_dir.glob("*.parquet")) or sorted(data_dir.rglob("*.parquet"))
    if not files:
        print(f"No parquet files found under {data_dir}")
        sys.exit(1)

    # Filter / sample
    if args.tickers:
        tickers_upper = set(t.upper() for t in args.tickers)
        files = [f for f in files if f.stem.upper() in tickers_upper]
    if args.sample:
        import random
        random.shuffle(files)
        files = files[:args.sample]

    print(f"=== 5-Minute Candle Mutual Exclusivity Study ===")
    print(f"Data dir : {data_dir}")
    print(f"Files    : {len(files):,}")
    print(f"Labelling: {'percentile top/bottom ' + str(PERCENTILE_CUTOFF) + '%' if USE_PERCENTILE else 'fixed threshold'}")
    print()

    # ── Load and process all files ─────────────────────────────────────────
    all_events: list[pd.DataFrame] = []
    n_candles_total = 0
    date_min, date_max = None, None
    errors = []

    for i, fpath in enumerate(files, 1):
        ticker = fpath.stem.split("_")[0].upper()
        try:
            df = load_parquet(fpath, COLUMN_MAP)
            if len(df) < 50:
                continue
            df = compute_features(df)
            df = label_events(df)

            n_candles_total += len(df)
            d_min = df["datetime"].min()
            d_max = df["datetime"].max()
            if date_min is None or d_min < date_min: date_min = d_min
            if date_max is None or d_max > date_max: date_max = d_max

            # Keep only event rows for ME computation (with their C-2/C-1 features)
            evt = df[df["event"].notna()].copy()
            all_events.append(evt)

            if i % 100 == 0 or i == len(files):
                n_rise = sum((e["event"] == "rise").sum() for e in all_events)
                n_drop = sum((e["event"] == "drop").sum() for e in all_events)
                print(f"  [{i}/{len(files)}] {ticker:8s}  "
                      f"candles={len(df):,}  events(R/D)={n_rise:,}/{n_drop:,}")

        except Exception as e:
            errors.append(f"{ticker}: {e}")
            if i <= 5:
                print(f"  WARN [{ticker}]: {e}")

    if not all_events:
        print("No events extracted. Check COLUMN_MAP and data format.")
        sys.exit(1)

    events_df = pd.concat(all_events, ignore_index=True)
    n_rise = (events_df["event"] == "rise").sum()
    n_drop = (events_df["event"] == "drop").sum()
    n_tickers = len(files) - len(errors)

    print(f"\n=== Data Summary ===")
    print(f"  Tickers processed : {n_tickers:,}")
    print(f"  Total 5m candles  : {n_candles_total:,}")
    print(f"  Date range        : {date_min} → {date_max}")
    print(f"  Rise events       : {n_rise:,}")
    print(f"  Drop events       : {n_drop:,}")
    print(f"  Errors            : {len(errors)}")
    if errors[:5]:
        for e in errors[:5]: print(f"    {e}")
    print()

    # ── Compute ME scores ──────────────────────────────────────────────────
    print("Computing mutual exclusivity scores...")
    me_df = compute_me_scores(events_df)
    print(f"  Features tested  : {len(me_df)}")
    print(f"  FDR-pass         : {me_df['fdr_pass'].sum()}")
    print(f"  Rise predictors  : {(me_df['me_score'] >= 2.0).sum()}")
    print(f"  Drop predictors  : {(me_df['me_score'] <= 0.5).sum()}")

    # ── Session stratification ─────────────────────────────────────────────
    top_feats = (
        me_df[me_df["me_score"] >= 2.0]["feature"].head(5).tolist() +
        me_df[me_df["me_score"] <= 0.5]["feature"].head(5).tolist()
    )
    print("\nStratifying by session bucket...")
    session_df = stratify_by_session(events_df, top_feats)

    # ── Build report ───────────────────────────────────────────────────────
    meta = {
        "n_tickers":  n_tickers,
        "n_candles":  n_candles_total,
        "n_rise":     int(n_rise),
        "n_drop":     int(n_drop),
        "date_range": f"{date_min} → {date_max}",
    }
    report_md  = build_report(me_df, session_df, meta)
    full_csv   = me_df.to_csv(index=False)
    session_csv = session_df.to_csv(index=False) if not session_df.empty else "session,feature\n"

    # Show top findings in console
    print("\n=== TOP RISE PREDICTORS (ME ≥ 2.0) ===")
    top_rise = me_df[me_df["me_score"] >= 2.0].head(10)
    if not top_rise.empty:
        print(top_rise[["feature", "me_score", "rise_lift", "drop_lift", "effect_size", "p_value"]].to_string(index=False))
    else:
        print("  None passed ME ≥ 2.0 threshold.")

    print("\n=== TOP DROP PREDICTORS (ME ≤ 0.5) ===")
    top_drop = me_df[me_df["me_score"] <= 0.5].sort_values("me_score").head(10)
    if not top_drop.empty:
        print(top_drop[["feature", "me_score", "rise_lift", "drop_lift", "effect_size", "p_value"]].to_string(index=False))
    else:
        print("  None passed ME ≤ 0.5 threshold.")

    # ── Push to GitHub ─────────────────────────────────────────────────────
    dry_run = args.dry_run or args.no_push
    ts_tag  = datetime.now().strftime("%Y%m%d_%H%M")

    if not dry_run:
        print("\n=== Pushing results to GitHub ===")
        github_push_file(
            "reports/CANDLE_ME_REPORT.md",
            report_md,
            f"[candle-me] {ts_tag} mutual exclusivity study ({n_tickers} tickers, {n_candles_total:,} candles)"
        )
        github_push_file(
            "reports/candle_me_full.csv",
            full_csv,
            f"[candle-me] {ts_tag} full feature table"
        )
        github_push_file(
            "reports/candle_me_session.csv",
            session_csv,
            f"[candle-me] {ts_tag} session stratification"
        )
        print("Done — check Thirdeye2112/atlas-research/reports/")
    else:
        # Save locally
        out = Path(args.data_dir).parent / "results"
        out.mkdir(exist_ok=True)
        (out / "CANDLE_ME_REPORT.md").write_text(report_md)
        (out / "candle_me_full.csv").write_text(full_csv)
        (out / "candle_me_session.csv").write_text(session_csv)
        print(f"\n[dry-run] Results saved to {out}")

    print("\nAll done.")

if __name__ == "__main__":
    main()
