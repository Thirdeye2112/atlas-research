"""
atlas_research.probability.ipo.events
----------------------------------------
Compute and persist ipo_events rows.

All return metrics use opening_price (day1_open) as the investor entry baseline,
consistent with "what happens to someone who buys at the IPO open."

Revisit detection uses the daily CLOSE:
  days_to_revisit_open  = first bar where close <= opening_price  (0 = Day 1)
  days_to_revisit_offer = first bar where close <= offer_price    (0 = Day 1)
  NULL = never revisited within available data.

Peak analysis spans the first 252 bars:
  peak_high            = max(high) in bars 0-251
  days_to_peak         = 0-indexed position of peak bar
  retracement_from_peak = (peak_high - min_low_after_peak) / peak_high * 100
"""

from __future__ import annotations

import sys
from datetime import timedelta
from typing import Optional

from sqlalchemy import text

from atlas_research.db.connection import get_connection


# ── Bucket helpers ────────────────────────────────────────────────────────────

def _bucket_open_vs_offer(v: Optional[float]) -> Optional[str]:
    if v is None:
        return None
    if v < 0:
        return "neg"
    if v < 10:
        return "0-10"
    if v < 20:
        return "10-20"
    if v < 50:
        return "20-50"
    return "50+"


def _bucket_peak_vs_open(v: Optional[float]) -> Optional[str]:
    if v is None:
        return None
    if v < 0:
        return "neg"
    if v < 10:
        return "0-10"
    if v < 20:
        return "10-20"
    if v < 40:
        return "20-40"
    if v < 60:
        return "40-60"
    return "60+"


def _bucket_retracement(v: Optional[float]) -> Optional[str]:
    if v is None:
        return None
    if v < 10:
        return "0-10"
    if v < 25:
        return "10-25"
    if v < 50:
        return "25-50"
    return "50+"


def _f(v) -> Optional[float]:
    """Safe float cast."""
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _r(v: Optional[float], decimals: int = 2) -> Optional[float]:
    """Round or return None."""
    return round(v, decimals) if v is not None else None


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_registry() -> dict[str, dict]:
    """Load all ipo_registry rows keyed by ticker."""
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT ticker, ipo_date, ipo_price, day1_open, day1_high, day1_low,
                   day1_close, day1_volume, lockup_days
            FROM ipo_registry
            ORDER BY ticker
        """)).fetchall()
    return {
        row[0]: {
            "ipo_date":     row[1],
            "offer_price":  _f(row[2]),
            "opening_price":_f(row[3]),   # day1_open
            "day1_high":    _f(row[4]),
            "day1_low":     _f(row[5]),
            "day1_close":   _f(row[6]),
            "day1_volume":  row[7],
            "lockup_days":  int(row[8]) if row[8] else 180,
        }
        for row in rows
    }


def _load_bars_bulk() -> dict[str, list[dict]]:
    """
    Load all post-IPO bars for every ipo_registry ticker in one query.
    Returns {ticker: [sorted bars dicts]} ascending by date.
    """
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT rb.ticker, rb.date, rb.open, rb.high, rb.low, rb.close, rb.volume
            FROM raw_bars rb
            JOIN ipo_registry ir ON rb.ticker = ir.ticker AND rb.date >= ir.ipo_date
            ORDER BY rb.ticker, rb.date ASC
        """)).fetchall()

    bars_by_ticker: dict[str, list[dict]] = {}
    for row in rows:
        t = row[0]
        if t not in bars_by_ticker:
            bars_by_ticker[t] = []
        bars_by_ticker[t].append({
            "date":   row[1],
            "open":   _f(row[2]),
            "high":   _f(row[3]),
            "low":    _f(row[4]),
            "close":  _f(row[5]),
            "volume": row[6],
        })
    return bars_by_ticker


# ── Core computation ──────────────────────────────────────────────────────────

