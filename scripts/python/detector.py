"""
Atlas Behavior Analysis - Step 2: Behavior Detector
=====================================================
Scans raw_bars for each active behavior definition and writes detections
to detected_behaviors.

All features are computed with strictly backward-looking rolling windows.
No forward data is used.

Usage:
    python scripts/python/detector.py
    python scripts/python/detector.py --tickers SPY QQQ AAPL TSLA NVDA --days 30
    python scripts/python/detector.py --days 90
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

BATCH_SIZE    = 500
MIN_BARS      = 210   # need ~200 bars for EMA200 warmup


# ---------------------------------------------------------------------------
# Feature computation
# ---------------------------------------------------------------------------

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute technical features from daily OHLCV. Strictly backward-looking."""
    df = df.copy().sort_values("date").reset_index(drop=True)

    # EMAs
    df["ema20"]  = df["close"].ewm(span=20,  adjust=False).mean()
    df["ema50"]  = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI(14) via EWM
    delta = df["close"].diff()
    gains = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    df["rsi14"] = 100 - 100 / (
        1 + gains.ewm(span=14, adjust=False).mean() /
        loss.ewm(span=14, adjust=False).mean().replace(0, np.nan)
    )

    # MACD (12/26/9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]        = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()

    # ATR(14)
    prev_close  = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["atr14"]    = tr.ewm(span=14, adjust=False).mean()
    df["atr14_ma"] = df["atr14"].rolling(20).mean()

    # Volume
    df["vol_ma20"] = df["volume"].rolling(20).mean().clip(lower=1)
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]

    # Gap from prior close
    df["prior_close"] = df["close"].shift(1)
    df["gap_pct"] = (df["open"] - df["prior_close"]) / df["prior_close"].replace(0, np.nan) * 100

    # Daily return and range
    df["daily_return"] = (df["close"] - df["prior_close"]) / df["prior_close"].replace(0, np.nan) * 100
    df["range_pct"]    = (df["high"] - df["low"]) / df["open"].replace(0, np.nan) * 100

    # 52-week high (rolling 260 trading days)
    df["hi_260"] = df["high"].rolling(260, min_periods=40).max()

    return df


# ---------------------------------------------------------------------------
# Behavior detection functions
# ---------------------------------------------------------------------------
# Each function takes a row (pd.Series) or pre-computed scalars and returns
# (bool, float) = (detected, intensity 0-1)

def detect_gap_up_large(r) -> tuple[bool, float]:
    g = r.get("gap_pct")
    if g is None or g != g: return False, 0.0
    return g >= 2.0, min(g / 5.0, 1.0)

def detect_gap_up_small(r) -> tuple[bool, float]:
    g = r.get("gap_pct")
    if g is None or g != g: return False, 0.0
    return (0.5 <= g < 2.0), min((g - 0.5) / 1.5, 1.0) if 0.5 <= g < 2.0 else 0.0

def detect_gap_down_large(r) -> tuple[bool, float]:
    g = r.get("gap_pct")
    if g is None or g != g: return False, 0.0
    return g <= -2.0, min(abs(g) / 5.0, 1.0)

def detect_gap_down_small(r) -> tuple[bool, float]:
    g = r.get("gap_pct")
    if g is None or g != g: return False, 0.0
    return (-2.0 < g <= -0.5), min((abs(g) - 0.5) / 1.5, 1.0) if -2.0 < g <= -0.5 else 0.0

def detect_above_all_emas(r) -> tuple[bool, float]:
    c, e20, e50, e200 = r.get("close"), r.get("ema20"), r.get("ema50"), r.get("ema200")
    if any(v is None or (v != v) for v in [c, e20, e50, e200]):
        return False, 0.0
    ok = c > e20 and c > e50 and c > e200
    dist = (c - e200) / e200 * 100 if ok and e200 else 0.0
    return ok, min(abs(dist) / 10.0, 1.0)

def detect_below_all_emas(r) -> tuple[bool, float]:
    c, e20, e50, e200 = r.get("close"), r.get("ema20"), r.get("ema50"), r.get("ema200")
    if any(v is None or (v != v) for v in [c, e20, e50, e200]):
        return False, 0.0
    ok = c < e20 and c < e50 and c < e200
    dist = (e200 - c) / e200 * 100 if ok and e200 else 0.0
    return ok, min(abs(dist) / 10.0, 1.0)

def detect_golden_cross(r) -> tuple[bool, float]:
    e50, e200, e50_p, e200_p = r.get("ema50"), r.get("ema200"), r.get("ema50_prev"), r.get("ema200_prev")
    if any(v is None or (v != v) for v in [e50, e200, e50_p, e200_p]):
        return False, 0.0
    cross = (e50 > e200) and (e50_p <= e200_p)
    return cross, 1.0 if cross else 0.0

def detect_death_cross(r) -> tuple[bool, float]:
    e50, e200, e50_p, e200_p = r.get("ema50"), r.get("ema200"), r.get("ema50_prev"), r.get("ema200_prev")
    if any(v is None or (v != v) for v in [e50, e200, e50_p, e200_p]):
        return False, 0.0
    cross = (e50 < e200) and (e50_p >= e200_p)
    return cross, 1.0 if cross else 0.0

