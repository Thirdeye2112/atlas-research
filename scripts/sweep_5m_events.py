#!/usr/bin/env python
"""
sweep_5m_events.py — instant win-rate / expectancy tuning over the event table.

Reads reports/validity/smc_events.parquet (from extract_5m_events.py) and
resolves ANY target/confluence combo in-memory in seconds:
    outcome_R(T) = +T            if max_fav_R >= T   (target hit before stop)
                   -1            elif stopped         (stopped out)
                   mtm_R         else                 (timed out, marked-to-market)
    win(T)       = max_fav_R >= T

Reports win% and expectancy (net of --cost R) on TRAIN and OOS for a grid of
(trigger x confluence x target), and prints the best OOS config that also holds
on train and clears a win-rate floor.

Usage:
  python scripts/sweep_5m_events.py
  python scripts/sweep_5m_events.py --cost 0.05 --min-win 45 --parquet <path>
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "reports" / "validity" / "smc_events.parquet"
TARGETS = (1.0, 1.5, 2.0, 2.5, 3.0)
CONF = {
    "base":            lambda d: np.ones(len(d), bool),
    "+vol":            lambda d: d["c_vol"].to_numpy(),
    "+vol+rsi":        lambda d: d["c_vol"].to_numpy() & d["c_rsi"].to_numpy(),
    "+vol+rsi+notext": lambda d: d["c_vol"].to_numpy() & d["c_rsi"].to_numpy() & d["c_notext"].to_numpy(),
}


def stats(df, T, cost):
    mf = df["max_fav_R"].to_numpy(); st = df["stopped"].to_numpy(); mtm = df["mtm_R"].to_numpy()
    win = mf >= T
    R = np.where(win, T, np.where(st, -1.0, mtm))
    n = len(df)
    return n, (100*win.mean() if n else float("nan")), (R.mean()-cost if n else float("nan"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=str(DEFAULT))
    ap.add_argument("--cost", type=float, default=0.05)
    ap.add_argument("--min-win", type=float, default=40.0, help="win%% floor for 'best' pick")
    ap.add_argument("--min-n-oos", type=int, default=300)
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    df["is_oos"] = df["is_oos"].astype(bool)
    print(f"loaded {len(df):,} events | tickers={df['ticker'].nunique():,} | "
          f"OOS={df['is_oos'].mean()*100:.0f}% | cost={args.cost}R\n")

    print(f"{'trigger':7}{'conf':17}{'tgt':>4} | {'n_tr':>9}{'win_tr':>7}{'exp_tr':>8} | "
          f"{'n_oos':>8}{'win_oos':>8}{'exp_oos':>8}")
    print("-"*88)
    best = None
    for trig in ("bos", "sweep"):
        dt = df[df["trigger"] == trig]
        for cname, cf in CONF.items():
            mask = cf(dt); sub = dt[mask]
            tr = sub[~sub["is_oos"]]; oo = sub[sub["is_oos"]]
            for T in TARGETS:
                ntr, wtr, etr = stats(tr, T, args.cost)
                noo, woo, eoo = stats(oo, T, args.cost)
                if ntr < 100:
                    continue
                print(f"{trig:7}{cname:17}{T:>4} | {ntr:>9,}{wtr:>6.1f}%{etr:>8.3f} | "
                      f"{noo:>8,}{woo:>7.1f}%{eoo:>8.3f}")
                # 'best' = positive & robust on BOTH splits, clears win floor on OOS
                if (noo >= args.min_n_oos and etr > 0 and eoo > 0 and woo >= args.min_win):
                    score = min(etr, eoo)
                    if best is None or score > best[0]:
                        best = (score, trig, cname, T, ntr, wtr, etr, noo, woo, eoo)
        print()

    if best:
        _, trig, cname, T, ntr, wtr, etr, noo, woo, eoo = best
        print(f"BEST robust config (win>={args.min_win}%, exp>0 both splits):")
        print(f"  {trig} | {cname} | target {T}R")
        print(f"  train: n={ntr:,} win={wtr:.1f}% exp={etr:+.3f}R | OOS: n={noo:,} win={woo:.1f}% exp={eoo:+.3f}R")
    else:
        print(f"No config cleared win>={args.min_win}% with exp>0 on both splits — "
              f"lower --min-win or improve the setup (retest entry / VCP / tighter stop).")


if __name__ == "__main__":
    main()
