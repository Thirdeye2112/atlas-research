#!/usr/bin/env python
"""
analyze_candlestick_winrate.py — iteration 1 of the candlestick learning loop.

Reads candlestick_outcomes (4.4M+ rows) and reports, per pattern and per
forward horizon, the DIRECTIONAL win-rate and mean edge:

    bullish pattern  -> win if forward return > 0 ; edge = +mean(return)
    bearish pattern  -> win if forward return < 0 ; edge = -mean(return)
    neutral pattern  -> no directional thesis; reported as |move| only

Edge is shown net of the universe drift baseline (mean forward return across
ALL pattern events at that horizon) so we measure real signal, not the fact
that stocks drift up. Horizons are trading days (daily bars): 1, 6, 12, 24.

The swing horizons (12, 24 days) are the focus; return_1 is daily noise.

Usage:
    python scripts/analyze_candlestick_winrate.py
    python scripts/analyze_candlestick_winrate.py --horizon 12 --min-n 200
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
from sqlalchemy import text
from atlas_research.db import connection

# Pattern -> intended direction (mirrors DIRECTION_MAP in the backtest script).
DIRECTION = {
    'Doji': 'neutral', 'Long-legged doji': 'neutral', 'Hammer': 'bullish',
    'Inverted hammer': 'bullish', 'Shooting star': 'bearish', 'Hanging man': 'bearish',
    'Marubozu': 'neutral', 'Spinning top': 'neutral', 'Bullish engulfing': 'bullish',
    'Bearish engulfing': 'bearish', 'Inside bar': 'neutral', 'Outside bar': 'neutral',
    'Harami': 'neutral', 'Tweezer top': 'bearish', 'Tweezer bottom': 'bullish',
    'Morning star': 'bullish', 'Evening star': 'bearish',
    'Three white soldiers': 'bullish', 'Three black crows': 'bearish',
}

HORIZONS = [1, 6, 12, 24]
OUT = ROOT / "reports" / "validity" / "candlestick_winrate_iter1.csv"


def agg_query(horizons):
    sel = ["candle_name", "count(*) AS n_total"]
    for h in horizons:
        sel += [
            f"count(return_{h}) AS n_{h}",
            f"avg(return_{h}) AS mean_{h}",
            f"avg(CASE WHEN return_{h} > 0 THEN 1.0 ELSE 0.0 END) AS fracup_{h}",
            # 'big move' = |move| >= 3% at this horizon (swing-sized, not noise)
            f"avg(CASE WHEN abs(return_{h}) >= 0.03 THEN 1.0 ELSE 0.0 END) AS fracbig_{h}",
        ]
    return f"SELECT {', '.join(sel)} FROM candlestick_outcomes GROUP BY candle_name"


def baseline_query(horizons):
    sel = [f"avg(return_{h}) AS base_{h}" for h in horizons]
    return f"SELECT {', '.join(sel)} FROM candlestick_outcomes"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=12, help="Primary swing horizon to sort by")
    ap.add_argument("--min-n", type=int, default=100, help="Min events to include a pattern")
    args = ap.parse_args()
    H = args.horizon

    with connection.get_connection() as c:
        df = pd.read_sql(text(agg_query(HORIZONS)), c)
        base = pd.read_sql(text(baseline_query(HORIZONS)), c).iloc[0]

    df["direction"] = df["candle_name"].map(DIRECTION).fillna("neutral")

    rows = []
    for _, r in df.iterrows():
        d = r["direction"]
        rec = {"pattern": r["candle_name"], "dir": d, "n": int(r["n_total"])}
        for h in HORIZONS:
            n = r[f"n_{h}"]; mean = r[f"mean_{h}"]; fracup = r[f"fracup_{h}"]
            if n and n > 0:
                # directional win-rate + edge
                if d == "bearish":
                    win = 1.0 - fracup
                    edge = -(mean - base[f"base_{h}"])
                    signed_mean = -mean
                elif d == "bullish":
                    win = fracup
                    edge = mean - base[f"base_{h}"]
                    signed_mean = mean
                else:  # neutral — no directional thesis
                    win = float("nan"); edge = float("nan"); signed_mean = mean
                rec[f"win_{h}"] = win
                rec[f"edge_{h}"] = edge           # mean directional return net of drift
                rec[f"ret_{h}"] = signed_mean     # mean directional return (gross)
                rec[f"big_{h}"] = r[f"fracbig_{h}"]
            else:
                rec[f"win_{h}"] = rec[f"edge_{h}"] = rec[f"ret_{h}"] = rec[f"big_{h}"] = float("nan")
        rows.append(rec)

    res = pd.DataFrame(rows)
    res = res[res["n"] >= args.min_n].copy()
    # sort directional patterns by edge at the primary horizon
    res["_sortkey"] = res[f"edge_{H}"].fillna(-99)
    res = res.sort_values("_sortkey", ascending=False).drop(columns="_sortkey")

    pd.set_option("display.width", 200, "display.max_columns", 40)
    print(f"\nBaseline drift (mean fwd return, all events): "
          + "  ".join(f"{h}d={base[f'base_{h}']*100:+.2f}%" for h in HORIZONS))
    print(f"Primary swing horizon: {H} trading days | min n = {args.min_n}\n")

    show = res[["pattern", "dir", "n",
                f"win_{H}", f"edge_{H}", f"ret_{H}", f"big_{H}"]].copy()
    show.columns = ["pattern", "dir", "n",
                    f"win%@{H}d", f"edge@{H}d", f"ret@{H}d", f"big%@{H}d"]
    for col in show.columns[3:]:
        show[col] = (show[col] * 100).round(2)
    print(show.to_string(index=False))

    # full multi-horizon table to CSV
    OUT.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT, index=False)
    print(f"\nFull multi-horizon table -> {OUT}")
    print("Legend: win% = directional win-rate; edge = mean directional return "
          "net of drift; ret = gross directional mean; big% = share of moves >= 3%.")


if __name__ == "__main__":
    main()
