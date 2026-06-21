"""
fetch_ipo_universe.py
---------------------
1. Scrapes Nasdaq IPO calendar API for every month 2019-01 → 2026-06,
   collecting ticker, company, ipo_date, ipo_price, exchange, underwriter.
2. Falls back to StockAnalysis.com HTML scrape for any year where Nasdaq
   API returns fewer than 5 IPOs.
3. Checks which tickers already have bars in raw_bars.
4. Downloads historical OHLCV via yfinance for any missing ticker.
5. Inserts bars into raw_bars (ON CONFLICT DO NOTHING — never overwrites).
6. Reports: total scraped, downloaded, inserted.

After this completes, run:
  python scripts/build_ipo_registry.py
  python scripts/compute_ipo_performance.py
  python scripts/ipo_analysis_report.py
"""

import os, sys, time, re, json
from datetime import date, timedelta
from collections import defaultdict

import psycopg2
import requests
import yfinance as yf
import pandas as pd
from dotenv import load_dotenv

load_dotenv(override=True)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")

# ── Configuration ─────────────────────────────────────────────────────────────

START = (2019, 1)
END   = (2026, 6)   # inclusive

BATCH_SIZE   = 50   # tickers per yfinance download call
BATCH_PAUSE  = 2    # seconds between batches
NASDAQ_PAUSE = 0.5  # seconds between Nasdaq API calls

NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nasdaq.com/market-activity/ipos",
    "Origin":          "https://www.nasdaq.com",
}

# Tickers to always skip (ETFs, indices, warrants, units, rights)
ALWAYS_EXCLUDE = {
    "SPY","QQQ","IWM","DIA","GLD","SLV","TLT","LQD","HYG",
    "UUP","GDX","XLB","XLC","XLE","XLF","XLI","XLK","XLP",
    "XLU","XLV","XLY","XLRE","XRT","IYR","ARKK","BRK-B",
    "^VIX","^TNX","^SPX","^DJI","^GSPC","^IXIC",
}

