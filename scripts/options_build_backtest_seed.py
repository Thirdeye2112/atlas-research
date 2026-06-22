#!/usr/bin/env python
"""
options_build_backtest_seed.py
================================
Milestone 4: merge the contracts reference data with the latest quote/
trade/snapshot probe, and compute first-pass backtest-seed fields.
RESEARCH/BACKTESTING ONLY -- no API calls of its own, just merges the CSVs
already written by the previous two scripts.

This is NOT the feature engine -- it's a seed/staging table to confirm the
fields line up before any real feature-engineering or DB integration.

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_build_backtest_seed.py

Output: data/processed/alpaca_options_backtest_seed_<date>.csv
"""
from __future__ import annotations

import glob
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent


def _latest(pattern: str) -> Path | None:
    candidates = sorted(glob.glob(str(REPO_ROOT / "data" / "raw" / pattern)))
    return Path(candidates[-1]) if candidates else None


def _load_or_die(pattern: str, label: str) -> pd.DataFrame:
    path = _latest(pattern)
    if path is None:
        print(f"ERROR: no {label} CSV found matching data/raw/{pattern}. "
              f"Run the script that produces it first.")
        sys.exit(1)
    print(f"  {label}: {path.name}")
    return pd.read_csv(path)


def normalize_records(contracts: pd.DataFrame, quotes: pd.DataFrame, trades: pd.DataFrame,
                       snaps: pd.DataFrame) -> pd.DataFrame:
    df = contracts.merge(quotes.add_prefix("quote_").rename(columns={"quote_symbol": "symbol"}),
                          on="symbol", how="left")
    df = df.merge(trades.add_prefix("trade_").rename(columns={"trade_symbol": "symbol"}),
                  on="symbol", how="left")
    df = df.merge(snaps.add_prefix("snap_").rename(columns={"snap_symbol": "symbol"}),
                  on="symbol", how="left")

    # Prefer snapshot fields (one consistent call) for price; fall back to the
    # standalone quote/trade probe if the snapshot didn't return one.
    bid = df.get("snap_bid_price", pd.Series(np.nan, index=df.index)).fillna(df.get("quote_bid_price"))
    ask = df.get("snap_ask_price", pd.Series(np.nan, index=df.index)).fillna(df.get("quote_ask_price"))
    trade_price = df.get("snap_trade_price", pd.Series(np.nan, index=df.index)).fillna(df.get("trade_price"))
    trade_size = df.get("snap_trade_size", pd.Series(np.nan, index=df.index)).fillna(df.get("trade_size"))

    df["bid"] = bid
    df["ask"] = ask
    df["option_mid"] = np.where(bid.notna() & ask.notna(), (bid + ask) / 2.0, np.nan)
    spread = ask - bid
    df["spread_pct"] = np.where(
        df["option_mid"].notna() & (df["option_mid"] != 0),
        spread / df["option_mid"],
        np.nan,
    )

    df["premium_estimate"] = np.where(
        trade_price.notna() & trade_size.notna(),
        trade_price * trade_size * 100,
        np.nan,
    )
    # NOTE: "volume" (a daily traded-contract count, distinct from a single
    # trade's size) is NOT fetched by options_market_data_test.py in
    # this milestone -- it would require OptionBarsRequest's bar.volume
    # field, and Step 0 of this connector's investigation found daily option
    # bars to be extremely sparse on this account's indicative feed (no real
    # historical trade tape backing them). Left as NaN rather than computed
    # from a mismatched proxy (e.g. a single trade's size is not "volume").
    df["volume"] = np.nan
    df["open_interest_num"] = pd.to_numeric(df["open_interest"], errors="coerce")
    df["volume_oi_ratio"] = np.where(
        df["volume"].notna() & df["open_interest_num"].notna() & (df["open_interest_num"] != 0),
        df["volume"] / df["open_interest_num"],
        np.nan,
    )

    exp = pd.to_datetime(df["expiration_date"], errors="coerce")
    df["dte"] = (exp - pd.Timestamp(date.today())).dt.days

    keep = [
        "underlying_symbol", "symbol", "name", "type", "expiration_date", "strike_price", "dte",
        "tradable", "open_interest", "open_interest_date", "close_price", "close_price_date",
        "bid", "ask", "option_mid", "spread_pct",
        "trade_price" if "trade_price" in df.columns else None,
        "trade_size" if "trade_size" in df.columns else None,
        "premium_estimate", "volume", "volume_oi_ratio",
        "snap_implied_volatility", "snap_delta",
        "quote_status", "trade_status", "snap_status",
    ]
    keep = [c for c in keep if c and c in df.columns]
    return df[keep].copy()


def main():
    print("Loading inputs:")
    contracts = _load_or_die("alpaca_option_contracts_*.csv", "contracts")
    quotes = _load_or_die("alpaca_option_quotes_*.csv", "quotes")
    trades = _load_or_die("alpaca_option_trades_*.csv", "trades")
    snaps = _load_or_die("alpaca_option_snapshots_*.csv", "snapshots")

    # Only the symbols actually probed in milestone 3 will have quote/trade/
    # snapshot data attached -- the merge is left-join from contracts, so
    # un-probed contracts simply carry NaN for those columns (expected).
    seed = normalize_records(contracts, quotes, trades, snaps)

    out_dir = REPO_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"alpaca_options_backtest_seed_{date.today().isoformat()}.csv"
    seed.to_csv(out_path, index=False)

    n_probed = seed["quote_status"].notna().sum() if "quote_status" in seed.columns else 0
    print(f"\nWrote {len(seed)} rows ({n_probed} with market-data probe results attached) -> {out_path}")
    print("\nColumn summary (non-null counts):")
    print(seed.notna().sum().to_string())

    # --- Postgres insertion point -------------------------------------------
    # CSV only for this milestone. Future DB write: create a migration for a
    # dedicated options_flow / options_backtest_seed table (see
    # reports/research/OPTIONS_FLOW_OVERLAY.md for the schema this repo's
    # research branches were originally going to use), then:
    #   from sqlalchemy import create_engine
    #   import config.settings as settings
    #   engine = create_engine(settings.DATABASE_URL)
    #   seed.to_sql("options_backtest_seed", engine, if_exists="append", index=False)


if __name__ == "__main__":
    main()
