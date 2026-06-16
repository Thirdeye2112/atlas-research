"""
Atlas Intraday Win/Loss Attribution v1
=======================================
For every detected setup, compares winners vs losers across 16+ conditions
to identify which contextual factors separate profitable setups from losing ones.

Conditions analysed:
  Numeric  : vol_ratio, dist_vwap_pct, rsi14, ema9_slope, macd_hist,
              atr_pct, body_pct, gap_pct, daily_ml_rank, daily_confluence
  Categorical: daily_conviction, daily_regime, daily_vix_regime
  Time     : time_bucket (6 bins across trading day)

Effect size: Cohen's d for numeric conditions; lift ratio for categorical/time.
Confidence : 1 - Mann-Whitney U p-value (numeric), 1 - chi-square p-value (categorical).

No lookahead. All features are from confidence_inputs stored at detection time,
plus daily context from the prior day's pipeline.
"""

from __future__ import annotations

import json
from datetime import date, timezone

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

SLIPPAGE_PCT     = 0.05
ANALYSIS_HORIZON = 6         # 30-min horizon
MIN_GROUP_N      = 8         # min winners OR losers to compute attribution
EFFECT_SIGNIFICANCE = 0.2    # |Cohen's d| threshold to flag a condition

# ---------------------------------------------------------------------------
# Numeric conditions to analyze (feature_key, display_name)
# ---------------------------------------------------------------------------
NUMERIC_CONDITIONS = [
    ("vol_ratio",        "Volume ratio (current vs 20-bar avg)"),
    ("dist_vwap_pct",    "Distance from VWAP (pct)"),
    ("rsi14",            "RSI(14)"),
    ("ema9_slope",       "EMA-9 slope"),
    ("macd_hist",        "MACD histogram"),
    ("atr_pct",          "ATR as pct of price"),
    ("body_pct",         "Candle body pct"),
    ("gap_pct",          "Gap from prior close (pct)"),
    ("daily_ml_rank",    "Daily ML signal strength"),
    ("daily_confluence", "Daily confluence score"),
    ("or_range_pct",     "Opening range size (pct)"),
]

CATEGORICAL_CONDITIONS = [
    ("daily_conviction",  ["HIGH", "VERY_HIGH"],     "Daily conviction HIGH/VH"),
    ("daily_conviction",  ["VERY_HIGH"],             "Daily conviction VERY_HIGH only"),
    ("daily_regime",      ["bull"],                  "Daily regime bull"),
    ("daily_regime",      ["bear"],                  "Daily regime bear"),
    ("daily_vix_regime",  ["low"],                   "VIX regime low"),
    ("daily_vix_regime",  ["low", "moderate"],       "VIX regime low or moderate"),
    ("daily_jarvis",      [True, "true", "1"],       "Jarvis green"),
]

