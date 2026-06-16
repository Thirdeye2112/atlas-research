"""
Atlas Meta-Signal Engine v1
Deterministic combo-key builder for signal combination scoring.

Key format (7 factors):
  conviction=HIGH|regime=bear|vix=moderate|tier=T2|ml=Q4|conf=35_50|jarvis=green

All bucket boundaries are fixed so keys remain stable across nightly runs.
"""

from __future__ import annotations

import math
import numpy as np
import pandas as pd
from typing import Union


# ---------------------------------------------------------------------------
# Bucket helpers
# ---------------------------------------------------------------------------

def ml_rank_bucket(ml_signal_strength: Union[float, None]) -> str:
    """Map ml_signal_strength (0-1) to quintile label Q1-Q5."""
    if ml_signal_strength is None:
        return "Q_unk"
    try:
        v = float(ml_signal_strength)
    except (TypeError, ValueError):
        return "Q_unk"
    if math.isnan(v):
        return "Q_unk"
    if v < 0.2:
        return "Q1"
    if v < 0.4:
        return "Q2"
    if v < 0.6:
        return "Q3"
    if v < 0.8:
        return "Q4"
    return "Q5"


def confluence_bucket(confluence_score: Union[float, None]) -> str:
    """
    Map confluence_score to bucket label.
    Scores in data are either small integers (0-4) from early pipeline,
    or floats in 25-65 range from current pipeline.
    """
    if confluence_score is None:
        return "cf_unk"
    try:
        v = float(confluence_score)
    except (TypeError, ValueError):
        return "cf_unk"
    if math.isnan(v):
        return "cf_unk"
    if v < 30:
        return "lt30"
    if v < 40:
        return "30_40"
    if v < 50:
        return "40_50"
    return "gt50"


def quality_tier_label(quality_tier: Union[int, float, None]) -> str:
    """Map quality_tier integer (1-4) to label."""
    if quality_tier is None:
        return "T_unk"
    try:
        v = int(quality_tier)
    except (TypeError, ValueError):
        return "T_unk"
    if v in (1, 2, 3, 4):
        return f"T{v}"
    return "T_unk"


def jarvis_state_label(jarvis_green: Union[bool, int, float, None]) -> str:
    """Map jarvis_green (True/False/None) to state label."""
    if jarvis_green is None:
        return "unknown"
    try:
        if isinstance(jarvis_green, float) and math.isnan(jarvis_green):
            return "unknown"
    except TypeError:
        pass
    return "green" if bool(jarvis_green) else "red"


def _safe_str(v, fallback: str = "unk") -> str:
    """Coerce a field value to a clean string, replacing None/NaN with fallback."""
    if v is None:
        return fallback
    try:
        if isinstance(v, float) and math.isnan(v):
            return fallback
    except TypeError:
        pass
    s = str(v).strip()
    return s if s else fallback


# ---------------------------------------------------------------------------
# Key builder
# ---------------------------------------------------------------------------

def build_combo_key(
    conviction_level: Union[str, None] = None,
    sector_regime: Union[str, None] = None,
    vix_regime: Union[str, None] = None,
    quality_tier: Union[int, float, None] = None,
    ml_signal_strength: Union[float, None] = None,
    confluence_score: Union[float, None] = None,
    jarvis_green: Union[bool, int, float, None] = None,
    *,
    row: Union[dict, None] = None,
) -> str:
    """
    Build a deterministic combo key from signal context.
    Pass either keyword arguments OR a dict/Series via ``row=``.

    Returns a pipe-delimited string:
        conviction=HIGH|regime=bear|vix=moderate|tier=T2|ml=Q4|conf=35_50|jarvis=green
    """
    if row is not None:
        conviction_level   = row.get("conviction_level")
        sector_regime      = row.get("sector_regime")
        vix_regime         = row.get("vix_regime")
        quality_tier       = row.get("quality_tier")
        ml_signal_strength = row.get("ml_signal_strength")
        confluence_score   = row.get("confluence_score")
        jarvis_green       = row.get("jarvis_green")

    parts = [
        f"conviction={_safe_str(conviction_level)}",
        f"regime={_safe_str(sector_regime)}",
        f"vix={_safe_str(vix_regime)}",
        f"tier={quality_tier_label(quality_tier)}",
        f"ml={ml_rank_bucket(ml_signal_strength)}",
        f"conf={confluence_bucket(confluence_score)}",
        f"jarvis={jarvis_state_label(jarvis_green)}",
    ]
    return "|".join(parts)


