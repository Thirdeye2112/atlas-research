#!/usr/bin/env python
"""
options_snapshot_universe.py
================================
Milestone 5: daily snapshot of option-contract reference data
(open_interest, close_price, etc.) across an Atlas ticker universe.
RESEARCH/BACKTESTING ONLY -- read-only, no orders. Reuses the contract-fetch
logic from options_list_contracts.py (fetch_contracts/normalize_records)
rather than duplicating it.

This is NOT trade-flow data -- it is contract reference data + open interest
only. See docs/options_flow_data_limitations.md for the full picture of
what's available vs not on this account (no OPRA: no historical trade
tape, no real historical volume). This snapshot is the raw input for
options_build_oi_structure_features.py.

Universe: loads config.settings.CLEAN_UNIVERSE_CSV (the existing Atlas
canonical ticker whitelist, config/clean_universe.csv) by default. Falls
back to a small liquid-name test list only if that file can't be loaded.
Pass --tickers to override explicitly, or --limit to cap how many universe
tickers are processed in one run -- the full clean_universe.csv is 3000+
tickers, one API call each, so --limit or --tickers is recommended for
interactive runs.

SAFETY: this script must never import order-placing classes (asserted by
tests/test_options_connector_safety.py). It only ever calls
TradingClient.get_option_contracts() -- a read-only reference-data call.

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py --tickers AAPL,MSFT,NVDA,TSLA,SPY,QQQ,CLF
    .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py --limit 50
    .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py          # full clean_universe.csv, no cap

Output: data/raw/options_snapshots/date=YYYY-MM-DD/options_contracts_snapshot.csv
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
# Running `python scripts/options_snapshot_universe.py` puts scripts/ at
# sys.path[0] automatically (so the sibling-script import below just works),
# but NOT the repo root -- needed for `import config.settings` regardless of
# the invoking cwd.
sys.path.insert(0, str(REPO_ROOT))

# Sibling-script import -- reuses the already-tested contract-fetch logic
# instead of duplicating it (per the brief).
from options_list_contracts import load_settings, get_trading_client, fetch_contracts, normalize_records  # noqa: E402

FALLBACK_UNIVERSE = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ", "CLF"]
EXPIRATION_WINDOW_DAYS = 60


def load_universe(explicit: str | None, limit: int | None) -> list[str]:
    if explicit:
        tickers = [t.strip().upper() for t in explicit.split(",") if t.strip()]
        print(f"Universe: {len(tickers)} ticker(s) from --tickers override.")
        return tickers

    try:
        import config.settings as settings
        csv_path = Path(settings.CLEAN_UNIVERSE_CSV)
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)
        df = pd.read_csv(csv_path)
        tickers = df["ticker"].dropna().astype(str).str.upper().tolist()
        print(f"Universe: {len(tickers)} ticker(s) loaded from {csv_path} "
              f"(Atlas canonical clean-universe whitelist).")
    except Exception as exc:
        print(f"WARNING: could not load the Atlas universe source ({type(exc).__name__}: {exc}). "
              f"Falling back to a small test list: {FALLBACK_UNIVERSE}")
        tickers = list(FALLBACK_UNIVERSE)

    if limit and limit > 0 and len(tickers) > limit:
        print(f"Capping to the first {limit} of {len(tickers)} ticker(s) (--limit {limit}). "
              f"This script makes one API call per ticker -- raise --limit or omit it to "
              f"process the full universe.")
        tickers = tickers[:limit]
    elif not limit:
        print(f"NOTE: no --limit given -- this run will make {len(tickers)} sequential "
              f"contract-fetch API calls. Pass --limit N to test on a subset first.")
    return tickers


def filter_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """tradable true if field exists: drop rows explicitly marked
    not-tradable, but don't drop rows just because the field is missing
    (we can't confirm those are NOT tradable)."""
    if df.empty or "tradable" not in df.columns:
        return df
    return df[df["tradable"].fillna(True) == True].copy()  # noqa: E712


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=None, help="comma-separated override; skips the Atlas universe source")
    ap.add_argument("--limit", type=int, default=None, help="cap on number of universe tickers processed (no cap if omitted)")
    ap.add_argument("--days", type=int, default=EXPIRATION_WINDOW_DAYS, help="expiration window: today..today+days")
    ap.add_argument("--contracts-limit", type=int, default=0,
                     help="max contracts per ticker, 0 = unbounded (paginate until exhausted). "
                          "Unbounded is the default and is needed to actually reach the full "
                          "--days window for liquid names -- capping at e.g. 1000 silently "
                          "truncates to only the nearest few expirations for names with large "
                          "chains (confirmed: AAPL alone has 1400+ active contracts in a 60-day "
                          "window, exhausting a 1000 cap before reaching dte>25).")
    args = ap.parse_args()

    from alpaca.trading.enums import AssetStatus

    tickers = load_universe(args.tickers, args.limit)
    exp_gte = date.today()
    exp_lte = exp_gte + timedelta(days=args.days)

    settings = load_settings()
    client = get_trading_client(settings)
    print(f"Mode: {'PAPER' if settings['paper'] else 'LIVE'} | {len(tickers)} ticker(s) | "
          f"expiration window: {exp_gte} .. {exp_lte} | status=active")

    frames = []
    for i, t in enumerate(tickers, 1):
        contracts = fetch_contracts(client, t, exp_gte, exp_lte, args.contracts_limit, status=AssetStatus.ACTIVE)
        df = normalize_records(contracts, t)
        df = filter_snapshot(df)
        print(f"  [{i}/{len(tickers)}] {t}: {len(df)} active/tradable contracts in window")
        frames.append(df)

    snapshot = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    out_dir = REPO_ROOT / "data" / "raw" / "options_snapshots" / f"date={date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "options_contracts_snapshot.csv"
    snapshot.to_csv(out_path, index=False)
    print(f"\nWrote {len(snapshot)} total rows across {len(tickers)} ticker(s) -> {out_path}")
    print("No orders were placed. Every call above is get_option_contracts() (read-only reference data).")


if __name__ == "__main__":
    main()
