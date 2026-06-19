#!/usr/bin/env python
"""
ta_render.py — render charts with detected structure / patterns marked, so a
human can confirm the system 'sees' what they see. Saves PNGs to reports/ta/.

Usage:
  python scripts/ta_render.py --ticker AAPL --start 2024-01-01 --width 5
  python scripts/ta_render.py --ticker AAPL --tf 5m --start 2026-04-01
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")

import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import text
from atlas_research.db import connection
from atlas_research.ta import structure as S
from atlas_research.ta import patterns as P

OUT = ROOT / "reports" / "ta"


def load(ticker, tf, start):
    with connection.get_connection() as c:
        if tf == "daily":
            df = pd.read_sql(text("SELECT date AS ts, high, low, close, adjusted_close "
                                  "FROM raw_bars WHERE ticker=:t AND date>=:s ORDER BY date"),
                             c, params={"t": ticker, "s": start})
            fac = df["adjusted_close"]/df["close"]
            df["high"]*=fac; df["low"]*=fac; df["close"]=df["adjusted_close"]
        else:
            df = pd.read_sql(text("SELECT ts, high, low, close FROM intraday_bars "
                                  "WHERE ticker=:t AND timeframe=:tf AND ts>=:s ORDER BY ts"),
                             c, params={"t": ticker, "tf": tf, "s": start})
    return df


def render_structure(ticker, tf, start, width):
    df = load(ticker, tf, start)
    if len(df) < 30:
        print(f"  not enough bars for {ticker} {tf}"); return None
    h=df["high"].to_numpy(); l=df["low"].to_numpy(); cl=df["close"].to_numpy()
    summ = S.structure_summary(h, l, cl, width=width)
    piv = summ["pivots"]
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(df))
    ax.plot(x, cl, color="#222", lw=1.0, label="close")
    # swing pivots
    for p in piv:
        ax.scatter(p.idx, p.price, color=("#c0392b" if p.kind=='H' else "#27ae60"), s=28, zorder=5)
    # zigzag line through pivots
    if len(piv) > 1:
        ax.plot([p.idx for p in piv], [p.price for p in piv], color="#888", lw=0.8, alpha=0.7)
    # S/R levels
    for lv in summ["levels"][:5]:
        ax.axhline(lv["level"], color=("#c0392b" if lv["side"]=="resistance" else "#27ae60"),
                   ls="--", lw=0.8, alpha=0.5)
    # trendlines
    for line, col in ((summ["res_line"], "#c0392b"), (summ["sup_line"], "#27ae60")):
        if line:
            sl, ic, idxs = line
            xx = np.array([idxs[0], len(df)-1])
            ax.plot(xx, sl*xx+ic, color=col, lw=1.2, ls=":")
    ax.set_title(f"{ticker} {tf} — structure  |  trend: {summ['trend'].upper()}  |  "
                 f"{len(piv)} swings (red=high green=low)", fontsize=12)
    ax.set_xlabel("bar"); ax.set_ylabel("price"); ax.grid(alpha=0.2)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"structure_{ticker}_{tf}.png"
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)
    print(f"  saved {path}  (trend={summ['trend']}, swings={len(piv)})")
    return path


def render_patterns(ticker, tf, start, width, want=None, max_panels=4):
    """Detect patterns and draw up to max_panels of them (zoomed) with entry/stop/target."""
    df = load(ticker, tf, start)
    if len(df) < 60:
        print(f"  not enough bars for {ticker}"); return None
    h=df["high"].to_numpy(); l=df["low"].to_numpy(); cl=df["close"].to_numpy()
    piv = S.swing_pivots(h, l, width=width)
    pats = P.detect_all(piv, h, l, cl)
    if want:
        pats = [p for p in pats if p.name == want]
    if not pats:
        print(f"  no {'/'+want if want else ''} patterns for {ticker}"); return None
    # spread selection across history
    pick = pats[:: max(1, len(pats)//max_panels)][:max_panels]
    fig, axes = plt.subplots(2, 2, figsize=(15, 9)); axes = axes.flatten()
    for ax, p in zip(axes, pick):
        idxs = [pt[0] for pt in p.points] + [p.confirm_idx]
        lo, hi = max(0, min(idxs)-15), min(len(df), max(idxs)+25)
        xx = np.arange(lo, hi)
        ax.plot(xx, cl[lo:hi], color="#222", lw=1.1)
        # key points + connectors
        px=[pt[0] for pt in p.points]; py=[pt[1] for pt in p.points]
        ax.plot(px, py, "o-", color="#8e44ad", lw=1.4, ms=6, zorder=5)
        if p.neckline is not None:
            ax.axhline(p.neckline, color="#666", ls="--", lw=0.9)
        ax.axhline(p.entry, color="#2980b9", lw=1.0, label="entry")
        ax.axhline(p.stop,  color="#c0392b", ls=":", lw=1.0, label="stop")
        ax.axhline(p.target,color="#27ae60", ls=":", lw=1.0, label="target")
        ax.axvline(p.confirm_idx, color="#2980b9", lw=0.7, alpha=0.5)
        ax.set_title(f"{p.name}  ({p.direction})  R:R={p.rr:.2f}", fontsize=11)
        ax.grid(alpha=0.2); ax.legend(fontsize=7, loc="best")
    for ax in axes[len(pick):]:
        ax.axis("off")
    fig.suptitle(f"{ticker} {tf} — detected patterns" + (f" [{want}]" if want else ""), fontsize=13)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"patterns_{ticker}_{tf}{'_'+want if want else ''}.png"
    fig.tight_layout(); fig.savefig(path, dpi=105); plt.close(fig)
    print(f"  saved {path}  ({len(pats)} {want or 'patterns'} found, showing {len(pick)})")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--tf", default="daily", choices=["daily","5m"])
    ap.add_argument("--start", default="2024-01-01")
    ap.add_argument("--width", type=int, default=5)
    ap.add_argument("--patterns", action="store_true", help="render detected patterns")
    ap.add_argument("--want", default=None, help="filter to one pattern name")
    args = ap.parse_args()
    if args.patterns:
        render_patterns(args.ticker, args.tf, args.start, args.width, args.want)
    else:
        render_structure(args.ticker, args.tf, args.start, args.width)


if __name__ == "__main__":
    main()
