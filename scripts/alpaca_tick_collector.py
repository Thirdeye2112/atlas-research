"""
Alpaca Tick Collector + Footprint Aggregator
=============================================
Collects tick-by-tick trade data from Alpaca and aggregates into
5-minute footprint candles (buy vol / sell vol / delta per price level).

Usage:
    # Historical backfill (last N days)
    python scripts/alpaca_tick_collector.py backfill --tickers AAPL MSFT NVDA --days 30

    # Live stream (runs during market hours, Ctrl+C to stop)
    python scripts/alpaca_tick_collector.py stream --tickers AAPL MSFT NVDA

    # Aggregate existing tick parquets → footprint candles
    python scripts/alpaca_tick_collector.py aggregate --tick-dir C:\Atlas\data\ticks

Env vars required:
    ALPACA_API_KEY
    ALPACA_SECRET_KEY

Output:
    <out-dir>/ticks/<TICKER>_ticks_<date>.parquet   — raw tick data
    <out-dir>/footprint/<TICKER>_fp_5m.parquet      — 5m footprint candles
"""

from __future__ import annotations
import os, sys, json, time, argparse, warnings
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL_DATA  = "https://data.alpaca.markets"
BASE_URL_PAPER = "https://paper-api.alpaca.markets"
FEED           = "iex"          # iex = free; sip = paid
OUT_DIR        = Path(os.environ.get("ALPACA_OUT_DIR", r"C:\Atlas\data"))

# Lee-Ready tolerance: trades within $0.01 of ask → buy, of bid → sell
LR_TICK = 0.01


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    key    = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        sys.exit(1)
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json"}


def _get(url: str, params: dict | None = None, retries: int = 3) -> dict:
    import urllib.request, urllib.parse
    hdrs = _headers()
    if params:
        url = url + "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# Historical tick fetcher (paginated)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_trades_historical(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Fetch all trades for ticker between start/end (ISO 8601 strings).
    Returns DataFrame with columns: ts, price, size, exchange, conditions.
    """
    url    = f"{BASE_URL_DATA}/v2/stocks/{ticker}/trades"
    params = {"start": start, "end": end, "feed": FEED,
              "limit": 10000, "sort": "asc"}
    rows   = []
    page   = 0

    while True:
        data   = _get(url, params)
        trades = data.get("trades", [])
        for t in trades:
            rows.append({
                "ts":         t.get("t"),
                "price":      float(t.get("p", 0)),
                "size":       int(t.get("s", 0)),
                "exchange":   t.get("x", ""),
                "conditions": ",".join(t.get("c", [])),
            })
        token = data.get("next_page_token")
        page += 1
        if not token:
            break
        params["page_token"] = token
        if page % 10 == 0:
            print(f"    {ticker}: fetched {len(rows):,} trades (page {page})")

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def fetch_quotes_latest(tickers: list[str]) -> dict[str, dict]:
    """Fetch latest NBBO quote for each ticker (for Lee-Ready classification)."""
    url    = f"{BASE_URL_DATA}/v2/stocks/quotes/latest"
    params = {"symbols": ",".join(tickers), "feed": FEED}
    data   = _get(url, params)
    return data.get("quotes", {})


# ─────────────────────────────────────────────────────────────────────────────
# Lee-Ready trade classification
# ─────────────────────────────────────────────────────────────────────────────

def classify_trades(trades: pd.DataFrame, quotes: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Classify each trade as buy (+1) or sell (-1) aggressor using tick rule
    (Lee-Ready requires bid/ask at trade time; tick rule is the fallback).

    Tick rule:
      - Price > prev price → buy
      - Price < prev price → sell
      - Price == prev price → carry forward last direction (zero-tick rule)
    """
    t = trades.copy()

    if quotes is not None and "bid" in quotes.columns and "ask" in quotes.columns:
        mid = (quotes["bid"] + quotes["ask"]) / 2
        t["direction"] = np.where(t["price"] >= mid, 1, -1)
    else:
        # Tick rule
        diff = t["price"].diff()
        dirs = np.zeros(len(t), dtype=float)
        last = 0.0
        for i, d in enumerate(diff.values):
            if d > 0:   last = 1.0
            elif d < 0: last = -1.0
            dirs[i] = last
        t["direction"] = dirs

    t["buy_vol"]  = np.where(t["direction"] > 0, t["size"], 0)
    t["sell_vol"] = np.where(t["direction"] < 0, t["size"], 0)
    return t


