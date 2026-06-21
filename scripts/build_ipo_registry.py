"""
build_ipo_registry.py
---------------------
Populates ipo_registry from raw_bars first-appearance dates.
"""

import os, sys, json, time
import psycopg2
import requests
from datetime import date, datetime
from dotenv import load_dotenv

load_dotenv(override=True)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")

EXCLUDE_TICKERS = {
    "^VIX", "^TNX", "^SPX", "^DJI", "^GSPC", "^IXIC",
    "SPY", "QQQ", "IWM", "DIA", "GLD", "SLV", "TLT", "LQD", "HYG",
    "UUP", "GDX", "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP",
    "XLU", "XLV", "XLY", "XLRE", "XRT", "IYR", "ARKK", "BRK-B",
}

KNOWN_META = {
    "PYPL": {"company_name": "PayPal Holdings", "sector": "Technology",
              "industry": "Software-Infrastructure", "exchange": "NASDAQ",
              "ipo_price": 36.00, "underwriter": "Deutsche Bank / Goldman Sachs"},
    "MRNA": {"company_name": "Moderna Inc.", "sector": "Healthcare",
              "industry": "Biotechnology", "exchange": "NASDAQ",
              "ipo_price": 23.00, "underwriter": "Morgan Stanley / Goldman Sachs"},
    "VICI": {"company_name": "VICI Properties", "sector": "Real Estate",
              "industry": "REIT-Diversified", "exchange": "NYSE",
              "ipo_price": 20.00, "underwriter": "Goldman Sachs / Citigroup"},
    "IR":   {"company_name": "Ingersoll Rand Inc.", "sector": "Industrials",
              "industry": "Specialty Industrial Machinery", "exchange": "NYSE",
              "ipo_price": None, "underwriter": "Goldman Sachs"},
    "CTVA": {"company_name": "Corteva Inc.", "sector": "Basic Materials",
              "industry": "Agricultural Inputs", "exchange": "NYSE",
              "ipo_price": 26.00, "underwriter": "Barclays / Goldman Sachs"},
    "CARR": {"company_name": "Carrier Global Corp.", "sector": "Industrials",
              "industry": "Building Products & Equipment", "exchange": "NYSE",
              "ipo_price": None, "underwriter": "Goldman Sachs / JP Morgan"},
    "OTIS": {"company_name": "Otis Worldwide Corp.", "sector": "Industrials",
              "industry": "Specialty Industrial Machinery", "exchange": "NYSE",
              "ipo_price": None, "underwriter": "Goldman Sachs / JP Morgan"},
    "GEHC": {"company_name": "GE HealthCare Technologies", "sector": "Healthcare",
              "industry": "Health Information Services", "exchange": "NASDAQ",
              "ipo_price": 60.00, "underwriter": "Goldman Sachs / JP Morgan"},
    "XLC":  {"company_name": "Communication Services Select Sector SPDR ETF",
              "sector": "ETF", "industry": "Communication Services", "exchange": "NYSE",
              "ipo_price": None, "underwriter": None},
    "XLRE": {"company_name": "Real Estate Select Sector SPDR ETF",
              "sector": "ETF", "industry": "Real Estate", "exchange": "NYSE",
              "ipo_price": None, "underwriter": None},
}

NASDAQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nasdaq.com/market-activity/ipos",
}


def try_nasdaq_ipo_api(ipo_date):
    month_str = ipo_date.strftime("%Y-%m")
    url = "https://api.nasdaq.com/api/ipo/calendar?date=" + month_str
    try:
        resp = requests.get(url, headers=NASDAQ_HEADERS, timeout=10)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        result = {}
        rows_data = data.get("data") or {}
        for section in ["priced", "upcoming"]:
            section_data = rows_data.get(section) or {}
            rows_list = section_data.get("rows") or []
            for row in rows_list:
                sym = (row.get("proposedTickerSymbol") or "").strip().upper()
                if not sym:
                    continue
                result[sym] = {
                    "company_name":   row.get("companyName", ""),
                    "exchange":       row.get("exchange", ""),
                    "ipo_price":      _parse_price(row.get("proposedSharePrice")),
                    "shares_offered": _parse_int(row.get("sharesOffered")),
                    "underwriter":    row.get("leadUnderwriters", ""),
                }
        return result
    except Exception as e:
        print("  Nasdaq API failed for " + month_str + ": " + str(e))
        return {}


def _parse_price(val):
    if val is None:
        return None
    try:
        s = str(val).replace("$", "").replace(",", "").strip()
        if "-" in s:
            parts = s.split("-")
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


def classify_day1(pop_pct):
    if pop_pct is None:
        return "unknown"
    if pop_pct >= 20:
        return "hot"
    if pop_pct >= 5:
        return "warm"
    if pop_pct >= 0:
        return "cold"
    return "broken"


