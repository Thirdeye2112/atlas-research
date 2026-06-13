#!/usr/bin/env python3
"""
fetch_full_us_universe.py
--------------------------
Downloads all tradeable US stocks from the NASDAQ screener API
(NASDAQ, NYSE, AMEX) and writes them to config/universe.csv.

Filters:
  - Price >= $1.00  (no sub-dollar)
  - Ticker 1-5 uppercase letters only  (no warrants, units, preferred)
  - No special chars (., ^, /)
  - Market cap >= $50M or unknown  (remove true micro-caps)

Run from the atlas-research project root:
    python scripts/fetch_full_us_universe.py
"""

import time
from pathlib import Path

import pandas as pd
import requests

OUT_PATH = Path(__file__).resolve().parent.parent / "config" / "universe.csv"

frames = []

for exchange in ['nasdaq', 'nyse', 'amex']:
    url = (
        f'https://api.nasdaq.com/api/screener/stocks'
        f'?tableonly=true&limit=25000&exchange={exchange}'
    )
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Accept': 'application/json',
        'Origin': 'https://www.nasdaq.com',
        'Referer': 'https://www.nasdaq.com/',
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    rows = r.json()['data']['table']['rows']
    df = pd.DataFrame(rows)
    df['exchange'] = exchange.upper()
    frames.append(df)
    print(f'{exchange.upper()}: {len(df)} tickers')
    time.sleep(1)

df = pd.concat(frames, ignore_index=True)
df = df.rename(columns={'symbol': 'ticker'})
df['ticker'] = df['ticker'].str.strip()

# ── Filters ───────────────────────────────────────────────────────────────────

# Clean price
df['_price'] = pd.to_numeric(
    df['lastsale'].str.replace('$', '', regex=False), errors='coerce'
)

# Clean market cap
df['_mktcap'] = pd.to_numeric(df['marketCap'], errors='coerce')

# 1) Remove sub-dollar stocks
df = df[df['_price'] >= 1.0]

# 2) Ticker must be 1-5 uppercase letters only (no warrants /W, units /U, etc.)
df = df[df['ticker'].str.match(r'^[A-Z]{1,5}$')]

# 3) No special characters
df = df[~df['ticker'].str.contains(r'[.^/]', regex=True)]

# 4) Remove duplicates (same ticker on multiple exchanges — keep first occurrence)
df = df.drop_duplicates('ticker')

# 5) Market cap: keep if unknown OR >= $50M
df = df[(df['_mktcap'].isna()) | (df['_mktcap'] >= 50_000_000)]

# ── Output ────────────────────────────────────────────────────────────────────

# Sector/industry not returned by NASDAQ screener API — fill empty
for col in ('sector', 'industry'):
    if col not in df.columns:
        df[col] = ''

out = (
    df[['ticker', 'name', 'sector', 'industry', 'exchange']]
    .sort_values('ticker')
    .reset_index(drop=True)
)

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT_PATH, index=False)
print(f'\nTotal: {len(out)} tradeable US stocks written to {OUT_PATH}')