# Company name substrings that indicate SPAC shells (no real operations)
SPAC_NAME_HINTS = [
    "blank check", "acquisition corp", "acquisition company",
    "acquisition holdings", "special purpose acquisition",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_price(val):
    if val is None:
        return None
    try:
        s = str(val).replace("$", "").replace(",", "").strip()
        if "-" in s:
            parts = [p.strip() for p in s.split("-") if p.strip()]
            if len(parts) == 2:
                return (float(parts[0]) + float(parts[1])) / 2
        return float(s) if s else None
    except Exception:
        return None


def _parse_int(val):
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except Exception:
        return None


def _is_spac_or_junk(ticker: str, company: str) -> bool:
    t = ticker.upper()
    # Warrants / units / rights have these suffixes on Nasdaq
    if re.search(r'[WUR]$', t) and len(t) > 3:
        return True
    if "-W" in t or "-U" in t or ".WS" in t or ".WT" in t:
        return True
    # Blank-check company by name
    c = (company or "").lower()
    if any(hint in c for hint in SPAC_NAME_HINTS):
        return True
    return False


def month_iter(start_ym, end_ym):
    """Yield (year, month) tuples from start to end inclusive."""
    y, m = start_ym
    ey, em = end_ym
    while (y, m) <= (ey, em):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# ── Step 1: Nasdaq API scrape ─────────────────────────────────────────────────

def scrape_nasdaq_month(year: int, month: int) -> dict:
    """Returns dict of { ticker: { company, ipo_date, ipo_price, exchange, shares, underwriter } }."""
    month_str = "%04d-%02d" % (year, month)
    url = "https://api.nasdaq.com/api/ipo/calendar?date=" + month_str
    try:
        resp = requests.get(url, headers=NASDAQ_HEADERS, timeout=15)
        if resp.status_code != 200:
            print("    NASDAQ %s → HTTP %d" % (month_str, resp.status_code))
            return {}
        data = resp.json().get("data") or {}
        result = {}
        for section in ["priced", "upcoming"]:
            rows = (data.get(section) or {}).get("rows") or []
            for row in rows:
                sym = (row.get("proposedTickerSymbol") or "").strip().upper()
                if not sym or len(sym) > 8:
                    continue
                company = (row.get("companyName") or "").strip()
                if _is_spac_or_junk(sym, company) or sym in ALWAYS_EXCLUDE:
                    continue
                # Parse IPO date from the row (format: "01/15/2024" or "2024-01-15")
                raw_date = row.get("proposedDate") or row.get("ipoDate") or ""
                ipo_date_parsed = None
                for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
                    try:
                        ipo_date_parsed = date.fromisoformat(
                            __import__("datetime").datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                        )
                        break
                    except Exception:
                        pass
                if ipo_date_parsed is None:
                    # fallback: use first day of the month
                    ipo_date_parsed = date(year, month, 1)

                result[sym] = {
                    "company_name":   company,
                    "ipo_date":       ipo_date_parsed,
                    "ipo_price":      _parse_price(row.get("proposedSharePrice")),
                    "exchange":       (row.get("exchange") or "").strip(),
                    "shares_offered": _parse_int(row.get("sharesOffered")),
                    "underwriter":    (row.get("leadUnderwriters") or "").strip(),
                }
        return result
    except Exception as e:
        print("    NASDAQ %s → exception: %s" % (month_str, e))
        return {}


def scrape_stockanalysis_year(year: int) -> dict:
    """
    Fallback: scrape StockAnalysis.com IPO list for a given year.
    Returns same dict format as scrape_nasdaq_month.
    """
    url = "https://stockanalysis.com/ipos/%d/" % year
    try:
        # StockAnalysis renders via JS, but the raw data is embedded in a <script> tag
        resp = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }, timeout=20)
        if resp.status_code != 200:
            print("    StockAnalysis %d → HTTP %d" % (year, resp.status_code))
            return {}

        # Try to find JSON data embedded in the page
        text = resp.text
        # Look for: window.__NEXT_DATA__ = {...} or similar embedded JSON
        match = re.search(r'__NEXT_DATA__\s*=\s*(\{.+?\})\s*;?\s*</script>', text, re.DOTALL)
        if not match:
            print("    StockAnalysis %d → could not find embedded data" % year)
            return {}

        page_data = json.loads(match.group(1))
        # Navigate to the IPO table data
        ipos_raw = None
        try:
            ipos_raw = page_data["props"]["pageProps"]["tableData"]
        except (KeyError, TypeError):
            pass
        if not ipos_raw:
            print("    StockAnalysis %d → no tableData in embedded JSON" % year)
            return {}

        result = {}
        for row in ipos_raw:
            sym = (row.get("symbol") or row.get("ticker") or "").strip().upper()
            if not sym:
                continue
            company = (row.get("name") or row.get("company") or "").strip()
            if _is_spac_or_junk(sym, company) or sym in ALWAYS_EXCLUDE:
                continue
            raw_date = row.get("ipoDate") or row.get("date") or ""
            ipo_date_parsed = None
            try:
                ipo_date_parsed = date.fromisoformat(raw_date[:10])
            except Exception:
                ipo_date_parsed = date(year, 1, 1)

            result[sym] = {
                "company_name":   company,
                "ipo_date":       ipo_date_parsed,
                "ipo_price":      _parse_price(row.get("ipoPrice") or row.get("price")),
                "exchange":       (row.get("exchange") or "").strip(),
                "shares_offered": None,
                "underwriter":    "",
            }
        return result
    except Exception as e:
        print("    StockAnalysis %d → exception: %s" % (year, e))
        return {}


