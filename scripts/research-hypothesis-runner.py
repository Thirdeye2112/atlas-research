#!/usr/bin/env python3
"""
research-hypothesis-runner.py
------------------------------
Reads a JSON hypothesis spec from stdin.
Queries raw_bars from atlas_research DB, runs a conditional backtest.
Writes JSON results to stdout. Errors go to stderr (non-zero exit on failure).

Spec schema (stdin):
  {
    "market_object": "SPY",
    "condition": "down_streak",
    "condition_params": {"days": 3},
    "direction": "long",
    "horizons": [5, 10, 20],
    "extracted_claim": "SPY bounces after 3 consecutive down days"
  }

Supported conditions:
  down_streak, up_streak, rsi_below, rsi_above,
  gap_down, gap_up, price_below_ma, price_above_ma, volume_spike
"""

import sys
import os
import json
import random
from typing import Optional

import psycopg2
import psycopg2.extras


def get_conn():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)


def get_bars(conn, ticker: str) -> list:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT date, open::float, high::float, low::float,
                   close::float, volume::float
            FROM raw_bars
            WHERE ticker = %s
            ORDER BY date
            """,
            (ticker.upper(),),
        )
        rows = cur.fetchall()
    if not rows:
        raise ValueError(f"No price data found for {ticker.upper()}")
    return [dict(r) for r in rows]


# ── Indicators ────────────────────────────────────────────────────────────────

def compute_rsi(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [None] * len(closes)

    rsi: list = [None] * period
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, period + 1)]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    for i in range(period, len(closes)):
        if i > period:
            diff = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(diff, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-diff, 0.0)) / period
        rsi.append(
            100.0 if avg_loss == 0 else 100 - 100 / (1 + avg_gain / avg_loss)
        )

    return rsi


def compute_sma(closes: list, period: int) -> list:
    sma: list = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        sma.append(sum(closes[i - period + 1 : i + 1]) / period)
    return sma


def compute_avg_volume(volumes: list, period: int = 20) -> list:
    avgs: list = [None] * (period - 1)
    for i in range(period - 1, len(volumes)):
        window = [v for v in volumes[i - period + 1 : i + 1] if v and v > 0]
        avgs.append(sum(window) / len(window) if window else None)
    return avgs


# ── Signal detection ──────────────────────────────────────────────────────────

def find_signals(bars: list, condition: str, params: dict) -> list:
    closes = [b["close"] for b in bars]
    opens = [b["open"] for b in bars]
    volumes = [b["volume"] or 0.0 for b in bars]
    signals: list = []

    if condition == "down_streak":
        n = int(params.get("days", 3))
        for i in range(n, len(bars)):
            if all(bars[i - k]["close"] < bars[i - k - 1]["close"] for k in range(n)):
                signals.append(i)

    elif condition == "up_streak":
        n = int(params.get("days", 3))
        for i in range(n, len(bars)):
            if all(bars[i - k]["close"] > bars[i - k - 1]["close"] for k in range(n)):
                signals.append(i)

    elif condition == "rsi_below":
        threshold = float(params.get("threshold", 30))
        period = int(params.get("period", 14))
        rsi = compute_rsi(closes, period)
        for i, r in enumerate(rsi):
            if r is not None and r < threshold:
                signals.append(i)

    elif condition == "rsi_above":
        threshold = float(params.get("threshold", 70))
        period = int(params.get("period", 14))
        rsi = compute_rsi(closes, period)
        for i, r in enumerate(rsi):
            if r is not None and r > threshold:
                signals.append(i)

    elif condition == "gap_down":
        pct = float(params.get("pct", 2)) / 100
        for i in range(1, len(bars)):
            if closes[i - 1] > 0 and opens[i] < closes[i - 1] * (1 - pct):
                signals.append(i)

    elif condition == "gap_up":
        pct = float(params.get("pct", 2)) / 100
        for i in range(1, len(bars)):
            if closes[i - 1] > 0 and opens[i] > closes[i - 1] * (1 + pct):
                signals.append(i)

    elif condition == "price_below_ma":
        period = int(params.get("period", 50))
        sma = compute_sma(closes, period)
        for i, s in enumerate(sma):
            if s is not None and closes[i] < s:
                signals.append(i)

    elif condition == "price_above_ma":
        period = int(params.get("period", 50))
        sma = compute_sma(closes, period)
        for i, s in enumerate(sma):
            if s is not None and closes[i] > s:
                signals.append(i)

    elif condition == "volume_spike":
        mult = float(params.get("multiplier", 2))
        avg_vol = compute_avg_volume(volumes)
        for i, av in enumerate(avg_vol):
            if av is not None and volumes[i] > mult * av:
                signals.append(i)

    else:
        raise ValueError(f"Unknown condition: {condition}")

    return signals


# ── Backtest maths ────────────────────────────────────────────────────────────

def forward_returns(bars: list, signals: list, horizon: int) -> list:
    results = []
    for i in signals:
        if i + horizon < len(bars):
            entry = bars[i]["close"]
            if entry > 0:
                results.append((bars[i + horizon]["close"] - entry) / entry)
    return results


def hit_rate(returns: list, direction: str) -> float:
    if not returns:
        return 0.0
    hits = sum(1 for r in returns if (r > 0 if direction == "long" else r < 0))
    return hits / len(returns)


def permutation_pvalue(
    bars: list, signals: list, horizon: int, direction: str, n_perms: int = 1000
) -> Optional[float]:
    """Compare signal hit rate against randomly sampled dates (proper permutation test)."""
    observed_returns = forward_returns(bars, signals, horizon)
    if len(observed_returns) < 5:
        return None
    n = len(observed_returns)
    observed_hr = hit_rate(observed_returns, direction)

    # Population: all dates with valid forward exits
    population = []
    for i in range(len(bars) - horizon):
        entry = bars[i]["close"]
        if entry > 0:
            population.append((bars[i + horizon]["close"] - entry) / entry)

    if len(population) < n:
        return None

    count = 0
    for _ in range(n_perms):
        sample = random.sample(population, n)
        if hit_rate(sample, direction) >= observed_hr:
            count += 1
    return count / n_perms


def yearly_breakdown(
    bars: list, signals: list, horizon: int, direction: str
) -> dict:
    years: dict = {}
    for i in signals:
        if i + horizon >= len(bars):
            continue
        d = bars[i]["date"]
        year = d.year if hasattr(d, "year") else int(str(d)[:4])
        entry = bars[i]["close"]
        if entry <= 0:
            continue
        ret = (bars[i + horizon]["close"] - entry) / entry
        hit = (ret > 0) if direction == "long" else (ret < 0)
        if year not in years:
            years[year] = {"hits": 0, "total": 0}
        years[year]["hits"] += int(hit)
        years[year]["total"] += 1

    return {
        str(y): {"hit_rate": round(d["hits"] / d["total"], 4), "n": d["total"]}
        for y, d in sorted(years.items())
        if d["total"] >= 2
    }


def build_narrative(spec: dict, n_signals: int, horizon_results: dict) -> str:
    ticker = spec["market_object"]
    claim = spec.get("extracted_claim", f"{ticker} {spec['condition']}")
    direction = spec["direction"]

    if n_signals < 5:
        return (
            f"Only {n_signals} signal(s) found for {ticker} — "
            "insufficient data for statistical conclusions."
        )

    h5 = horizon_results.get("5") or next(iter(horizon_results.values()), {})
    hr = h5.get("hit_rate", 0)
    n = h5.get("n", 0)
    pval = h5.get("p_value")
    primary_h = min(int(k) for k in horizon_results)

    strength = "strong" if hr >= 0.65 else "moderate" if hr >= 0.55 else "weak"
    direction_word = "bullish" if direction == "long" else "bearish"
    sig_str = ""
    if pval is not None:
        stars = "**" if pval < 0.01 else "*" if pval < 0.05 else ""
        sig_str = f" (p={pval:.3f}{stars})"

    stat_conclusion = (
        "Statistically significant at α=0.05."
        if pval is not None and pval < 0.05
        else "Not statistically significant at α=0.05."
    )

    return (
        f"{claim}. "
        f"Tested on {ticker}: {n_signals} signals, {n} with {primary_h}d exit data. "
        f"{primary_h}-day {direction_word} hit rate: {hr:.1%} — {strength}{sig_str}. "
        f"{stat_conclusion}"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import io
    raw = sys.stdin.buffer.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    spec = json.loads(raw.decode('utf-8'))

    ticker = spec["market_object"]
    condition = spec["condition"]
    params = spec.get("condition_params", {})
    direction = spec.get("direction", "long")
    horizons = [int(h) for h in spec.get("horizons", [5, 10, 20])]

    conn = get_conn()
    try:
        bars = get_bars(conn, ticker)
    finally:
        conn.close()

    signals = find_signals(bars, condition, params)

    horizon_results: dict = {}
    for h in horizons:
        rets = forward_returns(bars, signals, h)
        hr = hit_rate(rets, direction)
        avg_ret = sum(rets) / len(rets) if rets else 0.0
        pval = permutation_pvalue(bars, signals, h, direction) if len(rets) >= 5 else None
        horizon_results[str(h)] = {
            "n": len(rets),
            "hit_rate": round(hr, 4),
            "avg_return": round(avg_ret, 4),
            "p_value": round(pval, 4) if pval is not None else None,
        }

    primary_h = horizons[0] if horizons else 5
    yearly = yearly_breakdown(bars, signals, primary_h, direction)
    narrative = build_narrative(spec, len(signals), horizon_results)

    result = {
        "market_object": ticker.upper(),
        "condition": condition,
        "n_signals": len(signals),
        "horizons": horizon_results,
        "yearly": yearly,
        "narrative": narrative,
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