def _compute_event(ticker: str, meta: dict, bars: list[dict]) -> Optional[dict]:
    """Compute one ipo_events dict from registry meta + raw bars."""
    if not bars:
        return None

    opening_price = meta.get("opening_price")
    offer_price   = meta.get("offer_price")
    ipo_date      = meta.get("ipo_date")

    # opening_price is required; if missing use bar[0].open
    if not opening_price or opening_price <= 0:
        opening_price = _f(bars[0].get("open"))
    if not opening_price or opening_price <= 0:
        return None

    # offer_price fallback: use opening_price (spinoffs, no public offer)
    if not offer_price or offer_price <= 0:
        offer_price = opening_price

    lockup_days       = meta.get("lockup_days", 180)
    lockup_expiration = (ipo_date + timedelta(days=lockup_days)) if ipo_date else None

    # Day 1 — prefer registry values, fallback to bar[0]
    day1_high  = meta.get("day1_high")  or _f(bars[0].get("high"))
    day1_low   = meta.get("day1_low")   or _f(bars[0].get("low"))
    day1_close = meta.get("day1_close") or _f(bars[0].get("close"))

    # ── Week 1 (bars 0-4, trading days 1-5) ─────────────────────────────────
    w1 = bars[:5]
    w1_highs  = [b["high"]  for b in w1 if b.get("high")  is not None]
    w1_lows   = [b["low"]   for b in w1 if b.get("low")   is not None]
    week1_high   = max(w1_highs) if w1_highs else None
    week1_low    = min(w1_lows)  if w1_lows  else None
    week1_close  = _f(w1[4].get("close")) if len(w1) >= 5 else None
    week1_return = (week1_close / opening_price - 1) * 100 if week1_close else None

    # ── Month 1 (bars 0-20, trading days 1-21) ──────────────────────────────
    m1 = bars[:21]
    m1_highs  = [b["high"] for b in m1 if b.get("high") is not None]
    m1_lows   = [b["low"]  for b in m1 if b.get("low")  is not None]
    month1_high   = max(m1_highs) if m1_highs else None
    month1_low    = min(m1_lows)  if m1_lows  else None
    month1_close  = _f(m1[20].get("close")) if len(m1) >= 21 else None
    month1_return = (month1_close / opening_price - 1) * 100 if month1_close else None

    # ── Key Day-1 ratios ─────────────────────────────────────────────────────
    open_vs_offer = (opening_price - offer_price) / offer_price * 100
    close_vs_open = ((day1_close - opening_price) / opening_price * 100
                     if day1_close is not None else None)

    # ── Peak analysis: first 252 bars ────────────────────────────────────────
    peak_window = bars[:252]
    days_to_peak      = None
    peak_vs_open      = None
    retracement       = None

    if peak_window:
        highs = [(i, b["high"]) for i, b in enumerate(peak_window) if b.get("high") is not None]
        if highs:
            peak_idx, peak_high = max(highs, key=lambda x: x[1])
            days_to_peak = peak_idx
            peak_vs_open = (peak_high / opening_price - 1) * 100

            # Max drawdown: from peak to the lowest low in [peak_idx, 252)
            lows_after = [b["low"] for b in peak_window[peak_idx:]
                          if b.get("low") is not None]
            if lows_after and peak_high > 0:
                retracement = (peak_high - min(lows_after)) / peak_high * 100

    # ── Days to revisit (daily close crosses back through threshold) ──────────
    # days=0 means it happened on IPO Day 1 itself; NULL means never
    days_to_revisit_open = None
    for i, bar in enumerate(bars):
        c = _f(bar.get("close"))
        if c is not None and c <= opening_price:
            days_to_revisit_open = i
            break

    days_to_revisit_offer = None
    for i, bar in enumerate(bars):
        c = _f(bar.get("close"))
        if c is not None and c <= offer_price:
            days_to_revisit_offer = i
            break

    # ── Post-week1: bars 5-20 ────────────────────────────────────────────────
    post_w1 = bars[5:21]
    pw_highs = [b["high"] for b in post_w1 if b.get("high") is not None]
    pw_lows  = [b["low"]  for b in post_w1 if b.get("low")  is not None]
    post_week1_high_20d   = max(pw_highs) if pw_highs else None
    post_week1_low_20d    = min(pw_lows)  if pw_lows  else None
    post_week1_return_20d = (
        (_f(bars[20].get("close")) / week1_close - 1) * 100
        if len(bars) >= 21 and week1_close and week1_close > 0
        else None
    )

    return {
        "ticker":               ticker,
        "ipo_date":             ipo_date,
        "offer_price":          offer_price,
        "opening_price":        opening_price,
        "lockup_expiration":    lockup_expiration,
        "day1_high":            day1_high,
        "day1_low":             day1_low,
        "day1_close":           day1_close,
        "week1_high":           week1_high,
        "week1_low":            week1_low,
        "week1_close":          week1_close,
        "week1_return":         _r(week1_return),
        "month1_high":          month1_high,
        "month1_low":           month1_low,
        "month1_close":         month1_close,
        "month1_return":        _r(month1_return),
        "open_vs_offer":        _r(open_vs_offer),
        "close_vs_open":        _r(close_vs_open),
        "peak_vs_open":         _r(peak_vs_open),
        "days_to_peak":         days_to_peak,
        "retracement_from_peak": _r(retracement),
        "days_to_revisit_open": days_to_revisit_open,
        "days_to_revisit_offer": days_to_revisit_offer,
        "post_week1_high_20d":  post_week1_high_20d,
        "post_week1_low_20d":   post_week1_low_20d,
        "post_week1_return_20d": _r(post_week1_return_20d),
        "bucket_open_vs_offer": _bucket_open_vs_offer(open_vs_offer),
        "bucket_peak_vs_open":  _bucket_peak_vs_open(peak_vs_open),
        "bucket_retracement":   _bucket_retracement(retracement),
    }