def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True   # each row committed independently; one failure doesn't abort all
    cur  = conn.cursor()

    cur.execute("""
        SELECT ticker, MIN(date) AS first_date
        FROM raw_bars
        GROUP BY ticker
        HAVING MIN(date) >= '2015-01-01' AND MIN(date) <= CURRENT_DATE
        ORDER BY MIN(date)
    """)
    candidates = [{"ticker": r[0], "first_date": r[1]} for r in cur.fetchall()]
    candidates = [c for c in candidates
                  if c["ticker"] not in EXCLUDE_TICKERS
                  and not c["ticker"].startswith("^")]

    print("IPO candidates from raw_bars: " + str(len(candidates)))
    for c in candidates:
        print("  " + c["ticker"].ljust(8) + "  first_bar=" + str(c["first_date"]))
    print()

    nasdaq_cache = {}
    upserted = 0

    for c in candidates:
        ticker     = c["ticker"]
        first_date = c["first_date"]

        cur.execute("""
            SELECT open, high, low, close, volume
            FROM raw_bars
            WHERE ticker = %s AND date = %s
        """, (ticker, first_date))
        row = cur.fetchone()
        if not row:
            print("  " + ticker + ": no day1 bar, skipping")
            continue

        d1_open  = float(row[0]) if row[0] is not None else None
        d1_high  = float(row[1]) if row[1] is not None else None
        d1_low   = float(row[2]) if row[2] is not None else None
        d1_close = float(row[3]) if row[3] is not None else None
        d1_vol   = int(row[4])   if row[4] is not None else None

        month_key = first_date.strftime("%Y-%m")
        if month_key not in nasdaq_cache:
            print("  Fetching Nasdaq IPO calendar " + month_key + "...")
            nasdaq_cache[month_key] = try_nasdaq_ipo_api(first_date)
            time.sleep(0.4)
        api_data = nasdaq_cache[month_key].get(ticker, {})

        meta = KNOWN_META.get(ticker, {})

        company_name  = api_data.get("company_name") or meta.get("company_name") or ""
        exchange_v    = api_data.get("exchange")     or meta.get("exchange")     or ""
        shares_off    = api_data.get("shares_offered")
        underwriter   = api_data.get("underwriter")  or meta.get("underwriter")
        sector        = meta.get("sector", "")
        industry      = meta.get("industry", "")

        ipo_price_raw = api_data.get("ipo_price") or meta.get("ipo_price")
        ipo_price     = float(ipo_price_raw) if ipo_price_raw else d1_open

        if ipo_price and ipo_price > 0 and d1_close:
            pop_pct = (d1_close - ipo_price) / ipo_price * 100
        elif d1_open and d1_open > 0 and d1_close:
            pop_pct = (d1_close - d1_open) / d1_open * 100
        else:
            pop_pct = None

        # Clamp extreme pop values (penny stocks, bad data) to NUMERIC(8,4) range
        if pop_pct is not None and abs(pop_pct) > 9999:
            pop_pct = None

        day1_cat = classify_day1(pop_pct)

        pop_str = ("+%.1f%%" % pop_pct) if pop_pct is not None else "N/A"
        print("  " + ticker.ljust(8) + "  " + str(first_date) +
              "  price=%.2f  close=%.2f  pop=%s  [%s]  %s" % (
              ipo_price or 0, d1_close or 0, pop_str, day1_cat, company_name))

        try:
            cur.execute("""
                INSERT INTO ipo_registry
                  (ticker, ipo_date, ipo_price, company_name, sector, industry,
                   exchange, underwriter, shares_offered,
                   day1_open, day1_high, day1_low, day1_close, day1_volume,
                   day1_pop_pct, day1_category, source)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'build_ipo_registry')
                ON CONFLICT (ticker) DO UPDATE SET
                  ipo_date       = EXCLUDED.ipo_date,
                  ipo_price      = EXCLUDED.ipo_price,
                  company_name   = COALESCE(NULLIF(EXCLUDED.company_name,''), ipo_registry.company_name),
                  sector         = COALESCE(NULLIF(EXCLUDED.sector,''), ipo_registry.sector),
                  industry       = COALESCE(NULLIF(EXCLUDED.industry,''), ipo_registry.industry),
                  exchange       = COALESCE(NULLIF(EXCLUDED.exchange,''), ipo_registry.exchange),
                  underwriter    = COALESCE(EXCLUDED.underwriter, ipo_registry.underwriter),
                  shares_offered = COALESCE(EXCLUDED.shares_offered, ipo_registry.shares_offered),
                  day1_open      = EXCLUDED.day1_open,
                  day1_high      = EXCLUDED.day1_high,
                  day1_low       = EXCLUDED.day1_low,
                  day1_close     = EXCLUDED.day1_close,
                  day1_volume    = EXCLUDED.day1_volume,
                  day1_pop_pct   = EXCLUDED.day1_pop_pct,
                  day1_category  = EXCLUDED.day1_category,
                  source         = EXCLUDED.source
            """, (
                ticker, first_date, ipo_price, company_name, sector, industry,
                exchange_v, underwriter, shares_off,
                d1_open, d1_high, d1_low, d1_close, d1_vol,
                round(pop_pct, 4) if pop_pct is not None else None,
                day1_cat,
            ))
            upserted += 1
        except Exception as e:
            print("  SKIP %s: %s" % (ticker, e))

    stale = list(EXCLUDE_TICKERS) + ["BRK-B","GLD","LQD","DIA","TLT","UUP","HYG"]
    cur.execute("DELETE FROM ipo_registry WHERE ticker = ANY(%s)", (stale,))
    deleted = cur.rowcount

    cur.close()
    conn.close()

    print("\n" + "="*60)
    print("  REGISTRY BUILD COMPLETE")
    print("  Upserted: %d  |  Stale rows removed: %d" % (upserted, deleted))

    conn2 = psycopg2.connect(DB_URL)
    cur2 = conn2.cursor()
    cur2.execute("SELECT day1_category, COUNT(*) FROM ipo_registry GROUP BY day1_category ORDER BY day1_category")
    print("\n  Day1 category breakdown:")
    for cat, cnt in cur2.fetchall():
        print("    %-10s: %d" % (cat, cnt))
    cur2.close()
    conn2.close()
    print("="*60)


if __name__ == "__main__":
    main()