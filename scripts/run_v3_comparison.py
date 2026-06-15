"""
run_v3_comparison.py — V1 vs V3 feature set comparison.

V3 = TRAIN_FEATURES_V1 (39 features) + REGIME_INTERACTION_FEATURES (10 features).
Interaction features are computed on-the-fly from existing parquet columns.

Phases
------
1. Holdout comparison: train V1 and V3 on 2011-2025, evaluate on 2025-07-01 onward.
2. Walk-forward comparison: run V3 walk-forward; compare against V1 results in DB.
3. Report: write reports/FEATURE_SET_V3_REPORT.md with all metrics + promotion verdict.

Promotion rule: V3 beats V1 on >= 5 of 8 metrics AND does not increase IC instability.

Usage
-----
    python scripts/run_v3_comparison.py
    python scripts/run_v3_comparison.py --skip-wf       # skip V3 walk-forward (use holdout only)
    python scripts/run_v3_comparison.py --holdout-from 2025-07-01
    python scripts/run_v3_comparison.py --no-db
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import warnings
from datetime import date
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
from scipy import stats as scipy_stats

from config.settings import (
    TRAIN_FEATURES_V1, TRAIN_FEATURES_V3, REGIME_INTERACTION_FEATURES,
    LGBM_PARAMS_REGRESSOR, PARQUET_OUTPUT_DIR, MODEL_DIR,
    WF_MIN_TRAIN_YEARS, WF_VAL_MONTHS, WF_PURGE_DAYS, TRAIN_MIN_QUALITY_SCORE,
)
from atlas_research.features.regime_interactions import add_interactions
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_v3_comparison")

TARGET_COL   = "label_return_5d"
HOLDOUT_FROM = "2025-07-01"
REPORT_PATH  = ROOT / "reports" / "FEATURE_SET_V3_REPORT.md"


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_parquet(
    parquet_dir: Path,
    holdout_from: str,
    feature_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load parquet files split into pre-holdout (train) and holdout (eval)."""
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    pre, post = [], []

    # Base columns we need (interaction outputs are computed, not loaded)
    from atlas_research.features.regime_interactions import INTERACTION_NAMES, BASE_COLS_NEEDED
    base_cols = [f for f in feature_cols if f not in INTERACTION_NAMES]
    needed = {"ticker", "date", TARGET_COL} | set(base_cols) | BASE_COLS_NEEDED

    for f in files:
        bucket = post if f.stem >= f"feature_matrix_{holdout_from}" else pre
        try:
            df = pd.read_parquet(f, engine="pyarrow")
            avail = [c for c in needed if c in df.columns]
            bucket.append(df[avail])
        except Exception:
            pass

    def combine(frames: list) -> pd.DataFrame:
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        # Add interaction features
        add_interactions(out)
        out = out[out[TARGET_COL].notna()]
        # Fill missing feature cols with NaN
        for col in feature_cols:
            if col not in out.columns:
                out[col] = np.nan
        return out.sort_values("date").reset_index(drop=True)

    return combine(pre), combine(post)


# ── Model training ────────────────────────────────────────────────────────────

def train_lgbm(train_df: pd.DataFrame, feature_cols: list[str]) -> object:
    import lightgbm as lgb

    params = LGBM_PARAMS_REGRESSOR.copy()
    avail  = [f for f in feature_cols if f in train_df.columns]
    X      = train_df[avail].to_numpy(dtype=np.float64)
    y      = train_df[TARGET_COL].to_numpy(dtype=np.float64)

    n_es  = max(1, int(len(X) * 0.05))
    X_es, y_es = X[-n_es:], y[-n_es:]
    X_t,  y_t  = X[:-n_es], y[:-n_es]

    ds    = lgb.Dataset(X_t, label=y_t, feature_name=avail)
    es_ds = lgb.Dataset(X_es, label=y_es, feature_name=avail, reference=ds)
    model = lgb.train(
        params, ds,
        valid_sets=[es_ds],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
    )
    return model, avail


# ── Metrics ───────────────────────────────────────────────────────────────────

