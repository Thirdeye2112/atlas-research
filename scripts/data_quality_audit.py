"""
Data-quality audit and clean-universe builder for `raw_bars`.

Read-only, one-time(ish) scan of the daily price table that flags:
  1. Invalid bars (bad OHLC, nulls, negative volume)
  2. Implausible moves (bad prints / unhandled or handled stock splits)
  3. Structural issues (duplicates, gaps, short history, likely-delisted)
  4. Liquidity (recent avg dollar volume, recent median price)

...and writes:
  reports/validity/DATA_QUALITY_AUDIT.md  - human-readable summary
  reports/validity/bad_bars.parquet       - flagged bar-level issues. Columns: ticker, date,
                                             issue_type ('+'-joined if a bar trips >1 check),
                                             open/high/low/close/adjusted_close/volume (as stored,
                                             NaN where not applicable e.g. open for a move-only
                                             flag), prev_close, raw_return, adj_return,
                                             ratio_change (NaN unless issue_type involves a move/
                                             split check), n_copies (NaN unless a duplicate row).
  reports/validity/clean_universe.csv     - whitelist of trustworthy tickers

All heavy lifting (aggregation, window functions for per-ticker time series)
is pushed into SQL so we never materialize the full ~6.9M-row table in
pandas. Use --limit N to do a fast smoke-test pass on a small ticker subset
before running the full universe.

Usage:
    .venv/Scripts/python.exe scripts/data_quality_audit.py --limit 50
    .venv/Scripts/python.exe scripts/data_quality_audit.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

load_dotenv(override=True)  # .env always wins, even if a contaminated shell var (e.g. from
                              # go.ps1) already pointed DATABASE_URL at the wrong database

OUTPUT_DIR_DEFAULT = "reports/validity"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=None,
                    help="Only scan the first N tickers (alphabetical). For smoke-testing.")
    p.add_argument("--output-dir", default=OUTPUT_DIR_DEFAULT,
                    help=f"Where to write reports (default: {OUTPUT_DIR_DEFAULT})")
    p.add_argument("--min-bars", type=int, default=260,
                    help="Minimum distinct trading days required (default: 260, ~1 trading year)")
    p.add_argument("--recent-active-days", type=int, default=10,
                    help="A ticker with no bar within the most recent N distinct trading dates "
                         "in the table is flagged as likely-delisted (default: 10)")
    p.add_argument("--recent-liquidity-days", type=int, default=60,
                    help="Window (most recent N distinct trading dates) used for avg dollar "
                         "volume / median price (default: 60)")
    p.add_argument("--min-price", type=float, default=5.0,
                    help="Clean-universe minimum recent median price (default: 5.0)")
    p.add_argument("--min-adv", type=float, default=1_000_000.0,
                    help="Clean-universe minimum recent avg dollar volume (default: 1,000,000)")
    p.add_argument("--max-bad-bar-pct", type=float, default=0.005,
                    help="Clean-universe maximum bad-bar fraction (default: 0.005 = 0.5%%)")
    p.add_argument("--gap-days-threshold", type=int, default=15,
                    help="Calendar-day gap between consecutive bars (same ticker) above which "
                         "it's flagged as a large gap (default: 15 calendar days, "
                         "~10 trading days incl. weekends)")
    p.add_argument("--move-threshold", type=float, default=0.5,
                    help="Daily |adjusted_close| return above which a move is 'implausible' (default: 0.5)")
    p.add_argument("--move-threshold-extreme", type=float, default=1.0,
                    help="Second, more extreme implausible-move threshold (default: 1.0)")
    p.add_argument("--split-ratio-change-threshold", type=float, default=0.3,
                    help="Among implausible *raw-close* moves, the change in close/adjusted_close "
                         "ratio above which we conclude the split WAS absorbed by adjusted_close "
                         "('handled split', informational, not counted as bad data). Below this "
                         "threshold the ratio stayed flat despite a big price-level jump, which "
                         "means adjusted_close did NOT absorb it -> 'unhandled split or bad print' "
                         "(counted as bad data). Default: 0.3")
    p.add_argument("--canonical-out", default="config/clean_universe.csv",
                    help="On a FULL run, also write the whitelist here as the canonical "
                         "source downstream code reads (default: config/clean_universe.csv). "
                         "Set '' to skip.")
    return p.parse_args()


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")
    masked = re.sub(r"://([^:]+):[^@]+@", r"://\1:***@", url)
    print(f"[db] connecting to: {masked}")
    return create_engine(url)


def universe_cte(limit: int | None) -> str:
    """Returns a CTE definition (no trailing comma) restricting to a ticker subset if --limit given."""
    if limit:
        return f"universe AS (SELECT ticker FROM (SELECT DISTINCT ticker FROM raw_bars ORDER BY ticker LIMIT {int(limit)}) t)"
    return "universe AS (SELECT DISTINCT ticker FROM raw_bars)"


def read_sql_chunked(sql: str, engine: Engine, params: dict | None = None, chunksize: int = 200_000) -> pd.DataFrame:
    """
    Note: with the default psycopg2 driver, `chunksize` paginates pandas' own post-fetch
    processing, it does NOT make the underlying fetch server-side-cursor/streamed -- the
    driver still pulls the full result set client-side first. That's fine for these
    queries because they're already filtered/aggregated down to flagged rows (a small
    fraction of the table), never the full ~6.9M-row table. `stream_results=True` forces
    psycopg2 to use a server-side cursor so memory stays bounded even if a query somehow
    returns more rows than expected (e.g. a badly corrupted table with millions of bad bars).
    """
    conn = engine.connect().execution_options(stream_results=True)
    try:
        chunks = list(pd.read_sql(text(sql), conn, params=params, chunksize=chunksize))
    finally:
        conn.close()
    if not chunks:
        return pd.DataFrame()
    return pd.concat(chunks, ignore_index=True)


# --------------------------------------------------------------------------
# 1. Invalid bars (no time-series logic needed -> single filter pass)
# --------------------------------------------------------------------------
def find_invalid_bars(engine: Engine, u_cte: str) -> pd.DataFrame:
    sql = f"""
    WITH {u_cte}
    SELECT b.ticker, b.date, b.open, b.high, b.low, b.close, b.adjusted_close, b.volume,
           CASE
             WHEN b.open IS NULL OR b.high IS NULL OR b.low IS NULL OR b.close IS NULL
               THEN 'null_price'
             WHEN b.open <= 0 OR b.high <= 0 OR b.low <= 0 OR b.close <= 0
               THEN 'nonpositive_price'
             WHEN b.high < b.low
               THEN 'high_lt_low'
             WHEN b.close > b.high OR b.close < b.low
               THEN 'close_outside_high_low'
             WHEN b.open > b.high OR b.open < b.low
               THEN 'open_outside_high_low'
             WHEN b.volume < 0
               THEN 'negative_volume'
           END AS issue_type
    FROM raw_bars b
    JOIN universe u ON u.ticker = b.ticker
    WHERE b.open IS NULL OR b.high IS NULL OR b.low IS NULL OR b.close IS NULL
       OR b.open <= 0 OR b.high <= 0 OR b.low <= 0 OR b.close <= 0
       OR b.high < b.low
       OR b.close > b.high OR b.close < b.low
       OR b.open > b.high OR b.open < b.low
       OR b.volume < 0
    """
    return read_sql_chunked(sql, engine)


# --------------------------------------------------------------------------
# 2. Implausible moves + split classification (window functions, per ticker)
# --------------------------------------------------------------------------
def find_implausible_moves(engine: Engine, u_cte: str, move_thr: float, move_thr_extreme: float,
                             ratio_chg_thr: float) -> pd.DataFrame:
    """
    Returns one row per flagged bar with INDEPENDENT boolean flags (a bar can trip more
    than one): flag_move_50 / flag_move_100 are the literal "|adjusted_close return| >
    threshold" checks from the spec; flag_handled_split / flag_unhandled_split are the
    separate close-vs-adjusted_close divergence check. These are deliberately NOT
    collapsed into a single mutually-exclusive label: an unhandled-split bar legitimately
    *also* counts toward the headline implausible-move totals (its adjusted_close return
    is large precisely because the split wasn't absorbed), whereas a handled split
    typically will NOT trip the adjusted_close thresholds (that's what makes it "handled").
    """
    sql = f"""
    WITH {u_cte},
    ordered AS (
        SELECT b.ticker, b.date, b.close, b.adjusted_close,
               LAG(b.close) OVER (PARTITION BY b.ticker ORDER BY b.date) AS prev_close,
               LAG(b.adjusted_close) OVER (PARTITION BY b.ticker ORDER BY b.date) AS prev_adj_close
        FROM raw_bars b
        JOIN universe u ON u.ticker = b.ticker
        WHERE b.close IS NOT NULL AND b.adjusted_close IS NOT NULL
          AND b.close > 0 AND b.adjusted_close > 0
    ),
    calc AS (
        SELECT *,
               (adjusted_close / prev_adj_close) - 1.0 AS adj_return,
               (close / prev_close) - 1.0 AS raw_return,
               (close / adjusted_close) / (prev_close / prev_adj_close) - 1.0 AS ratio_change
        FROM ordered
        WHERE prev_close IS NOT NULL AND prev_adj_close IS NOT NULL
          AND prev_close > 0 AND prev_adj_close > 0
    )
    SELECT ticker, date, close, adjusted_close, prev_close, prev_adj_close,
           adj_return, raw_return, ratio_change,
           (ABS(adj_return) > {move_thr})                                              AS flag_move_50,
           (ABS(adj_return) > {move_thr_extreme})                                       AS flag_move_100,
           (ABS(raw_return) > {move_thr} AND ABS(ratio_change) > {ratio_chg_thr})        AS flag_handled_split,
           (ABS(raw_return) > {move_thr}
              AND (ratio_change IS NULL OR ABS(ratio_change) <= {ratio_chg_thr}))        AS flag_unhandled_split
    FROM calc
    WHERE ABS(adj_return) > {move_thr} OR ABS(raw_return) > {move_thr}
    """
    df = read_sql_chunked(sql, engine)
    if df.empty:
        return df

    def label(row):
        tags = []
        if row["flag_move_100"]:
            tags.append("implausible_move_extreme")
        elif row["flag_move_50"]:
            tags.append("implausible_move")
        if row["flag_unhandled_split"]:
            tags.append("unhandled_split_or_bad_print")
        if row["flag_handled_split"]:
            tags.append("handled_split_informational")
        return "+".join(tags) if tags else None

    df["issue_type"] = df.apply(label, axis=1)
    return df


# --------------------------------------------------------------------------
# 3. Structural per-ticker stats: counts, duplicates, gaps, recency
# --------------------------------------------------------------------------
def get_global_recent_dates(engine: Engine, n: int) -> list[date]:
    sql = "SELECT date FROM raw_bars GROUP BY date ORDER BY date DESC LIMIT :n"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"n": n}).fetchall()
    return [r[0] for r in rows]


def find_structural_stats(engine: Engine, u_cte: str, gap_days_threshold: int) -> pd.DataFrame:
    sql = f"""
    WITH {u_cte},
    gaps AS (
        SELECT b.ticker, b.date,
               b.date - LAG(b.date) OVER (PARTITION BY b.ticker ORDER BY b.date) AS gap_days
        FROM raw_bars b
        JOIN universe u ON u.ticker = b.ticker
    ),
    gap_agg AS (
        SELECT ticker, MAX(gap_days) AS max_gap_days,
               COUNT(*) FILTER (WHERE gap_days > {gap_days_threshold}) AS n_large_gaps
        FROM gaps
        GROUP BY ticker
    ),
    base AS (
        SELECT b.ticker,
               COUNT(*) AS row_count,
               COUNT(DISTINCT b.date) AS distinct_date_count,
               MIN(b.date) AS first_date,
               MAX(b.date) AS last_date
        FROM raw_bars b
        JOIN universe u ON u.ticker = b.ticker
        GROUP BY b.ticker
    )
    SELECT base.ticker, base.row_count, base.distinct_date_count,
           (base.row_count - base.distinct_date_count) AS duplicate_row_count,
           base.first_date, base.last_date,
           gap_agg.max_gap_days, gap_agg.n_large_gaps
    FROM base
    LEFT JOIN gap_agg ON gap_agg.ticker = base.ticker
    """
    return read_sql_chunked(sql, engine)


def find_duplicate_bars(engine: Engine, u_cte: str) -> pd.DataFrame:
    """The actual duplicated (ticker, date) rows, for bad_bars.parquet."""
    sql = f"""
    WITH {u_cte}
    SELECT b.ticker, b.date, b.open, b.high, b.low, b.close, b.adjusted_close, b.volume,
           'duplicate_ticker_date' AS issue_type,
           COUNT(*) OVER (PARTITION BY b.ticker, b.date) AS n_copies
    FROM raw_bars b
    JOIN universe u ON u.ticker = b.ticker
    WHERE (b.ticker, b.date) IN (
        SELECT b2.ticker, b2.date FROM raw_bars b2
        JOIN universe u2 ON u2.ticker = b2.ticker
        GROUP BY b2.ticker, b2.date HAVING COUNT(*) > 1
    )
    """
    return read_sql_chunked(sql, engine)


# --------------------------------------------------------------------------
# 4. Liquidity: recent avg dollar volume + median price
# --------------------------------------------------------------------------
def find_liquidity_stats(engine: Engine, u_cte: str, recent_dates: list[date]) -> pd.DataFrame:
    sql = f"""
    WITH {u_cte}
    SELECT b.ticker,
           AVG(b.close * b.volume) AS recent_avg_dollar_volume,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY b.close) AS recent_median_price,
           COUNT(*) AS recent_bar_count
    FROM raw_bars b
    JOIN universe u ON u.ticker = b.ticker
    WHERE b.date = ANY(:recent_dates)
      AND b.close IS NOT NULL AND b.close > 0 AND b.volume IS NOT NULL AND b.volume >= 0
    GROUP BY b.ticker
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"recent_dates": recent_dates})
    return df


