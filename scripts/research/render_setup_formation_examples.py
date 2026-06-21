#!/usr/bin/env python
"""
render_setup_formation_examples.py
=====================================
Renders a handful of annotated 5m candlestick charts per ticker, picked from
research_setup_formation rows already written by run_setup_formation_measurement.py,
so a human can eyeball whether a "SETUP_FORMING" call matches their eye.

For each (ticker, n_window in {2, 5}), picks one SETUP_FORMING example that hit
its forward target and one that didn't (in-sample only -- this is a visual
sanity check of the classifier, not held-out evaluation). Shows lookback
context, the classified N-window highlighted, the decision point T, and the
next 5 bars with the +-1*ATR14 target lines so the forward outcome is visible.

Usage (cwd = C:\\Atlas\\atlas-research, the main checkout -- see
setup_formation_common.py for why):
    .venv\\Scripts\\python.exe scripts\\research\\render_setup_formation_examples.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
import pandas as pd
from sqlalchemy import create_engine, text

import setup_formation_common as cfg
from setup_formation_common import DATABASE_URL, TICKERS, ATR_HIT_MULT

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKTREE_ROOT / "reports" / "research" / "charts"

LOOKBACK_EXTRA = 10   # bars of context shown before the N-window starts
EXAMPLE_N_VALUES = [2, 5]


def pick_examples(engine) -> pd.DataFrame:
    rows = []
    with engine.connect() as conn:
        for ticker in TICKERS:
            for n_window in EXAMPLE_N_VALUES:
                for want_hit in (True, False):
                    q = text("""
                        SELECT ticker, n_window, decision_ts, setup_state, setup_type,
                               direction, daily_context, forward_k, forward_return,
                               hit_target, in_sample_flag
                        FROM research_setup_formation
                        WHERE ticker = :t AND n_window = :n AND forward_k = 5
                          AND setup_state = 'SETUP_FORMING' AND in_sample_flag = TRUE
                          AND hit_target = :h
                        ORDER BY decision_ts DESC
                        LIMIT 1
                    """)
                    r = conn.execute(q, {"t": ticker, "n": n_window, "h": want_hit}).mappings().fetchone()
                    if r:
                        rows.append(dict(r))
    return pd.DataFrame(rows)


def load_window_bars(engine, ticker: str, decision_ts, n_window: int, lookback_extra: int, forward_k: int) -> pd.DataFrame:
    """Pull enough raw bars around decision_ts to show lookback context, the
    N-window, and the forward_k outcome bars, plus a little trailing ATR
    context (20 bars before the window start) for the ATR-target lines."""
    df = pd.read_sql(
        text("""
            SELECT ts, open, high, low, close, volume
            FROM intraday_bars
            WHERE ticker = :t AND timeframe = '5m'
            ORDER BY ts
        """),
        engine, params={"t": ticker},
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df = df.reset_index(drop=True)
    idx = df.index[df["ts"] == pd.Timestamp(decision_ts)]
    if len(idx) == 0:
        return pd.DataFrame()
    t = idx[0]
    lo = max(0, t - n_window + 1 - lookback_extra)
    hi = min(len(df) - 1, t + forward_k)
    window = df.iloc[lo:hi + 1].copy().reset_index(drop=True)
    window["_t_offset"] = window.index - (t - lo)   # 0 at decision point T
    window["_atr14"] = _atr14(df["close"], df["high"], df["low"]).iloc[lo:hi + 1].to_numpy()
    return window


def _atr14(close, high, low, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low, (high - prev_close).abs(), (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def draw_candles(ax, window: pd.DataFrame, n_window: int):
    for _, row in window.iterrows():
        x = row["_t_offset"]
        color = "#27ae60" if row["close"] >= row["open"] else "#c0392b"
        ax.plot([x, x], [row["low"], row["high"]], color=color, lw=1.0, zorder=3)
        body_lo, body_hi = sorted([row["open"], row["close"]])
        height = max(body_hi - body_lo, (row["high"] - row["low"]) * 0.02)
        ax.add_patch(Rectangle((x - 0.3, body_lo), 0.6, height,
                                facecolor=color, edgecolor=color, alpha=0.85, zorder=4))

    decision_idx_offsets = window[(window["_t_offset"] <= 0) & (window["_t_offset"] > -n_window)]["_t_offset"]
    if len(decision_idx_offsets):
        ax.axvspan(decision_idx_offsets.min() - 0.5, 0.5, color="#3498db", alpha=0.10, zorder=1)
    ax.axvline(0, color="#2c3e50", lw=1.2, ls="--", zorder=2)


def render_example(engine, ex: dict, out_dir: Path):
    ticker = ex["ticker"]; n_window = ex["n_window"]
    window = load_window_bars(engine, ticker, ex["decision_ts"], n_window, LOOKBACK_EXTRA, 5)
    if window.empty:
        print(f"  skip {ticker} N={n_window} @ {ex['decision_ts']}: bars not found")
        return None

    t_row = window[window["_t_offset"] == 0].iloc[0]
    close_T, atr_T = t_row["close"], t_row["_atr14"]

    fig, ax = plt.subplots(figsize=(11, 6))
    draw_candles(ax, window, n_window)

    if ex["direction"] in ("long", "short") and pd.notna(atr_T):
        target_up = close_T + ATR_HIT_MULT * atr_T
        target_down = close_T - ATR_HIT_MULT * atr_T
        ax.axhline(target_up, color="#27ae60", lw=0.8, ls=":", alpha=0.6, label=f"+{ATR_HIT_MULT}xATR")
        ax.axhline(target_down, color="#c0392b", lw=0.8, ls=":", alpha=0.6, label=f"-{ATR_HIT_MULT}xATR")
        ax.legend(loc="upper left", fontsize=8)

    hit_str = "HIT" if ex["hit_target"] else "NO-HIT"
    title = (
        f"{ticker} 5m | N={n_window} window={ex['setup_type']} dir={ex['direction']} "
        f"| daily_ctx={ex['daily_context']}\n"
        f"decision={ex['decision_ts']} | fwd5_return={ex['forward_return']:.2f}% | {hit_str} "
        f"(blue band = the {n_window}-bar decision window; dashed line = decision point T)"
    )
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("bars relative to decision point T (5m)")
    ax.set_ylabel("price")
    ax.grid(alpha=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{ticker}_N{n_window}_{ex['setup_type']}_{hit_str}_{pd.Timestamp(ex['decision_ts']).strftime('%Y%m%dT%H%M')}.png"
    path = out_dir / fname
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
    print(f"  saved {path}")
    return path


def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    examples = pick_examples(engine)
    if examples.empty:
        print("No SETUP_FORMING examples found in research_setup_formation -- run the measurement first.")
        return
    print(f"Picked {len(examples)} example decision points.")
    saved = []
    for _, ex in examples.iterrows():
        p = render_example(engine, ex.to_dict(), OUT_DIR)
        if p:
            saved.append(str(p))
    print(f"\nDone. {len(saved)} charts saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
