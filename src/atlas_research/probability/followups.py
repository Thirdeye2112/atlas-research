"""
atlas_research.probability.followups
--------------------------------------
Auto-generate regime-filtered follow-up questions from a base condition.

For a base condition like "SPY down streak N=4", generates:
  - SPY down 4d + above 200DMA
  - SPY down 4d + below 200DMA

These are compound conditions: base_mask AND modifier_mask.
Results are computed in-memory (not saved by default — call save_followup_spec
to persist).
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from .engine import load_bars, detect_condition
from .outcomes import compute_all_outcomes, stats_by_horizon
from .robustness import check_robustness


# ── Regime filter detectors ───────────────────────────────────────────────────

def detect_above_200dma(df: pd.DataFrame, min_periods: int = 100) -> pd.Series:
    """True when close is above its 200-day simple moving average."""
    sma = df["close"].rolling(200, min_periods=min_periods).mean()
    return (df["close"] > sma).fillna(False)


def detect_below_200dma(df: pd.DataFrame, min_periods: int = 100) -> pd.Series:
    """True when close is below its 200-day simple moving average."""
    sma = df["close"].rolling(200, min_periods=min_periods).mean()
    return (df["close"] < sma).fillna(False)


def detect_high_vix(df: pd.DataFrame, threshold: float = 20.0) -> pd.Series:
    """
    True on dates where VIX closed above threshold.
    Loads ^VIX from raw_bars.  Returns all-False Series if VIX not available.
    """
    try:
        from atlas_research.db.connection import get_connection
        from sqlalchemy import text

        with get_connection() as conn:
            rows = conn.execute(text(
                "SELECT date, close FROM raw_bars WHERE ticker = '^VIX' ORDER BY date"
            )).fetchall()

        if not rows:
            return pd.Series(False, index=df.index)

        vix = pd.Series(
            {pd.Timestamp(r[0]): float(r[1]) for r in rows},
            name="vix",
        )
        vix = vix.reindex(df.index).ffill()
        return (vix > threshold).fillna(False)
    except Exception:
        return pd.Series(False, index=df.index)


# ── Modifier catalogue ────────────────────────────────────────────────────────

MODIFIERS: dict[str, callable] = {
    "above_200dma": detect_above_200dma,
    "below_200dma": detect_below_200dma,
    "vix_above_20": lambda df: detect_high_vix(df, threshold=20.0),
}

MODIFIER_LABELS: dict[str, str] = {
    "above_200dma": "above 200DMA",
    "below_200dma": "below 200DMA",
    "vix_above_20": "VIX > 20",
}


# ── Core follow-up engine ─────────────────────────────────────────────────────

def _base_label(condition_type: str, params: dict) -> str:
    if condition_type in ("down_streak", "up_streak"):
        direction = "down" if "down" in condition_type else "up"
        return f"down {params['n']}d" if "down" in condition_type else f"up {params['n']}d"
    if condition_type in ("gap_down", "gap_up"):
        direction = "gap down" if "down" in condition_type else "gap up"
        return f"{direction} {params.get('threshold_pct', 0.5)}%"
    return condition_type


def generate_followup_results(
    ticker: str,
    condition_type: str,
    params: dict,
    df: Optional[pd.DataFrame] = None,
    modifiers: Optional[list[str]] = None,
) -> list[dict]:
    """
    Compute in-memory results for each modifier variant of a base condition.

    Parameters
    ----------
    ticker          : ticker symbol
    condition_type  : e.g. 'down_streak'
    params          : condition params dict e.g. {'n': 4}
    df              : pre-loaded DataFrame (loads from DB if None)
    modifiers       : which modifiers to run (defaults to all in MODIFIERS)

    Returns list of dicts, one per modifier, each with:
        modifier, label, base_n, compound_n, stats, robustness
    """
    if df is None:
        df = load_bars(ticker)
    if df.empty:
        return []

    base_mask  = detect_condition(df, condition_type, params)
    base_label = _base_label(condition_type, params)

    if modifiers is None:
        modifiers = list(MODIFIERS.keys())

    results: list[dict] = []

    for mod_key in modifiers:
        mod_fn = MODIFIERS.get(mod_key)
        if mod_fn is None:
            continue

        mod_mask     = mod_fn(df)
        compound     = base_mask & mod_mask
        events       = compute_all_outcomes(df, compound, ticker=ticker)
        stats        = stats_by_horizon(events)
        robustness   = check_robustness(events, horizon=5) if len(events) >= 5 else None

        results.append({
            "modifier":    mod_key,
            "label":       f"{ticker} {base_label} + {MODIFIER_LABELS[mod_key]}",
            "base_n":      int(base_mask.sum()),
            "compound_n":  len(events),
            "stats":       stats,
            "robustness":  robustness,
        })

    return results


# ── Console output ────────────────────────────────────────────────────────────

def _pct(v, sign: bool = True) -> str:
    if v is None:
        return " N/A"
    s = "+" if sign and v > 0 else ""
    return f"{s}{v:.1f}%"


def _hr(v) -> str:
    if v is None:
        return " N/A"
    return f"{v*100:.1f}%"


def print_followup_results(base_label: str, results: list[dict]) -> None:
    """Print a compact table of follow-up variant results."""
    if not results:
        return

    print(f"  Follow-ups for: {base_label}")
    print(f"  {'Variant':<38}  {'N':>4}  {'Hit5d':>6}  {'Avg5d':>6}  {'Hit20d':>6}  {'Avg20d':>7}")
    print("  " + "-" * 74)

    for r in results:
        s5  = r["stats"].get(5,  {})
        s20 = r["stats"].get(20, {})
        n   = r["compound_n"]
        label = r["label"]

        # Suppress if too few events
        if n < 5:
            print(f"  {label:<38}  {n:>4}  (insufficient data)")
            continue

        print(
            f"  {label:<38}  {n:>4}  "
            f"{_hr(s5.get('hit_rate')):>6}  "
            f"{_pct(s5.get('avg_return')):>6}  "
            f"{_hr(s20.get('hit_rate')):>6}  "
            f"{_pct(s20.get('avg_return')):>7}"
        )
    print()
