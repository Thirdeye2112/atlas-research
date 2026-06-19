#!/usr/bin/env python
"""
pattern_learn.py — the "wisdom" layer: read pattern_outcomes.parquet and learn
which pattern + context combinations are both HIGH WIN-RATE and PROFITABLE.

Reports per slice:
  win%      = target hit before stop (the plain win rate)
  exp(R)    = expectancy in R  (win -> +target:risk, loss -> -1, timeout -> ~0)
Because some patterns have reward:risk < 1, a high win% isn't automatically
profitable — exp(R) is the truth check. We then rank setups that clear a win
floor AND are profitable, with enough samples.

Usage: python scripts/pattern_learn.py [--min-win 70] [--min-n 300]
"""
from __future__ import annotations
import argparse, itertools
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PARQ = ROOT / "reports" / "ta" / "pattern_outcomes.parquet"
CTX = ["aligned", "vol_confirm", "above_200", "weekly_up"]


def metrics(d):
    n = len(d)
    if n == 0: return 0, float("nan"), float("nan")
    win = d["win"].mean()
    # expectancy in R: win -> +rr, loss -> -1, timeout -> 0
    rr = d["rr"].clip(upper=5).fillna(1.0)
    R = np.where(d["outcome"].to_numpy()=="win", rr,
         np.where(d["outcome"].to_numpy()=="loss", -1.0, 0.0))
    return n, 100*win, float(np.mean(R))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=str(PARQ))
    ap.add_argument("--min-win", type=float, default=70.0)
    ap.add_argument("--min-n", type=int, default=300)
    args = ap.parse_args()
    df = pd.read_parquet(args.parquet)
    for c in CTX: df[c] = df[c].astype(bool)
    print(f"loaded {len(df):,} patterns | {df['ticker'].nunique():,} tickers | "
          f"{df['date'].min().date()} -> {df['date'].max().date()}\n")

    print("=== by pattern (all contexts) ===")
    print(f"{'pattern':14}{'n':>8}{'win%':>8}{'exp(R)':>9}{'med R:R':>9}")
    for nm in sorted(df["name"].unique()):
        d = df[df.name==nm]; n,w,e = metrics(d)
        print(f"{nm:14}{n:>8,}{w:>7.1f}%{e:>9.3f}{d['rr'].median():>9.2f}")

    # search pattern x any subset of context flags for high-win, profitable setups
    print(f"\n=== high-confidence setups (win>={args.min_win}%, exp>0, n>={args.min_n}) ===")
    found = []
    for nm in df["name"].unique():
        base = df[df.name==nm]
        for k in range(0, len(CTX)+1):
            for combo in itertools.combinations(CTX, k):
                d = base
                for c in combo: d = d[d[c]]
                n,w,e = metrics(d)
                if n>=args.min_n and w>=args.min_win and e>0:
                    found.append((nm, combo, n, w, e))
    # keep the most selective/strongest, dedup by pattern keeping best win
    found.sort(key=lambda x:(-x[3], -x[4]))
    if not found:
        print("  (none cleared the bar — lower --min-win or refine entries/stops)")
    for nm, combo, n, w, e in found[:20]:
        ctx = "+".join(combo) if combo else "(any)"
        print(f"  {nm:13} {ctx:34} n={n:>6,} win={w:5.1f}% exp={e:+.3f}R")
    print("\nwin = target before stop; exp(R) accounts for reward:risk (the profit truth-check).")


if __name__ == "__main__":
    main()
