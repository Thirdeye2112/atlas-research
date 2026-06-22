#!/usr/bin/env python
"""
options_list_contracts.py
==================================
Milestone 2: fetch active option contracts (reference data + open interest)
for a handful of underlyings via TradingClient.GetOptionContractsRequest.
RESEARCH/BACKTESTING ONLY -- read-only, no orders.

This is the TRADING API's contract endpoint, not the historical market-data
API -- it returns real open_interest / open_interest_date / close_price /
close_price_date even without an OPRA market-data subscription (confirmed
empirically against this account: these fields ARE populated). It does NOT
give a historical trade tape -- see options_market_data_test.py for
the live quote/trade/snapshot probe and its OPRA-vs-indicative findings.

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_list_contracts.py
    .venv\\Scripts\\python.exe scripts\\options_list_contracts.py --underlyings AAPL,SPY
    .venv\\Scripts\\python.exe scripts\\options_list_contracts.py --days 30 --limit 500

Output: data/raw/alpaca_option_contracts_<YYYY-MM-DD>.csv
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_UNDERLYINGS = ["AAPL", "SPY", "NVDA", "TSLA"]

OUTPUT_COLUMNS = [
    "underlying_symbol", "symbol", "name", "type", "expiration_date", "strike_price",
    "tradable", "open_interest", "open_interest_date", "close_price", "close_price_date",
]


def load_settings() -> dict:
    import os
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")
    paper = os.environ.get("ALPACA_PAPER", "true").strip().lower() not in ("false", "0", "no")
    if not api_key or not secret_key:
        print("ERROR: ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env. "
              "Run scripts\\options_check_account.py first.")
        sys.exit(1)
    return {"api_key": api_key, "secret_key": secret_key, "paper": paper}


def get_trading_client(settings: dict):
    from alpaca.trading.client import TradingClient
    return TradingClient(settings["api_key"], settings["secret_key"], paper=settings["paper"])


def fetch_contracts(client, underlying: str, exp_gte: date, exp_lte: date, limit: int, status=None) -> tuple[list, dict | None]:
    """One underlying's active option contracts in the expiration window.
    Read-only. Paginates via page_token until exhausted or `limit` reached.
    status: optional AssetStatus filter (e.g. AssetStatus.ACTIVE), passed
    through to GetOptionContractsRequest server-side. Omitted (None)
    preserves this script's original no-status-filter behavior -- used by
    options_snapshot_universe.py to request status=ACTIVE explicitly.

    Returns (contracts, error). error is None on success, or a dict with
    'error_type' and 'error_message' on failure (contracts may still hold
    whatever was fetched before the failing page) -- used by
    options_snapshot_universe.py to retry transient failures and log
    permanent ones to failed_tickers.csv."""
    from alpaca.trading.requests import GetOptionContractsRequest

    all_contracts = []
    page_token = None
    while True:
        kwargs = dict(
            underlying_symbols=[underlying],
            expiration_date_gte=exp_gte,
            expiration_date_lte=exp_lte,
            limit=min(limit - len(all_contracts), 1000) if limit else 1000,
            page_token=page_token,
        )
        if status is not None:
            kwargs["status"] = status
        req = GetOptionContractsRequest(**kwargs)
        try:
            resp = client.get_option_contracts(req)
        except Exception as exc:
            msg = str(exc)
            if "401" in msg:
                error_type = "401_unauthorized"
                print(f"  ERROR (401 Unauthorized) for {underlying}: credentials rejected.")
            elif "403" in msg:
                error_type = "403_forbidden_or_entitlement"
                print(f"  ERROR (403 Forbidden) for {underlying}: not entitled to this data: {msg}")
            else:
                error_type = f"error_{type(exc).__name__}"
                print(f"  ERROR for {underlying} ({type(exc).__name__}): {msg}")
            return all_contracts, {"error_type": error_type, "error_message": msg}
        all_contracts.extend(resp.option_contracts)
        page_token = getattr(resp, "next_page_token", None)
        if not page_token or (limit and len(all_contracts) >= limit):
            break
    return (all_contracts[:limit] if limit else all_contracts), None


def normalize_records(contracts: list, underlying: str) -> pd.DataFrame:
    if not contracts:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    rows = []
    for c in contracts:
        rows.append({
            "underlying_symbol": underlying,
            "symbol": c.symbol,
            "name": c.name,
            "type": getattr(c.type, "value", c.type),
            "expiration_date": c.expiration_date,
            "strike_price": c.strike_price,
            "tradable": c.tradable,
            "open_interest": c.open_interest,
            "open_interest_date": c.open_interest_date,
            "close_price": c.close_price,
            "close_price_date": c.close_price_date,
        })
    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--underlyings", default=",".join(DEFAULT_UNDERLYINGS))
    ap.add_argument("--days", type=int, default=45, help="expiration window: today .. today+days")
    ap.add_argument("--limit", type=int, default=1000, help="max contracts per underlying")
    args = ap.parse_args()

    underlyings = [u.strip().upper() for u in args.underlyings.split(",") if u.strip()]
    exp_gte = date.today()
    exp_lte = exp_gte + timedelta(days=args.days)

    settings = load_settings()
    client = get_trading_client(settings)
    print(f"Mode: {'PAPER' if settings['paper'] else 'LIVE'} | underlyings={underlyings} | "
          f"expiration window: {exp_gte} .. {exp_lte} | limit/underlying={args.limit}")

    frames = []
    for u in underlyings:
        contracts, _error = fetch_contracts(client, u, exp_gte, exp_lte, args.limit)
        df = normalize_records(contracts, u)
        print(f"  {u}: {len(df)} contracts")
        if not df.empty:
            n_with_oi = df["open_interest"].notna().sum()
            print(f"      with open_interest populated: {n_with_oi}/{len(df)}")
        frames.append(df)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)

    out_dir = REPO_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"alpaca_option_contracts_{date.today().isoformat()}.csv"
    out.to_csv(out_path, index=False)
    print(f"\nWrote {len(out)} total rows to {out_path}")

    # --- Postgres insertion point -------------------------------------------
    # When ready to persist this to the database instead of (or alongside)
    # CSV, insert here using the same load_dotenv(find_dotenv(usecwd=True))
    # + config.settings.DATABASE_URL pattern used throughout the rest of
    # this repo's research scripts -- e.g.:
    #   from sqlalchemy import create_engine
    #   import config.settings as settings
    #   engine = create_engine(settings.DATABASE_URL)
    #   out.to_sql("options_contracts", engine, if_exists="append", index=False)
    # Not done in this milestone -- CSV only, per the brief.


if __name__ == "__main__":
    main()
