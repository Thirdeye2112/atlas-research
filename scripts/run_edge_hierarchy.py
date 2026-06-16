"""
Atlas Edge Hierarchy Analysis
==============================
Tests every major Atlas component independently and in combination.
Performs ablation: removes one component at a time and measures the
performance delta. Produces EDGE_HIERARCHY_REPORT.md.

Usage:
    python scripts/run_edge_hierarchy.py
    python scripts/run_edge_hierarchy.py --start-date 2020-01-01
    python scripts/run_edge_hierarchy.py --start-date 2015-01-01 --out reports/EDGE_HIERARCHY_REPORT.md
"""
from __future__ import annotations

import argparse
import math
import os
import sys
from datetime import date, datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy.stats import spearmanr

load_dotenv()
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from run_confluence_backtest import (
    load_static_stats,
    build_model_map,
    compute_forward_returns,
    _group_metrics,
    HORIZONS,
    N_PERMS,
    MIN_SAMPLE,
    MIN_DQ,
    WEIGHTS,
    _BULL_PROB,
    _BEAR_PROB,
    _HIT_THRESH,
    _IC_THRESH,
    _MIN_CAL_N,
    _pct,
    _ret,
)
from run_conviction_backtest import add_conviction
from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR, TRAIN_FEATURES_V1
from atlas_research.models.train import load_model
from atlas_research.models.dataset import cross_sectional_normalize
from atlas_research.features.regime_interactions import INTERACTION_NAMES
from atlas_research.utils.logging import get_logger

log = get_logger("edge_hierarchy")

# ── Extra features to retain from the parquet ───────────────────────────────────
EXTRA_COLS = [
    "omni_82_above", "omni_82_distance", "omni_82_slope", "omni_82_bounce",
    "oscar_87_above_50", "oscar_87_value",
    "hma_87_above",
    "jarvis_quality_adjusted", "quality_tier",
    "rsi_14", "macd_histogram", "roc_20", "return_20d",
    "dollar_volume_20", "data_quality_score",
    "realized_vol_20",   # for VIX-proxy regime classification
    "above_sma200",      # individual stock vs own 200-SMA (vs above_200dma which is SPY-based)
]

# ── Layer names ─────────────────────────────────────────────────────────────────
LAYERS = [
    "technical",    # RSI + MACD + momentum composite
    "omni_oscar",   # OMNI82 above + OSCAR87 above 50
    "jarvis",       # jarvis_quality_adjusted
    "quality_tier", # quality_tier (1-4)
    "pattern",      # pattern component direction
    "probability",  # probability component direction
    "feature_ic",   # feature IC component direction
    "regime",       # regime component direction
    "ml_rank",      # ML model rank percentile + probability
    "confluence",   # full confluence score direction
    "conviction",   # conviction level filter on top of confluence
]

# Components that participate in the alignment/ablation analysis
ABLATION_TARGETS = ["ml_rank", "pattern", "probability", "feature_ic", "regime"]


# ═══════════════════════════════════════════════════════════════════════════════
# Extended score batch — keeps OMNI/quality features from parquet
# ═══════════════════════════════════════════════════════════════════════════════

