"""
Build intraday_candle_memory_v2 (behavior_v2)
==============================================
Reads from intraday_candle_memory (v1), joins intraday_behavior_events for
each candle's trading date, appends a 20-dim behavior intensity vector to the
existing 16-dim v1 feature vector, producing a 36-dim combined vector.

Only tickers that have BOTH v1 candle memory AND behavior event coverage are
included.  Candles with no behavior events get a zero behavior vector.

Usage:
    python scripts/build_intraday_candle_memory_v2.py
    python scripts/build_intraday_candle_memory_v2.py --tickers SPY QQQ
    python scripts/build_intraday_candle_memory_v2.py --incremental
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import timezone

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from atlas_research.intraday.similarity.features_v2 import (
    BEHAVIOR_IDS,
    N_BEHAVIORS,
    N_FEATURES,
    N_FEATURES_V2,
    build_behavior_vector,
)

BATCH_SIZE = 1000
FEATURE_VERSION = "behavior_v2"

# Columns to copy from v1 (excluding id, feature_vector, created_at)
_V1_COLS = [
    "ticker", "ts", "timeframe",
    "open_price", "high_price", "low_price", "close_price", "volume",
    "body_pct", "upper_wick_ratio", "lower_wick_ratio", "is_green", "range_pct",
    "vol_ratio", "vol_zscore", "vwap_dist_pct", "or_position", "ema9_slope_norm",
    "rsi14", "macd_hist_norm", "atr_pct", "tod_min", "time_of_day", "candle_num",
    "daily_ml_rank", "daily_conviction", "daily_confluence",
    "daily_regime", "daily_vix", "daily_jarvis",
    "feature_vector",
    "future_return_1", "future_return_3", "future_return_6",
    "future_return_12", "future_return_24", "future_return_eod",
    "mfe_6", "mae_6", "mfe_12", "mae_12", "mfe_24", "mae_24",
    "hit_plus_0_5_atr", "hit_plus_1_0_atr",
    "hit_minus_0_5_atr", "hit_minus_1_0_atr",
]


def _load_behavior_map(engine, tickers: list[str]) -> dict[tuple, np.ndarray]:
    """Load intraday_behavior_events and build {(ticker, date): 20-dim array} lookup."""
    tk_list = ", ".join(f"'{t}'" for t in tickers)
    df = pd.read_sql(
        text(f"""
            SELECT ticker, event_date, behavior_id, intensity
            FROM intraday_behavior_events
            WHERE ticker IN ({tk_list})
        """),
        engine,
    )
    bmap: dict[tuple, np.ndarray] = {}
    if df.empty:
        return bmap

    df["event_date"] = pd.to_datetime(df["event_date"]).dt.date
    for (tk, edate), grp in df.groupby(["ticker", "event_date"]):
        events = grp[["behavior_id", "intensity"]].to_dict("records")
        bmap[(tk, edate)] = build_behavior_vector(events)
    return bmap


def _process_ticker(engine, ticker: str, bmap: dict, incremental: bool) -> int:
    """Load v1 memory for a ticker, attach behavior vectors, upsert into v2."""
    since_clause = ""
    if incremental:
        # Only process rows not yet in v2
        with engine.connect() as c:
            r = c.execute(text(
                f"SELECT MAX(ts) FROM intraday_candle_memory_v2 WHERE ticker = '{ticker}'"
            )).fetchone()
            if r and r[0]:
                since_ts = r[0]
                since_clause = f"AND ts > '{since_ts}'"

    v1 = pd.read_sql(
        text(f"""
            SELECT {', '.join(_V1_COLS)}
            FROM intraday_candle_memory
            WHERE ticker = '{ticker}' {since_clause}
            ORDER BY ts
        """),
        engine,
    )
    if v1.empty:
        return 0

    # Parse candle dates from ts
    v1["_candle_date"] = pd.to_datetime(v1["ts"], utc=True).dt.tz_convert(
        "America/Los_Angeles"
    ).dt.date

    # Parse v1 feature vectors
    def _parse_vec(v) -> np.ndarray:
        if v is None:
            return np.full(N_FEATURES, 0.5)
        if isinstance(v, (list, np.ndarray)):
            return np.array(v, dtype=np.float64)
        if isinstance(v, str):
            v = v.strip("{}")
            return np.fromstring(v, sep=",", dtype=np.float64)
        return np.full(N_FEATURES, 0.5)

    rows_out = []
    for _, row in v1.iterrows():
        v1_vec = _parse_vec(row["feature_vector"])
        if len(v1_vec) != N_FEATURES:
            v1_vec = np.full(N_FEATURES, 0.5)

        cdate  = row["_candle_date"]
        beh_vec = bmap.get((ticker, cdate), np.zeros(N_BEHAVIORS, dtype=np.float64))
        full_vec = np.concatenate([v1_vec, beh_vec])

        active = [BEHAVIOR_IDS[i] for i in range(N_BEHAVIORS) if beh_vec[i] > 0.0]

        rows_out.append({
            "ticker":           ticker,
            "ts":               row["ts"],
            "timeframe":        row.get("timeframe", "5m"),
            "feature_version":  FEATURE_VERSION,
            "open_price":       _f(row, "open_price"),
            "high_price":       _f(row, "high_price"),
            "low_price":        _f(row, "low_price"),
            "close_price":      _f(row, "close_price"),
            "volume":           _i(row, "volume"),
            "body_pct":         _f(row, "body_pct"),
            "upper_wick_ratio": _f(row, "upper_wick_ratio"),
            "lower_wick_ratio": _f(row, "lower_wick_ratio"),
            "is_green":         bool(row.get("is_green")) if row.get("is_green") is not None else None,
            "range_pct":        _f(row, "range_pct"),
            "vol_ratio":        _f(row, "vol_ratio"),
            "vol_zscore":       _f(row, "vol_zscore"),
            "vwap_dist_pct":    _f(row, "vwap_dist_pct"),
            "or_position":      _f(row, "or_position"),
            "ema9_slope_norm":  _f(row, "ema9_slope_norm"),
            "rsi14":            _f(row, "rsi14"),
            "macd_hist_norm":   _f(row, "macd_hist_norm"),
            "atr_pct":          _f(row, "atr_pct"),
            "tod_min":          _i(row, "tod_min"),
            "time_of_day":      row.get("time_of_day"),
            "candle_num":       _i(row, "candle_num"),
            "daily_ml_rank":    _f(row, "daily_ml_rank"),
            "daily_conviction": row.get("daily_conviction"),
            "daily_confluence": _f(row, "daily_confluence"),
            "daily_regime":     row.get("daily_regime"),
            "daily_vix":        row.get("daily_vix"),
            "daily_jarvis":     row.get("daily_jarvis"),
            "feature_vector_v1": v1_vec.tolist(),
            "behavior_vector":   beh_vec.tolist(),
            "active_behaviors":  active,
            "behavior_count":    len(active),
            "feature_vector":    full_vec.tolist(),
            "future_return_1":   _f(row, "future_return_1"),
            "future_return_3":   _f(row, "future_return_3"),
            "future_return_6":   _f(row, "future_return_6"),
            "future_return_12":  _f(row, "future_return_12"),
            "future_return_24":  _f(row, "future_return_24"),
            "future_return_eod": _f(row, "future_return_eod"),
            "mfe_6":             _f(row, "mfe_6"),
            "mae_6":             _f(row, "mae_6"),
            "mfe_12":            _f(row, "mfe_12"),
            "mae_12":            _f(row, "mae_12"),
            "mfe_24":            _f(row, "mfe_24"),
            "mae_24":            _f(row, "mae_24"),
            "hit_plus_0_5_atr":  bool(row["hit_plus_0_5_atr"]) if row.get("hit_plus_0_5_atr") is not None else None,
            "hit_plus_1_0_atr":  bool(row["hit_plus_1_0_atr"]) if row.get("hit_plus_1_0_atr") is not None else None,
            "hit_minus_0_5_atr": bool(row["hit_minus_0_5_atr"]) if row.get("hit_minus_0_5_atr") is not None else None,
            "hit_minus_1_0_atr": bool(row["hit_minus_1_0_atr"]) if row.get("hit_minus_1_0_atr") is not None else None,
        })

    # Upsert in batches
    sql = text("""
        INSERT INTO intraday_candle_memory_v2 (
            ticker, ts, timeframe, feature_version,
            open_price, high_price, low_price, close_price, volume,
            body_pct, upper_wick_ratio, lower_wick_ratio, is_green, range_pct,
            vol_ratio, vol_zscore, vwap_dist_pct, or_position, ema9_slope_norm,
            rsi14, macd_hist_norm, atr_pct, tod_min, time_of_day, candle_num,
            daily_ml_rank, daily_conviction, daily_confluence,
            daily_regime, daily_vix, daily_jarvis,
            feature_vector_v1, behavior_vector, active_behaviors, behavior_count, feature_vector,
            future_return_1, future_return_3, future_return_6, future_return_12,
            future_return_24, future_return_eod,
            mfe_6, mae_6, mfe_12, mae_12, mfe_24, mae_24,
            hit_plus_0_5_atr, hit_plus_1_0_atr, hit_minus_0_5_atr, hit_minus_1_0_atr
        ) VALUES (
            :ticker, :ts, :timeframe, :feature_version,
            :open_price, :high_price, :low_price, :close_price, :volume,
            :body_pct, :upper_wick_ratio, :lower_wick_ratio, :is_green, :range_pct,
            :vol_ratio, :vol_zscore, :vwap_dist_pct, :or_position, :ema9_slope_norm,
            :rsi14, :macd_hist_norm, :atr_pct, :tod_min, :time_of_day, :candle_num,
            :daily_ml_rank, :daily_conviction, :daily_confluence,
            :daily_regime, :daily_vix, :daily_jarvis,
            :feature_vector_v1, :behavior_vector, :active_behaviors, :behavior_count, :feature_vector,
            :future_return_1, :future_return_3, :future_return_6, :future_return_12,
            :future_return_24, :future_return_eod,
            :mfe_6, :mae_6, :mfe_12, :mae_12, :mfe_24, :mae_24,
            :hit_plus_0_5_atr, :hit_plus_1_0_atr, :hit_minus_0_5_atr, :hit_minus_1_0_atr
        )
        ON CONFLICT (ticker, ts, timeframe) DO UPDATE SET
            behavior_vector   = EXCLUDED.behavior_vector,
            active_behaviors  = EXCLUDED.active_behaviors,
            behavior_count    = EXCLUDED.behavior_count,
            feature_vector    = EXCLUDED.feature_vector,
            feature_version   = EXCLUDED.feature_version
    """)

    written = 0
    with engine.begin() as conn:
        for start in range(0, len(rows_out), BATCH_SIZE):
            batch = rows_out[start: start + BATCH_SIZE]
            conn.execute(sql, batch)
            written += len(batch)
    return written


def _f(row, key, default=None):
    v = row.get(key) if hasattr(row, "get") else getattr(row, key, None)
    if v is None:
        return default
    try:
        f = float(v)
        return None if f != f else f
    except (TypeError, ValueError):
        return default


def _i(row, key, default=None):
    v = _f(row, key)
    return None if v is None else int(v)


def main():
    parser = argparse.ArgumentParser(description="Build intraday_candle_memory_v2")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to process (default: all in v1 candle memory)")
    parser.add_argument("--incremental", action="store_true",
                        help="Only process candles not yet in v2")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    # Determine tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        with engine.connect() as c:
            rows = c.execute(text(
                "SELECT DISTINCT ticker FROM intraday_candle_memory ORDER BY ticker"
            )).fetchall()
        tickers = [r[0] for r in rows]

    print(f"Building intraday_candle_memory_v2 for {len(tickers)} tickers "
          f"({'incremental' if args.incremental else 'full'})...")

    print("  Loading behavior event map...")
    bmap = _load_behavior_map(engine, tickers)
    print(f"  {len(bmap):,} (ticker, date) pairs with behavior data.")

    total = 0
    for i, ticker in enumerate(tickers, 1):
        n = _process_ticker(engine, ticker, bmap, args.incremental)
        total += n
        if n > 0:
            print(f"  [{i}/{len(tickers)}] {ticker}: {n:,} rows upserted")
        elif i % 5 == 0:
            print(f"  [{i}/{len(tickers)}] {ticker}: already up to date")

    print(f"\nDone. {total:,} total rows written to intraday_candle_memory_v2.")

    # Summary stats
    with engine.connect() as c:
        r = c.execute(text(
            "SELECT COUNT(*), COUNT(DISTINCT ticker), "
            "SUM(behavior_count) / NULLIF(COUNT(*), 0)::float "
            "FROM intraday_candle_memory_v2"
        )).fetchone()
        print(f"v2 table: {r[0]:,} rows, {r[1]} tickers, "
              f"avg {r[2]:.2f} active behaviors/candle")


if __name__ == "__main__":
    main()
