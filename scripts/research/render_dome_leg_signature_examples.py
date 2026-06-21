#!/usr/bin/env python
"""
render_dome_leg_signature_examples.py
========================================
Renders 2 annotated example charts: a clean up-leg ("dome") and a clean
down-leg ("bowl"), with the leg start, the early-signature window (first 5
bars), the peak/trough, and the correction that ends the leg all marked.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\render_dome_leg_signature_examples.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from sqlalchemy import create_engine, text

from dome_leg_signature_common import DATABASE_URL, EARLY_N

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKTREE_ROOT / "reports" / "research" / "charts"

EXAMPLES = [
    {"label": "up_dome", "ticker": "AAPL", "leg_dir": "up",
     "start_ts": "2025-04-09 19:00:00+00:00", "peak_ts": "2025-04-09 19:50:00+00:00",
     "corr_ts": "2025-04-10 13:30:00+00:00"},
    {"label": "down_bowl", "ticker": "INTC", "leg_dir": "down",
     "start_ts": "2025-02-14 14:45:00+00:00", "peak_ts": "2025-02-14 15:40:00+00:00",
     "corr_ts": "2025-02-14 20:35:00+00:00"},
]

LOOKBACK_EXTRA = 8
FORWARD_EXTRA = 6


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
    bars = load_bars(engine, ex["ticker"])
    start_ts, peak_ts, corr_ts = (pd.Timestamp(ex["start_ts"]), pd.Timestamp(ex["peak_ts"]), pd.Timestamp(ex["corr_ts"]))
    idx0 = bars.index[bars["ts"] == start_ts]
    idxp = bars.index[bars["ts"] == peak_ts]
    idxc = bars.index[bars["ts"] == corr_ts]
    if len(idx0) == 0 or len(idxp) == 0:
        print(f"  skip {ex['label']}: bars not found")
        return None
    t0, tp = idx0[0], idxp[0]
    tc = idxc[0] if len(idxc) else tp
    lo = max(0, t0 - LOOKBACK_EXTRA)
    hi = min(len(bars) - 1, tc + FORWARD_EXTRA)
    window = bars.iloc[lo:hi + 1].copy().reset_index(drop=True)
    window["_off"] = window.index - (t0 - lo)

    fig, ax = plt.subplots(figsize=(11, 6))
    draw_candles(ax, window)

    early_end_offset = min(EARLY_N, tp - t0)
    ax.axvspan(-0.5, early_end_offset + 0.5, color="#3498db", alpha=0.12, zorder=1,
               label=f"early-signature window (first {EARLY_N} bars)")
    ax.axvline(0, color="#2c3e50", lw=1.2, ls="--", zorder=2, label="leg start")
    ax.axvline(tp - t0, color="#8e3aa3", lw=1.2, ls="--", zorder=2, label="peak/trough")
    if len(idxc):
        ax.axvline(tc - t0, color="#e67e22", lw=1.2, ls=":", zorder=2, label="correction end (forward outcome)")

    leg_word = "dome (up-leg)" if ex["leg_dir"] == "up" else "bowl (down-leg)"
    title = f"{ex['ticker']} 5m | {leg_word}\nstart={start_ts} | peak/trough={peak_ts} | correction_end={corr_ts}"
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("bars relative to leg start (5m)")
    ax.set_ylabel("price")
    ax.legend(loc="best", fontsize=7)
    ax.grid(alpha=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"dl_{ex['label']}.png"
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
