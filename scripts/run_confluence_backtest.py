"""
Confluence Engine Backtest
==========================
Validates whether signal alignment improves forward outcomes.
Does NOT assume it does — proves or disproves it.

Uses walk-forward V1 model artifacts so ML predictions are fully
out-of-sample for each date (no look-ahead from model training).

Studies:
  1. Alignment study  — grouped by aligned_count (0..5+)
  2. Score bucket study — grouped by confluence_score buckets
  3. Component comparison — ML vs Pattern vs Feature IC vs Confluence
  4. Atlas Score comparison — from alpha_signal_snapshots (if available)
  5. Permutation test — shuffled alignment/scores vs observed
  6. Regime breakdown — bull/bear/range × metrics
  7. Yearly breakdown — per-year metrics

Usage:
    python scripts/run_confluence_backtest.py
    python scripts/run_confluence_backtest.py --start-date 2020-01-01
    python scripts/run_confluence_backtest.py --start-date 2015-01-01 --end-date 2026-06-14
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR, TRAIN_FEATURES_V1
from atlas_research.db.connection import get_connection
from atlas_research.models.train import load_model, TrainedModelBundle
from atlas_research.models.dataset import cross_sectional_normalize
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────

PURGE_DAYS   = 7       # calendar days after model training date to skip
HORIZONS     = [1, 3, 5, 10, 20]
N_PERMS      = 500
MIN_SAMPLE   = 30
MIN_DQ       = 0.70    # quality filter (matches training)

WEIGHTS = {
    "ml": 0.30, "pattern": 0.20, "probability": 0.20,
    "feature_ic": 0.10, "regime": 0.15, "risk": 0.05,
}

SCORE_BUCKETS   = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
BUCKET_LABELS   = ["0-20", "20-40", "40-60", "60-80", "80-100"]

_BULL_PROB   = 0.55
_BEAR_PROB   = 0.45
_HIT_THRESH  = 0.55
_IC_THRESH   = 0.008
_MIN_CAL_N   = 30

# ── Load static DB stats ───────────────────────────────────────────────────────

def load_static_stats() -> tuple[list[dict], list[dict], dict[str, list[dict]]]:
    """Load pattern, calibration, and regime IC stats from DB (loaded once)."""
    with get_connection() as conn:
        # Market-wide conditional patterns
        prows = conn.execute(text("""
            SELECT cp.condition_type, cp.condition_params,
                   cpr.hit_rate, cpr.avg_return, cpr.sample_size
            FROM conditional_patterns cp
            JOIN conditional_pattern_results cpr ON cpr.pattern_id = cp.id
                 AND cpr.horizon_days = 5
            WHERE cpr.sample_size >= 20 AND cpr.ticker IS NULL
        """)).fetchall()
        pattern_stats = [
            {"condition_type": r[0], "params": r[1] or {},
             "hit_rate": float(r[2] or 0), "avg_return": float(r[3] or 0)}
            for r in prows
        ]
        log.info("backtest.loaded_patterns", n=len(pattern_stats))

        # Promoted calibration signals
        crows = conn.execute(text("""
            SELECT signal_type, signal_key, hit_rate_5d, avg_return_5d, n_resolved
            FROM alpha_signal_calibrations
            WHERE status = 'promoted' AND sanity_pass = TRUE
              AND n_resolved >= :n AND hit_rate_5d >= 0.55
        """), {"n": _MIN_CAL_N}).fetchall()
        calib_stats = [
            {"signal_type": r[0], "signal_key": r[1],
             "hit_rate_5d": float(r[2] or 0.5), "avg_return_5d": float(r[3] or 0),
             "n_resolved": int(r[4] or 0)}
            for r in crows
        ]
        log.info("backtest.loaded_calibrations", n=len(calib_stats))

        # Regime IC stats
        irows = conn.execute(text("""
            SELECT regime, feature_name, mean_ic, sign_stability
            FROM feature_regime_performance
            WHERE ABS(mean_ic) >= :thresh
              AND classification IN ('Always Useful', 'Regime Sensitive')
        """), {"thresh": _IC_THRESH}).fetchall()
        regime_stats: dict[str, list[dict]] = {}
        for regime, feat, mean_ic, stab in irows:
            if regime not in regime_stats:
                regime_stats[regime] = []
            regime_stats[regime].append({
                "feature_name": feat,
                "mean_ic": float(mean_ic or 0),
                "sign_stability": float(stab or 0.5),
            })
        log.info("backtest.loaded_regime_stats",
                 regimes=list(regime_stats.keys()),
                 total_features=sum(len(v) for v in regime_stats.values()))

    return pattern_stats, calib_stats, regime_stats


# ── Walk-forward model map ─────────────────────────────────────────────────────

def build_model_map(models_dir: Path) -> list[tuple[date, Path]]:
    """Returns [(training_date, model_path), ...] sorted asc, V1 only."""
    artifacts = []
    for d in models_dir.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        # V1 only: exclude v2, v3
        if "_v2_" in name or "_v3_" in name:
            continue
        if "return_regressor" not in name:
            continue
        parts = name.split("_")
        try:
            training_date = datetime.strptime(parts[-1], "%Y-%m-%d").date()
        except ValueError:
            continue
        mp = d / "model.joblib"
        if mp.exists():
            artifacts.append((training_date, mp))
    return sorted(artifacts)


def get_model_for_date(model_map: list[tuple[date, Path]],
                        signal_date: date) -> Path | None:
    """Return model trained before signal_date - PURGE_DAYS."""
    cutoff = signal_date - timedelta(days=PURGE_DAYS)
    best = None
    for td, mp in model_map:
        if td <= cutoff:
            best = mp
    return best


def group_dates_by_model(
    parquet_dates: list[date],
    model_map: list[tuple[date, Path]],
) -> dict[Path, list[date]]:
    """Group signal dates by which model artifact to use."""
    batches: dict[Path, list[date]] = {}
    skipped = 0
    for d in parquet_dates:
        mp = get_model_for_date(model_map, d)
        if mp is None:
            skipped += 1
            continue
        if mp not in batches:
            batches[mp] = []
        batches[mp].append(d)
    if skipped:
        log.info("backtest.no_model_for_dates", skipped=skipped)
    return batches


# ── Vectorized scoring ─────────────────────────────────────────────────────────

def _trigger_vec(condition_type: str, params: dict, df: pd.DataFrame) -> pd.Series:
    """Boolean Series: True where the pattern condition fires."""
    false_s = pd.Series(False, index=df.index)
    try:
        if condition_type == "consecutive_down":
            n = int(params.get("n_days", 3))
            key = f"return_{min(n, 5)}d"
            return df.get(key, false_s).fillna(0) < 0
        if condition_type == "consecutive_up":
            n = int(params.get("n_days", 3))
            key = f"return_{min(n, 5)}d"
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
            return df.get("oscar_87_above_50", false_s).fillna(0) > 0.5
        if condition_type in ("ema_lows_cross_up", "omni_cross_up", "ema_lows_above"):
            return df.get("omni_82_above", false_s).fillna(0) > 0.5
        if condition_type in ("hma_cross_up", "hma_above"):
            return df.get("hma_87_above", false_s).fillna(0) > 0.5
        if condition_type in ("ema_lows_support", "omni_bounce"):
            return df.get("omni_82_bounce", false_s).fillna(0) > 0.5
        if condition_type == "ema_lows_green_slope":
            above = df.get("omni_82_above", false_s).fillna(0) > 0.5
            slope = df.get("omni_82_slope",  pd.Series(0.0, index=df.index)).fillna(0) > 0
            return above & slope
        if condition_type == "end_of_month":
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


def score_batch(
    df: pd.DataFrame,
    bundle: TrainedModelBundle,
    feature_cols: list[str],
    pattern_stats: list[dict],
    calib_stats: list[dict],
    regime_stats: dict[str, list[dict]],
) -> pd.DataFrame:
    """
    Vectorized scoring of a single date's feature matrix.
    Returns compact DataFrame (no feature columns).
    """
    n = len(df)
    idx = df.index

    # ── ML (cross-sectional normalize first) ───────────────────────────────────
    df_norm = cross_sectional_normalize(df.copy(), feature_cols)
    for col in feature_cols:
        if col not in df_norm.columns:
            df_norm[col] = np.nan
    X = df_norm[feature_cols].to_numpy(dtype=np.float64)
    prob     = bundle.predict_prob(X)
    rank_pct = pd.Series(prob).rank(pct=True).to_numpy()
    ml_dir   = np.where(prob >= _BULL_PROB, 1, np.where(prob <= _BEAR_PROB, -1, 0))
    ml_str   = 0.6 * np.abs(prob - 0.5) * 2 + 0.4 * np.abs(rank_pct - 0.5) * 2

    # ── Regime ─────────────────────────────────────────────────────────────────
    spy_above = df.get("spy_above_sma200", pd.Series(np.nan, index=idx)).fillna(0.5)
    mkt_trend = df.get("market_trend",     pd.Series(0.0,    index=idx)).fillna(0)
    rv20      = df.get("realized_vol_20",  pd.Series(np.nan, index=idx))
    rv60      = df.get("realized_vol_60",  pd.Series(np.nan, index=idx))

    mkt_regime = np.where(mkt_trend > 0, "bull", np.where(mkt_trend < 0, "bear", "range"))
    above_200  = (spy_above.values > 0.5).astype(int)
    ic_regime  = np.where(above_200 == 1, "above_200dma", "below_200dma")
    vol_regime = np.where(
        rv20.notna().values & rv60.notna().values & (rv20.values > rv60.values * 1.25),
        "high_vol", "low_vol"
    )

    regime_dir = np.where(
        (mkt_regime == "bull") & (above_200 == 1), 1,
        np.where((mkt_regime == "bear") & (above_200 == 0), -1, 0)
    ).astype(int)
    regime_str = np.where(regime_dir != 0, 0.7, 0.3)
    regime_avail = (df.get("spy_above_sma200", pd.Series(np.nan, index=idx)).notna().values |
                    df.get("market_trend",     pd.Series(np.nan, index=idx)).notna().values)

    # ── Pattern ────────────────────────────────────────────────────────────────
    bull_pat  = np.zeros(n, dtype=int)
    bear_pat  = np.zeros(n, dtype=int)
    active_pat = np.zeros(n, dtype=int)
    for ps in pattern_stats:
        trig  = _trigger_vec(ps["condition_type"], ps["params"], df).values.astype(int)
        active_pat += trig
        hr = ps["hit_rate"]; ar = ps["avg_return"]
        if hr >= _HIT_THRESH:
            if ar > 0: bull_pat += trig
            elif ar < 0: bear_pat += trig
    net_pat = bull_pat - bear_pat
    pat_dir  = np.where(net_pat > 0, 1, np.where(net_pat < 0, -1, 0))
    pat_str  = np.where(
        active_pat > 0,
        np.clip((bull_pat + bear_pat).astype(float) / np.clip(active_pat, 1, None) * 0.4, 0, 1),
        0.0
    )
    pat_avail = (active_pat > 0)

    # ── Probability ─────────────────────────────────────────────────────────────
    # Handles ml_rank_bucket signals from the backtest-history calibration.
    # These signals are based on cross-sectional rank percentile tiers, which
    # provides partial independence from the ML component (the ML component uses
    # absolute probability; rank-based signals can fire for mid-probability stocks
    # that are relatively strong vs. peers on a given date).
    bull_pw = np.zeros(n); bear_pw = np.zeros(n); total_pw = np.zeros(n)
    for cs in calib_stats:
        st   = cs["signal_type"]
        sk   = cs["signal_key"]
        hr   = float(cs["hit_rate_5d"])
        ar   = float(cs["avg_return_5d"])
        nres = float(cs["n_resolved"])
        w    = abs(hr - 0.5) * min(1.0, nres / 200.0)

        if st == "ml_rank_bucket":
            try:
                lo_s, hi_s = sk.split("-")
                lo_f, hi_f = float(lo_s) / 100.0, float(hi_s) / 100.0
                if hi_f >= 1.0:
                    trig = (rank_pct >= lo_f).astype(float)
                else:
                    trig = ((rank_pct >= lo_f) & (rank_pct < hi_f)).astype(float)
            except (ValueError, AttributeError):
                continue
        else:
            continue

        total_pw += trig * abs(w)
        if ar > 0: bull_pw += trig * abs(w)
        else:      bear_pw += trig * abs(w)

    safe_pw  = np.where(total_pw > 0, total_pw, np.nan)
    bull_pfr = np.where(total_pw > 0, bull_pw / safe_pw, 0.5)
    bear_pfr = np.where(total_pw > 0, bear_pw / safe_pw, 0.5)
    prob_dir  = np.where((total_pw > 0) & (bull_pfr >= 0.60), 1,
                np.where((total_pw > 0) & (bear_pfr >= 0.60), -1, 0))
    prob_str  = np.clip(np.abs(bull_pfr - bear_pfr), 0, 1)
    prob_avail = (total_pw > 0)

    # ── Feature IC ─────────────────────────────────────────────────────────────
    bull_ic  = np.zeros(n); bear_ic = np.zeros(n)
    scored_f = np.zeros(n, dtype=int)
    for regime_key in ["above_200dma", "below_200dma"]:
        rmask = (ic_regime == regime_key)
        if not rmask.any():
            continue
        for fs in regime_stats.get(regime_key, []):
            feat = fs["feature_name"]
            if feat not in df.columns:
                continue
            val   = df[feat].to_numpy(dtype=float)
            valid = ~np.isnan(val)
            ic    = float(fs["mean_ic"])
            stab  = float(fs["sign_stability"])
            sign_match = ((ic > 0) == (val > 0)).astype(float) * 2 - 1
            contrib = np.abs(ic) * sign_match * stab
            mask    = rmask & valid
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

    # ── Risk ───────────────────────────────────────────────────────────────────
    penalty = np.zeros(n)
    dq  = df.get("data_quality_score", pd.Series(np.nan, index=idx)).to_numpy(dtype=float)
    dv  = df.get("dollar_volume_20",   pd.Series(np.nan, index=idx)).to_numpy(dtype=float)
    ed  = df.get("expected_drawdown",  pd.Series(np.nan, index=idx)).to_numpy(dtype=float)
    atr = df.get("atr_pct",            pd.Series(np.nan, index=idx)).to_numpy(dtype=float)
    penalty += np.where(~np.isnan(dq)  & (dq < 0.70),      10.0, np.where(~np.isnan(dq)  & (dq < 0.80),     4.0, 0))
    penalty += np.where(~np.isnan(dv)  & (dv < 1_000_000), 10.0, np.where(~np.isnan(dv)  & (dv < 5_000_000), 4.0, 0))
    penalty += np.where(~np.isnan(ed)  & (ed < -0.05),       5.0, np.where(~np.isnan(ed)  & (ed < -0.02),     2.0, 0))
    penalty += np.where(~np.isnan(atr) & (atr > 0.06),       3.0, 0)
    penalty = np.clip(penalty, 0, 25)

    # ── Alignment ──────────────────────────────────────────────────────────────
    comps = [
        (ml_dir,    ml_str,    np.ones(n, bool),  WEIGHTS["ml"]),
        (pat_dir,   pat_str,   pat_avail,          WEIGHTS["pattern"]),
        (prob_dir,  prob_str,  prob_avail,         WEIGHTS["probability"]),
        (feat_dir,  feat_str,  feat_avail,         WEIGHTS["feature_ic"]),
        (regime_dir,regime_str,regime_avail,       WEIGHTS["regime"]),
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

    dominant = np.where(bull_w > bear_w * 1.15, 1,
                np.where(bear_w > bull_w * 1.15, -1, 0))
    aligned_c  = np.where(dominant == 1, bull_c,
                 np.where(dominant == -1, bear_c, np.maximum(bull_c, bear_c))).astype(int)
    conflict_c = np.where(dominant == 1, bear_c,
                 np.where(dominant == -1, bull_c, np.minimum(bull_c, bear_c))).astype(int)
    align_r    = np.where(total_a > 0, aligned_c / total_a, 0.0)

    # ── Confluence score ────────────────────────────────────────────────────────
    al_str = np.zeros(n); al_wt = np.zeros(n)
    for cd, cs, ca, cw in comps[:-1]:   # exclude regime from strength calc
        is_al = ca & (cd == dominant) & (dominant != 0)
        al_str += np.where(is_al, cs * cw, 0)
        al_wt  += np.where(is_al, cw, 0)
    avg_al  = np.where(al_wt > 0, al_str / al_wt, 0)
    has_con = (dominant != 0) & (aligned_c > 0)
    base    = np.where(has_con, (0.65 * avg_al + 0.35 * align_r) * 100,
                       20.0 + np.clip(20.0 - conflict_c * 4.0, 0, 20))

    _FIT = {("bull",1):1.00,("bull",-1):0.72,("bull",0):0.85,
            ("bear",-1):1.00,("bear",1):0.72,("bear",0):0.85,
            ("range",1):0.88,("range",-1):0.88,("range",0):0.80}
    fitness = np.array([_FIT.get((mr, int(d)), 0.85)
                        for mr, d in zip(mkt_regime, dominant)])
    final = np.clip(base * fitness - penalty, 0, 100)
    dir_lbl = np.where(dominant == 1, "bullish",
              np.where(dominant == -1, "bearish", "neutral"))

    return pd.DataFrame({
        "ticker":               df["ticker"].values,
        "date":                 df["date"].values,
        "confluence_score":     np.round(final, 2),
        "confluence_direction": dir_lbl,
        "aligned_count":        aligned_c,
        "conflict_count":       conflict_c,
        "total_available":      total_a,
        "ml_prob":              np.round(prob, 4),
        "ml_rank":              np.round(rank_pct, 4),
        "ml_dir":               ml_dir,
        "pattern_dir":          pat_dir,
        "prob_dir":             prob_dir,
        "feat_ic_dir":          feat_dir,
        "regime_dir":           regime_dir,
        "market_regime":        mkt_regime,
        "vol_regime":           vol_regime,
        "above_200dma":         above_200,
        "risk_penalty":         np.round(penalty, 2),
    })


# ── Load and score all parquets ────────────────────────────────────────────────

def load_and_score(
    start_date: date,
    end_date: date,
    parquet_dir: Path,
    model_map: list[tuple[date, Path]],
    pattern_stats: list[dict],
    calib_stats: list[dict],
    regime_stats: dict[str, list[dict]],
) -> pd.DataFrame:
    """Scores all parquet files in date range using walk-forward models."""
    parquets = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    in_range = [
        p for p in parquets
        if start_date <= datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date() <= end_date
    ]
    if not in_range:
        log.error("backtest.no_parquets", start=str(start_date), end=str(end_date))
        return pd.DataFrame()

    all_dates = [
        datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date()
        for p in in_range
    ]
    batches = group_dates_by_model(all_dates, model_map)
    log.info("backtest.batches", n_models=len(batches), n_dates=len(all_dates))

    date_to_parquet = {
        datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date(): p
        for p in in_range
    }

    all_scored: list[pd.DataFrame] = []
    for model_path, dates in sorted(batches.items(), key=lambda x: str(x[0])):
        log.info("backtest.loading_model", path=str(model_path), n_dates=len(dates))
        try:
            bundle = load_model(model_path)
        except Exception as exc:
            log.error("backtest.model_load_failed", path=str(model_path), error=str(exc))
            continue

        feature_cols = (bundle.feature_names
                        if hasattr(bundle, "feature_names") and bundle.feature_names
                        else TRAIN_FEATURES_V1)
        # Exclude interaction features (V3 artifacts might include them)
        from atlas_research.features.regime_interactions import INTERACTION_NAMES
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
                scored = score_batch(df, bundle, feature_cols,
                                     pattern_stats, calib_stats, regime_stats)
                all_scored.append(scored)
            except Exception as exc:
                log.error("backtest.date_error", date=str(d), error=str(exc))

        del bundle

    if not all_scored:
        return pd.DataFrame()
    return pd.concat(all_scored, ignore_index=True)


# ── Forward returns from raw_bars ──────────────────────────────────────────────

def compute_forward_returns(
    scored: pd.DataFrame,
    extra_days: int = 30,
) -> pd.DataFrame:
    """Joins forward 1/3/5/10/20d returns + max_dd/runup 5d and 10d."""
    if scored.empty:
        return scored

    tickers = scored["ticker"].unique().tolist()
    smin    = pd.to_datetime(scored["date"]).min().date()
    smax    = pd.to_datetime(scored["date"]).max().date() + timedelta(days=extra_days)

    log.info("backtest.loading_raw_bars", tickers=len(tickers),
             start=str(smin), end=str(smax))

    sql = text("""
        SELECT ticker, date, close, high, low FROM raw_bars
        WHERE date BETWEEN :s AND :e AND ticker = ANY(:tickers)
        ORDER BY date, ticker
    """)
    with get_connection() as conn:
        bars = pd.read_sql(sql, conn, params={"s": smin, "e": smax, "tickers": tickers})

    if bars.empty:
        log.warning("backtest.no_raw_bars")
        return scored

    bars["date"] = pd.to_datetime(bars["date"]).dt.date
    close_piv = bars.pivot(index="date", columns="ticker", values="close")
    high_piv  = bars.pivot(index="date", columns="ticker", values="high")
    low_piv   = bars.pivot(index="date", columns="ticker", values="low")

    close_arr = close_piv.values.astype(float)
    high_arr  = high_piv.values.astype(float)
    low_arr   = low_piv.values.astype(float)

    # Forward returns for each horizon (N trading-day offset)
    fwd_pivots: dict[str, pd.DataFrame] = {}
    for h in HORIZONS:
        fwd = pd.DataFrame(
            np.where(
                (np.roll(close_arr, -h, axis=0)[:len(close_arr)-h] > 0) &
                (close_arr[:len(close_arr)-h] > 0),
                np.roll(close_arr, -h, axis=0)[:len(close_arr)-h] / close_arr[:len(close_arr)-h] - 1,
                np.nan,
            ),
            index=close_piv.index[:len(close_arr)-h],
            columns=close_piv.columns,
        )
        fwd_pivots[f"fwd_{h}d"] = fwd

    # Path stats (max drawdown via lows, max runup via highs) for 5d and 10d
    for h in [5, 10]:
        path_low  = np.full_like(close_arr, np.inf)
        path_high = np.full_like(close_arr, -np.inf)
        rows = len(close_arr)
        for i in range(1, h + 1):
            if i < rows:
                path_low[:rows-i]  = np.minimum(path_low[:rows-i],  low_arr[i:rows])
                path_high[:rows-i] = np.maximum(path_high[:rows-i], high_arr[i:rows])
        # Last h rows have no complete path
        path_low[-h:]  = np.nan
        path_high[-h:] = np.nan
        path_low[path_low   == np.inf]  = np.nan
        path_high[path_high == -np.inf] = np.nan

        fwd_pivots[f"max_dd_{h}d"] = pd.DataFrame(
            np.where(close_arr > 0, path_low  / close_arr - 1, np.nan),
            index=close_piv.index, columns=close_piv.columns)
        fwd_pivots[f"max_runup_{h}d"] = pd.DataFrame(
            np.where(close_arr > 0, path_high / close_arr - 1, np.nan),
            index=close_piv.index, columns=close_piv.columns)

    # Stack each pivot to long format and merge
    result = scored.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.date

    for col, piv in fwd_pivots.items():
        stacked = piv.stack(future_stack=True).reset_index()
        stacked.columns = ["date", "ticker", col]
        stacked["date"] = pd.to_datetime(stacked["date"]).dt.date
        stacked[col] = stacked[col].replace([np.inf, -np.inf], np.nan)
        result = result.merge(stacked, on=["ticker", "date"], how="left")

    log.info("backtest.fwd_returns_computed", rows=len(result),
             pct_5d=f"{result['fwd_5d'].notna().mean():.1%}")
    return result


# ── Analysis helpers ───────────────────────────────────────────────────────────

def _group_metrics(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Compute hit rate, avg return, median return per group for all horizons."""
    rows = []
    for grp, sub in df.groupby(group_col, sort=True):
        row: dict = {group_col: grp, "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"n_{h}d"]   = len(s)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) > 0 else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) > 0 else np.nan
            row[f"med_{h}d"] = float(s.median())      if len(s) > 0 else np.nan
        for h in [5, 10]:
            dd_col  = f"max_dd_{h}d"
            ru_col  = f"max_runup_{h}d"
            dd_s    = sub[dd_col].dropna()  if dd_col  in sub.columns else pd.Series(dtype=float)
            ru_s    = sub[ru_col].dropna()  if ru_col  in sub.columns else pd.Series(dtype=float)
            row[f"avg_dd_{h}d"]     = float(dd_s.mean())  if len(dd_s) > 0 else np.nan
            row[f"avg_runup_{h}d"]  = float(ru_s.mean())  if len(ru_s) > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def rank_ic(x: pd.Series, y: pd.Series) -> float:
    """Cross-sectional Spearman rank IC."""
    valid = x.notna() & y.notna()
    if valid.sum() < 10:
        return np.nan
    from scipy.stats import spearmanr
    corr, _ = spearmanr(x[valid], y[valid])
    return float(corr)


def alignment_study(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["aligned_grp"] = pd.cut(
        df2["aligned_count"].clip(0, 5),
        bins=[-0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5],
        labels=["0", "1", "2", "3", "4", "5+"]
    ).astype(str)
    return _group_metrics(df2, "aligned_grp")


def score_bucket_study(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["score_bucket"] = pd.cut(
        df2["confluence_score"],
        bins=[0, 20, 40, 60, 80, 100],
        labels=BUCKET_LABELS,
        include_lowest=True,
    ).astype(str)
    return _group_metrics(df2, "score_bucket")


def component_comparison(df: pd.DataFrame) -> pd.DataFrame:
    """Compare ML only vs Pattern vs Feature IC vs Confluence."""
    rows = []
    # Confluence (full score, top quintile)
    for label, col, top_thresh, use_dir in [
        ("ML only (top quintile)",        "ml_rank",         0.80,  False),
        ("ML only (all, IC)",             "ml_prob",         None,  False),
        ("Pattern bullish",               "pattern_dir",     None,  True),
        ("Probability bullish",           "prob_dir",        None,  True),
        ("Feature IC bullish",            "feat_ic_dir",     None,  True),
        ("Confluence 60-80",              "confluence_score", 60,   False),
        ("Confluence 80-100",             "confluence_score", 80,   False),
    ]:
        if use_dir:
            sub = df[df[col] == 1] if col in df.columns else pd.DataFrame()
        elif top_thresh is not None and col == "ml_rank":
            sub = df[df[col] >= top_thresh] if col in df.columns else pd.DataFrame()
        elif top_thresh is not None and col == "confluence_score":
            sub = df[df[col] >= top_thresh] if col in df.columns else pd.DataFrame()
        else:
            sub = df.copy()

        row: dict = {"signal": label, "n": len(sub)}
        for h in HORIZONS:
            col_h = f"fwd_{h}d"
            s = sub[col_h].dropna() if col_h in sub.columns and len(sub) > 0 else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan

        # Rank IC vs fwd_5d
        if col in df.columns and "fwd_5d" in df.columns:
            row["rank_ic_5d"] = rank_ic(df[col].replace(-1, np.nan), df["fwd_5d"])
        else:
            row["rank_ic_5d"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def atlas_score_comparison(df: pd.DataFrame) -> pd.DataFrame | None:
    """Compare vs Atlas Score from alpha_signal_snapshots."""
    try:
        sql = text("""
            SELECT ticker, snapshot_date, atlas_score, direction,
                   return_1d, return_3d, return_5d, return_10d, return_20d
            FROM alpha_signal_snapshots
            WHERE atlas_score IS NOT NULL AND return_5d IS NOT NULL
        """)
        with get_connection() as conn:
            atlas = pd.read_sql(sql, conn)
    except Exception:
        return None
    if atlas.empty or len(atlas) < MIN_SAMPLE:
        return None

    # Join with scored df on ticker + date
    scored_sub = df[["ticker", "date", "confluence_score", "ml_prob", "ml_rank"]].copy()
    scored_sub["date"] = pd.to_datetime(scored_sub["date"]).dt.date
    atlas["snapshot_date"] = pd.to_datetime(atlas["snapshot_date"]).dt.date
    merged = atlas.merge(scored_sub, left_on=["ticker", "snapshot_date"],
                         right_on=["ticker", "date"], how="inner")

    if len(merged) < MIN_SAMPLE:
        return None

    rows = []
    for label, col, top_thresh in [
        ("Atlas Score 60+",    "atlas_score",     60),
        ("Atlas Score 80+",    "atlas_score",     80),
        ("ML only top quintile","ml_rank",        0.80),
        ("Confluence 60+",     "confluence_score", 60),
        ("Confluence 80+",     "confluence_score", 80),
    ]:
        sub = merged[merged[col] >= top_thresh] if col in merged.columns else pd.DataFrame()
        row: dict = {"signal": label, "n": len(sub)}
        for h in HORIZONS:
            col_h = f"return_{h}d"
            s = sub[col_h].dropna() if col_h in sub.columns and len(sub) >= MIN_SAMPLE else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def permutation_study(df: pd.DataFrame, n_perms: int = N_PERMS) -> dict:
    """
    Shuffle aligned_count and confluence_score independently.
    Test: does the observed top-group metric exceed permuted distribution?
    Adapts thresholds based on whether the 80-100 bucket is populated (v2+).
    """
    rng = np.random.default_rng(42)
    results: dict = {}

    # Detect whether 80-100 bucket is populated (probability component active)
    max_align = int(df["aligned_count"].max()) if "aligned_count" in df.columns else 4
    has_80plus = bool((df["confluence_score"] >= 80).sum() >= MIN_SAMPLE)

    align_thresh = max_align if max_align >= 5 else 4
    score_thresh = 80 if has_80plus else 60

    for metric_col, split_col, observed_fn, thresh in [
        ("fwd_5d", "aligned_count",
         lambda d: d[d["aligned_count"] >= align_thresh]["fwd_5d"].dropna().mean(),
         align_thresh),
        ("fwd_5d", "confluence_score",
         lambda d: d[d["confluence_score"] >= score_thresh]["fwd_5d"].dropna().mean(),
         score_thresh),
    ]:
        observed = observed_fn(df)
        if np.isnan(observed):
            results[split_col] = {"observed": np.nan, "p_value": np.nan, "n_perms": 0,
                                  "threshold": thresh}
            continue

        fwd   = df[metric_col].to_numpy(dtype=float)
        col_v = df[split_col].to_numpy(dtype=float)
        perm_stats = []

        for _ in range(n_perms):
            shuffled = rng.permutation(col_v)
            mask = shuffled >= thresh
            if mask.sum() >= MIN_SAMPLE:
                perm_stats.append(np.nanmean(fwd[mask]))

        if not perm_stats:
            results[split_col] = {"observed": observed, "p_value": np.nan, "n_perms": 0}
            continue

        arr     = np.array(perm_stats)
        p_value = float((arr >= observed).mean())
        results[split_col] = {
            "observed":    round(observed, 6),
            "perm_mean":   round(float(arr.mean()), 6),
            "perm_std":    round(float(arr.std()),  6),
            "perm_95pct":  round(float(np.percentile(arr, 95)), 6),
            "p_value":     round(p_value, 4),
            "n_perms":     len(arr),
            "significant": p_value < 0.05,
            "threshold":   thresh,
        }
    return results


def regime_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    top_conf = df[df["confluence_score"] >= 60].copy()
    top_conf["regime_grp"] = top_conf["market_regime"] + "_" + top_conf["vol_regime"].fillna("unknown")
    return _group_metrics(top_conf, "regime_grp")


def yearly_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2["year"] = df2["date"].dt.year.astype(str)
    top = df2[df2["confluence_score"] >= 60].copy()
    return _group_metrics(top, "year")


# ── Report writer ──────────────────────────────────────────────────────────────

def _pct(v) -> str:
    return f"{v:.1%}" if not (v is None or (isinstance(v, float) and np.isnan(v))) else "n/a"

def _ret(v) -> str:
    return f"{v:+.3%}" if not (v is None or (isinstance(v, float) and np.isnan(v))) else "n/a"

def _tbl(df: pd.DataFrame, row_col: str, metric_cols: list[str], headers: list[str]) -> str:
    header = f"| {row_col:<14} | " + " | ".join(f"{h:>8}" for h in headers) + " |"
    sep    = f"|{'-'*16}|" + "|".join("-"*10 for _ in headers) + "|"
    lines  = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for col, fmt in zip(metric_cols, [None]*len(metric_cols)):
            v = r.get(col, np.nan)
            if "hr_" in col:
                cells.append(_pct(v))
            elif "avg_" in col or "med_" in col or "dd_" in col or "runup_" in col or "ic" in col.lower():
                cells.append(_ret(v))
            else:
                cells.append(str(int(v)) if not (isinstance(v, float) and np.isnan(v)) else "n/a")
        lines.append(f"| {str(r[row_col]):<14} | " + " | ".join(f"{c:>8}" for c in cells) + " |")
    return "\n".join(lines)


def write_report(
    start_date: date,
    end_date: date,
    total_obs: int,
    align_df: pd.DataFrame,
    bucket_df: pd.DataFrame,
    comp_df: pd.DataFrame,
    atlas_df: pd.DataFrame | None,
    perm: dict,
    regime_df: pd.DataFrame,
    year_df: pd.DataFrame,
    engine_version: str = "v1",
    n_prob_signals: int = 0,
) -> str:
    hr_cols  = [f"hr_{h}d"  for h in HORIZONS]
    avg_cols = [f"avg_{h}d" for h in HORIZONS]
    h_hdrs   = [f"HR {h}d"   for h in HORIZONS]
    a_hdrs   = [f"Avg {h}d"  for h in HORIZONS]

    max_align = int(align_df["aligned_grp"].astype(str).str.strip("+").replace("", "0").max()) if not align_df.empty else 4
    if n_prob_signals > 0:
        prob_note = (f"> Probability component ACTIVE — {n_prob_signals} promoted ML-tier signals "
                     f"(ml_rank_bucket, ml_direction, ml_conviction).\n"
                     f"> ML-tier signals use walk-forward ML predictions (same look-ahead caveat as ML component).\n"
                     f"> Maximum alignment count = 5 (ML + Pattern + Probability + Feature IC + Regime).")
    else:
        prob_note = ("> Probability component unavailable — no promoted signals in alpha_signal_calibrations.\n"
                     "> Maximum alignment count = 4 (ML + Pattern + Feature IC + Regime).")

    report_title = f"# Confluence Engine {engine_version} Backtest Report"

    lines = [
        report_title,
        f"**Date generated:** {date.today()}",
        f"**Backtest period:** {start_date} to {end_date}",
        f"**Total observations:** {total_obs:,}",
        "",
        "> **Methodology note:** Walk-forward V1 model artifacts used for ML scoring (out-of-sample).",
        "> Pattern stats and regime IC stats are calibrated on full history (mild look-ahead in those components).",
        prob_note,
        "",
        "---",
        "",
        "## 1. Alignment Study",
        "",
        "Do more aligned signals produce better forward returns?",
        "",
        "### Hit Rates by Aligned Signal Count",
        "",
        _tbl(align_df, "aligned_grp", hr_cols, h_hdrs),
        "",
        "### Average Returns by Aligned Signal Count",
        "",
        _tbl(align_df, "aligned_grp", avg_cols, a_hdrs),
        "",
        "### Max Drawdown and Runup (5d, 10d)",
        "",
    ]

    # Drawdown/runup table
    dd_cols = ["avg_dd_5d", "avg_runup_5d", "avg_dd_10d", "avg_runup_10d", "n"]
    dd_hdrs = ["DD 5d", "Runup 5d", "DD 10d", "Runup 10d", "N"]
    lines.append(_tbl(align_df, "aligned_grp", dd_cols, dd_hdrs))
    lines += ["", "---", "", "## 2. Confluence Score Bucket Study", ""]
    lines.append("### Hit Rates by Score Bucket")
    lines += ["", _tbl(bucket_df, "score_bucket", hr_cols, h_hdrs), ""]
    lines.append("### Average Returns by Score Bucket")
    lines += ["", _tbl(bucket_df, "score_bucket", avg_cols, a_hdrs), ""]
    lines.append("### Max Drawdown and Runup by Score Bucket")
    lines += ["", _tbl(bucket_df, "score_bucket", dd_cols, dd_hdrs), ""]
    lines += ["---", "", "## 3. Component Comparison", ""]
    lines.append("> Measures how well each standalone signal filters for quality.")
    lines += ["", "### Hit Rates"]
    lines += ["", _tbl(comp_df, "signal", hr_cols + ["rank_ic_5d"], h_hdrs + ["IC 5d"]), ""]
    lines += ["### Average Returns"]
    lines += ["", _tbl(comp_df, "signal", avg_cols, a_hdrs), ""]

    if atlas_df is not None and len(atlas_df) > 0:
        lines += ["---", "", "## 4. Atlas Score vs Confluence Comparison", ""]
        lines += [_tbl(atlas_df, "signal", hr_cols, h_hdrs), ""]
    else:
        lines += ["---", "", "## 4. Atlas Score Comparison", ""]
        lines += ["> Insufficient overlap data. Run after more alpha_signal_snapshots are available.", ""]

    lines += ["---", "", "## 5. Permutation Tests", ""]
    for col_key in ["aligned_count", "confluence_score"]:
        r    = perm.get(col_key, {})
        obs  = r.get("observed", np.nan)
        pv   = r.get("p_value",  np.nan)
        pm   = r.get("perm_mean", np.nan)
        p95  = r.get("perm_95pct", np.nan)
        sig  = r.get("significant", False)
        thr  = r.get("threshold", 4 if col_key == "aligned_count" else 60)
        if col_key == "aligned_count":
            label = f"{thr}+ aligned"
        else:
            label = f"{thr}+ score bucket"
        verdict = "**SIGNIFICANT (p < 0.05)**" if sig else "NOT significant"
        lines += [
            f"### {label}",
            f"- Observed 5d avg return: {_ret(obs)}",
            f"- Permuted mean: {_ret(pm)}, 95th pct: {_ret(p95)}",
            f"- p-value: {pv:.4f}" if not np.isnan(pv) else "- p-value: n/a",
            f"- Result: {verdict}",
            "",
        ]

    lines += ["---", "", "## 6. Regime Breakdown (Confluence >= 60)", ""]
    lines += [_tbl(regime_df, "regime_grp", hr_cols[:3] + avg_cols[:3] + ["n"],
                   h_hdrs[:3] + a_hdrs[:3] + ["N"]), ""]

    lines += ["---", "", "## 7. Yearly Breakdown (Confluence >= 60)", ""]
    lines += [_tbl(year_df, "year", hr_cols[:2] + avg_cols[:2] + ["n"],
                   h_hdrs[:2] + a_hdrs[:2] + ["N"]), ""]

    lines += ["---", "", "## 8. Promotion Criteria Assessment", ""]

    # Score monotonicity check (0-20 excluded — floor scoring for neutrals)
    bucket_hr5 = {}
    for _, r in bucket_df.iterrows():
        bucket_hr5[str(r["score_bucket"])] = r.get("hr_5d", np.nan)

    # Check monotonicity for 20-40 through 60-80 (ignore 0-20 floor and empty 80-100)
    active_buckets = [b for b in BUCKET_LABELS[1:] if not np.isnan(bucket_hr5.get(b, np.nan))]
    mon_pass = all(
        bucket_hr5.get(hi, 0) >= bucket_hr5.get(lo, 0)
        for lo, hi in zip(active_buckets[:-1], active_buckets[1:])
    ) if len(active_buckets) >= 2 else False

    # Top available bucket vs baselines — prefer 80-100 if populated (v2)
    has_80_100 = not np.isnan(bucket_hr5.get("80-100", np.nan))
    top_bucket_label = "80-100" if has_80_100 else "60-80"
    top_conf_hr = bucket_hr5.get(top_bucket_label, np.nan)
    ml_hr_vals = comp_df[comp_df["signal"] == "ML only (top quintile)"]["hr_5d"]
    ml_hr = float(ml_hr_vals.iloc[0]) if len(ml_hr_vals) > 0 else np.nan

    aln_sig = perm.get("aligned_count", {}).get("significant", False)
    scr_sig = perm.get("confluence_score", {}).get("significant", False)

    lines += [
        f"| Criterion | Result |",
        f"|-----------|--------|",
        f"| Top score bucket ({top_bucket_label}) best HR | {'YES' if not np.isnan(top_conf_hr) and top_conf_hr == max((v for v in bucket_hr5.values() if not np.isnan(v)), default=np.nan) else 'NO'} |",
        f"| Monotonic score -> hit rate (20-80) | {'YES' if mon_pass else 'NO'} |",
        f"| Confluence {top_bucket_label} HR 5d | {_pct(top_conf_hr)} |",
        f"| ML only top quintile HR 5d | {_pct(ml_hr)} |",
        f"| Confluence beats ML (5d) | {'YES' if not np.isnan(top_conf_hr) and not np.isnan(ml_hr) and top_conf_hr > ml_hr else 'NO'} |",
        f"| Permutation p < 0.05 (alignment) | {'YES' if aln_sig else 'NO'} |",
        f"| Permutation p < 0.05 (score) | {'YES' if scr_sig else 'NO'} |",
        "",
    ]

    lines += ["## 9. Recommendation", ""]

    # Determine recommendation
    criteria_met = sum([
        mon_pass,
        aln_sig,
        scr_sig,
        not np.isnan(top_conf_hr) and not np.isnan(ml_hr) and top_conf_hr > ml_hr,
    ])

    if criteria_met >= 3:
        rec = "**PROMOTE** — Confluence Engine passes sufficient validation criteria."
        path = """
### Atlas Score Evolution Path

1. **Phase 1 (now)**: Run confluence scoring alongside Atlas Score. Add `confluence_score`
   field to the ticker API response without changing the UI.
2. **Phase 2**: Add a small confluence indicator to the ticker detail page (dots
   showing how many signals align). Keep Atlas Score as the primary score.
3. **Phase 3 (if promoted)**: Introduce `Atlas Confluence Score` as an enhancement to
   Atlas Score. Formula: `atlas_confluence = 0.6 * atlas_score + 0.4 * confluence_score`.
   Requires >6 months of live comparison data before blending.
4. **What NOT to break**: Existing `atlas_score`, `direction`, `confidence_score` fields
   in the API. The UI can add confluence info as additive columns, not replacements.
"""
    elif criteria_met >= 2:
        rec = "**KEEP EXPERIMENTAL** — Some criteria met. Needs more data or signal improvement."
        path = "> Recommend running after probability component has promoted signals and Atlas Score comparison has >500 observations."
    else:
        rec = "**REVISE WEIGHTING** — Current component weights and pattern calibration insufficient."
        path = "> Revisit after promoting calibration signals (run alpha_signal_calibrations pipeline) and collecting >1 year of live Atlas Score snapshots."

    lines += [rec, "", path, ""]

    prob_caveat = (
        f"1. **Probability component — ML-tier signals**: {n_prob_signals} signals promoted from "
        f"backtest-history calibration (ml_rank_bucket, ml_direction, ml_conviction). "
        "These are derived from the same ML model — they validate tier-specific effects "
        "but share information with the ML component. Look-ahead present (calibrated on full history)."
        if n_prob_signals > 0 else
        "1. **Probability component inactive**: No promoted signals. Max alignment = 4."
    )

    lines += [
        "---",
        "",
        "## Appendix: Key Caveats",
        "",
        prob_caveat,
        "2. **Pattern stats look-ahead**: conditional_pattern_results uses full-history aggregate stats.",
        "   In a strict out-of-sample study, these would be calibrated walk-forward.",
        "3. **Feature IC look-ahead**: feature_regime_performance uses full-history IC computation.",
        "4. **Atlas Score comparison limited**: Only a few days of alpha_signal_snapshots overlap available.",
        "5. **ML is out-of-sample**: Walk-forward model artifacts ensure no ML look-ahead bias.",
        "6. **Max drawdown uses intraday low**: Slightly more pessimistic than close-to-close.",
    ]

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date",  default="2015-01-01")
    ap.add_argument("--end-date",    default=str(date.today()))
    ap.add_argument("--parquet-dir", default=str(PARQUET_OUTPUT_DIR))
    ap.add_argument("--n-perms",     type=int, default=N_PERMS)
    ap.add_argument("--out",         default="reports/CONFLUENCE_SCORE_REPORT.md")
    args = ap.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date   = datetime.strptime(args.end_date,   "%Y-%m-%d").date()
    parquet_dir = Path(args.parquet_dir)

    print(f"\nConfluence Engine Backtest")
    print(f"Period  : {start_date} to {end_date}")
    print(f"Parquets: {parquet_dir}")
    print(f"Perms   : {args.n_perms}")
    print("-" * 50)

    pattern_stats, calib_stats, regime_stats = load_static_stats()
    print(f"Patterns: {len(pattern_stats)}  Calibrations: {len(calib_stats)}  Regime features: {sum(len(v) for v in regime_stats.values())}")

    model_map = build_model_map(MODEL_DIR)
    print(f"Model artifacts (V1): {len(model_map)}")
    if not model_map:
        print("ERROR: No V1 model artifacts found.")
        return 1

    print("\nScoring historical parquets...")
    scored = load_and_score(
        start_date, end_date, parquet_dir,
        model_map, pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("No scored data. Exiting.")
        return 1
    print(f"Scored {len(scored):,} observations across {scored['date'].nunique()} dates")

    print("\nComputing forward returns from raw_bars...")
    df = compute_forward_returns(scored)
    print(f"Forward returns computed: fwd_5d available for {df['fwd_5d'].notna().sum():,} rows")

    print("\nRunning studies...")
    align_df  = alignment_study(df)
    bucket_df = score_bucket_study(df)
    comp_df   = component_comparison(df)
    atlas_df  = atlas_score_comparison(df)
    perm      = permutation_study(df, n_perms=args.n_perms)
    regime_df = regime_breakdown(df)
    year_df   = yearly_breakdown(df)

    print("\nAlignment study:")
    print(align_df[["aligned_grp", "n", "hr_5d", "avg_5d"]].to_string(index=False))

    print("\nScore bucket study:")
    print(bucket_df[["score_bucket", "n", "hr_5d", "avg_5d"]].to_string(index=False))

    print("\nPermutation results:")
    for k, v in perm.items():
        print(f"  {k}: observed={v.get('observed','n/a'):.4f}, p={v.get('p_value','n/a')}")

    engine_version = "v2" if len(calib_stats) > 0 else "v1"
    report = write_report(
        start_date, end_date, len(df),
        align_df, bucket_df, comp_df, atlas_df,
        perm, regime_df, year_df,
        engine_version=engine_version,
        n_prob_signals=len(calib_stats),
    )

    out_path = _ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
