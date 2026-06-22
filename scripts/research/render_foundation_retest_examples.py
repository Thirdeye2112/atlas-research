#!/usr/bin/env python
"""
render_foundation_retest_examples.py
=======================================
Renders 2 annotated example charts: the closest near-miss trigger
(swing_pivot_high_confirmed, a WIN -- instructive because it's tempting and
still doesn't survive multiple-testing) and the consistent "fade the
breakout" pattern (channel_break_up, a LOSS -- instructive because it shows
the breakout's own direction losing to its R-bracket).

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\render_foundation_retest_examples.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from sqlalchemy import create_engine, text

from foundation_retest_common import DATABASE_URL, TICKER

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKTREE_ROOT / "reports" / "research" / "charts"

EXAMPLES = [
    {"label": "swing_pivot_high_NEARMISS_WIN", "decision_ts": "2026-06-05 14:30:00+00:00",
     "direction": "short", "max_r": 2, "title_suffix": "closest near-miss trigger -- WIN (R=2), does NOT survive BH-FDR"},
    {"label": "channel_break_up_FADE_LOSS", "decision_ts": "2026-06-12 19:50:00+00:00",
     "direction": "long", "max_r": 0, "title_suffix": "consistent 'fade the breakout' pattern -- LOSS, does NOT survive BH-FDR",
     "forward_override": 3},
]

LOOKBACK = 14
FORWARD = 16


def load_bars(engine, ticker):
    df = pd.read_sql(text("SELECT ts, open, high, low, close FROM intraday_bars "
                           "WHERE ticker=:t AND timeframe='5m' ORDER BY ts"), engine, params={"t": ticker})
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.reset_index(drop=True)


def draw_candles(ax, window):
    for _, row in window.iterrows():
        x = row["_off"]
        color = "#27ae60" if row["close"] >= row["open"] else "#c0392b"
        ax.plot([x, x], [row["low"], row["high"]], color=color, lw=1.0, zorder=3)
        body_lo, body_hi = sorted([row["open"], row["close"]])
        height = max(body_hi - body_lo, (row["high"] - row["low"]) * 0.02)
        ax.add_patch(Rectangle((x - 0.3, body_lo), 0.6, height,
                                facecolor=color, edgecolor=color, alpha=0.85, zorder=4))


def render_example(engine, ex: dict, out_dir: Path):
    bars = load_bars(engine, TICKER)
    dts = pd.Timestamp(ex["decision_ts"])
    idx = bars.index[bars["ts"] == dts]
    if len(idx) == 0:
        print(f"  skip {ex['label']}: bar not found")
        return None
    t0 = idx[0]
    fwd = ex.get("forward_override", FORWARD)
    lo = max(0, t0 - LOOKBACK)
    hi = min(len(bars) - 1, t0 + fwd)
    window = bars.iloc[lo:hi + 1].copy().reset_index(drop=True)
    window["_off"] = window.index - (t0 - lo)

    entry = bars["close"].iloc[t0]
    high_s, low_s, close_s = bars["high"], bars["low"], bars["close"]
    prev_close = close_s.shift(1)
    tr = pd.concat([high_s - low_s, (high_s - prev_close).abs(), (low_s - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=14, adjust=False).mean().iloc[t0]

    direction = ex["direction"]
    sign = 1.0 if direction == "long" else -1.0
    stop = entry - sign * atr

    fig, ax = plt.subplots(figsize=(11, 6))
    draw_candles(ax, window)
    ax.axvline(0, color="#2c3e50", lw=1.2, ls="--", zorder=2, label="decision (trigger fires)")
    ax.axhline(stop, color="#c0392b", lw=0.9, ls=":", alpha=0.7, label="stop (1x ATR)")
    for r in (1, 2, 3):
        tgt = entry + sign * r * atr
        ax.axhline(tgt, color="#27ae60", lw=0.8, ls=":", alpha=0.9 if r == ex["max_r"] else 0.4)

    ax.legend(loc="best", fontsize=7)
    title = f"{TICKER} 5m | {ex['label'].split('_')[0]}_{ex['label'].split('_')[1]} | {ex['title_suffix']}\n" \
            f"decision={dts} | direction={direction}"
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("bars relative to decision point (5m)")
    ax.set_ylabel("price")
    ax.grid(alpha=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"fr_{ex['label']}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  saved {path}")
    return path


def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    saved = []
    for ex in EXAMPLES:
        p = render_example(engine, ex, OUT_DIR)
        if p:
            saved.append(str(p))
    print(f"\nDone. {len(saved)} charts saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
