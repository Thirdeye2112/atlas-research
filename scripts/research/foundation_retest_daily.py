"""
foundation_retest_daily.py
=============================
Point-in-time daily-context attachment -- reproduces
setup_formation_common.py's attach_daily_context (research/setup-formation,
phase 1 of this research arc), including the tz/dtype fix discovered there
(merge_asof requires both keys to be the exact same dtype/tz-awareness).

For each 5m bar at local date D, attaches the most recent pattern_memory
daily row with confirm_date < D (never D itself -- today's daily candle
hasn't closed yet relative to any intraday decision point on D). This is
the SAME daily-context source and SAME causal rule used in setup-formation
v1; reused here for direct comparability, not reinvented.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text


def load_daily_pattern_context(engine, ticker: str) -> pd.DataFrame:
    df = pd.read_sql(
        text("""
            SELECT id, ticker, confirm_date, trend, market_trend,
                   dist_support, dist_resistance
            FROM pattern_memory
            WHERE timeframe = 'daily' AND ticker = :t
            ORDER BY confirm_date, id
        """),
        engine, params={"t": ticker},
    )
    df = df.sort_values(["confirm_date", "id"]).drop_duplicates(subset=["confirm_date"], keep="last")
    df["confirm_date"] = pd.to_datetime(df["confirm_date"]).astype("datetime64[ns]")
    return df.drop(columns=["id"]).reset_index(drop=True)


def attach_daily_context(feat_df: pd.DataFrame, daily_ctx: pd.DataFrame) -> pd.DataFrame:
    local_date = (
        feat_df["ts"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
        .astype("datetime64[ns]")
    )
    left = pd.DataFrame({"_decision_date": local_date}).reset_index(drop=False)
    left = left.rename(columns={"index": "_orig_idx"}).sort_values("_decision_date")

    right = daily_ctx.sort_values("confirm_date")

    merged = pd.merge_asof(
        left, right,
        left_on="_decision_date", right_on="confirm_date",
        direction="backward", allow_exact_matches=False,
    )
    merged = merged.sort_values("_orig_idx").reset_index(drop=True)

    out = feat_df.reset_index(drop=True).copy()
    out["daily_trend"] = merged["trend"].values
    out["daily_market_trend"] = merged["market_trend"].values
    out["daily_dist_support"] = merged["dist_support"].values
    out["daily_dist_resistance"] = merged["dist_resistance"].values
    return out


def daily_agrees(direction: str, daily_trend) -> bool | None:
    """True if the trigger's direction matches the prior-day daily trend,
    False if it conflicts, None if daily_trend is unknown (no prior-day row,
    e.g. the first days of a ticker's history)."""
    if daily_trend is None or (isinstance(daily_trend, float) and np.isnan(daily_trend)):
        return None
    if daily_trend not in ("up", "down"):
        return None
    if direction == "long":
        return daily_trend == "up"
    if direction == "short":
        return daily_trend == "down"
    return None
