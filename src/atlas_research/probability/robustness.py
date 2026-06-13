"""
atlas_research.probability.robustness
---------------------------------------
Evaluate whether a backtest result is robust enough to trust.

Four checks:
  1. Sample size        — N >= MIN_N events
  2. Multi-year         — at least MIN_YEARS distinct years
  3. Year dominance     — edge persists when best year is excluded
  4. Outlier sensitivity — edge persists after winsorizing at 5th/95th pct

Returns a RobustnessReport that parameter_search and promotion can consume.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

MIN_N          = 30
MIN_YEARS      = 3
WINSORIZE_PCT  = 5      # clip at 5th / 95th percentile


@dataclass
class RobustnessReport:
    passed: bool
    n_events: int
    year_count: int
    dominant_year: Optional[str]         # year whose removal kills the edge
    dominant_year_pct: Optional[float]   # fraction of events in that year
    outlier_impact: Optional[float]      # % change in avg after winsorization
    reasons_failed: list[str] = field(default_factory=list)
    score: float = 0.0                   # 0.0 – 1.0 (fraction of checks passed)


def check_robustness(events: list[dict], horizon: int = 5) -> RobustnessReport:
    """
    Evaluate a list of per-event outcome dicts (from compute_all_outcomes).

    Parameters
    ----------
    events  : list of dicts with 'signal_date', 'ret_Nd' keys
    horizon : which return horizon to evaluate (default 5d)
    """
    n = len(events)
    reasons: list[str] = []

    # ── 1. Sample size ────────────────────────────────────────────────────────
    if n < MIN_N:
        reasons.append(f"n={n} < {MIN_N}")

    # ── 2. Multi-year ─────────────────────────────────────────────────────────
    ret_key = f"ret_{horizon}d"

    years: dict[str, list[float]] = {}
    for e in events:
        sd = e.get("signal_date")
        ret = e.get(ret_key)
        if sd is None:
            continue
        yr = str(sd)[:4]
        if yr not in years:
            years[yr] = []
        if ret is not None:
            years[yr].append(float(ret))

    year_count = len(years)
    if year_count < MIN_YEARS:
        reasons.append(f"only {year_count} year(s) of data (need {MIN_YEARS})")

    # ── 3. Year dominance (leave-best-year-out) ───────────────────────────────
    dominant_year: Optional[str] = None
    dominant_year_pct: Optional[float] = None

    all_rets = [e.get(ret_key) for e in events if e.get(ret_key) is not None]
    global_avg = float(np.mean(all_rets)) if all_rets else 0.0

    if year_count >= 2 and all_rets and global_avg > 0:
        year_avgs = {
            y: float(np.mean(vs)) for y, vs in years.items() if vs
        }
        if year_avgs:
            best_yr = max(year_avgs, key=year_avgs.__getitem__)
            other_rets = [
                e.get(ret_key)
                for e in events
                if str(e.get("signal_date", ""))[:4] != best_yr
                and e.get(ret_key) is not None
            ]
            if other_rets:
                other_avg = float(np.mean(other_rets))
                best_yr_n = sum(
                    1 for e in events
                    if str(e.get("signal_date", ""))[:4] == best_yr
                )
                dominant_year_pct = best_yr_n / n if n else 0.0

                if other_avg <= 0:
                    dominant_year = best_yr
                    reasons.append(
                        f"edge collapses without {best_yr} "
                        f"({best_yr_n}/{n} events, other-years avg={other_avg:.2f}%)"
                    )

    # ── 4. Outlier sensitivity ────────────────────────────────────────────────
    outlier_impact: Optional[float] = None

    if len(all_rets) >= 10:
        arr = np.array(all_rets, dtype=float)
        raw_avg = float(np.mean(arr))
        p5, p95 = np.percentile(arr, [WINSORIZE_PCT, 100 - WINSORIZE_PCT])
        win_avg = float(np.mean(np.clip(arr, p5, p95)))

        if raw_avg != 0:
            outlier_impact = (win_avg - raw_avg) / abs(raw_avg) * 100

        if win_avg <= 0 < raw_avg:
            reasons.append(
                f"edge disappears after outlier removal "
                f"(raw avg={raw_avg:.2f}%, winsorized={win_avg:.2f}%)"
            )

    passed = len(reasons) == 0

    # Score = fraction of four checks passed
    checks = [
        n >= MIN_N,
        year_count >= MIN_YEARS,
        dominant_year is None,
        outlier_impact is None or outlier_impact > -50,
    ]
    score = round(sum(checks) / len(checks), 2)

    return RobustnessReport(
        passed=passed,
        n_events=n,
        year_count=year_count,
        dominant_year=dominant_year,
        dominant_year_pct=dominant_year_pct,
        outlier_impact=outlier_impact,
        reasons_failed=reasons,
        score=score,
    )
