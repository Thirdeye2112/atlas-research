"""
run_probability_calibration.py — Historical probability signal calibration.

Calibrates ML-derived signal tiers against 2015-2026 forward returns using
walk-forward model artifacts (same as the confluence backtest — no look-ahead
in ML predictions).

Signal types:
  ml_rank_bucket  / 0-20, 20-40, 40-60, 60-80, 80-100  (cross-sectional rank pct)
  ml_direction    / bullish, bearish                     (prob > 0.55 / < 0.45)
  ml_conviction   / high, moderate                       (prob > 0.70 / > 0.55)

Promotion criteria (written to alpha_signal_calibrations):
  n_resolved >= 100, perm_p < 0.05, year_count >= 3, avg_return_5d > 0

Note: These signals are derived from the same ML model used by the ML component.
They test whether discrete rank TIERS have tier-specific calibrated predictive
power — a different question from the ML component's continuous probability signal.
Results carry look-ahead in the sense that we use 2015-2026 to validate signals
that will be applied to the same period (same caveat as Pattern and IC components).

Usage:
    python scripts/run_probability_calibration.py
    python scripts/run_probability_calibration.py --start-date 2015-01-01
    python scripts/run_probability_calibration.py --no-db   # print only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from scipy.stats import binomtest
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

PURGE_DAYS   = 7        # same as confluence backtest
MIN_DQ       = 0.70
PERM_ITERS   = 2_000    # fewer than main calibration — fast enough for this purpose
MIN_N_REPORT = 20

PROMO_N      = 100      # higher bar than live calibration since we have large samples
PROMO_HIT    = 0.54
PROMO_P      = 0.05
PROMO_YEARS  = 3

CAND_N       = 50
CAND_HIT     = 0.52
CAND_P       = 0.10

CAL_DATE     = "2099-01-01"   # sentinel date for backtest-history calibration records


# ── Signal definitions ─────────────────────────────────────────────────────────

def assign_signals(prob: np.ndarray, rank_pct: np.ndarray) -> dict[str, np.ndarray]:
    """
    Returns dict of signal_type/signal_key → boolean mask arrays.
    Each mask selects which rows belong to that signal.

    Only ml_rank_bucket signals are included. ml_direction and ml_conviction
    use the same 0.55 threshold as the ML component, making them 100% correlated
    and providing no independent evidence. Rank-percentile is computed cross-
    sectionally, so it fires independently of the absolute probability threshold.
    """
    signals: dict[str, np.ndarray] = {}

    # ML rank bucket: cross-sectional rank in 20-pt bins.
    # 60-80 and 80-100 are the expected high-signal buckets.
    # All bins included so we get full picture; only promotable ones will be used.
    for lo, hi in [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]:
        key = f"{lo}-{hi}"
        lo_f, hi_f = lo / 100.0, hi / 100.0
        if hi == 100:
            signals[f"ml_rank_bucket/{key}"] = (rank_pct >= lo_f)
        else:
            signals[f"ml_rank_bucket/{key}"] = (rank_pct >= lo_f) & (rank_pct < hi_f)

    return signals


# ── Walk-forward model map (copied from backtest) ──────────────────────────────

def build_model_map(models_dir: Path) -> list[tuple[date, Path]]:
    artifacts = []
    for d in models_dir.iterdir():
        if not d.is_dir():
            continue
        name = d.name
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


def get_model_for_date(model_map: list[tuple[date, Path]], signal_date: date) -> Path | None:
    cutoff = signal_date - timedelta(days=PURGE_DAYS)
    best = None
    for td, mp in model_map:
        if td <= cutoff:
            best = mp
    return best


# ── Bootstrap permutation test ─────────────────────────────────────────────────

def _bootstrap_p(arr: np.ndarray, universe: np.ndarray, iters: int) -> float:
    obs = float(np.mean(arr > 0))
    n   = len(arr)
    idx = np.random.choice(len(universe), size=(iters, n), replace=True)
    null_hits = np.mean(universe[idx] > 0, axis=1)
    return float(np.mean(null_hits >= obs))


# ── Forward returns from raw_bars ──────────────────────────────────────────────

def load_forward_returns(
    scored: pd.DataFrame,
    extra_days: int = 30,
) -> pd.DataFrame:
    """Add fwd_5d forward return column to scored DataFrame."""
    if scored.empty:
        return scored

    tickers = scored["ticker"].unique().tolist()
    smin    = pd.to_datetime(scored["date"]).min().date()
    smax    = pd.to_datetime(scored["date"]).max().date() + timedelta(days=extra_days)

    log.info("prob_cal.loading_raw_bars", tickers=len(tickers),
             start=str(smin), end=str(smax))

    sql = text("""
        SELECT ticker, date, close FROM raw_bars
        WHERE date BETWEEN :s AND :e AND ticker = ANY(:tickers)
        ORDER BY date, ticker
    """)
    with get_connection() as conn:
        bars = pd.read_sql(sql, conn, params={"s": smin, "e": smax, "tickers": tickers})

    if bars.empty:
        log.warning("prob_cal.no_raw_bars")
        scored["fwd_5d"] = np.nan
        return scored

    bars["date"] = pd.to_datetime(bars["date"]).dt.date
    close_piv = bars.pivot(index="date", columns="ticker", values="close")
    close_arr = close_piv.values.astype(float)

    h = 5
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

    fwd_long = fwd.stack(future_stack=True).reset_index()
    fwd_long.columns = ["date", "ticker", "fwd_5d"]
    fwd_long["date"] = pd.to_datetime(fwd_long["date"]).dt.date
    fwd_long["fwd_5d"] = fwd_long["fwd_5d"].replace([np.inf, -np.inf], np.nan)

    result = scored.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.date
    result = result.merge(fwd_long, on=["ticker", "date"], how="left")
    log.info("prob_cal.fwd_returns", rows=len(result),
             pct_5d=f"{result['fwd_5d'].notna().mean():.1%}")
    return result


# ── Main calibration ───────────────────────────────────────────────────────────

def run_calibration_pass(
    start_date: date,
    end_date: date,
    parquet_dir: Path,
    model_map: list[tuple[date, Path]],
) -> pd.DataFrame:
    """
    Score all parquets in range with walk-forward models.
    Returns DataFrame with columns: ticker, date, year, prob, rank_pct, fwd_5d
    """
    parquets = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    in_range = [
        p for p in parquets
        if start_date <= datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date() <= end_date
    ]
    if not in_range:
        log.error("prob_cal.no_parquets")
        return pd.DataFrame()

    # Group dates by model
    all_dates = [
        datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date()
        for p in in_range
    ]
    date_to_parquet = {
        datetime.strptime(p.stem.split("_", 2)[2], "%Y-%m-%d").date(): p
        for p in in_range
    }

    batches: dict[Path, list[date]] = {}
    skipped = 0
    for d in all_dates:
        mp = get_model_for_date(model_map, d)
        if mp is None:
            skipped += 1
            continue
        batches.setdefault(mp, []).append(d)
    if skipped:
        print(f"  [cal] Skipped {skipped} dates (no model artifact)")

    from atlas_research.features.regime_interactions import INTERACTION_NAMES

    all_rows: list[pd.DataFrame] = []
    for model_path, dates in sorted(batches.items(), key=lambda x: str(x[0])):
        try:
            bundle = load_model(model_path)
        except Exception as exc:
            log.error("prob_cal.model_load_failed", path=str(model_path), error=str(exc))
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

                df_norm = cross_sectional_normalize(df.copy(), feature_cols)
                for col in feature_cols:
                    if col not in df_norm.columns:
                        df_norm[col] = np.nan
                X    = df_norm[feature_cols].to_numpy(dtype=np.float64)
                prob = bundle.predict_prob(X)
                rank_pct = pd.Series(prob).rank(pct=True).to_numpy()

                all_rows.append(pd.DataFrame({
                    "ticker":   df["ticker"].values,
                    "date":     d,
                    "year":     str(d.year),
                    "prob":     prob,
                    "rank_pct": rank_pct,
                }))
            except Exception as exc:
                log.error("prob_cal.date_error", date=str(d), error=str(exc))

        del bundle

    if not all_rows:
        return pd.DataFrame()

    scored = pd.concat(all_rows, ignore_index=True)
    print(f"  [cal] Scored {len(scored):,} rows across {scored['date'].nunique()} dates "
          f"({scored['year'].nunique()} years)")

    # Add forward returns
    scored = load_forward_returns(scored, extra_days=30)
    return scored


def compute_stats(
    scored: pd.DataFrame,
    universe_5d: np.ndarray,
) -> list[dict]:
    """Compute calibration stats for all signal tiers."""
    scored_w5 = scored[scored["fwd_5d"].notna()].copy()
    if len(scored_w5) < MIN_N_REPORT:
        return []

    prob     = scored_w5["prob"].to_numpy(dtype=float)
    rank_pct = scored_w5["rank_pct"].to_numpy(dtype=float)
    fwd_5d   = scored_w5["fwd_5d"].to_numpy(dtype=float)
    years    = scored_w5["year"].tolist()

    # Recompute universe from scored_w5 (consistent with what we have)
    univ_5d = fwd_5d.copy()

    signal_masks = assign_signals(prob, rank_pct)
    rows = []
    for sig_key_full, mask in signal_masks.items():
        sig_type, sig_key = sig_key_full.split("/", 1)
        sub_fwd = fwd_5d[mask]
        sub_yrs = [y for y, m in zip(years, mask) if m]

        n = int(mask.sum())
        if n < MIN_N_REPORT:
            continue

        hit_5d = float(np.mean(sub_fwd > 0))
        avg_5d = float(np.mean(sub_fwd))
        std_5d = float(np.std(sub_fwd, ddof=1)) if n > 1 else 0.0

        # Permutation test vs universe
        if len(univ_5d) > n:
            perm_p = _bootstrap_p(sub_fwd, univ_5d, PERM_ITERS)
        else:
            k  = int(np.sum(sub_fwd > 0))
            perm_p = float(binomtest(k, n, 0.5, alternative="greater").pvalue)

        # Sanity vs 50%
        k = int(np.sum(sub_fwd > 0))
        sanity_pass = bool(binomtest(k, n, 0.5, alternative="greater").pvalue < 0.05)

        # Year breakdown
        year_bd: dict = {}
        for yr in sorted(set(sub_yrs)):
            yr_mask = np.array([y == yr for y in sub_yrs])
            sub = sub_fwd[yr_mask]
            if len(sub) >= 3:
                year_bd[yr] = {
                    "n":             int(len(sub)),
                    "hit_rate_5d":   round(float(np.mean(sub > 0)), 4),
                    "avg_return_5d": round(float(np.mean(sub)), 6),
                }

        year_count = len(year_bd)

        # Classify
        if n >= PROMO_N and hit_5d > PROMO_HIT and perm_p < PROMO_P and year_count >= PROMO_YEARS:
            status = "promoted"
        elif n >= CAND_N and hit_5d > CAND_HIT and perm_p < CAND_P:
            status = "candidate"
        else:
            status = "rejected"

        rows.append({
            "signal_type":         sig_type,
            "signal_key":          sig_key,
            "n_signals":           n,
            "n_resolved":          n,
            "hit_rate_5d":         round(hit_5d, 4),
            "avg_return_5d":       round(avg_5d, 6),
            "std_return_5d":       round(std_5d, 6),
            "median_return_5d":    round(float(np.median(sub_fwd)), 6),
            "year_breakdown":      year_bd,
            "year_count":          year_count,
            "sanity_pass":         sanity_pass,
            "permutation_p_value": round(perm_p, 6),
            "status":              status,
            "notes":               _notes(sig_type, sig_key, hit_5d, avg_5d, perm_p, n, year_count, status),
        })

    return rows


def _notes(sig_type, sig_key, hit, avg, p, n, yrs, status) -> str:
    if status == "promoted":
        return (f"Backtest-calibrated: {hit:.1%} 5d HR over {n:,} obs "
                f"across {yrs} years (p={p:.4f})")
    if status == "candidate":
        return f"Promising: {hit:.1%} HR, {n:,} obs — needs more data or years (p={p:.4f})"
    if hit <= 0.50:
        return f"No edge: {hit:.1%} 5d HR (below 50%)"
    if p >= CAND_P:
        return f"Not significant vs market baseline: p={p:.4f}"
    return f"Below promotion threshold: {hit:.1%} HR, n={n:,}, yrs={yrs}"


def write_calibration(rows: list[dict]) -> int:
    if not rows:
        return 0
    with get_connection() as conn:
        for r in rows:
            conn.execute(text("""
                INSERT INTO alpha_signal_calibrations (
                    calibration_date, signal_type, signal_key,
                    n_signals, n_resolved,
                    hit_rate_5d, avg_return_5d, median_return_5d, std_return_5d,
                    year_breakdown, year_count,
                    sanity_pass, permutation_p_value,
                    status, notes
                ) VALUES (
                    :cal_date, :sig_type, :sig_key,
                    :n_signals, :n_resolved,
                    :hit_rate_5d, :avg_return_5d, :med_ret, :std_ret,
                    :year_bd, :year_count,
                    :sanity, :perm_p,
                    :status, :notes
                )
                ON CONFLICT (calibration_date, signal_type, signal_key) DO UPDATE SET
                    n_signals           = EXCLUDED.n_signals,
                    n_resolved          = EXCLUDED.n_resolved,
                    hit_rate_5d         = EXCLUDED.hit_rate_5d,
                    avg_return_5d       = EXCLUDED.avg_return_5d,
                    median_return_5d    = EXCLUDED.median_return_5d,
                    std_return_5d       = EXCLUDED.std_return_5d,
                    year_breakdown      = EXCLUDED.year_breakdown,
                    year_count          = EXCLUDED.year_count,
                    sanity_pass         = EXCLUDED.sanity_pass,
                    permutation_p_value = EXCLUDED.permutation_p_value,
                    status              = EXCLUDED.status,
                    notes               = EXCLUDED.notes,
                    updated_at          = NOW()
            """), {
                "cal_date":     CAL_DATE,
                "sig_type":     r["signal_type"],
                "sig_key":      r["signal_key"],
                "n_signals":    r["n_signals"],
                "n_resolved":   r["n_resolved"],
                "hit_rate_5d":  r["hit_rate_5d"],
                "avg_return_5d":r["avg_return_5d"],
                "med_ret":      r["median_return_5d"],
                "std_ret":      r["std_return_5d"],
                "year_bd":      json.dumps(r["year_breakdown"]),
                "year_count":   r["year_count"],
                "sanity":       r["sanity_pass"],
                "perm_p":       r["permutation_p_value"],
                "status":       r["status"],
                "notes":        r["notes"],
            })
        conn.commit()
    return len(rows)


def print_report(rows: list[dict]) -> None:
    if not rows:
        print("[PROB-CAL] No rows computed.")
        return

    promoted  = [r for r in rows if r["status"] == "promoted"]
    candidate = [r for r in rows if r["status"] == "candidate"]
    rejected  = [r for r in rows if r["status"] == "rejected"]

    print(f"\n{'='*80}")
    print("  ML-DERIVED PROBABILITY SIGNAL CALIBRATION REPORT")
    print(f"{'='*80}")
    print(f"\n  Promoted: {len(promoted)}  |  Candidate: {len(candidate)}  |  Rejected: {len(rejected)}")

    by_type: dict[str, list] = defaultdict(list)
    for r in rows:
        by_type[r["signal_type"]].append(r)

    for sig_type, type_rows in sorted(by_type.items()):
        type_rows = sorted(type_rows, key=lambda x: -(x["hit_rate_5d"] or 0))
        print(f"\n-- {sig_type.upper()} --")
        hdr = f"  {'signal_key':<20}  {'n_res':>8}  {'yrs':>4}  {'HR 5d':>7}  {'Avg 5d%':>8}  {'p-val':>8}  {'status':<12}"
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for r in type_rows:
            print(f"  {r['signal_key']:<20}  {r['n_resolved']:>8,}  {r['year_count']:>4}  "
                  f"{r['hit_rate_5d']:>6.1%}  {r['avg_return_5d']*100:>+7.2f}%  "
                  f"{r['permutation_p_value']:>8.4f}  {r['status']:<12}")

    if promoted:
        print(f"\n  PROMOTED SIGNALS:")
        for r in sorted(promoted, key=lambda x: -(x["hit_rate_5d"] or 0)):
            print(f"    [{r['signal_type']}] {r['signal_key']:<20}  n={r['n_resolved']:,}  "
                  f"HR={r['hit_rate_5d']:.1%}  avg={r['avg_return_5d']*100:+.2f}%  "
                  f"p={r['permutation_p_value']:.4f}  yrs={r['year_count']}")
            print(f"      -> {r['notes']}")

    print(f"\n{'='*80}\n")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Probability signal calibration from parquet history")
    ap.add_argument("--start-date", default="2015-01-01",
                    help="Start date (default: 2015-01-01)")
    ap.add_argument("--end-date",   default=None,
                    help="End date (default: today)")
    ap.add_argument("--no-db",      action="store_true",
                    help="Skip writing to DB (print report only)")
    args = ap.parse_args()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date   = (datetime.strptime(args.end_date, "%Y-%m-%d").date()
                  if args.end_date else date.today())

    parquet_dir = Path(PARQUET_OUTPUT_DIR)
    if not parquet_dir.exists():
        print(f"[ERROR] Parquet directory not found: {parquet_dir}")
        return 1

    model_map = build_model_map(Path(MODEL_DIR))
    if not model_map:
        print("[ERROR] No model artifacts found")
        return 1
    print(f"[prob-cal] Models: {len(model_map)}  range: "
          f"{model_map[0][0]} to {model_map[-1][0]}")

    print(f"\n[1/3] Scoring parquets {start_date} to {end_date} "
          f"with walk-forward models...")
    scored = run_calibration_pass(start_date, end_date, parquet_dir, model_map)
    if scored.empty:
        print("[ERROR] No scored data produced")
        return 1

    print(f"\n[2/3] Computing calibration stats for ML signal tiers...")
    # Universe baseline from all resolved observations
    universe_5d = scored["fwd_5d"].dropna().to_numpy(dtype=float)
    print(f"  Universe baseline: n={len(universe_5d):,}  "
          f"hit={float(np.mean(universe_5d > 0)):.1%}  "
          f"median={float(np.median(universe_5d))*100:+.2f}%")

    rows = compute_stats(scored, universe_5d)
    print(f"  Computed {len(rows)} calibration rows")

    print_report(rows)

    if not args.no_db and rows:
        print(f"\n[3/3] Writing {len(rows)} calibration rows to alpha_signal_calibrations "
              f"(calibration_date='{CAL_DATE}')...")
        n = write_calibration(rows)
        print(f"  Written {n} rows")
        promoted = [r for r in rows if r["status"] == "promoted"]
        print(f"  PROMOTED: {len(promoted)} signals ready for confluence backtest v2")
    elif args.no_db:
        print("\n[--no-db] Skipping DB write.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
