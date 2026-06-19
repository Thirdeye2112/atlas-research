#!/usr/bin/env python
"""
sweep_v3_exits.py — compare exit strategies, net of cost, with a regime split.

Reads smc_events_v3.parquet and compares exit modes:
  fixed_2R, fixed_3R  (from max_fav_R/stopped/mtm_R)
  be_runner           (breakeven@1R + trail give-back-1R)
  partial             (half@1R + trail the rest)
For each confluence x exit mode: win% (R>0) and expectancy (net cost) on
TRAIN, OOS, and OOS split by SPY regime (bull = spy_up). Also shows expectancy
at a higher cost (0.10R) to stress the thin edge.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "reports" / "validity" / "smc_events_v3.parquet"

CONF = {
    "base":            lambda d: np.ones(len(d), bool),
    "full":            lambda d: d["c_vol"].to_numpy() & d["c_rsi"].to_numpy() & d["c_notext"].to_numpy(),
    "full+vcp":        lambda d: d["c_vol"].to_numpy() & d["c_rsi"].to_numpy() & d["c_notext"].to_numpy() & d["c_vcp"].to_numpy(),
}

def fixed_R(d, T):
    win = d["max_fav_R"].to_numpy() >= T
    return np.where(win, T, np.where(d["stopped"].to_numpy(), -1.0, d["mtm_R"].to_numpy()))

def mode_R(d, mode):
    if mode == "fixed_2R": return fixed_R(d, 2.0)
    if mode == "fixed_3R": return fixed_R(d, 3.0)
    if mode == "be_runner": return d["r_be_runner"].to_numpy()
    if mode == "partial":   return d["r_partial"].to_numpy()

def line(R, cost):
    if len(R) == 0: return (0, float("nan"), float("nan"))
    return (len(R), 100*(R > 0).mean(), R.mean() - cost)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=str(DEFAULT))
    ap.add_argument("--cost", type=float, default=0.05)
    ap.add_argument("--cost2", type=float, default=0.10)
    args = ap.parse_args()
    df = pd.read_parquet(args.parquet)
    for col in ("is_oos", "spy_up", "stopped"):
        df[col] = df[col].astype(bool)
    print(f"loaded {len(df):,} events | tickers={df['ticker'].nunique():,} | "
          f"OOS={df['is_oos'].mean()*100:.0f}% | bull(spy_up)={df['spy_up'].mean()*100:.0f}%\n")

    modes = ("fixed_2R", "fixed_3R", "be_runner", "partial")
    hdr = (f"{'conf':9}{'exit':11} | {'win_tr':>7}{'exp_tr':>8} | {'win_oos':>8}{'exp_oos':>8} | "
           f"{'exp_oosBULL':>12}{'exp_oosNON':>11} | {'exp@.10':>8}")
    print(hdr); print("-"*len(hdr))
    for cname, cf in CONF.items():
        sub = df[cf(df)]
        tr = sub[~sub["is_oos"]]; oo = sub[sub["is_oos"]]
        oo_b = oo[oo["spy_up"]]; oo_n = oo[~oo["spy_up"]]
        for mode in modes:
            ntr, wtr, etr = line(mode_R(tr, mode), args.cost)
            noo, woo, eoo = line(mode_R(oo, mode), args.cost)
            _, _, eob = line(mode_R(oo_b, mode), args.cost)
            _, _, eon = line(mode_R(oo_n, mode), args.cost)
            _, _, eoo2 = line(mode_R(oo, mode), args.cost2)
            if ntr < 100: continue
            print(f"{cname:9}{mode:11} | {wtr:>6.1f}%{etr:>8.3f} | {woo:>7.1f}%{eoo:>8.3f} | "
                  f"{eob:>12.3f}{eon:>11.3f} | {eoo2:>8.3f}")
        print()
    print("exp = expectancy in R net of cost. exp@.10 = OOS expectancy at 0.10R cost.")
    print("Want: exp>0 on train AND OOS AND OOS-NON-bull (regime-robust), survives @.10.")

if __name__ == "__main__":
    main()
