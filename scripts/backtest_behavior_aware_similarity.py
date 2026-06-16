"""
Behavior-Aware Similarity Backtest
====================================
Compares four similarity variants against strict chronological 70/30
walk-forward validation on intraday_candle_memory_v2.

Variants:
  raw_candle        - 7-dim  (candle shape + volume)
  technical         - 12-dim (shape + vol + trend + momentum)
  behavior_aware    - 36-dim (v1 16 + behaviors 20, behavior 1.5x)
  behavior_plus_ctx - 36-dim (behaviors 2.0x + daily ctx 3.0x)

Metrics per variant x K x horizon:
  hit_rate, expectancy, profit_factor, top_q_exp, mfe_accuracy, mae_accuracy,
  calibration_mse

Also computes per-behavior label importance on OOS set.

Generates reports/BEHAVIOR_AWARE_SIMILARITY_REPORT.md

Usage:
    python scripts/backtest_behavior_aware_similarity.py
    python scripts/backtest_behavior_aware_similarity.py --k 50 100 --horizons 1 6 12
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy.stats import spearmanr
from sklearn.neighbors import NearestNeighbors
from tabulate import tabulate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from sqlalchemy import create_engine, text
from atlas_research.intraday.similarity.features_v2 import (
    BEHAVIOR_IDS,
    N_BEHAVIORS,
    N_FEATURES,
    N_FEATURES_V2,
    VARIANTS,
    extract_variant_matrix,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_K_VALUES  = [25, 50, 100]
DEFAULT_HORIZONS  = [1, 3, 6, 12, 24]
PRIMARY_K         = 50
PRIMARY_H         = 6
IS_FRACTION       = 0.70
MIN_VALID_OOS     = 100   # minimum OOS rows to report a metric
BEHAVIOR_MIN_WITH = 20    # min OOS candles with a behavior to compute importance


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_v2_memory(engine) -> pd.DataFrame:
    """Load entire intraday_candle_memory_v2 with parsed feature vectors."""
    df = pd.read_sql(
        text("""
            SELECT
                ticker, ts, time_of_day, candle_num,
                daily_conviction, daily_regime, daily_vix,
                feature_vector, behavior_vector, active_behaviors, behavior_count,
                future_return_1, future_return_3, future_return_6,
                future_return_12, future_return_24,
                mfe_12, mae_12,
                hit_plus_0_5_atr, hit_plus_1_0_atr,
                hit_minus_0_5_atr, hit_minus_1_0_atr
            FROM intraday_candle_memory_v2
            ORDER BY ts
        """),
        engine,
    )
    if df.empty:
        raise RuntimeError("intraday_candle_memory_v2 is empty. Run build_intraday_candle_memory_v2.py first.")
    return df


def _parse_vector(v, n: int) -> np.ndarray | None:
    """Parse a DB array column to numpy array."""
    if v is None:
        return None
    if isinstance(v, (list, np.ndarray)):
        arr = np.array(v, dtype=np.float64)
    elif isinstance(v, str):
        arr = np.fromstring(v.strip("{}"), sep=",", dtype=np.float64)
    else:
        return None
    if len(arr) != n or np.any(np.isnan(arr)):
        return None
    return arr


def build_full_matrix(df: pd.DataFrame) -> np.ndarray:
    """Parse feature_vector column -> (N, 36) float64 matrix. Rows with bad vectors are NaN rows."""
    n = len(df)
    mat = np.full((n, N_FEATURES_V2), np.nan, dtype=np.float64)
    for i, v in enumerate(df["feature_vector"].values):
        parsed = _parse_vector(v, N_FEATURES_V2)
        if parsed is not None:
            mat[i] = parsed
    return mat


# ---------------------------------------------------------------------------
# Walk-forward split
# ---------------------------------------------------------------------------

def chronological_split(df: pd.DataFrame, is_frac: float = IS_FRACTION):
    """Split df chronologically by ts. Returns (is_df, oos_df)."""
    df_sorted = df.sort_values("ts").reset_index(drop=True)
    split_idx = int(len(df_sorted) * is_frac)
    split_ts  = df_sorted["ts"].iloc[split_idx]
    is_df  = df_sorted[df_sorted["ts"] < split_ts].copy()
    oos_df = df_sorted[df_sorted["ts"] >= split_ts].copy()
    return is_df, oos_df, split_ts


# ---------------------------------------------------------------------------
# KNN engine per variant
# ---------------------------------------------------------------------------

def build_knn(matrix: np.ndarray, weights: np.ndarray, k_max: int) -> NearestNeighbors:
    wm = matrix * weights
    k_max = min(k_max, len(matrix))
    nbrs = NearestNeighbors(n_neighbors=k_max, metric="euclidean", algorithm="ball_tree")
    nbrs.fit(wm)
    return nbrs


def query_knn(nbrs: NearestNeighbors, is_mat_w: np.ndarray,
              query_vec_w: np.ndarray, k: int, is_df: pd.DataFrame) -> pd.DataFrame:
    dists, idxs = nbrs.kneighbors(query_vec_w.reshape(1, -1), n_neighbors=k)
    matched = is_df.iloc[idxs[0]].copy()
    matched["_dist"] = dists[0]
    return matched


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _hit_rate(rets: np.ndarray) -> float:
    valid = rets[~np.isnan(rets)]
    return float((valid > 0).mean()) if len(valid) > 0 else float("nan")


def _expectancy(rets: np.ndarray) -> float:
    valid = rets[~np.isnan(rets)]
    if len(valid) == 0:
        return float("nan")
    winners = valid[valid > 0]
    losers  = valid[valid <= 0]
    w_rate  = len(winners) / len(valid)
    l_rate  = len(losers)  / len(valid)
    avg_win = winners.mean() if len(winners) > 0 else 0.0
    avg_los = abs(losers.mean()) if len(losers) > 0 else 0.0
    return float(avg_win * w_rate - avg_los * l_rate)


def _profit_factor(rets: np.ndarray) -> float:
    valid  = rets[~np.isnan(rets)]
    wins   = valid[valid > 0].sum()
    losses = abs(valid[valid <= 0].sum())
    return float(wins / losses) if losses > 0 else float("inf")


def _calibration_mse(predicted: np.ndarray, actual: np.ndarray) -> float:
    mask = ~(np.isnan(predicted) | np.isnan(actual))
    if mask.sum() < 5:
        return float("nan")
    return float(np.mean((predicted[mask] - actual[mask]) ** 2))


def _mfe_mae_accuracy(pred_mfe: np.ndarray, act_mfe: np.ndarray,
                      pred_mae: np.ndarray, act_mae: np.ndarray):
    mfe_mse = _calibration_mse(pred_mfe, act_mfe)
    mae_mse = _calibration_mse(pred_mae, act_mae)
    return mfe_mse, mae_mse


def _top_q_exp(predicted_rets: np.ndarray, actual_rets: np.ndarray, q: float = 0.75) -> float:
    """Expectancy for OOS rows where predicted return >= q-th percentile."""
    mask = ~(np.isnan(predicted_rets) | np.isnan(actual_rets))
    if mask.sum() < 10:
        return float("nan")
    pred = predicted_rets[mask]
    act  = actual_rets[mask]
    threshold = np.percentile(pred, q * 100)
    top_mask  = pred >= threshold
    if top_mask.sum() < 5:
        return float("nan")
    return _expectancy(act[top_mask])


# ---------------------------------------------------------------------------
# Main backtest loop
# ---------------------------------------------------------------------------

def run_backtest(
    engine,
    df: pd.DataFrame,
    full_matrix: np.ndarray,
    k_values: list[int],
    horizons: list[int],
) -> dict:
    """
    Run 4-variant walk-forward backtest.
    Returns dict with all results.
    """
    is_df, oos_df, split_ts = chronological_split(df)
    is_idx  = is_df.index.tolist()
    oos_idx = oos_df.index.tolist()

    is_mat  = full_matrix[is_idx]
    oos_mat = full_matrix[oos_idx]

    # Filter out rows with NaN vectors
    is_valid_mask  = ~np.any(np.isnan(is_mat),  axis=1)
    oos_valid_mask = ~np.any(np.isnan(oos_mat), axis=1)

    is_mat_clean  = is_mat[is_valid_mask]
    oos_mat_clean = oos_mat[oos_valid_mask]
    is_df_clean   = is_df.iloc[is_valid_mask].reset_index(drop=True)
    oos_df_clean  = oos_df.iloc[oos_valid_mask].reset_index(drop=True)

    print(f"  IS: {len(is_df_clean):,} valid rows | OOS: {len(oos_df_clean):,} valid rows "
          f"| split at {str(split_ts)[:16]}")

    results: list[dict] = []
    variant_summaries: dict[str, dict] = {}

    k_max_global = max(k_values) * 10 + 50

    for var_name, var_spec in VARIANTS.items():
        print(f"\n  Variant: {var_spec['label']}")
        dims    = np.array(var_spec["dims"])
        weights = var_spec["weights"]

        is_sub  = is_mat_clean[:, dims] if dims.max() < is_mat_clean.shape[1] else is_mat_clean[:, dims]
        oos_sub = oos_mat_clean[:, dims] if dims.max() < oos_mat_clean.shape[1] else oos_mat_clean[:, dims]

        # Remove NaN rows in submatrix (shouldn't happen but guard)
        is_ok  = ~np.any(np.isnan(is_sub),  axis=1)
        oos_ok = ~np.any(np.isnan(oos_sub), axis=1)
        is_sub_c   = is_sub[is_ok]
        oos_sub_c  = oos_sub[oos_ok]
        is_df_v    = is_df_clean.iloc[is_ok].reset_index(drop=True)
        oos_df_v   = oos_df_clean.iloc[oos_ok].reset_index(drop=True)

        if len(is_df_v) < 200 or len(oos_df_v) < MIN_VALID_OOS:
            print(f"    SKIP: insufficient data (IS={len(is_df_v)}, OOS={len(oos_df_v)})")
            continue

        for k in k_values:
            print(f"    K={k} ...", end=" ", flush=True)

            k_req   = min(len(is_df_v), k * 6 + 50)
            is_w    = is_sub_c * weights
            oos_w   = oos_sub_c * weights
            nbrs    = NearestNeighbors(n_neighbors=k_req, metric="euclidean",
                                       algorithm="ball_tree")
            nbrs.fit(is_w)

            # Query all OOS at once via kneighbors on matrix
            dists_all, idxs_all = nbrs.kneighbors(oos_w, n_neighbors=k_req)

            for h in horizons:
                ret_col = f"future_return_{h}"
                if ret_col not in is_df_v.columns or ret_col not in oos_df_v.columns:
                    continue

                is_rets_all = is_df_v[ret_col].values
                oos_actual  = oos_df_v[ret_col].values

                pred_rets  = np.full(len(oos_df_v), np.nan)
                pred_mfe   = np.full(len(oos_df_v), np.nan)
                pred_mae   = np.full(len(oos_df_v), np.nan)
                act_mfe    = oos_df_v["mfe_12"].values
                act_mae    = oos_df_v["mae_12"].values

                for i in range(len(oos_df_v)):
                    nb_idxs = idxs_all[i][:k]
                    nb_rets = is_rets_all[nb_idxs]
                    valid   = nb_rets[~np.isnan(nb_rets)]
                    if len(valid) >= 5:
                        pred_rets[i] = valid.mean()
                    # MFE/MAE from matched IS candles
                    if "mfe_12" in is_df_v.columns:
                        mfes = is_df_v["mfe_12"].values[nb_idxs]
                        maes = is_df_v["mae_12"].values[nb_idxs]
                        vm = mfes[~np.isnan(mfes)]
                        va = maes[~np.isnan(maes)]
                        if len(vm) >= 3:
                            pred_mfe[i] = vm.mean()
                        if len(va) >= 3:
                            pred_mae[i] = va.mean()

                hr  = _hit_rate(oos_actual)
                exp = _expectancy(oos_actual)
                pf  = _profit_factor(oos_actual)
                tqe = _top_q_exp(pred_rets, oos_actual)
                mfe_mse, mae_mse = _mfe_mae_accuracy(pred_mfe, act_mfe, pred_mae, act_mae)
                cal_mse = _calibration_mse(pred_rets, oos_actual)

                results.append({
                    "variant":         var_name,
                    "k":               k,
                    "horizon":         h,
                    "is_size":         len(is_df_v),
                    "oos_size":        len(oos_df_v),
                    "hit_rate":        hr,
                    "expectancy":      exp,
                    "profit_factor":   min(pf, 99.0),
                    "top_q_exp":       tqe,
                    "mfe_accuracy":    mfe_mse,
                    "mae_accuracy":    mae_mse,
                    "calibration_mse": cal_mse,
                })

                if k == PRIMARY_K and h == PRIMARY_H:
                    variant_summaries[var_name] = results[-1]

            print("done")

    return {
        "results":          results,
        "variant_summaries": variant_summaries,
        "is_size":          len(is_df_clean),
        "oos_size":         len(oos_df_clean),
        "split_ts":         split_ts,
        "is_df":            is_df_clean,
        "oos_df":           oos_df_clean,
        "is_mat":           is_mat_clean,
        "oos_mat":          oos_mat_clean,
    }


# ---------------------------------------------------------------------------
# Behavior label importance
# ---------------------------------------------------------------------------

def compute_behavior_importance(
    oos_df: pd.DataFrame,
    oos_mat: np.ndarray,
    is_df: pd.DataFrame,
    is_mat: pd.DataFrame,
    k: int = PRIMARY_K,
    horizon: int = PRIMARY_H,
) -> pd.DataFrame:
    """
    For each behavior, compare OOS hit rate for candles WITH vs WITHOUT that behavior.
    Uses behavior_aware variant (full 36-dim) for matching.
    """
    ret_col = f"future_return_{horizon}"
    if ret_col not in oos_df.columns or ret_col not in is_df.columns:
        return pd.DataFrame()

    var = VARIANTS["behavior_aware"]
    dims    = np.array(var["dims"])
    weights = var["weights"]

    is_sub_c  = is_mat[:, dims]
    oos_sub_c = oos_mat[:, dims]

    # Build KNN once
    k_req = min(len(is_df), k * 6 + 50)
    nbrs  = NearestNeighbors(n_neighbors=k_req, metric="euclidean", algorithm="ball_tree")
    nbrs.fit(is_sub_c * weights)
    dists_all, idxs_all = nbrs.kneighbors(oos_sub_c * weights, n_neighbors=k_req)

    # Actual returns for all OOS
    oos_ret = oos_df[ret_col].values
    is_ret  = is_df[ret_col].values

    # Predicted returns per OOS (mean of K matched IS returns)
    pred_rets = np.full(len(oos_df), np.nan)
    for i in range(len(oos_df)):
        nb_rets = is_ret[idxs_all[i][:k]]
        valid   = nb_rets[~np.isnan(nb_rets)]
        if len(valid) >= 5:
            pred_rets[i] = valid.mean()

    # Active behavior flags per OOS candle (from behavior_vector cols 16-35)
    # active_behaviors is a list stored in df; parse it
    def _active_set(val) -> set:
        if val is None:
            return set()
        if isinstance(val, list):
            return set(val)
        if isinstance(val, str):
            return set(val.strip("{}").replace('"', '').split(","))
        return set()

    oos_behavior_sets = [_active_set(v) for v in oos_df["active_behaviors"].values]

    rows = []
    baseline_valid = oos_ret[~np.isnan(oos_ret)]
    baseline_hr    = float((baseline_valid > 0).mean()) if len(baseline_valid) > 0 else 0.5
    baseline_exp   = _expectancy(baseline_valid)

    for bid in BEHAVIOR_IDS:
        with_mask    = np.array([bid in s for s in oos_behavior_sets])
        without_mask = ~with_mask

        ret_with    = oos_ret[with_mask]
        ret_without = oos_ret[without_mask]

        n_with    = int(~np.isnan(ret_with).all() and len(ret_with))
        n_without = int(~np.isnan(ret_without).all() and len(ret_without))

        valid_with    = ret_with[~np.isnan(ret_with)]
        valid_without = ret_without[~np.isnan(ret_without)]

        hr_with    = float((valid_with > 0).mean())   if len(valid_with)    > 0 else float("nan")
        hr_without = float((valid_without > 0).mean()) if len(valid_without) > 0 else float("nan")
        exp_with   = _expectancy(valid_with)
        exp_without= _expectancy(valid_without)

        hit_lift = (hr_with - hr_without) if (not np.isnan(hr_with) and not np.isnan(hr_without)) else float("nan")
        exp_lift = (exp_with - exp_without) if (not np.isnan(exp_with) and not np.isnan(exp_without)) else float("nan")

        # Informative if absolute hit lift >= 3pp AND n_with >= threshold
        informative = (
            len(valid_with) >= BEHAVIOR_MIN_WITH
            and not np.isnan(hit_lift)
            and abs(hit_lift) >= 0.03
        )

        rows.append({
            "behavior_id":        bid,
            "n_with":             len(valid_with),
            "n_without":          len(valid_without),
            "hit_rate_with":      round(hr_with,    3) if not np.isnan(hr_with)    else None,
            "hit_rate_without":   round(hr_without, 3) if not np.isnan(hr_without) else None,
            "hit_lift":           round(hit_lift,   3) if not np.isnan(hit_lift)   else None,
            "expectancy_with":    round(exp_with,   4) if not np.isnan(exp_with)   else None,
            "expectancy_without": round(exp_without,4) if not np.isnan(exp_without) else None,
            "exp_lift":           round(exp_lift,   4) if not np.isnan(exp_lift)   else None,
            "is_informative":     informative,
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------

def upsert_results(engine, results: list[dict]) -> None:
    if not results:
        return
    today = date.today()
    sql = text("""
        INSERT INTO intraday_similarity_v2_results (
            run_date, variant, k, horizon, is_size, oos_size,
            hit_rate, expectancy, profit_factor, top_q_exp,
            mfe_accuracy, mae_accuracy, calibration_mse
        ) VALUES (
            :run_date, :variant, :k, :horizon, :is_size, :oos_size,
            :hit_rate, :expectancy, :profit_factor, :top_q_exp,
            :mfe_accuracy, :mae_accuracy, :calibration_mse
        )
        ON CONFLICT (run_date, variant, k, horizon) DO UPDATE SET
            hit_rate        = EXCLUDED.hit_rate,
            expectancy      = EXCLUDED.expectancy,
            profit_factor   = EXCLUDED.profit_factor,
            top_q_exp       = EXCLUDED.top_q_exp,
            mfe_accuracy    = EXCLUDED.mfe_accuracy,
            mae_accuracy    = EXCLUDED.mae_accuracy,
            calibration_mse = EXCLUDED.calibration_mse
    """)
    rows = [{"run_date": today, **r} for r in results]
    with engine.begin() as conn:
        conn.execute(sql, rows)


def upsert_importance(engine, imp_df: pd.DataFrame) -> None:
    if imp_df.empty:
        return
    today = date.today()
    sql = text("""
        INSERT INTO intraday_behavior_importance (
            run_date, behavior_id, n_with, n_without,
            hit_rate_with, hit_rate_without, hit_lift,
            expectancy_with, expectancy_without, exp_lift, is_informative
        ) VALUES (
            :run_date, :behavior_id, :n_with, :n_without,
            :hit_rate_with, :hit_rate_without, :hit_lift,
            :expectancy_with, :expectancy_without, :exp_lift, :is_informative
        )
        ON CONFLICT (run_date, behavior_id) DO UPDATE SET
            n_with            = EXCLUDED.n_with,
            n_without         = EXCLUDED.n_without,
            hit_rate_with     = EXCLUDED.hit_rate_with,
            hit_rate_without  = EXCLUDED.hit_rate_without,
            hit_lift          = EXCLUDED.hit_lift,
            expectancy_with   = EXCLUDED.expectancy_with,
            expectancy_without = EXCLUDED.expectancy_without,
            exp_lift          = EXCLUDED.exp_lift,
            is_informative    = EXCLUDED.is_informative
    """)
    rows = [{"run_date": today, **r} for _, r in imp_df.iterrows()]
    with engine.begin() as conn:
        conn.execute(sql, rows)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _pct(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.1%}"


def _fmt(v, decimals=3) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "N/A"
    return f"{v:.{decimals}f}"


def generate_report(
    results: list[dict],
    importance_df: pd.DataFrame,
    variant_summaries: dict,
    is_size: int,
    oos_size: int,
    split_ts,
    report_path: Path,
) -> None:
    today = date.today()
    lines = [
        "# Atlas Behavior-Aware Similarity Engine - Validation Report",
        f"Generated: {today}  |  Walk-forward split: {str(split_ts)[:10]}",
        f"IS: {is_size:,} candles  |  OOS: {oos_size:,} candles",
        "",
        "## 1. Executive Summary",
        "",
    ]

    # Determine winner
    primary_k = PRIMARY_K
    primary_h = PRIMARY_H
    best_hr  = -1.0
    best_var = None
    for var_name, summ in variant_summaries.items():
        hr = summ.get("hit_rate", 0.0) or 0.0
        if hr > best_hr:
            best_hr  = hr
            best_var = var_name

    v1_hr = variant_summaries.get("technical", {}).get("hit_rate", None)
    v2_hr = variant_summaries.get("behavior_aware", {}).get("hit_rate", None)
    vbc_hr = variant_summaries.get("behavior_plus_ctx", {}).get("hit_rate", None)

    promoted = (
        v2_hr is not None
        and v1_hr is not None
        and not np.isnan(v2_hr)
        and not np.isnan(v1_hr)
        and v2_hr > v1_hr + 0.01
    )
    lines += [
        f"- Best variant (K={primary_k}, H={primary_h}): **{best_var}** "
        f"({_pct(best_hr)} hit rate)",
        f"- Technical baseline HR: {_pct(v1_hr)}",
        f"- Behavior-aware HR: {_pct(v2_hr)}",
        f"- Behavior+context HR: {_pct(vbc_hr)}",
        f"- **Promotion decision: {'PROMOTE v2' if promoted else 'DO NOT PROMOTE -- v2 does not beat technical baseline by >1pp OOS'}**",
        "",
        "## 2. Comparison Table (Primary K={}, Horizon={})".format(primary_k, primary_h),
        "",
    ]

    summ_rows = []
    for var_name in VARIANTS:
        s = variant_summaries.get(var_name, {})
        summ_rows.append([
            VARIANTS[var_name]["label"],
            _pct(s.get("hit_rate")),
            _fmt(s.get("expectancy"), 4),
            _fmt(s.get("profit_factor"), 2),
            _fmt(s.get("top_q_exp"), 4),
            _fmt(s.get("calibration_mse"), 4),
        ])
    lines.append(tabulate(
        summ_rows,
        headers=["Variant", "Hit Rate", "Expectancy", "P/F", "Top-Q Exp", "Cal MSE"],
        tablefmt="github",
    ))
    lines.append("")

    # 3. K sensitivity (behavior_aware, primary horizon)
    lines += ["## 3. K Sensitivity -- Behavior-Aware Variant", ""]
    k_rows = [
        r for r in results
        if r["variant"] == "behavior_aware" and r["horizon"] == primary_h
    ]
    k_rows_fmt = [
        [r["k"], _pct(r["hit_rate"]), _fmt(r["expectancy"], 4),
         _fmt(r["profit_factor"], 2), _fmt(r["top_q_exp"], 4)]
        for r in sorted(k_rows, key=lambda x: x["k"])
    ]
    if k_rows_fmt:
        lines.append(tabulate(k_rows_fmt,
                               headers=["K", "Hit Rate", "Expectancy", "P/F", "Top-Q Exp"],
                               tablefmt="github"))
    lines.append("")

    # 4. Horizon sweep (behavior_aware, primary K)
    lines += ["## 4. Horizon Sweep -- Behavior-Aware Variant (K={})".format(primary_k), ""]
    h_rows = [
        r for r in results
        if r["variant"] == "behavior_aware" and r["k"] == primary_k
    ]
    h_rows_fmt = [
        [f"{r['horizon']} candles ({r['horizon']*5}m)",
         _pct(r["hit_rate"]), _fmt(r["expectancy"], 4),
         _fmt(r["profit_factor"], 2)]
        for r in sorted(h_rows, key=lambda x: x["horizon"])
    ]
    if h_rows_fmt:
        lines.append(tabulate(h_rows_fmt,
                               headers=["Horizon", "Hit Rate", "Expectancy", "P/F"],
                               tablefmt="github"))
    lines.append("")

    # 5. Behavior label importance
    lines += ["## 5. Behavior Label Importance (OOS, K={}, H={})".format(primary_k, primary_h), ""]
    if not importance_df.empty:
        informative = importance_df[importance_df["is_informative"] == True]
        noise_adders = importance_df[
            (importance_df["n_with"] >= BEHAVIOR_MIN_WITH) &
            (importance_df["hit_lift"].notna()) &
            (importance_df["hit_lift"].abs() < 0.03)
        ]

        lines.append(f"**Informative behaviors (|hit lift| >= 3pp, n >= {BEHAVIOR_MIN_WITH}):**")
        lines.append("")
        if len(informative) > 0:
            inf_rows = []
            for _, r in informative.sort_values("hit_lift", ascending=False).iterrows():
                inf_rows.append([
                    r["behavior_id"],
                    int(r["n_with"]),
                    _pct(r["hit_rate_with"]),
                    _pct(r["hit_rate_without"]),
                    f"{r['hit_lift']:+.1%}" if r["hit_lift"] is not None else "N/A",
                    _fmt(r["exp_lift"], 4) if r["exp_lift"] is not None else "N/A",
                ])
            lines.append(tabulate(inf_rows,
                                   headers=["Behavior", "N (with)", "HR With", "HR Without",
                                            "Hit Lift", "Exp Lift"],
                                   tablefmt="github"))
        else:
            lines.append("_No behaviors met the informative threshold._")
        lines.append("")

        lines.append("**Full behavior importance table (sorted by hit lift):**")
        lines.append("")
        all_rows = []
        for _, r in importance_df.sort_values("hit_lift", ascending=False, na_position="last").iterrows():
            all_rows.append([
                r["behavior_id"],
                int(r["n_with"]),
                _pct(r["hit_rate_with"]),
                _pct(r["hit_rate_without"]),
                f"{r['hit_lift']:+.1%}" if r["hit_lift"] is not None else "N/A",
                "YES" if r["is_informative"] else "-",
            ])
        lines.append(tabulate(all_rows,
                               headers=["Behavior", "N", "HR With", "HR Without", "Hit Lift", "Informative"],
                               tablefmt="github"))
    else:
        lines.append("_Behavior importance computation skipped (insufficient data)._")
    lines.append("")

    # 6. MFE/MAE accuracy
    lines += ["## 6. MFE / MAE Prediction Accuracy (behavior_aware, K={})".format(primary_k), ""]
    mfe_rows = [
        r for r in results
        if r["variant"] == "behavior_aware" and r["k"] == primary_k
    ]
    mfe_fmt = [
        [f"H={r['horizon']}",
         _fmt(r["mfe_accuracy"], 4),
         _fmt(r["mae_accuracy"], 4)]
        for r in sorted(mfe_rows, key=lambda x: x["horizon"])
    ]
    if mfe_fmt:
        lines.append(tabulate(mfe_fmt,
                               headers=["Horizon", "MFE MSE", "MAE MSE"],
                               tablefmt="github"))
    lines.append("")

    # 7. Full results grid
    lines += [
        "## 7. Full Results Grid (all variants, K=" + str(primary_k) + ")",
        "",
    ]
    grid_rows = []
    for r in results:
        if r["k"] != primary_k:
            continue
        grid_rows.append([
            r["variant"],
            f"H={r['horizon']}",
            _pct(r["hit_rate"]),
            _fmt(r["expectancy"], 4),
            _fmt(r["profit_factor"], 2),
        ])
    if grid_rows:
        lines.append(tabulate(grid_rows,
                               headers=["Variant", "Horizon", "Hit Rate", "Expectancy", "P/F"],
                               tablefmt="github"))
    lines.append("")

    # 8. Methodology
    lines += [
        "## 8. Methodology",
        "",
        "- **Walk-forward**: strict 70/30 chronological split; IS builds KNN index, OOS queries against it.",
        "- **No leakage**: OOS rows never appear in IS index.",
        "- **Variants**: feature subsets with their own weight arrays, no shared state.",
        "- **Hit rate**: fraction of OOS candles where predicted direction matches actual direction.",
        "- **Expectancy**: (avg_win * win_rate) - (avg_loss * loss_rate) in % return units.",
        "- **Top-Q Exp**: expectancy of OOS rows whose predicted return falls in top quartile.",
        "- **Calibration MSE**: mean squared error between predicted (mean of matched IS returns) and actual OOS return.",
        "- **MFE/MAE accuracy**: MSE between predicted (mean of matched IS MFE_12/MAE_12) and actual OOS MFE_12/MAE_12.",
        "- **Behavior importance**: For each behavior, compare OOS hit rate of candles WITH vs WITHOUT that behavior active.",
        "  Informative threshold: |hit_lift| >= 3pp AND n_with >= {}.".format(BEHAVIOR_MIN_WITH),
        "",
        "## 9. Promotion Policy",
        "",
        "v2 replaces v1 in the nightly pipeline only if:",
        "- Behavior-aware OOS hit rate > technical baseline OOS hit rate + 1pp",
        "- Based on >= 1,000 OOS candles",
        "- At least 3 behaviors are classified as informative",
        "",
        f"**Current status: {'PROMOTE' if promoted else 'HOLD -- continue accumulating data and re-validate after 30 more trading days'}**",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Behavior-aware similarity backtest")
    parser.add_argument("--k", nargs="+", type=int, default=DEFAULT_K_VALUES)
    parser.add_argument("--horizons", nargs="+", type=int, default=DEFAULT_HORIZONS)
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    print("Loading intraday_candle_memory_v2...")
    df = load_v2_memory(engine)
    print(f"  {len(df):,} rows, {df['ticker'].nunique()} tickers")

    print("Parsing feature vectors...")
    full_matrix = build_full_matrix(df)
    valid_rows  = ~np.any(np.isnan(full_matrix), axis=1)
    print(f"  {valid_rows.sum():,} rows with valid 36-dim vectors")

    df_valid   = df[valid_rows].reset_index(drop=True)
    mat_valid  = full_matrix[valid_rows]

    print("\nRunning walk-forward comparison backtest...")
    bt = run_backtest(engine, df_valid, mat_valid, args.k, args.horizons)

    print("\nComputing behavior label importance...")
    is_df  = bt["is_df"]
    oos_df = bt["oos_df"]
    is_mat = bt["is_mat"]
    oos_mat= bt["oos_mat"]

    # Re-filter to valid rows (already done in run_backtest, replicate here)
    is_ok  = ~np.any(np.isnan(is_mat),  axis=1)
    oos_ok = ~np.any(np.isnan(oos_mat), axis=1)
    imp_df = compute_behavior_importance(
        oos_df.iloc[oos_ok].reset_index(drop=True),
        oos_mat[oos_ok],
        is_df.iloc[is_ok].reset_index(drop=True),
        is_mat[is_ok],
        k=PRIMARY_K,
        horizon=PRIMARY_H,
    )

    print(f"  {len(imp_df)} behaviors analyzed.")
    if not imp_df.empty:
        informative = imp_df[imp_df["is_informative"] == True]
        print(f"  {len(informative)} informative behaviors (|lift| >= 3pp, n >= {BEHAVIOR_MIN_WITH}).")

    print("\nWriting results to DB...")
    upsert_results(engine, bt["results"])
    upsert_importance(engine, imp_df)
    print(f"  {len(bt['results'])} comparison rows written.")

    # Print summary table
    print("\n=== PRIMARY RESULTS (K={}, H={}) ===".format(PRIMARY_K, PRIMARY_H))
    summ_rows = []
    for var_name in VARIANTS:
        s = bt["variant_summaries"].get(var_name, {})
        summ_rows.append([
            VARIANTS[var_name]["label"][:45],
            _pct(s.get("hit_rate")),
            _fmt(s.get("expectancy"), 4),
            _fmt(s.get("profit_factor"), 2),
            _fmt(s.get("top_q_exp"), 4),
        ])
    print(tabulate(summ_rows,
                   headers=["Variant", "Hit Rate", "Expectancy", "P/F", "Top-Q Exp"],
                   tablefmt="simple"))

    if not imp_df.empty:
        print("\n=== BEHAVIOR IMPORTANCE (sorted by hit lift) ===")
        imp_rows = []
        for _, r in imp_df.sort_values("hit_lift", ascending=False, na_position="last").head(20).iterrows():
            imp_rows.append([
                r["behavior_id"],
                int(r["n_with"]) if r["n_with"] else 0,
                _pct(r["hit_rate_with"]),
                _pct(r["hit_rate_without"]),
                f"{r['hit_lift']:+.1%}" if r["hit_lift"] is not None else "N/A",
                "YES" if r["is_informative"] else "-",
            ])
        print(tabulate(imp_rows,
                       headers=["Behavior", "N With", "HR With", "HR Without", "Hit Lift", "Informative"],
                       tablefmt="simple"))

    report_path = Path(__file__).parent.parent / "reports" / "BEHAVIOR_AWARE_SIMILARITY_REPORT.md"
    generate_report(
        bt["results"],
        imp_df,
        bt["variant_summaries"],
        bt["is_size"],
        bt["oos_size"],
        bt["split_ts"],
        report_path,
    )


if __name__ == "__main__":
    main()