# ─────────────────────────────────────────────────────────────────────────────
# Footprint aggregator
# ─────────────────────────────────────────────────────────────────────────────

def aggregate_footprint(trades: pd.DataFrame,
                        freq: str = "5min",
                        price_tick: float = 0.05) -> pd.DataFrame:
    """
    Aggregate classified tick data into footprint candles.

    Each row = one 5-minute bar + price level bucket.
    Columns:
        bar_ts         — candle open timestamp
        price_bucket   — rounded price level
        buy_vol        — buyer-aggressor volume at this level
        sell_vol       — seller-aggressor volume at this level
        delta          — buy_vol - sell_vol (positive = buying pressure)
        trades         — total trade count
    """
    if trades.empty:
        return pd.DataFrame()

    t = trades.copy()
    t["bar_ts"]      = t["ts"].dt.floor(freq)
    t["price_bucket"]= (t["price"] / price_tick).round() * price_tick

    fp = t.groupby(["bar_ts", "price_bucket"]).agg(
        buy_vol  = ("buy_vol",  "sum"),
        sell_vol = ("sell_vol", "sum"),
        trades   = ("size",     "count"),
    ).reset_index()
    fp["delta"] = fp["buy_vol"] - fp["sell_vol"]
    return fp.sort_values(["bar_ts", "price_bucket"]).reset_index(drop=True)


def aggregate_candle_summary(footprint: pd.DataFrame) -> pd.DataFrame:
    """
    Roll footprint rows up to one row per 5m candle.
    Columns: bar_ts, total_buy, total_sell, delta, cvd, trades,
             poc_price (price of max volume), buy_pct
    """
    if footprint.empty:
        return pd.DataFrame()

    grp = footprint.groupby("bar_ts")
    summary = pd.DataFrame({
        "total_buy":  grp["buy_vol"].sum(),
        "total_sell": grp["sell_vol"].sum(),
        "delta":      grp["delta"].sum(),
        "trades":     grp["trades"].sum(),
    }).reset_index()
    summary["buy_pct"] = summary["total_buy"] / (
        summary["total_buy"] + summary["total_sell"]).replace(0, np.nan) * 100

    # POC = price level with highest total volume in the bar
    vol_by_level = footprint.copy()
    vol_by_level["total_vol"] = vol_by_level["buy_vol"] + vol_by_level["sell_vol"]
    poc = vol_by_level.loc[vol_by_level.groupby("bar_ts")["total_vol"].idxmax(),
                           ["bar_ts", "price_bucket"]].rename(
                               columns={"price_bucket": "poc_price"})
    summary = summary.merge(poc, on="bar_ts", how="left")

    # Cumulative volume delta (CVD) — shows directional accumulation over session
    summary = summary.sort_values("bar_ts").reset_index(drop=True)
    summary["cvd"] = summary.groupby(summary["bar_ts"].dt.date)["delta"].cumsum()

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# NBBO snapshot (for live use)
# ─────────────────────────────────────────────────────────────────────────────