def detect_near_52w_high(r) -> tuple[bool, float]:
    c, hi260 = r.get("close"), r.get("hi_260")
    if c is None or hi260 is None or hi260 != hi260 or hi260 == 0:
        return False, 0.0
    pct_below = (hi260 - c) / hi260 * 100
    ok = pct_below <= 3.0
    return ok, max(0.0, 1.0 - pct_below / 3.0) if ok else 0.0

def detect_inside_day(r) -> tuple[bool, float]:
    hi, lo, hi_p, lo_p = r.get("high"), r.get("low"), r.get("high_prev"), r.get("low_prev")
    if any(v is None or (v != v) for v in [hi, lo, hi_p, lo_p]):
        return False, 0.0
    ok = hi <= hi_p and lo >= lo_p
    return ok, 1.0 if ok else 0.0

def detect_rsi_oversold_reclaim(r) -> tuple[bool, float]:
    rsi = r.get("rsi14")
    rsi_min3 = r.get("rsi_min3")
    if rsi is None or rsi_min3 is None or rsi != rsi:
        return False, 0.0
    ok = rsi >= 40 and rsi_min3 < 30
    return ok, min((rsi - 40) / 20.0, 1.0) if ok else 0.0

def detect_rsi_overbought(r) -> tuple[bool, float]:
    rsi = r.get("rsi14")
    rsi_p = r.get("rsi14_prev")
    if rsi is None or rsi != rsi:
        return False, 0.0
    ok = rsi > 70 and (rsi_p is not None and rsi_p > 70)
    return ok, min((rsi - 70) / 15.0, 1.0) if ok else 0.0

def detect_macd_bull_cross(r) -> tuple[bool, float]:
    m, s, mp, sp = r.get("macd"), r.get("macd_signal"), r.get("macd_prev"), r.get("macd_signal_prev")
    if any(v is None or (v != v) for v in [m, s, mp, sp]):
        return False, 0.0
    ok = (m > s) and (mp <= sp)
    return ok, 1.0 if ok else 0.0

def detect_macd_bear_cross(r) -> tuple[bool, float]:
    m, s, mp, sp = r.get("macd"), r.get("macd_signal"), r.get("macd_prev"), r.get("macd_signal_prev")
    if any(v is None or (v != v) for v in [m, s, mp, sp]):
        return False, 0.0
    ok = (m < s) and (mp >= sp)
    return ok, 1.0 if ok else 0.0

def detect_vol_surge_bull(r) -> tuple[bool, float]:
    vr = r.get("vol_ratio")
    dr = r.get("daily_return")
    if vr is None or dr is None or vr != vr:
        return False, 0.0
    ok = vr >= 2.5 and dr > 0
    return ok, min(vr / 5.0, 1.0) if ok else 0.0

def detect_vol_surge_bear(r) -> tuple[bool, float]:
    vr = r.get("vol_ratio")
    dr = r.get("daily_return")
    if vr is None or dr is None or vr != vr:
        return False, 0.0
    ok = vr >= 2.5 and dr < 0
    return ok, min(vr / 5.0, 1.0) if ok else 0.0

def detect_low_vol_drift_up(r) -> tuple[bool, float]:
    vr = r.get("vol_ratio")
    dr = r.get("daily_return")
    if vr is None or dr is None or vr != vr:
        return False, 0.0
    ok = dr >= 0.5 and vr < 0.70
    return ok, max(0.0, 1.0 - vr / 0.7) if ok else 0.0

def detect_atr_squeeze(r) -> tuple[bool, float]:
    atr, atr_ma = r.get("atr14"), r.get("atr14_ma")
    if atr is None or atr_ma is None or atr_ma == 0 or atr_ma != atr_ma:
        return False, 0.0
    ratio = atr / atr_ma
    ok = ratio < 0.70
    return ok, max(0.0, 1.0 - ratio / 0.7) if ok else 0.0

def detect_atr_expansion(r) -> tuple[bool, float]:
    atr, atr_ma = r.get("atr14"), r.get("atr14_ma")
    if atr is None or atr_ma is None or atr_ma == 0 or atr_ma != atr_ma:
        return False, 0.0
    ratio = atr / atr_ma
    ok = ratio > 1.50
    return ok, min((ratio - 1.0) / 1.0, 1.0) if ok else 0.0

def detect_large_daily_range(r) -> tuple[bool, float]:
    rp = r.get("range_pct")
    if rp is None or rp != rp:
        return False, 0.0
    ok = rp > 3.0
    return ok, min(rp / 6.0, 1.0) if ok else 0.0


