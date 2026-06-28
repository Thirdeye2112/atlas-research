"""
Alpaca Auto Stream — market-hours-aware live tick collector
===========================================================
Designed to be triggered by Windows Task Scheduler at 06:25 AM Pacific
(5 minutes before market open). It:

  1. Calls Alpaca clock API to confirm market is open (or waits until it is)
  2. Starts the WebSocket tick stream for your full ticker universe
  3. Automatically stops at market close
  4. Logs everything to logs/stream_YYYYMMDD.log
  5. Pushes daily footprint parquets to GitHub at end of day (optional)

Usage:
    python scripts/alpaca_stream_auto.py [--tickers AAPL MSFT ...] [--universe]
    python scripts/alpaca_stream_auto.py --universe   # uses all tickers from 5m parquets

Env vars:
    ALPACA_API_KEY, ALPACA_SECRET_KEY
    ALPACA_OUT_DIR   (default C:\Atlas\data)
    ALPACA_5M_DIR    (default C:\Atlas\data\5m  — used to discover universe)
    GITHUB_TOKEN     (optional — push footprints to atlas-research at close)
"""

from __future__ import annotations
import os, sys, json, time, argparse, logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd

BASE_URL_DATA = "https://data.alpaca.markets"
BASE_URL_API  = "https://api.alpaca.markets"
FEED          = "iex"
OUT_DIR       = Path(os.environ.get("ALPACA_OUT_DIR", r"C:\Atlas\data"))
PARQUET_5M    = Path(os.environ.get("ALPACA_5M_DIR",  r"C:\Atlas\data\5m"))
FLUSH_SECS    = 300   # flush ticks to disk every 5 minutes
PRICE_TICK    = 0.05  # footprint bucket size ($0.05)


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging() -> logging.Logger:
    log_dir = OUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    date_s  = datetime.now().strftime("%Y%m%d")
    log_file = log_dir / f"stream_{date_s}.log"

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                            datefmt="%H:%M:%S")
    fh  = logging.FileHandler(log_file, encoding="utf-8")
    ch  = logging.StreamHandler(sys.stdout)
    fh.setFormatter(fmt); ch.setFormatter(fmt)

    log = logging.getLogger("atlas_stream")
    log.setLevel(logging.INFO)
    log.addHandler(fh); log.addHandler(ch)
    log.info(f"Log → {log_file}")
    return log


logger: logging.Logger | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Alpaca helpers
# ─────────────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    key    = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    if not key or not secret:
        print("ERROR: ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
        sys.exit(1)
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
            "Accept": "application/json"}


def _get(url: str, params: dict | None = None) -> dict:
    import urllib.request, urllib.parse
    hdrs = _headers()
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get_clock() -> dict:
    """Returns {is_open, next_open, next_close} from Alpaca."""
    return _get(f"{BASE_URL_API}/v2/clock")


def wait_for_market_open(log) -> datetime:
    """Block until market is open. Returns the close time."""
    while True:
        clock = get_clock()
        if clock.get("is_open"):
            close_str = clock["next_close"]
            close_dt  = datetime.fromisoformat(close_str.replace("Z", "+00:00"))
            log.info(f"Market is OPEN  |  closes at {close_dt.strftime('%H:%M UTC')}")
            return close_dt
        next_open = clock.get("next_open", "")
        log.info(f"Market closed. Next open: {next_open}  — waiting 60s ...")
        time.sleep(60)


# ─────────────────────────────────────────────────────────────────────────────
# Universe discovery
# ─────────────────────────────────────────────────────────────────────────────

def discover_universe(parquet_dir: Path) -> list[str]:
    """Read tickers from all 5m parquet filenames in the data dir."""
    files = sorted(parquet_dir.glob("*.parquet"))
    seen  = set()
    for f in files:
        ticker = f.stem.split("_")[0].upper()
        seen.add(ticker)
    return sorted(seen)


# ─────────────────────────────────────────────────────────────────────────────
# Tick classification + footprint (inline, no import needed)
# ─────────────────────────────────────────────────────────────────────────────

def classify_tick_rule(prices: list[float], sizes: list[int]) -> list[int]:
    dirs = []
    last = 0
    for i, p in enumerate(prices):
        if i == 0:
            dirs.append(0)
            continue
        if p > prices[i-1]:   last = 1
        elif p < prices[i-1]: last = -1
        dirs.append(last)
    return dirs


