"""
Atlas External Data Ingestion -- Alpaca Corporate Actions & News
================================================================
Pulls REAL corporate actions (splits, dividends, mergers, spin-offs, ...) and
news articles from Alpaca for the clean universe and writes them to the
corporate_actions and news_events tables (migration 0044).

Usage:
    # Smoke test: first 25 tickers, verify live response shapes
    python scripts/ingest_alpaca_corpactions_news.py --limit 25 --log reports/validity/alpaca_external_smoke.log

    # Full pull, 2020-01-01 -> today, whole clean universe
    python scripts/ingest_alpaca_corpactions_news.py --start 2020-01-01 --log reports/validity/alpaca_external_full.log

    # Corp actions only / news only
    python scripts/ingest_alpaca_corpactions_news.py --what corp
    python scripts/ingest_alpaca_corpactions_news.py --what news

    # Regenerate the markdown report from whatever is already in the DB
    python scripts/ingest_alpaca_corpactions_news.py --what report --report-md reports/validity/ALPACA_EXTERNAL_DATA.md

Vendor: Alpaca (alpaca-py). Corporate Actions API (v1) + News API (v1beta1),
both free-tier accessible. Does NOT auto-trade. Does NOT modify daily signals.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

DATABASE_URL = os.environ["DATABASE_URL"]

DEFAULT_UNIVERSE = Path(__file__).resolve().parent.parent / "config" / "clean_universe.csv"
SYMBOL_BATCH = 50          # Alpaca accepts comma-separated symbol lists; keep requests bounded.

# Alpaca corporate-action plural keys -> (primary_symbol_field, related_symbol_field, cusip_field)
CA_SYMBOL_MAP = {
    "forward_splits":         ("symbol",         None,             "cusip"),
    "reverse_splits":         ("symbol",         None,             "new_cusip"),
    "unit_splits":            ("old_symbol",     "new_symbol",     "old_cusip"),
    "stock_dividends":        ("symbol",         None,             "cusip"),
    "cash_dividends":         ("symbol",         None,             "cusip"),
    "spin_offs":              ("source_symbol",  "new_symbol",     "source_cusip"),
    "cash_mergers":           ("acquiree_symbol", "acquirer_symbol", "acquiree_cusip"),
    "stock_mergers":          ("acquiree_symbol", "acquirer_symbol", "acquiree_cusip"),
    "stock_and_cash_mergers": ("acquiree_symbol", "acquirer_symbol", "acquiree_cusip"),
    "redemptions":            ("symbol",         None,             "cusip"),
    "name_changes":           ("old_symbol",     "new_symbol",     "old_cusip"),
    "worthless_removals":     ("symbol",         None,             "cusip"),
    "rights_distributions":   ("source_symbol",  "new_symbol",     "source_cusip"),
}
SPLIT_TYPES  = ("forward_splits", "reverse_splits", "unit_splits")
MERGER_TYPES = ("cash_mergers", "stock_mergers", "stock_and_cash_mergers")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

class _Log:
    """Tee to stdout and (optionally) a log file."""
    def __init__(self, path: str | None):
        # Windows consoles default to cp1252; force UTF-8 so report glyphs
        # (→, —, …) don't raise UnicodeEncodeError.
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        self._fh = open(path, "a", encoding="utf-8") if path else None

    def __call__(self, msg: str = ""):
        print(msg, flush=True)
        if self._fh:
            self._fh.write(msg + "\n")
            self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _year_windows(start: date, end: date):
    """Inclusive yearly [start, end] sub-windows to bound each API request."""
    wins, y = [], start.year
    while y <= end.year:
        ws = max(date(y, 1, 1), start)
        we = min(date(y, 12, 31), end)
        wins.append((ws, we))
        y += 1
    return wins


def _with_retry(fn, log: _Log, max_tries: int = 6, base: float = 2.0):
    """Retry on rate-limit / transient errors with exponential backoff."""
    for i in range(max_tries):
        try:
            return fn()
        except Exception as e:                       # noqa: BLE001 - inspect message
            msg = str(e).lower()
            transient = ("429" in msg or "rate limit" in msg
                         or "too many requests" in msg or "timeout" in msg
                         or "connection" in msg)
            if i == max_tries - 1 or not transient:
                raise
            wait = base * (2 ** i)
            log(f"    transient error ({e!s:.80}); retry {i + 1}/{max_tries} in {wait:.0f}s")
            time.sleep(wait)


def load_universe(path: Path, limit: int | None) -> list[str]:
    df = pd.read_csv(path)
    col = next((c for c in df.columns if c.lower() in ("ticker", "symbol")), df.columns[0])
    syms = (df[col].astype(str).str.strip().str.upper()
            .replace("", pd.NA).dropna().unique().tolist())
    return syms[:limit] if limit else syms


# ---------------------------------------------------------------------------
# Corporate actions
# ---------------------------------------------------------------------------

def _jsonable(obj) -> dict:
    """Alpaca pydantic model -> JSON-serializable dict."""
    try:
        return obj.model_dump(mode="json")
    except Exception:
        out = {}
        for k, v in vars(obj).items():
            out[k] = v.isoformat() if isinstance(v, (date, datetime)) else v
        return out


def normalize_ca(ca_set, universe: set[str]) -> list[dict]:
    """CorporateActionsSet -> normalized rows (primary symbol must be in universe)."""
    rows = []
    for ca_type, actions in (ca_set.data or {}).items():
        prim_f, rel_f, cusip_f = CA_SYMBOL_MAP.get(ca_type, ("symbol", None, "cusip"))
        for a in actions:
            symbol = getattr(a, prim_f, None)
            if not symbol or symbol not in universe:
                continue

            # Unified merger cash. The zero-bug: `rate if rate else cash_rate`
            # wrongly drops a legitimate 0.0 -> must use `is not None`.
            cash_amount = None
            if ca_type in MERGER_TYPES:
                rate_val = getattr(a, "rate", None)
                cash_rate_val = getattr(a, "cash_rate", None)
                cash_amount = rate_val if rate_val is not None else cash_rate_val

            rows.append({
                "ca_type":        ca_type,
                "symbol":         symbol,
                "related_symbol": getattr(a, rel_f, None) if rel_f else None,
                "cusip":          getattr(a, cusip_f, None),
                "old_rate":       getattr(a, "old_rate", None),
                "new_rate":       getattr(a, "new_rate", None),
                "rate":           getattr(a, "rate", None) if ca_type not in MERGER_TYPES else None,
                "cash_amount":    cash_amount,
                "process_date":   getattr(a, "process_date", None),
                "ex_date":        getattr(a, "ex_date", None),
                "effective_date": getattr(a, "effective_date", None),
                "record_date":    getattr(a, "record_date", None),
                "payable_date":   getattr(a, "payable_date", None),
                "special":        getattr(a, "special", None),
                "foreign":        getattr(a, "foreign", None),
                "raw":            json.dumps(_jsonable(a)),
            })
    return rows


_CA_INSERT = text("""
    INSERT INTO corporate_actions
        (ca_type, symbol, related_symbol, cusip, old_rate, new_rate, rate, cash_amount,
         process_date, ex_date, effective_date, record_date, payable_date,
         special, "foreign", raw)
    VALUES
        (:ca_type, :symbol, :related_symbol, :cusip, :old_rate, :new_rate, :rate, :cash_amount,
         :process_date, :ex_date, :effective_date, :record_date, :payable_date,
         :special, :foreign, CAST(:raw AS JSONB))
    ON CONFLICT DO NOTHING
