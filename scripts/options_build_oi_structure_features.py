#!/usr/bin/env python
"""
options_build_oi_structure_features.py
=========================================
Milestone 6: turn the latest options_contracts_snapshot.csv (written by
options_snapshot_universe.py) into per-ticker open-interest STRUCTURE
features. RESEARCH/BACKTESTING ONLY -- no API calls of its own, pure
local computation (CSV + a read-only join against raw_bars for spot price).

This is an OI/reference-data overlay, NOT trade flow: it answers "where is
existing open interest parked, and how concentrated/short-dated is it" --
not "what traded today" or "who was aggressing." There is no real daily
option volume on this account (no OPRA), so volume_oi_ratio-style features
are never computed here. See docs/options_flow_data_limitations.md.

Moneyness thresholds (documented here, not hidden in code):
    NEAR_MONEY_BAND_PCT = 0.05   -- strike within +-5% of spot = "near money"
    SHORT_DATED_DTE_MAX = 30     -- days-to-expiration <= 30 = "short-dated"
OTM call/put are "clearly OTM" -- beyond the near-money band on the OTM
side -- so near-money and OTM buckets don't double-count the same OI.

Underlying price: joined from the existing raw_bars OHLCV table (latest
available close per ticker, read-only). If raw_bars is unreachable, or a
given ticker has no row in it, underlying_close is left null for that
ticker and the moneyness-dependent features (near_money_*, otm_*) are
skipped for it -- logged explicitly, not silently NaN.

SAFETY: this script must never import order-placing classes (asserted by
tests/test_options_connector_safety.py). It makes no Alpaca API calls at
all -- CSV + DB read only.

Usage (PowerShell, cwd = repo root):
    .venv\\Scripts\\python.exe scripts\\options_build_oi_structure_features.py

Output: data/processed/options_oi_structure_features_<snapshot-date>.csv
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

REPO_ROOT = Path(__file__).resolve().parent.parent
# Needed for `import config.settings` inside load_underlying_closes(),
# regardless of the invoking cwd -- see options_snapshot_universe.py for the
# same fix and why it's needed (sys.path[0] is the script's own directory,
# not the repo root, no matter how the script is invoked).
sys.path.insert(0, str(REPO_ROOT))

NEAR_MONEY_BAND_PCT = 0.05
SHORT_DATED_DTE_MAX = 30

MONEYNESS_FEATURES = ["near_money_call_oi", "near_money_put_oi", "otm_call_oi", "otm_put_oi"]


def find_latest_snapshot() -> tuple[Path, str] | tuple[None, None]:
    base = REPO_ROOT / "data" / "raw" / "options_snapshots"
    if not base.exists():
        return None, None
    date_dirs = sorted(d for d in base.glob("date=*") if (d / "options_contracts_snapshot.csv").exists())
    if not date_dirs:
        return None, None
    latest = date_dirs[-1]
    snapshot_date = latest.name.split("=", 1)[1]
    return latest / "options_contracts_snapshot.csv", snapshot_date


def load_underlying_closes(tickers: list[str]) -> pd.DataFrame:
    """Read-only join against raw_bars. Returns an empty-but-correctly-shaped
    frame (all tickers absent -> underlying_close NaN after merge) if the DB
    is unreachable or the table doesn't exist -- the caller doesn't need to
    branch on success/failure, the left-merge handles both uniformly."""
    cols = ["underlying_symbol", "underlying_close_date", "underlying_close"]
    try:
        import config.settings as settings
        from sqlalchemy import create_engine, text, bindparam

        engine = create_engine(settings.DATABASE_URL)
        query = (
            text("""
                SELECT DISTINCT ON (ticker) ticker AS underlying_symbol,
                       date AS underlying_close_date, close AS underlying_close
                FROM raw_bars
                WHERE ticker IN :tickers
                ORDER BY ticker, date DESC
            """)
            .bindparams(bindparam("tickers", expanding=True))
        )
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"tickers": tickers})
        print(f"Underlying prices: joined {len(df)}/{len(tickers)} ticker(s) from raw_bars.")
        return df
    except Exception as exc:
        print(f"WARNING: could not join underlying prices from raw_bars ({type(exc).__name__}: {exc}). "
              f"underlying_close will be null for ALL tickers -- {MONEYNESS_FEATURES} will be skipped "
              f"for every ticker (placeholder column, per the brief).")
        return pd.DataFrame(columns=cols)


def moneyness_pct(strike, underlying_close):
    """(strike / spot) - 1. Positive = strike above spot, negative = below,
    zero = at the money. Works on scalars or pandas Series/numpy arrays."""
    return strike / underlying_close - 1


def is_otm_call(strike, underlying_close):
    """Textbook definition, no near-money band: a call is OTM iff its
    strike is above spot."""
    return strike > underlying_close


def is_itm_call(strike, underlying_close):
    return strike < underlying_close


def is_otm_put(strike, underlying_close):
    """A put is OTM iff its strike is below spot (the inverse of a call)."""
    return strike < underlying_close


def is_itm_put(strike, underlying_close):
    return strike > underlying_close


def _safe_div(num, den):
    if den is None or den == 0 or pd.isna(den):
        return float("nan")
    return num / den


def _top_strike_and_concentration(oi: pd.Series, strikes: pd.Series) -> tuple[float, float]:
    """OI summed per strike (across expirations at that strike), then the
    single most-concentrated strike and what fraction of that side's total
    OI sits there. NaN/NaN if there's no OI data at all for this side."""
    if oi.empty:
        return float("nan"), float("nan")
    by_strike = oi.groupby(strikes).sum(min_count=1).dropna()
    if by_strike.empty:
        return float("nan"), float("nan")
    top_strike = float(by_strike.idxmax())
    top_oi = float(by_strike.max())
    concentration = _safe_div(top_oi, float(by_strike.sum()))
    return top_strike, concentration


