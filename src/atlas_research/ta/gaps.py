"""
ta/gaps.py — Gap and Fair Value Gap (FVG / 3-bar imbalance) detection.

Gap Types Implemented
---------------------

1. CLASSIC DAILY GAP
   Definition: today's open jumps past prior day's extreme (completely untraded zone).
     gap_up  : today.open > prior_day.high
     gap_down: today.open < prior_day.low
   Zone (the untraded area):
     gap_up  : zone = [prior_day.high, today.open]
     gap_down: zone = [today.open,     prior_day.low]
   size_pct  : (zone_top - zone_bottom) / zone_bottom * 100  (always positive)
   Applies to: daily bars only (raw_bars).
   Look-ahead: None. Uses only prior_day OHLC and today's open. Both are known
               at today's open (prior day closed; today opened).

2. FAIR VALUE GAP (FVG) / 3-BAR IMBALANCE
   Definition (standard SMC/ICT): for 3 consecutive bars [C1, C2, C3]:
     bullish FVG: C1.high < C3.low   → untraded zone = [C1.high, C3.low]
     bearish FVG: C1.low  > C3.high  → untraded zone = [C3.high, C1.low]
   C2 is the "impulse" candle; its range does not completely bridge C1 and C3.
   The detection criterion checks only whether the price extremes of C1 and C3
   leave a gap — C2's OHLC does not affect the gap boundary.
   size_pct  : (zone_top - zone_bottom) / zone_bottom * 100
   Applies to: any timeframe (daily or 5m).
   Look-ahead: CRITICAL. The FVG is ONLY confirmed at C3's CLOSE.
               ts stored = C3.ts (the bar's open timestamp in intraday_bars).
               For 5m bars, C3 closes at ts + 5min; for daily, at day close.
               Downstream consumers must not use this signal before C3 closes.

Entry points
------------
    from atlas_research.ta.gaps import compute_classic_gaps, compute_fvgs

    # daily bars: ticker, date, open, high, low, close — sorted by date ASC
    classic = compute_classic_gaps(df)

    # any bars: ticker, ts (UTC), open, high, low, close — sorted by ts ASC
    fvgs = compute_fvgs(df, timeframe="5m")
    fvgs_d = compute_fvgs(df_daily, timeframe="daily")

Both return a DataFrame with the schema matching the gaps table.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Classic Daily Gap
# ---------------------------------------------------------------------------

def compute_classic_gaps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect classic daily gaps from raw_bars data (single ticker).

    Parameters
    ----------
    df : pd.DataFrame
        Columns required: ticker, date (datetime or date), open, high, low, close.
        Must be sorted ascending by date.  Single ticker only.

    Returns
    -------
    pd.DataFrame with schema matching the gaps table, gap_type='classic'.
    Empty DataFrame if no gaps found or fewer than 2 bars.
    """
    if len(df) < 2:
        return _empty_gaps()

    df = df.copy().sort_values("date").reset_index(drop=True)
    ticker = df["ticker"].iloc[0]

    rows = []
    for i in range(1, len(df)):
        today = df.iloc[i]
        prev = df.iloc[i - 1]

        o = float(today["open"])
        ph = float(prev["high"])
        pl = float(prev["low"])
        pc = float(prev["close"])

        if any(np.isnan([o, ph, pl, pc])):
            continue

        if o > ph:
            # Gap up: today opened above prior day's high
            direction = "up"
            zone_top = o
            zone_bottom = ph
        elif o < pl:
            # Gap down: today opened below prior day's low
            direction = "down"
            zone_top = pl
            zone_bottom = o
        else:
            continue  # no classic gap

        size_pct = (zone_top - zone_bottom) / max(zone_bottom, 1e-9) * 100
        # ts = today's date as UTC midnight TIMESTAMPTZ
        ts = pd.Timestamp(today["date"]).normalize().tz_localize("UTC") if pd.Timestamp(today["date"]).tzinfo is None else pd.Timestamp(today["date"]).normalize().tz_convert("UTC")

        rows.append({
            "ticker":          ticker,
            "ts":              ts,
            "timeframe":       "daily",
            "gap_type":        "classic",
            "direction":       direction,
            "zone_top":        zone_top,
            "zone_bottom":     zone_bottom,
            "size_pct":        size_pct,
            "detect_close_ts": ts,
            "bar1_ts":         pd.Timestamp(prev["date"]).normalize().tz_localize("UTC") if pd.Timestamp(prev["date"]).tzinfo is None else pd.Timestamp(prev["date"]).normalize().tz_convert("UTC"),
            "bar3_ts":         None,
        })

    return pd.DataFrame(rows) if rows else _empty_gaps()


