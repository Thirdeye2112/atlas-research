"""
Attribution report writer — generates PREDICTION_ERROR_ATTRIBUTION_REPORT.md.

Sections:
  1. Summary (total predictions, hit rate, breakdown by horizon)
  2. Where Atlas was right (top performing conditions)
  3. Where Atlas was wrong (failure class distribution)
  4. Signal reliability trends (improving vs degrading)
  5. Regime analysis (which regimes cause failures)
  6. Adaptive weighting recommendations
  7. Raw data tables (conviction level, regime breakdowns)
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from atlas_research.attribution import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

_REPORT_PATH = Path(__file__).resolve().parents[4] / "reports" / "PREDICTION_ERROR_ATTRIBUTION_REPORT.md"


def write_attribution_report(
    end_date: date | None = None,
    lookback_days: int = 180,
    horizon_days: int = 5,
    out_path: Path | None = None,
) -> Path:
    """
    Generate the full attribution report and write it to reports/.

    Parameters
    ----------
    end_date     : reporting end date (default today)
    lookback_days: how many days of data to include (default 180)
    horizon_days : which horizon to report on (default 5)
    out_path     : override output path (default reports/PREDICTION_ERROR_ATTRIBUTION_REPORT.md)

    Returns
    -------
    Path to the written report.
    """
    if end_date is None:
        end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    out_path   = out_path or _REPORT_PATH

    # ── Load data ──────────────────────────────────────────────────────────────
    outcomes_df  = repository.get_prediction_outcomes_df(start_date, end_date, horizon_days)
    failure_df   = repository.get_attribution_summary(start_date, end_date, horizon_days)
    reliability  = repository.get_reliability_snapshot(window_days=90, horizon_days=horizon_days)
    recommendations = repository.get_all_recommendations(days_back=30)

    # Group stats
    by_conviction = repository.get_outcome_stats_by_group("conviction_level", start_date, end_date, horizon_days)
    by_regime     = repository.get_outcome_stats_by_group("regime", start_date, end_date, horizon_days)
    by_direction  = repository.get_outcome_stats_by_group("predicted_direction", start_date, end_date, horizon_days)

    lines = _build_report(
        start_date, end_date, horizon_days, lookback_days,
        outcomes_df, failure_df, reliability, recommendations,
        by_conviction, by_regime, by_direction,
    )

    report = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    log.info("attribution.report.written", path=str(out_path), n_outcomes=len(outcomes_df))
    return out_path


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def _build_report(
    start_date: date,
    end_date: date,
    horizon_days: int,
    lookback_days: int,
    outcomes_df: pd.DataFrame,
    failure_df: pd.DataFrame,
    reliability: pd.DataFrame,
    recommendations: pd.DataFrame,
    by_conviction: pd.DataFrame,
    by_regime: pd.DataFrame,
    by_direction: pd.DataFrame,
) -> list[str]:

    total = len(outcomes_df)
    if total == 0:
        return ["# Atlas Prediction Error Attribution Report", "",
                "> No matured predictions in the reporting window yet.",
                "> Run the attribution pipeline after outcomes have matured (horizon elapsed).", ""]

    n_hits   = int(outcomes_df["hit_or_miss"].sum())
    n_misses = total - n_hits
    hit_rate = n_hits / total if total else 0
    avg_ret  = float(outcomes_df["actual_return"].mean()) if not outcomes_df.empty else float("nan")

    lines: list[str] = [
        "# Atlas Prediction Error Attribution Report",
        f"**Period:** {start_date} to {end_date}  |  **Horizon:** {horizon_days}d",
        f"**Generated:** {date.today()}",
        "",
        "> **What is this?** A closed-loop analysis of every Atlas confluence prediction",
        "> vs its realized outcome. Shows where Atlas is right, wrong, and why,",
        "> and what to do about it.",
        "> Recommendations require human review before any weight changes.",
        "",
        "---",
        "",
        "## 1. Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total matured predictions | {total:,} |",
        f"| Correct (hit) | {n_hits:,} ({_pct(hit_rate)}) |",
        f"| Wrong (miss) | {n_misses:,} ({_pct(1-hit_rate)}) |",
        f"| Avg actual return | {_ret(avg_ret)} |",
        f"| Reporting window | {lookback_days} days |",
        f"| Prediction horizon | {horizon_days} days |",
        "",
    ]

    # ── Section 2: Where Atlas was right ─────────────────────────────────────
    lines += [
        "---",
        "",
        "## 2. Where Atlas Was Right",
        "",
    ]

    if not by_conviction.empty:
        lines += [
            "### By Conviction Level",
            "",
            _table(by_conviction, ["grp", "n", "hit_rate", "avg_return"],
                   ["Level", "N", "HR 5d", "Avg 5d"]),
            "",
        ]

    if not by_direction.empty:
        lines += [
            "### By Predicted Direction",
            "",
            _table(by_direction, ["grp", "n", "hit_rate", "avg_return"],
                   ["Direction", "N", "HR 5d", "Avg 5d"]),
            "",
        ]

    # Top 5 correct conditions (conviction VERY_HIGH hits)
    top_hits = outcomes_df[
        (outcomes_df["hit_or_miss"] == True) &
        (outcomes_df["conviction_level"] == "VERY_HIGH")
    ]
    if not top_hits.empty:
        lines += [
            "### Best Condition: VERY_HIGH Conviction Hits",
            f"- n={len(top_hits):,}  |  hit_rate=100% (by definition)  |  avg_return={_ret(top_hits['actual_return'].mean())}",
            f"- avg_runup={_ret(top_hits['max_runup'].mean())}  |  avg_drawdown={_ret(top_hits['max_drawdown'].mean())}",
            "",
        ]

    # ── Section 3: Where Atlas was wrong ─────────────────────────────────────
    lines += [
        "---",
        "",
        "## 3. Where Atlas Was Wrong",
        "",
        "### Failure Class Distribution",
        "",
    ]

    if failure_df.empty:
        lines += ["> No failure classifications computed yet.", ""]
    else:
        lines += [
            "| Failure Class | N | Misses | Avg Confidence |",
            "|---------------|---|--------|----------------|",
        ]
        for _, row in failure_df.iterrows():
            lines.append(
                f"| {row['failure_class']} | {_n(row['n_total'])} | "
                f"{_n(row['n_misses'])} | {_pct(_f(row['avg_confidence']))} |"
            )
        lines += [
            "",
            "**Failure class definitions:**",
            "- `correct` — prediction was right",
            "- `event_gap` — unexpected large price gap (news/earnings); hard to predict",
            "- `model_overconfidence` — ML assigned >70% probability but was wrong",
            "- `regime_mismatch` — market environment contradicted the signal direction",
            "- `conflicting_signal_ignored` — 2+ conflicting signals present at prediction time",
            "- `weak_confluence` — score <40 or LOW conviction; prediction was low-quality",
            "- `momentum_exhaustion` — stock was overbought/oversold at prediction (RSI)",
            "- `mean_reversion_failure` — predicted reversal against strong trend that continued",
            "- `low_liquidity_failure` — volume <50% of ADV; noise dominated signal",
            "- `unknown` — does not fit the above patterns",
            "",
        ]

    # ── Section 4: Signal Reliability ────────────────────────────────────────
    lines += [
        "---",
        "",
        "## 4. Signal Reliability (90-Day Rolling Window)",
        "",
    ]

    if reliability.empty:
        lines += ["> No reliability scores computed yet. Run the attribution pipeline.", ""]
    else:
        improving  = reliability[reliability["trend"] == "improving"]["component_name"].tolist()
        degrading  = reliability[reliability["trend"] == "degrading"]["component_name"].tolist()
        stable     = reliability[reliability["trend"] == "stable"]["component_name"].tolist()

        lines += [
            f"**Improving signals:** {', '.join(improving) or 'none'}",
            f"**Degrading signals:** {', '.join(degrading) or 'none'}",
            f"**Stable signals:** {', '.join(stable) or 'none'}",
            "",
            "### Hit Rate by Component (90d, direction=all)",
            "",
            "| Component | N | Hit Rate | Avg Return | IC | Trend |",
            "|-----------|---|----------|------------|----|----|",
        ]
        for _, row in reliability.iterrows():
            lines.append(
                f"| {row['component_name']} | {_n(row['n_predictions'])} | "
                f"{_pct(_f(row['hit_rate']))} | {_ret(_f(row['avg_return']))} | "
                f"{_ic(_f(row['ic']))} | {row['trend'] or 'stable'} |"
            )
        lines += [""]

    # ── Section 5: Regime Analysis ────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## 5. Regime Analysis",
        "",
        "Which regimes are causing the most failures?",
        "",
    ]

    if by_regime.empty:
        lines += ["> No regime data available.", ""]
    else:
        lines += [
            _table(by_regime, ["grp", "n", "hit_rate", "avg_return", "avg_drawdown"],
                   ["Regime", "N", "HR 5d", "Avg 5d", "Avg DD"]),
            "",
        ]
        worst = by_regime[by_regime["n"] >= 20].nsmallest(1, "hit_rate")
        if not worst.empty:
            w = worst.iloc[0]
            lines += [
                f"> Worst regime: **{w['grp']}** — HR={_pct(_f(w['hit_rate']))}, "
                f"n={_n(w['n'])}, avg_return={_ret(_f(w['avg_return']))}",
                "",
            ]

    # ── Section 6: Adaptive Recommendations ──────────────────────────────────
    lines += [
        "---",
        "",
        "## 6. Adaptive Weighting Recommendations",
        "",
        "> **Important:** Recommendations are advisory only. No production weights",
        "> are changed automatically. Each recommendation must be explicitly promoted",
        "> via `POST /api/research/adaptive-recommendations/{id}/promote`.",
        "",
    ]

    if recommendations.empty:
        lines += ["> No pending recommendations.", ""]
    else:
        pending = recommendations[recommendations["status"] == "pending"]
        promoted = recommendations[recommendations["status"] == "promoted"]
        rejected = recommendations[recommendations["status"] == "rejected"]

        lines += [
            f"**Pending:** {len(pending)}  |  **Promoted:** {len(promoted)}  |  "
            f"**Rejected:** {len(rejected)}",
            "",
        ]

        if not pending.empty:
            urgent = pending[pending["priority"] == "urgent"]
            if not urgent.empty:
                lines += ["### Urgent Recommendations", ""]
                for _, row in urgent.iterrows():
                    lines += _format_recommendation(row)

            normal = pending[pending["priority"] == "normal"]
            if not normal.empty:
                lines += ["### Normal Recommendations", ""]
                for _, row in normal.iterrows():
                    lines += _format_recommendation(row)

        if not promoted.empty:
            lines += ["### Recently Promoted", ""]
            for _, row in promoted.head(5).iterrows():
                lines.append(
                    f"- **{row['component_name']}** `{row['recommendation']}` "
                    f"(promoted {row['promoted_at'] or 'n/a'})"
                )
            lines += [""]

    # ── Section 7: Raw tables ─────────────────────────────────────────────────
    lines += [
        "---",
        "",
        "## 7. Appendix: Detailed Outcome Tables",
        "",
        "### Conviction Level Breakdown",
        "",
        _table(by_conviction,
               ["grp", "n", "n_hits", "hit_rate", "avg_return", "avg_runup", "avg_drawdown"],
               ["Level", "N", "Hits", "HR 5d", "Avg 5d", "Avg Runup", "Avg DD"]),
        "",
        "### Regime Breakdown",
        "",
        _table(by_regime,
               ["grp", "n", "n_hits", "hit_rate", "avg_return", "avg_runup", "avg_drawdown"],
               ["Regime", "N", "Hits", "HR 5d", "Avg 5d", "Avg Runup", "Avg DD"]),
        "",
        "---",
        "",
        "## 8. Next Steps",
        "",
        "1. Review pending adaptive recommendations in Section 6 above.",
        "2. For each `urgent` recommendation, verify the evidence in the DB:",
        "   `SELECT * FROM signal_reliability_scores WHERE component_name = 'X' ORDER BY computed_date DESC LIMIT 5`",
        "3. To promote a recommendation: `POST /api/research/adaptive-recommendations/{id}/promote`",
        "4. To reject: `POST /api/research/adaptive-recommendations/{id}/reject`",
        "5. After promoting, update the component weight in `src/atlas_research/confluence/components/{name}.py`",
        "   and re-run the confluence backtest to verify the change improves performance.",
        "",
    ]

    return lines


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _pct(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.1%}"


def _ret(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:+.3%}"


def _ic(v: float | None) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "n/a"
    return f"{v:.3f}"


def _n(v: Any) -> str:
    if v is None:
        return "n/a"
    try:
        return f"{int(v):,}"
    except (TypeError, ValueError):
        return str(v)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _table(df: pd.DataFrame, cols: list[str], headers: list[str]) -> str:
    if df.empty:
        return "> No data."
    formatters: dict[str, Any] = {}
    rows: list[str] = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for _, row in df.iterrows():
        cells = []
        for col in cols:
            v = row.get(col)
            if col in ("hit_rate",):
                cells.append(_pct(_f(v)))
            elif col in ("avg_return", "avg_runup", "avg_drawdown"):
                cells.append(_ret(_f(v)))
            elif col in ("n", "n_hits", "n_misses"):
                cells.append(_n(v))
            else:
                cells.append(str(v) if v is not None else "n/a")
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _format_recommendation(row: pd.Series) -> list[str]:
    ev = row.get("evidence") or {}
    if isinstance(ev, str):
        import json
        try:
            ev = json.loads(ev)
        except Exception:
            ev = {}
    hr    = _pct(_f(ev.get("hit_rate")))
    base  = _pct(_f(ev.get("baseline_hr")))
    delta = ev.get("delta")
    delta_str = f"{delta:+.1%}" if delta is not None and not math.isnan(float(delta)) else "n/a"
    n_str = _n(ev.get("n"))
    return [
        f"**{row['component_name']}** — `{row['recommendation']}`",
        f"- Current weight: {row['current_weight']}  "
        f"Suggested: {row['suggested_weight']}",
        f"- HR={hr} ({delta_str} vs baseline={base}), n={n_str}",
        f"- {row['rationale']}",
        "",
    ]