def compute_ticker_features(ticker: str, df: pd.DataFrame, underlying_close, underlying_close_date, today: date) -> dict:
    total = len(df)
    oi = pd.to_numeric(df["open_interest"], errors="coerce")
    contract_type = df["type"].astype(str).str.lower()
    is_call = contract_type == "call"
    is_put = contract_type == "put"
    strike = pd.to_numeric(df["strike_price"], errors="coerce")

    total_call_oi = oi[is_call].sum(skipna=True)
    total_put_oi = oi[is_put].sum(skipna=True)

    exp = pd.to_datetime(df["expiration_date"], errors="coerce")
    dte = (exp - pd.Timestamp(today)).dt.days
    short_dated = dte <= SHORT_DATED_DTE_MAX

    max_call_oi_strike, call_oi_concentration_top_strike = _top_strike_and_concentration(oi[is_call], strike[is_call])
    max_put_oi_strike, put_oi_concentration_top_strike = _top_strike_and_concentration(oi[is_put], strike[is_put])

    oi_contract_count = int(oi.notna().sum())

    feat = {
        "ticker": ticker,
        "underlying_close": underlying_close,
        "underlying_close_date": underlying_close_date,
        "contract_count_total": total,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "put_call_oi_ratio": _safe_div(total_put_oi, total_call_oi),
        "short_dated_call_oi": oi[is_call & short_dated].sum(skipna=True),
        "short_dated_put_oi": oi[is_put & short_dated].sum(skipna=True),
        "max_call_oi_strike": max_call_oi_strike,
        "max_put_oi_strike": max_put_oi_strike,
        "call_oi_concentration_top_strike": call_oi_concentration_top_strike,
        "put_oi_concentration_top_strike": put_oi_concentration_top_strike,
        "oi_contract_count": oi_contract_count,
        "oi_coverage_pct": _safe_div(oi_contract_count, total) * 100 if total else float("nan"),
    }

    if underlying_close is None or pd.isna(underlying_close):
        for col in MONEYNESS_FEATURES:
            feat[col] = float("nan")
        return feat, True

    near_money = (strike - underlying_close).abs() / underlying_close <= NEAR_MONEY_BAND_PCT
    # "Clearly" OTM = textbook OTM (is_otm_call/is_otm_put) minus the
    # near-money band, so near_money_*_oi and otm_*_oi never double-count
    # the same open interest. Equivalent to the original
    # strike > spot*(1+band) / strike < spot*(1-band) formulas -- this form
    # makes the relationship to the strict definitions explicit.
    otm_call = is_call & is_otm_call(strike, underlying_close) & ~near_money
    otm_put = is_put & is_otm_put(strike, underlying_close) & ~near_money
    feat["near_money_call_oi"] = oi[is_call & near_money].sum(skipna=True)
    feat["near_money_put_oi"] = oi[is_put & near_money].sum(skipna=True)
    feat["otm_call_oi"] = oi[otm_call].sum(skipna=True)
    feat["otm_put_oi"] = oi[otm_put].sum(skipna=True)
    return feat, False


