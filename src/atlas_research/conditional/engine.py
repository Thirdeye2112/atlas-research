"""
Conditional probability backtesting engine.

Loads patterns from conditional_patterns, evaluates each condition against
raw_bars, computes forward-return statistics, and upserts results into
conditional_pattern_results.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any

import numpy as np
from sqlalchemy import text

from atlas_research.db.connection import get_raw_engine
from atlas_research.features import omni_proxy


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class Pattern:
    id: int
    name: str
    condition_type: str
    universe: str
    condition_params: dict
    horizons: list[int]
    min_sample_size: int


@dataclass
class Bar:
    ticker: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ── RSI helper ────────────────────────────────────────────────────────────────

def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100.0 - (100.0 / (1.0 + rs))


# ── Condition evaluators ──────────────────────────────────────────────────────

def _eval_consecutive_down(bars: list[Bar], params: dict) -> list[int]:
    n = int(params.get("n_days", 3))
    hits = []
    for i in range(n, len(bars)):
        if all(bars[i - k].close < bars[i - k - 1].close for k in range(n)):
            hits.append(i)
    return hits


def _eval_consecutive_up(bars: list[Bar], params: dict) -> list[int]:
    n = int(params.get("n_days", 3))
    hits = []
    for i in range(n, len(bars)):
        if all(bars[i - k].close > bars[i - k - 1].close for k in range(n)):
            hits.append(i)
    return hits


def _eval_oversold_rsi(bars: list[Bar], params: dict) -> list[int]:
    threshold = float(params.get("threshold", 30))
    closes = [b.close for b in bars]
    hits = []
    for i in range(15, len(bars)):
        r = _rsi(closes[: i + 1])
        if r is not None and r < threshold:
            hits.append(i)
    return hits


def _eval_overbought_rsi(bars: list[Bar], params: dict) -> list[int]:
    threshold = float(params.get("threshold", 70))
    closes = [b.close for b in bars]
    hits = []
    for i in range(15, len(bars)):
        r = _rsi(closes[: i + 1])
        if r is not None and r > threshold:
            hits.append(i)
    return hits


def _eval_gap_down(bars: list[Bar], params: dict) -> list[int]:
    min_gap = float(params.get("min_gap_pct", 2.0)) / 100.0
    hits = []
    for i in range(1, len(bars)):
        gap = (bars[i].open - bars[i - 1].close) / bars[i - 1].close
        if gap <= -min_gap:
            hits.append(i)
    return hits


def _eval_gap_up(bars: list[Bar], params: dict) -> list[int]:
    min_gap = float(params.get("min_gap_pct", 2.0)) / 100.0
    hits = []
    for i in range(1, len(bars)):
        gap = (bars[i].open - bars[i - 1].close) / bars[i - 1].close
        if gap >= min_gap:
            hits.append(i)
    return hits


def _eval_near_52w_low(bars: list[Bar], params: dict) -> list[int]:
    within_pct = float(params.get("within_pct", 5.0)) / 100.0
    hits = []
    lookback = min(252, len(bars))
    for i in range(lookback, len(bars)):
        window_low = min(b.low for b in bars[i - lookback: i])
        if window_low > 0 and (bars[i].close - window_low) / window_low <= within_pct:
            hits.append(i)
    return hits


def _eval_near_52w_high(bars: list[Bar], params: dict) -> list[int]:
    within_pct = float(params.get("within_pct", 5.0)) / 100.0
    hits = []
    lookback = min(252, len(bars))
    for i in range(lookback, len(bars)):
        window_high = max(b.high for b in bars[i - lookback: i])
        if window_high > 0 and (window_high - bars[i].close) / window_high <= within_pct:
            hits.append(i)
    return hits


def _eval_high_volume(bars: list[Bar], params: dict) -> list[int]:
    multiplier = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    hits = []
    for i in range(lookback, len(bars)):
        avg_vol = sum(b.volume for b in bars[i - lookback: i]) / lookback
        if avg_vol > 0 and bars[i].volume >= multiplier * avg_vol:
            hits.append(i)
    return hits


def _eval_nr7(bars: list[Bar], params: dict) -> list[int]:
    lookback = int(params.get("lookback", 7))
    hits = []
    for i in range(lookback - 1, len(bars)):
        today_range = bars[i].high - bars[i].low
        if today_range <= 0:
            continue
        prior_ranges = [bars[i - k].high - bars[i - k].low for k in range(1, lookback)]
        if all(today_range < r for r in prior_ranges):
            hits.append(i)
    return hits


def _eval_breakout_52w_high(bars: list[Bar], params: dict) -> list[int]:
    lookback = min(252, len(bars))
    hits = []
    for i in range(lookback, len(bars)):
        prior_high = max(b.high for b in bars[i - lookback: i])
        if bars[i].close > prior_high:
            hits.append(i)
    return hits


def _eval_volume_climax_down(bars: list[Bar], params: dict) -> list[int]:
    multiplier = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    hits = []
    for i in range(lookback, len(bars)):
        avg_vol = sum(b.volume for b in bars[i - lookback: i]) / lookback
        if avg_vol > 0 and bars[i].volume >= multiplier * avg_vol and bars[i].close < bars[i].open:
            hits.append(i)
    return hits


def _eval_volume_climax_up(bars: list[Bar], params: dict) -> list[int]:
    multiplier = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    hits = []
    for i in range(lookback, len(bars)):
        avg_vol = sum(b.volume for b in bars[i - lookback: i]) / lookback
        if avg_vol > 0 and bars[i].volume >= multiplier * avg_vol and bars[i].close > bars[i].open:
            hits.append(i)
    return hits


def _eval_above_level(bars: list[Bar], params: dict) -> list[int]:
    threshold = float(params.get("threshold", 30.0))
    return [i for i, b in enumerate(bars) if b.close > threshold]


def _sma(closes: list[float], period: int, end_idx: int) -> float | None:
    if end_idx < period:
        return None
    window = closes[end_idx - period: end_idx]
    return sum(window) / period


def _eval_below_sma(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 200))
    closes = [b.close for b in bars]
    hits = []
    for i in range(period, len(bars)):
        sma = _sma(closes, period, i)
        if sma is not None and bars[i].close < sma:
            hits.append(i)
    return hits


def _eval_above_sma(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 50))
    closes = [b.close for b in bars]
    hits = []
    for i in range(period, len(bars)):
        sma = _sma(closes, period, i)
        if sma is not None and bars[i].close > sma:
            hits.append(i)
    return hits


def _eval_end_of_month(bars: list[Bar], params: dict) -> list[int]:
    n = int(params.get("n_days", 3))
    hits = []
    # Group bar indices by year-month
    from collections import defaultdict
    month_groups: dict[str, list[int]] = defaultdict(list)
    for i, b in enumerate(bars):
        ym = b.date[:7]  # "YYYY-MM"
        month_groups[ym].append(i)
    for indices in month_groups.values():
        for idx in indices[-n:]:
            hits.append(idx)
    return sorted(hits)


def _eval_turn_of_month(bars: list[Bar], params: dict) -> list[int]:
    n = int(params.get("n_days", 3))
    hits = []
    from collections import defaultdict
    month_groups: dict[str, list[int]] = defaultdict(list)
    for i, b in enumerate(bars):
        ym = b.date[:7]
        month_groups[ym].append(i)
    for indices in month_groups.values():
        for idx in indices[:n]:
            hits.append(idx)
    return sorted(hits)


def _eval_day_of_week(bars: list[Bar], params: dict) -> list[int]:
    import datetime
    weekday = int(params.get("weekday", 0))  # 0=Mon, 4=Fri
    hits = []
    for i, b in enumerate(bars):
        try:
            d = datetime.date.fromisoformat(b.date[:10])
            if d.weekday() == weekday:
                hits.append(i)
        except ValueError:
            pass
    return hits


def _bars_to_arrays(bars: list[Bar]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    close = np.array([b.close for b in bars], dtype=np.float64)
    high  = np.array([b.high  for b in bars], dtype=np.float64)
    low   = np.array([b.low   for b in bars], dtype=np.float64)
    return close, high, low


def _eval_omni_cross_up(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.omni_cross_up_indices(close, period)


def _eval_omni_cross_down(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.omni_cross_down_indices(close, period)


def _eval_ema_lows_cross_up(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, low = _bars_to_arrays(bars)
    return omni_proxy.ema_lows_cross_up_indices(low, close, period)


def _eval_ema_lows_cross_down(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, low = _bars_to_arrays(bars)
    return omni_proxy.ema_lows_cross_down_indices(low, close, period)


def _eval_ema_lows_support(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    touch_pct = float(params.get("touch_pct", 0.005))
    close, _, low = _bars_to_arrays(bars)
    open_ = np.array([b.open for b in bars], dtype=np.float64)
    return omni_proxy.ema_lows_support_indices(low, close, open_, period, touch_pct)


def _eval_hma_cross_up(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.hma_cross_up_indices(close, period)


def _eval_hma_cross_down(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.hma_cross_down_indices(close, period)


def _eval_omni_green_nd(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    n_days = int(params.get("n_days", 3))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.omni_above_nd_indices(close, period, n_days)


def _eval_omni_red_nd(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    n_days = int(params.get("n_days", 3))
    close, _, _ = _bars_to_arrays(bars)
    return omni_proxy.omni_below_nd_indices(close, period, n_days)


def _eval_oscar_cross_up(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, high, low = _bars_to_arrays(bars)
    return omni_proxy.oscar_cross_up_indices(high, low, close, period)


def _eval_oscar_cross_down(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, high, low = _bars_to_arrays(bars)
    return omni_proxy.oscar_cross_down_indices(high, low, close, period)


def _eval_oscar_above_50(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 87))
    close, high, low = _bars_to_arrays(bars)
    return omni_proxy.oscar_above_50_indices(high, low, close, period)


def _eval_ema_lows_above_nd(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 82))
    n_days = int(params.get("n_days", 3))
    close, _, low = _bars_to_arrays(bars)
    return omni_proxy.ema_lows_above_nd_indices(low, close, period, n_days)


def _eval_ema_lows_green_slope(bars: list[Bar], params: dict) -> list[int]:
    period = int(params.get("period", 82))
    slope_bars = int(params.get("slope_bars", 5))
    close, _, low = _bars_to_arrays(bars)
    return omni_proxy.ema_lows_green_slope_indices(low, close, period, slope_bars)


# ── Calendar evaluators ───────────────────────────────────────────────────────
# These query market_calendar for event dates. Results are module-level cached
# so subsequent tickers in the same run don't re-query the DB.

_calendar_cache: dict[str, set[str]] = {}


def _load_calendar_dates(event_type: str, proximity_days: int = 0) -> set[str]:
    import datetime
    cache_key = f"{event_type}:{proximity_days}"
    if cache_key in _calendar_cache:
        return _calendar_cache[cache_key]
    try:
        with get_raw_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT date::text FROM market_calendar WHERE event_type = :et ORDER BY date"
            ), {"et": event_type}).fetchall()
    except Exception:
        _calendar_cache[cache_key] = set()
        return set()
    if proximity_days == 0:
        result: set[str] = {r[0] for r in rows}
    else:
        result = set()
        for r in rows:
            d = datetime.date.fromisoformat(r[0])
            for off in range(-proximity_days, proximity_days + 1):
                result.add((d + datetime.timedelta(days=off)).isoformat())
    _calendar_cache[cache_key] = result
    return result


def _eval_fomc_proximity(bars: list[Bar], params: dict) -> list[int]:
    proximity = int(params.get("proximity_days", 0))
    fomc_dates = _load_calendar_dates("fomc_meeting", proximity_days=proximity)
    return [i for i, b in enumerate(bars) if b.date[:10] in fomc_dates]


def _eval_opex_week(bars: list[Bar], params: dict) -> list[int]:
    import datetime
    opex_dates = _load_calendar_dates("options_expiry")
    opex_weeks: set[str] = set()
    for ds in opex_dates:
        d = datetime.date.fromisoformat(ds)
        monday = d - datetime.timedelta(days=d.weekday())
        opex_weeks.add(monday.isoformat())
    hits = []
    for i, b in enumerate(bars):
        d = datetime.date.fromisoformat(b.date[:10])
        monday = d - datetime.timedelta(days=d.weekday())
        if monday.isoformat() in opex_weeks:
            hits.append(i)
    return hits


def _eval_triple_witching_week(bars: list[Bar], params: dict) -> list[int]:
    import datetime
    tw_dates = _load_calendar_dates("triple_witching")
    tw_weeks: set[str] = set()
    for ds in tw_dates:
        d = datetime.date.fromisoformat(ds)
        monday = d - datetime.timedelta(days=d.weekday())
        tw_weeks.add(monday.isoformat())
    hits = []
    for i, b in enumerate(bars):
        d = datetime.date.fromisoformat(b.date[:10])
        monday = d - datetime.timedelta(days=d.weekday())
        if monday.isoformat() in tw_weeks:
            hits.append(i)
    return hits


# ── Sector rotation evaluators ────────────────────────────────────────────────
# Query sector_relative_strength once per sector ticker, cache results.

_sector_rank_cache: dict[str, dict[str, int]] = {}
_sector_rs20d_cache: dict[str, dict[str, float]] = {}


def _load_sector_ranks(sector_ticker: str) -> dict[str, int]:
    if sector_ticker in _sector_rank_cache:
        return _sector_rank_cache[sector_ticker]
    try:
        with get_raw_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT date::text, rank_among_sectors
                FROM sector_relative_strength
                WHERE sector_ticker = :t AND rank_among_sectors IS NOT NULL
                ORDER BY date
            """), {"t": sector_ticker}).fetchall()
    except Exception:
        _sector_rank_cache[sector_ticker] = {}
        return {}
    result = {r[0]: int(r[1]) for r in rows}
    _sector_rank_cache[sector_ticker] = result
    return result


