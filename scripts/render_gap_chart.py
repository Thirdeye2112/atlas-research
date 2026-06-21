#!/usr/bin/env python
"""
render_gap_chart.py — Render a price chart with gap / FVG zones highlighted.

Usage
-----
    # Render one classic gap for SPY:
    python scripts/render_gap_chart.py --ticker SPY --gap-type classic --direction up

    # Render one bullish FVG (5m):
    python scripts/render_gap_chart.py --ticker SPY --gap-type fvg --timeframe 5m

    # Render a specific gap by row id:
    python scripts/render_gap_chart.py --gap-id 1234

Output: reports/ta/gaps_<TICKER>_<GAP_TYPE>_<DATE>.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from sqlalchemy import create_engine, text

from config import settings

OUT_DIR = ROOT / "reports" / "ta"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_gap(engine, gap_id: int | None, ticker: str, gap_type: str,
              timeframe: str, direction: str) -> dict:
    """Return one gap row as a dict."""
    if gap_id is not None:
        sql = text("""
            SELECT id, ticker, ts AT TIME ZONE 'UTC', timeframe, gap_type, direction,
                   zone_top, zone_bottom, size_pct,
                   bar1_ts AT TIME ZONE 'UTC', bar3_ts AT TIME ZONE 'UTC'
            FROM gaps WHERE id = :gid
        """)
        with engine.connect() as c:
            row = c.execute(sql, {"gid": gap_id}).fetchone()
    else:
        # Prefer a gap with size > 0.15% for visual clarity; fall back to any
        sql = text("""
            SELECT id, ticker, ts AT TIME ZONE 'UTC', timeframe, gap_type, direction,
                   zone_top, zone_bottom, size_pct,
                   bar1_ts AT TIME ZONE 'UTC', bar3_ts AT TIME ZONE 'UTC'
            FROM gaps
            WHERE ticker = :tk AND gap_type = :gt AND direction = :dir
              AND timeframe = :tf AND size_pct > 0.10
            ORDER BY size_pct DESC
            LIMIT 1
        """)
        with engine.connect() as c:
            row = c.execute(sql, {"tk": ticker, "gt": gap_type,
                                   "dir": direction, "tf": timeframe}).fetchone()

    if row is None:
        raise ValueError("No gap found matching criteria")

    return {
        "id": row[0], "ticker": row[1], "ts": row[2],
        "timeframe": row[3], "gap_type": row[4], "direction": row[5],
        "zone_top": float(row[6]), "zone_bottom": float(row[7]),
        "size_pct": float(row[8]),
        "bar1_ts": row[9], "bar3_ts": row[10],
    }


def fetch_bars_around(engine, gap: dict, n_bars_before: int = 20,
                      n_bars_after: int = 10) -> pd.DataFrame:
    """Load OHLC bars surrounding the gap detection timestamp."""
    tf = gap["timeframe"]
    ts = gap["ts"]  # UTC naive (from AT TIME ZONE 'UTC')

    if tf == "5m":
        sql = text("""
            SELECT ts AT TIME ZONE 'UTC' AS ts_utc,
                   open, high, low, close
            FROM intraday_bars
            WHERE ticker = :tk AND timeframe = '5m'
              AND ts AT TIME ZONE 'UTC'
                  BETWEEN :ts - (:nb * INTERVAL '5 minutes')
                  AND     :ts + (:na * INTERVAL '5 minutes')
            ORDER BY ts
        """)
    else:
        sql = text("""
            SELECT date::timestamp AS ts_utc,
                   open, high, low, close
            FROM raw_bars
            WHERE ticker = :tk
              AND date BETWEEN (:ts - (:nb * INTERVAL '1 day'))::date
              AND              (:ts + (:na * INTERVAL '1 day'))::date
            ORDER BY date
        """)

    with engine.connect() as c:
        rows = c.execute(sql, {"tk": gap["ticker"], "ts": ts,
                                "nb": n_bars_before, "na": n_bars_after}).fetchall()

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"])
    return df


def draw_candles(ax, df: pd.DataFrame, width_frac: float = 0.6):
    """Draw OHLC candlesticks on ax. df must have ts, open, high, low, close."""
    xs = list(range(len(df)))
    for x, (_, row) in zip(xs, df.iterrows()):
        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
        color = "#26a69a" if c >= o else "#ef5350"  # green / red
        w = width_frac / 2
        # Body
        ax.add_patch(mpatches.FancyBboxPatch(
            (x - w, min(o, c)), 2 * w, max(abs(c - o), 0.0001),
            boxstyle="square,pad=0", linewidth=0.5,
            edgecolor=color, facecolor=color, zorder=3,
        ))
        # Wick
        ax.plot([x, x], [l, h], color=color, linewidth=0.8, zorder=2)
    ax.set_xlim(-1, len(df))
    # x-tick labels: show timestamp for every ~5th bar
    step = max(1, len(df) // 8)
    ax.set_xticks(range(0, len(df), step))
    ax.set_xticklabels(
        [df.iloc[i]["ts"].strftime("%m/%d %H:%M" if df["ts"].iloc[0].hour != 0 else "%Y-%m-%d")
         for i in range(0, len(df), step)],
        rotation=30, ha="right", fontsize=7,
    )


def render(gap: dict, bars: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    draw_candles(ax, bars)

    zt = gap["zone_top"]
    zb = gap["zone_bottom"]
    color = "#26a69a" if gap["direction"] == "up" else "#ef5350"  # green / red

    # Gap zone shading
    ax.axhspan(zb, zt, alpha=0.25, color=color, zorder=1, label="Gap zone")
    ax.axhline(zt, color=color, linewidth=1.0, linestyle="--", alpha=0.8)
    ax.axhline(zb, color=color, linewidth=1.0, linestyle="--", alpha=0.8)

    # Mark detection bar (C3 for FVG, gap bar for classic)
    ts_series = bars["ts"].values
    det_ts = pd.Timestamp(gap["ts"])
    det_idx = None
    for i, t in enumerate(ts_series):
        if abs((pd.Timestamp(t) - det_ts).total_seconds()) < 300:
            det_idx = i
            break

    if det_idx is not None:
        ax.axvline(det_idx, color="#ffeb3b", linewidth=1.2, alpha=0.7,
                   linestyle=":", label="Detection bar (C3)")

    # Mark C1 for FVG
    if gap["gap_type"] == "fvg" and gap["bar1_ts"] is not None:
        c1_ts = pd.Timestamp(gap["bar1_ts"])
        for i, t in enumerate(ts_series):
            if abs((pd.Timestamp(t) - c1_ts).total_seconds()) < 300:
                ax.axvline(i, color="#ce93d8", linewidth=1.0, alpha=0.7,
                           linestyle=":", label="C1 bar")
                break

    # Title and labels
    dir_str = "Bullish" if gap["direction"] == "up" else "Bearish"
    type_str = "FVG" if gap["gap_type"] == "fvg" else "Classic Gap"
    tf_str = gap["timeframe"]
    ts_label = str(gap["ts"])[:16]

    title = (f"{gap['ticker']}  {dir_str} {type_str} ({tf_str})  @{ts_label}\n"
             f"zone=[{zb:.4f}, {zt:.4f}]  size={gap['size_pct']:.4f}%")
    ax.set_title(title, color="#e0e0e0", fontsize=10, pad=8)
    ax.tick_params(colors="#9e9e9e", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#37474f")

    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_ylabel("Price", color="#9e9e9e", fontsize=8)

    legend = ax.legend(loc="upper left", fontsize=7, facecolor="#1a1a2e",
                       edgecolor="#37474f", labelcolor="#e0e0e0")

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"saved: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render gap / FVG chart")
    parser.add_argument("--ticker", default="SPY")
    parser.add_argument("--gap-type", choices=["classic", "fvg"], default="fvg")
    parser.add_argument("--timeframe", choices=["daily", "5m"], default="5m")
    parser.add_argument("--direction", choices=["up", "down"], default="up")
    parser.add_argument("--gap-id", type=int, default=None)
    parser.add_argument("--n-before", type=int, default=20)
    parser.add_argument("--n-after", type=int, default=10)
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL)

    gap = fetch_gap(engine, args.gap_id, args.ticker, args.gap_type,
                    args.timeframe, args.direction)

    bars = fetch_bars_around(engine, gap, n_bars_before=args.n_before,
                             n_bars_after=args.n_after)

    if bars.empty:
        print(f"No bars found around {gap['ts']} for {gap['ticker']} {gap['timeframe']}")
        sys.exit(1)

    ts_str = str(gap["ts"])[:10]
    fname = f"gaps_{gap['ticker']}_{gap['gap_type']}_{gap['timeframe']}_{ts_str}.png"
    out_path = OUT_DIR / fname

    render(gap, bars, out_path)


if __name__ == "__main__":
    main()
