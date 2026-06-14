"""
health.py — Feature health classification and review flag engine.

Reads from feature_performance (IC stats across walk-forward folds) and
feature_snapshots_wide (pairwise correlations). Classifies each feature
into a category and writes to feature_review_flags.

Categories (no auto-deletion — recommendations only):
    strong           High IC, stable sign, significant t-stat
    useful           Positive IC, adequate stability
    weak             Low IC or unstable across folds
    degrading        Sign frequently flips across folds
    candidate_remove Highly correlated with a stronger feature
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# ── Classification thresholds ────────────────────────────────────────────────

STRONG_MEAN_IC   = 0.03   # mean Spearman IC across folds
STRONG_TSTAT     = 2.0    # IC t-stat
STRONG_STABILITY = 0.60   # fraction of folds where IC > 0

USEFUL_MEAN_IC   = 0.01
USEFUL_TSTAT     = 1.0
USEFUL_STABILITY = 0.50

WEAK_MEAN_IC     = 0.01
WEAK_TSTAT       = 0.50

DEGRADING_STABILITY = 0.45   # < this → sign is unreliable

CORR_THRESHOLD   = 0.80   # pairwise Pearson correlation


class FeatureStats(NamedTuple):
    feature_name:    str
    mean_ic:         float | None
    ic_tstat:        float | None
    sign_stability:  float | None  # fraction of folds with IC > 0
    mean_rank_ic:    float | None
    n_folds:         int
    max_correlation: float | None
    correlated_with: str | None


def classify_feature(stats: FeatureStats, stronger_features: set[str]) -> tuple[str, str]:
    """
    Classify a feature into a review category.

    Args:
        stats:             Computed stats for this feature.
        stronger_features: Set of feature names classified as strong or useful
                           (used for candidate_remove logic).

    Returns:
        (category, recommendation)
    """
    mean_ic = stats.mean_ic or 0.0
    tstat   = stats.ic_tstat or 0.0
    stab    = stats.sign_stability or 0.5
    corr    = stats.max_correlation or 0.0
    peer    = stats.correlated_with

    # Order matters: check most severe conditions first.

    if stab < DEGRADING_STABILITY:
        rec = (
            f"Sign flips in {(1-stab)*100:.0f}% of folds. "
            "Investigate regime dependency before using."
        )
        return "degrading", rec

    if corr >= CORR_THRESHOLD and peer and peer in stronger_features:
        rec = (
            f"Correlation={corr:.2f} with {peer} (which is stronger). "
            "Removing may reduce multicollinearity without losing alpha."
        )
        return "candidate_remove", rec

    if mean_ic >= STRONG_MEAN_IC and tstat >= STRONG_TSTAT and stab >= STRONG_STABILITY:
        rec = f"Strong alpha signal. IC={mean_ic:.4f}, t={tstat:.2f}. Keep."
        return "strong", rec

    if mean_ic >= USEFUL_MEAN_IC and tstat >= USEFUL_TSTAT and stab >= USEFUL_STABILITY:
        rec = f"Useful signal. IC={mean_ic:.4f}, t={tstat:.2f}. Keep."
        return "useful", rec

    rec = (
        f"Low IC={mean_ic:.4f}, t={tstat:.2f}. "
        "Consider removing if correlated with a stronger feature."
    )
    return "weak", rec


def compute_feature_flags(
    db_url: str,
    flag_date: date,
    model_version: str = "v1",
    target: str = "label_return_5d",
    min_folds: int = 1,
) -> list[dict]:
    """
    Load IC stats from feature_performance, compute pairwise correlations from
    feature_snapshots_wide, classify each feature, return list of flag dicts.

    Args:
        db_url:        Connection string for atlas_research DB.
        flag_date:     Date to stamp the flags (today).
        model_version: Filter feature_performance by model_version.
        target:        Filter feature_performance by target column.
        min_folds:     Features with fewer folds are included but flagged.

    Returns:
        List of dicts ready for write_flags().
    """
    # ── Load IC stats ──────────────────────────────────────────────────────
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT feature_name,
                       AVG(spearman_ic)                                AS mean_ic,
                       AVG(ic_tstat)                                   AS ic_tstat,
                       STDDEV(spearman_ic)                             AS ic_std,
                       COUNT(*)                                        AS n_folds,
                       SUM(CASE WHEN spearman_ic > 0 THEN 1 ELSE 0 END)::float
                           / NULLIF(COUNT(*), 0)                       AS sign_stability,
                       AVG(mean_ic)                                    AS mean_rank_ic
                FROM feature_performance
                WHERE model_version = %s AND target = %s
                GROUP BY feature_name
            """, (model_version, target))
            ic_rows = cur.fetchall()
            ic_cols = [d[0] for d in cur.description]
    ic_df = pd.DataFrame(ic_rows, columns=ic_cols)

    if ic_df.empty:
        log.warning("feature_health.no_ic_data",
                    model_version=model_version, target=target)
        return []

    # ── Load latest wide rows for correlation matrix ──────────────────────
    corr_map: dict[str, tuple[float, str | None]] = {}

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(date) FROM feature_snapshots_wide
            """)
            row = cur.fetchone()
            latest_date = row[0] if row else None

    if latest_date is not None:
        from atlas_research.exports.wide_export import WIDE_FEATURES
        feat_cols = [f for f in WIDE_FEATURES if f not in
                     ("quality_tier", "jarvis_quality_adjusted", "data_quality_score")]
        select = ", ".join(feat_cols)
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {select} FROM feature_snapshots_wide WHERE date = %s",
                    (latest_date,)
                )
                wide_rows = cur.fetchall()
                wide_cols = [d[0] for d in cur.description]
        wide_df = pd.DataFrame(wide_rows, columns=wide_cols)

        if not wide_df.empty and len(wide_df) > 10:
            corr_matrix = wide_df.corr(method="pearson", numeric_only=True).abs()
            ic_names = set(ic_df["feature_name"].tolist())
            for feat in ic_names:
                if feat not in corr_matrix.columns:
                    continue
                col = corr_matrix[feat].drop(index=feat, errors="ignore")
                col = col[col.index.isin(ic_names)]
                if col.empty:
                    continue
                max_corr = float(col.max())
                peer = col.idxmax() if max_corr >= CORR_THRESHOLD else None
                corr_map[feat] = (max_corr, peer)

    # ── Classify ───────────────────────────────────────────────────────────
    # Build strong/useful set for candidate_remove logic (two passes)
    rows: list[dict] = []
    stats_list: list[FeatureStats] = []

    for _, r in ic_df.iterrows():
        fname = r["feature_name"]
        max_c, peer = corr_map.get(fname, (None, None))
        stats_list.append(FeatureStats(
            feature_name    = fname,
            mean_ic         = _f(r["mean_ic"]),
            ic_tstat        = _f(r["ic_tstat"]),
            sign_stability  = _f(r["sign_stability"]),
            mean_rank_ic    = _f(r["mean_rank_ic"]),
            n_folds         = int(r["n_folds"]),
            max_correlation = max_c,
            correlated_with = peer,
        ))

    # First pass: identify strong/useful features
    stronger: set[str] = set()
    for st in stats_list:
        mean_ic = st.mean_ic or 0.0
        tstat   = st.ic_tstat or 0.0
        stab    = st.sign_stability or 0.5
        if (mean_ic >= STRONG_MEAN_IC and tstat >= STRONG_TSTAT and stab >= STRONG_STABILITY):
            stronger.add(st.feature_name)
        elif (mean_ic >= USEFUL_MEAN_IC and tstat >= USEFUL_TSTAT and stab >= USEFUL_STABILITY):
            stronger.add(st.feature_name)

    # Second pass: classify with peer context
    for st in stats_list:
        cat, rec = classify_feature(st, stronger)
        rows.append({
            "flag_date":       flag_date,
            "feature_name":    st.feature_name,
            "category":        cat,
            "mean_ic":         st.mean_ic,
            "ic_tstat":        st.ic_tstat,
            "sign_stability":  st.sign_stability,
            "mean_rank_ic":    st.mean_rank_ic,
            "max_correlation": st.max_correlation,
            "correlated_with": st.correlated_with,
            "n_folds":         st.n_folds,
            "recommendation":  rec,
        })

    log.info("feature_health.flags_computed",
             n_features=len(rows), flag_date=str(flag_date))
    return rows


def write_flags(db_url: str, flags: list[dict]) -> int:
    """Upsert feature_review_flags rows. Returns number of rows written."""
    if not flags:
        return 0

    sql = """
        INSERT INTO feature_review_flags
            (flag_date, feature_name, category, mean_ic, ic_tstat,
             sign_stability, mean_rank_ic, max_correlation, correlated_with,
             n_folds, recommendation)
        VALUES
            (%(flag_date)s, %(feature_name)s, %(category)s, %(mean_ic)s,
             %(ic_tstat)s, %(sign_stability)s, %(mean_rank_ic)s,
             %(max_correlation)s, %(correlated_with)s, %(n_folds)s,
             %(recommendation)s)
        ON CONFLICT (flag_date, feature_name) DO UPDATE SET
            category        = EXCLUDED.category,
            mean_ic         = EXCLUDED.mean_ic,
            ic_tstat        = EXCLUDED.ic_tstat,
            sign_stability  = EXCLUDED.sign_stability,
            mean_rank_ic    = EXCLUDED.mean_rank_ic,
            max_correlation = EXCLUDED.max_correlation,
            correlated_with = EXCLUDED.correlated_with,
            n_folds         = EXCLUDED.n_folds,
            recommendation  = EXCLUDED.recommendation,
            created_at      = now()
    """

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, sql, flags, page_size=200)
        conn.commit()

    return len(flags)


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        fv = float(v)
        return None if (fv != fv) else fv  # NaN check
    except (TypeError, ValueError):
        return None
