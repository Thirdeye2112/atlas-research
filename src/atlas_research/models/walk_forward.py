"""
Walk-forward validation — expanding window with purge gap.

DESIGN
------
Expanding window: each fold adds one year of training data.
The validation period is always the next WF_VAL_MONTHS months.
The OOS test period (final evaluation) is held out entirely and
never seen during fold selection.

FOLD STRUCTURE
--------------
Given 15 years of data (2010–2024) and WF_MIN_TRAIN_YEARS=3:

  Fold 1:  train 2010–2012, val 2013
  Fold 2:  train 2010–2013, val 2014
  Fold 3:  train 2010–2014, val 2015
  ...
  Fold N:  train 2010–2022, val 2023

Purge gap: last WF_PURGE_DAYS trading days of training are dropped
to prevent 5-day label leakage into the validation period.

BASELINE MODE
-------------
run_baseline() trains a single model on all available data and reports
in-sample metrics only.  Fast sanity check before running full WF.
Useful for confirming the pipeline works end-to-end.

OUTPUTS
-------
Each fold writes:
  - model_registry row (train metrics, val metrics, artifact path)
  - feature_performance rows (per-feature IC on validation set)
  - predictions rows (model scores on the validation tickers/dates)
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from atlas_research.models.dataset import (
    apply_purge_gap, cross_sectional_normalize, load_date_range, to_arrays
)
from atlas_research.models.evaluate import (
    evaluate_fold, feature_ic_report
)
from atlas_research.models.train import (
    TrainedModelBundle, artifact_path, save_model,
    train_classifier, train_regressor
)
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Fold descriptor
# ---------------------------------------------------------------------------

@dataclass
class Fold:
    number:      int
    train_start: date
    train_end:   date
    val_start:   date
    val_end:     date


@dataclass
class FoldResult:
    fold:           Fold
    train_metrics:  dict = field(default_factory=dict)
    val_metrics:    dict = field(default_factory=dict)
    feature_ics:    list[dict] = field(default_factory=list)
    model_reg_id:   int = -1
    model_clf_id:   int = -1
    n_train:        int = 0
    n_val:          int = 0
    error:          str | None = None


# ---------------------------------------------------------------------------
# Fold generation
# ---------------------------------------------------------------------------

def _subtract_months(d: date, months: int) -> date:
    """Return the date ``months`` calendar months before ``d`` (clamped day)."""
    import calendar
    if months <= 0:
        return d
    total = (d.year * 12 + (d.month - 1)) - months
    year, month = divmod(total, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def oos_window(data_end: date, oos_months: int) -> tuple[date | None, date | None]:
    """
    Return (oos_start, oos_end) for the reserved out-of-sample hold-out, or
    (None, None) when oos_months <= 0.

    oos_start is the first day fold generation must NOT cross; oos_end == data_end.
    """
    if oos_months <= 0:
        return None, None
    oos_start = _subtract_months(data_end, oos_months) + timedelta(days=1)
    return oos_start, data_end


def generate_folds(
    data_start: date,
    data_end: date,
    min_train_years: int,
    val_months: int,
    oos_months: int = 0,
) -> list[Fold]:
    """
    Generate expanding-window fold descriptors.

    Args:
        data_start:       Earliest date with training data.
        data_end:         Latest date available.
        min_train_years:  Minimum years of history before first fold.
        val_months:       Validation period length in months.
        oos_months:       Final months reserved as out-of-sample hold-out.
                          Fold generation never produces a fold whose validation
                          window enters this embargoed region.

    Returns:
        List of Fold objects in chronological order.
    """
    folds = []
    fold_num = 1

    # Reserve the final oos_months as an embargoed hold-out: folds are generated
    # only up to fold_horizon, so no fold's validation window touches the OOS.
    fold_horizon = _subtract_months(data_end, oos_months) if oos_months > 0 else data_end

    # First training end: data_start + min_train_years
    train_end = date(
        data_start.year + min_train_years,
        data_start.month,
        data_start.day,
    )

    while True:
        val_start = train_end + timedelta(days=1)
        # val_end: val_months calendar months later
        val_end_month = val_start.month + val_months
        val_end_year  = val_start.year + (val_end_month - 1) // 12
        val_end_month = ((val_end_month - 1) % 12) + 1
        # Last day of val_end_month
        import calendar
        last_day = calendar.monthrange(val_end_year, val_end_month)[1]
        val_end  = date(val_end_year, val_end_month, last_day)

        if val_start >= fold_horizon:
            break
        val_end = min(val_end, fold_horizon)

        folds.append(Fold(
            number      = fold_num,
            train_start = data_start,
            train_end   = train_end,
            val_start   = val_start,
            val_end     = val_end,
        ))

        fold_num += 1
        # Next fold adds one year to training end
        train_end = date(train_end.year + 1, train_end.month, train_end.day)

    return folds


# ---------------------------------------------------------------------------
# Single fold runner
# ---------------------------------------------------------------------------

def run_fold(
    fold: Fold,
    parquet_dir: Path,
    model_dir: Path,
    feature_cols: list[str],
    reg_target: str,
    clf_target: str,
    model_version: str,
    purge_days: int,
    min_quality_score: float,
    normalize_cross_sectional: bool = True,
    write_db: bool = True,
    feature_set_version: str = "v1",
) -> FoldResult:
    """
    Train both models on one fold and evaluate on the validation set.

    Args:
        fold:                   Fold descriptor with train/val date ranges.
        parquet_dir:            Directory of daily parquet files.
        model_dir:              Directory to save model artifacts.
        feature_cols:           Ordered feature column names.
        reg_target:             Regression target column ('label_return_5d').
        clf_target:             Classification target ('label_positive_5d').
        model_version:          Version tag for model_registry.
        purge_days:             Days to remove from end of training set.
        min_quality_score:      Quality filter threshold.
        normalize_cross_sectional: Rank-normalize features within each date.
        write_db:               If True, write model_registry and feature_performance.

    Returns:
        FoldResult with metrics, DB ids, and any error message.
    """
    result = FoldResult(fold=fold)

    try:
        # ── Load training data ────────────────────────────────
        train_df = load_date_range(
            fold.train_start, fold.train_end,
            feature_cols, reg_target,
            parquet_dir, min_quality_score,
        )
        # For classification, we need the clf_target too
        if clf_target != reg_target and not train_df.empty:
            clf_train = load_date_range(
                fold.train_start, fold.train_end,
                feature_cols, clf_target,
                parquet_dir, min_quality_score,
            )

        # ── Load validation data ──────────────────────────────
        val_df = load_date_range(
            fold.val_start, fold.val_end,
            feature_cols, reg_target,
            parquet_dir, min_quality_score,
        )
        clf_val = load_date_range(
            fold.val_start, fold.val_end,
            feature_cols, clf_target,
            parquet_dir, min_quality_score,
        ) if clf_target != reg_target else val_df.copy()

        if train_df.empty or val_df.empty:
            result.error = "insufficient_data"
            log.warning("wf.fold_skipped", fold=fold.number, reason="no data")
            return result

        # ── Apply purge gap ───────────────────────────────────
        train_df, val_df = apply_purge_gap(train_df, val_df, purge_days)
        if clf_target != reg_target:
            clf_train, clf_val = apply_purge_gap(clf_train, clf_val, purge_days)

        # ── Cross-sectional normalisation ─────────────────────
        if normalize_cross_sectional:
            train_df  = cross_sectional_normalize(train_df,  feature_cols)
            val_df    = cross_sectional_normalize(val_df,    feature_cols)
            if clf_target != reg_target:
                clf_train = cross_sectional_normalize(clf_train, feature_cols)
                clf_val   = cross_sectional_normalize(clf_val,   feature_cols)

        # ── Convert to arrays ─────────────────────────────────
        X_train, y_reg_train, _, train_dates  = to_arrays(train_df, feature_cols, reg_target)
        X_val,   y_reg_val,   val_tickers, val_dates = \
            to_arrays(val_df, feature_cols, reg_target)

        if clf_target != reg_target:
            X_clf_train, y_clf_train, _, _ = to_arrays(clf_train, feature_cols, clf_target)
            X_clf_val,   y_clf_val,   _, _ = to_arrays(clf_val,   feature_cols, clf_target)
        else:
            # Same dataset; re-extract clf target
            X_clf_train, y_clf_train, _, _ = to_arrays(train_df, feature_cols, clf_target)
            X_clf_val,   y_clf_val,   _, _ = to_arrays(val_df,   feature_cols, clf_target)

        result.n_train = len(X_train)
        result.n_val   = len(X_val)

        log.info(
            "wf.fold_data",
            fold=fold.number,
            train_rows=result.n_train,
            val_rows=result.n_val,
        )

        # ── Train regressor ───────────────────────────────────
        reg_model, reg_imp = train_regressor(
            X_train, y_reg_train, X_val, y_reg_val, feature_cols
        )
        # ── Train classifier ──────────────────────────────────
        clf_model, platt, clf_imp = train_classifier(
            X_clf_train, y_clf_train, X_clf_val, y_clf_val, feature_cols
        )

        # ── Bundle and save ───────────────────────────────────
        bundle = TrainedModelBundle(
            regressor       = reg_model,
            classifier      = clf_model,
            platt           = platt,
            feature_names   = feature_cols,
            train_end       = fold.train_end,
            model_version   = model_version,
            reg_importances = reg_imp,
            clf_importances = clf_imp,
        )

        apath_reg = artifact_path(
            "return_regressor", model_version, fold.train_end, model_dir
        )
        sha = save_model(bundle, apath_reg)

        # ── Evaluate ──────────────────────────────────────────
        y_reg_pred = reg_model.predict(X_val)
        y_clf_prob = bundle.predict_prob(X_clf_val)

        result.val_metrics = evaluate_fold(
            y_reg_val, y_reg_pred, y_clf_prob, val_dates, "regression"
        )
        clf_metrics = evaluate_fold(
            y_clf_val, y_clf_prob, y_clf_prob, val_dates, "classification"
        )
        result.val_metrics["clf_auc"]   = clf_metrics.get("auc", float("nan"))
        result.val_metrics["clf_brier"] = clf_metrics.get("brier", float("nan"))

        # Train metrics (on a random sample of the training set — cheaper than
        # full).  Use the sampled rows' OWN training dates so the in-sample
        # cross-sectional IC groups correctly; the previous code passed
        # val_dates.iloc[:n], mismatching predictions to unrelated dates and
        # making in-sample IC meaningless.
        sample_idx = np.random.default_rng(42).choice(
            len(X_train), min(5000, len(X_train)), replace=False
        )
        result.train_metrics = evaluate_fold(
            y_reg_train[sample_idx],
            reg_model.predict(X_train[sample_idx]),
            None,
            train_dates.iloc[sample_idx].reset_index(drop=True),
            "regression",
        )

        # ── Feature IC on validation ──────────────────────────
        val_feat_df = val_df.copy()
        val_feat_df["y_pred_reg"] = y_reg_pred
        result.feature_ics = feature_ic_report(
            val_feat_df, feature_cols, reg_target
        )
        # Attach LGBM gain importances
        feat_to_gain = dict(zip(feature_cols, reg_imp["gain"]))
        feat_to_split = dict(zip(feature_cols, reg_imp["split"]))
        for row in result.feature_ics:
            row["lgbm_gain"]  = feat_to_gain.get(row["feature_name"])
            row["lgbm_split"] = feat_to_split.get(row["feature_name"])

        # ── Write to DB ───────────────────────────────────────
        if write_db:
            from atlas_research.db import repository

            reg_record = {
                "model_name":          "return_regressor",
                "model_version":       model_version,
                "target":              reg_target,
                "horizon":             5,
                "training_start":      fold.train_start,
                "training_end":        fold.train_end,
                "feature_version":     "v1",
                "feature_set_version": feature_set_version,
                "feature_names":       feature_cols,
                "feature_count":       len(feature_cols),
                "train_rows":      result.n_train,
                "val_rows":        result.n_val,
                "ic":              result.val_metrics.get("mean_ic"),
                "rank_ic":         result.val_metrics.get("rank_ic"),
                "sharpe":          result.val_metrics.get("sharpe"),
                "brier":           result.val_metrics.get("clf_brier"),
                "auc":             result.val_metrics.get("clf_auc"),
                "artifact_path":   str(apath_reg),
                "artifact_hash":   sha,
                "hyperparams":     None,
                "fold_metrics":    [result.val_metrics],
                "notes":           f"walk_forward fold {fold.number}",
            }
            result.model_reg_id = repository.upsert_model_registry(reg_record)

            # Feature performance rows
            fp_rows = []
            for fic in result.feature_ics:
                fp_rows.append({
                    "feature_name":  fic["feature_name"],
                    "model_version": model_version,
                    "target":        reg_target,
                    "horizon_days":  5,
                    "eval_start":    fold.val_start,
                    "eval_end":      fold.val_end,
                    "fold_number":   fold.number,
                    "spearman_ic":   fic.get("spearman_ic"),
                    "pearson_ic":    fic.get("pearson_ic"),
                    "ic_tstat":      fic.get("ic_tstat"),
                    "mean_ic":       fic.get("mean_ic"),
                    "ic_std":        fic.get("ic_std"),
                    "lgbm_gain":     fic.get("lgbm_gain"),
                    "lgbm_split":    fic.get("lgbm_split"),
                })
            if fp_rows:
                repository.upsert_feature_performance(fp_rows)

        log.info(
            "wf.fold_complete",
            fold=fold.number,
            rank_ic=round(result.val_metrics.get("rank_ic", float("nan")) or 0, 4),
            clf_auc=round(result.val_metrics.get("clf_auc", float("nan")) or 0, 4),
            clf_brier=round(result.val_metrics.get("clf_brier", float("nan")) or 0, 4),
        )

    except Exception as exc:
        result.error = str(exc)
        log.error("wf.fold_error", fold=fold.number, error=str(exc))
        log.debug(traceback.format_exc())

    return result


# ---------------------------------------------------------------------------
# Full walk-forward run
# ---------------------------------------------------------------------------

def run_walk_forward(
    data_start: date,
    data_end: date,
    parquet_dir: Path,
    model_dir: Path,
    feature_cols: list[str],
    model_version: str,
    min_train_years: int,
    val_months: int,
    purge_days: int,
    min_quality_score: float,
    write_db: bool = True,
    feature_set_version: str = "v1",
    oos_months: int = 0,
) -> list[FoldResult]:
    """
    Run full expanding-window walk-forward validation.

    The final ``oos_months`` of data are reserved as an embargoed out-of-sample
    hold-out that fold generation never touches.

    Returns a list of FoldResult objects (one per fold).
    Folds run sequentially — parallelism deferred to Phase 3.
    """
    folds = generate_folds(data_start, data_end, min_train_years, val_months, oos_months)
    oos_start, oos_end = oos_window(data_end, oos_months)
    log.info("wf.started", n_folds=len(folds), data_start=str(data_start),
             data_end=str(data_end),
             oos_reserved=(f"{oos_start}->{oos_end}" if oos_start else "none"))

    # PARALLEL EXECUTION PLACEHOLDER
    # When WF_PARALLEL_FOLDS > 1 is enabled in Phase 3, replace this loop with:
    #   with ProcessPoolExecutor(max_workers=settings.WF_PARALLEL_FOLDS) as ex:
    #       futures = {ex.submit(run_fold, fold, ...): fold for fold in folds}
    #       results = [f.result() for f in as_completed(futures)]
    # Prerequisite: prove sequential correctness on real data first.
    results = []
    for fold in folds:
        log.info(
            "wf.running_fold",
            fold=fold.number,
            train=f"{fold.train_start}->{fold.train_end}",
            val=f"{fold.val_start}->{fold.val_end}",
        )
        result = run_fold(
            fold=fold,
            parquet_dir=parquet_dir,
            model_dir=model_dir,
            feature_cols=feature_cols,
            reg_target="label_return_5d",
            clf_target="label_positive_5d",
            model_version=model_version,
            purge_days=purge_days,
            min_quality_score=min_quality_score,
            write_db=write_db,
            feature_set_version=feature_set_version,
        )
        results.append(result)

    # Summary across folds
    valid = [r for r in results if r.error is None]
    if valid:
        mean_ic  = np.nanmean([r.val_metrics.get("rank_ic", float("nan")) for r in valid])
        mean_auc = np.nanmean([r.val_metrics.get("clf_auc", float("nan")) for r in valid])
        log.info("wf.complete",
                 folds_ok=len(valid), folds_err=len(results)-len(valid),
                 mean_rank_ic=round(float(mean_ic), 4),
                 mean_clf_auc=round(float(mean_auc), 4))

    return results


# ---------------------------------------------------------------------------
# Baseline mode (single model, no walk-forward)
# ---------------------------------------------------------------------------

def run_baseline(
    train_start: date,
    train_end: date,
    parquet_dir: Path,
    model_dir: Path,
    feature_cols: list[str],
    model_version: str,
    purge_days: int,
    min_quality_score: float,
    write_db: bool = True,
) -> FoldResult:
    """
    Train a single model on [train_start, train_end] and report in-sample metrics.

    No validation fold — this is a quick sanity check to confirm the pipeline
    works end-to-end before running the full walk-forward.
    Writes to model_registry with notes='baseline'.
    """
    log.info("wf.baseline_mode",
             train_start=str(train_start), train_end=str(train_end))

    # Use the last 10% of training data as a pseudo-val set
    span = (train_end - train_start).days
    pseudo_split = train_start + timedelta(days=int(span * 0.90))

    fold = Fold(
        number      = 0,
        train_start = train_start,
        train_end   = pseudo_split,
        val_start   = pseudo_split + timedelta(days=1),
        val_end     = train_end,
    )
    result = run_fold(
        fold=fold,
        parquet_dir=parquet_dir,
        model_dir=model_dir,
        feature_cols=feature_cols,
        reg_target="label_return_5d",
        clf_target="label_positive_5d",
        model_version=model_version,
        purge_days=purge_days,
        min_quality_score=min_quality_score,
        write_db=write_db,
    )
    log.info("wf.baseline_complete", metrics=result.val_metrics)
    return result