def scrape_all_ipos() -> dict:
    """
    Returns { ticker: { company_name, ipo_date, ipo_price, exchange, shares_offered, underwriter } }
    for all IPOs 2019-2026.
    """
    all_ipos = {}
    per_year_nasdaq = defaultdict(int)  # year → count from Nasdaq

    print("Scraping Nasdaq IPO calendar API...")
    for year, month in month_iter(START, END):
        month_str = "%04d-%02d" % (year, month)
        result = scrape_nasdaq_month(year, month)
        for ticker, meta in result.items():
            if ticker not in all_ipos:
                all_ipos[ticker] = meta
        per_year_nasdaq[year] += len(result)
        print("  %s: %d IPOs (running total: %d)" % (month_str, len(result), len(all_ipos)))
        time.sleep(NASDAQ_PAUSE)

    # Fallback: for years where Nasdaq returned < 5 IPOs total, try StockAnalysis
    for year in range(START[0], END[0] + 1):
        if per_year_nasdaq[year] < 5:
            print("  Nasdaq returned %d for %d — trying StockAnalysis fallback..." % (
                per_year_nasdaq[year], year))
            sa_result = scrape_stockanalysis_year(year)
            added = 0
            for ticker, meta in sa_result.items():
                if ticker not in all_ipos:
                    all_ipos[ticker] = meta
                    added += 1
            print("    StockAnalysis %d: added %d new IPOs" % (year, added))
            time.sleep(1)

    return all_ipos


# ── Step 2: Check existing raw_bars coverage ──────────────────────────────────

def get_covered_tickers(conn) -> set:
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT ticker FROM raw_bars")
    result = {r[0] for r in cur.fetchall()}
    cur.close()
    return result


# ── Step 3: Download + insert bars ───────────────────────────────────────────