TIME_BUCKETS = {
    "open_30m":  (570, 600),
    "930_10":    (600, 630),
    "10_1030":   (630, 660),
    "1030_14":   (660, 840),
    "14_15":     (840, 900),
    "15_16":     (900, 960),
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_setups_with_outcomes(engine, horizon: int = ANALYSIS_HORIZON) -> pd.DataFrame:
    sql = f"""
    SELECT
        s.setup_id, s.ticker, s.ts, s.setup_type, s.direction,
        s.confidence_inputs,
        s.daily_conviction, s.daily_regime, s.daily_vix_regime,
        s.daily_ml_rank, s.daily_confluence, s.daily_jarvis,
        o.future_return, o.mfe, o.mae, o.hit_target, o.hit_stop
    FROM intraday_setups s
    JOIN intraday_outcomes o ON o.setup_id = s.setup_id AND o.horizon_bars = {horizon}
    WHERE o.future_return IS NOT NULL
    ORDER BY s.ts
    """
    df = pd.read_sql(sql, engine, parse_dates=["ts"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def _expand_confidence_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Parse confidence_inputs JSON and merge columns into df."""
    def _parse(v):
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return {}

    parsed = df["confidence_inputs"].apply(_parse)
    feat   = pd.json_normalize(parsed.tolist())
    feat.index = df.index
    # Only add columns that don't already exist
    for col in feat.columns:
        if col not in df.columns:
            df[col] = feat[col]
    return df


def _add_time_bucket(df: pd.DataFrame) -> pd.DataFrame:
    """Add time_bucket and tod_min from UTC timestamp."""
    local = df["ts"].dt.tz_convert("America/New_York")
    tod   = local.dt.hour * 60 + local.dt.minute
    df["tod_min"] = tod
    bins   = [570, 600, 630, 660, 840, 900, 960]
    labels = list(TIME_BUCKETS.keys())
    df["time_bucket"] = pd.cut(tod, bins=bins, labels=labels, right=False)
    return df


def _add_week_label(df: pd.DataFrame) -> pd.DataFrame:
    """Add ISO year-week label for breadth checks."""
    local = df["ts"].dt.tz_convert("America/New_York")
    df["week_label"] = local.dt.strftime("%G-W%V")
    return df


# ---------------------------------------------------------------------------
# Effect size helpers
# ---------------------------------------------------------------------------

def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    pooled_std = np.sqrt(((na - 1) * np.var(a, ddof=1) + (nb - 1) * np.var(b, ddof=1)) / (na + nb - 2))
    if pooled_std < 1e-10:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled_std)


def _mannwhitney_p(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < MIN_GROUP_N or len(b) < MIN_GROUP_N:
        return 1.0
    try:
        _, p = stats.mannwhitneyu(a, b, alternative="two-sided")
        return float(p)
    except Exception:
        return 1.0


def _chisquare_p(cat_col: pd.Series, win_col: pd.Series) -> float:
    """Chi-square test of independence between a categorical column and win/loss."""
    ct = pd.crosstab(cat_col, win_col)
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return 1.0
    try:
        _, p, _, _ = stats.chi2_contingency(ct)
        return float(p)
    except Exception:
        return 1.0


# ---------------------------------------------------------------------------
# Attribution computation
# ---------------------------------------------------------------------------

def compute_attribution(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """
    For each (setup_type, direction), compare winner vs loser feature values.

    Args:
        df: setups + outcomes DataFrame (output of load_setups_with_outcomes)
        as_of: date label for this attribution run

    Returns:
        attribution DataFrame ready for upsert.
    """
    df = _expand_confidence_inputs(df.copy())
    df = _add_time_bucket(df)
    df = _add_week_label(df)
    df["net_return"] = df["future_return"] - SLIPPAGE_PCT
    df["is_winner"]  = df["net_return"] > 0

    rows = []

    for (st, direction), grp in df.groupby(["setup_type", "direction"]):
        grp     = grp.sort_values("ts").reset_index(drop=True)
        winners = grp[grp["is_winner"]]
        losers  = grp[~grp["is_winner"]]

        if len(winners) < MIN_GROUP_N or len(losers) < MIN_GROUP_N:
            continue

        # ── Numeric conditions ──────────────────────────────────────
        for feat, display in NUMERIC_CONDITIONS:
            w_vals = pd.to_numeric(winners.get(feat, pd.Series(dtype=float)), errors="coerce").dropna().values
            l_vals = pd.to_numeric(losers.get(feat,  pd.Series(dtype=float)), errors="coerce").dropna().values
            if len(w_vals) < MIN_GROUP_N or len(l_vals) < MIN_GROUP_N:
                continue

            d      = _cohens_d(w_vals, l_vals)
            p      = _mannwhitney_p(w_vals, l_vals)
            rows.append({
                "setup_type":     st,
                "direction":      direction,
                "as_of_date":     as_of,
                "condition_name": feat,
                "condition_type": "numeric",
                "winner_mean":    float(np.mean(w_vals)),
                "loser_mean":     float(np.mean(l_vals)),
                "difference":     float(np.mean(w_vals) - np.mean(l_vals)),
                "effect_size":    d,
                "winner_n":       len(w_vals),
                "loser_n":        len(l_vals),
                "sample_size":    len(grp),
                "p_value":        p,
                "confidence":     max(0.0, 1.0 - p),
            })

        # ── Categorical conditions ───────────────────────────────────
        for feat, true_vals, display in CATEGORICAL_CONDITIONS:
            col = grp.get(feat, pd.Series(dtype=object))
            if col.isna().all():
                continue
            in_cat  = col.isin(true_vals)
            cname   = f"{feat}={'|'.join(str(v) for v in true_vals)}"

            w_rate_overall = float(grp["is_winner"].mean())
            if in_cat.sum() < MIN_GROUP_N:
                continue
            w_rate_in  = float(grp.loc[in_cat, "is_winner"].mean())
            w_rate_out = float(grp.loc[~in_cat, "is_winner"].mean()) if (~in_cat).sum() >= 3 else w_rate_overall
            lift       = w_rate_in / w_rate_overall if w_rate_overall > 0 else 1.0
            p          = _chisquare_p(in_cat.astype(int), grp["is_winner"].astype(int))
            rows.append({
                "setup_type":     st,
                "direction":      direction,
                "as_of_date":     as_of,
                "condition_name": cname,
                "condition_type": "categorical",
                "winner_mean":    w_rate_in,
                "loser_mean":     w_rate_out,
                "difference":     w_rate_in - w_rate_out,
                "effect_size":    lift,
                "winner_n":       int(in_cat.sum()),
                "loser_n":        int((~in_cat).sum()),
                "sample_size":    len(grp),
                "p_value":        p,
                "confidence":     max(0.0, 1.0 - p),
            })

        # ── Time-of-day conditions ───────────────────────────────────
        if "time_bucket" in grp.columns and grp["time_bucket"].notna().any():
            w_rate_overall = float(grp["is_winner"].mean())
            for bucket in TIME_BUCKETS:
                mask = grp["time_bucket"].astype(str) == bucket
                if mask.sum() < MIN_GROUP_N:
                    continue
                w_rate_bucket = float(grp.loc[mask, "is_winner"].mean())
                lift  = w_rate_bucket / w_rate_overall if w_rate_overall > 0 else 1.0
                p     = _chisquare_p(mask.astype(int), grp["is_winner"].astype(int))
                rows.append({
                    "setup_type":     st,
                    "direction":      direction,
                    "as_of_date":     as_of,
                    "condition_name": f"time={bucket}",
                    "condition_type": "time",
                    "winner_mean":    w_rate_bucket,
                    "loser_mean":     w_rate_overall,
                    "difference":     w_rate_bucket - w_rate_overall,
                    "effect_size":    lift,
                    "winner_n":       int(mask.sum()),
                    "loser_n":        int((~mask).sum()),
                    "sample_size":    len(grp),
                    "p_value":        p,
                    "confidence":     max(0.0, 1.0 - p),
                })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def upsert_attribution(df: pd.DataFrame, engine) -> int:
    if df.empty:
        return 0
    sql = text("""
    INSERT INTO intraday_setup_attribution
        (setup_type, direction, as_of_date, condition_name, condition_type,
         winner_mean, loser_mean, difference, effect_size,
         winner_n, loser_n, sample_size, p_value, confidence)
    VALUES
        (:setup_type, :direction, :as_of_date, :condition_name, :condition_type,
         :winner_mean, :loser_mean, :difference, :effect_size,
         :winner_n, :loser_n, :sample_size, :p_value, :confidence)
    ON CONFLICT (setup_type, direction, as_of_date, condition_name) DO UPDATE SET
        winner_mean  = EXCLUDED.winner_mean,
        loser_mean   = EXCLUDED.loser_mean,
        difference   = EXCLUDED.difference,
        effect_size  = EXCLUDED.effect_size,
        winner_n     = EXCLUDED.winner_n,
        loser_n      = EXCLUDED.loser_n,
        sample_size  = EXCLUDED.sample_size,
        p_value      = EXCLUDED.p_value,
        confidence   = EXCLUDED.confidence
    """)

    def _c(v):
        if v is None:
            return None
        if isinstance(v, float) and v != v:
            return None
        return v

    rows = [{k: _c(v) for k, v in r.items()} for r in df.to_dict(orient="records")]
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)