def score_batch_extended(
    df: pd.DataFrame,
    bundle,
    feature_cols: list[str],
    pattern_stats: list[dict],
    calib_stats: list[dict],
    regime_stats: dict[str, list[dict]],
) -> pd.DataFrame:
    """
    Mirrors run_confluence_backtest.score_batch() but:
    - Returns per-component directions for ablation analysis
    - Retains OMNI / Jarvis / quality features
    """
    n   = len(df)
    idx = df.index

    # ── ML ─────────────────────────────────────────────────────────────────────
    df_norm = cross_sectional_normalize(df.copy(), feature_cols)
    for col in feature_cols:
        if col not in df_norm.columns:
            df_norm[col] = np.nan
    X        = df_norm[feature_cols].to_numpy(dtype=np.float64)
    prob     = bundle.predict_prob(X)
    rank_pct = pd.Series(prob).rank(pct=True).to_numpy()
    ml_dir   = np.where(prob >= _BULL_PROB, 1, np.where(prob <= _BEAR_PROB, -1, 0))
    ml_str   = 0.6 * np.abs(prob - 0.5) * 2 + 0.4 * np.abs(rank_pct - 0.5) * 2

    # ── Regime ─────────────────────────────────────────────────────────────────
    spy_above  = df.get("spy_above_sma200", pd.Series(np.nan, index=idx)).fillna(0.5)
    mkt_trend  = df.get("market_trend",     pd.Series(0.0,    index=idx)).fillna(0)
    rv20       = df.get("realized_vol_20",  pd.Series(np.nan, index=idx))
    rv60       = df.get("realized_vol_60",  pd.Series(np.nan, index=idx))

    mkt_regime = np.where(mkt_trend > 0, "bull", np.where(mkt_trend < 0, "bear", "range"))
    above_200  = (spy_above.values > 0.5).astype(int)
    ic_regime  = np.where(above_200 == 1, "above_200dma", "below_200dma")
    vol_regime = np.where(
        rv20.notna().values & rv60.notna().values & (rv20.values > rv60.values * 1.25),
        "high_vol", "low_vol",
    )
    regime_dir = np.where(
        (mkt_regime == "bull") & (above_200 == 1), 1,
        np.where((mkt_regime == "bear") & (above_200 == 0), -1, 0),
    ).astype(int)
    regime_str   = np.where(regime_dir != 0, 0.7, 0.3)
    regime_avail = (
        df.get("spy_above_sma200", pd.Series(np.nan, index=idx)).notna().values |
        df.get("market_trend",     pd.Series(np.nan, index=idx)).notna().values
    )

    # ── Pattern ────────────────────────────────────────────────────────────────
    false_s = pd.Series(False, index=idx)
    bull_pat  = np.zeros(n, int); bear_pat = np.zeros(n, int); active_pat = np.zeros(n, int)
    for ps in pattern_stats:
        ct = ps["condition_type"]; pm = ps["params"]
        trig = _trigger_vec_local(ct, pm, df, false_s).values.astype(int)
        active_pat += trig
        hr = ps["hit_rate"]; ar = ps["avg_return"]
        if hr >= _HIT_THRESH:
            if ar > 0:  bull_pat += trig
            elif ar < 0: bear_pat += trig
    net_pat = bull_pat - bear_pat
    pat_dir  = np.where(net_pat > 0, 1, np.where(net_pat < 0, -1, 0))
    pat_str  = np.where(
        active_pat > 0,
        np.clip((bull_pat + bear_pat).astype(float) / np.clip(active_pat, 1, None) * 0.4, 0, 1),
        0.0,
    )
    pat_avail = (active_pat > 0)

    # ── Probability ────────────────────────────────────────────────────────────
    bull_pw = np.zeros(n); bear_pw = np.zeros(n); total_pw = np.zeros(n)
    for cs in calib_stats:
        st = cs["signal_type"]; sk = cs["signal_key"]
        hr = float(cs["hit_rate_5d"]); ar = float(cs["avg_return_5d"])
        nres = float(cs["n_resolved"])
        w = abs(hr - 0.5) * min(1.0, nres / 200.0)
        if st == "ml_rank_bucket":
            try:
                lo_f, hi_f = float(sk.split("-")[0]) / 100.0, float(sk.split("-")[1]) / 100.0
                trig = ((rank_pct >= lo_f) & (rank_pct < hi_f if hi_f < 1.0 else np.ones(n, bool))).astype(float)
            except Exception:
                continue
        else:
            continue
        total_pw += trig * abs(w)
        if ar > 0:  bull_pw += trig * abs(w)
        else:       bear_pw += trig * abs(w)
    safe_pw  = np.where(total_pw > 0, total_pw, np.nan)
    bull_pfr = np.where(total_pw > 0, bull_pw / safe_pw, 0.5)
    bear_pfr = np.where(total_pw > 0, bear_pw / safe_pw, 0.5)
    prob_dir  = np.where((total_pw > 0) & (bull_pfr >= 0.60), 1,
                np.where((total_pw > 0) & (bear_pfr >= 0.60), -1, 0))
    prob_str  = np.clip(np.abs(bull_pfr - bear_pfr), 0, 1)
    prob_avail = (total_pw > 0)

    # ── Feature IC ─────────────────────────────────────────────────────────────
    bull_ic = np.zeros(n); bear_ic = np.zeros(n); scored_f = np.zeros(n, int)
    for regime_key in ["above_200dma", "below_200dma"]:
        rmask = (ic_regime == regime_key)
        for fs in regime_stats.get(regime_key, []):
            feat = fs["feature_name"]
            if feat not in df.columns:
                continue
            val  = df[feat].to_numpy(dtype=float)
            valid = ~np.isnan(val)
            ic = float(fs["mean_ic"]); stab = float(fs["sign_stability"])
            sign_match = ((ic > 0) == (val > 0)).astype(float) * 2 - 1
            contrib = np.abs(ic) * sign_match * stab
            mask = rmask & valid
            scored_f += mask.astype(int)
            bull_ic  += np.where(mask & (contrib > 0),  contrib,  0)
            bear_ic  += np.where(mask & (contrib < 0), -contrib,  0)
    tot_ic   = bull_ic + bear_ic
    safe_ic  = np.where(tot_ic > 0, tot_ic, np.nan)
    bull_ifr = np.where(tot_ic > 0, bull_ic / safe_ic, 0.5)
    bear_ifr = np.where(tot_ic > 0, bear_ic / safe_ic, 0.5)
    feat_dir  = np.where((scored_f >= 5) & (bull_ifr >= 0.60), 1,
                np.where((scored_f >= 5) & (bear_ifr >= 0.60), -1, 0))
    feat_str  = np.clip(np.abs(bull_ifr - bear_ifr), 0, 1)
    feat_avail = (scored_f >= 5)

    # ── Risk penalty ───────────────────────────────────────────────────────────
    penalty = np.zeros(n)
    dq  = df.get("data_quality_score", pd.Series(np.nan, index=idx)).to_numpy(float)
    dv  = df.get("dollar_volume_20",   pd.Series(np.nan, index=idx)).to_numpy(float)
    ed  = df.get("expected_drawdown",  pd.Series(np.nan, index=idx)).to_numpy(float)
    atr = df.get("atr_pct",            pd.Series(np.nan, index=idx)).to_numpy(float)
    penalty += np.where(~np.isnan(dq)  & (dq < 0.70),      10.0, np.where(~np.isnan(dq)  & (dq < 0.80),     4.0, 0))
    penalty += np.where(~np.isnan(dv)  & (dv < 1_000_000), 10.0, np.where(~np.isnan(dv)  & (dv < 5_000_000), 4.0, 0))
    penalty += np.where(~np.isnan(ed)  & (ed < -0.05),       5.0, np.where(~np.isnan(ed)  & (ed < -0.02),     2.0, 0))
    penalty += np.where(~np.isnan(atr) & (atr > 0.06),       3.0, 0)
    penalty  = np.clip(penalty, 0, 25)

    # ── Alignment + full confluence score ──────────────────────────────────────
    comps = [
        (ml_dir,    ml_str,    np.ones(n, bool), WEIGHTS["ml"]),
        (pat_dir,   pat_str,   pat_avail,         WEIGHTS["pattern"]),
        (prob_dir,  prob_str,  prob_avail,        WEIGHTS["probability"]),
        (feat_dir,  feat_str,  feat_avail,        WEIGHTS["feature_ic"]),
        (regime_dir,regime_str,regime_avail,      WEIGHTS["regime"]),
    ]
    bull_w = np.zeros(n); bear_w = np.zeros(n)
    bull_c = np.zeros(n, int); bear_c = np.zeros(n, int)
    neut_c = np.zeros(n, int); total_a = np.zeros(n, int)
    for cd, cs, ca, cw in comps:
        total_a += ca.astype(int)
        bull_w  += np.where(ca & (cd == 1),  cs * cw, 0)
        bear_w  += np.where(ca & (cd == -1), cs * cw, 0)
        bull_c  += np.where(ca & (cd == 1),  1, 0)
        bear_c  += np.where(ca & (cd == -1), 1, 0)
        neut_c  += np.where(ca & (cd == 0),  1, 0)

    dominant   = np.where(bull_w > bear_w * 1.15, 1, np.where(bear_w > bull_w * 1.15, -1, 0))
    aligned_c  = np.where(dominant == 1, bull_c, np.where(dominant == -1, bear_c, np.maximum(bull_c, bear_c))).astype(int)
    conflict_c = np.where(dominant == 1, bear_c, np.where(dominant == -1, bull_c, np.minimum(bull_c, bear_c))).astype(int)
    align_r    = np.where(total_a > 0, aligned_c / total_a, 0.0)

    al_str = np.zeros(n); al_wt = np.zeros(n)
    for cd, cs, ca, cw in comps[:-1]:
        is_al = ca & (cd == dominant) & (dominant != 0)
        al_str += np.where(is_al, cs * cw, 0)
        al_wt  += np.where(is_al, cw, 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        avg_al = np.where(al_wt > 0, al_str / al_wt, 0)
    has_con = (dominant != 0) & (aligned_c > 0)
    base    = np.where(has_con, (0.65 * avg_al + 0.35 * align_r) * 100,
                       20.0 + np.clip(20.0 - conflict_c * 4.0, 0, 20))

    _FIT = {("bull",1):1.00,("bull",-1):0.72,("bull",0):0.85,
            ("bear",-1):1.00,("bear",1):0.72,("bear",0):0.85,
            ("range",1):0.88,("range",-1):0.88,("range",0):0.80}
    fitness   = np.array([_FIT.get((mr, int(d)), 0.85) for mr, d in zip(mkt_regime, dominant)])
    final     = np.clip(base * fitness - penalty, 0, 100)
    dir_lbl   = np.where(dominant == 1, "bullish", np.where(dominant == -1, "bearish", "neutral"))

    out = pd.DataFrame({
        "ticker":               df["ticker"].values,
        "date":                 df["date"].values,
        # Full confluence
        "confluence_score":     np.round(final, 2),
        "confluence_direction": dir_lbl,
        "dominant_dir":         dominant,
        "aligned_count":        aligned_c,
        "conflict_count":       conflict_c,
        "total_available":      total_a,
        # Per-component signals
        "ml_dir":               ml_dir,
        "ml_str":               np.round(ml_str, 4),
        "ml_prob":              np.round(prob, 4),
        "ml_rank":              np.round(rank_pct, 4),
        "pat_dir":              pat_dir,
        "pat_str":              np.round(pat_str, 4),
        "pat_avail":            pat_avail.astype(int),
        "prob_dir":             prob_dir,
        "prob_str":             np.round(prob_str, 4),
        "prob_avail":           prob_avail.astype(int),
        "feat_ic_dir":          feat_dir,
        "feat_str":             np.round(feat_str, 4),
        "feat_avail":           feat_avail.astype(int),
        "regime_dir":           regime_dir,
        "regime_str":           np.round(regime_str, 4),
        "regime_avail":         regime_avail.astype(int),
        # Context
        "market_regime":        mkt_regime,
        "vol_regime":           vol_regime,
        "above_200dma":         above_200,
        "risk_penalty":         np.round(penalty, 2),
    })

    # Pass-through OMNI / Jarvis / quality features from raw parquet
    for col in EXTRA_COLS:
        if col in df.columns:
            out[col] = df[col].values
        else:
            out[col] = np.nan

    return out


def _trigger_vec_local(condition_type, params, df, false_s):
    try:
        if condition_type == "consecutive_down":
            n = int(params.get("n_days", 3)); key = f"return_{min(n,5)}d"
            return df.get(key, false_s).fillna(0) < 0
        if condition_type == "consecutive_up":
            n = int(params.get("n_days", 3)); key = f"return_{min(n,5)}d"
            return df.get(key, false_s).fillna(0) > 0
        if condition_type == "oversold_rsi":
            return df.get("rsi_14", false_s).fillna(50) <= float(params.get("threshold", 30))
        if condition_type == "overbought_rsi":
            return df.get("rsi_14", false_s).fillna(50) >= float(params.get("threshold", 70))
        if condition_type == "gap_down":
            mgp = float(params.get("min_gap_pct", 2.0)) / 100.0
            return df.get("return_1d", false_s).fillna(0) <= -mgp
        if condition_type == "near_52w_low":
            within = float(params.get("within_pct", 5.0)) / 100.0
            return df.get("dist_52w_low", false_s).fillna(1) <= within
        if condition_type == "near_52w_high":
            within = float(params.get("within_pct", 5.0)) / 100.0
            return df.get("dist_52w_high", false_s).fillna(1) <= within
        if condition_type == "high_volume":
            mult = float(params.get("multiplier", 2.0))
            return df.get("rvol_20", false_s).fillna(0) >= mult
        # ── OMNI-based patterns (proxy: current-bar state ≈ recent cross-up) ────
        if condition_type in ("oscar_cross_up", "oscar_above_50"):
            # OSCAR(87) currently above 50 — proxy for recent cross-up event
            return df.get("oscar_87_above_50", false_s).fillna(0) > 0.5
        if condition_type in ("ema_lows_cross_up", "omni_cross_up", "ema_lows_above"):
            # Close currently above EMA-of-lows (OMNI-82) — proxy for recent cross-up
            return df.get("omni_82_above", false_s).fillna(0) > 0.5
        if condition_type in ("hma_cross_up", "hma_above"):
            # HMA(87) currently bullish
            return df.get("hma_87_above", false_s).fillna(0) > 0.5
        if condition_type in ("ema_lows_support", "omni_bounce"):
            # Low near OMNI and closed bullish (omni_82_bounce already encodes this)
            return df.get("omni_82_bounce", false_s).fillna(0) > 0.5
        if condition_type == "ema_lows_green_slope":
            above = df.get("omni_82_above", false_s).fillna(0) > 0.5
            slope = df.get("omni_82_slope",  pd.Series(np.nan, index=df.index)).fillna(0) > 0
            return above & slope
        if condition_type == "end_of_month":
            # Last 3 calendar days of month
            dates = pd.to_datetime(df["date"]) if "date" in df.columns else None
            if dates is not None:
                return pd.Series((dates.dt.day >= 28).values, index=df.index)
        if condition_type == "volume_climax_down":
            vol_spike = df.get("volume_ratio_20", false_s).fillna(0) >= float(params.get("vol_mult", 2.5))
            neg_day   = df.get("return_1d", false_s).fillna(0) < -float(params.get("down_pct", 2.0)) / 100.0
            return vol_spike & neg_day
    except Exception:
        pass
    return false_s


# ═══════════════════════════════════════════════════════════════════════════════
# Extended load_and_score
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_score_extended(
    start_date: date,
    end_date: date,
    parquet_dir: Path,
    model_map: list[tuple[date, Path]],
    pattern_stats: list[dict],
    calib_stats: list[dict],
    regime_stats: dict[str, list[dict]],
) -> pd.DataFrame:
    from datetime import timedelta
    parquets = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    in_range = [
        p for p in parquets
        if start_date <= datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date() <= end_date
    ]
    if not in_range:
        log.error("edge.no_parquets", start=str(start_date), end=str(end_date))
        return pd.DataFrame()

    all_dates = [datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date() for p in in_range]

    # Build model map (group dates by model)
    PURGE_DAYS = 7
    batches: dict[Path, list[date]] = {}
    for d in all_dates:
        cutoff = d - timedelta(days=PURGE_DAYS)
        best = None
        for td, mp in model_map:
            if td <= cutoff:
                best = mp
        if best:
            batches.setdefault(best, []).append(d)

    date_to_parquet = {
        datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date(): p
        for p in in_range
    }

    all_scored: list[pd.DataFrame] = []
    for model_path, dates in sorted(batches.items(), key=lambda x: str(x[0])):
        try:
            bundle = load_model(model_path)
        except Exception as exc:
            log.error("edge.model_load_failed", path=str(model_path), error=str(exc))
            continue

        feature_cols = (bundle.feature_names
                        if hasattr(bundle, "feature_names") and bundle.feature_names
                        else TRAIN_FEATURES_V1)
        feature_cols = [f for f in feature_cols if f not in INTERACTION_NAMES]

        for d in sorted(dates):
            ppath = date_to_parquet.get(d)
            if ppath is None or not ppath.exists():
                continue
            try:
                df = pd.read_parquet(ppath, engine="pyarrow")
                df["date"] = d
                if "data_quality_score" in df.columns:
                    df = df[df["data_quality_score"] >= MIN_DQ]
                if df.empty:
                    continue
                scored = score_batch_extended(df, bundle, feature_cols,
                                              pattern_stats, calib_stats, regime_stats)
                all_scored.append(scored)
            except Exception as exc:
                log.error("edge.date_error", date=str(d), error=str(exc))
        del bundle

    if not all_scored:
        return pd.DataFrame()
    return pd.concat(all_scored, ignore_index=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_metrics(
    df: pd.DataFrame,
    direction_col: str,
    fwd_col: str = "fwd_5d",
    strength_col: str | None = None,
    min_n: int = MIN_SAMPLE,
) -> dict:
    """Compute hit_rate, expectancy, sharpe, IC, n for a given direction signal."""
    sub = df[df[direction_col] != 0].copy()   # directional only
    ret = sub[fwd_col].dropna()
    sub_ret = sub.loc[ret.index]

    n = len(ret)
    if n < min_n:
        return {"n": n, "hit_rate": None, "expectancy": None, "sharpe": None, "ic": None,
                "direction_rate": None}

    # Direction-signed returns: multiply actual return × direction if we want the signal-aligned return
    dir_vals = sub_ret[direction_col].to_numpy(dtype=float)
    ret_vals = ret.to_numpy(dtype=float)
    signed   = dir_vals * ret_vals   # positive if direction was correct

    hit_rate    = float((signed > 0).mean())
    expectancy  = float(ret_vals.mean())
    sharpe_ann  = float(ret_vals.mean() / ret_vals.std() * math.sqrt(252)) if ret_vals.std() > 0 else 0.0

    # IC: Spearman correlation between strength (or |direction|) and actual return
    if strength_col and strength_col in sub_ret.columns:
        str_vals = sub_ret[strength_col].dropna()
        common   = str_vals.index.intersection(ret.index)
        if len(common) >= 10:
            ic, _ = spearmanr(str_vals.loc[common], ret.loc[common])
        else:
            ic = np.nan
    else:
        # Use signed direction as a degenerate 3-value signal
        common = pd.Series(dir_vals, index=sub_ret.index)
        if len(common) >= 10:
            ic, _ = spearmanr(common, ret.loc[sub_ret.index])
        else:
            ic = np.nan

    direction_rate = float((df[direction_col] != 0).mean())

    return {
        "n":              n,
        "hit_rate":       round(hit_rate, 4),
        "expectancy":     round(expectancy, 6),
        "sharpe":         round(sharpe_ann, 3),
        "ic":             round(float(ic), 4) if not np.isnan(ic) else None,
        "direction_rate": round(direction_rate, 4),
    }


def _layer_direction(df: pd.DataFrame, layer: str) -> pd.Series:
    """
    Returns an int Series: +1 bullish, -1 bearish, 0 neutral / unavailable.
    Each layer uses the most direct signal available.
    """
    n = len(df)
    if layer == "technical":
        # Majority vote of RSI + MACD + 20d return
        rsi   = df.get("rsi_14",         pd.Series(np.nan, index=df.index))
        macd  = df.get("macd_histogram",  pd.Series(np.nan, index=df.index))
        r20   = df.get("return_20d",      pd.Series(np.nan, index=df.index))
        rsi_d = np.where(rsi.fillna(50) < 30, 1, np.where(rsi.fillna(50) > 70, -1, 0))
        mac_d = np.where(macd.fillna(0) > 0, 1, np.where(macd.fillna(0) < 0, -1, 0))
        r20_d = np.where(r20.fillna(0) > 0, 1, np.where(r20.fillna(0) < 0, -1, 0))
        votes = rsi_d + mac_d + r20_d
        return pd.Series(np.where(votes >= 2, 1, np.where(votes <= -2, -1, 0)), index=df.index)

    elif layer == "omni_oscar":
        omni = df.get("omni_82_above",    pd.Series(np.nan, index=df.index))
        osc  = df.get("oscar_87_above_50", pd.Series(np.nan, index=df.index))
        omni_avail = omni.notna()
        osc_avail  = osc.notna()
        od   = np.where(omni.fillna(0.5) > 0.5,  1, -1)
        ocsd = np.where(osc.fillna(0.5)  > 0.5,  1, -1)
        # When oscar is missing, fall back to omni alone (od*2) so its sign still resolves.
        # When omni is missing, use oscar alone.  When both missing, emit 0 (neutral).
        both  = omni_avail.values & osc_avail.values
        o_only = omni_avail.values & ~osc_avail.values
        s_only = ~omni_avail.values & osc_avail.values
        votes = np.where(both, od + ocsd,
                np.where(o_only, od * 2,
                np.where(s_only, ocsd * 2, 0)))
        avail = omni_avail.values | osc_avail.values
        return pd.Series(
            np.where(avail, np.where(votes > 0, 1, np.where(votes < 0, -1, 0)), 0),
            index=df.index,
        )

    elif layer == "jarvis":
        j = df.get("jarvis_quality_adjusted", pd.Series(np.nan, index=df.index))
        return pd.Series(np.where(j.fillna(0) > 0, 1, np.where(j.fillna(0) < 0, -1, 0)), index=df.index)

    elif layer == "quality_tier":
        qt = df.get("quality_tier", pd.Series(np.nan, index=df.index))
        return pd.Series(np.where(qt.fillna(4) <= 2, 1, np.where(qt.fillna(4) >= 4, -1, 0)), index=df.index)

    elif layer == "pattern":
        return pd.Series(df["pat_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "probability":
        return pd.Series(df["prob_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "feature_ic":
        return pd.Series(df["feat_ic_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "regime":
        return pd.Series(df["regime_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "ml_rank":
        return pd.Series(df["ml_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "confluence":
        return pd.Series(df["dominant_dir"].to_numpy(dtype=int), index=df.index)

    elif layer == "conviction":
        # Only use HIGH or VERY_HIGH conviction rows as directional
        level   = df["conviction_level"].values
        dom_dir = df["dominant_dir"].to_numpy(dtype=int)
        return pd.Series(
            np.where(np.isin(level, ["HIGH", "VERY_HIGH"]) & (dom_dir != 0), dom_dir, 0),
            index=df.index,
        )

    return pd.Series(np.zeros(n, int), index=df.index)


def _layer_strength(df: pd.DataFrame, layer: str) -> pd.Series | None:
    """Returns a continuous strength column for IC computation."""
    mapping = {
        "ml_rank":    "ml_str",
        "pattern":    "pat_str",
        "probability":"prob_str",
        "feature_ic": "feat_str",
        "regime":     "regime_str",
        "confluence": "confluence_score",
        "conviction": "conviction_score",
        "omni_oscar": "omni_82_distance",
        "technical":  "rsi_14",
        "jarvis":     "jarvis_quality_adjusted",
    }
    col = mapping.get(layer)
    if col and col in df.columns:
        return df[col]
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Ablation
# ═══════════════════════════════════════════════════════════════════════════════

COMP_META = {
    "ml_rank":    {"dir": "ml_dir",    "str": "ml_str",    "avail": None,         "w": WEIGHTS["ml"]},
    "pattern":    {"dir": "pat_dir",   "str": "pat_str",   "avail": "pat_avail",  "w": WEIGHTS["pattern"]},
    "probability":{"dir": "prob_dir",  "str": "prob_str",  "avail": "prob_avail", "w": WEIGHTS["probability"]},
    "feature_ic": {"dir": "feat_ic_dir","str": "feat_str",  "avail": "feat_avail", "w": WEIGHTS["feature_ic"]},
    "regime":     {"dir": "regime_dir","str": "regime_str","avail": "regime_avail","w": WEIGHTS["regime"]},
}

def _recompute_alignment(
    df: pd.DataFrame,
    exclude: str | None = None,
) -> np.ndarray:
    """
    Re-compute dominant direction with one component excluded.
    Returns int array (+1/0/-1).
    """
    n = len(df)
    bull_w = np.zeros(n); bear_w = np.zeros(n)
    for comp, meta in COMP_META.items():
        if comp == exclude:
            continue
        cd = df[meta["dir"]].to_numpy(dtype=int)
        cs = df[meta["str"]].to_numpy(dtype=float)
        ca = df[meta["avail"]].to_numpy(dtype=bool) if meta["avail"] else np.ones(n, bool)
        cw = meta["w"]
        bull_w += np.where(ca & (cd == 1),  cs * cw, 0)
        bear_w += np.where(ca & (cd == -1), cs * cw, 0)
    return np.where(bull_w > bear_w * 1.15, 1, np.where(bear_w > bull_w * 1.15, -1, 0)).astype(int)


def _directional_stats(
    df: pd.DataFrame,
    dir_col_or_arr,
    fwd_col: str,
) -> tuple[float, float, int]:
    """
    Returns (hit_rate, expectancy, n) for rows where direction != 0 and fwd is not NaN.
    dir_col_or_arr may be a column name (str) or a numpy array aligned to df.index.
    """
    if isinstance(dir_col_or_arr, str):
        dirs = df[dir_col_or_arr].to_numpy(dtype=int)
    else:
        dirs = np.asarray(dir_col_or_arr, dtype=int)

    rets = df[fwd_col].to_numpy(dtype=float)
    mask = (dirs != 0) & ~np.isnan(rets)
    d = dirs[mask]
    r = rets[mask]
    if len(r) < MIN_SAMPLE:
        return np.nan, np.nan, int(mask.sum())
    return float((d * r > 0).mean()), float(r.mean()), int(mask.sum())


def run_ablation(df: pd.DataFrame, fwd_col: str = "fwd_5d") -> dict[str, dict]:
    """
    For each ablation target, measure the hit rate with and without that component.
    Returns: {component: {full_hr, ablated_hr, delta_hr, full_n, ablated_n}}
    """
    results = {}

    # Baseline (all components)
    base_hr, base_exp, base_n = _directional_stats(df, "dominant_dir", fwd_col)

    results["_baseline"] = {
        "full_hr":  round(base_hr,  4) if not np.isnan(base_hr)  else None,
        "full_exp": round(base_exp, 6) if not np.isnan(base_exp) else None,
        "n":        base_n,
    }

    for comp in ABLATION_TARGETS:
        abl_dir = _recompute_alignment(df, exclude=comp)
        abl_hr, abl_exp, abl_n = _directional_stats(df, abl_dir, fwd_col)

        delta_hr  = (abl_hr  - base_hr)  if (not np.isnan(abl_hr)  and not np.isnan(base_hr))  else np.nan
        delta_exp = (abl_exp - base_exp) if (not np.isnan(abl_exp) and not np.isnan(base_exp)) else np.nan

        results[comp] = {
            "full_hr":    round(base_hr,  4) if not np.isnan(base_hr)  else None,
            "ablated_hr": round(abl_hr,   4) if not np.isnan(abl_hr)   else None,
            "delta_hr":   round(delta_hr, 4) if not np.isnan(delta_hr) else None,
            "full_exp":   round(base_exp,  6) if not np.isnan(base_exp)  else None,
            "ablated_exp":round(abl_exp,   6) if not np.isnan(abl_exp)   else None,
            "delta_exp":  round(delta_exp, 6) if not np.isnan(delta_exp) else None,
            "ablated_n":  int((abl_dir != 0).sum()),
        }

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# Combination analysis
# ═══════════════════════════════════════════════════════════════════════════════

def run_combo_analysis(df: pd.DataFrame, fwd_col: str = "fwd_5d") -> list[dict]:
    """
    Test all pairs of components: restrict to rows where BOTH components agree
    on direction, and measure hit rate.
    """
    combos = list(combinations(ABLATION_TARGETS, 2))
    rows = []
    for c1, c2 in combos:
        d1 = df[COMP_META[c1]["dir"]].to_numpy(dtype=int)
        d2 = df[COMP_META[c2]["dir"]].to_numpy(dtype=int)
        rets = df[fwd_col].to_numpy(dtype=float)
        mask = (d1 == d2) & (d1 != 0) & ~np.isnan(rets)
        if mask.sum() < MIN_SAMPLE:
            continue
        dirs_m = d1[mask]
        rets_m = rets[mask]
        signed = dirs_m * rets_m
        hr  = float((signed > 0).mean())
        exp = float(rets_m.mean())
        rows.append({
            "combo":      f"{c1} + {c2}",
            "n":          int(mask.sum()),
            "hit_rate":   round(hr, 4),
            "expectancy": round(exp, 6),
        })

    rows.sort(key=lambda x: x["hit_rate"], reverse=True)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas Edge Hierarchy Analysis")
    parser.add_argument("--start-date", default="2015-01-01")
    parser.add_argument("--end-date",   default=None)
    parser.add_argument("--out",        default="reports/EDGE_HIERARCHY_REPORT.md")
    args = parser.parse_args()

    start_date = date.fromisoformat(args.start_date)
    end_date   = date.fromisoformat(args.end_date) if args.end_date else date.today()
    out_path   = _ROOT / args.out

    print(f"\nAtlas Edge Hierarchy Analysis")
    print(f"Period   : {start_date} to {end_date}")
    print(f"Output   : {out_path}")
    print("-" * 60)

    # ── Load infrastructure ────────────────────────────────────────────────────
    print("\nStep 1/6: Loading DB stats...")
    pattern_stats, calib_stats, regime_stats = load_static_stats()
    print(f"  Patterns: {len(pattern_stats)}, Calibrated signals: {len(calib_stats)}, Regime IC regimes: {len(regime_stats)}")

    print("\nStep 2/6: Building model map...")
    model_dir  = Path(MODEL_DIR)
    parquet_dir = Path(PARQUET_OUTPUT_DIR)
    model_map  = build_model_map(model_dir)
    if not model_map:
        print("  ERROR: No model artifacts found. Cannot run analysis.")
        return 1
    print(f"  Found {len(model_map)} model artifacts")

    # ── Score all dates ────────────────────────────────────────────────────────
    print("\nStep 3/6: Scoring all dates...")
    scored = load_and_score_extended(
        start_date, end_date, parquet_dir, model_map,
        pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("  ERROR: No scored rows produced.")
        return 1
    print(f"  Scored {len(scored):,} ticker-date rows")

    # ── Join forward returns ───────────────────────────────────────────────────
    print("\nStep 4/6: Computing forward returns...")
    scored = compute_forward_returns(scored)
    scored = add_conviction(scored)
    print(f"  Rows with fwd_5d: {scored['fwd_5d'].notna().sum():,}")

    # ── Per-layer analysis ─────────────────────────────────────────────────────
    print("\nStep 5/6: Computing per-layer metrics...")
    layer_results: list[dict] = []
    for layer in LAYERS:
        print(f"  Layer: {layer}")
        direction = _layer_direction(scored, layer)
        scored[f"_dir_{layer}"] = direction
        strength  = _layer_strength(scored, layer)
        str_col   = None
        if strength is not None:
            col_name = f"_str_{layer}"
            scored[col_name] = strength
            str_col = col_name

        m = _compute_metrics(scored, f"_dir_{layer}", fwd_col="fwd_5d", strength_col=str_col)
        m["layer"] = layer
        layer_results.append(m)

    # ── Ablation testing ───────────────────────────────────────────────────────
    print("\nStep 6/6: Running ablation tests...")
    ablation = run_ablation(scored)
    combos   = run_combo_analysis(scored)

    # ── Regime breakdown for top layers ───────────────────────────────────────
    scored["regime_grp"] = scored["market_regime"] + "_" + scored["vol_regime"].fillna("unk")

    # ── Write report ───────────────────────────────────────────────────────────
    print("\nGenerating report...")
    report = _build_report(
        start_date, end_date, scored, layer_results, ablation, combos,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written: {out_path}")
    return 0


# ═══════════════════════════════════════════════════════════════════════════════
# Report builder
# ═══════════════════════════════════════════════════════════════════════════════

def _fmt_hr(v) -> str:
    return f"{v:.1%}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "n/a"

def _fmt_ret(v) -> str:
    return f"{v:+.3%}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "n/a"

def _fmt_ic(v) -> str:
    return f"{v:.4f}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "n/a"

def _fmt_f(v, dec=3) -> str:
    return f"{v:.{dec}f}" if v is not None and not (isinstance(v, float) and math.isnan(v)) else "n/a"

def _fmt_n(v) -> str:
    return f"{int(v):,}" if v is not None else "n/a"

def _delta_str(v) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1%}"

def _rank_rec(layer: str, ablation: dict, layer_row: dict) -> tuple[str, str]:
    """Assign a recommendation based on evidence."""
    hr   = layer_row.get("hit_rate")
    ic   = layer_row.get("ic")
    abl  = ablation.get(layer, {})
    dhr  = abl.get("delta_hr")   # negative = removal improved, positive = removal hurt
    dexp = abl.get("delta_exp")

    # Confluence and conviction are aggregations — always keep
    if layer in ("confluence", "conviction"):
        return "KEEP", "Aggregation layer; removing individual components is more precise than removing this"

    if hr is None:
        return "EXPERIMENTAL", "Insufficient data to evaluate"

    # Positive contribution: removal hurts (delta < 0 = removing worsened performance)
    if dhr is not None and dhr < -0.003:
        if hr > 0.545:
            return "PROMOTE", f"Strong contributor: HR={_fmt_hr(hr)}, removal drops HR by {_delta_str(dhr)}"
        return "KEEP", f"Positive contributor: HR={_fmt_hr(hr)}, removal drops HR by {_delta_str(dhr)}"

    # Neutral: removal has no measurable effect
    if dhr is not None and abs(dhr) < 0.003:
        if ic is not None and abs(ic) > 0.01:
            return "KEEP", f"Neutral ablation impact but non-zero IC={_fmt_ic(ic)}"
        return "REWORK", f"No measurable ablation delta ({_delta_str(dhr)}); may add noise"

    # Negative: removal improves performance
    if dhr is not None and dhr > 0.003:
        return "REMOVE" if dhr > 0.01 else "REWORK", \
               f"Removing this component improves HR by {_delta_str(dhr)}"

    # OMNI/OSCAR — known to be regime-sensitive
    if layer == "omni_oscar":
        return "EXPERIMENTAL", "Regime-sensitive; test with bull/bear regime split"

    # Jarvis / quality_tier — implicit signals
    if layer in ("jarvis", "quality_tier"):
        return "KEEP", "Implicit quality gate; no clean ablation path but protects from micro-cap noise"

    return "KEEP", f"HR={_fmt_hr(hr)}, IC={_fmt_ic(ic)}"


def _build_report(
    start_date: date,
    end_date: date,
    df: pd.DataFrame,
    layer_results: list[dict],
    ablation: dict,
    combos: list[dict],
) -> str:
    total_rows = len(df)
    n_directional = int((df["dominant_dir"] != 0).sum())
    baseline = ablation.get("_baseline", {})

    lines: list[str] = [
        "# Atlas Edge Hierarchy Report",
        f"**Period:** {start_date} → {end_date}  |  **Universe rows:** {total_rows:,}  |  **Directional calls:** {n_directional:,}",
        f"**Generated:** {date.today()}",
        "",
        "> This report quantifies the marginal predictive contribution of each Atlas subsystem.",
        "> Hit rate = % of directional calls where price moved in the predicted direction (5d horizon).",
        "> IC = Spearman rank correlation between signal strength and actual return.",
        "> Ablation = what happens to hit rate if this component is removed from alignment.",
        "> All metrics are out-of-sample (walk-forward models, no look-ahead).",
        "",
        "---",
        "",
        "## 1. Per-Layer Performance",
        "",
        "| Layer | N (directional) | Hit Rate 5d | Expectancy 5d | Sharpe | IC | Coverage |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in sorted(layer_results, key=lambda x: x.get("hit_rate") or 0, reverse=True):
        layer = r["layer"]
        lines.append(
            f"| {layer} | {_fmt_n(r['n'])} | {_fmt_hr(r.get('hit_rate'))} | "
            f"{_fmt_ret(r.get('expectancy'))} | {_fmt_f(r.get('sharpe'))} | "
            f"{_fmt_ic(r.get('ic'))} | {_fmt_hr(r.get('direction_rate'))} |"
        )

    lines += [
        "",
        "> **Coverage** = % of all rows where the layer produces a directional signal.",
        "",
        "---",
        "",
        "## 2. Ablation Testing (5d Horizon)",
        "",
        f"**Baseline (all components):** HR={_fmt_hr(baseline.get('full_hr'))}, "
        f"Expectancy={_fmt_ret(baseline.get('full_exp'))}, N={_fmt_n(baseline.get('n'))}",
        "",
        "Ablation removes one component from alignment, re-applies the 1.15× weight rule, and measures the change.",
        "Negative delta = removal **hurt** performance (component adds value).",
        "Positive delta = removal **helped** performance (component subtracts value).",
        "",
        "| Component Removed | Ablated HR | Delta HR | Ablated Exp | Delta Exp | Ablated N |",
        "|---|---|---|---|---|---|",
    ]

    for comp in ABLATION_TARGETS:
        a = ablation.get(comp, {})
        lines.append(
            f"| {comp} | {_fmt_hr(a.get('ablated_hr'))} | {_delta_str(a.get('delta_hr'))} | "
            f"{_fmt_ret(a.get('ablated_exp'))} | {_delta_str(a.get('delta_exp'))} | {_fmt_n(a.get('ablated_n'))} |"
        )

    # ── Ranked contribution table ───────────────────────────────────────────────
    # Sort ablation targets by |delta_hr| (most impactful first)
    ranked_comps = sorted(
        ABLATION_TARGETS,
        key=lambda c: abs(ablation.get(c, {}).get("delta_hr") or 0),
        reverse=True,
    )

    lines += [
        "",
        "---",
        "",
        "## 3. Ranked Contribution Table",
        "",
        "Ranked by absolute ablation impact (how much performance changes when removed).",
        "",
        "| Rank | Component | Delta HR | Direction | Confidence |",
        "|---|---|---|---|---|",
    ]

    for i, comp in enumerate(ranked_comps, 1):
        a    = ablation.get(comp, {})
        dhr  = a.get("delta_hr")
        if dhr is None:
            direction = "unknown"; conf = "low"
        elif dhr < -0.003:
            direction = "POSITIVE (adds edge)"; conf = "high" if abs(dhr) > 0.01 else "medium"
        elif dhr > 0.003:
            direction = "NEGATIVE (removes edge)"; conf = "high" if abs(dhr) > 0.01 else "medium"
        else:
            direction = "NEUTRAL (no measurable impact)"; conf = "medium"
        lines.append(f"| {i} | {comp} | {_delta_str(dhr)} | {direction} | {conf} |")

    # ── Full layer ranking by hit rate ─────────────────────────────────────────
    lines += [
        "",
        "### All Layers Ranked by Hit Rate",
        "",
        "| Rank | Layer | Hit Rate | IC | Notes |",
        "|---|---|---|---|---|",
    ]

    sorted_layers = sorted(layer_results, key=lambda x: x.get("hit_rate") or 0, reverse=True)
    for i, r in enumerate(sorted_layers, 1):
        layer = r["layer"]
        abl   = ablation.get(layer, {})
        dhr   = abl.get("delta_hr")
        note  = f"ablation Δ={_delta_str(dhr)}" if dhr is not None else "ablation: N/A (not in alignment)"
        lines.append(
            f"| {i} | {layer} | {_fmt_hr(r.get('hit_rate'))} | {_fmt_ic(r.get('ic'))} | {note} |"
        )

    # ── Combination analysis ────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 4. Best Component Combinations (both must agree)",
        "",
        "Measures hit rate when two components independently agree on direction.",
        "",
        "| Combo | N | Hit Rate | Expectancy |",
        "|---|---|---|---|",
    ]

    top_combos = combos[:10]
    bot_combos = sorted(combos, key=lambda x: x["hit_rate"])[:5]

    for c in top_combos:
        lines.append(
            f"| {c['combo']} | {_fmt_n(c['n'])} | {_fmt_hr(c['hit_rate'])} | {_fmt_ret(c['expectancy'])} |"
        )

    lines += [
        "",
        "### Worst Combinations (agreement is actually harmful)",
        "",
        "| Combo | N | Hit Rate | Expectancy |",
        "|---|---|---|---|",
    ]
    for c in bot_combos:
        lines.append(
            f"| {c['combo']} | {_fmt_n(c['n'])} | {_fmt_hr(c['hit_rate'])} | {_fmt_ret(c['expectancy'])} |"
        )

    # ── Redundancy analysis ─────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 5. Redundancy Analysis",
        "",
        "Two components are **redundant** if their agreement rate is high (> 70%) and adding the second",
        "component produces negligible incremental IC.",
        "",
        "| Component Pair | Agreement Rate | Notes |",
        "|---|---|---|",
    ]

    # Compute pairwise agreement between component directions
    for c1, c2 in combinations(ABLATION_TARGETS, 2):
        d1 = df[COMP_META[c1]["dir"]].to_numpy(dtype=int)
        d2 = df[COMP_META[c2]["dir"]].to_numpy(dtype=int)
        avail1 = df[COMP_META[c1]["avail"]].to_numpy(dtype=bool) if COMP_META[c1]["avail"] else np.ones(len(df), bool)
        avail2 = df[COMP_META[c2]["avail"]].to_numpy(dtype=bool) if COMP_META[c2]["avail"] else np.ones(len(df), bool)
        both_avail  = avail1 & avail2
        both_dir    = (d1 != 0) & (d2 != 0)
        mask        = both_avail & both_dir
        if mask.sum() < MIN_SAMPLE:
            agreement = None
        else:
            agreement = float((d1[mask] == d2[mask]).mean())
        note = "⚠️ high overlap" if (agreement and agreement > 0.70) else ""
        lines.append(f"| {c1} × {c2} | {_fmt_hr(agreement)} | {note} |")

    # ── Regime breakdown ─────────────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 6. Regime Breakdown (Confluence, HIGH+ conviction)",
        "",
        "| Regime | N | Hit Rate 5d | Avg Return 5d |",
        "|---|---|---|---|",
    ]

    vh = df[df["conviction_level"].isin(["HIGH", "VERY_HIGH"])].copy()
    vh["regime_grp"] = vh["market_regime"] + "_" + vh["vol_regime"].fillna("unk")
    for grp, sub in sorted(vh.groupby("regime_grp"), key=lambda x: x[0]):
        ret = sub["fwd_5d"].dropna()
        if len(ret) < MIN_SAMPLE:
            continue
        hr  = float((ret > 0).mean())
        avg = float(ret.mean())
        lines.append(f"| {grp} | {_fmt_n(len(ret))} | {_fmt_hr(hr)} | {_fmt_ret(avg)} |")

    # ── Year-by-year stability ──────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 7. Yearly Stability (Confluence Direction, All Rows)",
        "",
        "| Year | N | Hit Rate 5d | Avg Return 5d |",
        "|---|---|---|---|",
    ]

    df2 = df.copy()
    df2["year"] = pd.to_datetime(df2["date"]).dt.year
    dir_col = "dominant_dir"
    for yr, sub in df2.groupby("year"):
        sub_dir = sub[dir_col].to_numpy(dtype=int)
        sub_sub = sub[sub_dir != 0].copy()
        ret = sub_sub["fwd_5d"].dropna()
        if len(ret) < MIN_SAMPLE:
            continue
        dirs = sub_dir[sub_dir != 0][:len(ret)]
        signed = dirs * ret.to_numpy()
        hr  = float((signed > 0).mean())
        avg = float(ret.mean())
        lines.append(f"| {yr} | {_fmt_n(len(ret))} | {_fmt_hr(hr)} | {_fmt_ret(avg)} |")

    # ── Final recommendations ──────────────────────────────────────────────────
    lines += [
        "",
        "---",
        "",
        "## 8. Recommendations by Subsystem",
        "",
        "| # | Component | Recommendation | Rationale |",
        "|---|---|---|---|",
    ]

    # Rank all layers by hit_rate for recommendation ordering
    all_recs = []
    for r in sorted_layers:
        layer = r["layer"]
        rec, rationale = _rank_rec(layer, ablation, r)
        all_recs.append((layer, rec, rationale, r.get("hit_rate")))

    rec_order = {"PROMOTE": 0, "KEEP": 1, "REWORK": 2, "EXPERIMENTAL": 3, "REMOVE": 4}
    all_recs.sort(key=lambda x: (rec_order.get(x[1], 5), -(x[3] or 0)))

    for i, (layer, rec, rationale, hr) in enumerate(all_recs, 1):
        lines.append(f"| {i} | {layer} | **{rec}** | {rationale} |")

    # ── Summary verdict ─────────────────────────────────────────────────────────
    promote = [x[0] for x in all_recs if x[1] == "PROMOTE"]
    keep    = [x[0] for x in all_recs if x[1] == "KEEP"]
    rework  = [x[0] for x in all_recs if x[1] == "REWORK"]
    remove  = [x[0] for x in all_recs if x[1] == "REMOVE"]
    exp     = [x[0] for x in all_recs if x[1] == "EXPERIMENTAL"]

    lines += [
        "",
        "---",
        "",
        "## 9. Summary Verdict",
        "",
        f"| | |",
        f"|---|---|",
        f"| **PROMOTE** ({len(promote)}) | {', '.join(promote) or 'none'} |",
        f"| **KEEP** ({len(keep)}) | {', '.join(keep) or 'none'} |",
        f"| **REWORK** ({len(rework)}) | {', '.join(rework) or 'none'} |",
        f"| **EXPERIMENTAL** ({len(exp)}) | {', '.join(exp) or 'none'} |",
        f"| **REMOVE** ({len(remove)}) | {', '.join(remove) or 'none'} |",
        "",
        "### Key Findings",
        "",
    ]

    # Automated findings
    findings = []

    # Best ablation target (most impactful when removed = highest |delta_hr|)
    best_comp = max(ABLATION_TARGETS, key=lambda c: abs(ablation.get(c, {}).get("delta_hr") or 0))
    best_abl  = ablation.get(best_comp, {})
    if best_abl.get("delta_hr") is not None:
        findings.append(
            f"1. **{best_comp}** has the largest marginal impact on alignment quality "
            f"(removal changes HR by {_delta_str(best_abl['delta_hr'])})."
        )

    # Worst combination
    if bot_combos:
        bc = bot_combos[0]
        findings.append(
            f"2. Worst component agreement: **{bc['combo']}** — when these two agree, "
            f"HR={_fmt_hr(bc['hit_rate'])} (n={_fmt_n(bc['n'])}). May indicate co-linear noise."
        )

    # Best combination
    if top_combos:
        tc = top_combos[0]
        findings.append(
            f"3. Best component agreement: **{tc['combo']}** — HR={_fmt_hr(tc['hit_rate'])} (n={_fmt_n(tc['n'])})."
        )

    # Regime sensitivity
    vh_ret = df[df["conviction_level"].isin(["HIGH", "VERY_HIGH"])]["fwd_5d"].dropna()
    if len(vh_ret) >= MIN_SAMPLE:
        vh_hr = float((vh_ret > 0).mean())
        findings.append(
            f"4. HIGH/VERY_HIGH conviction universe: HR={_fmt_hr(vh_hr)}, n={_fmt_n(len(vh_ret))}. "
            f"Conviction filter is the primary quality gate."
        )

    for f in findings:
        lines.append(f)

    lines += [
        "",
        "---",
        "",
        "## Appendix: Methodology",
        "",
        "- **Walk-forward models:** Each date uses only a model trained ≥7 days prior (no look-ahead).",
        "- **Hit rate:** Fraction of directional calls (bullish or bearish, neutral excluded) where price moved in predicted direction over 5 trading days.",
        "- **Expectancy:** Mean actual 5d return for all directional rows (not direction-signed).",
        "- **Sharpe:** Annualised mean/std of 5d returns for directional rows × √252.",
        "- **IC:** Spearman rank correlation between signal strength and actual 5d return.",
        "- **Ablation:** Remove one component from the alignment weight calculation. Re-apply 1.15× threshold rule. Measure change in hit rate vs full-model baseline.",
        "- **Combination:** Restrict to rows where both components produce the same directional signal. Measure hit rate of the joint signal.",
        "- **Coverage:** % of all (ticker, date) rows where the layer produces a non-neutral directional signal.",
        "",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
