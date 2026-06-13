#!/usr/bin/env python3
"""
run_hypothesis_test.py
-----------------------
Conditional backtest against raw_bars.  Reads a JSON spec from stdin or
--spec argument.  Multiple conditions are AND-combined.

Spec format:
  {
    "ticker": "SPY",
    "conditions": [
      {"type": "consecutive_down", "params": {"n": 3}},
      {"type": "rsi_below",        "params": {"threshold": 35}}
    ],
    "direction": "long",
    "horizons": [1, 5, 10, 20]
  }

Output format:
  {
    "ticker": "SPY",
    "conditions_desc": "consecutive_down(n=3) AND rsi_below(threshold=35)",
    "sample_size": 128,
    "horizons": [
      {"days": 5, "hit_rate": 0.71, "avg_return": 0.82, "n": 128, "p_value": 0.02}
    ],
    "yearly": {"2022": {"hit_rate": 0.65, "n": 20}, ...},
    "passed_permutation": true,
    "p_value": 0.02,
    "narrative": "71% bullish hit rate at 5 days (n=128, p<0.05)"
  }

Supported condition types:
  consecutive_down, consecutive_up, rsi_below, rsi_above,
  price_above_sma, price_below_sma, jarvis_green, jarvis_red,
  gap_up, gap_down, volume_spike, near_52w_high, near_52w_low,
  nr7, inside_bar
"""

import sys
import os
import json
import random
import argparse
from typing import Optional

import psycopg2
import psycopg2.extras


# ── DB helpers ────────────────────────────────────────────────────────────────

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
        raise ValueError(f"No price data for {ticker.upper()}")
    return [dict(r) for r in rows]


def get_predictions(conn, ticker: str) -> dict:
    """Return {date_str: probability_positive} from predictions table."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT date::text, probability_positive
                FROM predictions
                WHERE ticker = %s AND probability_positive IS NOT NULL
                """,
                (ticker.upper(),),
            )
            return {r["date"]: float(r["probability_positive"]) for r in cur.fetchall()}
    except Exception:
        return {}


# ── Indicators ────────────────────────────────────────────────────────────────

def compute_rsi(closes: list, period: int = 14) -> list:
    if len(closes) < period + 1:
        return [None] * len(closes)
    rsi: list = [None] * period
    gains = [max(closes[i] - closes[i - 1], 0.0) for i in range(1, period + 1)]
    losses = [max(closes[i - 1] - closes[i], 0.0) for i in range(1, period + 1)]
    ag = sum(gains) / period
    al = sum(losses) / period
    for i in range(period, len(closes)):
        if i > period:
            d = closes[i] - closes[i - 1]
            ag = (ag * (period - 1) + max(d, 0.0)) / period
            al = (al * (period - 1) + max(-d, 0.0)) / period
        rsi.append(100.0 if al == 0 else 100 - 100 / (1 + ag / al))
    return rsi


def compute_sma(closes: list, period: int) -> list:
    sma: list = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        sma.append(sum(closes[i - period + 1 : i + 1]) / period)
    return sma


def compute_avg_volume(volumes: list, period: int = 20) -> list:
    avgs: list = [None] * (period - 1)
    for i in range(period - 1, len(volumes)):
        w = [v for v in volumes[i - period + 1 : i + 1] if v and v > 0]
        avgs.append(sum(w) / len(w) if w else None)
    return avgs


# ── Condition evaluation ──────────────────────────────────────────────────────