# ---------------------------------------------------------------------------
# Fair Value Gap (3-bar imbalance)
# ---------------------------------------------------------------------------

def compute_fvgs(
    df: pd.DataFrame,
    timeframe: str,
    min_size_pct: float = 0.0,
) -> pd.DataFrame:
    """
    Detect Fair Value Gaps (3-bar imbalances) for any timeframe.

    Parameters
    ----------
    df : pd.DataFrame
        Columns required: ticker, ts (UTC TIMESTAMPTZ), open, high, low, close.
        For daily bars, ts should be date cast to UTC midnight TIMESTAMPTZ.
        Must be sorted ascending by ts.  Single ticker only.
    timeframe : str
        '5m' or 'daily' — stored in the output rows.
    min_size_pct : float
        Minimum gap size in % of zone_bottom to include. Default 0 (no filter).

    Returns
    -------
    pd.DataFrame with schema matching the gaps table, gap_type='fvg'.

    Look-ahead guarantee
    --------------------
    For each triplet (C1, C2, C3) at index (i-2, i-1, i), the gap is:
      - defined using ONLY C1.high, C1.low, C3.high, C3.low (no future bars)
      - recorded with ts = C3.ts (the detection bar)
    C2's content does not affect detection (it is the candle between the gap edges).
    """
    if len(df) < 3:
        return _empty_gaps()

    df = df.copy().sort_values("ts").reset_index(drop=True)
    ticker = df["ticker"].iloc[0]

    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    # Use tolist() to guarantee tz-aware pd.Timestamp objects (avoid .values on tz Series
    # which in pandas 3.x can return DatetimeArray with subtle tz-stripping on scalar access)
    ts_list = df["ts"].tolist()

    rows = []
    for i in range(2, len(df)):
        c1h = h[i - 2]
        c1l = l[i - 2]
        c3h = h[i]
        c3l = l[i]

        if any(np.isnan([c1h, c1l, c3h, c3l])):
            continue

        ts_c3 = ts_list[i]      # tz-aware pd.Timestamp (UTC)
        ts_c1 = ts_list[i - 2]  # tz-aware pd.Timestamp (UTC)

        if c1h < c3l:
            # Bullish FVG: gap between C1.high and C3.low (price moved up, leaving gap)
            direction = "up"
            zone_bottom = c1h
            zone_top = c3l
            size_pct = (zone_top - zone_bottom) / max(zone_bottom, 1e-9) * 100
            if size_pct < min_size_pct:
                continue
            rows.append(_fvg_row(ticker, ts_c3, ts_c1, timeframe,
                                 direction, zone_top, zone_bottom, size_pct))

        if c1l > c3h:
            # Bearish FVG: gap between C3.high and C1.low (price moved down, leaving gap)
            direction = "down"
            zone_bottom = c3h
            zone_top = c1l
            size_pct = (zone_top - zone_bottom) / max(zone_bottom, 1e-9) * 100
            if size_pct < min_size_pct:
                continue
            rows.append(_fvg_row(ticker, ts_c3, ts_c1, timeframe,
                                 direction, zone_top, zone_bottom, size_pct))

    return pd.DataFrame(rows) if rows else _empty_gaps()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fvg_row(
    ticker: str,
    ts_c3: pd.Timestamp,
    ts_c1: pd.Timestamp,
    timeframe: str,
    direction: str,
    zone_top: float,
    zone_bottom: float,
    size_pct: float,
) -> dict:
    return {
        "ticker":          ticker,
        "ts":              ts_c3,
        "timeframe":       timeframe,
        "gap_type":        "fvg",
        "direction":       direction,
        "zone_top":        zone_top,
        "zone_bottom":     zone_bottom,
        "size_pct":        size_pct,
        "detect_close_ts": ts_c3,  # C3 open; gap known at C3's CLOSE (ts + bar_duration)
        "bar1_ts":         ts_c1,
        "bar3_ts":         ts_c3,
    }


def _empty_gaps() -> pd.DataFrame:
    return pd.DataFrame(columns=[
        "ticker", "ts", "timeframe", "gap_type", "direction",
        "zone_top", "zone_bottom", "size_pct",
        "detect_close_ts", "bar1_ts", "bar3_ts",
    ])