def build_combo_key_vectorized(df: pd.DataFrame) -> pd.Series:
    """
    Fast vectorized version — operates on a DataFrame with the standard context columns.
    Returns a Series of combo_key strings aligned with df.index.
    """
    ml_s = df["ml_signal_strength"] if "ml_signal_strength" in df.columns else pd.Series(float("nan"), index=df.index)
    cf_s = df["confluence_score"]   if "confluence_score"   in df.columns else pd.Series(float("nan"), index=df.index)
    qt_s = df["quality_tier"]       if "quality_tier"       in df.columns else pd.Series(None, index=df.index)
    jg_s = df["jarvis_green"]       if "jarvis_green"       in df.columns else pd.Series(None, index=df.index)
    cv_s = df["conviction_level"]   if "conviction_level"   in df.columns else pd.Series(None, index=df.index)
    rg_s = df["sector_regime"]      if "sector_regime"      in df.columns else pd.Series(None, index=df.index)
    vx_s = df["vix_regime"]         if "vix_regime"         in df.columns else pd.Series(None, index=df.index)

    # ml bucket
    ml_num = pd.to_numeric(ml_s, errors="coerce")
    ml_b = pd.cut(
        ml_num,
        bins=[-np.inf, 0.2, 0.4, 0.6, 0.8, np.inf],
        labels=["Q1", "Q2", "Q3", "Q4", "Q5"],
    ).astype(str)
    ml_b[ml_num.isna()] = "Q_unk"

    # confluence bucket
    cf_num = pd.to_numeric(cf_s, errors="coerce")
    cf_b = pd.cut(
        cf_num,
        bins=[-np.inf, 30, 40, 50, np.inf],
        labels=["lt30", "30_40", "40_50", "gt50"],
    ).astype(str)
    cf_b[cf_num.isna()] = "cf_unk"

    # quality tier
    qt_num = pd.to_numeric(qt_s, errors="coerce").round(0)
    qt_b = qt_num.map(lambda x: f"T{int(x)}" if x in (1.0, 2.0, 3.0, 4.0) else "T_unk")

    # jarvis state
    jg_b = jg_s.map(lambda x: "unknown" if (x is None or (isinstance(x, float) and np.isnan(x)))
                                 else ("green" if bool(x) else "red"))

    # safe string for categoricals
    def _s(series: pd.Series, fallback: str = "unk") -> pd.Series:
        return series.fillna(fallback).astype(str).str.strip().replace("", fallback).replace("nan", fallback)

    cv_b = _s(cv_s)
    rg_b = _s(rg_s)
    vx_b = _s(vx_s)

    keys = (
        "conviction=" + cv_b + "|"
        "regime="     + rg_b + "|"
        "vix="        + vx_b + "|"
        "tier="       + qt_b + "|"
        "ml="         + ml_b + "|"
        "conf="       + cf_b + "|"
        "jarvis="     + jg_b
    )
    return keys


# ---------------------------------------------------------------------------
# Key parser
# ---------------------------------------------------------------------------

def parse_combo_key(key: str) -> dict:
    """Parse a combo key string back into its component dict."""
    parts = {}
    for segment in key.split("|"):
        if "=" in segment:
            k, v = segment.split("=", 1)
            parts[k] = v
    return parts
