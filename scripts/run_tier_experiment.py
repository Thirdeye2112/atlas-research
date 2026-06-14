"""
run_tier_experiment.py — Quality tier model experiment.

Trains 6 LightGBM models on different quality tier subsets and compares them
on IC, AUC, Brier, decile spread, and fold stability.

Models:
    A  all          Full universe
    B  large_cap    quality_tier == 1
    C  mid_cap      quality_tier == 2
    D  small_cap    quality_tier == 3
    E  micro_cap    quality_tier == 4
    F  interaction  Full universe + quality_tier as an explicit feature

Usage
-----
    python scripts/run_tier_experiment.py
    python scripts/run_tier_experiment.py --target label_positive_5d
    python scripts/run_tier_experiment.py --from-wide   # load from DB wide table
    python scripts/run_tier_experiment.py --parquet-dir exports/parquet
    python scripts/run_tier_experiment.py --min-rows 500  # relax data guard
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_tier_experiment")

MIN_ROWS_PER_TIER = 200   # minimum rows to train a tier model


# ── Data loading ──────────────────────────────────────────────────────────────

def load_from_parquet(parquet_dir: Path, target_col: str) -> pd.DataFrame:
    """Load all parquet files in directory, concatenate into DataFrame."""
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        try:
            df = pd.read_parquet(f, engine="pyarrow")
            frames.append(df)
        except Exception as exc:
            log.warning("tier_exp.parquet_error", file=str(f), error=str(exc))
    if not frames:
        return pd.DataFrame()
    full = pd.concat(frames, ignore_index=True)
    if "data_quality_score" in full.columns:
        full = full[full["data_quality_score"] >= 0.70]
    if target_col in full.columns:
        full = full[full[target_col].notna()]
    return full.reset_index(drop=True)


def load_from_wide(db_url: str, target_col: str) -> pd.DataFrame:
    """Load from feature_snapshots_wide + labels table via DB."""
    import psycopg2
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT w.*,
                       l.return_5d   AS label_return_5d,
                       l.positive_5d AS label_positive_5d,
                       l.return_1d   AS label_return_1d,
                       l.return_10d  AS label_return_10d,
                       l.return_20d  AS label_return_20d
                FROM feature_snapshots_wide w
                LEFT JOIN labels l ON l.ticker = w.ticker AND l.date = w.date
                WHERE w.data_quality_score >= 0.70
                   OR w.data_quality_score IS NULL
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
    df = pd.DataFrame(rows, columns=cols)
    if target_col in df.columns:
        df = df[df[target_col].notna()]
    return df.reset_index(drop=True)


# ── Model training & eval ─────────────────────────────────────────────────────

def _train_and_eval(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    dates_val: pd.Series,
    feature_names: list[str],
    is_classifier: bool,
) -> dict:
    """Train one LightGBM model and return evaluation metrics."""
    try:
        import lightgbm as lgb
    except ImportError:
        return {"error": "lightgbm not installed"}

    from config.settings import LGBM_PARAMS_CLASSIFIER, LGBM_PARAMS_REGRESSOR
    from atlas_research.models.evaluate import rank_ic, brier_score, roc_auc

    params = (LGBM_PARAMS_CLASSIFIER if is_classifier else LGBM_PARAMS_REGRESSOR).copy()
    params["n_estimators"] = 200  # faster for experiment

    n_es = max(1, int(len(X_tr) * 0.10))
    X_es, y_es = X_tr[-n_es:], y_tr[-n_es:]
    X_t,  y_t  = X_tr[:-n_es], y_tr[:-n_es]

    ds = lgb.Dataset(X_t, label=y_t, feature_name=feature_names)

    if len(X_t) >= 500:
        es_ds = lgb.Dataset(X_es, label=y_es, feature_name=feature_names,
                            reference=ds)
        model = lgb.train(
            params, ds,
            valid_sets=[es_ds],
            callbacks=[
                lgb.early_stopping(20, verbose=False),
                lgb.log_evaluation(-1),
            ],
        )
    else:
        model = lgb.train(params, ds, callbacks=[lgb.log_evaluation(-1)])

    preds = model.predict(X_val)

    metrics: dict = {
        "n_train": len(X_tr),
        "n_val":   len(X_val),
        "ic":      round(rank_ic(y_val, preds), 4),
    }

    if is_classifier:
        # preds are probabilities
        metrics["auc"]   = round(roc_auc(y_val, preds), 4)
        metrics["brier"] = round(brier_score(y_val, preds), 4)
    else:
        # For regressor, compute decile spread
        try:
            df_v = pd.DataFrame({"y": y_val, "p": preds, "date": dates_val.values})
            df_v["decile"] = df_v.groupby("date")["p"].transform(
                lambda x: pd.qcut(x.rank(method="first"), 10,
                                  labels=False, duplicates="drop")
            )
            top    = df_v[df_v["decile"] == 9]["y"].mean()
            bottom = df_v[df_v["decile"] == 0]["y"].mean()
            metrics["decile_spread"] = round(float(top - bottom), 4)
        except Exception:
            metrics["decile_spread"] = None

    return metrics


def run_experiment(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    is_classifier: bool,
    min_rows: int = MIN_ROWS_PER_TIER,
) -> dict[str, dict]:
    """
    Train 6 models and return {model_id: metrics}.

    Uses a simple 80/20 time-split (no walk-forward for speed).
    For research comparison — production training uses full walk-forward.
    """
    if df.empty:
        return {}

    # Ensure feature_cols exist
    avail = [c for c in feature_cols if c in df.columns]
    df = df.copy()
    for c in feature_cols:
        if c not in df.columns:
            df[c] = np.nan

    # Sort by date for time split
    df = df.sort_values("date").reset_index(drop=True)
    split = int(len(df) * 0.80)
    train_df = df.iloc[:split].copy()
    val_df   = df.iloc[split:].copy()

    def _arrays(d: pd.DataFrame, feat_list: list[str]):
        X = d[feat_list].to_numpy(dtype=np.float64)
        y = d[target_col].to_numpy(dtype=np.float64)
        dates = d["date"].reset_index(drop=True)
        return X, y, dates

    results: dict[str, dict] = {}

    tier_configs = [
        ("A_all",      None,  feature_cols,                  "All universe"),
        ("B_large",    1,     feature_cols,                  "Large cap (tier 1)"),
        ("C_mid",      2,     feature_cols,                  "Mid cap (tier 2)"),
        ("D_small",    3,     feature_cols,                  "Small cap (tier 3)"),
        ("E_micro",    4,     feature_cols,                  "Micro cap (tier 4)"),
        ("F_interact", None,  feature_cols + ["quality_tier"], "All + quality_tier feature"),
    ]

    for model_id, tier, feats, label in tier_configs:
        feats = [f for f in feats if f in df.columns]
        if not feats:
            results[model_id] = {"label": label, "error": "no features"}
            continue

        if tier is not None:
            tr = train_df[train_df["quality_tier"] == float(tier)].copy()
            va = val_df[val_df["quality_tier"] == float(tier)].copy()
        else:
            tr, va = train_df.copy(), val_df.copy()

        if len(tr) < min_rows or len(va) < 20:
            results[model_id] = {
                "label":   label,
                "n_train": len(tr),
                "n_val":   len(va),
                "skip":    f"insufficient data (need {min_rows} train rows)",
            }
            log.info("tier_exp.skip", model=model_id, n_train=len(tr))
            continue

        X_tr, y_tr, _    = _arrays(tr, feats)
        X_val, y_val, dt = _arrays(va, feats)

        log.info("tier_exp.training", model=model_id, n_train=len(X_tr), n_val=len(X_val))
        m = _train_and_eval(X_tr, y_tr, X_val, y_val, dt, feats, is_classifier)
        m["label"] = label
        results[model_id] = m

    return results


# ── Output ────────────────────────────────────────────────────────────────────

def print_results(results: dict[str, dict], is_classifier: bool, target_col: str) -> None:
    sep = "-" * 88
    print("\n" + sep)
    print(f"  QUALITY TIER EXPERIMENT RESULTS   target={target_col}")
    print(sep)

    if is_classifier:
        print(f"  {'Model':<14}  {'Description':<28}  {'n_train':>7}  "
              f"{'IC':>7}  {'AUC':>7}  {'Brier':>7}  Status")
    else:
        print(f"  {'Model':<14}  {'Description':<28}  {'n_train':>7}  "
              f"{'IC':>7}  {'Decile':>8}  Status")
    print("  " + "-" * 84)

    best_ic = max(
        (r.get("ic", -9) for r in results.values() if "skip" not in r and "error" not in r),
        default=None
    )

    for mid, r in results.items():
        label = r.get("label", mid)
        if "error" in r:
            print(f"  {mid:<14}  {label:<28}  {'':>7}  {'ERROR':>7}  {r['error']}")
            continue
        if "skip" in r:
            n = r.get("n_train", 0)
            print(f"  {mid:<14}  {label:<28}  {n:>7}  {'SKIP':>7}  {r['skip']}")
            continue

        n_tr = r.get("n_train", 0)
        ic   = r.get("ic")
        ic_s = f"{ic:+.4f}" if ic is not None else "   n/a"
        star = " *" if ic is not None and ic == best_ic else ""

        if is_classifier:
            auc   = r.get("auc")
            brier = r.get("brier")
            auc_s   = f"{auc:.4f}"   if auc   is not None else "   n/a"
            brier_s = f"{brier:.4f}" if brier is not None else "   n/a"
            print(f"  {mid:<14}  {label:<28}  {n_tr:>7}  "
                  f"{ic_s:>7}  {auc_s:>7}  {brier_s:>7}  OK{star}")
        else:
            ds = r.get("decile_spread")
            ds_s = f"{ds:+.4f}" if ds is not None else "    n/a"
            print(f"  {mid:<14}  {label:<28}  {n_tr:>7}  "
                  f"{ic_s:>7}  {ds_s:>8}  OK{star}")

    print()
    _print_recommendation(results, is_classifier)


def _print_recommendation(results: dict[str, dict], is_classifier: bool) -> None:
    valid = {k: v for k, v in results.items()
             if "skip" not in v and "error" not in v and v.get("ic") is not None}

    if not valid:
        print("  RECOMMENDATION: Insufficient data to recommend. Run with more history.")
        return

    ic_map = {k: v["ic"] for k, v in valid.items()}
    best   = max(ic_map, key=ic_map.get)
    all_ic = ic_map.get("A_all")
    inter_ic = ic_map.get("F_interact")

    print("  RECOMMENDATION:")

    if not all_ic:
        print("  Cannot determine — Model A (all universe) did not complete.")
        return

    tier_models = {k: v for k, v in ic_map.items()
                   if k in ("B_large", "C_mid", "D_small", "E_micro")}

    best_tier_ic = max(tier_models.values()) if tier_models else None
    best_tier    = max(tier_models, key=tier_models.get) if tier_models else None

    if best_tier_ic and best_tier_ic > all_ic * 1.10:
        print(f"  Tier-specific models WIN. Best: {best_tier} (IC={best_tier_ic:+.4f} "
              f"vs all={all_ic:+.4f}).")
        print(f"  -> Train separate models per quality tier.")
    elif inter_ic and inter_ic > all_ic * 1.05:
        print(f"  Interaction model WIN. F IC={inter_ic:+.4f} vs all={all_ic:+.4f}.")
        print(f"  -> Keep single model but include quality_tier as a feature.")
    else:
        print(f"  Single model (all universe) is competitive. All IC={all_ic:+.4f}.")
        if best_tier_ic:
            print(f"  Best tier model: {best_tier} (IC={best_tier_ic:+.4f}) -- marginal gain "
                  f"({(best_tier_ic/all_ic-1)*100:+.1f}%). Not worth the complexity.")
        print(f"  -> Keep single model.")

    # Micro-cap warning
    micro = valid.get("E_micro", {})
    if micro.get("ic", 0) < 0:
        print(f"\n  [!] Micro-cap (tier 4) IC={micro.get('ic', 0):+.4f} (negative).")
        print(f"     Consider excluding micro-cap from training entirely.")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas quality tier model experiment")
    parser.add_argument("--target",      default="label_return_5d",
                        help="Target column (default label_return_5d)")
    parser.add_argument("--from-wide",   action="store_true",
                        help="Load from feature_snapshots_wide in DB instead of parquet")
    parser.add_argument("--parquet-dir", default=None,
                        help="Parquet directory (default: exports/parquet)")
    parser.add_argument("--min-rows",    type=int, default=MIN_ROWS_PER_TIER,
                        help=f"Min rows per tier to train (default {MIN_ROWS_PER_TIER})")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    is_classifier = "positive" in args.target

    # ── Load data ──────────────────────────────────────────────────────────
    print(f"\nAtlas Quality Tier Experiment")
    print(f"  Target     : {args.target}")
    print(f"  Source     : {'DB wide table' if args.from_wide else 'parquet files'}")
    print(f"  Classifier : {is_classifier}")

    if args.from_wide:
        print("\nLoading from feature_snapshots_wide...")
        df = load_from_wide(db_url, args.target)
    else:
        parquet_dir = Path(args.parquet_dir) if args.parquet_dir else ROOT / "exports" / "parquet"
        print(f"\nLoading parquet files from {parquet_dir}...")
        df = load_from_parquet(parquet_dir, args.target)

    if df.empty:
        print("[WARN] No data loaded.")
        print("       Run the nightly pipeline first to generate features + labels.")
        print("       Or use --from-wide if feature_snapshots_wide is populated.")
        return

    # Check quality_tier availability
    if "quality_tier" not in df.columns or df["quality_tier"].isna().all():
        print("[WARN] quality_tier not found in data.")
        print("       Tier-specific models (B-E) will be skipped.")

    tier_counts = {}
    if "quality_tier" in df.columns:
        for t in [1.0, 2.0, 3.0, 4.0]:
            tier_counts[int(t)] = int((df["quality_tier"] == t).sum())

    print(f"\n  Total rows  : {len(df):,}")
    print(f"  Date range  : {df['date'].min()} to {df['date'].max()}")
    if tier_counts:
        for t, n in tier_counts.items():
            names = {1:"large",2:"mid",3:"small",4:"micro"}
            print(f"  Tier {t} ({names[t]:<6}): {n:>6,} rows")

    if len(df) < 100:
        print(f"\n[WARN] Only {len(df)} rows — results will not be statistically meaningful.")
        print("       Need at least ~1,000 rows per tier for reliable IC estimates.")
        print("       Results shown for informational purposes only.")

    # ── Feature columns ────────────────────────────────────────────────────
    from config.settings import ALL_FEATURES, TRAIN_FEATURES
    feature_cols = [c for c in TRAIN_FEATURES if c in df.columns]

    print(f"\n  Feature cols: {len(feature_cols)} available of {len(TRAIN_FEATURES)}")

    # ── Run experiment ─────────────────────────────────────────────────────
    print("\nTraining models...")
    results = run_experiment(df, feature_cols, args.target, is_classifier,
                             min_rows=args.min_rows)

    # ── Print results ──────────────────────────────────────────────────────
    print_results(results, is_classifier, args.target)


if __name__ == "__main__":
    main()
