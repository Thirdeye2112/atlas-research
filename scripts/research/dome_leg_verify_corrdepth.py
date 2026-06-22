#!/usr/bin/env python
"""
Supplementary check: does the early_slope -> corr_depth correlation (the
part of the original report NOT subject to the part-whole accounting
overlap, since corr_depth is a fully separate future segment b->c) survive
the Check-2 look-ahead fix (window starting at the confirmation bar
a.idx+width, not at a.idx itself)?
"""
from __future__ import annotations
import sys
from pathlib import Path
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))
sys.path.insert(0, str(_WORKTREE_ROOT))
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=True)

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
import config.settings as settings
from atlas_research.intraday.features import compute_features
from atlas_research.ta.structure import swing_pivots

from dome_leg_verify import (
    ORIGINAL_3, FRESH_5, PIVOT_WIDTH, AMP_MULT, EARLY_N, significant_pivots, pearson_p, load_5m_bars,
)

DATABASE_URL = settings.DATABASE_URL


def build_corrdepth_check(ticker, sig_pivots, close, width=PIVOT_WIDTH, early_n=EARLY_N):
    rows = []
    n = len(close)
    for i in range(len(sig_pivots) - 1):
        a, b = sig_pivots[i], sig_pivots[i + 1]
        if a.kind == "L" and b.kind == "H":
            leg_dir = "up"
        elif a.kind == "H" and b.kind == "L":
            leg_dir = "down"
        else:
            continue
        if a.price <= 0 or b.price <= 0:
            continue
        leg_bars = b.idx - a.idx
        if leg_bars <= early_n:
            continue
        c = sig_pivots[i + 2] if i + 2 < len(sig_pivots) else None
        if c is None:
            continue
        if leg_dir == "up" and c.kind == "L":
            corr_depth = (b.price - c.price) / b.price
        elif leg_dir == "down" and c.kind == "H":
            corr_depth = (c.price - b.price) / b.price
        else:
            continue

        conf_idx = a.idx + width
        e_end2 = conf_idx + early_n
        if not (conf_idx < b.idx and e_end2 < b.idx and e_end2 < n):
            continue
        conf_price = close[conf_idx]
        if conf_price <= 0:
            continue
        if leg_dir == "up":
            early_slope_confirmed = ((close[e_end2] - conf_price) / conf_price) / early_n
        else:
            early_slope_confirmed = ((conf_price - close[e_end2]) / conf_price) / early_n

        # naive (original-style) early_slope, window starting at a.idx
        e_end_naive = a.idx + early_n
        if leg_dir == "up":
            early_slope_naive = ((close[e_end_naive] - a.price) / a.price) / early_n
        else:
            early_slope_naive = ((a.price - close[e_end_naive]) / a.price) / early_n

        rows.append(dict(ticker=ticker, leg_dir=leg_dir, corr_depth=corr_depth,
                          early_slope_naive=early_slope_naive, early_slope_confirmed=early_slope_confirmed))
    return rows


def main():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    all_rows = []
    for ticker in ORIGINAL_3 + FRESH_5:
        bars = load_5m_bars(engine, ticker)
        feat_df = compute_features(bars)
        h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
        c = feat_df["close"].to_numpy(float); atr = feat_df["atr14"].to_numpy(float)
        piv = swing_pivots(h, l, width=PIVOT_WIDTH)
        sig = significant_pivots(piv, atr, AMP_MULT)
        all_rows += build_corrdepth_check(ticker, sig, c)

    df = pd.DataFrame(all_rows)
    print(f"Total rows: {len(df)}\n")
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        sub_scope = df[df["ticker"].isin(tickers)]
        for leg_dir in ("up", "down"):
            sub = sub_scope[sub_scope["leg_dir"] == leg_dir]
            r_naive, n_naive, p_naive = pearson_p(sub["early_slope_naive"], sub["corr_depth"])
            r_conf, n_conf, p_conf = pearson_p(sub["early_slope_confirmed"], sub["corr_depth"])
            print(f"[{scope}] {leg_dir}-leg: r(early_slope NAIVE [starts at a.idx], corr_depth)={r_naive:.3f} (n={n_naive}, p={p_naive:.2e})   "
                  f"r(early_slope CONFIRMED [starts at a.idx+{PIVOT_WIDTH}], corr_depth)={r_conf:.3f} (n={n_conf}, p={p_conf:.2e})")


if __name__ == "__main__":
    main()
