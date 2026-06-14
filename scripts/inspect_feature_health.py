"""
inspect_feature_health.py — Atlas Feature Health Report.

Reads IC stats from feature_performance and pairwise correlations from
feature_snapshots_wide. Classifies every feature and writes recommendations
to feature_review_flags.

Does NOT delete or modify any features — recommendations only.

Usage
-----
    python scripts/inspect_feature_health.py
    python scripts/inspect_feature_health.py --model-version v1 --target label_return_5d
    python scripts/inspect_feature_health.py --no-db    # dry run, skip writing flags
    python scripts/inspect_feature_health.py --date 2026-06-14
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from atlas_research.features.health import (
    compute_feature_flags,
    write_flags,
    STRONG_MEAN_IC, USEFUL_MEAN_IC, WEAK_MEAN_IC,
    STRONG_TSTAT, USEFUL_TSTAT, WEAK_TSTAT,
    STRONG_STABILITY, DEGRADING_STABILITY, CORR_THRESHOLD,
)
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("inspect_feature_health")

CATEGORY_ORDER = ["strong", "useful", "weak", "degrading", "candidate_remove"]
CATEGORY_LABEL = {
    "strong":           "STRONG           [+]",
    "useful":           "USEFUL           [~]",
    "weak":             "WEAK             [x]",
    "degrading":        "DEGRADING        [!]",
    "candidate_remove": "CANDIDATE REMOVE [!]",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Feature Health Report")
    parser.add_argument("--model-version", default="v1",
                        help="Filter feature_performance by model_version (default v1)")
    parser.add_argument("--target", default="label_return_5d",
                        help="Target column to evaluate against (default label_return_5d)")
    parser.add_argument("--date", default=None,
                        help="Flag date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--no-db", action="store_true",
                        help="Dry run — compute but do not write to feature_review_flags")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    flag_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else date.today()
    )

    print(f"\nAtlas Feature Health Report")
    print(f"  Model version : {args.model_version}")
    print(f"  Target        : {args.target}")
    print(f"  Flag date     : {flag_date}")
    print(f"  Write to DB   : {'no (--no-db)' if args.no_db else 'yes'}")

    # ── Compute flags ──────────────────────────────────────────────────────
    print("\nComputing feature stats...")
    flags = compute_feature_flags(
        db_url, flag_date,
        model_version=args.model_version,
        target=args.target,
    )

    if not flags:
        print("\n[WARN] No IC data found in feature_performance.")
        print("       Run walk-forward validation first to populate IC stats.")
        print("       (scripts/run_walk_forward.py or equivalent)")
        _print_classification_rules()
        return

    # ── Write to DB ────────────────────────────────────────────────────────
    if not args.no_db:
        n = write_flags(db_url, flags)
        print(f"  Wrote {n} flags to feature_review_flags")

    # ── Print report ───────────────────────────────────────────────────────
    _print_report(flags)


SEP90 = "-" * 90
SEP86 = "-" * 86
SEP84 = "-" * 84


def _print_report(flags: list[dict]) -> None:
    flags_by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for f in flags:
        flags_by_cat.setdefault(f["category"], []).append(f)

    print("\n" + SEP90)
    print(f"  FEATURE HEALTH REPORT   ({len(flags)} features evaluated)")
    print(SEP90)
    print(
        f"  {'Feature':<32}  {'Category':<22}  {'IC':>7}  {'t-stat':>7}  "
        f"{'Stab':>6}  {'MaxCorr':>7}  {'Peer':<20}"
    )
    print("  " + SEP86)

    for cat in CATEGORY_ORDER:
        rows = sorted(flags_by_cat[cat], key=lambda x: -(x["mean_ic"] or 0))
        if not rows:
            continue
        dash = "-" * max(1, 50 - len(cat))
        print(f"\n  -- {CATEGORY_LABEL[cat]} ({dash})")
        for r in rows:
            ic_s   = f"{r['mean_ic']:+.4f}"       if r["mean_ic"]        is not None else "    n/a"
            t_s    = f"{r['ic_tstat']:+.2f}"      if r["ic_tstat"]       is not None else "   n/a"
            stab_s = f"{r['sign_stability']:.2f}" if r["sign_stability"] is not None else "  n/a"
            corr_s = f"{r['max_correlation']:.2f}" if r["max_correlation"] is not None else "    n/a"
            peer_s = (r["correlated_with"] or "")[:20]
            print(
                f"  {r['feature_name']:<32}  {cat:<22}  {ic_s:>7}  "
                f"{t_s:>7}  {stab_s:>6}  {corr_s:>7}  {peer_s:<20}"
            )

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n" + SEP90)
    print("  SUMMARY")
    print(SEP90)
    for cat in CATEGORY_ORDER:
        n = len(flags_by_cat[cat])
        label = cat.upper().replace("_", " ")
        names = ", ".join(f["feature_name"] for f in flags_by_cat[cat][:5])
        if n > 5:
            names += f" +{n-5} more"
        print(f"  {label:<20} {n:>3}  {names}")

    print()
    print("  RECOMMENDATIONS:")
    critical = flags_by_cat["candidate_remove"] + flags_by_cat["degrading"]
    if critical:
        print("  [!]  Review these features:")
        for f in critical:
            print(f"     {f['feature_name']:<32} -- {f['recommendation']}")
    else:
        print("  No critical issues found.")

    weak = flags_by_cat["weak"]
    if weak:
        low_ic = [f["feature_name"] for f in weak if (f["mean_ic"] or 0) < 0.005]
        if low_ic:
            print("\n  Low-IC features (IC < 0.005, may add noise):")
            for nm in low_ic:
                print(f"     {nm}")

    print()
    _print_classification_rules()


def _print_classification_rules() -> None:
    print("  CLASSIFICATION RULES:")
    print(f"    strong           IC >= {STRONG_MEAN_IC}  AND  t >= {STRONG_TSTAT}  AND  stability >= {STRONG_STABILITY}")
    print(f"    useful           IC >= {USEFUL_MEAN_IC}  AND  t >= {USEFUL_TSTAT}  AND  stability >= 0.50")
    print(f"    weak             IC <  {WEAK_MEAN_IC}   OR   t <  {WEAK_TSTAT}")
    print(f"    degrading        sign stability < {DEGRADING_STABILITY} (sign flips across folds)")
    print(f"    candidate_remove max pairwise corr >= {CORR_THRESHOLD} with a stronger feature")
    print()


if __name__ == "__main__":
    main()