def flush_buffer(ticker: str, rows: list[dict], out_dir: Path, log) -> None:
    if not rows:
        return
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"], utc=True).dt.tz_localize(None)
    df = df.sort_values("ts").reset_index(drop=True)

    # Tick-rule classification
    dirs = classify_tick_rule(df["price"].tolist(), df["size"].tolist())
    df["direction"] = dirs
    df["buy_vol"]   = np.where(np.array(dirs) > 0, df["size"], 0)
    df["sell_vol"]  = np.where(np.array(dirs) < 0, df["size"], 0)

    # Save raw ticks
    date_s   = datetime.now().strftime("%Y%m%d")
    tick_dir = out_dir / "ticks"
    tick_dir.mkdir(parents=True, exist_ok=True)
    tp = tick_dir / f"{ticker}_ticks_{date_s}.parquet"
    if tp.exists():
        existing = pd.read_parquet(tp)
        df = pd.concat([existing, df], ignore_index=True).drop_duplicates("ts")
    df.to_parquet(tp, index=False)

    # Footprint candles
    df["bar_ts"]       = df["ts"].dt.floor("5min")
    df["price_bucket"] = (df["price"] / PRICE_TICK).round() * PRICE_TICK
    fp = df.groupby(["bar_ts", "price_bucket"]).agg(
        buy_vol  = ("buy_vol",  "sum"),
        sell_vol = ("sell_vol", "sum"),
        trades   = ("size",     "count"),
    ).reset_index()
    fp["delta"] = fp["buy_vol"] - fp["sell_vol"]

    # Candle summary
    grp = fp.groupby("bar_ts")
    summary = pd.DataFrame({
        "total_buy":  grp["buy_vol"].sum(),
        "total_sell": grp["sell_vol"].sum(),
        "delta":      grp["delta"].sum(),
        "trades":     grp["trades"].sum(),
    }).reset_index()
    summary["buy_pct"] = (summary["total_buy"] /
                          (summary["total_buy"] + summary["total_sell"]).replace(0, np.nan) * 100)
    vol_by = fp.copy()
    vol_by["total_vol"] = vol_by["buy_vol"] + vol_by["sell_vol"]
    poc = vol_by.loc[vol_by.groupby("bar_ts")["total_vol"].idxmax(),
                     ["bar_ts","price_bucket"]].rename(columns={"price_bucket":"poc_price"})
    summary = summary.merge(poc, on="bar_ts", how="left")
    summary = summary.sort_values("bar_ts").reset_index(drop=True)
    summary["cvd"] = summary.groupby(summary["bar_ts"].dt.date)["delta"].cumsum()

    fp_dir = out_dir / "footprint"
    fp_dir.mkdir(parents=True, exist_ok=True)
    sp = fp_dir / f"{ticker}_fp_5m.parquet"
    if sp.exists():
        existing = pd.read_parquet(sp)
        summary  = pd.concat([existing, summary], ignore_index=True)
        summary  = summary.drop_duplicates("bar_ts").sort_values("bar_ts").reset_index(drop=True)
    summary.to_parquet(sp, index=False)

    log.info(f"  {ticker}: flushed {len(rows):,} ticks → {len(summary)} 5m fp bars")


# ─────────────────────────────────────────────────────────────────────────────
# GitHub push at end of day
# ─────────────────────────────────────────────────────────────────────────────