def snapshot_nbbo(tickers: list[str], out_dir: Path) -> pd.DataFrame:
    """Grab latest NBBO for all tickers and append to a daily parquet."""
    quotes_raw = fetch_quotes_latest(tickers)
    rows = []
    ts   = datetime.now(timezone.utc).replace(tzinfo=None)
    for ticker, q in quotes_raw.items():
        rows.append({
            "ts":       ts,
            "ticker":   ticker,
            "bid":      float(q.get("bp", 0)),
            "bid_size": int(q.get("bs", 0)),
            "ask":      float(q.get("ap", 0)),
            "ask_size": int(q.get("as", 0)),
            "spread":   float(q.get("ap", 0)) - float(q.get("bp", 0)),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    date_str = ts.strftime("%Y%m%d")
    p = out_dir / "nbbo" / f"nbbo_{date_str}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        existing = pd.read_parquet(p)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_parquet(p, index=False)
    print(f"  NBBO snapshot saved → {p.name}  ({len(rows)} tickers)")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Subcommands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_backfill(args):
    tickers = [t.upper() for t in args.tickers]
    days    = args.days
    out_dir = Path(args.out_dir)
    end     = datetime.now(timezone.utc)
    start   = end - timedelta(days=days)
    start_s = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_s   = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"=== Backfill: {len(tickers)} tickers  last {days} days ===")
    print(f"  Range: {start_s} → {end_s}\n")

    for ticker in tickers:
        print(f"  {ticker} ...", end=" ", flush=True)
        try:
            trades = fetch_trades_historical(ticker, start_s, end_s)
            if trades.empty:
                print("no data")
                continue
            classified = classify_trades(trades)
            footprint  = aggregate_footprint(classified)
            summary    = aggregate_candle_summary(footprint)

            # Save raw ticks
            tick_dir = out_dir / "ticks"
            tick_dir.mkdir(parents=True, exist_ok=True)
            date_tag = start.strftime("%Y%m%d")
            tp = tick_dir / f"{ticker}_ticks_{date_tag}.parquet"
            classified.to_parquet(tp, index=False)

            # Save footprint candle summary
            fp_dir = out_dir / "footprint"
            fp_dir.mkdir(parents=True, exist_ok=True)
            sp = fp_dir / f"{ticker}_fp_5m.parquet"
            if sp.exists():
                existing = pd.read_parquet(sp)
                summary  = pd.concat([existing, summary], ignore_index=True)
                summary  = summary.drop_duplicates("bar_ts").sort_values("bar_ts").reset_index(drop=True)
            summary.to_parquet(sp, index=False)

            print(f"{len(trades):,} ticks → {len(summary)} 5m bars  buy%={summary['buy_pct'].mean():.1f}%")
        except Exception as e:
            print(f"ERROR: {e}")

    print("\nDone.")


def cmd_stream(args):
    """Live WebSocket tick stream — runs until Ctrl+C."""
    try:
        import websocket
    except ImportError:
        print("Installing websocket-client ...")
        os.system(f"{sys.executable} -m pip install websocket-client -q")
        import websocket

    tickers = [t.upper() for t in args.tickers]
    out_dir = Path(args.out_dir)
    key     = os.environ.get("ALPACA_API_KEY", "")
    secret  = os.environ.get("ALPACA_SECRET_KEY", "")
    url     = f"wss://stream.data.alpaca.markets/v2/{FEED}"

    buffer: dict[str, list] = defaultdict(list)
    last_flush = time.time()
    FLUSH_SECS = 300  # flush to disk every 5 minutes

    def flush():
        nonlocal last_flush
        ts_now = datetime.now(timezone.utc).replace(tzinfo=None)
        date_s = ts_now.strftime("%Y%m%d")
        for ticker, rows in list(buffer.items()):
            if not rows: continue
            df = pd.DataFrame(rows)
            df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
            classified = classify_trades(df)
            footprint  = aggregate_footprint(classified)
            summary    = aggregate_candle_summary(footprint)

            tick_dir = out_dir / "ticks"
            tick_dir.mkdir(parents=True, exist_ok=True)
            tp = tick_dir / f"{ticker}_ticks_{date_s}.parquet"
            if tp.exists():
                existing = pd.read_parquet(tp)
                classified = pd.concat([existing, classified], ignore_index=True).drop_duplicates("ts")
            classified.to_parquet(tp, index=False)

            fp_dir = out_dir / "footprint"
            fp_dir.mkdir(parents=True, exist_ok=True)
            sp = fp_dir / f"{ticker}_fp_5m.parquet"
            if sp.exists():
                existing = pd.read_parquet(sp)
                summary  = pd.concat([existing, summary], ignore_index=True)
                summary  = summary.drop_duplicates("bar_ts").sort_values("bar_ts").reset_index(drop=True)
            summary.to_parquet(sp, index=False)
            buffer[ticker].clear()
        last_flush = time.time()
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] Flushed to disk")

    def on_open(ws):
        ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))

    def on_message(ws, message):
        msgs = json.loads(message)
        for m in msgs:
            if m.get("T") == "t":  # trade
                ticker = m.get("S", "")
                if ticker in tickers:
                    buffer[ticker].append({
                        "ts":         m.get("t"),
                        "price":      float(m.get("p", 0)),
                        "size":       int(m.get("s", 0)),
                        "exchange":   m.get("x", ""),
                        "conditions": ",".join(m.get("c", [])),
                    })
            elif m.get("T") == "success" and m.get("msg") == "authenticated":
                subs = {"action": "subscribe", "trades": tickers}
                ws.send(json.dumps(subs))
                print(f"  Subscribed to {len(tickers)} tickers: {tickers[:5]}{'...' if len(tickers)>5 else ''}")
        if time.time() - last_flush > FLUSH_SECS:
            flush()

    def on_error(ws, err):
        print(f"WebSocket error: {err}")

    def on_close(ws, *_):
        print("Stream closed — flushing buffer ...")
        flush()

    print(f"=== Live Tick Stream: {len(tickers)} tickers ===")
    print(f"  Output → {out_dir}")
    print(f"  Flushing to disk every {FLUSH_SECS//60} minutes")
    print(f"  Press Ctrl+C to stop\n")

    ws_app = websocket.WebSocketApp(url,
                                     on_open=on_open,
                                     on_message=on_message,
                                     on_error=on_error,
                                     on_close=on_close)
    try:
        ws_app.run_forever()
    except KeyboardInterrupt:
        ws_app.close()


