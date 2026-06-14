"""
run_holdout_validation.py — Final holdout validation: V1 vs V2 feature sets.

Trains two LightGBM regressors on identical pre-holdout data (2011-07-01 to
2025-06-30), evaluates on the untouched holdout period (2025-07-01 to
2026-03-17), and compares:

  - Mean Rank IC
  - IC std (across dates)
  - Decile spread (top 10% return - bottom 10% return)
  - AUC   (regressor preds treated as rank-probability vs return_5d > 0)
  - Brier score
  - Top decile actual 5d return
  - Bottom decile actual 5d return
  - Prediction overlap (Jaccard of top-decile tickers per day, then averaged)

Promotion criterion: V2 wins or ties on >= 4 of 8 metrics.

Usage
-----
    python scripts/run_holdout_validation.py
    python scripts/run_holdout_validation.py --holdout-from 2025-07-01
    python scripts/run_holdout_validation.py --no-db
"""

from __future__ import annotations

import argparse
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
from scipy import stats as scipy_stats

from config.settings import TRAIN_FEATURES_V1, TRAIN_FEATURES_V2
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_holdout_validation")

TARGET_COL   = "label_return_5d"   # forward 5d return; NOT the trailing return_5d feature
HOLDOUT_FROM = "2025-07-01"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_parquet_split(
    parquet_dir: Path,
    holdout_from: str,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    pre, post = [], []
    needed = {"ticker", "date", TARGET_COL} | set(feature_cols)

    for f in files:
        bucket = post if f.stem >= f"feature_matrix_{holdout_from}" else pre
        try:
            df = pd.read_parquet(f, engine="pyarrow")
            avail = [c for c in needed if c in df.columns]
            bucket.append(df[avail])
        except Exception:
            pass

    def combine(frames: list[pd.DataFrame]) -> pd.DataFrame:
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        out = out[out[TARGET_COL].notna()]
        for col in feature_cols:
            if col not in out.columns:
                out[col] = np.nan
        return out.sort_values("date").reset_index(drop=True)

    return combine(pre), combine(post)


# ── Model training ────────────────────────────────────────────────────────────

def train_model(
    train_df: pd.DataFrame,
    feature_cols: list[str],
    label: str = TARGET_COL,
) -> object:
    import lightgbm as lgb
    from config.settings import LGBM_PARAMS_REGRESSOR

    params = LGBM_PARAMS_REGRESSOR.copy()
    params["n_estimators"] = 500

    X = train_df[feature_cols].to_numpy(dtype=np.float64)
    y = train_df[label].to_numpy(dtype=np.float64)

    n_es = max(1, int(len(X) * 0.05))
    X_es, y_es = X[-n_es:], y[-n_es:]
    X_t,  y_t  = X[:-n_es], y[:-n_es]

    ds    = lgb.Dataset(X_t, label=y_t, feature_name=feature_cols)
    es_ds = lgb.Dataset(X_es, label=y_es, feature_name=feature_cols, reference=ds)

    model = lgb.train(
        params, ds,
        valid_sets=[es_ds],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
    )
    return model


# ── Metrics ───────────────────────────────────────────────────────────────────

def rank_ic_series(y_true: np.ndarray, y_pred: np.ndarray, dates: np.ndarray) -> np.ndarray:
    ics = []
    for d in np.unique(dates):
        mask = dates == d
        yt = y_true[mask]
        yp = y_pred[mask]
        if len(yt) < 5:
            continue
        ic, _ = scipy_stats.spearmanr(yt, yp)
        if not np.isnan(ic):
            ics.append(ic)
    return np.array(ics)


def decile_spread(
    y_true: np.ndarray, y_pred: np.ndarray, dates: np.ndarray
) -> tuple[float, float, float]:
    top_rets, bot_rets = [], []
    for d in np.unique(dates):
        mask = dates == d
        yt = y_true[mask]
        yp = y_pred[mask]
        n = len(yt)
        if n < 10:
            continue
        k = max(1, n // 10)
        idx_sort = np.argsort(yp)
        top_rets.append(np.mean(yt[idx_sort[-k:]]))
        bot_rets.append(np.mean(yt[idx_sort[:k]]))
    if not top_rets:
        return 0.0, 0.0, 0.0
    return float(np.mean(top_rets)), float(np.mean(bot_rets)), float(np.mean(top_rets) - np.mean(bot_rets))


def auc_brier(y_true_ret: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    from sklearn.metrics import roc_auc_score, brier_score_loss
    binary = (y_true_ret > 0).astype(int)
    # Rank-normalise predictions to [0,1] as a probability proxy
    ranks = scipy_stats.rankdata(y_pred) / len(y_pred)
    try:
        auc = float(roc_auc_score(binary, ranks))
    except Exception:
        auc = float("nan")
    brier = float(brier_score_loss(binary, ranks))
    return auc, brier


def prediction_overlap(
    pred_v1: np.ndarray, pred_v2: np.ndarray,
    tickers: np.ndarray, dates: np.ndarray,
) -> float:
    jaccards = []
    for d in np.unique(dates):
        mask = dates == d
        t = tickers[mask]
        p1 = pred_v1[mask]
        p2 = pred_v2[mask]
        n = len(t)
        if n < 10:
            continue
        k = max(1, n // 10)
        top1 = set(t[np.argsort(p1)[-k:]])
        top2 = set(t[np.argsort(p2)[-k:]])
        inter = len(top1 & top2)
        union = len(top1 | top2)
        jaccards.append(inter / union if union > 0 else 0.0)
    return float(np.mean(jaccards)) if jaccards else 0.0


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(
    model,
    holdout_df: pd.DataFrame,
    feature_cols: list[str],
    pred_other: np.ndarray | None = None,
) -> dict:
    X_h = holdout_df[feature_cols].to_numpy(dtype=np.float64)
    y_h = holdout_df[TARGET_COL].to_numpy(dtype=np.float64)
    dates_h = holdout_df["date"].to_numpy()
    tickers_h = holdout_df["ticker"].to_numpy()

    preds = model.predict(X_h)

    ics = rank_ic_series(y_h, preds, dates_h)
    top_ret, bot_ret, spread = decile_spread(y_h, preds, dates_h)
    auc, brier = auc_brier(y_h, preds)
    overlap = prediction_overlap(preds, pred_other, tickers_h, dates_h) if pred_other is not None else None

    return {
        "preds":         preds,
        "mean_ic":       float(np.mean(ics)),
        "ic_std":        float(np.std(ics)),
        "decile_spread": spread,
        "top_decile_ret": top_ret,
        "bot_decile_ret": bot_ret,
        "auc":           auc,
        "brier":         brier,
        "overlap":       overlap,
        "n_dates":       len(np.unique(dates_h)),
        "n_rows":        len(y_h),
    }


# ── Output ────────────────────────────────────────────────────────────────────

def print_comparison(v1: dict, v2: dict) -> tuple[bool, int, int]:
    sep = "-" * 82

    def winner(v1_val: float, v2_val: float, lower_is_better: bool = False) -> str:
        if lower_is_better:
            return "V2 [+]" if v2_val < v1_val else ("TIE" if v2_val == v1_val else "V1 [+]")
        return "V2 [+]" if v2_val > v1_val else ("TIE" if v2_val == v1_val else "V1 [+]")

    metrics = [
        ("Mean Rank IC",         v1["mean_ic"],        v2["mean_ic"],        False),
        ("IC Std (lower=better)", v1["ic_std"],         v2["ic_std"],         True),
        ("Decile Spread",        v1["decile_spread"],  v2["decile_spread"],  False),
        ("AUC",                  v1["auc"],            v2["auc"],            False),
        ("Brier (lower=better)", v1["brier"],          v2["brier"],          True),
        ("Top Decile Return",    v1["top_decile_ret"], v2["top_decile_ret"], False),
        ("Bot Decile Return",    v1["bot_decile_ret"], v2["bot_decile_ret"], False),
    ]

    print(f"\n{sep}")
    print("  HOLDOUT VALIDATION: V1 vs V2 FEATURE SETS")
    print(sep)
    print(f"  Holdout period : {HOLDOUT_FROM} to 2026-03-17")
    print(f"  Holdout rows   : {v1['n_rows']:,}  ({v1['n_dates']} dates)")
    print(f"  V1 features    : {len(TRAIN_FEATURES_V1)}")
    print(f"  V2 features    : {len(TRAIN_FEATURES_V2)}")
    if v2["overlap"] is not None:
        print(f"  Pred overlap   : {v2['overlap']*100:.1f}%  (Jaccard, top-decile per day)")
    print()
    print(f"  {'Metric':<28}  {'V1':>10}  {'V2':>10}  {'Winner'}")
    print("  " + "-" * 60)

    v2_wins = 0
    v1_wins = 0
    for name, val1, val2, lib in metrics:
        w = winner(val1, val2, lib)
        if w.startswith("V2"):
            v2_wins += 1
        elif w.startswith("V1"):
            v1_wins += 1
        fmt1 = f"{val1:+.4f}" if val1 is not None and not (isinstance(val1, float) and np.isnan(val1)) else "  n/a "
        fmt2 = f"{val2:+.4f}" if val2 is not None and not (isinstance(val2, float) and np.isnan(val2)) else "  n/a "
        print(f"  {name:<28}  {fmt1:>10}  {fmt2:>10}  {w}")

    print()
    print(f"  V2 wins: {v2_wins}/7    V1 wins: {v1_wins}/7")
    promote = v2_wins >= 4
    verdict = "PROMOTE V2" if promote else "KEEP V1"
    print(f"  Verdict: {verdict}  (threshold: >= 4 of 7)")
    print(sep)
    print()

    return promote, v2_wins, v1_wins


# ── DB write ──────────────────────────────────────────────────────────────────

def write_validation_results(
    db_url: str,
    holdout_from: str,
    v1: dict,
    v2: dict,
    promoted: bool,
) -> None:
    rows = [
        ("holdout_v1", holdout_from, "2026-03-17",
         v1["mean_ic"], v1["ic_std"], v1["decile_spread"],
         v1["auc"], v1["brier"], v1["top_decile_ret"], v1["bot_decile_ret"],
         len(TRAIN_FEATURES_V1), False, promoted),
        ("holdout_v2", holdout_from, "2026-03-17",
         v2["mean_ic"], v2["ic_std"], v2["decile_spread"],
         v2["auc"], v2["brier"], v2["top_decile_ret"], v2["bot_decile_ret"],
         len(TRAIN_FEATURES_V2), True, promoted),
    ]
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, """
                INSERT INTO model_registry
                    (model_name, model_version, target, horizon,
                     training_start, training_end,
                     rank_ic, ic, auc, brier,
                     feature_count, feature_set_version, promoted,
                     notes)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, [
                (name, "v1", "return_5d", 5,
                 "2011-07-01", to_date,
                 mean_ic, mean_ic, auc, brier,
                 n_feat,
                 "v2" if is_v2 else "v1",
                 prom,
                 f"holdout validation {holdout_from} to 2026-03-17")
                for name, from_date, to_date,
                    mean_ic, ic_std, spread,
                    auc, brier, top_ret, bot_ret,
                    n_feat, is_v2, prom in rows
            ])
        conn.commit()
    print(f"  Validation results written to model_registry.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Holdout validation: V1 vs V2 feature sets")
    parser.add_argument("--holdout-from", default=HOLDOUT_FROM, help="Holdout start date YYYY-MM-DD")
    parser.add_argument("--no-db",        action="store_true", help="Skip DB writes")
    parser.add_argument("--parquet-dir",  default=None)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    parquet_dir = Path(args.parquet_dir) if args.parquet_dir else ROOT / "exports" / "parquet"
    holdout_from = args.holdout_from

    # We need features from both V1 and V2 for loading; use V1 (superset)
    all_needed = list(set(TRAIN_FEATURES_V1) | set(TRAIN_FEATURES_V2))

    print(f"\nHoldout Validation  V1 ({len(TRAIN_FEATURES_V1)} features) vs V2 ({len(TRAIN_FEATURES_V2)} features)")
    print(f"  Holdout from  : {holdout_from}")
    print(f"  Parquet dir   : {parquet_dir}")
    print(f"  V2 drops      : {sorted(set(TRAIN_FEATURES_V1) - set(TRAIN_FEATURES_V2))}")

    print("\nLoading parquet data...")
    t0 = time.monotonic()
    train_df, holdout_df = load_parquet_split(parquet_dir, holdout_from, all_needed)
    print(f"  Pre-holdout  : {len(train_df):,} rows  ({train_df['date'].min()} to {train_df['date'].max()})")
    print(f"  Holdout      : {len(holdout_df):,} rows  ({holdout_df['date'].min()} to {holdout_df['date'].max()})")

    if len(holdout_df) < 100:
        sys.exit("[ERROR] Holdout is too small. Check parquet data and --holdout-from date.")

    # ── Train V1 ──────────────────────────────────────────────────────────
    v1_feats = [f for f in TRAIN_FEATURES_V1 if f in train_df.columns]
    print(f"\nTraining V1 ({len(v1_feats)} features)...")
    t1 = time.monotonic()
    model_v1 = train_model(train_df, v1_feats)
    print(f"  Done in {time.monotonic()-t1:.1f}s")

    # ── Train V2 ──────────────────────────────────────────────────────────
    v2_feats = [f for f in TRAIN_FEATURES_V2 if f in train_df.columns]
    print(f"\nTraining V2 ({len(v2_feats)} features)...")
    t2 = time.monotonic()
    model_v2 = train_model(train_df, v2_feats)
    print(f"  Done in {time.monotonic()-t2:.1f}s")

    # ── Evaluate both on holdout ───────────────────────────────────────────
    print("\nEvaluating on holdout...")
    h1_feats = [f for f in v1_feats if f in holdout_df.columns]
    h2_feats = [f for f in v2_feats if f in holdout_df.columns]

    # Need V2 preds first to compute overlap
    X_h2 = holdout_df[h2_feats].to_numpy(dtype=np.float64)
    preds_v2_raw = model_v2.predict(X_h2)

    results_v1 = evaluate(model_v1, holdout_df, h1_feats, pred_other=preds_v2_raw)
    results_v2 = evaluate(model_v2, holdout_df, h2_feats, pred_other=results_v1["preds"])

    elapsed = time.monotonic() - t0
    print(f"  Total time: {elapsed:.1f}s")

    # ── Compare ────────────────────────────────────────────────────────────
    promote, v2_wins, v1_wins = print_comparison(results_v1, results_v2)

    # ── Write to DB ────────────────────────────────────────────────────────
    if not args.no_db:
        write_validation_results(db_url, holdout_from, results_v1, results_v2, promote)

    # ── Return exit code for downstream use ────────────────────────────────
    # 0 = promote V2, 1 = keep V1
    sys.exit(0 if promote else 1)


if __name__ == "__main__":
    main()
