"""
atlas_research.transcripts.backtester
=======================================
Automated statistical backtester for research hypotheses.

For each queued hypothesis, this module:
1. Resolves the market_object and condition into a time series of event dates.
2. Computes forward returns on those event dates from raw_bars / parquet data.
3. Runs hit-rate, t-test, and Spearman-IC analysis.
4. Writes results to hypothesis_tests + hypothesis_results.
5. Updates test_status on research_hypotheses.

Condition handlers
------------------
Each condition maps to a Python function that returns a list of
(date, ticker) event tuples given the raw bars DataFrame.

Supported built-in conditions (extensible):
  - down_n_consecutive_days   : n consecutive down closes
  - up_n_consecutive_days     : n consecutive up closes
  - return_below_threshold    : rolling n-day return < threshold
  - return_above_threshold    : rolling n-day return > threshold
  - rsi_oversold              : RSI < threshold
  - rsi_overbought            : RSI > threshold
  - near_52w_low              : within pct% of 52-week low
  - near_52w_high             : within pct% of 52-week high
  - volatility_expansion      : realised vol spikes > n * trailing avg
  - gap_down                  : open < prior close by pct
  - gap_up                    : open > prior close by pct
  - volume_spike              : volume > n * rolling avg
  - above_sma / below_sma     : price vs moving average

Usage
-----
    from atlas_research.transcripts.backtester import HypothesisBacktester
    bt = HypothesisBacktester()
    n_ran = bt.run_queued(limit=50)
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import structlog
from scipy import stats as scipy_stats
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_SAMPLE_SIZE = 15      # minimum events for a result to be meaningful
COMPOSITE_WEIGHTS = {     # weights for composite_score
    "hit_rate":    0.30,
    "sharpe":      0.35,
    "rank_ic":     0.25,
    "sample_size": 0.10,  # log-scaled
}
PROMOTION_THRESHOLDS = {
    "min_sample_size": 20,
    "min_hit_rate":    0.55,
    "max_p_value":     0.10,
    "min_composite":   0.40,
}


# ---------------------------------------------------------------------------
# Condition handlers
# ---------------------------------------------------------------------------

def _load_bars(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    """Load OHLCV from raw_bars for given tickers and date range."""
    with get_connection() as conn:
        df = pd.read_sql(
            text("""
                SELECT ticker, date, open, high, low, close, volume
                FROM raw_bars
                WHERE ticker = ANY(:tickers)
                  AND date BETWEEN :start AND :end
                ORDER BY ticker, date
            """),
            conn,
            params={"tickers": tickers, "start": start, "end": end},
        )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _load_spy_bars(start: date, end: date) -> pd.DataFrame:
    return _load_bars(["SPY"], start, end)


def _get_universe_tickers() -> list[str]:
    """Return all active tickers from securities table."""
    with get_connection() as conn:
        rows = conn.execute(
            text("SELECT ticker FROM securities WHERE active = true ORDER BY ticker")
        ).fetchall()
    return [r[0] for r in rows]


def _condition_down_n_consecutive(
    df: pd.DataFrame,
    params: dict,
) -> list[tuple[date, str]]:
    """Events where ticker had n consecutive down closes."""
    n = int(params.get("n_days", 5))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["down"] = (grp["close"] < grp["close"].shift(1)).astype(int)
        grp["consec"] = grp["down"].groupby(
            (grp["down"] != grp["down"].shift()).cumsum()
        ).cumcount() + 1
        triggered = grp[(grp["down"] == 1) & (grp["consec"] >= n)]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_up_n_consecutive(df: pd.DataFrame, params: dict) -> list[tuple]:
    n = int(params.get("n_days", 3))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["up"] = (grp["close"] > grp["close"].shift(1)).astype(int)
        grp["consec"] = grp["up"].groupby(
            (grp["up"] != grp["up"].shift()).cumsum()
        ).cumcount() + 1
        triggered = grp[(grp["up"] == 1) & (grp["consec"] >= n)]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_return_threshold(
    df: pd.DataFrame,
    params: dict,
    above: bool,
) -> list[tuple]:
    n = int(params.get("n_days", 5))
    threshold = float(params.get("threshold", -0.05))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["ret"] = np.log(grp["close"] / grp["close"].shift(n))
        if above:
            triggered = grp[grp["ret"] > threshold]
        else:
            triggered = grp[grp["ret"] < threshold]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_rsi(df: pd.DataFrame, params: dict, oversold: bool) -> list[tuple]:
    period = int(params.get("period", 14))
    threshold = float(params.get("threshold", 30 if oversold else 70))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        delta = grp["close"].diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        grp["rsi"] = 100 - (100 / (1 + rs))
        if oversold:
            triggered = grp[grp["rsi"] < threshold]
        else:
            triggered = grp[grp["rsi"] > threshold]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_near_52w_low(df: pd.DataFrame, params: dict) -> list[tuple]:
    pct = float(params.get("pct", 0.05))  # within 5% of 52w low
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["low_52"] = grp["close"].rolling(252, min_periods=60).min()
        grp["dist"] = (grp["close"] - grp["low_52"]) / grp["low_52"]
        triggered = grp[grp["dist"] <= pct]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_near_52w_high(df: pd.DataFrame, params: dict) -> list[tuple]:
    pct = float(params.get("pct", 0.05))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["high_52"] = grp["close"].rolling(252, min_periods=60).max()
        grp["dist"] = (grp["high_52"] - grp["close"]) / grp["high_52"]
        triggered = grp[grp["dist"] <= pct]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_volume_spike(df: pd.DataFrame, params: dict) -> list[tuple]:
    n = int(params.get("n_days", 20))
    mult = float(params.get("multiplier", 2.0))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["avg_vol"] = grp["volume"].rolling(n).mean()
        triggered = grp[grp["volume"] > grp["avg_vol"] * mult]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_gap(df: pd.DataFrame, params: dict, gap_up: bool) -> list[tuple]:
    pct = float(params.get("pct", 0.02))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["gap"] = (grp["open"] - grp["close"].shift(1)) / grp["close"].shift(1)
        if gap_up:
            triggered = grp[grp["gap"] > pct]
        else:
            triggered = grp[grp["gap"] < -pct]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_volatility_expansion(df: pd.DataFrame, params: dict) -> list[tuple]:
    short_w = int(params.get("short_window", 5))
    long_w  = int(params.get("long_window", 20))
    mult    = float(params.get("multiplier", 1.5))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["ret"] = np.log(grp["close"] / grp["close"].shift(1))
        grp["vol_short"] = grp["ret"].rolling(short_w).std()
        grp["vol_long"]  = grp["ret"].rolling(long_w).std()
        triggered = grp[grp["vol_short"] > grp["vol_long"] * mult]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_above_sma(df: pd.DataFrame, params: dict) -> list[tuple]:
    window = int(params.get("window", 200))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["sma"] = grp["close"].rolling(window).mean()
        triggered = grp[grp["close"] > grp["sma"]]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


def _condition_below_sma(df: pd.DataFrame, params: dict) -> list[tuple]:
    window = int(params.get("window", 200))
    events = []
    for ticker, grp in df.groupby("ticker"):
        grp = grp.sort_values("date").reset_index(drop=True)
        grp["sma"] = grp["close"].rolling(window).mean()
        triggered = grp[grp["close"] < grp["sma"]]
        events.extend((row["date"], ticker) for _, row in triggered.iterrows())
    return events


# Registry maps condition string → handler function
CONDITION_HANDLERS = {
    "down_n_consecutive_days":  lambda df, p: _condition_down_n_consecutive(df, p),
    "up_n_consecutive_days":    lambda df, p: _condition_up_n_consecutive(df, p),
    "down_consecutive":         lambda df, p: _condition_down_n_consecutive(df, p),
    "up_consecutive":           lambda df, p: _condition_up_n_consecutive(df, p),
    "return_below_threshold":   lambda df, p: _condition_return_threshold(df, p, above=False),
    "return_above_threshold":   lambda df, p: _condition_return_threshold(df, p, above=True),
    "rsi_oversold":             lambda df, p: _condition_rsi(df, p, oversold=True),
    "rsi_overbought":           lambda df, p: _condition_rsi(df, p, oversold=False),
    "near_52w_low":             lambda df, p: _condition_near_52w_low(df, p),
    "near_52w_high":            lambda df, p: _condition_near_52w_high(df, p),
    "volume_spike":             lambda df, p: _condition_volume_spike(df, p),
    "gap_up":                   lambda df, p: _condition_gap(df, p, gap_up=True),
    "gap_down":                 lambda df, p: _condition_gap(df, p, gap_up=False),
    "volatility_expansion":     lambda df, p: _condition_volatility_expansion(df, p),
    "above_sma":                lambda df, p: _condition_above_sma(df, p),
    "below_sma":                lambda df, p: _condition_below_sma(df, p),
}


# ---------------------------------------------------------------------------
# Forward return computation
# ---------------------------------------------------------------------------

def _compute_forward_returns(
    df: pd.DataFrame,
    events: list[tuple[date, str]],
    horizon: int,
) -> pd.DataFrame:
    """
    For each (event_date, ticker) pair, look up the forward return
    over `horizon` trading days.

    Returns DataFrame with columns: event_date, ticker, forward_return.
    """
    if not events:
        return pd.DataFrame(columns=["event_date", "ticker", "forward_return"])

    # Build a date→close lookup per ticker
    records = []
    close_by_ticker: dict[str, dict[date, float]] = {}
    for ticker, grp in df.groupby("ticker"):
        close_by_ticker[ticker] = dict(zip(grp["date"], grp["close"]))

    # Get sorted date lists per ticker for horizon lookup
    dates_by_ticker: dict[str, list[date]] = {
        t: sorted(v.keys()) for t, v in close_by_ticker.items()
    }

    for event_date, ticker in events:
        if ticker not in close_by_ticker:
            continue
        dates = dates_by_ticker[ticker]
        close_map = close_by_ticker[ticker]
        if event_date not in close_map:
            continue
        # Find the position of event_date in sorted dates
        try:
            idx = dates.index(event_date)
        except ValueError:
            continue
        future_idx = idx + horizon
        if future_idx >= len(dates):
            continue
        future_date = dates[future_idx]
        entry_close = close_map[event_date]
        exit_close  = close_map[future_date]
        if entry_close <= 0:
            continue
        fwd_ret = math.log(exit_close / entry_close)
        records.append({
            "event_date":    event_date,
            "ticker":        ticker,
            "forward_return": fwd_ret,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Statistical analysis
# ---------------------------------------------------------------------------

def _compute_statistics(
    fwd_df: pd.DataFrame,
    horizon: int,
    direction: str,
    spy_regime: dict[date, int] | None = None,
) -> dict:
    """
    Compute full statistical suite from forward return series.
    direction: 'mean_reversion_long' | 'momentum_long' | 'momentum_short' | etc.
    """
    if fwd_df.empty or len(fwd_df) < MIN_SAMPLE_SIZE:
        return {}

    rets = fwd_df["forward_return"].values

    # Sign flip for short hypotheses
    if "short" in direction:
        rets = -rets

    avg_ret     = float(np.mean(rets))
    med_ret     = float(np.median(rets))
    std_ret     = float(np.std(rets, ddof=1))
    hit_rate    = float(np.mean(rets > 0))

    # t-test vs zero
    t_stat, p_value = scipy_stats.ttest_1samp(rets, 0.0)
    t_stat  = float(t_stat)
    p_value = float(p_value)

    # Annualised Sharpe
    ann_factor = math.sqrt(252 / max(horizon, 1))
    sharpe = (avg_ret / std_ret * ann_factor) if std_ret > 0 else 0.0

    # Max drawdown on the sorted event returns
    cum = np.cumsum(rets)
    running_max = np.maximum.accumulate(cum)
    drawdowns = running_max - cum
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Rank IC (if cross-sectional: compute daily IC vs a neutral rank)
    # For time-series hypotheses, use correlation of returns with rank(time)
    rank_ic = None
    if len(fwd_df) >= 10:
        if "ticker" in fwd_df.columns and fwd_df["ticker"].nunique() > 1:
            # Cross-sectional: daily Spearman IC of event_score vs forward_ret
            # We don't have a score here — use 1.0 for all events (binary trigger)
            # So IC = Spearman(1.0 vector, rets) = undefined
            # Use time-series IC instead: rank(event_date) vs return
            date_rank = fwd_df["event_date"].rank()
            if date_rank.nunique() > 1 and fwd_df["forward_return"].nunique() > 1:
                ic_corr, _ = scipy_stats.spearmanr(date_rank, fwd_df["forward_return"])
                rank_ic = float(ic_corr) if not math.isnan(ic_corr) else None

    # Regime breakdown (if spy_regime provided)
    regime_breakdown = {}
    if spy_regime:
        for regime_name, regime_val in [("bull", 1), ("bear", -1), ("neutral", 0)]:
            mask = fwd_df["event_date"].map(
                lambda d: spy_regime.get(d, 0) == regime_val
            )
            sub = fwd_df[mask]["forward_return"].values
            if "short" in direction:
                sub = -sub
            if len(sub) >= 5:
                regime_breakdown[regime_name] = {
                    "n":        int(len(sub)),
                    "hit_rate": float(np.mean(sub > 0)),
                    "avg_ret":  float(np.mean(sub)),
                }

    # Composite score (0-1)
    # Normalise each component to [0, 1], then weight
    norm_hit  = max(0.0, (hit_rate - 0.5) / 0.5)    # 0.5 → 0, 1.0 → 1
    norm_sh   = max(0.0, min(1.0, sharpe / 2.0))     # 2.0 → 1.0
    norm_ic   = max(0.0, min(1.0, (rank_ic or 0) / 0.1)) if rank_ic else 0
    norm_n    = min(1.0, math.log10(max(len(fwd_df), 1)) / math.log10(200))
    composite = (
        COMPOSITE_WEIGHTS["hit_rate"]    * norm_hit +
        COMPOSITE_WEIGHTS["sharpe"]      * norm_sh  +
        COMPOSITE_WEIGHTS["rank_ic"]     * norm_ic  +
        COMPOSITE_WEIGHTS["sample_size"] * norm_n
    )

    return {
        "sample_size":      len(fwd_df),
        "event_dates":      sorted(fwd_df["event_date"].unique().tolist()),
        "tickers":          sorted(fwd_df["ticker"].unique().tolist()) if "ticker" in fwd_df.columns else [],
        "hit_rate":         hit_rate,
        "avg_return":       avg_ret,
        "median_return":    med_ret,
        "std_return":       std_ret,
        "sharpe":           sharpe,
        "max_drawdown":     max_dd,
        "t_stat":           t_stat,
        "p_value":          p_value,
        "rank_ic":          rank_ic,
        "regime_breakdown": regime_breakdown,
        "composite_score":  float(composite),
    }


# ---------------------------------------------------------------------------
# Market regime lookup
# ---------------------------------------------------------------------------

def _build_spy_regime(start: date, end: date) -> dict[date, int]:
    """Return {date: 1=bull / -1=bear / 0=neutral} based on SPY vs SMA200."""
    df = _load_spy_bars(start, end)
    if df.empty:
        return {}
    df = df.sort_values("date")
    df["sma200"] = df["close"].rolling(200, min_periods=60).mean()
    regime = {}
    for _, row in df.iterrows():
        if pd.isna(row["sma200"]):
            regime[row["date"]] = 0
        elif row["close"] > row["sma200"] * 1.02:
            regime[row["date"]] = 1
        elif row["close"] < row["sma200"] * 0.98:
            regime[row["date"]] = -1
        else:
            regime[row["date"]] = 0
    return regime


# ---------------------------------------------------------------------------
# Main backtester
# ---------------------------------------------------------------------------

class HypothesisBacktester:

    def run_queued(self, limit: int = 50) -> int:
        """
        Fetch up to `limit` queued hypotheses and run their backtests.
        Returns number of hypotheses processed.
        """
        with get_connection() as conn:
            rows = conn.execute(text("""
                SELECT hypothesis_id, market_object, condition,
                       condition_params, target, horizons,
                       direction, regime_filter, confidence_prior
                FROM research_hypotheses
                WHERE test_status = 'queued'
                ORDER BY confidence_prior DESC, created_at ASC
                LIMIT :limit
            """), {"limit": limit}).fetchall()

        if not rows:
            log.info("backtester.no_queued_hypotheses")
            return 0

        log.info("backtester.starting", n_hypotheses=len(rows))
        processed = 0

        for row in rows:
            hid = row[0]
            try:
                self._run_hypothesis(row)
                processed += 1
            except Exception as exc:
                log.error("backtester.hypothesis_failed", hypothesis_id=hid, error=str(exc))
                self._mark_failed(hid, str(exc))

        log.info("backtester.done", processed=processed)
        return processed

    def _run_hypothesis(self, row: Any) -> None:
        hid            = row[0]
        market_object  = row[1] or "universe"
        condition_str  = row[2] or "unspecified"
        params_raw     = row[3] or {}
        target         = row[4] or "forward_return_5d"
        horizons       = row[5] or [5]
        direction      = row[6] or "neutral"
        regime_filter  = row[7]

        params = params_raw if isinstance(params_raw, dict) else {}

        log.info(
            "backtester.running_hypothesis",
            hypothesis_id=hid,
            condition=condition_str,
            market_object=market_object,
        )

        # Mark as running
        self._mark_running(hid)

        # Resolve tickers
        if market_object in ("SPY", "QQQ", "IWM", "DIA"):
            tickers = [market_object]
        elif market_object == "universe":
            tickers = _get_universe_tickers()
        else:
            tickers = [market_object]

        # Date range: full history available in raw_bars
        with get_connection() as conn:
            date_row = conn.execute(text(
                "SELECT MIN(date), MAX(date) FROM raw_bars WHERE ticker = ANY(:t)"
            ), {"t": tickers}).fetchone()

        if not date_row or not date_row[0]:
            self._skip_hypothesis(hid, "no_bar_data")
            return

        test_start = date_row[0]
        test_end   = date_row[1]

        # Apply regime filter to date range? (simplified: just annotate results)
        spy_regime = _build_spy_regime(test_start, test_end)

        # Load bars
        df = _load_bars(tickers, test_start, test_end)
        if df.empty:
            self._skip_hypothesis(hid, "empty_bars")
            return

        # Find condition handler
        handler = CONDITION_HANDLERS.get(condition_str.lower())
        if handler is None:
            # Try fuzzy match
            for key in CONDITION_HANDLERS:
                if key.split("_")[0] in condition_str.lower():
                    handler = CONDITION_HANDLERS[key]
                    break

        if handler is None:
            log.warning("backtester.unknown_condition", condition=condition_str)
            self._skip_hypothesis(hid, f"unknown_condition:{condition_str}")
            return

        # Get events
        events = handler(df, params)

        if not events:
            self._skip_hypothesis(hid, "no_events_fired")
            return

        log.info("backtester.events_found", n_events=len(events), hypothesis_id=hid)

        # Apply regime filter if specified
        if regime_filter and spy_regime:
            target_regime = {"bull_only": 1, "bear_only": -1}.get(regime_filter, None)
            if target_regime is not None:
                events = [
                    (d, t) for d, t in events
                    if spy_regime.get(d, 0) == target_regime
                ]

        if not events:
            self._skip_hypothesis(hid, "no_events_after_regime_filter")
            return

        # Run for each horizon
        for horizon in horizons:
            fwd_df = _compute_forward_returns(df, events, horizon)

            if len(fwd_df) < MIN_SAMPLE_SIZE:
                log.info(
                    "backtester.insufficient_sample",
                    hypothesis_id=hid,
                    horizon=horizon,
                    n=len(fwd_df),
                )
                continue

            stats = _compute_statistics(fwd_df, horizon, direction, spy_regime)
            if not stats:
                continue

            test_id = self._write_test(hid, horizon, test_start, test_end)
            self._write_result(test_id, hid, horizon, stats)

            log.info(
                "backtester.result_written",
                hypothesis_id=hid,
                horizon=horizon,
                hit_rate=round(stats.get("hit_rate", 0), 3),
                sharpe=round(stats.get("sharpe", 0), 3),
                n=stats.get("sample_size"),
                composite=round(stats.get("composite_score", 0), 3),
            )

        self._mark_done(hid)

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _mark_running(self, hid: str) -> None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE research_hypotheses SET test_status = 'running', updated_at = now() WHERE hypothesis_id = :h"
            ), {"h": hid})
            conn.commit()

    def _mark_done(self, hid: str) -> None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE research_hypotheses SET test_status = 'done', updated_at = now() WHERE hypothesis_id = :h"
            ), {"h": hid})
            conn.commit()

    def _mark_failed(self, hid: str, reason: str) -> None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE research_hypotheses SET test_status = 'failed', skip_reason = :r, updated_at = now() WHERE hypothesis_id = :h"
            ), {"h": hid, "r": reason[:500]})
            conn.commit()

    def _skip_hypothesis(self, hid: str, reason: str) -> None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE research_hypotheses SET test_status = 'skipped', skip_reason = :r, updated_at = now() WHERE hypothesis_id = :h"
            ), {"h": hid, "r": reason})
            conn.commit()

    def _write_test(
        self,
        hid: str,
        horizon: int,
        test_start: date,
        test_end: date,
    ) -> int:
        with get_connection() as conn:
            result = conn.execute(text("""
                INSERT INTO hypothesis_tests
                    (hypothesis_id, horizon_days, test_start, test_end, status)
                VALUES (:h, :hz, :ts, :te, 'done')
                ON CONFLICT (hypothesis_id, horizon_days, test_start, test_end) DO UPDATE
                SET status = 'done', run_at = now()
                RETURNING id
            """), {"h": hid, "hz": horizon, "ts": test_start, "te": test_end})
            conn.commit()
            return result.fetchone()[0]

    def _write_result(
        self,
        test_id: int,
        hid: str,
        horizon: int,
        stats: dict,
    ) -> None:
        # Sanitise NaN/Inf for JSON serialisation
        def _s(v):
            if v is None:
                return None
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v

        regime_json = json.dumps(stats.get("regime_breakdown") or {})
        # event_dates is a list of date objects → convert to strings
        event_dates = [str(d) for d in (stats.get("event_dates") or [])]

        with get_connection() as conn:
            conn.execute(text("""
                INSERT INTO hypothesis_results (
                    test_id, hypothesis_id, horizon_days,
                    sample_size, event_dates, tickers,
                    hit_rate, avg_return, median_return, std_return, sharpe, max_drawdown,
                    t_stat, p_value, rank_ic,
                    regime_breakdown, composite_score
                ) VALUES (
                    :tid, :hid, :hz,
                    :n, :edates, :tickers,
                    :hr, :avg, :med, :std, :sh, :dd,
                    :tstat, :pval, :ic,
                    CAST(:regime AS jsonb), :composite
                )
                ON CONFLICT (test_id) DO UPDATE SET
                    hit_rate       = EXCLUDED.hit_rate,
                    avg_return     = EXCLUDED.avg_return,
                    composite_score = EXCLUDED.composite_score
            """), {
                "tid":      test_id,
                "hid":      hid,
                "hz":       horizon,
                "n":        stats.get("sample_size"),
                "edates":   event_dates,
                "tickers":  stats.get("tickers") or [],
                "hr":       _s(stats.get("hit_rate")),
                "avg":      _s(stats.get("avg_return")),
                "med":      _s(stats.get("median_return")),
                "std":      _s(stats.get("std_return")),
                "sh":       _s(stats.get("sharpe")),
                "dd":       _s(stats.get("max_drawdown")),
                "tstat":    _s(stats.get("t_stat")),
                "pval":     _s(stats.get("p_value")),
                "ic":       _s(stats.get("rank_ic")),
                "regime":   regime_json,
                "composite": _s(stats.get("composite_score")),
            })
            conn.commit()