def cmd_aggregate(args):
    """Re-aggregate existing tick parquets → footprint candles."""
    tick_dir = Path(args.tick_dir)
    out_dir  = Path(args.out_dir)
    files    = sorted(tick_dir.glob("*_ticks_*.parquet"))
    print(f"=== Aggregate: {len(files)} tick files ===")

    by_ticker: dict[str, list[Path]] = defaultdict(list)
    for f in files:
        ticker = f.stem.split("_")[0].upper()
        by_ticker[ticker].append(f)

    for ticker, fps in sorted(by_ticker.items()):
        frames = [pd.read_parquet(f) for f in fps]
        trades = pd.concat(frames, ignore_index=True)
        trades["ts"] = pd.to_datetime(trades["ts"])
        trades = trades.drop_duplicates("ts").sort_values("ts").reset_index(drop=True)

        if "direction" not in trades.columns:
            trades = classify_trades(trades)
        footprint = aggregate_footprint(trades)
        summary   = aggregate_candle_summary(footprint)

        fp_dir = out_dir / "footprint"
        fp_dir.mkdir(parents=True, exist_ok=True)
        sp = fp_dir / f"{ticker}_fp_5m.parquet"
        summary.to_parquet(sp, index=False)
        print(f"  {ticker}: {len(trades):,} ticks → {len(summary)} 5m bars")

    print("Done.")


def cmd_snapshot(args):
    """Grab one NBBO snapshot right now for all tickers."""
    tickers = [t.upper() for t in args.tickers]
    out_dir = Path(args.out_dir)
    df      = snapshot_nbbo(tickers, out_dir)
    if not df.empty:
        print(df[["ticker","bid","ask","spread","bid_size","ask_size"]].to_string(index=False))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Alpaca Tick Collector + Footprint Aggregator")
    ap.add_argument("--out-dir", default=str(OUT_DIR),
                    help="Base output directory (default: ALPACA_OUT_DIR env or C:\\Atlas\\data)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # backfill
    p_bf = sub.add_parser("backfill", help="Historical tick backfill")
    p_bf.add_argument("--tickers", nargs="+", required=True)
    p_bf.add_argument("--days",    type=int,  default=30)

    # stream
    p_st = sub.add_parser("stream", help="Live WebSocket tick stream")
    p_st.add_argument("--tickers", nargs="+", required=True)

    # aggregate
    p_ag = sub.add_parser("aggregate", help="Aggregate existing tick parquets")
    p_ag.add_argument("--tick-dir", required=True)

    # snapshot
    p_sn = sub.add_parser("snapshot", help="Single NBBO quote snapshot")
    p_sn.add_argument("--tickers", nargs="+", required=True)

    args = ap.parse_args()

    if args.cmd   == "backfill":  cmd_backfill(args)
    elif args.cmd == "stream":    cmd_stream(args)
    elif args.cmd == "aggregate": cmd_aggregate(args)
    elif args.cmd == "snapshot":  cmd_snapshot(args)


if __name__ == "__main__":
    main()