# ── Public API ────────────────────────────────────────────────────────────────

_INSERT_SQL = text("""
    INSERT INTO ipo_events (
        ticker, ipo_date, offer_price, opening_price, lockup_expiration,
        day1_high, day1_low, day1_close,
        week1_high, week1_low, week1_close, week1_return,
        month1_high, month1_low, month1_close, month1_return,
        open_vs_offer, close_vs_open,
        peak_vs_open, days_to_peak, retracement_from_peak,
        days_to_revisit_open, days_to_revisit_offer,
        post_week1_high_20d, post_week1_low_20d, post_week1_return_20d,
        bucket_open_vs_offer, bucket_peak_vs_open, bucket_retracement,
        computed_at
    ) VALUES (
        :ticker, :ipo_date, :offer_price, :opening_price, :lockup_expiration,
        :day1_high, :day1_low, :day1_close,
        :week1_high, :week1_low, :week1_close, :week1_return,
        :month1_high, :month1_low, :month1_close, :month1_return,
        :open_vs_offer, :close_vs_open,
        :peak_vs_open, :days_to_peak, :retracement_from_peak,
        :days_to_revisit_open, :days_to_revisit_offer,
        :post_week1_high_20d, :post_week1_low_20d, :post_week1_return_20d,
        :bucket_open_vs_offer, :bucket_peak_vs_open, :bucket_retracement,
        now()
    )
    ON CONFLICT (ticker) DO UPDATE SET
        ipo_date               = EXCLUDED.ipo_date,
        offer_price            = EXCLUDED.offer_price,
        opening_price          = EXCLUDED.opening_price,
        lockup_expiration      = EXCLUDED.lockup_expiration,
        day1_high              = EXCLUDED.day1_high,
        day1_low               = EXCLUDED.day1_low,
        day1_close             = EXCLUDED.day1_close,
        week1_high             = EXCLUDED.week1_high,
        week1_low              = EXCLUDED.week1_low,
        week1_close            = EXCLUDED.week1_close,
        week1_return           = EXCLUDED.week1_return,
        month1_high            = EXCLUDED.month1_high,
        month1_low             = EXCLUDED.month1_low,
        month1_close           = EXCLUDED.month1_close,
        month1_return          = EXCLUDED.month1_return,
        open_vs_offer          = EXCLUDED.open_vs_offer,
        close_vs_open          = EXCLUDED.close_vs_open,
        peak_vs_open           = EXCLUDED.peak_vs_open,
        days_to_peak           = EXCLUDED.days_to_peak,
        retracement_from_peak  = EXCLUDED.retracement_from_peak,
        days_to_revisit_open   = EXCLUDED.days_to_revisit_open,
        days_to_revisit_offer  = EXCLUDED.days_to_revisit_offer,
        post_week1_high_20d    = EXCLUDED.post_week1_high_20d,
        post_week1_low_20d     = EXCLUDED.post_week1_low_20d,
        post_week1_return_20d  = EXCLUDED.post_week1_return_20d,
        bucket_open_vs_offer   = EXCLUDED.bucket_open_vs_offer,
        bucket_peak_vs_open    = EXCLUDED.bucket_peak_vs_open,
        bucket_retracement     = EXCLUDED.bucket_retracement,
        computed_at            = now()
""")


def build_all_events(verbose: bool = True) -> int:
    """
    Compute and upsert ipo_events for all ipo_registry tickers.
    Returns number of rows successfully processed.
    """
    if verbose:
        print("Loading registry and bars...", flush=True)

    registry = _load_registry()
    bars_by_ticker = _load_bars_bulk()

    if verbose:
        print(f"  {len(registry)} IPOs in registry, "
              f"{len(bars_by_ticker)} with bars data")

    ok = skip = 0
    with get_connection() as conn:
        for ticker, meta in registry.items():
            bars = bars_by_ticker.get(ticker, [])
            ev   = _compute_event(ticker, meta, bars)
            if ev is None:
                skip += 1
                if verbose:
                    print(f"  SKIP {ticker}: insufficient data", flush=True)
                continue
            conn.execute(_INSERT_SQL, ev)
            ok += 1

    if verbose:
        print(f"  Upserted: {ok}  |  Skipped: {skip}")
    return ok


def get_event(ticker: str) -> Optional[dict]:
    """Fetch one ipo_events row as a dict."""
    with get_connection() as conn:
        row = conn.execute(text(
            "SELECT * FROM ipo_events WHERE ticker = :t"
        ), {"t": ticker.upper()}).mappings().fetchone()
    return dict(row) if row else None


def load_all_events() -> list[dict]:
    """Fetch all ipo_events rows as a list of dicts."""
    with get_connection() as conn:
        rows = conn.execute(text(
            "SELECT * FROM ipo_events ORDER BY ipo_date"
        )).mappings().fetchall()
    return [dict(r) for r in rows]
