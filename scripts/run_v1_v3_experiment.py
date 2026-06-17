#!/usr/bin/env python
"""
run_v1_v3_experiment.py — clean-pipeline V1 vs V3 comparison (Phase 2).

Runs BOTH feature sets on IDENTICAL OOS-embargoed walk-forward folds, using the
exact dataset/train/evaluate functions from the fixed pipeline (trading-day
purge, flag-aware cross-sectional normalisation, leak-free Platt calibration).

For each fold we load the data ONCE with the V3 superset of columns, normalise
once, then slice the feature matrix for V1 and V3 — so the two models see the
same rows, same folds, same normalisation, differing only in feature columns.

Outputs reports/validity/v1_v3_experiment.json with:
  - pooled per-day rank IC (mean, std, t-stat, n_days) for V1 and V3
  - AUC, Brier, decile spread, decile monotonicity, top-decile return
  - regressor tree counts per fold
  - sign_stability of V3 interaction features vs their V1 base features
  - a single OOS score for the chosen candidate (per --oos-feature-set)

Usage:
    python scripts/run_v1_v3_experiment.py
    python scripts/run_v1_v3_experiment.py --oos-feature-set v3   # score V3 on OOS
    python scripts/run_v1_v3_experiment.py --max-folds 3          # quick smoke
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
warnings.filterwarnings("ignore")

import glob
import numpy as np
import pandas as pd
from scipy import stats

from config import settings
from atlas_research.models.dataset import (
    apply_purge_gap, cross_sectional_normalize, load_date_range, to_arrays,
)
from atlas_research.models.train import train_regressor, train_classifier, predict_classifier
from atlas_research.models.evaluate import roc_auc, brier_score
from atlas_research.models.walk_forward import generate_folds, oos_window
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("v1_v3_experiment")

REG_TARGET = "label_return_5d"
CLF_TARGET = "label_positive_5d"
OUT = ROOT / "reports" / "validity" / "v1_v3_experiment.json"


# ── per-day metrics ────────────────────────────────────────────────────────

def per_day_ic(dates, y_true, y_pred) -> list[float]:
    df = pd.DataFrame({"d": dates, "y": y_true, "p": y_pred})
    out = []
    for _, g in df.groupby("d"):
        if len(g) < 5 or g["p"].nunique() < 2 or g["y"].nunique() < 2:
            continue
        ic, _ = stats.spearmanr(g["p"], g["y"])
        if ic is not None and not math.isnan(ic):
            out.append(float(ic))
    return out


def per_day_deciles(dates, y_true, y_pred):
    """Return (top_mean, bottom_mean, decile_means[10]) pooled across days."""
    df = pd.DataFrame({"d": dates, "y": y_true, "p": y_pred})
    tops, bots = [], []
    dec_acc = {k: [] for k in range(10)}
    for _, g in df.groupby("d"):
        n = len(g)
        if n < 20:
            continue
        order = np.argsort(g["p"].to_numpy())
        yv = g["y"].to_numpy()[order]
        # split into 10 buckets by prediction rank
        edges = np.linspace(0, n, 11).astype(int)
        for k in range(10):
            seg = yv[edges[k]:edges[k + 1]]
            if len(seg):
                dec_acc[k].append(float(np.mean(seg)))
        k_top = max(1, n // 10)
        tops.append(float(np.mean(yv[-k_top:])))
        bots.append(float(np.mean(yv[:k_top])))
    dec_means = [float(np.mean(dec_acc[k])) if dec_acc[k] else float("nan") for k in range(10)]
    top = float(np.mean(tops)) if tops else float("nan")
    bot = float(np.mean(bots)) if bots else float("nan")
    return top, bot, dec_means


def ic_summary(ics: list[float]) -> dict:
    a = np.array(ics, dtype=float)
    n = len(a)
    if n < 2:
        return {"mean_ic": float("nan"), "ic_std": float("nan"),
                "ic_tstat": float("nan"), "n_days": n}
    mean = float(np.mean(a)); std = float(np.std(a, ddof=1))
    t = mean / (std / math.sqrt(n)) if std > 0 else float("nan")
    return {"mean_ic": mean, "ic_std": std, "ic_tstat": t, "n_days": n}


def decile_monotonicity(dec_means: list[float]) -> float:
    vals = [v for v in dec_means if not math.isnan(v)]
    if len(vals) < 3:
        return float("nan")
    idx = list(range(len(vals)))
    rho, _ = stats.spearmanr(idx, vals)
    return float(rho)


# ── data loading (shared across both feature sets) ─────────────────────────

def load_fold_frame(start, end, feature_cols_v3, target):
    """Load + normalise once with the V3 superset of columns."""
    df = load_date_range(start, end, feature_cols_v3, target,
                         settings.PARQUET_OUTPUT_DIR, settings.TRAIN_MIN_QUALITY_SCORE)
    return df


def slice_xy(df, feature_cols, target):
    X, y, tk, dt = to_arrays(df, feature_cols, target)
    return X, y, tk, dt


# ── one fold, both feature sets ────────────────────────────────────────────

def run_fold_both(fold, v1_cols, v3_cols, collectors):
    # Load once (reg + clf) with V3 superset, purge, normalise.
    tr = load_fold_frame(fold.train_start, fold.train_end, v3_cols, REG_TARGET)
    va = load_fold_frame(fold.val_start, fold.val_end, v3_cols, REG_TARGET)
    tr_c = load_fold_frame(fold.train_start, fold.train_end, v3_cols, CLF_TARGET)
    va_c = load_fold_frame(fold.val_start, fold.val_end, v3_cols, CLF_TARGET)
    if tr.empty or va.empty:
        log.warning("exp.fold_skip", fold=fold.number)
        return
    tr, va = apply_purge_gap(tr, va, settings.WF_PURGE_DAYS)
    tr_c, va_c = apply_purge_gap(tr_c, va_c, settings.WF_PURGE_DAYS)
    tr = cross_sectional_normalize(tr, v3_cols); va = cross_sectional_normalize(va, v3_cols)
    tr_c = cross_sectional_normalize(tr_c, v3_cols); va_c = cross_sectional_normalize(va_c, v3_cols)

    for name, cols in [("v1", v1_cols), ("v3", v3_cols)]:
        Xtr, ytr, _, _ = slice_xy(tr, cols, REG_TARGET)
        Xva, yva, _, dva = slice_xy(va, cols, REG_TARGET)
        reg, imp = train_regressor(Xtr, ytr, Xva, yva, cols)
        pred = reg.predict(Xva)
        ics = per_day_ic(dva.to_numpy(), yva, pred)
        top, bot, dmeans = per_day_deciles(dva.to_numpy(), yva, pred)

        # classifier
        Xtrc, ytrc, _, _ = slice_xy(tr_c, cols, CLF_TARGET)
        Xvac, yvac, _, _ = slice_xy(va_c, cols, CLF_TARGET)
        clf, platt, _ = train_classifier(Xtrc, ytrc, Xvac, yvac, cols)
        prob = predict_classifier(clf, platt, Xvac)
        auc = roc_auc(yvac, prob); brier = brier_score(yvac, prob)

        c = collectors[name]
        c["ics"].extend(ics)
        c["fold_ic_mean"].append(float(np.mean(ics)) if ics else float("nan"))
        c["tops"].append(top); c["bots"].append(bot)
        c["dec_means"].append(dmeans)
        c["auc"].append(auc); c["brier"].append(brier)
        c["reg_trees"].append(int(reg.num_trees()))
        c["clf_trees"].append(int(clf.num_trees()))
        # univariate feature IC signs for sign_stability (val fold)
        sign_row = {}
        vdf = va.copy(); vdf["_y"] = yva
        for f in cols:
            if f not in vdf.columns:
                continue
            sub = vdf[["date", f, "_y"]].dropna()
            fic = []
            for _, g in sub.groupby("date"):
                if len(g) < 5 or g[f].nunique() < 2 or g["_y"].nunique() < 2:
                    continue
                ic, _ = stats.spearmanr(g[f], g["_y"])
                if not math.isnan(ic):
                    fic.append(ic)
            if fic:
                sign_row[f] = 1 if np.mean(fic) >= 0 else -1
        c["feat_signs"].append(sign_row)
        log.info("exp.fold_set_done", fold=fold.number, set=name,
                 n_ic_days=len(ics), reg_trees=int(reg.num_trees()))


def sign_stability(feat_signs: list[dict], feature: str) -> float | None:
    signs = [fs[feature] for fs in feat_signs if feature in fs]
    if not signs:
        return None
    pos = sum(1 for s in signs if s > 0) / len(signs)
    return float(max(pos, 1 - pos))


def _score_oos(result, name, ds, oos_s, oos_e, v1_cols, v3_cols):
    """Train the chosen feature set on all pre-OOS data, score OOS ONCE."""
    cols = v1_cols if name == "v1" else v3_cols
    print(f"\nScoring {name.upper()} ONCE on OOS {oos_s}->{oos_e} ...")
    tr = load_fold_frame(ds, oos_s, v3_cols, REG_TARGET)
    oo = load_fold_frame(oos_s, oos_e, v3_cols, REG_TARGET)
    tr, oo = apply_purge_gap(tr, oo, settings.WF_PURGE_DAYS)
    tr = cross_sectional_normalize(tr, v3_cols); oo = cross_sectional_normalize(oo, v3_cols)
    Xtr, ytr, _, _ = slice_xy(tr, cols, REG_TARGET)
    Xoo, yoo, _, doo = slice_xy(oo, cols, REG_TARGET)
    reg, _ = train_regressor(Xtr, ytr, Xoo, yoo, cols)
    pred = reg.predict(Xoo)
    ics = per_day_ic(doo.to_numpy(), yoo, pred)
    top, bot, dmeans = per_day_deciles(doo.to_numpy(), yoo, pred)
    oos = ic_summary(ics)
    oos.update({"top_decile_ret": top, "bot_decile_ret": bot,
                "decile_spread": top - bot,
                "decile_monotonicity": decile_monotonicity(dmeans),
                "reg_trees": int(reg.num_trees()),
                "feature_set": name, "n_rows": int(len(yoo))})
    if oos["ic_tstat"] == oos["ic_tstat"] and oos["n_days"] > 2:
        oos["ic_p_naive"] = float(2 * stats.t.sf(abs(oos["ic_tstat"]), df=oos["n_days"] - 1))
    result["oos"] = oos
    print(f"  OOS {name}: mean_ic={oos['mean_ic']:+.4f}  t={oos['ic_tstat']:+.2f}  "
          f"n_days={oos['n_days']}  decile_spread={oos['decile_spread']:+.4f}")
    return oos


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oos-feature-set", choices=["v1", "v3"], default=None,
                    help="Score this set ONCE on the embargoed OOS. Omit to skip OOS.")
    ap.add_argument("--max-folds", type=int, default=None, help="Limit folds (smoke test)")
    ap.add_argument("--oos-only", action="store_true",
                    help="Skip the fold loop; only score OOS and merge into existing JSON.")
    args = ap.parse_args()

    files = sorted(glob.glob(str(settings.PARQUET_OUTPUT_DIR / "feature_matrix_*.parquet")))
    ds = date.fromisoformat(files[0].split("feature_matrix_")[1][:10])
    de = date.fromisoformat(files[-1].split("feature_matrix_")[1][:10])
    oos_s, oos_e = oos_window(de, settings.WF_OOS_MONTHS)

    v1_cols = list(settings.TRAIN_FEATURES_V1)
    v3_cols = list(settings.TRAIN_FEATURES_V3)

    folds = generate_folds(ds, de, settings.WF_MIN_TRAIN_YEARS,
                           settings.WF_VAL_MONTHS, settings.WF_OOS_MONTHS)
    if args.max_folds:
        folds = folds[:args.max_folds]

    print(f"V1 vs V3 experiment | data {ds}->{de} | OOS {oos_s}->{oos_e} | {len(folds)} folds")

    # ── OOS-only mode: load prior validation result, score OOS, re-save ─────
    if args.oos_only:
        if not OUT.exists():
            sys.exit("[ERROR] --oos-only needs an existing v1_v3_experiment.json")
        if not args.oos_feature_set:
            sys.exit("[ERROR] --oos-only requires --oos-feature-set")
        result = json.loads(OUT.read_text())
        _score_oos(result, args.oos_feature_set, ds, oos_s, oos_e, v1_cols, v3_cols)
        OUT.write_text(json.dumps(result, indent=2))
        print(f"\nMerged OOS into {OUT}")
        return

    collectors = {n: {"ics": [], "fold_ic_mean": [], "tops": [], "bots": [],
                      "dec_means": [], "auc": [], "brier": [], "reg_trees": [],
                      "clf_trees": [], "feat_signs": []} for n in ("v1", "v3")}

    for fold in folds:
        log.info("exp.fold_start", fold=fold.number,
                 train=f"{fold.train_start}->{fold.train_end}",
                 val=f"{fold.val_start}->{fold.val_end}")
        run_fold_both(fold, v1_cols, v3_cols, collectors)

    # ── aggregate ───────────────────────────────────────────────────────────
    result = {"data_start": str(ds), "data_end": str(de),
              "oos_start": str(oos_s), "oos_end": str(oos_e),
              "n_folds": len(folds), "sets": {}}
    for name in ("v1", "v3"):
        c = collectors[name]
        s = ic_summary(c["ics"])
        # pooled decile means (average the per-fold decile vectors)
        dm = np.nanmean(np.array(c["dec_means"], dtype=float), axis=0).tolist() if c["dec_means"] else []
        result["sets"][name] = {
            **s,
            "auc_mean": float(np.nanmean(c["auc"])),
            "brier_mean": float(np.nanmean(c["brier"])),
            "top_decile_ret": float(np.nanmean(c["tops"])),
            "bot_decile_ret": float(np.nanmean(c["bots"])),
            "decile_spread": float(np.nanmean(c["tops"]) - np.nanmean(c["bots"])),
            "decile_means": dm,
            "decile_monotonicity": decile_monotonicity(dm),
            "reg_trees": c["reg_trees"],
            "clf_trees": c["clf_trees"],
            "fold_ic_mean": c["fold_ic_mean"],
        }

    # ── sign stability: V3 interactions vs their V1 base features ───────────
    base_map = {
        "omni_82_distance_x_above_200dma": "omni_82_distance",
        "omni_82_above_x_above_200dma": "omni_82_above",
        "omni_82_slope_x_above_200dma": "omni_82_slope",
        "realized_vol_20_x_below_200dma": "realized_vol_20",
        "realized_vol_60_x_below_200dma": "realized_vol_60",
        "return_1d_x_below_200dma": "return_1d",
        "return_3d_x_below_200dma": "return_3d",
        "return_5d_x_below_200dma": "return_5d",
        "rs_spy_20_x_bull": "rs_spy_20",
        "rs_spy_60_x_bull": "rs_spy_60",
    }
    stab = {}
    for inter, base in base_map.items():
        stab[inter] = {
            "interaction_stability": sign_stability(collectors["v3"]["feat_signs"], inter),
            "base_feature": base,
            "base_stability": sign_stability(collectors["v1"]["feat_signs"], base),
        }
    result["sign_stability"] = stab

    # ── multiple-comparison-adjusted significance (V1, V2, V3 = 3 trials) ───
    N_TRIALS = 3
    for name in ("v1", "v3"):
        t = result["sets"][name]["ic_tstat"]
        n = result["sets"][name]["n_days"]
        if t == t and n > 2:
            p = 2 * stats.t.sf(abs(t), df=n - 1)
            result["sets"][name]["ic_p_naive"] = float(p)
            result["sets"][name]["ic_p_bonferroni_3trials"] = float(min(1.0, p * N_TRIALS))

    # ── OOS scoring of the single chosen candidate ──────────────────────────
    if args.oos_feature_set:
        _score_oos(result, args.oos_feature_set, ds, oos_s, oos_e, v1_cols, v3_cols)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2))
    print(f"\nWrote {OUT}")
    for name in ("v1", "v3"):
        s = result["sets"][name]
        print(f"  {name}: mean_ic={s['mean_ic']:+.4f} t={s['ic_tstat']:+.2f} "
              f"AUC={s['auc_mean']:.4f} Brier={s['brier_mean']:.4f} "
              f"spread={s['decile_spread']:+.4f} mono={s['decile_monotonicity']:+.2f}")


if __name__ == "__main__":
    main()
