#!/usr/bin/env python
"""
render_pattern_fulfillment_examples.py
=========================================
Renders 3 annotated example charts: a confirmed pattern that paid (WIN), a
confirmed pattern that failed (LOSS), and an invalidation-becomes inversion
trade. Pulls specific known-good instances from research_pattern_fulfillment
(picked via ad hoc query during this session) and re-loads the surrounding
bars for plotting -- same candlestick-rendering style as the setup-formation
v1/v2 example renderers (Agg backend, green/red bodies, blue band, dashed
decision line, ATR target lines).

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\render_pattern_fulfillment_examples.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from sqlalchemy import create_engine, text

from pattern_fulfillment_common import DATABASE_URL

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKTREE_ROOT / "reports" / "research" / "charts"

EXAMPLES = [
    {"label": "tweezer_top_WIN", "ticker": "AAPL", "timeframe": "5m",
     "pattern_type": "tweezer_top", "instance_ts": "2026-06-04 19:25:00+00:00",
     "event_ts": "2026-06-04 19:30:00+00:00", "direction": "short", "max_r": 3,
     "title_suffix": "confirmed + Stage B WIN (R=3)"},
    {"label": "tweezer_top_LOSS", "ticker": "INTC", "timeframe": "5m",
     "pattern_type": "tweezer_top", "instance_ts": "2026-06-18 16:50:00+00:00",
     "event_ts": "2026-06-18 17:00:00+00:00", "direction": "short", "max_r": 0,
     "title_suffix": "confirmed + Stage B LOSS"},
    {"label": "double_top_INVERSION_WIN", "ticker": "AAPL", "timeframe": "daily",
     "pattern_type": "double_top", "instance_ts": "2026-04-06 00:00:00+00:00",
     "event_ts": "2026-04-15 00:00:00+00:00", "direction": "long", "max_r": 1,
     "title_suffix": "INVALIDATED -> inversion (long) WIN (R=1)"},
]

LOOKBACK_EXTRA = {"5m": 12, "daily": 15}
FORWARD_BARS = {"5m": 26, "daily": 17}


def load_bars(engine, ticker, timeframe):
    if timeframe == "5m":
        df = pd.read_sql(text("SELECT ts, open, high, low, close FROM intraday_bars "
                               "WHERE ticker=:t AND timeframe='5m' ORDER BY ts"),
                          engine, params={"t": ticker})
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    else:
        df = pd.read_sql(text("SELECT date, open, high, low, close FROM raw_bars "
                               "WHERE ticker=:t ORDER BY date"), engine, params={"t": ticker})
        df["ts"] = pd.to_datetime(df["date"], utc=True)
    return df.reset_index(drop=True)


def draw_candles(ax, window, recog_offset, event_offset):
    for _, row in window.iterrows():
        x = row["_off"]
        color = "#27ae60" if row["close"] >= row["open"] else "#c0392b"
        ax.plot([x, x], [row["low"], row["high"]], color=color, lw=1.0, zorder=3)
        body_lo, body_hi = sorted([row["open"], row["close"]])
        height = max(body_hi - body_lo, (row["high"] - row["low"]) * 0.02)
        ax.add_patch(Rectangle((x - 0.3, body_lo), 0.6, height,
                                facecolor=color, edgecolor=color, alpha=0.85, zorder=4))
    ax.axvline(recog_offset, color="#2c3e50", lw=1.2, ls="--", zorder=2, label="recognition (T_recog)")
    if event_offset != recog_offset:
        ax.axvline(event_offset, color="#8e44ad", lw=1.2, ls=":", zorder=2, label="stage A event")


def render_example(engine, ex: dict, out_dir: Path):
    bars = load_bars(engine, ex["ticker"], ex["timeframe"])
    inst_ts = pd.Timestamp(ex["instance_ts"])
    event_ts = pd.Timestamp(ex["event_ts"])
    idx = bars.index[bars["ts"] == inst_ts]
    eidx = bars.index[bars["ts"] == event_ts]
    if len(idx) == 0 or len(eidx) == 0:
        print(f"  skip {ex['label']}: bars not found")
        return None
    t0, te = idx[0], eidx[0]
    lb = LOOKBACK_EXTRA[ex["timeframe"]]
    fb = FORWARD_BARS[ex["timeframe"]]
    lo = max(0, t0 - lb)
    hi = min(len(bars) - 1, te + fb)
    window = bars.iloc[lo:hi + 1].copy().reset_index(drop=True)
    window["_off"] = window.index - (t0 - lo)
    recog_offset = 0
    event_offset = te - t0

    entry = bars["close"].iloc[te]
    fig, ax = plt.subplots(figsize=(11, 6))
    draw_candles(ax, window, recog_offset, event_offset)

    direction = ex["direction"]
    sign = 1.0 if direction == "long" else -1.0
    high_s, low_s, close_s = bars["high"], bars["low"], bars["close"]
    prev_close = close_s.shift(1)
    tr = pd.concat([high_s - low_s, (high_s - prev_close).abs(), (low_s - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(span=14, adjust=False).mean().iloc[te]
    stop = entry - sign * atr
    ax.axhline(stop, color="#c0392b", lw=0.9, ls=":", alpha=0.7, label="stop (1x ATR)")
    for r in (1, 2, 3):
        tgt = entry + sign * r * atr
        ax.axhline(tgt, color="#27ae60", lw=0.8, ls=":", alpha=0.5 if r != ex["max_r"] else 0.9)

    ax.legend(loc="best", fontsize=7)
    title = f"{ex['ticker']} {ex['timeframe']} | {ex['pattern_type']} | {ex['title_suffix']}\n" \
            f"recognition={inst_ts} | stage_a_event={event_ts} | direction={direction}"
    ax.set_title(title, fontsize=9)
    ax.set_xlabel(f"bars relative to recognition ({ex['timeframe']})")
    ax.set_ylabel("price")
    ax.grid(alpha=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"pf_{ex['label']}.png"
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