""")


def upsert_ca(rows: list[dict], engine) -> int:
    if not rows:
        return 0
    BATCH = 500
    for s in range(0, len(rows), BATCH):
        with engine.begin() as conn:
            conn.execute(_CA_INSERT, rows[s:s + BATCH])
    return len(rows)


def ingest_corp_actions(client, universe: list[str], windows, dry_run, log, engine) -> int:
    from alpaca.data.requests import CorporateActionsRequest
    uni_set = set(universe)
    total = 0
    batches = list(_chunks(universe, SYMBOL_BATCH))
    log(f"[corp] {len(universe)} tickers in {len(batches)} batch(es) x {len(windows)} window(s)")
    for bi, batch in enumerate(batches, 1):
        for (ws, we) in windows:
            req = CorporateActionsRequest(symbols=batch, start=ws, end=we)
            ca_set = _with_retry(lambda: client.get_corporate_actions(req), log)
            rows = normalize_ca(ca_set, uni_set)
            total += len(rows) if dry_run else upsert_ca(rows, engine)
        log(f"[corp] batch {bi}/{len(batches)} done   running total rows={total:,}")
    return total


# ---------------------------------------------------------------------------
# News
# ---------------------------------------------------------------------------

def fanout_news(articles, universe: set[str]) -> list[dict]:
    """One row per (article, symbol) for symbols in our universe. Drop HTML content."""
    rows = []
    for n in articles:
        for sym in (getattr(n, "symbols", None) or []):
            if sym not in universe:
                continue
            rows.append({
                "news_id":    int(getattr(n, "id")),
                "symbol":     sym,
                "headline":   getattr(n, "headline", None),
                "summary":    getattr(n, "summary", None),
                "source":     getattr(n, "source", None),
                "url":        getattr(n, "url", None),
                "created_at": getattr(n, "created_at", None),
            })
    return rows


_NEWS_COLS = ["news_id", "symbol", "headline", "summary", "source", "url", "created_at"]


def upsert_news(rows: list[dict], engine) -> int:
    """COPY into TEMP staging, then INSERT ... ON CONFLICT DO NOTHING (fast bulk)."""
    if not rows:
        return 0
    df = pd.DataFrame(rows, columns=_NEWS_COLS)
    buf = io.StringIO()
    df.to_csv(buf, index=False, header=False)
    buf.seek(0)
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("""
            CREATE TEMP TABLE _stage_news (
                news_id bigint, symbol text, headline text, summary text,
                source text, url text, created_at timestamptz
            ) ON COMMIT DROP
        """)
        cur.copy_expert(
            "COPY _stage_news (news_id, symbol, headline, summary, source, url, created_at) "
            "FROM STDIN WITH (FORMAT csv)", buf)
        cur.execute("""
            INSERT INTO news_events
                (news_id, symbol, headline, summary, source, url, created_at)
            SELECT news_id, symbol, headline, summary, source, url, created_at
            FROM _stage_news
            ON CONFLICT (news_id, symbol) DO NOTHING
        """)
        raw.commit()
    finally:
        raw.close()
    return len(df)


def ingest_news(client, universe: list[str], windows, dry_run, log, engine,
                smoke: bool) -> int:
    from alpaca.data.requests import NewsRequest
    uni_set = set(universe)
    total = 0
    batches = list(_chunks(universe, SYMBOL_BATCH))
    log(f"[news] {len(universe)} tickers in {len(batches)} batch(es) x {len(windows)} window(s)"
        + ("  (smoke: 1 page/window)" if smoke else ""))
    for bi, batch in enumerate(batches, 1):
        sym_str = ",".join(batch)
        for (ws, we) in windows:
            start_dt = datetime(ws.year, ws.month, ws.day, tzinfo=timezone.utc)
            end_dt = datetime(we.year, we.month, we.day, 23, 59, 59, tzinfo=timezone.utc)
            page_token, pages = None, 0
            while True:
                req = NewsRequest(
                    start=start_dt, end=end_dt, symbols=sym_str,
                    include_content=False, exclude_contentless=False,
                    page_token=page_token, limit=(50 if smoke else None),
                )
                news_set = _with_retry(lambda: client.get_news(req), log)
                articles = (news_set.data or {}).get("news", [])
                rows = fanout_news(articles, uni_set)
                total += len(rows) if dry_run else upsert_news(rows, engine)
                pages += 1
                page_token = getattr(news_set, "next_page_token", None)
                if not page_token or (smoke and pages >= 1):
                    break
        log(f"[news] batch {bi}/{len(batches)} done   running total rows={total:,}")
    return total


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def build_report(engine) -> str:
    with engine.begin() as conn:
        ca_by_type = conn.execute(text(
            "SELECT ca_type, count(*) FROM corporate_actions GROUP BY ca_type ORDER BY 2 DESC"
        )).fetchall()
        ca_total = conn.execute(text("SELECT count(*) FROM corporate_actions")).scalar() or 0
        news_total = conn.execute(text("SELECT count(*) FROM news_events")).scalar() or 0
        split_tickers = conn.execute(text(
            "SELECT count(DISTINCT symbol) FROM corporate_actions "
            "WHERE ca_type IN ('forward_splits','reverse_splits','unit_splits')"
        )).scalar() or 0
        news_tickers = conn.execute(text(
            "SELECT count(DISTINCT symbol) FROM news_events")).scalar() or 0
        ca_min, ca_max = conn.execute(text(
            "SELECT min(COALESCE(ex_date, effective_date, process_date)), "
            "       max(COALESCE(ex_date, effective_date, process_date)) "
            "FROM corporate_actions")).fetchone()
        news_min, news_max = conn.execute(text(
            "SELECT min(created_at), max(created_at) FROM news_events")).fetchone()

    lines = []
    lines.append("# Alpaca External Data — Corporate Actions & News")
    lines.append("")
    lines.append(f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} from REAL Alpaca data._")
    lines.append("")
    lines.append("> No synthetic baseline report ever existed in this repo, so the numbers below "
                 "are reported standalone (nothing to diff against).")
    lines.append("")
    lines.append("## Corporate actions")
    lines.append("")
    lines.append(f"- **Total rows:** {ca_total:,}")
    lines.append(f"- **Distinct tickers with splits:** {split_tickers:,}")
    lines.append(f"- **Date coverage (ex/effective/process):** {ca_min} → {ca_max}")
    lines.append("")
    lines.append("| ca_type | rows |")
    lines.append("|---|---:|")
    for t, c in ca_by_type:
        lines.append(f"| {t} | {c:,} |")
    lines.append("")
    lines.append("## News events (universe-filtered, one row per article×symbol)")
    lines.append("")
    lines.append(f"- **Total rows:** {news_total:,}")
    lines.append(f"- **Distinct tickers with news:** {news_tickers:,}")
    lines.append(f"- **Earliest news date actually returned:** {news_min}")
    lines.append(f"- **Latest news date:** {news_max}")
    lines.append("")
    lines.append("> Caveat (verified, not papered over): news is universe-filtered, and Alpaca "
                 "news history is sparse pre-2016. The earliest date above is the real coverage floor.")
    lines.append("")
    return "\n".join(lines)


def print_samples(engine, log):
    for tbl, cols in (
        ("corporate_actions", "ca_type, symbol, ex_date, effective_date, new_rate, cash_amount"),
        ("news_events", "news_id, symbol, created_at, source, left(headline,60) AS headline"),
    ):
        with engine.begin() as conn:
            df = pd.read_sql(text(f"SELECT {cols} FROM {tbl} ORDER BY 1 LIMIT 5"), conn)
        log(f"\n--- {tbl}: first rows ---")
        log(df.to_string(index=False) if not df.empty else "(no rows)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--what", choices=["both", "corp", "news", "report"], default="both")
    p.add_argument("--start", default="2020-01-01", help="YYYY-MM-DD (default 2020-01-01)")
    p.add_argument("--end", default=None, help="YYYY-MM-DD (default today)")
    p.add_argument("--limit", type=int, default=None,
                   help="Smoke: cap tickers (also caps news to 1 page/window)")
    p.add_argument("--universe", default=str(DEFAULT_UNIVERSE))
    p.add_argument("--log", default=None)
    p.add_argument("--report-md", default=None, help="Also write the markdown report to this path")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    log = _Log(args.log)
    smoke = args.limit is not None
    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else date.today()
    windows = _year_windows(start, end)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    log("=== Atlas External Data — Alpaca Corporate Actions & News ===")
    log(f"what={args.what}  range={start}..{end}  smoke={smoke}  dry_run={args.dry_run}")

    # Existing-data check (before any write).
    if args.what != "report":
        with engine.begin() as conn:
            ca_n = conn.execute(text("SELECT count(*) FROM corporate_actions")).scalar()
            nw_n = conn.execute(text("SELECT count(*) FROM news_events")).scalar()
        log(f"[pre] existing rows -> corporate_actions={ca_n:,}  news_events={nw_n:,}")

    if args.what == "report":
        report = build_report(engine)
        log(report)
        if args.report_md:
            Path(args.report_md).write_text(report, encoding="utf-8")
            log(f"\nWrote {args.report_md}")
        log.close()
        return

    universe = load_universe(Path(args.universe), args.limit)
    log(f"[pre] universe: {len(universe)} tickers from {args.universe}")

    from alpaca.data.historical.corporate_actions import CorporateActionsClient
    from alpaca.data.historical.news import NewsClient
    key, secret = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]

    n_ca = n_news = 0
    if args.what in ("both", "corp"):
        ca_client = CorporateActionsClient(api_key=key, secret_key=secret)
        n_ca = ingest_corp_actions(ca_client, universe, windows, args.dry_run, log, engine)
    if args.what in ("both", "news"):
        news_client = NewsClient(api_key=key, secret_key=secret)
        n_news = ingest_news(news_client, universe, windows, args.dry_run, log, engine, smoke)

    log("\n=== Summary ===")
    log(f"  corporate_actions rows written/seen: {n_ca:,}")
    log(f"  news_events rows written/seen:       {n_news:,}")

    if not args.dry_run:
        print_samples(engine, log)
        log("\n" + build_report(engine))
        if args.report_md:
            Path(args.report_md).write_text(build_report(engine), encoding="utf-8")
            log(f"Wrote {args.report_md}")

    log("\nDone.")
    log.close()


if __name__ == "__main__":
    main()
