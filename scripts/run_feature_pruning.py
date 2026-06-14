"""
run_feature_pruning.py — Feature set pruning experiment.

Trains LightGBM on 5 feature sets derived from feature health findings,
evaluates mean rank IC, AUC, Brier, decile spread, and stability.

Feature sets:
  features_current            ALL_FEATURES + data_quality_score (baseline)
  features_remove_weak        Drop 12 weak features (low IC / unstable t-stat)
  features_remove_degrading   Drop 12 degrading features (sign-flip > 55% folds)
  features_keep_only_useful   Only 4 useful features + data_quality_score
  features_mean_reversion_plus_omni  Calibration-guided mean-reversion set

Evaluation: 80/20 time split on parquet history.
Result: written to feature_pruning_results + printed report.

Usage
-----
    python scripts/run_feature_pruning.py
    python scripts/run_feature_pruning.py --no-db
    python scripts/run_feature_pruning.py --parquet-dir exports/parquet
    python scripts/run_feature_pruning.py --target label_positive_5d
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from config.settings import ALL_FEATURES, TRAIN_FEATURES
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_feature_pruning")

# ── Feature sets ─────────────────────────────────────────────────────────────

# From feature_review_flags (run inspect_feature_health.py output):
_WEAK = [
    "realized_vol_60", "distance_sma200", "rs_spy_120", "above_sma200",
    "above_sma50", "return_60d", "rs_spy_60", "distance_sma50",
    "omni_82_bounce", "omni_82_slope", "dollar_volume_20", "atr_14",
]

_DEGRADING = [
    "roc_20", "rs_spy_20", "return_20d", "rsi_14", "above_sma20",
    "return_5d", "return_3d", "distance_sma20", "return_10d",
    "return_1d", "macd_histogram", "omni_82_value",
]

_USEFUL = [
    "omni_82_distance", "omni_82_above", "realized_vol_20", "volume_ratio_20",
]

# Mean-reversion set: calibration-guided features that showed positive alpha
_MR_OMNI = [
    "rsi_14",                        # oversold signal (regime context)
    "realized_vol_20",               # low vol = stable
    "omni_82_distance",              # proximity to OMNI 82 support
    "omni_82_above",                 # above/below OMNI
    "omni_82_slope",                 # OMNI trend direction
    "omni_82_distance_5d_change",    # momentum of OMNI distance
    "volume_ratio_20",               # volume context
    "volume_trend_5d",               # recent vol trend
    "rs_spy_120",                    # long-term RS (stability signal)
    "above_sma200",                  # broad trend regime
    "distance_sma200",               # distance from 200d (how extended)
    "spy_above_sma200",              # market regime
    "market_trend",                  # market regime
    "data_quality_score",
]

FEATURE_SETS: dict[str, list[str]] = {
    "features_current": TRAIN_FEATURES,
    "features_remove_weak": [f for f in TRAIN_FEATURES if f not in _WEAK],
    "features_remove_degrading": [f for f in TRAIN_FEATURES if f not in _DEGRADING],
    "features_keep_only_useful": _USEFUL + ["data_quality_score"],
    "features_mean_reversion_plus_omni": _MR_OMNI,
}


# ── Training + evaluation ─────────────────────────────────────────────────────

def load_parquet_range(parquet_dir: Path, target_col: str,
                       feature_cols: list[str]) -> pd.DataFrame:
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = []
    needed = {"ticker", "date"} | set(feature_cols) | {target_col}
    for f in files:
        try:
            full = pd.read_parquet(f, engine="pyarrow")
            available = [c for c in needed if c in full.columns]
            frames.append(full[available])
        except Exception:
            pass
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    if "data_quality_score" in df.columns:
        df = df[df["data_quality_score"].isna() | (df["data_quality_score"] >= 0.70)]
    if target_col in df.columns:
        df = df[df[target_col].notna()]
    return df.reset_index(drop=True)


def train_and_eval(
    X_tr: np.ndarray, y_tr: np.ndarray,
    X_val: np.ndarray, y_val: np.ndarray,
    dates_val: pd.Series,
    feature_names: list[str],
    is_classifier: bool,
) -> dict:
    try:
        import lightgbm as lgb
    except ImportError:
        return {"error": "lightgbm not installed"}

    from config.settings import LGBM_PARAMS_CLASSIFIER, LGBM_PARAMS_REGRESSOR
    from atlas_research.models.evaluate import rank_ic, brier_score, roc_auc

    params = (LGBM_PARAMS_CLASSIFIER if is_classifier else LGBM_PARAMS_REGRESSOR).copy()
    params["n_estimators"] = 300

    n_es = max(1, int(len(X_tr) * 0.10))
    X_es, y_es = X_tr[-n_es:], y_tr[-n_es:]
    X_t,  y_t  = X_tr[:-n_es], y_tr[:-n_es]

    ds = lgb.Dataset(X_t, label=y_t, feature_name=feature_names)

    if len(X_t) >= 1000:
        es_ds = lgb.Dataset(X_es, label=y_es, feature_name=feature_names, reference=ds)
        model = lgb.train(params, ds, valid_sets=[es_ds],
                          callbacks=[lgb.early_stopping(20, verbose=False),
                                     lgb.log_evaluation(-1)])
    else:
        model = lgb.train(params, ds, callbacks=[lgb.log_evaluation(-1)])

    preds = model.predict(X_val)
    ic    = float(rank_ic(y_val, preds))
    importances = sorted(
        zip(feature_names, model.feature_importance(importance_type="gain").tolist()),
        key=lambda x: -x[1]
    )[:10]

    metrics = {"ic": ic, "top_features": importances}
    if is_classifier:
        metrics["auc"]   = float(roc_auc(y_val, preds))
        metrics["brier"] = float(brier_score(y_val, preds))
    else:
        # Decile spread
        try:
            dv = pd.DataFrame({"y": y_val, "p": preds, "d": dates_val.values})
            dv["dec"] = dv.groupby("d")["p"].transform(
                lambda x: pd.qcut(x.rank(method="first"), 10,
                                  labels=False, duplicates="drop")
            )
            top    = dv[dv["dec"] == 9]["y"].mean()
            bottom = dv[dv["dec"] == 0]["y"].mean()
            metrics["decile_spread"] = float(top - bottom)
        except Exception:
            metrics["decile_spread"] = None

    return metrics


def run_pruning_experiment(
    parquet_dir: Path,
    target_col: str,
    min_rows: int = 500,
) -> dict[str, dict]:
    is_clf = "positive" in target_col

    # Load the widest needed set once (all features union)
    all_needed = set()
    for fset in FEATURE_SETS.values():
        all_needed.update(fset)

    print(f"\n  Loading parquet files from {parquet_dir} ...")
    df_all = load_parquet_range(parquet_dir, target_col, list(all_needed))
    if df_all.empty:
        return {k: {"error": "no parquet data"} for k in FEATURE_SETS}

    # Add missing columns as NaN
    for col in all_needed:
        if col not in df_all.columns:
            df_all[col] = np.nan

    df_all = df_all.sort_values("date").reset_index(drop=True)
    split   = int(len(df_all) * 0.80)
    train_df = df_all.iloc[:split].copy()
    val_df   = df_all.iloc[split:].copy()

    print(f"  Total rows: {len(df_all):,}  "
          f"train={len(train_df):,}  val={len(val_df):,}  "
          f"({df_all['date'].min()} to {df_all['date'].max()})")

    results: dict[str, dict] = {}
    for set_name, feat_cols in FEATURE_SETS.items():
        feat_cols = [f for f in feat_cols if f in df_all.columns]
        if not feat_cols:
            results[set_name] = {"error": "no features available"}
            continue

        X_tr = train_df[feat_cols].to_numpy(dtype=np.float64)
        y_tr = train_df[target_col].to_numpy(dtype=np.float64)
        X_val = val_df[feat_cols].to_numpy(dtype=np.float64)
        y_val = val_df[target_col].to_numpy(dtype=np.float64)
        dates_val = val_df["date"].reset_index(drop=True)

        if len(X_tr) < min_rows:
            results[set_name] = {"error": f"only {len(X_tr)} train rows (need {min_rows})"}
            continue

        print(f"  Training {set_name} ({len(feat_cols)} features)...")
        t0 = time.monotonic()
        m = train_and_eval(X_tr, y_tr, X_val, y_val, dates_val, feat_cols, is_clf)
        elapsed = time.monotonic() - t0

        m["n_features"]  = len(feat_cols)
        m["n_train"]     = len(X_tr)
        m["n_val"]       = len(X_val)
        m["runtime_s"]   = round(elapsed, 2)
        results[set_name] = m

    return results


def print_results(results: dict[str, dict], is_classifier: bool) -> None:
    sep = "-" * 100
    print(f"\n{sep}")
    print("  FEATURE PRUNING EXPERIMENT RESULTS")
    print(sep)

    if is_classifier:
        print(f"  {'Feature Set':<38}  {'n_feat':>6}  {'IC':>7}  "
              f"{'AUC':>7}  {'Brier':>7}  {'Time':>6}")
    else:
        print(f"  {'Feature Set':<38}  {'n_feat':>6}  {'IC':>7}  "
              f"{'Decile':>8}  {'Time':>6}")
    print("  " + "-" * 80)

    baseline_ic = None
    for set_name in ["features_current"] + [k for k in results if k != "features_current"]:
        r = results.get(set_name, {})
        if "error" in r:
            print(f"  {set_name:<38}  {'ERROR':>6}  {r['error']}")
            continue

        n_feat = r.get("n_features", 0)
        ic_s   = f"{r['ic']:+.4f}" if r.get("ic") is not None else "  n/a "
        time_s = f"{r.get('runtime_s', 0):.1f}s"

        if set_name == "features_current" and r.get("ic") is not None:
            baseline_ic = r["ic"]

        if is_classifier:
            auc_s   = f"{r['auc']:.4f}"   if r.get("auc")   is not None else " n/a "
            brier_s = f"{r['brier']:.4f}" if r.get("brier") is not None else " n/a "
            print(f"  {set_name:<38}  {n_feat:>6}  {ic_s:>7}  "
                  f"{auc_s:>7}  {brier_s:>7}  {time_s:>6}")
        else:
            ds = r.get("decile_spread")
            ds_s = f"{ds:+.4f}" if ds is not None else "   n/a "
            print(f"  {set_name:<38}  {n_feat:>6}  {ic_s:>7}  {ds_s:>8}  {time_s:>6}")

    print()
    print("  TOP FEATURES per set:")
    for set_name, r in results.items():
        if "top_features" in r:
            top = [f"{n}({g:.0f})" for n, g in r["top_features"][:5]]
            print(f"  {set_name:<38}  {', '.join(top)}")

    print()
    if baseline_ic is not None:
        better = [k for k, r in results.items()
                  if k != "features_current" and r.get("ic", -99) > baseline_ic]
        if better:
            best = max(better, key=lambda k: results[k].get("ic", -99))
            print(f"  WINNER: {best}  IC={results[best]['ic']:+.4f} vs baseline={baseline_ic:+.4f}")
        else:
            print(f"  WINNER: features_current (baseline={baseline_ic:+.4f}). "
                  "No pruned set beats current.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Feature pruning experiment")
    parser.add_argument("--target", default="label_return_5d")
    parser.add_argument("--parquet-dir", default=None)
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument("--min-rows", type=int, default=500)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    is_clf = "positive" in args.target
    parquet_dir = Path(args.parquet_dir) if args.parquet_dir else ROOT / "exports" / "parquet"

    print(f"\nFeature Pruning Experiment")
    print(f"  Target    : {args.target}")
    print(f"  Parquet   : {parquet_dir}")
    print(f"  Write DB  : {'no (--no-db)' if args.no_db else 'yes'}")
    print(f"\nFeature sets ({len(FEATURE_SETS)}):")
    for k, v in FEATURE_SETS.items():
        print(f"  {k:<38} {len(v):>3} features")

    results = run_pruning_experiment(parquet_dir, args.target, args.min_rows)
    print_results(results, is_clf)

    # ── Write to DB ──────────────────────────────────────────────────────
    if not args.no_db:
        db_rows = []
        for set_name, r in results.items():
            if "error" in r:
                continue
            db_rows.append({
                "feature_set":   set_name,
                "n_features":    r.get("n_features"),
                "mean_rank_ic":  r.get("ic"),
                "ic_std":        None,
                "auc":           r.get("auc"),
                "brier":         r.get("brier"),
                "decile_spread": r.get("decile_spread"),
                "runtime_s":     r.get("runtime_s"),
                "top_features":  json.dumps(
                    [{"name": n, "gain": g} for n, g in r.get("top_features", [])]
                ),
            })
        if db_rows:
            with psycopg2.connect(db_url) as conn:
                with conn.cursor() as cur:
                    execute_batch(cur, """
                        INSERT INTO feature_pruning_results
                            (feature_set, n_features, mean_rank_ic, ic_std,
                             auc, brier, decile_spread, runtime_s, top_features)
                        VALUES
                            (%(feature_set)s, %(n_features)s, %(mean_rank_ic)s,
                             %(ic_std)s, %(auc)s, %(brier)s, %(decile_spread)s,
                             %(runtime_s)s, %(top_features)s::jsonb)
                        ON CONFLICT (feature_set) DO UPDATE SET
                            n_features    = EXCLUDED.n_features,
                            mean_rank_ic  = EXCLUDED.mean_rank_ic,
                            auc           = EXCLUDED.auc,
                            brier         = EXCLUDED.brier,
                            decile_spread = EXCLUDED.decile_spread,
                            runtime_s     = EXCLUDED.runtime_s,
                            top_features  = EXCLUDED.top_features,
                            computed_at   = now()
                    """, db_rows)
                conn.commit()
            print(f"  Written {len(db_rows)} rows to feature_pruning_results")


if __name__ == "__main__":
    main()