def _load_sector_rs20d(sector_ticker: str) -> dict[str, float]:
    if sector_ticker in _sector_rs20d_cache:
        return _sector_rs20d_cache[sector_ticker]
    try:
        with get_raw_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT date::text, rs_vs_spy_20d
                FROM sector_relative_strength
                WHERE sector_ticker = :t AND rs_vs_spy_20d IS NOT NULL
                ORDER BY date
            """), {"t": sector_ticker}).fetchall()
    except Exception:
        _sector_rs20d_cache[sector_ticker] = {}
        return {}
    result = {r[0]: float(r[1]) for r in rows}
    _sector_rs20d_cache[sector_ticker] = result
    return result


def _eval_sector_leading_nd(bars: list[Bar], params: dict) -> list[int]:
    sector_ticker = str(params.get("sector_ticker", "XLV"))
    rank_threshold = int(params.get("rank_threshold", 2))
    n_days = int(params.get("n_days", 20))
    rank_by_date = _load_sector_ranks(sector_ticker)
    if not rank_by_date:
        return []
    hits = []
    for i in range(n_days - 1, len(bars)):
        if all(rank_by_date.get(bars[i - k].date[:10], 99) <= rank_threshold
               for k in range(n_days)):
            hits.append(i)
    return hits


def _eval_xly_vs_xlp(bars: list[Bar], params: dict) -> list[int]:
    xly_rs = _load_sector_rs20d("XLY")
    xlp_rs = _load_sector_rs20d("XLP")
    if not xly_rs or not xlp_rs:
        return []
    hits = []
    for i, b in enumerate(bars):
        dt = b.date[:10]
        if dt in xly_rs and dt in xlp_rs and xly_rs[dt] > xlp_rs[dt]:
            hits.append(i)
    return hits


def _eval_iwm_vs_spy(bars: list[Bar], params: dict) -> list[int]:
    outperform_pct = float(params.get("outperform_pct", 2.0)) / 100.0
    n_days = int(params.get("n_days", 10))
    try:
        with get_raw_engine().connect() as conn:
            iwm_rows = conn.execute(text(
                "SELECT date::text, close FROM raw_bars WHERE ticker='IWM' ORDER BY date"
            )).fetchall()
            spy_rows = conn.execute(text(
                "SELECT date::text, close FROM raw_bars WHERE ticker='SPY' ORDER BY date"
            )).fetchall()
    except Exception:
        return []
    iwm_close = {r[0]: float(r[1]) for r in iwm_rows}
    spy_close = {r[0]: float(r[1]) for r in spy_rows}
    dates_sorted = sorted(set(iwm_close) & set(spy_close))
    date_idx = {d: i for i, d in enumerate(dates_sorted)}
    iwm_arr = [iwm_close[d] for d in dates_sorted]
    spy_arr = [spy_close[d] for d in dates_sorted]

    # Find dates where IWM n_days return > SPY n_days return + outperform_pct
    outperforming_dates: set[str] = set()
    for j in range(n_days, len(dates_sorted)):
        iwm_ret = (iwm_arr[j] - iwm_arr[j - n_days]) / iwm_arr[j - n_days]
        spy_ret = (spy_arr[j] - spy_arr[j - n_days]) / spy_arr[j - n_days]
        if iwm_ret - spy_ret >= outperform_pct:
            outperforming_dates.add(dates_sorted[j])

    return [i for i, b in enumerate(bars) if b.date[:10] in outperforming_dates]


_EVALUATORS = {
    "consecutive_down":  _eval_consecutive_down,
    "consecutive_up":    _eval_consecutive_up,
    "oversold_rsi":      _eval_oversold_rsi,
    "overbought_rsi":    _eval_overbought_rsi,
    "gap_down":          _eval_gap_down,
    "gap_up":            _eval_gap_up,
    "near_52w_low":      _eval_near_52w_low,
    "near_52w_high":     _eval_near_52w_high,
    "high_volume":       _eval_high_volume,
    "nr7":               _eval_nr7,
    "breakout_52w_high": _eval_breakout_52w_high,
    "volume_climax_down":_eval_volume_climax_down,
    "volume_climax_up":  _eval_volume_climax_up,
    "above_level":       _eval_above_level,
    "below_sma":         _eval_below_sma,
    "above_sma":         _eval_above_sma,
    "end_of_month":      _eval_end_of_month,
    "turn_of_month":     _eval_turn_of_month,
    "day_of_week":       _eval_day_of_week,
    "omni_cross_up":        _eval_omni_cross_up,
    "omni_cross_down":      _eval_omni_cross_down,
    "omni_green_nd":        _eval_omni_green_nd,
    "omni_red_nd":          _eval_omni_red_nd,
    "oscar_cross_up":       _eval_oscar_cross_up,
    "oscar_cross_down":     _eval_oscar_cross_down,
    "oscar_above_50":       _eval_oscar_above_50,
    "ema_lows_cross_up":    _eval_ema_lows_cross_up,
    "ema_lows_cross_down":  _eval_ema_lows_cross_down,
    "ema_lows_support":     _eval_ema_lows_support,
    "ema_lows_above_nd":    _eval_ema_lows_above_nd,
    "ema_lows_green_slope": _eval_ema_lows_green_slope,
    "hma_cross_up":         _eval_hma_cross_up,
    "hma_cross_down":       _eval_hma_cross_down,
    # Calendar evaluators
    "fomc_proximity":        _eval_fomc_proximity,
    "opex_week":             _eval_opex_week,
    "triple_witching_week":  _eval_triple_witching_week,
    # Sector rotation evaluators
    "sector_leading_nd":     _eval_sector_leading_nd,
    "xly_vs_xlp":            _eval_xly_vs_xlp,
    "iwm_vs_spy":            _eval_iwm_vs_spy,
}


# ── Statistics ────────────────────────────────────────────────────────────────

def _log_return(start: float, end: float) -> float | None:
    if start <= 0 or end <= 0:
        return None
    return math.log(end / start)


def _t_stat(values: list[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = statistics.mean(values)
    std = statistics.stdev(values)
    if std == 0:
        return None
    return mean / (std / math.sqrt(n))


def _stats(returns: list[float], horizon: int) -> dict:
    if not returns:
        return {}
    n = len(returns)
    mean = statistics.mean(returns)
    med = statistics.median(returns)
    std = statistics.stdev(returns) if n > 1 else 0.0
    hit_rate = sum(1 for r in returns if r > 0) / n
    sharpe = (mean / std * math.sqrt(252 / horizon)) if std > 0 else None

    # approximate p-value from t-stat (two-tailed, large-sample)
    t = _t_stat(returns)
    p_value = None
    if t is not None:
        # Normal approximation: p ≈ 2*(1 - Φ(|t|))
        # Using simple Abramowitz & Stegun approximation
        z = abs(t)
        b = 1 / (1 + 0.2316419 * z)
        poly = b * (0.319381530 + b * (-0.356563782 + b * (1.781477937 + b * (-1.821255978 + b * 1.330274429))))
        cdf_upper = (1 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * z * z) * poly
        p_value = 2 * cdf_upper

    return {
        "sample_size":   n,
        "hit_rate":      hit_rate,
        "avg_return":    mean,
        "median_return": med,
        "std_return":    std,
        "sharpe":        sharpe,
        "p_value":       p_value,
    }


# ── Main engine ───────────────────────────────────────────────────────────────

class ConditionalEngine:
    def __init__(self) -> None:
        self._engine = get_raw_engine()

    def _load_patterns(self, name: str | None = None) -> list[Pattern]:
        q = "SELECT id, name, condition_type, universe, condition_params, horizons, min_sample_size FROM conditional_patterns"
        params: dict = {}
        if name:
            q += " WHERE name = :name"
            params["name"] = name
        q += " ORDER BY id"
        with self._engine.connect() as conn:
            rows = conn.execute(text(q), params).fetchall()
        return [
            Pattern(
                id=r[0], name=r[1], condition_type=r[2], universe=r[3],
                condition_params=r[4] or {}, horizons=list(r[5] or [1, 5, 10, 20]),
                min_sample_size=r[6] or 30,
            )
            for r in rows
        ]

    def _load_tickers(self, universe: str) -> list[str]:
        # Single-ticker universe (e.g. "SPY") — verify it exists in raw_bars
        if universe and universe.upper() == universe and len(universe) <= 5 and universe not in ("SP500", "ALL"):
            with self._engine.connect() as conn:
                row = conn.execute(text(
                    "SELECT COUNT(*) FROM raw_bars WHERE ticker = :t"
                ), {"t": universe}).fetchone()
            if row and row[0] > 0:
                return [universe]
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT DISTINCT ticker FROM raw_bars ORDER BY ticker"
            )).fetchall()
        return [r[0] for r in rows]

    def _load_bars(self, ticker: str) -> list[Bar]:
        with self._engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT ticker, date::text, open, high, low, close, volume "
                "FROM raw_bars WHERE ticker = :ticker ORDER BY date"
            ), {"ticker": ticker}).fetchall()
        return [Bar(ticker=r[0], date=r[1], open=float(r[2] or 0),
                    high=float(r[3] or 0), low=float(r[4] or 0),
                    close=float(r[5] or 0), volume=float(r[6] or 0))
                for r in rows]

    def _upsert_result(self, pattern_id: int, ticker: str | None, horizon: int, stats: dict) -> None:
        if not stats:
            return
        with self._engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO conditional_pattern_results
                    (pattern_id, ticker, horizon_days, sample_size, hit_rate,
                     avg_return, median_return, std_return, sharpe, p_value, evaluated_at)
                VALUES
                    (:pid, :ticker, :horizon, :n, :hr, :avg, :med, :std, :sh, :pv, now())
                ON CONFLICT (pattern_id, COALESCE(ticker,''), horizon_days)
                DO UPDATE SET
                    sample_size   = EXCLUDED.sample_size,
                    hit_rate      = EXCLUDED.hit_rate,
                    avg_return    = EXCLUDED.avg_return,
                    median_return = EXCLUDED.median_return,
                    std_return    = EXCLUDED.std_return,
                    sharpe        = EXCLUDED.sharpe,
                    p_value       = EXCLUDED.p_value,
                    evaluated_at  = now()
            """), {
                "pid":    pattern_id,
                "ticker": ticker,
                "horizon": horizon,
                "n":      stats.get("sample_size"),
                "hr":     stats.get("hit_rate"),
                "avg":    stats.get("avg_return"),
                "med":    stats.get("median_return"),
                "std":    stats.get("std_return"),
                "sh":     stats.get("sharpe"),
                "pv":     stats.get("p_value"),
            })

    def _run_pattern_for_ticker(self, pattern: Pattern, bars: list[Bar]) -> int:
        evaluator = _EVALUATORS.get(pattern.condition_type)
        if evaluator is None or len(bars) < 30:
            return 0

        hit_indices = evaluator(bars, pattern.condition_params)
        if not hit_indices:
            return 0

        max_horizon = max(pattern.horizons)
        usable = [i for i in hit_indices if i + max_horizon < len(bars)]
        if len(usable) < pattern.min_sample_size:
            return 0

        for horizon in pattern.horizons:
            returns = []
            for i in usable:
                r = _log_return(bars[i].close, bars[i + horizon].close)
                if r is not None:
                    returns.append(r)
            if len(returns) >= pattern.min_sample_size:
                s = _stats(returns, horizon)
                self._upsert_result(pattern.id, bars[0].ticker if bars else None, horizon, s)

        return len(usable)

    def _run_pattern_aggregate(self, pattern: Pattern, all_bars: list[list[Bar]]) -> int:
        evaluator = _EVALUATORS.get(pattern.condition_type)
        if evaluator is None:
            return 0

        max_horizon = max(pattern.horizons)
        total_signals = 0
        returns_by_horizon: dict[int, list[float]] = {h: [] for h in pattern.horizons}

        for bars in all_bars:
            if len(bars) < 30:
                continue
            hit_indices = evaluator(bars, pattern.condition_params)
            usable = [i for i in hit_indices if i + max_horizon < len(bars)]
            total_signals += len(usable)
            for horizon in pattern.horizons:
                for i in usable:
                    r = _log_return(bars[i].close, bars[i + horizon].close)
                    if r is not None:
                        returns_by_horizon[horizon].append(r)

        for horizon in pattern.horizons:
            rets = returns_by_horizon[horizon]
            if len(rets) >= pattern.min_sample_size:
                s = _stats(rets, horizon)
                self._upsert_result(pattern.id, None, horizon, s)

        return total_signals

    def run_pattern(self, pattern_name: str) -> int:
        patterns = self._load_patterns(pattern_name)
        if not patterns:
            raise ValueError(f"Pattern not found: {pattern_name}")
        pattern = patterns[0]
        tickers = self._load_tickers(pattern.universe)
        all_bars = [self._load_bars(t) for t in tickers]
        all_bars = [b for b in all_bars if b]

        for bars in all_bars:
            self._run_pattern_for_ticker(pattern, bars)

        return self._run_pattern_aggregate(pattern, all_bars)

    def run_all(self) -> dict:
        patterns = self._load_patterns()
        run = 0
        failed = 0
        total_signals = 0

        for pattern in patterns:
            try:
                tickers = self._load_tickers(pattern.universe)
                all_bars = [self._load_bars(t) for t in tickers]
                all_bars = [b for b in all_bars if b]
                for bars in all_bars:
                    self._run_pattern_for_ticker(pattern, bars)
                n = self._run_pattern_aggregate(pattern, all_bars)
                total_signals += n
                run += 1
            except Exception as exc:
                print(f"  [engine] pattern '{pattern.name}' failed: {exc}")
                failed += 1

        return {"run": run, "failed": failed, "total_signals": total_signals}