# --------------------------------------------------------------------------
# Report writer
# --------------------------------------------------------------------------
def write_markdown_report(path: str, *, args: argparse.Namespace, n_tickers_scanned: int,
                            global_max_date: date, recent_active_cutoff: date,
                            invalid_df: pd.DataFrame, moves_df: pd.DataFrame,
                            struct_df: pd.DataFrame, dup_df: pd.DataFrame,
                            liq_df: pd.DataFrame, ticker_stats: pd.DataFrame,
                            clean_universe: pd.DataFrame, elapsed_s: float) -> None:
    n_invalid = len(invalid_df)
    n_move_50 = moves_df["flag_move_50"].sum() if len(moves_df) else 0
    n_move_100 = moves_df["flag_move_100"].sum() if len(moves_df) else 0
    n_handled_split = moves_df["flag_handled_split"].sum() if len(moves_df) else 0
    n_unhandled_split = moves_df["flag_unhandled_split"].sum() if len(moves_df) else 0
    n_dup_rows = len(dup_df)
    n_dup_tickers = dup_df["ticker"].nunique() if len(dup_df) else 0
    n_short_history = (ticker_stats["distinct_date_count"] < args.min_bars).sum()
    n_delisted = (~ticker_stats["has_recent_bar"]).sum()
    n_large_gap_tickers = (ticker_stats["n_large_gaps"].fillna(0) > 0).sum()

    def top_offenders(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
        if df.empty:
            return df
        return (df.groupby("ticker").size().sort_values(ascending=False)
                  .head(n).rename("bad_bar_count").reset_index())

    bad_moves_df = moves_df.loc[moves_df["flag_move_50"] | moves_df["flag_unhandled_split"],
                                  ["ticker", "date", "issue_type"]] if len(moves_df) else pd.DataFrame(columns=["ticker", "date", "issue_type"])
    bad_bars_all = pd.concat([
        invalid_df[["ticker", "date", "issue_type"]] if len(invalid_df) else pd.DataFrame(columns=["ticker", "date", "issue_type"]),
        bad_moves_df,
        dup_df[["ticker", "date", "issue_type"]] if len(dup_df) else pd.DataFrame(columns=["ticker", "date", "issue_type"]),
    ], ignore_index=True)
    top = top_offenders(bad_bars_all)

    lines = []
    a = lines.append
    a("# Data Quality Audit — raw_bars")
    a("")
    a(f"Generated: {pd.Timestamp.now(tz='UTC').isoformat()}  |  Scan time: {elapsed_s:.1f}s")
    a(f"Tickers scanned: {n_tickers_scanned:,}" + (f" (LIMITED to --limit {args.limit})" if args.limit else " (full universe)"))
    a(f"Table max date observed: {global_max_date}")
    a("")
    a("## Methodology / thresholds used")
    a("")
    a(f"- Min trading days required: **{args.min_bars}**")
    a(f"- 'Likely delisted' = no bar within the most recent **{args.recent_active_days}** distinct trading dates "
      f"in the table (cutoff date: **{recent_active_cutoff}**)")
    a(f"- Liquidity window: most recent **{args.recent_liquidity_days}** distinct trading dates")
    a(f"- Large-gap threshold: **{args.gap_days_threshold}** calendar days between consecutive bars (same ticker)")
    a(f"- Implausible-move thresholds (on adjusted_close daily return): **>{args.move_threshold:.0%}** and **>{args.move_threshold_extreme:.0%}**")
    a(f"- Split classification: among bars where raw `close` return exceeds {args.move_threshold:.0%}, "
      f"if the `close/adjusted_close` ratio also shifts by more than {args.split_ratio_change_threshold:.0%} "
      f"we treat it as a **handled split** (adjusted_close correctly absorbs it — informational only, "
      f"not counted as bad data). If the ratio stays roughly flat despite the big raw-close move, "
      f"that means adjusted_close did *not* absorb a real price-level jump — classified as "
      f"**unhandled_split_or_bad_print** and counted as bad data. *Caveat: this will not catch smaller-ratio "
      f"splits (e.g. 3:2, 5:4) whose raw return is below the {args.move_threshold:.0%} detection threshold — "
      f"a known limitation of reusing a single move threshold for split detection.*")
    a(f"- Clean-universe filter: recent median price ≥ **${args.min_price:.2f}**, recent avg dollar volume ≥ "
      f"**${args.min_adv:,.0f}**, bad-bar fraction < **{args.max_bad_bar_pct:.2%}**, trading days ≥ "
      f"**{args.min_bars}**, AND not likely-delisted (this last condition is *not* one of the four criteria "
      f"in the original spec — I added it because a name that delisted 11–{args.recent_active_days+50} days "
      f"ago can still clear the price/liquidity bars on its last active days yet isn't actually tradeable "
      f"today; flag this assumption if you'd rather keep delisted names in the whitelist for survivorship-bias-aware backtests.) "
      f"Bad-bar fraction is computed over **distinct flagged dates**, not raw flagged rows — a duplicated "
      f"(ticker,date) with 2 copies counts as 1 bad day, not 2, so duplicates aren't double-weighted.")
    a("")
    a("## Headline counts")
    a("")
    a(f"| Issue | Count |")
    a(f"|---|---|")
    a(f"| Invalid bars (bad OHLC / null / negative volume) | {n_invalid:,} |")
    a(f"| Implausible adjusted_close moves (>{args.move_threshold:.0%}) | {n_move_50:,} |")
    a(f"| ...of which >{args.move_threshold_extreme:.0%} | {n_move_100:,} |")
    a(f"| Handled splits (informational, not 'bad') | {n_handled_split:,} |")
    a(f"| Unhandled split / bad print (counted as bad) | {n_unhandled_split:,} |")
    a(f"| Duplicate (ticker,date) rows | {n_dup_rows:,} across {n_dup_tickers:,} tickers |")
    a(f"| Tickers with < {args.min_bars} trading days | {n_short_history:,} |")
    a(f"| Tickers with a gap > {args.gap_days_threshold}d | {n_large_gap_tickers:,} |")
    a(f"| Tickers likely delisted (no bar in last {args.recent_active_days} sessions) | {n_delisted:,} |")
    a(f"| **Clean-universe tickers** | **{len(clean_universe):,}** / {n_tickers_scanned:,} |")
    a("")
    a("## Top offenders by bad-bar count")
    a("")
    a("_Counts here are raw flagged issues — a single bar that trips two checks (e.g. an invalid-OHLC bar "
      "that also produces an implausible return) counts twice here. The clean-universe filter below instead "
      "uses **distinct flagged dates** per ticker, so a ticker can show a higher number here than its actual "
      "bad-day percentage would suggest._")
    a("")
    if top.empty:
        a("_No bad bars found._")
    else:
        a("| Ticker | Bad bar count |")
        a("|---|---|")
        for _, r in top.iterrows():
            a(f"| {r['ticker']} | {r['bad_bar_count']:,} |")
    a("")
    a("## Example flagged bars")
    a("")
    if len(invalid_df):
        a("**Invalid OHLC examples:**")
        a("")
        a("| Ticker | Date | Issue | Open | High | Low | Close | Volume |")
        a("|---|---|---|---|---|---|---|---|")
        for _, r in invalid_df.head(10).iterrows():
            a(f"| {r['ticker']} | {r['date']} | {r['issue_type']} | {r['open']} | {r['high']} | {r['low']} | {r['close']} | {r['volume']} |")
        a("")
    if len(moves_df):
        a("**Implausible move / split examples:**")
        a("")
        a("| Ticker | Date | Issue | Prev close | Close | Adj. return | Ratio Δ |")
        a("|---|---|---|---|---|---|---|")
        show = moves_df[moves_df["issue_type"].notna()].head(10)
        for _, r in show.iterrows():
            a(f"| {r['ticker']} | {r['date']} | {r['issue_type']} | {r['prev_close']:.2f} | {r['close']:.2f} | "
              f"{r['adj_return']:.1%} | {('%.1f%%' % (r['ratio_change']*100)) if pd.notna(r['ratio_change']) else 'n/a'} |")
        a("")
    a("## Overall data-health stats")
    a("")
    total_rows = int(ticker_stats["row_count"].sum())
    a(f"- Total rows scanned: {total_rows:,}")
    a(f"- Distinct tickers scanned: {n_tickers_scanned:,}")
    a(f"- Bad-bar rate (flagged rows / total rows): {len(bad_bars_all) / max(total_rows,1):.4%}")
    a(f"- Median trading days per ticker: {ticker_stats['distinct_date_count'].median():.0f}")
    a(f"- Tickers passing every clean-universe gate: {len(clean_universe):,} "
      f"({len(clean_universe)/max(n_tickers_scanned,1):.1%} of scanned universe)")
    a("")
    a("## Output files")
    a("")
    a("- `reports/validity/bad_bars.parquet` — bar-level flagged issues (invalid OHLC, "
      "implausible/unhandled-split moves, duplicates)")
    a("- `reports/validity/clean_universe.csv` — recommended whitelist (`ticker` column)")
    a("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)
    engine = get_engine()
    t0 = time.time()

    u_cte = universe_cte(args.limit)

    print("[1/6] Resolving ticker universe & global recent-date windows...")
    recent_active_dates = get_global_recent_dates(engine, args.recent_active_days)
    recent_liquidity_dates = get_global_recent_dates(engine, args.recent_liquidity_days)
    if not recent_active_dates:
        sys.exit("raw_bars appears to be empty.")
    global_max_date = max(recent_active_dates)
    recent_active_cutoff = min(recent_active_dates)
    print(f"    global max date = {global_max_date}, recent-active cutoff = {recent_active_cutoff}")

    print("[2/6] Scanning invalid bars (bad OHLC / null / negative volume)...")
    invalid_df = find_invalid_bars(engine, u_cte)
    print(f"    found {len(invalid_df):,} invalid bars")

    print("[3/6] Scanning implausible moves & split classification (window functions)...")
    moves_df = find_implausible_moves(engine, u_cte, args.move_threshold, args.move_threshold_extreme,
                                        args.split_ratio_change_threshold)
    print(f"    found {len(moves_df):,} flagged moves")

    print("[4/6] Scanning structural stats (counts, duplicates, gaps)...")
    struct_df = find_structural_stats(engine, u_cte, args.gap_days_threshold)
    dup_df = find_duplicate_bars(engine, u_cte) if struct_df["duplicate_row_count"].fillna(0).sum() > 0 else pd.DataFrame(
        columns=["ticker", "date", "issue_type"])
    struct_df["has_recent_bar"] = struct_df["last_date"] >= recent_active_cutoff
    print(f"    {len(struct_df):,} tickers, {int(struct_df['duplicate_row_count'].fillna(0).sum()):,} duplicate rows")

    print("[5/6] Scanning liquidity (recent avg $ volume, median price)...")
    liq_df = find_liquidity_stats(engine, u_cte, recent_liquidity_dates)

    print("[6/6] Building bad-bar percentages & clean universe...")
    bad_moves_for_count = moves_df.loc[moves_df["flag_move_50"] | moves_df["flag_unhandled_split"], ["ticker", "date"]] \
        if len(moves_df) else pd.DataFrame(columns=["ticker", "date"])
    # Count DISTINCT (ticker, date) pairs touched by any issue -- a duplicated date contributes
    # one "bad day" regardless of how many duplicate rows exist for it, and a bar that happens to
    # trip both an invalid-OHLC check and a move check isn't double-counted either.
    bad_dates = pd.concat([
        invalid_df[["ticker", "date"]] if len(invalid_df) else pd.DataFrame(columns=["ticker", "date"]),
        bad_moves_for_count,
        dup_df[["ticker", "date"]] if len(dup_df) else pd.DataFrame(columns=["ticker", "date"]),
    ], ignore_index=True).drop_duplicates()
    bad_per_ticker = bad_dates.groupby("ticker").size().rename("bad_bar_count")

    ticker_stats = struct_df.merge(liq_df, on="ticker", how="left").merge(
        bad_per_ticker, on="ticker", how="left")
    ticker_stats["bad_bar_count"] = ticker_stats["bad_bar_count"].fillna(0)
    ticker_stats["bad_bar_pct"] = ticker_stats["bad_bar_count"] / ticker_stats["distinct_date_count"].clip(lower=1)
    ticker_stats["recent_avg_dollar_volume"] = ticker_stats["recent_avg_dollar_volume"].fillna(0.0)
    ticker_stats["recent_median_price"] = ticker_stats["recent_median_price"].fillna(0.0)

    clean_mask = (
        (ticker_stats["recent_median_price"] >= args.min_price)
        & (ticker_stats["recent_avg_dollar_volume"] >= args.min_adv)
        & (ticker_stats["bad_bar_pct"] < args.max_bad_bar_pct)
        & (ticker_stats["distinct_date_count"] >= args.min_bars)
        & (ticker_stats["has_recent_bar"])
    )
    clean_universe = ticker_stats.loc[clean_mask, ["ticker"]].sort_values("ticker").reset_index(drop=True)

    # --- write bad_bars.parquet (explicit, documented schema) ---
    BAD_BARS_COLUMNS = ["ticker", "date", "issue_type", "open", "high", "low", "close",
                         "adjusted_close", "volume", "prev_close", "raw_return", "adj_return",
                         "ratio_change", "n_copies"]

    def _empty(cols):
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in cols})

    bad_bars_parts = []
    if len(invalid_df):
        part = invalid_df.copy()
        for c in ["prev_close", "raw_return", "adj_return", "ratio_change", "n_copies"]:
            part[c] = np.nan
        bad_bars_parts.append(part)
    if len(moves_df):
        flagged_moves = moves_df[moves_df["issue_type"].notna()].copy()
        for c in ["open", "high", "low", "volume", "n_copies"]:
            flagged_moves[c] = np.nan
        bad_bars_parts.append(flagged_moves)
    if len(dup_df):
        part = dup_df.copy()
        for c in ["prev_close", "raw_return", "adj_return", "ratio_change"]:
            part[c] = np.nan
        bad_bars_parts.append(part)
    if bad_bars_parts:
        bad_bars_out = pd.concat(bad_bars_parts, ignore_index=True, sort=False)[BAD_BARS_COLUMNS]
    else:
        bad_bars_out = _empty(BAD_BARS_COLUMNS)
    bad_bars_path = os.path.join(args.output_dir, "bad_bars.parquet")
    bad_bars_out.to_parquet(bad_bars_path, index=False)

    # --- write clean_universe.csv (dated audit copy) ---
    clean_path = os.path.join(args.output_dir, "clean_universe.csv")
    clean_universe.to_csv(clean_path, index=False)
    # --- promote to canonical via the GATED, atomic promote module (full runs only) ---
    if not args.limit and args.canonical_out:
        import subprocess
        promote = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promote_clean_universe.py")
        cmd = [sys.executable, promote, "--candidate", clean_path,
               "--canonical", args.canonical_out, "--scanned-tickers", str(len(ticker_stats))]
        print(f"  promoting via gated atomic swap: {' '.join(cmd[1:])}")
        rc = subprocess.run(cmd).returncode
        if rc != 0:
            print(f"  WARNING: gated promotion did NOT swap canonical (exit {rc}); "
                  f"candidate left at {clean_path}. Canonical unchanged.")

    # --- write markdown report ---
    report_path = os.path.join(args.output_dir, "DATA_QUALITY_AUDIT.md")
    write_markdown_report(
        report_path, args=args, n_tickers_scanned=len(ticker_stats),
        global_max_date=global_max_date, recent_active_cutoff=recent_active_cutoff,
        invalid_df=invalid_df, moves_df=moves_df, struct_df=ticker_stats, dup_df=dup_df,
        liq_df=liq_df, ticker_stats=ticker_stats, clean_universe=clean_universe,
        elapsed_s=time.time() - t0,
    )

    elapsed = time.time() - t0
    print()
    print("=" * 60)
    print(f"DONE in {elapsed:.1f}s")
    print(f"  Tickers scanned:        {len(ticker_stats):,}")
    print(f"  Invalid bars:           {len(invalid_df):,}")
    print(f"  Implausible moves (>50%): {moves_df['flag_move_50'].sum() if len(moves_df) else 0:,}")
    print(f"  ...of which >100%:      {moves_df['flag_move_100'].sum() if len(moves_df) else 0:,}")
    print(f"  Unhandled split/bad print: {moves_df['flag_unhandled_split'].sum() if len(moves_df) else 0:,}")
    print(f"  Handled splits (info):  {moves_df['flag_handled_split'].sum() if len(moves_df) else 0:,}")
    print(f"  Duplicate rows:         {len(dup_df):,}")
    print(f"  Short-history tickers:  {(ticker_stats['distinct_date_count'] < args.min_bars).sum():,}")
    print(f"  Likely-delisted:        {(~ticker_stats['has_recent_bar']).sum():,}")
    print(f"  Clean universe size:    {len(clean_universe):,} / {len(ticker_stats):,}")
    print(f"  Wrote: {report_path}")
    print(f"  Wrote: {bad_bars_path}")
    print(f"  Wrote: {clean_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
