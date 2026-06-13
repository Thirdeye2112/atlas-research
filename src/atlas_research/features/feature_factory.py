"""
Feature factory — single entry point for feature computation.

ARCHITECTURE NOTE
-----------------
Feature modules (trend, momentum, …) accept numpy arrays only.
This module owns the framework conversion:

    DataFrame / Series  →  numpy arrays  →  feature modules  →  dict

The result is that feature modules have zero framework dependencies
and can be called from pandas, polars, arrow, or any other data layer
without modification.  This is the Polars migration path.

Purity contract: this factory calls only pure feature functions.
No database reads, no model calls, no global state inside this module
or any module it calls.  All I/O happens at the pipeline layer.

Usage:
    from atlas_research.features.feature_factory import build_features

    fv = build_features("AAPL", bars_df, spy_bars_df)
    # returns dict[str, float | None]
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from atlas_research.features import (
    momentum,
    omni_proxy,
    regime,
    relative_strength,
    trend,
    volatility,
    volume,
)

# Minimum bars needed for any feature to be computable.
# RSI-14 needs 15; SMA-200 needs 200.  Features requiring more bars
# return None for that ticker/date; they are not errors.
MIN_BARS = 15


def build_features(
    ticker: str,
    bars: pd.DataFrame,
    spy_bars: pd.DataFrame | None = None,
) -> dict[str, float | None] | None:
    """
    Compute all Phase-1 features for a single (ticker, date) snapshot.

    This function converts DataFrames → numpy arrays once, then delegates
    to pure feature functions.  No DB access, no side effects.

    Args:
        ticker:   Symbol (used for caller logging only; not used internally).
        bars:     DataFrame with columns [date, open, high, low, close,
                  adjusted_close, volume], sorted ascending by date.
                  The final row is the snapshot date.
        spy_bars: SPY bars, same format.  Pass None to skip RS and regime.

    Returns:
        Dict of feature_name → float | None, or None if bars < MIN_BARS.
    """
    if bars is None or len(bars) < MIN_BARS:
        return None

    # ── Convert to numpy once ────────────────────────────────
    # All downstream functions receive plain numpy float64 arrays.
    close  = bars["adjusted_close"].to_numpy(dtype=np.float64)
    high   = bars["high"].to_numpy(dtype=np.float64)
    low    = bars["low"].to_numpy(dtype=np.float64)
    vol    = bars["volume"].to_numpy(dtype=np.float64)
    open_  = bars["open"].to_numpy(dtype=np.float64) if "open" in bars.columns else None

    features: dict[str, float | None] = {}

    # ── Feature groups (all pure functions) ──────────────────
    features.update(trend.compute(close))
    features.update(momentum.compute(close))
    features.update(volatility.compute(close, high, low))
    features.update(volume.compute(close, vol))
    features.update(omni_proxy.compute(close, high, low, open_))

    # ── Quality tier + quality-adjusted Jarvis ───────────────
    # Tier 1: price>$50 & dvol>$25M  (large cap, signal is bullish)
    # Tier 2: price $20-50 & dvol>$5M (mid cap, signal is bullish)
    # Tier 3: price $5-20 & dvol>$1M  (small cap, signal is neutral)
    # Tier 4: everything else          (micro/junk, signal reverses to bearish)
    lookback = min(252, len(close))
    med_price = float(np.median(close[-lookback:]))
    avg_dvol  = float(np.mean(close[-lookback:] * vol[-lookback:]))
    if med_price > 50 and avg_dvol > 25_000_000:
        tier = 1
    elif 20 <= med_price <= 50 and avg_dvol > 5_000_000:
        tier = 2
    elif 5 <= med_price <= 20 and avg_dvol > 1_000_000:
        tier = 3
    else:
        tier = 4
    features["quality_tier"] = float(tier)

    omni_above = features.get("omni_82_above")
    if omni_above is not None:
        if tier <= 2:
            features["jarvis_quality_adjusted"] = omni_above * 2.0 - 1.0   # 1.0 if green, -1.0 if not
        elif tier == 3:
            features["jarvis_quality_adjusted"] = 0.0
        else:
            features["jarvis_quality_adjusted"] = -(omni_above * 2.0 - 1.0)  # inverted for junk
    else:
        features["jarvis_quality_adjusted"] = None

    # ── Relative strength + regime (require SPY) ─────────────
    if spy_bars is not None and len(spy_bars) >= MIN_BARS:
        spy_close = spy_bars["adjusted_close"].to_numpy(dtype=np.float64)

        # Align to common trailing length
        min_len = min(len(close), len(spy_close))
        features.update(
            relative_strength.compute(
                close[-min_len:],
                spy_close[-min_len:],
            )
        )
        features.update(regime.compute(spy_close))
    else:
        features.update({"rs_spy_20": None, "rs_spy_60": None, "rs_spy_120": None,
                          "rs_spy_20_momentum": None})
        features.update({
            "spy_above_sma50":  None,
            "spy_above_sma200": None,
            "spy_return_20d":   None,
            "market_trend":     None,
        })

    return features


def build_features_from_arrays(
    close:     np.ndarray,
    high:      np.ndarray,
    low:       np.ndarray,
    vol:       np.ndarray,
    spy_close: np.ndarray | None = None,
) -> dict[str, float | None] | None:
    """
    Framework-free entry point — accepts raw numpy arrays directly.
    Used by Polars-based callers and tests that don't want to build DataFrames.

    Args:
        close:     Adjusted close prices, ascending date order.
        high:      Daily highs, same length.
        low:       Daily lows, same length.
        vol:       Share volumes, same length.
        spy_close: SPY adjusted close, trailing window.  None to skip RS/regime.

    Returns:
        Dict of feature_name → float | None, or None if len(close) < MIN_BARS.
    """
    if len(close) < MIN_BARS:
        return None

    features: dict[str, float | None] = {}
    features.update(trend.compute(close))
    features.update(momentum.compute(close))
    features.update(volatility.compute(close, high, low))
    features.update(volume.compute(close, vol))
    features.update(omni_proxy.compute(close, high, low))

    if spy_close is not None and len(spy_close) >= MIN_BARS:
        min_len = min(len(close), len(spy_close))
        features.update(relative_strength.compute(close[-min_len:], spy_close[-min_len:]))
        features.update(regime.compute(spy_close))
    else:
        features.update({"rs_spy_20": None, "rs_spy_60": None, "rs_spy_120": None,
                          "rs_spy_20_momentum": None})
        features.update({
            "spy_above_sma50": None, "spy_above_sma200": None,
            "spy_return_20d": None, "market_trend": None,
        })

    return features
