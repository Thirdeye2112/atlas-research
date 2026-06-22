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

SAFE-RUN CONTROLS (hardening pass): a bare run with no flags processes only
the first DEFAULT_DEV_LIMIT (25) tickers from the Atlas universe -- it
CANNOT accidentally process the full 3000+ ticker clean_universe.csv.
Three modes, decided in this order:
    1. --symbols AAPL,SPY,...   -- explicit list, ignores the universe file entirely
    2. --all-universe           -- the ONLY way to process the full universe
    3. (neither given)          -- first --limit (default 25) tickers of the
                                    universe -- the safe default
Every run prints which mode it's in before making any API calls.

Universe source: config.settings.CLEAN_UNIVERSE_CSV (the existing Atlas
canonical ticker whitelist, config/clean_universe.csv). Falls back to a
small liquid-name test list only if that file can't be loaded.

Per-ticker fetch failures are retried (MAX_FETCH_ATTEMPTS, skipping retry
for permanent 401/403 errors) and, if still failing, logged to
failed_tickers.csv rather than silently dropped. Every run also writes
snapshot_audit.json with run-level stats (coverage, DTE range, runtime,
success/failure lists) -- written unconditionally, even on a run with zero
failures or zero contracts.

SAFETY: this script must never import order-placing classes (asserted by
tests/test_options_connector_safety.py). It only ever calls
TradingClient.get_option_contracts() -- a read-only reference-data call.

Usage (PowerShell, cwd = repo root):
    Dev/test (default-safe, cannot process the full universe):
        .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py
        .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py --symbols AAPL,SPY,NVDA
        .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py --limit 25
    Full universe (explicit opt-in required):
        .venv\\Scripts\\python.exe scripts\\options_snapshot_universe.py --all-universe

Output:
    data/raw/options_snapshots/date=YYYY-MM-DD/options_contracts_snapshot.csv
    data/raw/options_snapshots/date=YYYY-MM-DD/snapshot_audit.json
    data/raw/options_snapshots/date=YYYY-MM-DD/failed_tickers.csv
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
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
DEFAULT_DEV_LIMIT = 25
MAX_FETCH_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 1.5
PERMANENT_ERROR_TYPES = ("401_unauthorized", "403_forbidden_or_entitlement")
SOURCE_LABEL = "alpaca_contract_reference"

FAILED_TICKERS_COLUMNS = ["ticker", "error_type", "error_message", "attempt_count"]


def load_full_universe() -> list[str]:
    """The Atlas canonical clean-universe whitelist, or the small fallback
    list if it can't be loaded. No cap applied here -- resolve_universe()
    decides how much of this to actually use."""
    try:
        import config.settings as settings
        csv_path = Path(settings.CLEAN_UNIVERSE_CSV)
        if not csv_path.exists():
            raise FileNotFoundError(csv_path)
        df = pd.read_csv(csv_path)
        tickers = df["ticker"].dropna().astype(str).str.upper().tolist()
        print(f"Atlas universe source: {len(tickers)} ticker(s) from {csv_path}.")
        return tickers
    except Exception as exc:
        print(f"WARNING: could not load the Atlas universe source ({type(exc).__name__}: {exc}). "
              f"Falling back to a small test list: {FALLBACK_UNIVERSE}")
        return list(FALLBACK_UNIVERSE)


def resolve_universe(symbols: str | None, limit: int, all_universe: bool) -> tuple[list[str], str]:
    """Decides which tickers to process and which mode this run is in.
    Returns (tickers, mode_label). Safe by construction: the only way to
    process the full clean_universe.csv is --all-universe; every other path
    is capped at --limit (default 25)."""
    if symbols:
        tickers = [t.strip().upper() for t in symbols.split(",") if t.strip()]
        if all_universe:
            print("NOTE: --symbols given; ignoring --all-universe.")
        return tickers, f"DEV/TEST (--symbols, {len(tickers)} ticker(s))"

    full = load_full_universe()

    if all_universe:
        return full, f"FULL UNIVERSE (--all-universe, {len(full)} ticker(s))"

    capped = full[:limit]
    return capped, f"DEV/TEST (--limit {limit}, first {len(capped)} of {len(full)} loaded)"


def filter_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    """tradable true if field exists: drop rows explicitly marked
    not-tradable, but don't drop rows just because the field is missing
    (we can't confirm those are NOT tradable)."""
    if df.empty or "tradable" not in df.columns:
        return df
    return df[df["tradable"].fillna(True) == True].copy()  # noqa: E712


def fetch_with_retries(client, ticker: str, exp_gte: date, exp_lte: date, contracts_limit: int, status) -> tuple[list, dict | None, int]:
    """Up to MAX_FETCH_ATTEMPTS attempts. Does not retry permanent
    auth/entitlement errors (401/403) -- retrying those wastes time without
    any chance of success. Returns (contracts, error_or_None, attempt_count)."""
    contracts: list = []
    error: dict | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        contracts, error = fetch_contracts(client, ticker, exp_gte, exp_lte, contracts_limit, status=status)
        if error is None:
            return contracts, None, attempt
        if error["error_type"] in PERMANENT_ERROR_TYPES:
            return contracts, error, attempt
        if attempt < MAX_FETCH_ATTEMPTS:
            print(f"    retrying {ticker} (attempt {attempt} failed: {error['error_type']})")
            time.sleep(RETRY_BACKOFF_SECONDS)
    return contracts, error, MAX_FETCH_ATTEMPTS