def _rank_ic_series(y_true: np.ndarray, y_pred: np.ndarray, dates: np.ndarray) -> np.ndarray:
    ics = []
    for d in np.unique(dates):
        m = dates == d
        yt, yp = y_true[m], y_pred[m]
        if len(yt) < 5:
            continue
        ic, _ = scipy_stats.spearmanr(yt, yp)
        if not np.isnan(ic):
            ics.append(ic)
    return np.array(ics)


def _decile_spread(y_true, y_pred, dates):
    tops, bots = [], []
    for d in np.unique(dates):
        m = dates == d
        yt, yp = y_true[m], y_pred[m]
        n = len(yt)
        if n < 10:
            continue
        k = max(1, n // 10)
        idx = np.argsort(yp)
        tops.append(np.mean(yt[idx[-k:]]))
        bots.append(np.mean(yt[idx[:k]]))
    if not tops:
        return 0.0, 0.0, 0.0
    return float(np.mean(tops)), float(np.mean(bots)), float(np.mean(tops) - np.mean(bots))


def _auc_brier(y_true_ret, y_pred):
    from sklearn.metrics import roc_auc_score, brier_score_loss
    binary = (y_true_ret > 0).astype(int)
    ranks  = scipy_stats.rankdata(y_pred) / len(y_pred)
    try:
        auc = float(roc_auc_score(binary, ranks))
    except Exception:
        auc = float("nan")
    return auc, float(brier_score_loss(binary, ranks))


def _overlap(p1, p2, tickers, dates):
    jacs = []
    for d in np.unique(dates):
        m = dates == d
        t, a, b = tickers[m], p1[m], p2[m]
        n = len(t)
        if n < 10:
            continue
        k = max(1, n // 10)
        s1 = set(t[np.argsort(a)[-k:]])
        s2 = set(t[np.argsort(b)[-k:]])
        u = len(s1 | s2)
        jacs.append(len(s1 & s2) / u if u else 0.0)
    return float(np.mean(jacs)) if jacs else 0.0


def evaluate(model, holdout_df: pd.DataFrame, feature_cols: list[str],
             other_preds: np.ndarray | None = None) -> dict:
    avail  = [f for f in feature_cols if f in holdout_df.columns]
    X      = holdout_df[avail].to_numpy(dtype=np.float64)
    y      = holdout_df[TARGET_COL].to_numpy(dtype=np.float64)
    dates  = holdout_df["date"].to_numpy()
    tickers = holdout_df["ticker"].to_numpy()

    preds   = model.predict(X)
    ics     = _rank_ic_series(y, preds, dates)
    top, bot, spread = _decile_spread(y, preds, dates)
    auc, brier = _auc_brier(y, preds)
    sharpe  = float(np.mean(ics) / np.std(ics) * np.sqrt(252)) if np.std(ics) > 0 else 0.0
    overlap = _overlap(preds, other_preds, tickers, dates) if other_preds is not None else None

    return {
        "preds":         preds,
        "mean_ic":       float(np.mean(ics)),
        "ic_std":        float(np.std(ics)),
        "sharpe":        sharpe,
        "decile_spread": spread,
        "top_decile_ret": top,
        "bot_decile_ret": bot,
        "auc":           auc,
        "brier":         brier,
        "overlap":       overlap,
        "n_dates":       len(np.unique(dates)),
        "n_rows":        len(y),
    }


# ── Walk-forward V3 ───────────────────────────────────────────────────────────

def run_v3_walk_forward(parquet_dir: Path, model_dir: Path, write_db: bool) -> list[dict]:
    from atlas_research.models.walk_forward import run_walk_forward
    from atlas_research.models.dataset import load_date_range

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    if not parquet_files:
        return []
    first = parquet_files[0].stem.replace("feature_matrix_", "")
    data_start = date.fromisoformat(first)
    data_end   = date.today()

    results = run_walk_forward(
        data_start          = data_start,
        data_end            = data_end,
        parquet_dir         = parquet_dir,
        model_dir           = model_dir,
        feature_cols        = TRAIN_FEATURES_V3,
        model_version       = "v3",
        min_train_years     = WF_MIN_TRAIN_YEARS,
        val_months          = WF_VAL_MONTHS,
        purge_days          = WF_PURGE_DAYS,
        min_quality_score   = TRAIN_MIN_QUALITY_SCORE,
        write_db            = write_db,
        feature_set_version = "v3",
    )
    return results


# ── V1 WF stats from DB ───────────────────────────────────────────────────────

def get_v1_wf_stats(db_url: str) -> dict:
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rank_ic, sharpe
                FROM model_registry
                WHERE feature_set_version = 'v1'
                  AND model_name = 'return_regressor'
                  AND rank_ic IS NOT NULL
                ORDER BY training_end DESC
                LIMIT 12
            """)
            rows = cur.fetchall()
    if not rows:
        return {"mean_rank_ic": None, "mean_sharpe": None, "n_folds": 0}
    ics     = [r[0] for r in rows if r[0] is not None]
    sharpes = [r[1] for r in rows if r[1] is not None]
    return {
        "mean_rank_ic": float(np.mean(ics))     if ics     else None,
        "mean_sharpe":  float(np.mean(sharpes)) if sharpes else None,
        "n_folds":      len(rows),
    }


# ── Holdout comparison output ─────────────────────────────────────────────────

def _fmt(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "   n/a "
    return f"{v:+.4f}"


def print_holdout_comparison(v1: dict, v3: dict) -> tuple[int, int]:
    sep = "-" * 90

    METRICS = [
        ("Mean Rank IC",          "mean_ic",        False),
        ("IC Std (lower=better)", "ic_std",         True),
        ("Sharpe",                "sharpe",         False),
        ("Decile Spread",         "decile_spread",  False),
        ("AUC",                   "auc",            False),
        ("Brier (lower=better)",  "brier",          True),
        ("Top Decile Return",     "top_decile_ret", False),
        ("Bot Decile Return",     "bot_decile_ret", False),
    ]

    print(f"\n{sep}")
    print("  HOLDOUT COMPARISON: V1 (39 feat) vs V3 (49 feat)")
    print(sep)
    print(f"  Holdout period : {HOLDOUT_FROM} onward")
    print(f"  Holdout rows   : {v1['n_rows']:,}  ({v1['n_dates']} dates)")
    if v3["overlap"] is not None:
        print(f"  Pred overlap   : {v3['overlap']*100:.1f}%  (Jaccard, top-decile per day)")
    print()
    print(f"  {'Metric':<28}  {'V1':>10}  {'V3':>10}  Winner")
    print("  " + "-" * 62)

    v3_wins = v1_wins = 0
    for name, key, lower_better in METRICS:
        val1 = v1.get(key)
        val3 = v3.get(key)
        if val1 is None or val3 is None:
            w = "n/a"
        elif lower_better:
            w = "V3 [+]" if val3 < val1 else ("TIE" if val3 == val1 else "V1 [+]")
        else:
            w = "V3 [+]" if val3 > val1 else ("TIE" if val3 == val1 else "V1 [+]")
        if w.startswith("V3"):
            v3_wins += 1
        elif w.startswith("V1"):
            v1_wins += 1
        print(f"  {name:<28}  {_fmt(val1):>10}  {_fmt(val3):>10}  {w}")

    print()
    print(f"  V3 wins: {v3_wins}/8    V1 wins: {v1_wins}/8")
    verdict = "PROMOTE V3" if v3_wins >= 5 else "KEEP V1"
    print(f"  Verdict: {verdict}  (threshold: >= 5 of 8)")
    print(sep)
    return v3_wins, v1_wins


# ── Report writer ─────────────────────────────────────────────────────────────

def write_report(
    holdout_v1: dict,
    holdout_v3: dict,
    wf_v3_results: list,
    wf_v1_db: dict,
    v3_wins: int,
    v1_wins: int,
) -> None:
    promoted = (v3_wins >= 5 and
                (holdout_v3.get("ic_std") or 9) <= (holdout_v1.get("ic_std") or 0) * 1.1)

    wf_v3_ok  = [r for r in wf_v3_results if not r.error]
    wf_v3_ics = [r.val_metrics.get("rank_ic") for r in wf_v3_ok
                 if r.val_metrics.get("rank_ic") is not None]
    wf_v3_sh  = [r.val_metrics.get("sharpe") for r in wf_v3_ok
                 if r.val_metrics.get("sharpe") is not None]
    wf_v3_mean_ic = float(np.mean(wf_v3_ics)) if wf_v3_ics else None
    wf_v3_mean_sh = float(np.mean(wf_v3_sh))  if wf_v3_sh  else None

    today = date.today().isoformat()

    lines = [
        "# Feature Set V3 Report",
        f"**Date:** {today}  ",
        f"**Script:** `scripts/run_v3_comparison.py`  ",
        "",
        "---",
        "",
        "## Overview",
        "",
        "V3 adds 10 regime-interaction features to the V1 base (39 features).",
        "Each interaction = `base_feature * regime_mask` where the regime mask is",
        "a binary column derived from `spy_above_sma200` or `market_trend`.",
        "Interaction features are computed on-the-fly at training and inference time;",
        "no parquet backfill required.",
        "",
        "**V1:** 39 features (production baseline, mean WF rank IC = 0.0599)",
        f"**V3:** {len(TRAIN_FEATURES_V3)} features (V1 + {len(REGIME_INTERACTION_FEATURES)} interactions)",
        "",
        "### Interaction Features Added",
        "",
        "| Feature | Formula | Rationale |",
        "|---|---|---|",
        "| `omni_82_distance_x_above_200dma` | omni_82_distance * spy_above_sma200 | OMNI IC +0.026 above 200DMA, -0.011 below |",
        "| `omni_82_above_x_above_200dma` | omni_82_above * spy_above_sma200 | OMNI flag IC +0.015 above, -0.006 below |",
        "| `omni_82_slope_x_above_200dma` | omni_82_slope * spy_above_sma200 | OMNI slope IC +0.002 above, -0.054 below |",
        "| `realized_vol_20_x_below_200dma` | realized_vol_20 * (1-spy_above_sma200) | vol IC +0.053 in bear, +0.046 below 200DMA |",
        "| `realized_vol_60_x_below_200dma` | realized_vol_60 * (1-spy_above_sma200) | vol IC +0.053 in bear, +0.048 below 200DMA |",
        "| `return_1d_x_below_200dma` | return_1d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |",
        "| `return_3d_x_below_200dma` | return_3d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |",
        "| `return_5d_x_below_200dma` | return_5d * (1-spy_above_sma200) | mean reversion stronger below 200DMA |",
        "| `rs_spy_20_x_bull` | rs_spy_20 * (market_trend==1) | RS IC +0.010 in low_vol, near 0 in bull/bear |",
        "| `rs_spy_60_x_bull` | rs_spy_60 * (market_trend==1) | RS IC +0.005 in low_vol, -0.056 below 200DMA |",
        "",
        "---",
        "",
        "## Phase 1: Holdout Comparison (2011-2025 train, 2025-07-01+ eval)",
        "",
        f"| Metric | V1 (39 feat) | V3 ({len(TRAIN_FEATURES_V3)} feat) | Winner |",
        "|---|---|---|---|",
    ]

    METRICS = [
        ("Mean Rank IC",          "mean_ic",        False),
        ("IC Std (lower=better)", "ic_std",         True),
        ("Sharpe",                "sharpe",         False),
        ("Decile Spread",         "decile_spread",  False),
        ("AUC",                   "auc",            False),
        ("Brier (lower=better)",  "brier",          True),
        ("Top Decile Return",     "top_decile_ret", False),
        ("Bot Decile Return",     "bot_decile_ret", False),
    ]
    for name, key, lower in METRICS:
        v1v = holdout_v1.get(key)
        v3v = holdout_v3.get(key)
        if v1v is None or v3v is None:
            w = "n/a"
        elif lower:
            w = "**V3**" if v3v < v1v else ("TIE" if v3v == v1v else "**V1**")
        else:
            w = "**V3**" if v3v > v1v else ("TIE" if v3v == v1v else "**V1**")
        lines.append(f"| {name} | {_fmt(v1v)} | {_fmt(v3v)} | {w} |")

    ov = holdout_v3.get("overlap")
    lines += [
        "",
        f"**Prediction overlap (Jaccard, top-decile):** {ov*100:.1f}%" if ov else "",
        f"**Holdout rows:** {holdout_v1.get('n_rows', 0):,}  ({holdout_v1.get('n_dates', 0)} dates)",
        f"**V3 wins:** {v3_wins}/8  |  **V1 wins:** {v1_wins}/8",
        "",
    ]

    lines += [
        "---",
        "",
        "## Phase 2: Walk-Forward Comparison",
        "",
        "| Metric | V1 (from DB) | V3 (this run) |",
        "|---|---|---|",
        f"| Mean Rank IC | {_fmt(wf_v1_db.get('mean_rank_ic'))} | {_fmt(wf_v3_mean_ic)} |",
        f"| Mean Sharpe  | {_fmt(wf_v1_db.get('mean_sharpe'))}  | {_fmt(wf_v3_mean_sh)} |",
        f"| Folds OK     | {wf_v1_db.get('n_folds', 0)} | {len(wf_v3_ok)} |",
        "",
    ]

    if wf_v3_ok:
        lines += ["**V3 per-fold rank IC:**", ""]
        lines.append("| Fold | Val Start | Val End | Rank IC | Sharpe |")
        lines.append("|---|---|---|---|---|")
        for r in wf_v3_ok:
            ric = r.val_metrics.get("rank_ic")
            sh  = r.val_metrics.get("sharpe")
            lines.append(
                f"| {r.fold.number} | {r.fold.val_start} | {r.fold.val_end} "
                f"| {_fmt(ric)} | {_fmt(sh)} |"
            )
        lines.append("")

    lines += [
        "---",
        "",
        "## Promotion Verdict",
        "",
    ]

    if v3_wins >= 5:
        stability_ok = (holdout_v3.get("ic_std") or 9) <= (holdout_v1.get("ic_std") or 0) * 1.1
        if stability_ok:
            lines += [
                "**VERDICT: PROMOTE V3** (wins {}/8 holdout metrics + IC stability OK)".format(v3_wins),
                "",
                "Steps to promote:",
                "1. Set `MODEL_FEATURE_SET_VERSION=v3` in `.env`",
                "2. Re-run `python scripts/run_training.py` to retrain on full data with V3",
                "3. Re-run `python scripts/run_training.py --predict-only`",
                "4. Update `CONSENSUS.md` to reflect V3 as production",
                "",
                "V1 remains available as rollback: `MODEL_FEATURE_SET_VERSION=v1`",
            ]
        else:
            lines += [
                "**VERDICT: KEEP V1** (V3 wins {}/8 holdout metrics but IC std increased)".format(v3_wins),
                "",
                "V3 wins enough metrics but introduces instability (IC std increased >10%).",
                "Run for another 6 months of data before reconsidering.",
            ]
    else:
        lines += [
            "**VERDICT: KEEP V1** (V3 wins only {}/8 holdout metrics; threshold = 5)".format(v3_wins),
            "",
            "V3 interaction features did not consistently outperform V1 on the holdout.",
            "Possible reasons:",
            "- 2025-2026 holdout is a bull market; OMNI features already work well above 200DMA",
            "- Interaction features may need more data in bear/below-200DMA regimes to show advantage",
            "- Consider V3 with different interaction combinations or thresholds",
            "",
            "V1 remains production. V3 is preserved as `MODEL_FEATURE_SET_VERSION=v3` for future use.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Caveats",
        "",
        "1. **Holdout period is a bull market (2025-07-01+)** — regime interactions may not show",
        "   advantage until the model encounters a bear market or high-vol period.",
        "2. **V3 walk-forward uses the same folds as V1** — the mean rank IC comparison is fair",
        "   since both evaluate on identical validation windows.",
        "3. **Interaction features have NaN in older parquet** where base columns are missing —",
        "   LightGBM handles NaN natively; early folds effectively run with fewer interactions.",
    ]

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  Report written: {REPORT_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="V1 vs V3 feature set comparison")
    parser.add_argument("--holdout-from", default=HOLDOUT_FROM)
    parser.add_argument("--skip-wf",      action="store_true",
                        help="Skip V3 walk-forward; use holdout results only")
    parser.add_argument("--no-db",        action="store_true")
    parser.add_argument("--parquet-dir",  default=None)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    parquet_dir = Path(args.parquet_dir) if args.parquet_dir else PARQUET_OUTPUT_DIR
    model_dir   = MODEL_DIR
    write_db    = not args.no_db

    print(f"\nV3 Feature Set Comparison")
    print(f"  V1 : {len(TRAIN_FEATURES_V1)} features (baseline)")
    print(f"  V3 : {len(TRAIN_FEATURES_V3)} features (V1 + {len(REGIME_INTERACTION_FEATURES)} interactions)")
    print(f"  Holdout from : {args.holdout_from}")
    print(f"  Parquet dir  : {parquet_dir}")

    # ── Phase 1: Holdout comparison ────────────────────────────────────────
    print(f"\n[1/3] Loading parquet data (holdout from {args.holdout_from})...")
    t0 = time.monotonic()

    all_needed = list(set(TRAIN_FEATURES_V1) | set(TRAIN_FEATURES_V3))
    train_df, holdout_df = load_all_parquet(parquet_dir, args.holdout_from, all_needed)

    print(f"  Pre-holdout : {len(train_df):,} rows  ({train_df['date'].min()} to {train_df['date'].max()})")
    print(f"  Holdout     : {len(holdout_df):,} rows  ({holdout_df['date'].min()} to {holdout_df['date'].max()})")

    if len(holdout_df) < 100:
        sys.exit("[ERROR] Holdout too small. Check parquet data and --holdout-from.")

    print(f"\n  Training V1 ({len(TRAIN_FEATURES_V1)} features)...")
    t1 = time.monotonic()
    model_v1, v1_feats = train_lgbm(train_df, TRAIN_FEATURES_V1)
    print(f"  Done ({time.monotonic()-t1:.1f}s)")

    print(f"\n  Training V3 ({len(TRAIN_FEATURES_V3)} features)...")
    t2 = time.monotonic()
    model_v3, v3_feats = train_lgbm(train_df, TRAIN_FEATURES_V3)
    print(f"  Done ({time.monotonic()-t2:.1f}s)")

    print(f"\n  Evaluating on holdout...")
    h1_feats = [f for f in v1_feats if f in holdout_df.columns]
    h3_feats = [f for f in v3_feats if f in holdout_df.columns]

    # Compute V3 preds first for overlap calc
    X_h3 = holdout_df[h3_feats].to_numpy(dtype=np.float64)
    preds_v3_raw = model_v3.predict(X_h3)

    results_v1 = evaluate(model_v1, holdout_df, h1_feats, other_preds=preds_v3_raw)
    results_v3 = evaluate(model_v3, holdout_df, h3_feats, other_preds=results_v1["preds"])

    v3_wins, v1_wins = print_holdout_comparison(results_v1, results_v3)

    # ── Phase 2: V3 Walk-forward ────────────────────────────────────────────
    wf_v3_results = []
    if not args.skip_wf:
        print(f"\n[2/3] Running V3 walk-forward (full 12-fold)...")
        t_wf = time.monotonic()
        wf_v3_results = run_v3_walk_forward(parquet_dir, model_dir, write_db)
        wf_ok  = [r for r in wf_v3_results if not r.error]
        wf_err = [r for r in wf_v3_results if r.error]
        print(f"  Done ({time.monotonic()-t_wf:.1f}s): {len(wf_ok)} folds OK, {len(wf_err)} errors")

        if wf_ok:
            v3_ics = [r.val_metrics.get("rank_ic") for r in wf_ok
                      if r.val_metrics.get("rank_ic") is not None]
            print(f"  V3 mean rank IC (WF): {np.mean(v3_ics):+.4f}")
    else:
        print("\n[2/3] Skipping walk-forward (--skip-wf)")

    # ── Phase 3: Fetch V1 WF stats from DB ─────────────────────────────────
    print(f"\n[3/3] Fetching V1 WF stats from DB...")
    wf_v1_db = get_v1_wf_stats(db_url)
    print(f"  V1 mean rank IC (WF, {wf_v1_db['n_folds']} folds): "
          f"{wf_v1_db['mean_rank_ic']:+.4f}" if wf_v1_db['mean_rank_ic'] else "  n/a")

    # ── Write report ────────────────────────────────────────────────────────
    write_report(results_v1, results_v3, wf_v3_results, wf_v1_db, v3_wins, v1_wins)

    elapsed = time.monotonic() - t0
    print(f"\n  Total time: {elapsed:.1f}s")
    print(f"  Report: {REPORT_PATH}")

    # Exit 0 = V3 wins, 1 = keep V1
    sys.exit(0 if v3_wins >= 5 else 1)


if __name__ == "__main__":
    main()