def push_daily_summary(out_dir: Path, tickers: list[str], log) -> None:
    import base64, urllib.request
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        log.info("GITHUB_TOKEN not set — skipping GitHub push")
        return

    REPO   = "Thirdeye2112/atlas-research"
    BRANCH = "main"
    date_s = datetime.now().strftime("%Y%m%d")

    def push(path_in_repo: str, content: bytes) -> None:
        api  = f"https://api.github.com/repos/{REPO}/contents/{path_in_repo}"
        hdrs = {"Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "Content-Type": "application/json",
                "User-Agent": "atlas-research-bot"}
        sha = None
        try:
            req = urllib.request.Request(api, headers=hdrs)
            with urllib.request.urlopen(req) as r:
                sha = json.loads(r.read()).get("sha")
        except Exception:
            pass
        payload: dict = {
            "message": f"[tick-stream] daily footprint {date_s}",
            "content": base64.b64encode(content).decode("ascii"),
            "branch":  BRANCH,
        }
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                     headers=hdrs, method="PUT")
        with urllib.request.urlopen(req) as r:
            log.info(f"  GitHub → {path_in_repo} [{r.status}]")

    # Build a combined daily summary CSV
    frames = []
    for ticker in tickers:
        sp = out_dir / "footprint" / f"{ticker}_fp_5m.parquet"
        if not sp.exists():
            continue
        df = pd.read_parquet(sp)
        today = datetime.now().date()
        df["_date"] = pd.to_datetime(df["bar_ts"]).dt.date
        day_df = df[df["_date"] == today].copy()
        if day_df.empty:
            continue
        day_df["ticker"] = ticker
        frames.append(day_df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        csv_bytes = combined.to_csv(index=False).encode("utf-8")
        push(f"data/footprint/footprint_{date_s}.csv", csv_bytes)
    else:
        log.info("No footprint data to push for today")


# ─────────────────────────────────────────────────────────────────────────────
# Main stream loop
# ─────────────────────────────────────────────────────────────────────────────

def run_stream(tickers: list[str], market_close: datetime, out_dir: Path, log) -> None:
    try:
        import websocket
    except ImportError:
        log.info("Installing websocket-client ...")
        os.system(f"{sys.executable} -m pip install websocket-client -q")
        import websocket

    key    = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    url    = f"wss://stream.data.alpaca.markets/v2/{FEED}"

    buffer: dict[str, list] = defaultdict(list)
    last_flush = time.time()
    stop_flag  = [False]

    def flush_all():
        for ticker, rows in list(buffer.items()):
            if rows:
                flush_buffer(ticker, rows, out_dir, log)
                buffer[ticker].clear()

    def on_open(ws):
        ws.send(json.dumps({"action": "auth", "key": key, "secret": secret}))

    def on_message(ws, message):
        nonlocal last_flush
        msgs = json.loads(message)
        for m in msgs:
            if m.get("T") == "t":
                ticker = m.get("S", "")
                if ticker in tickers:
                    buffer[ticker].append({
                        "ts":    m.get("t"),
                        "price": float(m.get("p", 0)),
                        "size":  int(m.get("s", 0)),
                        "exchange":   m.get("x", ""),
                        "conditions": ",".join(m.get("c", [])),
                    })
            elif m.get("T") == "success" and m.get("msg") == "authenticated":
                ws.send(json.dumps({"action": "subscribe", "trades": tickers}))
                log.info(f"Subscribed: {len(tickers)} tickers")

        # Flush every 5 minutes
        if time.time() - last_flush > FLUSH_SECS:
            flush_all()
            last_flush = time.time()

        # Auto-stop at market close
        now_utc = datetime.now(timezone.utc)
        if now_utc >= market_close and not stop_flag[0]:
            stop_flag[0] = True
            log.info("Market closed — shutting down stream")
            ws.close()

    def on_error(ws, err):
        log.error(f"WebSocket error: {err}")

    def on_close(ws, *_):
        log.info("Stream closed — final flush ...")
        flush_all()

    log.info(f"Starting stream  |  {len(tickers)} tickers  |  "
             f"closes {market_close.strftime('%H:%M UTC')}")

    ws_app = websocket.WebSocketApp(url, on_open=on_open, on_message=on_message,
                                     on_error=on_error, on_close=on_close)
    try:
        ws_app.run_forever(ping_interval=30, ping_timeout=10,
                           reconnect=5)   # auto-reconnect on drop
    except KeyboardInterrupt:
        log.info("Interrupted — flushing ...")
        flush_all()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global logger
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers",   nargs="+", default=None)
    ap.add_argument("--universe",  action="store_true",
                    help="Auto-discover tickers from ALPACA_5M_DIR parquets")
    ap.add_argument("--out-dir",   default=str(OUT_DIR))
    ap.add_argument("--no-github", action="store_true")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    logger  = setup_logging()

    # Resolve ticker list
    if args.universe:
        tickers = discover_universe(PARQUET_5M)
        if not tickers:
            logger.error(f"No tickers found in {PARQUET_5M}")
            sys.exit(1)
        logger.info(f"Universe: {len(tickers)} tickers from {PARQUET_5M}")
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        logger.error("Pass --tickers or --universe")
        sys.exit(1)

    logger.info(f"Tickers: {tickers[:10]}{'...' if len(tickers)>10 else ''}")

    # Wait for market open
    market_close = wait_for_market_open(logger)

    # Run stream until close
    run_stream(tickers, market_close, out_dir, logger)

    # End-of-day push to GitHub
    if not args.no_github:
        logger.info("End-of-day GitHub push ...")
        push_daily_summary(out_dir, tickers, logger)

    logger.info("Session complete.")


if __name__ == "__main__":
    main()