def build_audit(run_timestamp: str, paper_mode: bool, tickers: list[str], tickers_successful: list[str],
                 tickers_failed: list[str], snapshot: pd.DataFrame, runtime_seconds: float) -> dict:
    contracts_total = len(snapshot)
    if contracts_total:
        oi_with = int(snapshot["open_interest"].notna().sum())
        close_with = int(snapshot["close_price"].notna().sum())
        exp = pd.to_datetime(snapshot["expiration_date"], errors="coerce")
        dte = (exp - pd.Timestamp(date.today())).dt.days.dropna()
        min_dte = int(dte.min()) if not dte.empty else None
        max_dte = int(dte.max()) if not dte.empty else None
        oi_coverage_pct = round(oi_with / contracts_total * 100, 2)
        close_price_coverage_pct = round(close_with / contracts_total * 100, 2)
    else:
        oi_with = close_with = 0
        min_dte = max_dte = None
        oi_coverage_pct = close_price_coverage_pct = None

    return {
        "run_timestamp": run_timestamp,
        "paper_mode": paper_mode,
        "tickers_requested": tickers,
        "tickers_successful": tickers_successful,
        "tickers_failed": tickers_failed,
        "contracts_total": contracts_total,
        "contracts_with_open_interest": oi_with,
        "contracts_with_close_price": close_with,
        "oi_coverage_pct": oi_coverage_pct,
        "close_price_coverage_pct": close_price_coverage_pct,
        "min_dte": min_dte,
        "max_dte": max_dte,
        "runtime_seconds": round(runtime_seconds, 2),
        "source": SOURCE_LABEL,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=None, help="comma-separated explicit override; skips the Atlas universe source entirely")
    ap.add_argument("--limit", type=int, default=DEFAULT_DEV_LIMIT,
                     help=f"cap on number of universe tickers processed in dev/test mode (default {DEFAULT_DEV_LIMIT})")
    ap.add_argument("--all-universe", action="store_true",
                     help="required to process the FULL clean_universe.csv (3000+ tickers, one API call each) -- "
                          "without this flag, runs are always capped to --limit or --symbols")
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

    t0 = time.time()
    run_timestamp = datetime.now(timezone.utc).isoformat()

    tickers, mode_label = resolve_universe(args.symbols, args.limit, args.all_universe)
    print(f"=== MODE: {mode_label} ===")

    exp_gte = date.today()
    exp_lte = exp_gte + timedelta(days=args.days)

    settings = load_settings()
    client = get_trading_client(settings)
    print(f"Account mode: {'PAPER' if settings['paper'] else 'LIVE'} | {len(tickers)} ticker(s) | "
          f"expiration window: {exp_gte} .. {exp_lte} | status=active")

    frames = []
    tickers_successful = []
    failed_rows = []
    for i, t in enumerate(tickers, 1):
        contracts, error, attempts = fetch_with_retries(client, t, exp_gte, exp_lte, args.contracts_limit, AssetStatus.ACTIVE)
        df = normalize_records(contracts, t)
        df = filter_snapshot(df)
        if error is None:
            tickers_successful.append(t)
            print(f"  [{i}/{len(tickers)}] {t}: {len(df)} active/tradable contracts in window (attempt {attempts})")
        else:
            failed_rows.append({
                "ticker": t, "error_type": error["error_type"],
                "error_message": error["error_message"], "attempt_count": attempts,
            })
            print(f"  [{i}/{len(tickers)}] {t}: FAILED after {attempts} attempt(s) -- {error['error_type']}")
        frames.append(df)

    snapshot = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    tickers_failed = [row["ticker"] for row in failed_rows]

    out_dir = REPO_ROOT / "data" / "raw" / "options_snapshots" / f"date={date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = out_dir / "options_contracts_snapshot.csv"
    snapshot.to_csv(snapshot_path, index=False)

    runtime_seconds = time.time() - t0
    audit = build_audit(run_timestamp, settings["paper"], tickers, tickers_successful, tickers_failed, snapshot, runtime_seconds)
    audit_path = out_dir / "snapshot_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    failed_path = out_dir / "failed_tickers.csv"
    pd.DataFrame(failed_rows, columns=FAILED_TICKERS_COLUMNS).to_csv(failed_path, index=False)

    print(f"\nWrote {len(snapshot)} total rows across {len(tickers_successful)}/{len(tickers)} successful ticker(s) -> {snapshot_path}")
    print(f"Audit -> {audit_path}")
    print(f"Failed tickers ({len(failed_rows)}) -> {failed_path}")
    print("No orders were placed. Every call above is get_option_contracts() (read-only reference data).")


if __name__ == "__main__":
    main()