DETECTOR_MAP: dict[str, callable] = {
    "GAP_UP_LARGE":         detect_gap_up_large,
    "GAP_UP_SMALL":         detect_gap_up_small,
    "GAP_DOWN_LARGE":       detect_gap_down_large,
    "GAP_DOWN_SMALL":       detect_gap_down_small,
    "ABOVE_ALL_EMAS":       detect_above_all_emas,
    "BELOW_ALL_EMAS":       detect_below_all_emas,
    "GOLDEN_CROSS":         detect_golden_cross,
    "DEATH_CROSS":          detect_death_cross,
    "NEAR_52W_HIGH":        detect_near_52w_high,
    "INSIDE_DAY":           detect_inside_day,
    "RSI_OVERSOLD_RECLAIM": detect_rsi_oversold_reclaim,
    "RSI_OVERBOUGHT":       detect_rsi_overbought,
    "MACD_BULL_CROSS":      detect_macd_bull_cross,
    "MACD_BEAR_CROSS":      detect_macd_bear_cross,
    "VOL_SURGE_BULL":       detect_vol_surge_bull,
    "VOL_SURGE_BEAR":       detect_vol_surge_bear,
    "LOW_VOL_DRIFT_UP":     detect_low_vol_drift_up,
    "ATR_SQUEEZE":          detect_atr_squeeze,
    "ATR_EXPANSION":        detect_atr_expansion,
    "LARGE_DAILY_RANGE":    detect_large_daily_range,
}


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def add_prev_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add lagged columns needed by some detectors."""
    df["ema50_prev"]        = df["ema50"].shift(1)
    df["ema200_prev"]       = df["ema200"].shift(1)
    df["high_prev"]         = df["high"].shift(1)
    df["low_prev"]          = df["low"].shift(1)
    df["rsi14_prev"]        = df["rsi14"].shift(1)
    df["macd_prev"]         = df["macd"].shift(1)
    df["macd_signal_prev"]  = df["macd_signal"].shift(1)
    # RSI min over last 3 bars (excluding current) for oversold reclaim
    df["rsi_min3"]          = df["rsi14"].shift(1).rolling(3).min()
    return df


def process_ticker(ticker: str, bars_df: pd.DataFrame,
                   active_behaviors: list[str],
                   since_date: date | None) -> list[dict]:
    if len(bars_df) < MIN_BARS:
        return []

    feat = compute_features(bars_df)
    feat = add_prev_fields(feat)

    # Filter to only rows in the analysis window
    if since_date is not None:
        feat = feat[feat["date"] >= since_date]
    if feat.empty:
        return []

    detections = []
    for _, row in feat.iterrows():
        r = row.to_dict()
        for bid in active_behaviors:
            fn = DETECTOR_MAP.get(bid)
            if fn is None:
                continue
            try:
                detected, intensity = fn(r)
            except Exception:
                continue
            if detected:
                detections.append({
                    "ticker":         ticker,
                    "detection_date": row["date"],
                    "behavior_id":    bid,
                    "intensity":      float(intensity),
                })
    return detections


def upsert_detections(engine, rows: list[dict]) -> int:
    if not rows:
        return 0
    sql = text("""
        INSERT INTO detected_behaviors (ticker, detection_date, behavior_id, intensity)
        VALUES (:ticker, :detection_date, :behavior_id, :intensity)
        ON CONFLICT (ticker, detection_date, behavior_id) DO UPDATE SET
            intensity = EXCLUDED.intensity
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Detect behaviors in historical daily bars")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to scan (default: all in securities table)")
    parser.add_argument("--days", type=int, default=30,
                        help="Days of lookback for detection window (default: 30)")
    args = parser.parse_args()

    engine  = create_engine(os.environ["DATABASE_URL"])
    since   = date.today() - timedelta(days=args.days)
    # Need extra history for rolling windows (EMA200 needs ~200 bars warmup)
    load_from = since - timedelta(days=400)

    # Load active behaviors
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT behavior_id FROM behavior_definitions WHERE active = true ORDER BY behavior_id"
        )).fetchall()
    active_behaviors = [r[0] for r in rows]
    if not active_behaviors:
        print("No active behaviors found. Run seed_behaviors.py first.")
        return

    # Load tickers
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT DISTINCT ticker FROM raw_bars WHERE date >= :d ORDER BY ticker",
            ), {"d": load_from}).fetchall()
        tickers = [r[0] for r in rows]

    print(f"Detecting {len(active_behaviors)} behaviors in {len(tickers)} tickers "
          f"({since} to today, loading bars from {load_from})")

    total_detections = 0
    for i, ticker in enumerate(tickers, 1):
        bars = pd.read_sql(
            text(f"SELECT date, open, high, low, close, volume FROM raw_bars "
                 f"WHERE ticker = '{ticker}' AND date >= :d ORDER BY date"),
            engine, params={"d": load_from},
        )
        if bars.empty:
            continue
        bars["date"] = pd.to_datetime(bars["date"]).dt.date

        dets = process_ticker(ticker, bars, active_behaviors, since)
        if dets:
            for start in range(0, len(dets), BATCH_SIZE):
                upsert_detections(engine, dets[start: start + BATCH_SIZE])
            total_detections += len(dets)
            print(f"  [{i}/{len(tickers)}] {ticker}: {len(dets)} detections")
        elif i % 100 == 0:
            print(f"  [{i}/{len(tickers)}] {ticker}: 0")

    print(f"\nDone. {total_detections} total detections written.")


if __name__ == "__main__":
    main()
