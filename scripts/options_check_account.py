#!/usr/bin/env python
"""
options_check_account.py
==========================
Milestone 1 of the Alpaca options-data connector: confirm we can
authenticate and see what the account is actually entitled to. RESEARCH/
BACKTESTING ONLY -- this script only ever calls TradingClient.get_account()
(a read-only call). It never places, cancels, or modifies an order.

Run this FIRST, before any other alpaca_*.py script. The later scripts
assume credentials and paper mode are already confirmed working here.

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_check_account.py

Env vars (from .env, never hardcoded, never printed):
    ALPACA_API_KEY
    ALPACA_SECRET_KEY      (also accepts ALPACA_API_SECRET as an alias --
                             the .env in this repo already uses
                             ALPACA_SECRET_KEY; ALPACA_API_SECRET is
                             supported too in case a future .env uses that
                             name instead)
    ALPACA_PAPER           "true"/"false", default "true" -- this script
                             (and every script in this connector) defaults
                             to paper trading and must be told explicitly,
                             via this var, to use a live account.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)


def load_settings() -> dict:
    """Reads credentials from the environment. Never logs secret values."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_API_SECRET")
    paper = os.environ.get("ALPACA_PAPER", "true").strip().lower() not in ("false", "0", "no")

    missing = [name for name, val in (("ALPACA_API_KEY", api_key), ("ALPACA_SECRET_KEY", secret_key)) if not val]
    if missing:
        print(f"ERROR: missing required environment variable(s): {', '.join(missing)}")
        print("       Set them in .env at the repo root (never hardcode credentials in scripts).")
        sys.exit(1)

    return {"api_key": api_key, "secret_key": secret_key, "paper": paper}


def get_trading_client(settings: dict):
    from alpaca.trading.client import TradingClient
    return TradingClient(settings["api_key"], settings["secret_key"], paper=settings["paper"])


def _mask_account_number(acct_num: str | None) -> str:
    if not acct_num:
        return "<none>"
    acct_num = str(acct_num)
    if len(acct_num) <= 4:
        return "*" * len(acct_num)
    return "*" * (len(acct_num) - 4) + acct_num[-4:]


def main():
    settings = load_settings()
    print(f"Mode: {'PAPER' if settings['paper'] else 'LIVE'} "
          f"(set ALPACA_PAPER=false in .env to use a live account -- defaults to paper)")

    client = get_trading_client(settings)

    try:
        acct = client.get_account()
    except Exception as exc:
        msg = str(exc)
        if "401" in msg or "unauthorized" in msg.lower():
            print("ERROR (401 Unauthorized): credentials were rejected. Check ALPACA_API_KEY / "
                  "ALPACA_SECRET_KEY in .env match the account you intend to use "
                  f"({'paper' if settings['paper'] else 'live'} keys are NOT interchangeable).")
        elif "403" in msg:
            print(f"ERROR (403 Forbidden): the account exists but this call isn't permitted: {msg}")
        else:
            print(f"ERROR: could not fetch account ({type(exc).__name__}): {msg}")
        sys.exit(1)

    print()
    print("=== Account status ===")
    print(f"  status:                 {acct.status}")
    print(f"  account_number:         {_mask_account_number(acct.account_number)}")
    print(f"  paper:                  {settings['paper']}")
    print(f"  options_approved_level: {getattr(acct, 'options_approved_level', '<field not present>')}")
    print(f"  options_trading_level:  {getattr(acct, 'options_trading_level', '<field not present>')}")
    print(f"  options_buying_power:   {getattr(acct, 'options_buying_power', '<field not present>')}")
    print(f"  buying_power:           {acct.buying_power}")
    print()
    print("No orders were placed. This call is read-only (get_account()).")


if __name__ == "__main__":
    main()