OUTPUT_COLUMNS = [
    "ticker", "underlying_close", "underlying_close_date", "contract_count_total",
    "total_call_oi", "total_put_oi", "put_call_oi_ratio",
    "near_money_call_oi", "near_money_put_oi", "otm_call_oi", "otm_put_oi",
    "short_dated_call_oi", "short_dated_put_oi",
    "max_call_oi_strike", "max_put_oi_strike",
    "call_oi_concentration_top_strike", "put_oi_concentration_top_strike",
    "oi_contract_count", "oi_coverage_pct",
]


def main():
    snapshot_path, snapshot_date = find_latest_snapshot()
    if snapshot_path is None:
        print("ERROR: no options_contracts_snapshot.csv found under data/raw/options_snapshots/date=*/. "
              "Run scripts\\options_snapshot_universe.py first.")
        sys.exit(1)

    snapshot = pd.read_csv(snapshot_path)
    if snapshot.empty:
        print(f"ERROR: {snapshot_path} is empty -- nothing to compute features from.")
        sys.exit(1)
    print(f"Loaded {len(snapshot)} contract rows from {snapshot_path} (snapshot date {snapshot_date}).")

    tickers = sorted(snapshot["underlying_symbol"].dropna().unique().tolist())
    today = date.fromisoformat(snapshot_date)
    closes = load_underlying_closes(tickers)
    close_map = {r.underlying_symbol: (r.underlying_close, r.underlying_close_date) for r in closes.itertuples()}

    rows = []
    skipped_tickers = []
    for ticker in tickers:
        df = snapshot[snapshot["underlying_symbol"] == ticker]
        underlying_close, underlying_close_date = close_map.get(ticker, (np.nan, None))
        feat, moneyness_skipped = compute_ticker_features(ticker, df, underlying_close, underlying_close_date, today)
        rows.append(feat)
        if moneyness_skipped:
            skipped_tickers.append(ticker)
            print(f"  {ticker}: underlying_close missing -- skipping {', '.join(MONEYNESS_FEATURES)}")

    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)

    out_dir = REPO_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"options_oi_structure_features_{snapshot_date}.csv"
    out.to_csv(out_path, index=False)

    print(f"\nWrote {len(out)} ticker row(s) -> {out_path}")
    if skipped_tickers:
        print(f"Moneyness features (near_money_*/otm_*) skipped for {len(skipped_tickers)}/{len(tickers)} "
              f"ticker(s) -- no underlying_close available: {skipped_tickers}")
    else:
        print("Moneyness features computed for all tickers (underlying_close available for every ticker).")
    print("No API calls were made by this script (CSV + read-only DB join only).")


if __name__ == "__main__":
    main()
