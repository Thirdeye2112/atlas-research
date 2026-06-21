#!/usr/bin/env python
"""
render_setup_formation_v2_examples.py
========================================
Renders a handful of annotated 5m candlestick charts per ticker, picked from
research_setup_formation_v2 rows already written by
run_setup_formation_v2_measurement.py, so a human can eyeball whether the
tool-state snapshot at a high-confluence (and, for contrast, a near-zero
confluence) decision point matches their eye.

For each ticker, picks one HIGH-confluence (>=5) and one QUIET (confluence=0)
SETUP decision point (in-sample, most recent, forward_k=5), shows lookback
context, the 2-bar decision window highlighted, the decision point T, and the
full per-tool state/active annotation as a text box.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\render_setup_formation_v2_examples.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pandas as pd
from sqlalchemy import create_engine, text

from setup_formation_v2_common import DATABASE_URL, TICKERS, N_WINDOW, TOOL_NAMES

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = WORKTREE_ROOT / "reports" / "research" / "charts"

LOOKBACK_EXTRA = 12
FORWARD_K = 5

STATE_COLS = ["state_candle", "state_volume", "state_macd", "state_rsi", "state_ema",
              "state_vwap", "state_atr", "state_swing", "state_orb"]
ACTIVE_COLS = ["active_" + t for t in TOOL_NAMES]


def pick_examples(engine) -> pd.DataFrame:
    rows = []
    with engine.connect() as conn:
        for ticker in TICKERS:
            for label, where in (
                ("high_confluence", "confluence_count >= 5"),
                ("quiet", "confluence_count = 0"),
            ):
                q = text(f"""
                    SELECT ticker, decision_ts, confluence_count, active_tools_csv,
                           {", ".join(STATE_COLS)}, {", ".join(ACTIVE_COLS)},
                           direction_candle, forward_return, hit_target, in_sample_flag
                    FROM research_setup_formation_v2
                    WHERE ticker = :t AND forward_k = :k AND in_sample_flag = TRUE
                      AND {where}
                    ORDER BY decision_ts DESC
                    LIMIT 1
                """)
                r = conn.execute(q, {"t": ticker, "k": FORWARD_K}).mappings().fetchone()
                if r:
                    d = dict(r)
                    d["_label"] = label
                    rows.append(d)
    return pd.DataFrame(rows)


def load_window_bars(engine, ticker: str, decision_ts, lookback_extra: int, forward_k: int) -> pd.DataFrame:
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
    lo = max(0, t - N_WINDOW + 1 - lookback_extra)
    hi = min(len(df) - 1, t + forward_k)
    window = df.iloc[lo:hi + 1].copy().reset_index(drop=True)
    window["_t_offset"] = window.index - (t - lo)
    return window


def draw_candles(ax, window: pd.DataFrame):
    for _, row in window.iterrows():
        x = row["_t_offset"]
        color = "#27ae60" if row["close"] >= row["open"] else "#c0392b"
        ax.plot([x, x], [row["low"], row["high"]], color=color, lw=1.0, zorder=3)
        body_lo, body_hi = sorted([row["open"], row["close"]])
        height = max(body_hi - body_lo, (row["high"] - row["low"]) * 0.02)
        ax.add_patch(Rectangle((x - 0.3, body_lo), 0.6, height,
                                facecolor=color, edgecolor=color, alpha=0.85, zorder=4))

    decision_offsets = window[(window["_t_offset"] <= 0) & (window["_t_offset"] > -N_WINDOW)]["_t_offset"]
    if len(decision_offsets):
        ax.axvspan(decision_offsets.min() - 0.5, 0.5, color="#3498db", alpha=0.10, zorder=1)
    ax.axvline(0, color="#2c3e50", lw=1.2, ls="--", zorder=2)


def render_example(engine, ex: dict, out_dir: Path):
    ticker = ex["ticker"]
    window = load_window_bars(engine, ticker, ex["decision_ts"], LOOKBACK_EXTRA, FORWARD_K)
    if window.empty:
        print(f"  skip {ticker} @ {ex['decision_ts']}: bars not found")
        return None

    fig, ax = plt.subplots(figsize=(11, 6.5))
    draw_candles(ax, window)

    active_set = set(ex["active_tools_csv"].split(",")) if ex["active_tools_csv"] else set()
    annot_lines = [f"confluence={ex['confluence_count']}  active=[{ex['active_tools_csv'] or 'none'}]"]
    for tool, state_col in zip(TOOL_NAMES, STATE_COLS):
        marker = "*" if tool in active_set else " "
        annot_lines.append(f"{marker} {tool:7s}: {ex[state_col]}")
    annot_text = "\n".join(annot_lines)

    ax.text(0.01, 0.98, annot_text, transform=ax.transAxes, fontsize=8,
            family="monospace", va="top", ha="left",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.85, edgecolor="#999"))

    hit_str = "n/a" if ex["hit_target"] is None else ("HIT" if ex["hit_target"] else "NO-HIT")
    fwd_ret = ex["forward_return"]
    title = (
        f"{ticker} 5m | N={N_WINDOW} decision window | label={ex['_label']} | "
        f"direction_candle={ex['direction_candle']}\n"
        f"decision={ex['decision_ts']} | fwd5_return={fwd_ret:.3f}% | {hit_str} "
        f"(blue band = the {N_WINDOW}-bar decision window; dashed line = decision point T; "
        f"* = active tool)"
    )
    ax.set_title(title, fontsize=9)
    ax.set_xlabel("bars relative to decision point T (5m)")
    ax.set_ylabel("price")
    ax.grid(alpha=0.2)

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"v2_{ticker}_{ex['_label']}_{pd.Timestamp(ex['decision_ts']).strftime('%Y%m%dT%H%M')}.png"
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
        print("No examples found in research_setup_formation_v2 -- run the measurement first.")
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
