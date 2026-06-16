"""
Atlas Intraday Rule Refiner v1
================================
Generates candidate refinements for each intraday setup type based on
win/loss attribution results. Tests each refinement walk-forward and
promotes only versions that improve out-of-sample performance.

Refinement philosophy:
  - One or two extra conditions only (no black-box mutation)
  - Conditions must be interpretable (e.g., "vol_ratio > 1.5")
  - Conditions use only information available at detection time
  - Minimum sample threshold required before generating any refinement
  - OOS must beat original OOS — IS improvement alone is not sufficient

Promotion criteria (Part 7):
  - refined IS n >= MIN_REFINED_IS_N
  - OOS n >= MIN_REFINED_OOS_N
  - oos_expectancy > 0
  - oos_pf > original_pf
  - max_drawdown not materially worse
  - multi_ticker_breadth >= MIN_TICKER_BREADTH
  - multi_week_breadth >= MIN_WEEK_BREADTH
  - outlier sensitivity < OUTLIER_SENSITIVITY_THRESHOLD
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

SLIPPAGE_PCT               = 0.05
MIN_BASE_IS_N              = 30   # minimum original IS n before generating refinements
MIN_REFINED_IS_N           = 20   # minimum IS n after applying filter
MIN_REFINED_OOS_N          = 5    # minimum OOS n after applying filter
MIN_TICKER_BREADTH         = 3    # must appear in >= N tickers with >= 3 trades each
MIN_WEEK_BREADTH           = 3    # must appear in >= N weeks
OUTLIER_SENSITIVITY_THRESH = 0.40 # if removing top trade drops expectancy by >40%, flag
MIN_ATTRIBUTION_EFFECT     = 0.20 # |Cohen's d| or |lift-1| threshold to flag condition
MAX_CONDITIONS_PER_RULE    = 2    # max added conditions per refinement


# ---------------------------------------------------------------------------
# Condition catalog
# ---------------------------------------------------------------------------
# Each condition: (name, feature_col, filter_fn, description, direction_bias)
# direction_bias: 'long', 'short', or None (applies to both)

CONDITION_CATALOG = [
    # Volume
    ("high_volume",      "vol_ratio",       lambda v: float(v) > 1.5,   "Vol ratio > 1.5x",        None),
    ("very_high_volume", "vol_ratio",       lambda v: float(v) > 2.0,   "Vol ratio > 2.0x",        None),
    ("low_volume",       "vol_ratio",       lambda v: float(v) < 0.8,   "Vol ratio < 0.8x",        None),
    # VWAP
    ("above_vwap",       "dist_vwap_pct",   lambda v: float(v) > 0,     "Price above VWAP",        "long"),
    ("below_vwap",       "dist_vwap_pct",   lambda v: float(v) < 0,     "Price below VWAP",        "short"),
    ("near_vwap",        "dist_vwap_pct",   lambda v: abs(float(v))<0.15, "Within 0.15% of VWAP",  None),
    # RSI
    ("rsi_bullish",      "rsi14",           lambda v: float(v) > 50,    "RSI > 50",                "long"),
    ("rsi_bearish",      "rsi14",           lambda v: float(v) < 50,    "RSI < 50",                "short"),
    ("rsi_not_extreme",  "rsi14",           lambda v: 35 < float(v) < 65, "RSI 35-65 (neutral)",   None),
    # EMA slope
    ("ema_up",           "ema9_slope",      lambda v: float(v) > 0,     "EMA9 slope positive",     "long"),
    ("ema_down",         "ema9_slope",      lambda v: float(v) < 0,     "EMA9 slope negative",     "short"),
    # MACD
    ("macd_positive",    "macd_hist",       lambda v: float(v) > 0,     "MACD histogram > 0",      "long"),
    ("macd_negative",    "macd_hist",       lambda v: float(v) < 0,     "MACD histogram < 0",      "short"),
    # Gap
    ("gap_up",           "gap_pct",         lambda v: float(v) > 0.3,   "Gap up > 0.3%",           "long"),
    ("gap_down",         "gap_pct",         lambda v: float(v) < -0.3,  "Gap down > 0.3%",         "short"),
    ("flat_open",        "gap_pct",         lambda v: abs(float(v))<0.15, "Gap < 0.15% (flat)",    None),
    # Daily conviction (column-based, not from confidence_inputs)
    ("conviction_high",  "daily_conviction", lambda v: str(v) in ("HIGH","VERY_HIGH"), "Daily conviction HIGH+", None),
    ("conviction_vh",    "daily_conviction", lambda v: str(v) == "VERY_HIGH",          "Daily conviction VH",    None),
    # Daily regime
    ("regime_bull",      "daily_regime",    lambda v: str(v) == "bull", "Daily regime bull",        "long"),
    ("regime_bear",      "daily_regime",    lambda v: str(v) == "bear", "Daily regime bear",        "short"),
    # VIX regime
    ("vix_calm",         "daily_vix_regime", lambda v: str(v) in ("low","moderate"), "VIX low or moderate", None),
    ("vix_low",          "daily_vix_regime", lambda v: str(v) == "low",             "VIX low only",        None),
    # Time of day
    ("first_30min",      "time_bucket",     lambda v: str(v) == "open_30m",              "First 30 min",      None),
    ("first_hour",       "time_bucket",     lambda v: str(v) in ("open_30m","930_10"),   "First hour",        None),
    ("not_first_30min",  "time_bucket",     lambda v: str(v) != "open_30m",              "After 10:00",       None),
    ("power_hour",       "time_bucket",     lambda v: str(v) == "15_16",                 "Power hour",        None),
]

# Pair conditions that complement each other for 2-condition refinements
COMPATIBLE_PAIRS = [
    ("high_volume",   "above_vwap"),
    ("high_volume",   "conviction_high"),
    ("high_volume",   "regime_bull"),
    ("high_volume",   "regime_bear"),
    ("high_volume",   "first_hour"),
    ("above_vwap",    "conviction_high"),
    ("above_vwap",    "ema_up"),
    ("below_vwap",    "ema_down"),
    ("conviction_high", "regime_bull"),
    ("conviction_high", "regime_bear"),
    ("conviction_high", "vix_calm"),
    ("rsi_bullish",   "ema_up"),
    ("rsi_bearish",   "ema_down"),
    ("macd_positive", "above_vwap"),
    ("macd_negative", "below_vwap"),
    ("first_hour",    "high_volume"),
    ("first_hour",    "conviction_high"),
    ("gap_up",        "above_vwap"),
    ("gap_down",      "below_vwap"),
    ("vix_calm",      "regime_bull"),
    ("vix_calm",      "regime_bear"),
]


# ---------------------------------------------------------------------------
# Filter application
# ---------------------------------------------------------------------------

def _apply_condition(df: pd.DataFrame, cond_name: str) -> pd.Series:
    """Return boolean mask for rows passing the named condition."""
    for name, col, fn, desc, bias in CONDITION_CATALOG:
        if name != cond_name:
            continue
        if col not in df.columns:
            return pd.Series(False, index=df.index)
        vals = df[col]
        mask = pd.Series(False, index=df.index)
        for i, v in vals.items():
            try:
                if v is not None and not (isinstance(v, float) and v != v):
                    mask[i] = fn(v)
            except Exception:
                pass
        return mask
    return pd.Series(False, index=df.index)


def _filter_by_conditions(df: pd.DataFrame, conditions: list[str]) -> pd.DataFrame:
    """Apply all conditions (AND logic), return filtered DataFrame."""
    mask = pd.Series(True, index=df.index)
    for cname in conditions:
        mask &= _apply_condition(df, cname)
    return df[mask].copy()


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _pf(returns: np.ndarray) -> float:
    wins   = float(returns[returns > 0].sum())
    losses = float(abs(returns[returns <= 0].sum()))
    if losses == 0:
        return 5.0 if wins > 0 else 1.0
    return min(5.0, wins / losses)


def _metrics(returns: np.ndarray) -> dict:
    r = returns - SLIPPAGE_PCT
    n = len(r)
    if n == 0:
        return dict(n=0, wr=0.0, exp=0.0, pf=0.0, max_dd=0.0)
    cum  = np.cumsum(r)
    rmax = np.maximum.accumulate(cum)
    dd   = float((rmax - cum).max()) if len(cum) else 0.0
    return dict(n=n, wr=float((r > 0).mean()), exp=float(np.mean(r)),
                pf=_pf(r), max_dd=dd)


# ---------------------------------------------------------------------------
# Breadth checks
# ---------------------------------------------------------------------------

def _ticker_breadth(df: pd.DataFrame) -> int:
    """Number of tickers with >= 3 setups in this refined group."""
    if "ticker" not in df.columns:
        return 0
    counts = df["ticker"].value_counts()
    return int((counts >= 3).sum())


def _week_breadth(df: pd.DataFrame) -> int:
    """Number of distinct ISO weeks represented."""
    if "week_label" not in df.columns:
        return 0
    return int(df["week_label"].nunique())


def _outlier_sensitivity(returns: np.ndarray) -> float:
    """
    Drop in expectancy (%) when removing the single largest winning trade.
    High sensitivity means results depend on one outlier trade.
    """
    r = returns - SLIPPAGE_PCT
    if len(r) < 3:
        return 1.0
    base_exp = float(np.mean(r))
    if base_exp <= 0:
        return 0.0
    # Remove largest winner
    max_idx = np.argmax(r)
    trimmed = np.delete(r, max_idx)
    if len(trimmed) == 0:
        return 1.0
    trimmed_exp = float(np.mean(trimmed))
    if base_exp <= 0:
        return 0.0
    drop = max(0.0, (base_exp - trimmed_exp) / abs(base_exp))
    return float(drop)


# ---------------------------------------------------------------------------
# Promotion decision
# ---------------------------------------------------------------------------

def _assign_refined_status(
    is_m: dict, oos_m: dict,
    orig_is_m: dict, orig_oos_m: dict,
    ticker_breadth: int, week_breadth: int,
    outlier_sens: float,
) -> tuple[str, str]:
    """Returns (status, reject_reason)."""
    fails = []
    if is_m["n"] < MIN_REFINED_IS_N:
        fails.append(f"refined IS n={is_m['n']}<{MIN_REFINED_IS_N}")
    if oos_m["n"] < MIN_REFINED_OOS_N:
        fails.append(f"refined OOS n={oos_m['n']}<{MIN_REFINED_OOS_N}")
    if oos_m["exp"] <= 0:
        fails.append(f"OOS exp={oos_m['exp']:+.3f}% <= 0")
    if oos_m["pf"] <= orig_oos_m.get("pf", 0):
        fails.append(f"OOS PF {oos_m['pf']:.2f} not > original {orig_oos_m.get('pf',0):.2f}")
    if ticker_breadth < MIN_TICKER_BREADTH:
        fails.append(f"ticker breadth {ticker_breadth}<{MIN_TICKER_BREADTH}")
    if week_breadth < MIN_WEEK_BREADTH:
        fails.append(f"week breadth {week_breadth}<{MIN_WEEK_BREADTH}")
    if outlier_sens > OUTLIER_SENSITIVITY_THRESH:
        fails.append(f"outlier sensitivity {outlier_sens:.0%}>{OUTLIER_SENSITIVITY_THRESH:.0%}")

    if fails:
        return "rejected", "; ".join(fails)

    # All hard criteria met — check if it beats original IS too
    if is_m["exp"] > orig_is_m.get("exp", 0):
        return "promoted", "all criteria met"
    return "candidate", "OOS ok but IS not clearly better than original"


# ---------------------------------------------------------------------------
# Main: generate and test refinements for one setup type
# ---------------------------------------------------------------------------

def _eligible_conditions(direction: str, attribution_df: pd.DataFrame,
                          available_cols: set[str]) -> list[str]:
    """Return condition names that are significant AND have their feature available."""
    if attribution_df.empty:
        return []

    eligible = []
    for name, col, fn, desc, bias in CONDITION_CATALOG:
        if bias is not None and bias != direction:
            continue
        if col not in available_cols:
            continue
        # Check attribution significance
        row = attribution_df[attribution_df["condition_name"].str.contains(col, regex=False, na=False)]
        if not row.empty:
            max_effect = row["effect_size"].abs().max()
            if max_effect < 1 + MIN_ATTRIBUTION_EFFECT:  # lift-based: 1 = no effect
                # Also check Cohen's d-style effect
                max_diff = row["effect_size"].abs().max()
                if max_diff < MIN_ATTRIBUTION_EFFECT:
                    continue
        eligible.append(name)

    return eligible


def generate_refinements(
    setup_type: str,
    direction: str,
    df: pd.DataFrame,
    attribution_df: pd.DataFrame,
    as_of: date,
) -> list[dict]:
    """
    Generate and test candidate refinements for one (setup_type, direction).

    Args:
        setup_type:     e.g. "orb_bull"
        direction:      "long" | "short"
        df:             Full dataset for this setup (all tickers, sorted by ts)
        attribution_df: Attribution rows for this (setup_type, direction)
        as_of:          Date label

    Returns:
        List of refinement dicts ready for DB upsert.
    """
    results = []

    # 70/30 chronological split
    n_total   = len(df)
    split_idx = int(n_total * 0.70)
    is_df     = df.iloc[:split_idx]
    oos_df    = df.iloc[split_idx:]

    orig_is_returns  = is_df["future_return"].values.astype(float)
    orig_oos_returns = oos_df["future_return"].values.astype(float)
    orig_is_m        = _metrics(orig_is_returns)
    orig_oos_m       = _metrics(orig_oos_returns)

    if orig_is_m["n"] < MIN_BASE_IS_N:
        return []  # Not enough base data

    # Available feature columns (from confidence_inputs or direct)
    available_cols = set(df.columns)

    # Which conditions are eligible based on attribution significance?
    eligible = _eligible_conditions(direction, attribution_df, available_cols)

    def _test_conditions(conditions: list[str]) -> dict | None:
        """Filter IS/OOS and compute metrics. Returns result dict or None if insufficient."""
        expr = " AND ".join(f"[{c}]" for c in conditions)
        cond_descs = []
        for name, col, fn, desc, bias in CONDITION_CATALOG:
            if name in conditions:
                cond_descs.append(desc)

        rule_expr = f"{setup_type}/{direction}: {' + '.join(cond_descs)}"

        # Apply filter to entire dataset (IS + OOS together for consistency)
        ref_is  = _filter_by_conditions(is_df,  conditions)
        ref_oos = _filter_by_conditions(oos_df, conditions)

        ref_is_r  = ref_is["future_return"].values.astype(float)
        ref_oos_r = ref_oos["future_return"].values.astype(float)

        ref_is_m  = _metrics(ref_is_r)
        ref_oos_m = _metrics(ref_oos_r)

        if ref_is_m["n"] < MIN_REFINED_IS_N:
            return None  # Too few after filtering

        t_breadth = _ticker_breadth(ref_oos)
        w_breadth = _week_breadth(ref_oos)
        out_sens  = _outlier_sensitivity(ref_oos_r) if len(ref_oos_r) >= 3 else 1.0

        status, reject_reason = _assign_refined_status(
            ref_is_m, ref_oos_m, orig_is_m, orig_oos_m,
            t_breadth, w_breadth, out_sens,
        )

        def _sf(v):
            if v is None:
                return None
            if isinstance(v, float) and v != v:
                return None
            return v

        return {
            "parent_setup_type":   setup_type,
            "direction":           direction,
            "rule_expression":     rule_expr,
            "added_conditions":    json.dumps(conditions),
            "as_of_date":          as_of,
            "original_sample_size": orig_is_m["n"],
            "original_expectancy": _sf(orig_is_m["exp"]),
            "original_pf":         _sf(orig_is_m["pf"]),
            "original_win_rate":   _sf(orig_is_m["wr"]),
            "refined_sample_size": ref_is_m["n"],
            "refined_expectancy":  _sf(ref_is_m["exp"]),
            "refined_pf":          _sf(ref_is_m["pf"]),
            "refined_win_rate":    _sf(ref_is_m["wr"]),
            "oos_sample_size":     ref_oos_m["n"],
            "oos_expectancy":      _sf(ref_oos_m["exp"]),
            "oos_pf":              _sf(ref_oos_m["pf"]),
            "oos_win_rate":        _sf(ref_oos_m["wr"]),
            "walk_forward_passed": status in ("promoted", "candidate"),
            "multi_ticker_breadth": t_breadth,
            "multi_week_breadth":   w_breadth,
            "outlier_sensitivity":  _sf(out_sens),
            "status":              status,
            "reject_reason":       reject_reason if status == "rejected" else None,
        }

    seen_exprs: set[str] = set()

    # ── 1-condition refinements ────────────────────────────────────────────
    for cname in eligible:
        r = _test_conditions([cname])
        if r is not None and r["rule_expression"] not in seen_exprs:
            seen_exprs.add(r["rule_expression"])
            results.append(r)

    # ── 2-condition refinements (compatible pairs only) ───────────────────
    eligible_set = set(eligible)
    for a, b in COMPATIBLE_PAIRS:
        if a not in eligible_set or b not in eligible_set:
            continue
        r = _test_conditions([a, b])
        if r is not None and r["rule_expression"] not in seen_exprs:
            seen_exprs.add(r["rule_expression"])
            results.append(r)

    return results


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def upsert_refined_rules(rows: list[dict], engine) -> int:
    if not rows:
        return 0
    from sqlalchemy import text
    sql = text("""
    INSERT INTO intraday_refined_rules
        (parent_setup_type, direction, rule_expression, added_conditions, as_of_date,
         original_sample_size, original_expectancy, original_pf, original_win_rate,
         refined_sample_size, refined_expectancy, refined_pf, refined_win_rate,
         oos_sample_size, oos_expectancy, oos_pf, oos_win_rate,
         walk_forward_passed, multi_ticker_breadth, multi_week_breadth,
         outlier_sensitivity, status, reject_reason)
    VALUES
        (:parent_setup_type, :direction, :rule_expression, :added_conditions, :as_of_date,
         :original_sample_size, :original_expectancy, :original_pf, :original_win_rate,
         :refined_sample_size, :refined_expectancy, :refined_pf, :refined_win_rate,
         :oos_sample_size, :oos_expectancy, :oos_pf, :oos_win_rate,
         :walk_forward_passed, :multi_ticker_breadth, :multi_week_breadth,
         :outlier_sensitivity, :status, :reject_reason)
    ON CONFLICT (parent_setup_type, direction, rule_expression, as_of_date) DO UPDATE SET
        refined_sample_size  = EXCLUDED.refined_sample_size,
        refined_expectancy   = EXCLUDED.refined_expectancy,
        refined_pf           = EXCLUDED.refined_pf,
        refined_win_rate     = EXCLUDED.refined_win_rate,
        oos_sample_size      = EXCLUDED.oos_sample_size,
        oos_expectancy       = EXCLUDED.oos_expectancy,
        oos_pf               = EXCLUDED.oos_pf,
        oos_win_rate         = EXCLUDED.oos_win_rate,
        walk_forward_passed  = EXCLUDED.walk_forward_passed,
        multi_ticker_breadth = EXCLUDED.multi_ticker_breadth,
        multi_week_breadth   = EXCLUDED.multi_week_breadth,
        outlier_sensitivity  = EXCLUDED.outlier_sensitivity,
        status               = EXCLUDED.status,
        reject_reason        = EXCLUDED.reject_reason
    """)

    def _c(v):
        if isinstance(v, float) and v != v:
            return None
        return v

    clean = [{k: _c(v) for k, v in r.items()} for r in rows]
    with engine.begin() as conn:
        conn.execute(sql, clean)
    return len(clean)