def apply_condition(bars: list, cond_type: str, params: dict, preds: dict) -> list:
    """Return a boolean mask of len(bars)."""
    n = len(bars)
    mask = [False] * n
    closes  = [b["close"]  for b in bars]
    opens   = [b["open"]   for b in bars]
    highs   = [b["high"]   for b in bars]
    lows    = [b["low"]    for b in bars]
    volumes = [b["volume"] or 0.0 for b in bars]

    if cond_type == "consecutive_down":
        days = int(params.get("n", 3))
        for i in range(days, n):
            if all(bars[i - k]["close"] < bars[i - k - 1]["close"] for k in range(days)):
                mask[i] = True

    elif cond_type == "consecutive_up":
        days = int(params.get("n", 3))
        for i in range(days, n):
            if all(bars[i - k]["close"] > bars[i - k - 1]["close"] for k in range(days)):
                mask[i] = True

    elif cond_type == "rsi_below":
        threshold = float(params.get("threshold", 30))
        period    = int(params.get("period", 14))
        rsi = compute_rsi(closes, period)
        for i, r in enumerate(rsi):
            if r is not None and r < threshold:
                mask[i] = True

    elif cond_type == "rsi_above":
        threshold = float(params.get("threshold", 70))
        period    = int(params.get("period", 14))
        rsi = compute_rsi(closes, period)
        for i, r in enumerate(rsi):
            if r is not None and r > threshold:
                mask[i] = True

    elif cond_type == "price_above_sma":
        period = int(params.get("period", 50))
        sma = compute_sma(closes, period)
        for i, s in enumerate(sma):
            if s is not None and closes[i] > s:
                mask[i] = True

    elif cond_type == "price_below_sma":
        period = int(params.get("period", 50))
        sma = compute_sma(closes, period)
        for i, s in enumerate(sma):
            if s is not None and closes[i] < s:
                mask[i] = True

    elif cond_type == "jarvis_green":
        threshold = float(params.get("threshold", 0.6))
        for i, bar in enumerate(bars):
            d = str(bar["date"])
            prob = preds.get(d)
            if prob is not None and prob > threshold:
                mask[i] = True

    elif cond_type == "jarvis_red":
        threshold = float(params.get("threshold", 0.4))
        for i, bar in enumerate(bars):
            d = str(bar["date"])
            prob = preds.get(d)
            if prob is not None and prob < threshold:
                mask[i] = True

    elif cond_type == "gap_up":
        pct = float(params.get("pct", 2)) / 100
        for i in range(1, n):
            if closes[i - 1] > 0 and opens[i] > closes[i - 1] * (1 + pct):
                mask[i] = True

    elif cond_type == "gap_down":
        pct = float(params.get("pct", 2)) / 100
        for i in range(1, n):
            if closes[i - 1] > 0 and opens[i] < closes[i - 1] * (1 - pct):
                mask[i] = True

    elif cond_type == "volume_spike":
        mult = float(params.get("multiplier", 2))
        avg_vol = compute_avg_volume(volumes)
        for i, av in enumerate(avg_vol):
            if av is not None and volumes[i] > mult * av:
                mask[i] = True

    elif cond_type == "near_52w_high":
        pct      = float(params.get("pct", 3)) / 100
        lookback = int(params.get("lookback", 252))
        for i in range(lookback, n):
            high_52w = max(highs[i - lookback : i])
            if high_52w > 0 and closes[i] >= high_52w * (1 - pct):
                mask[i] = True

    elif cond_type == "near_52w_low":
        pct      = float(params.get("pct", 3)) / 100
        lookback = int(params.get("lookback", 252))
        for i in range(lookback, n):
            low_52w = min(lows[i - lookback : i])
            if low_52w > 0 and closes[i] <= low_52w * (1 + pct):
                mask[i] = True

    elif cond_type == "nr7":
        # Current bar's range is the narrowest of last 7 bars
        for i in range(6, n):
            current_range = highs[i] - lows[i]
            prev_ranges   = [highs[i - k] - lows[i - k] for k in range(1, 7)]
            if current_range < min(prev_ranges):
                mask[i] = True

    elif cond_type == "inside_bar":
        # Current bar's range fits entirely within the prior bar
        for i in range(1, n):
            if highs[i] < highs[i - 1] and lows[i] > lows[i - 1]:
                mask[i] = True

    else:
        raise ValueError(f"Unknown condition type: {cond_type!r}")

    return mask


def find_signals(bars: list, conditions: list, preds: dict) -> list:
    """Return indices where ALL conditions are simultaneously true."""
    n = len(bars)
    combined = [True] * n
    for cond in conditions:
        mask = apply_condition(bars, cond["type"], cond.get("params", {}), preds)
        for i in range(n):
            combined[i] = combined[i] and mask[i]
    return [i for i, v in enumerate(combined) if v]


# ── Backtest maths ────────────────────────────────────────────────────────────

def forward_returns(bars: list, signals: list, horizon: int) -> list:
    rets = []
    for i in signals:
        if i + horizon < len(bars):
            entry = bars[i]["close"]
            if entry > 0:
                rets.append((bars[i + horizon]["close"] - entry) / entry)
    return rets


