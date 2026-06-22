#!/usr/bin/env python
"""
options_market_data_test.py
====================================
Milestone 3: probe latest quote / latest trade / snapshot for a small list
of option symbols (read from the contracts CSV written by
options_list_contracts.py). RESEARCH/BACKTESTING ONLY -- read-only,
no orders.

Tries the INDICATIVE feed first (the free tier), since that is what most
accounts -- including this one, confirmed -- are actually entitled to.
Falls back to reporting a clear message (not a crash) if OPRA is requested
implicitly and rejected. This script's main JOB is to tell you, plainly,
which feed your account can actually use -- it is the answer to "does my
plan allow indicative/OPRA options data?", not a guarantee of usable
historical depth (see the README note at the bottom of this file's output
for what we found on this account: OPRA is not signed, and the indicative
feed has no real historical trade tape -- only current-moment snapshots).

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_market_data_test.py
    .venv\\Scripts\\python.exe scripts\\options_market_data_test.py --n-symbols 10

Output:
    data/raw/alpaca_option_quotes_<date>.csv
    data/raw/alpaca_option_trades_<date>.csv
    data/raw/alpaca_option_snapshots_<date>.csv
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> dict:
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")
    if not api_key or not secret_key:
        print("ERROR: ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env. "
              "Run scripts\\options_check_account.py first.")
        sys.exit(1)
    return {"api_key": api_key, "secret_key": secret_key}


def get_option_data_client(settings: dict):
    from alpaca.data.historical.option import OptionHistoricalDataClient
    return OptionHistoricalDataClient(settings["api_key"], settings["secret_key"])


def _latest_contracts_csv() -> Path | None:
    candidates = sorted(glob.glob(str(REPO_ROOT / "data" / "raw" / "alpaca_option_contracts_*.csv")))
    return Path(candidates[-1]) if candidates else None


def load_symbols(n: int) -> list[str]:
    csv_path = _latest_contracts_csv()
    if csv_path is None:
        print("ERROR: no alpaca_option_contracts_*.csv found in data/raw/. "
              "Run scripts\\options_list_contracts.py first.")
        sys.exit(1)
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"ERROR: {csv_path} is empty -- nothing to test.")
        sys.exit(1)
    # Prefer contracts with populated open_interest (more likely to have
    # any real quote/trade activity at all).
    df = df.sort_values("open_interest", ascending=False, na_position="last")
    symbols = df["symbol"].head(n).tolist()
    print(f"Loaded {len(df)} contracts from {csv_path.name}; testing top {len(symbols)} by open_interest.")
    return symbols


def fetch_latest_quotes(client, symbols: list[str], feed) -> pd.DataFrame:
    from alpaca.data.requests import OptionLatestQuoteRequest
    rows = []
    for sym in symbols:
        try:
            req = OptionLatestQuoteRequest(symbol_or_symbols=sym, feed=feed) if feed else \
                  OptionLatestQuoteRequest(symbol_or_symbols=sym)
            resp = client.get_option_latest_quote(req)
            q = resp.get(sym)
            if q is None:
                rows.append({"symbol": sym, "status": "no_data"})
                continue
            rows.append({"symbol": sym, "status": "ok", "timestamp": q.timestamp,
                         "bid_price": q.bid_price, "bid_size": q.bid_size,
                         "ask_price": q.ask_price, "ask_size": q.ask_size})
        except Exception as exc:
            rows.append({"symbol": sym, "status": _classify_error(exc)})
    return pd.DataFrame(rows)


def fetch_latest_trades(client, symbols: list[str], feed) -> pd.DataFrame:
    from alpaca.data.requests import OptionLatestTradeRequest
    rows = []
    for sym in symbols:
        try:
            req = OptionLatestTradeRequest(symbol_or_symbols=sym, feed=feed) if feed else \
                  OptionLatestTradeRequest(symbol_or_symbols=sym)
            resp = client.get_option_latest_trade(req)
            t = resp.get(sym)
            if t is None:
                rows.append({"symbol": sym, "status": "no_data"})
                continue
            rows.append({"symbol": sym, "status": "ok", "timestamp": t.timestamp,
                         "price": t.price, "size": t.size, "conditions": t.conditions,
                         "exchange": t.exchange})
        except Exception as exc:
            rows.append({"symbol": sym, "status": _classify_error(exc)})
    return pd.DataFrame(rows)


def fetch_snapshots(client, symbols: list[str], feed) -> pd.DataFrame:
    from alpaca.data.requests import OptionSnapshotRequest
    rows = []
    try:
        req = OptionSnapshotRequest(symbol_or_symbols=symbols, feed=feed) if feed else \
              OptionSnapshotRequest(symbol_or_symbols=symbols)
        resp = client.get_option_snapshot(req)
        for sym in symbols:
            s = resp.get(sym)
            if s is None:
                rows.append({"symbol": sym, "status": "no_data"})
                continue
            lt = s.latest_trade
            lq = s.latest_quote
            rows.append({
                "symbol": sym, "status": "ok",
                "trade_price": lt.price if lt else None, "trade_size": lt.size if lt else None,
                "trade_ts": lt.timestamp if lt else None, "trade_conditions": lt.conditions if lt else None,
                "bid_price": lq.bid_price if lq else None, "ask_price": lq.ask_price if lq else None,
                "implied_volatility": s.implied_volatility,
                "delta": s.greeks.delta if s.greeks else None,
            })
    except Exception as exc:
        status = _classify_error(exc)
        for sym in symbols:
            rows.append({"symbol": sym, "status": status})
    return pd.DataFrame(rows)


def _classify_error(exc: Exception) -> str:
    msg = str(exc)
    if "401" in msg or "unauthorized" in msg.lower():
        return f"error_401_unauthorized: {msg[:120]}"
    if "403" in msg or "OPRA" in msg:
        return f"error_403_or_entitlement: {msg[:160]}"
    if "empty" in msg.lower() or "no data" in msg.lower():
        return f"error_empty_data: {msg[:120]}"
    return f"error_{type(exc).__name__}: {msg[:160]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-symbols", type=int, default=20)
    args = ap.parse_args()

    settings = load_settings()
    client = get_option_data_client(settings)
    symbols = load_symbols(args.n_symbols)

    from alpaca.data.enums import OptionsFeed
    print("\n--- Probing feed entitlement: trying INDICATIVE (free tier) first ---")
    feed = OptionsFeed.INDICATIVE

    quotes_df = fetch_latest_quotes(client, symbols, feed)
    trades_df = fetch_latest_trades(client, symbols, feed)
    snaps_df = fetch_snapshots(client, symbols, feed)

    print("\n--- Checking whether OPRA (paid, real consolidated tape) is entitled ---")
    try:
        from alpaca.data.requests import OptionLatestQuoteRequest
        req = OptionLatestQuoteRequest(symbol_or_symbols=symbols[0], feed=OptionsFeed.OPRA)
        client.get_option_latest_quote(req)
        print("  OPRA: ENTITLED (request succeeded)")
    except Exception as exc:
        print(f"  OPRA: NOT entitled -- {_classify_error(exc)}")
        print("  (this account is on the indicative/free feed only -- aggressor-side trade "
              "classification and any real historical trade tape are not available; see "
              "reports/research/OPTIONS_FLOW_OVERLAY.md Step 0 for the full investigation)")

    out_dir = REPO_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    quotes_df.to_csv(out_dir / f"alpaca_option_quotes_{today}.csv", index=False)
    trades_df.to_csv(out_dir / f"alpaca_option_trades_{today}.csv", index=False)
    snaps_df.to_csv(out_dir / f"alpaca_option_snapshots_{today}.csv", index=False)

    print(f"\nQuotes:    {len(quotes_df)} rows ({(quotes_df['status']=='ok').sum()} ok) -> "
          f"data/raw/alpaca_option_quotes_{today}.csv")
    print(f"Trades:    {len(trades_df)} rows ({(trades_df['status']=='ok').sum()} ok) -> "
          f"data/raw/alpaca_option_trades_{today}.csv")
    print(f"Snapshots: {len(snaps_df)} rows ({(snaps_df['status']=='ok').sum()} ok) -> "
          f"data/raw/alpaca_option_snapshots_{today}.csv")

    # --- Postgres insertion point -------------------------------------------
    # As with options_list_contracts.py: CSV only for this milestone.
    # Future DB write would follow the same create_engine(settings.DATABASE_URL)
    # + .to_sql(...) pattern once a schema for raw quote/trade/snapshot rows
    # is decided (see options_flow table design discussion in
    # reports/research/OPTIONS_FLOW_OVERLAY.md).


if __name__ == "__main__":
    main()