def download_and_insert(missing_tickers: list, ipos: dict, conn):
    """
    Downloads yfinance OHLCV for each ticker in missing_tickers (batched),
    inserts into raw_bars. Returns (downloaded, inserted) counts.
    """
    if not missing_tickers:
        return 0, 0

    # Use the earliest IPO date in the batch as the download start
    global_start = "2018-12-01"  # slight buffer before 2019-01
    global_end   = str(date.today() + timedelta(days=1))

    downloaded = 0
    inserted   = 0

    total_batches = (len(missing_tickers) + BATCH_SIZE - 1) // BATCH_SIZE
    for batch_idx in range(total_batches):
        batch = missing_tickers[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        print("  Batch %d/%d: downloading %d tickers (%s … %s)" % (
            batch_idx + 1, total_batches, len(batch), batch[0], batch[-1]))

        try:
            raw = yf.download(
                batch,
                start=global_start,
                end=global_end,
                auto_adjust=False,
                progress=False,
                threads=True,
                timeout=30,
            )
        except Exception as e:
            print("    yfinance download failed: %s — skipping batch" % e)
            time.sleep(BATCH_PAUSE)
            continue

        if raw is None or raw.empty:
            print("    empty result for batch")
            time.sleep(BATCH_PAUSE)
            continue

        # Multi-ticker download returns multi-level columns; single ticker is flat
        if len(batch) == 1:
            ticker = batch[0]
            df_ticker = raw.copy()
            _insert_ticker_bars(ticker, df_ticker, conn)
            inserted += len(df_ticker)
            downloaded += 1
        else:
            # Columns are (field, ticker) multi-index
            for ticker in batch:
                try:
                    # Extract single ticker's data
                    cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
                    available = [c for c in cols if (c, ticker) in raw.columns]
                    if not available:
                        # Sometimes yfinance lowercases field names
                        alt = [c for c in ["open","high","low","close","adjclose","volume"]
                               if (c, ticker) in raw.columns]
                        if not alt:
                            continue
                        available = alt
                    df_ticker = raw[[(c, ticker) for c in available]].copy()
                    df_ticker.columns = available
                    df_ticker = df_ticker.dropna(subset=["Close"] if "Close" in available else ["close"])
                    if df_ticker.empty:
                        continue
                    n = _insert_ticker_bars(ticker, df_ticker, conn)
                    if n > 0:
                        inserted += n
                        downloaded += 1
                except Exception as e:
                    print("    %s extract failed: %s" % (ticker, e))

        print("    → batch complete, downloaded=%d so far" % downloaded)
        time.sleep(BATCH_PAUSE)

    return downloaded, inserted


def _insert_ticker_bars(ticker: str, df: pd.DataFrame, conn) -> int:
    """
    Insert OHLCV rows for ticker into raw_bars.
    Returns number of rows inserted.
    """
    # Normalise column names
    df.columns = [c.lower().replace(" ", "_").replace("adj_close", "adjusted_close")
                  for c in df.columns]
    required = {"close"}
    if not required.issubset(set(df.columns)):
        return 0

    if "adjusted_close" not in df.columns and "adj_close" in df.columns:
        df = df.rename(columns={"adj_close": "adjusted_close"})

    rows = []
    for dt, row in df.iterrows():
        close_val = row.get("close")
        if close_val is None or (hasattr(close_val, '__float__') and pd.isna(close_val)):
            continue
        bar_date = dt.date() if hasattr(dt, "date") else dt

        def fv(col):
            v = row.get(col)
            if v is None:
                return None
            try:
                f = float(v)
                return None if pd.isna(f) else f
            except Exception:
                return None

        def iv(col):
            v = row.get(col)
            if v is None:
                return None
            try:
                f = float(v)
                return None if pd.isna(f) else int(f)
            except Exception:
                return None

        rows.append((
            ticker,
            bar_date,
            fv("open"),
            fv("high"),
            fv("low"),
            float(close_val),
            fv("adjusted_close"),
            iv("volume"),
            "fetch_ipo_universe",
        ))

    if not rows:
        return 0

    cur = conn.cursor()
    try:
        cur.executemany("""
            INSERT INTO raw_bars (ticker, date, open, high, low, close, adjusted_close, volume, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (ticker, date) DO NOTHING
        """, rows)
        conn.commit()
        return cur.rowcount
    except Exception as e:
        print("    DB insert failed for %s: %s" % (ticker, e))
        conn.rollback()
        return 0
    finally:
        cur.close()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  FETCH IPO UNIVERSE  (2019-2026)")
    print("=" * 70)

    conn = psycopg2.connect(DB_URL)

    # ── Phase 1: Scrape IPO calendar ─────────────────────────────────────────
    print("\nPhase 1: Scraping IPO calendars...")
    ipos = scrape_all_ipos()
    print("\nTotal unique IPOs scraped: %d" % len(ipos))

    # Breakdown by year
    by_year = defaultdict(int)
    for meta in ipos.values():
        by_year[meta["ipo_date"].year] += 1
    for yr in sorted(by_year):
        print("  %d: %d IPOs" % (yr, by_year[yr]))

    # ── Phase 2: Check coverage ───────────────────────────────────────────────
    print("\nPhase 2: Checking raw_bars coverage...")
    covered = get_covered_tickers(conn)
    missing = [t for t in sorted(ipos.keys()) if t not in covered]
    already_have = len(ipos) - len(missing)
    print("  Already in raw_bars: %d" % already_have)
    print("  Need to download:    %d" % len(missing))

    # ── Phase 3: Download bars ────────────────────────────────────────────────
    print("\nPhase 3: Downloading bars via yfinance...")
    print("  Batches of %d, %ds pause between batches" % (BATCH_SIZE, BATCH_PAUSE))
    downloaded, inserted = download_and_insert(missing, ipos, conn)

    # ── Phase 4: Report ───────────────────────────────────────────────────────
    conn.close()

    print("\n" + "=" * 70)
    print("  FETCH COMPLETE")
    print("  IPOs scraped:      %d" % len(ipos))
    print("  Already in DB:     %d" % already_have)
    print("  Tickers downloaded: %d" % downloaded)
    print("  Bars inserted:     %d" % inserted)
    print()
    print("  Next steps:")
    print("    python scripts/build_ipo_registry.py")
    print("    python scripts/compute_ipo_performance.py")
    print("    python scripts/ipo_analysis_report.py")
    print("=" * 70)


if __name__ == "__main__":
    main()