def hit_rate(returns: list, direction: str) -> float:
    if not returns:
        return 0.0
    if direction == "long":
        return sum(1 for r in returns if r > 0) / len(returns)
    return sum(1 for r in returns if r < 0) / len(returns)


def permutation_pvalue(
    bars: list, signals: list, horizon: int, direction: str, n_perms: int = 1000
) -> Optional[float]:
    """Compare signal hit rate against randomly sampled dates."""
    rets = forward_returns(bars, signals, horizon)
    if len(rets) < 5:
        return None
    n = len(rets)
    observed = hit_rate(rets, direction)

    # Population: all dates with a valid forward exit
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
        if hit_rate(sample, direction) >= observed:
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
        str(y): {"hit_rate": round(d["hits"] / d["total"], 3), "n": d["total"]}
        for y, d in sorted(years.items())
        if d["total"] >= 2
    }


def conditions_desc(conditions: list) -> str:
    parts = []
    for c in conditions:
        p = c.get("params", {})
        p_str = ", ".join(f"{k}={v}" for k, v in p.items())
        parts.append(f"{c['type']}({p_str})" if p_str else c["type"])
    return " AND ".join(parts)


def build_narrative(
    ticker: str, n_signals: int, horizon_results: dict, direction: str
) -> str:
    if n_signals < 5:
        return f"Only {n_signals} signal(s) found for {ticker} — insufficient data."

    # Prefer 5d, then 10d, then smallest available
    primary_key = next(
        (k for k in ("5", "10", "1", "20") if k in horizon_results),
        min(horizon_results, key=int),
    )
    h = horizon_results[primary_key]
    hr   = h["hit_rate"]
    n    = h["n"]
    pval = h.get("p_value")

    direction_word = "bullish" if direction == "long" else "bearish"
    hr_pct = f"{hr * 100:.0f}%"
    p_str  = ""
    if pval is not None:
        p_str = ", p<0.01" if pval < 0.01 else ", p<0.05" if pval < 0.05 else f", p={pval:.2f}"

    return f"{hr_pct} {direction_word} hit rate at {primary_key} days (n={n}{p_str})"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=str, help="JSON spec as a string argument")
    args = parser.parse_args()

    if args.spec:
        spec = json.loads(args.spec)
    else:
        raw = sys.stdin.buffer.read()
        if raw.startswith(b"\xef\xbb\xbf"):  # strip UTF-8 BOM (PowerShell piping)
            raw = raw[3:]
        spec = json.loads(raw.decode("utf-8"))

    ticker     = spec["ticker"]
    conditions = spec["conditions"]
    direction  = spec.get("direction", "long")
    horizons   = [int(h) for h in spec.get("horizons", [1, 5, 10, 20])]

    needs_jarvis = any(c["type"] in ("jarvis_green", "jarvis_red") for c in conditions)

    conn = get_conn()
    try:
        bars  = get_bars(conn, ticker)
        preds = get_predictions(conn, ticker) if needs_jarvis else {}
    finally:
        conn.close()

    signals = find_signals(bars, conditions, preds)

    horizon_results: dict = {}
    for h in horizons:
        rets    = forward_returns(bars, signals, h)
        hr      = hit_rate(rets, direction)
        avg_ret = sum(rets) / len(rets) if rets else 0.0
        pval    = permutation_pvalue(bars, signals, h, direction) if len(rets) >= 5 else None
        horizon_results[str(h)] = {
            "days":       h,
            "n":          len(rets),
            "hit_rate":   round(hr, 4),
            "avg_return": round(avg_ret * 100, 4),  # percent (0.82 = 0.82%)
            "p_value":    round(pval, 4) if pval is not None else None,
        }

    # Primary = 5d preferred, else smallest
    primary_key = "5" if "5" in horizon_results else str(min(horizons))
    primary     = horizon_results[primary_key]
    primary_h   = int(primary_key)
    primary_pval = primary.get("p_value")

    yearly    = yearly_breakdown(bars, signals, primary_h, direction)
    narrative = build_narrative(ticker, len(signals), horizon_results, direction)

    output = {
        "ticker":            ticker.upper(),
        "conditions_desc":   conditions_desc(conditions),
        "sample_size":       len(signals),
        "horizons":          sorted(horizon_results.values(), key=lambda x: x["days"]),
        "yearly":            yearly,
        "passed_permutation": primary_pval is not None and primary_pval < 0.05,
        "p_value":           primary_pval,
        "narrative":         narrative,
    }

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
