"""
Model evaluation metrics for walk-forward validation.

All functions are pure: metrics = f(y_true, y_pred, ...).
No I/O, no model loading, no database access.

METRICS IMPLEMENTED
-------------------
Regression (return_5d):
    rmse            Root mean squared error
    mae             Mean absolute error
    rank_ic         Spearman rank correlation between prediction and outcome
    ic_tstat        IC / (IC_std / sqrt(n_dates)) — measures consistency
    sharpe          Sharpe ratio of a long-top-quintile / short-bottom-quintile
                    signal portfolio (simplified: no transaction costs)

Classification (positive_5d):
    auc             ROC AUC
    brier           Brier score (lower = better calibration)
    log_loss        Binary cross-entropy
    accuracy        Simple accuracy at 0.5 threshold
    precision       Precision at 0.5 threshold
    recall          Recall at 0.5 threshold

Cross-sectional IC (computed per date, then averaged):
    mean_ic         Mean daily Spearman IC across all dates
    ic_std          Standard deviation of daily IC
    ir              IC / IC_std (Information Ratio)
    pct_positive_ic % of dates where IC > 0
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import warnings
from scipy import stats


# ---------------------------------------------------------------------------
# Regression metrics
# ---------------------------------------------------------------------------

def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root mean squared error."""
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean absolute error."""
    return float(np.mean(np.abs(y_true - y_pred)))


def rank_ic(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """
    Spearman rank correlation between predictions and outcomes.
    The primary signal quality metric for a cross-sectional model.
    """
    if len(y_true) < 3:
        return float("nan")
    corr, _ = stats.spearmanr(y_pred, y_true)
    return float(corr)


def ic_tstat(ic_values: np.ndarray) -> float:
    """
    t-statistic of IC values: mean(IC) / (std(IC) / sqrt(n)).
    Measures whether the IC is statistically different from zero
    (i.e. the signal is consistent, not just lucky on a few dates).
    """
    n = len(ic_values)
    if n < 2:
        return float("nan")
    mean = float(np.mean(ic_values))
    std  = float(np.std(ic_values, ddof=1))
    if std == 0:
        return float("nan")
    return mean / (std / math.sqrt(n))


def signal_sharpe(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    dates: pd.Series,
    n_long: int = 5,
    n_short: int = 5,
    annualize: float = 252.0,
) -> float:
    """
    Simplified Sharpe ratio of a long-top-N / short-bottom-N signal portfolio.

    Groups by date, ranks predictions, goes long the top n_long tickers and
    short the bottom n_short tickers.  Returns annualised Sharpe.
    No transaction costs, equal weighting.
    """
    df = pd.DataFrame({"date": dates, "y_true": y_true, "y_pred": y_pred})
    daily_pnl = []

    for _, group in df.groupby("date"):
        if len(group) < n_long + n_short:
            continue
        ranked = group.sort_values("y_pred", ascending=False)
        longs  = ranked.head(n_long)["y_true"].mean()
        shorts = ranked.tail(n_short)["y_true"].mean()
        daily_pnl.append(longs - shorts)

    if len(daily_pnl) < 5:
        return float("nan")

    pnl = np.array(daily_pnl)
    mean = float(np.mean(pnl))
    std  = float(np.std(pnl, ddof=1))
    if std == 0:
        return float("nan")
    return float((mean / std) * math.sqrt(annualize))


# ---------------------------------------------------------------------------
# Classification metrics
# ---------------------------------------------------------------------------

def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Brier score: mean squared error between predicted probability and outcome.
    Range [0, 1]. Lower = better. Baseline (always predict 0.5) = 0.25.
    """
    return float(np.mean((y_prob - y_true) ** 2))


def roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    ROC AUC via trapezoidal rule (no sklearn dependency).
    Returns 0.5 for degenerate cases.
    """
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    # Sort by descending predicted probability
    order  = np.argsort(y_prob)[::-1]
    y_sort = y_true[order]

    tp = np.cumsum(y_sort)
    fp = np.cumsum(1 - y_sort)

    tpr = tp / n_pos
    fpr = fp / n_neg

    # Trapezoidal AUC (np.trapezoid in numpy >= 2.0; np.trapz in older)
    try:
        auc = float(np.trapezoid(tpr, fpr))
    except AttributeError:
        auc = float(np.trapz(tpr, fpr))  # numpy < 2.0
    return abs(auc)   # abs handles descending fpr edge case


def log_loss_binary(y_true: np.ndarray, y_prob: np.ndarray,
                    eps: float = 1e-7) -> float:
    """Binary cross-entropy log loss."""
    y_prob = np.clip(y_prob, eps, 1 - eps)
    return float(-np.mean(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob)))


def accuracy_at_threshold(y_true: np.ndarray, y_prob: np.ndarray,
                          threshold: float = 0.5) -> float:
    """Accuracy at a fixed probability threshold."""
    pred = (y_prob >= threshold).astype(float)
    return float(np.mean(pred == y_true))


# ---------------------------------------------------------------------------
# Cross-sectional IC  (per-date, then averaged)
# ---------------------------------------------------------------------------

def cross_sectional_ic(
    df: pd.DataFrame,
    pred_col: str = "y_pred",
    true_col: str = "y_true",
    date_col: str = "date",
) -> dict[str, float]:
    """
    Compute mean daily Spearman IC and derived statistics.

    Args:
        df:        DataFrame with date, prediction, and outcome columns.
        pred_col:  Column of model predictions.
        true_col:  Column of actual outcomes.
        date_col:  Date column for grouping.

    Returns:
        Dict with keys: mean_ic, ic_std, ir, pct_positive_ic, ic_tstat_val, n_dates.
    """
    ic_values = []

    for _, group in df.groupby(date_col):
        if len(group) < 3:
            continue
        if group[pred_col].nunique() < 2 or group[true_col].nunique() < 2:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            corr, _ = stats.spearmanr(group[pred_col], group[true_col])
        if corr is not None and not math.isnan(corr):
            ic_values.append(corr)

    if not ic_values:
        return {
            "mean_ic": float("nan"), "ic_std": float("nan"),
            "ir": float("nan"), "pct_positive_ic": float("nan"),
            "ic_tstat_val": float("nan"), "n_dates": 0,
        }

    ic_arr = np.array(ic_values)
    mean   = float(np.mean(ic_arr))
    std    = float(np.std(ic_arr, ddof=1)) if len(ic_arr) > 1 else float("nan")
    ir     = mean / std if (std and std != 0) else float("nan")

    return {
        "mean_ic":        mean,
        "ic_std":         std,
        "ir":             ir,
        "pct_positive_ic": float(np.mean(ic_arr > 0)),
        "ic_tstat_val":   ic_tstat(ic_arr),
        "n_dates":        len(ic_arr),
    }


# ---------------------------------------------------------------------------
# Feature-level IC (per-feature univariate correlation with target)
# ---------------------------------------------------------------------------

def feature_ic_report(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    date_col: str = "date",
) -> list[dict]:
    """
    Compute mean cross-sectional Spearman IC for each feature vs target.
    Returns a list of dicts suitable for upsert_feature_performance().
    """
    rows = []
    for feat in feature_cols:
        if feat not in df.columns:
            continue
        feat_df = df[[date_col, feat, target_col]].dropna()
        if len(feat_df) < 10:
            continue

        ic_vals = []
        for _, group in feat_df.groupby(date_col):
            if len(group) < 3:
                continue
            # Constant column → spearmanr returns NaN with a ConstantInputWarning;
            # suppress it and skip the NaN result cleanly.
            if group[feat].nunique() < 2 or group[target_col].nunique() < 2:
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                corr, _ = stats.spearmanr(group[feat], group[target_col])
            if corr is not None and not math.isnan(corr):
                ic_vals.append(corr)

        if not ic_vals:
            continue

        ic_arr = np.array(ic_vals)
        mean_  = float(np.mean(ic_arr))
        std_   = float(np.std(ic_arr, ddof=1)) if len(ic_arr) > 1 else float("nan")
        tstat  = ic_tstat(ic_arr)

        rows.append({
            "feature_name": feat,
            "mean_ic":      mean_,
            "ic_std":       std_,
            "spearman_ic":  mean_,          # alias for the DB column
            "pearson_ic":   None,           # computed on demand in Phase 3
            "ic_tstat":     tstat,
            "lgbm_gain":    None,           # filled in after model training
            "lgbm_split":   None,
        })

    return sorted(rows, key=lambda r: abs(r["mean_ic"] or 0), reverse=True)


# ---------------------------------------------------------------------------
# Aggregate metrics dict  (returned from evaluate_fold)
# ---------------------------------------------------------------------------

def evaluate_fold(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prob: np.ndarray | None,
    dates: pd.Series,
    target_type: str,
) -> dict[str, float]:
    """
    Compute all relevant metrics for one walk-forward fold.

    Args:
        y_true:      Ground truth values.
        y_pred:      Model predictions (expected return for regressor,
                     probability for classifier; same array if single model).
        y_prob:      Calibrated probabilities (for classification).
                     Pass None for regression-only evaluation.
        dates:       Date series aligned with y_true.
        target_type: 'regression' | 'classification'

    Returns:
        Metrics dict with all computed values.  NaN for inapplicable metrics.
    """
    metrics: dict[str, float] = {}
    df = pd.DataFrame({"date": dates, "y_true": y_true, "y_pred": y_pred})

    if target_type == "regression":
        metrics["rmse"]     = rmse(y_true, y_pred)
        metrics["mae"]      = mae(y_true, y_pred)
        metrics["rank_ic"]  = rank_ic(y_true, y_pred)
        metrics["sharpe"]   = signal_sharpe(y_true, y_pred, dates)
        cs = cross_sectional_ic(df, pred_col="y_pred", true_col="y_true")
        metrics.update(cs)
        metrics["auc"]      = float("nan")
        metrics["brier"]    = float("nan")
        metrics["log_loss"] = float("nan")

    elif target_type == "classification":
        metrics["rmse"]    = float("nan")
        metrics["mae"]     = float("nan")
        metrics["rank_ic"] = rank_ic(y_true, y_pred)  # rank IC on prob

        if y_prob is not None:
            metrics["auc"]      = roc_auc(y_true, y_prob)
            metrics["brier"]    = brier_score(y_true, y_prob)
            metrics["log_loss"] = log_loss_binary(y_true, y_prob)
            metrics["accuracy"] = accuracy_at_threshold(y_true, y_prob)
        else:
            metrics.update({"auc": float("nan"), "brier": float("nan"),
                            "log_loss": float("nan"), "accuracy": float("nan")})

        cs = cross_sectional_ic(df, pred_col="y_pred", true_col="y_true")
        metrics.update(cs)
        metrics["sharpe"] = signal_sharpe(y_true, y_pred, dates)

    return metrics
