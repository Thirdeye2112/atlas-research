#!/usr/bin/env python
"""
render_vwap_chart.py — Render one 5m session with price + session-VWAP overlaid.

Reads from: intraday_bars (read-only), vwap_5m (read-only).
Writes to:  reports/ta/vwap_<TICKER>_<SESSION_DATE>.png

Usage:
    python scripts/render_vwap_chart.py --ticker SPY
    python scripts/render_vwap_chart.py --ticker SPY --session 2026-06-18
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

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine, text

from config import settings

OUT = ROOT / "reports" / "ta"


def load_session(ticker: str, session_date: str, engine) -> pd.DataFrame:
    """Load one session of bars + VWAP from the DB."""
    sql = text("""
        SELECT b.ts, b.open, b.high, b.low, b.close, b.volume,
               v.vwap, v.dist_from_vwap, v.above_vwap
        FROM intraday_bars b
        JOIN vwap_5m v ON v.ticker = b.ticker AND v.ts = b.ts
        WHERE b.ticker = :tk
          AND b.timeframe = '5m'
          AND v.session_date = :sd
        ORDER BY b.ts ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tk": ticker, "sd": session_date}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume",
                                     "vwap", "dist_from_vwap", "above_vwap"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def get_latest_session(ticker: str, engine) -> str | None:
    sql = text("SELECT MAX(session_date) FROM vwap_5m WHERE ticker = :tk")
    with engine.connect() as conn:
        val = conn.execute(sql, {"tk": ticker}).scalar()
    return str(val) if val else None


def render(ticker: str, session_date: str, engine) -> Path | None:
    df = load_session(ticker, session_date, engine)
    if df.empty:
        print(f"  No data for {ticker} session {session_date} in vwap_5m")
        return None

    n = len(df)
    x = np.arange(n)

    # Convert ts to ET for x-axis labels
    et_ts = df["ts"].dt.tz_convert("America/New_York")
    label_times = [t.strftime("%H:%M") for t in et_ts]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)

    # ── Top panel: candlestick close + VWAP ─────────────────────────────────
    # Coloured candle bodies (simplified: filled bar from open to close)
    for i, row in df.iterrows():
        color = "#2ecc71" if row["close"] >= row["open"] else "#e74c3c"
        ax1.plot([i, i], [row["low"], row["high"]], color=color, lw=0.8, alpha=0.6)
        ax1.add_patch(plt.Rectangle(
            (i - 0.3, min(row["open"], row["close"])),
            0.6, abs(row["close"] - row["open"]) or 0.01,
            color=color, alpha=0.7
        ))

    ax1.plot(x, df["vwap"].values, color="#2980b9", lw=1.8, label="VWAP", zorder=4)

    # Shade region above/below VWAP
    ax1.fill_between(x, df["close"].values, df["vwap"].values,
                     where=(df["close"].values >= df["vwap"].values),
                     alpha=0.08, color="#2ecc71", label="above VWAP")
    ax1.fill_between(x, df["close"].values, df["vwap"].values,
                     where=(df["close"].values < df["vwap"].values),
                     alpha=0.08, color="#e74c3c", label="below VWAP")

    session_open = df["open"].iloc[0]
    first_bar_tp = (df["high"].iloc[0] + df["low"].iloc[0] + df["close"].iloc[0]) / 3
    first_vwap = df["vwap"].iloc[0]
    ax1.set_title(
        f"{ticker}  |  5m session: {session_date}  |  {n} bars\n"
        f"VWAP (blue) = session-cumulative (HLC/3)×vol  |  "
        f"Bar 0: tp={first_bar_tp:.3f}  VWAP[0]={first_vwap:.3f}  "
        f"(should be equal: {abs(first_bar_tp - first_vwap) < 1e-4})",
        fontsize=11,
    )
    ax1.set_ylabel("Price")
    ax1.legend(fontsize=9, loc="upper right")
    ax1.grid(alpha=0.2)

    # ── Bottom panel: dist_from_vwap ─────────────────────────────────────────
    ax2.bar(x, df["dist_from_vwap"].values,
            color=np.where(df["dist_from_vwap"].values >= 0, "#2ecc71", "#e74c3c"),
            alpha=0.7, width=0.8)
    ax2.axhline(0, color="#333", lw=0.8)
    ax2.set_ylabel("dist_from_vwap\n(close−vwap)/vwap")
    ax2.set_xlabel("Bar (5-min)")
    ax2.grid(alpha=0.2)

    # X-axis: show time labels every 6 bars (30 min)
    tick_positions = list(range(0, n, 6))
    tick_labels = [label_times[i] for i in tick_positions]
    ax1.set_xticks(tick_positions)
    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=30, fontsize=8)

    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"vwap_{ticker}_{session_date}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"  saved: {path}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default="SPY")
    ap.add_argument("--session", default=None,
                    help="Session date YYYY-MM-DD (default: latest in vwap_5m)")
    args = ap.parse_args()

    engine = create_engine(settings.DATABASE_URL)
    session_date = args.session or get_latest_session(args.ticker, engine)
    if not session_date:
        print(f"No sessions in vwap_5m for {args.ticker}")
        return
    print(f"Rendering {args.ticker} session {session_date}")
    render(args.ticker.upper(), session_date, engine)


if __name__ == "__main__":
    main()
