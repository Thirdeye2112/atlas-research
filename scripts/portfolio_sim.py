#!/usr/bin/env python
"""
portfolio_sim.py — turn per-trade R into an equity curve (Sharpe / maxDD).

Takes the validated config from smc_events_v3.parquet (bos + Stage-2 + confluence,
be_runner exit) and simulates a real portfolio:
  - risk RISK_PCT of CURRENT equity per trade (position sizing off the stop)
  - cap new trades per day at MAX_PER_DAY (concurrency proxy; holds ~1 day)
  - daily-loss limit: stop taking new trades once the day is down DAILY_LOSS_LIMIT
  - compound daily
Each trade P&L = (r_be_runner - cost) * risk_amount  [R is in units of risk].

Reports equity multiple, CAGR, annualised Sharpe, max drawdown, win rate and
trade count, for TRAIN and OOS, across a few concurrency caps.

Approximation: trades resolve within their day (horizon ~1 day), so "max
concurrent" is modelled as max new-trades-per-day. Honest first-order portfolio.

Usage:
  python scripts/portfolio_sim.py
  python scripts/portfolio_sim.py --conf full --cost 0.05 --risk 0.01
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "reports" / "validity" / "smc_events_v3.parquet"

def confmask(d, conf):
    if conf == "base": return np.ones(len(d), bool)
    m = d["c_vol"].to_numpy() & d["c_rsi"].to_numpy() & d["c_notext"].to_numpy()
    if conf == "full+vcp": m = m & d["c_vcp"].to_numpy()
    return m

def simulate(trades, start_equity, risk_pct, max_per_day, daily_loss_limit):
    """trades: DataFrame with columns date, ts, R_net (already net of cost). Chronological."""
    equity = start_equity
    daily_eq = []                     # (date, equity_end)
    n_taken = 0; wins = 0
    for date, grp in trades.groupby("date", sort=True):
        grp = grp.sort_values("ts")
        day_start = equity
        taken_today = 0
        day_pnl = 0.0
        for _, t in grp.iterrows():
            if taken_today >= max_per_day:
                break
            if day_pnl <= -daily_loss_limit * day_start:   # daily loss limit hit
                break
            risk_amt = equity * risk_pct
            pnl = t["R_net"] * risk_amt
            equity += pnl
            day_pnl += pnl
            taken_today += 1; n_taken += 1
            if t["R_net"] > 0: wins += 1
        daily_eq.append((date, equity))
    if not daily_eq:
        return None
    eq = pd.DataFrame(daily_eq, columns=["date", "equity"]).set_index("date")
    rets = eq["equity"].pct_change().dropna()
    years = max((eq.index[-1] - eq.index[0]).days / 365.25, 1e-9)
    cagr = (eq["equity"].iloc[-1] / start_equity) ** (1/years) - 1
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else float("nan")
    dd = (eq["equity"] / eq["equity"].cummax() - 1).min()
    return dict(mult=eq["equity"].iloc[-1]/start_equity, cagr=cagr, sharpe=sharpe,
                maxdd=dd, n=n_taken, win=100*wins/max(n_taken,1), days=len(eq), eq=eq)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", default=str(DEFAULT))
    ap.add_argument("--conf", default="full", choices=["base","full","full+vcp"])
    ap.add_argument("--cost", type=float, default=0.05)
    ap.add_argument("--r-cap", type=float, default=3.0,
                    help="cap per-trade R outcome (realistic max; guards untradeable fat tail)")
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--daily-loss", type=float, default=0.02)
    ap.add_argument("--start", type=float, default=100_000.0)
    args = ap.parse_args()

    df = pd.read_parquet(args.parquet)
    df = df[confmask(df, args.conf)].copy()
    df["R_net"] = df["r_be_runner"].clip(upper=args.r_cap) - args.cost
    df["ts"] = pd.to_datetime(df["ts"])
    df["date"] = df["ts"].dt.normalize()
    df["is_oos"] = df["is_oos"].astype(bool)
    print(f"Portfolio sim | conf={args.conf} exit=be_runner | risk={args.risk:.0%}/trade "
          f"daily_loss={args.daily_loss:.0%} cost={args.cost}R r_cap={args.r_cap}R | {len(df):,} signals\n")

    for split, d in (("TRAIN", df[~df["is_oos"]]), ("OOS", df[df["is_oos"]])):
        print(f"=== {split}  ({d['date'].min().date()} -> {d['date'].max().date()}, "
              f"{d['date'].nunique()} days, {len(d):,} signals) ===")
        print(f"{'max/day':>8}{'trades':>9}{'win%':>7}{'equity x':>10}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>8}")
        for mpd in (3, 5, 10, 20):
            r = simulate(d, args.start, args.risk, mpd, args.daily_loss)
            if r:
                print(f"{mpd:>8}{r['n']:>9,}{r['win']:>6.1f}%{r['mult']:>9.2f}x"
                      f"{r['cagr']*100:>7.1f}%{r['sharpe']:>8.2f}{r['maxdd']*100:>7.1f}%")
        print()
    print("Note: trades resolve within ~1 day (horizon); max/day proxies max concurrent.")
    print("CAGR/Sharpe/maxDD are first-order — fat-tailed R means real DD can exceed this.")

if __name__ == "__main__":
    main()
