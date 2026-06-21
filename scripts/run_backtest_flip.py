"""
run_backtest_flip.py
--------------------
Flip strategy backtest comparing three strategies using Jarvis (OMNI = EMA(Low, 82)) signals.

Strategies:
  A. hold_jarvis     — Hold long between OMNI cross_up and cross_down; stay in cash otherwise
  B. flip_any        — Always in market; flip long→short on every OMNI cross
  C. flip_confirmed  — Flip only when 2+ signals confirm (OMNI cross + one of: RSI momentum,
                       volume climax, price vs SMA20); requires confidence >= 60

Universe: all tickers in raw_bars, 2019-01-01 through today
"""

import os, sys
import numpy as np
import pandas as pd
import psycopg2
import json
from datetime import date
from dotenv import load_dotenv

load_dotenv(override=True)
DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    sys.exit("DATABASE_URL not set. Check your .env and that load_dotenv() ran.")

# ── EMA helper ────────────────────────────────────────────────────────────────

def ema(series: np.ndarray, period: int) -> np.ndarray:
    """Wilder-style EMA initialised on first `period` bars."""
    result = np.full(len(series), np.nan)
    if len(series) < period:
        return result
    result[period - 1] = series[:period].mean()
    alpha = 2.0 / (period + 1)
    for i in range(period, len(series)):
        result[i] = series[i] * alpha + result[i - 1] * (1 - alpha)
    return result


def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder RSI."""
    result = np.full(len(closes), np.nan)
    if len(closes) < period + 1:
        return result
    deltas = np.diff(closes)
    gains  = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[:period].mean()
    avg_loss = losses[:period].mean()
    for i in range(period, len(closes) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss > 1e-10 else 100.0
        result[i + 1] = 100.0 - 100.0 / (1.0 + rs)
    return result


def sma(series: np.ndarray, period: int) -> np.ndarray:
    result = np.full(len(series), np.nan)
    for i in range(period - 1, len(series)):
        result[i] = series[i - period + 1 : i + 1].mean()
    return result


# ── Signal computation ────────────────────────────────────────────────────────

def compute_signals(df: pd.DataFrame):
    """Add signal columns to the ticker's bar DataFrame."""
    lows    = df["low"].values
    closes  = df["close"].values
    volumes = df["volume"].values.astype(float)
    highs   = df["high"].values

    omni         = ema(lows, 82)
    omni_above   = closes > omni                          # price above OMNI line
    rsi_vals     = rsi(closes, 14)
    sma20        = sma(closes, 20)
    vol_sma20    = sma(volumes, 20)

    # RSI momentum (today vs 5 bars ago)
    rsi_mom = np.full(len(closes), np.nan)
    rsi_mom[5:] = rsi_vals[5:] - rsi_vals[:-5]

    # Volume ratio
    vol_ratio = np.where(vol_sma20 > 0, volumes / vol_sma20, np.nan)

    # Price vs SMA20 pct
    dist_sma20 = np.where(sma20 > 0, (closes - sma20) / sma20 * 100, np.nan)

    df["omni"]         = omni
    df["omni_above"]   = omni_above
    df["rsi"]          = rsi_vals
    df["rsi_mom"]      = rsi_mom
    df["vol_ratio"]    = vol_ratio
    df["dist_sma20"]   = dist_sma20

    # OMNI cross: True on the bar where above→below or below→above
    above = omni_above.astype(int)
    df["cross_up"]   = (above == 1) & (np.roll(above, 1) == 0)
    df["cross_down"] = (above == 0) & (np.roll(above, 1) == 1)
    # kill wrap-around
    df.loc[df.index[0], ["cross_up", "cross_down"]] = False

    return df


# ── Strategy simulators ───────────────────────────────────────────────────────

def sim_hold_jarvis(df: pd.DataFrame):
    """Strategy A: Hold long when price is above OMNI; cash otherwise."""
    trades = []
    in_trade = False
    entry_price = None
    entry_date  = None
    peak = None

    for i, row in df.iterrows():
        if not in_trade:
            if row["cross_up"] and not np.isnan(row["omni"]):
                in_trade   = True
                entry_price = row["close"]
                entry_date  = row["date"]
                peak        = entry_price
        else:
            peak = max(peak, row["close"])
            if row["cross_down"] or i == df.index[-1]:
                ret = (row["close"] - entry_price) / entry_price * 100
                drawdown = (row["close"] - peak) / peak * 100 if peak > 0 else 0
                trades.append({
                    "direction": "long",
                    "entry": entry_price,
                    "exit":  row["close"],
                    "ret_pct": ret,
                    "drawdown": drawdown,
                    "days": (row["date"] - entry_date).days,
                })
                in_trade = False
    return trades


def sim_flip_any(df: pd.DataFrame):
    """Strategy B: Always in market; flip long↔short on every OMNI cross."""
    trades = []
    in_trade = False
    direction = None
    entry_price = None
    entry_date  = None
    peak = None

    # determine initial direction after warmup
    start_idx = df[~df["omni"].isna()].index
    if len(start_idx) == 0:
        return trades

    first_valid = start_idx[0]
    row0 = df.loc[first_valid]

    in_trade   = True
    direction  = "long" if row0["omni_above"] else "short"
    entry_price = row0["close"]
    entry_date  = row0["date"]
    peak        = entry_price

    for i in df.index:
        if i == first_valid:
            continue
        row = df.loc[i]
        should_flip = (direction == "long" and row["cross_down"]) or \
                      (direction == "short" and row["cross_up"])

        if in_trade:
            exit_price = row["close"]
            if direction == "long":
                peak = max(peak, exit_price)
                drawdown = (exit_price - peak) / peak * 100 if peak > 0 else 0
                ret = (exit_price - entry_price) / entry_price * 100
            else:
                peak = min(peak, exit_price)
                drawdown = (peak - exit_price) / peak * 100 if peak > 0 else 0
                ret = (entry_price - exit_price) / entry_price * 100

            if should_flip or i == df.index[-1]:
                trades.append({
                    "direction": direction,
                    "entry": entry_price,
                    "exit":  exit_price,
                    "ret_pct": ret,
                    "drawdown": drawdown,
                    "days": (row["date"] - entry_date).days,
                })
                if should_flip:
                    direction   = "short" if direction == "long" else "long"
                    entry_price = exit_price
                    entry_date  = row["date"]
                    peak        = exit_price
    return trades


def sim_flip_confirmed(df: pd.DataFrame, min_confidence: int = 60):
    """
    Strategy C: Flip only when OMNI cross is confirmed by at least one additional signal.
    Confirmation signals (each worth 30 pts; OMNI cross = 40 pts):
      - RSI momentum crossing zero in flip direction
      - Volume > 1.5× avg (climax volume)
      - Price crosses SMA20 in same direction as flip
    """
    trades = []
    in_trade = False
    direction = None
    entry_price = None
    entry_date  = None
    peak = None

    start_idx = df[~df["omni"].isna()].index
    if len(start_idx) == 0:
        return trades

    first_valid = start_idx[0]
    row0 = df.loc[first_valid]
    in_trade   = True
    direction  = "long" if row0["omni_above"] else "short"
    entry_price = row0["close"]
    entry_date  = row0["date"]
    peak        = entry_price

    for i in df.index:
        if i == first_valid:
            continue
        row  = df.loc[i]
        flip_to_short = (direction == "long"  and row["cross_down"])
        flip_to_long  = (direction == "short" and row["cross_up"])
        want_flip = flip_to_short or flip_to_long

        # compute confidence if we want to flip
        confidence = 0
        if want_flip:
            confidence += 40  # OMNI cross always fires

            if flip_to_short:
                if not np.isnan(row["rsi_mom"]) and row["rsi_mom"] < 0:
                    confidence += 30
                if not np.isnan(row["vol_ratio"]) and row["vol_ratio"] > 1.5:
                    confidence += 30
                if not np.isnan(row["dist_sma20"]) and row["close"] < row["omni"]:
                    confidence += 20
            else:
                if not np.isnan(row["rsi_mom"]) and row["rsi_mom"] > 0:
                    confidence += 30
                if not np.isnan(row["vol_ratio"]) and row["vol_ratio"] > 1.5:
                    confidence += 30
                if not np.isnan(row["dist_sma20"]) and row["close"] > row["omni"]:
                    confidence += 20

        should_flip = want_flip and confidence >= min_confidence

        if in_trade:
            exit_price = row["close"]
            if direction == "long":
                peak = max(peak, exit_price)
                drawdown = (exit_price - peak) / peak * 100 if peak > 0 else 0
                ret = (exit_price - entry_price) / entry_price * 100
            else:
                peak = min(peak, exit_price)
                drawdown = (peak - exit_price) / peak * 100 if peak > 0 else 0
                ret = (entry_price - exit_price) / entry_price * 100

            if should_flip or i == df.index[-1]:
                trades.append({
                    "direction": direction,
                    "entry": entry_price,
                    "exit":  exit_price,
                    "ret_pct": ret,
                    "drawdown": drawdown,
                    "days": (row["date"] - entry_date).days,
                })
                if should_flip:
                    direction   = "short" if direction == "long" else "long"
                    entry_price = exit_price
                    entry_date  = row["date"]
                    peak        = exit_price
    return trades


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(trades: list, bh_return: float) -> dict:
    if not trades:
        return {
            "total_trades": 0, "win_rate": 0.0, "avg_return_pct": 0.0,
            "total_return_pct": 0.0, "max_drawdown_pct": 0.0,
            "sharpe_ratio": 0.0, "vs_buy_hold_pct": 0.0,
        }
    rets = np.array([t["ret_pct"] for t in trades])
    wins = (rets > 0).sum()
    total_ret = float(rets.sum())
    std = rets.std()
    sharpe = (rets.mean() / std * np.sqrt(252)) if std > 1e-6 else 0.0
    max_dd = float(min(t["drawdown"] for t in trades))
    return {
        "total_trades":      len(trades),
        "win_rate":          float(wins / len(trades)),
        "avg_return_pct":    float(rets.mean()),
        "total_return_pct":  total_ret,
        "max_drawdown_pct":  max_dd,
        "sharpe_ratio":      float(sharpe),
        "vs_buy_hold_pct":   total_ret - bh_return,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # Get universe of tickers
    cur.execute("""
        SELECT DISTINCT ticker FROM raw_bars
        WHERE date >= '2019-01-01' AND ticker != 'SPY'
        ORDER BY ticker
    """)
    tickers = [r[0] for r in cur.fetchall()]
    print(f"Universe: {len(tickers)} tickers")

    date_from = date(2019, 1, 1)
    date_to   = date.today()

    # Aggregate results per strategy
    all_a, all_b, all_c = [], [], []
    bh_returns = []

    for idx, ticker in enumerate(tickers):
        if idx % 50 == 0:
            print(f"  {idx}/{len(tickers)}: {ticker}")

        cur.execute("""
            SELECT date, open, high, low, close, volume
            FROM raw_bars
            WHERE ticker = %s AND date >= '2019-01-01'
            ORDER BY date ASC
        """, (ticker,))
        rows = cur.fetchall()
        if len(rows) < 100:
            continue

        df = pd.DataFrame(rows, columns=["date","open","high","low","close","volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.reset_index(drop=True)

        # Buy-and-hold return for this ticker
        bh = (df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0] * 100
        bh_returns.append(bh)

        df = compute_signals(df)

        trades_a = sim_hold_jarvis(df)
        trades_b = sim_flip_any(df)
        trades_c = sim_flip_confirmed(df, min_confidence=60)

        all_a.extend(trades_a)
        all_b.extend(trades_b)
        all_c.extend(trades_c)

    cur.close()

    avg_bh = float(np.mean(bh_returns)) if bh_returns else 0.0
    metrics_a = compute_metrics(all_a, avg_bh)
    metrics_b = compute_metrics(all_b, avg_bh)
    metrics_c = compute_metrics(all_c, avg_bh)

    # ── Print comparison table ────────────────────────────────────────────────
    header = f"{'Metric':<28} {'A: Hold Jarvis':>16} {'B: Flip Any':>16} {'C: Flip Confirmed':>18}"
    sep    = "-" * len(header)
    print(f"\n{sep}")
    print("  FLIP STRATEGY BACKTEST RESULTS")
    print(f"  Universe: {len(tickers)} tickers  |  {date_from} → {date_to}")
    print(f"  Avg Buy-and-Hold return: {avg_bh:.1f}%")
    print(sep)
    print(header)
    print(sep)

    rows_out = [
        ("Total Trades",        metrics_a["total_trades"],         metrics_b["total_trades"],         metrics_c["total_trades"],         "{:.0f}"),
        ("Win Rate",            metrics_a["win_rate"]*100,          metrics_b["win_rate"]*100,          metrics_c["win_rate"]*100,          "{:.1f}%"),
        ("Avg Return / Trade",  metrics_a["avg_return_pct"],        metrics_b["avg_return_pct"],        metrics_c["avg_return_pct"],        "{:.2f}%"),
        ("Total Return Sum",    metrics_a["total_return_pct"],      metrics_b["total_return_pct"],      metrics_c["total_return_pct"],      "{:.1f}%"),
        ("Max Drawdown",        metrics_a["max_drawdown_pct"],      metrics_b["max_drawdown_pct"],      metrics_c["max_drawdown_pct"],      "{:.2f}%"),
        ("Sharpe Ratio",        metrics_a["sharpe_ratio"],          metrics_b["sharpe_ratio"],          metrics_c["sharpe_ratio"],          "{:.3f}"),
        ("vs Buy & Hold",       metrics_a["vs_buy_hold_pct"],       metrics_b["vs_buy_hold_pct"],       metrics_c["vs_buy_hold_pct"],       "{:.1f}%"),
    ]

    for label, va, vb, vc, fmt in rows_out:
        print(f"  {label:<26} {fmt.format(va):>16} {fmt.format(vb):>16} {fmt.format(vc):>18}")

    print(sep)

    # ── Store results in DB ───────────────────────────────────────────────────
    conn2 = psycopg2.connect(DB_URL)
    cur2  = conn2.cursor()
    cur2.execute("DELETE FROM backtest_flip_results WHERE run_at::date = CURRENT_DATE")

    for strategy, metrics in [
        ("hold_jarvis",      metrics_a),
        ("flip_any",         metrics_b),
        ("flip_confirmed",   metrics_c),
    ]:
        cur2.execute("""
            INSERT INTO backtest_flip_results
              (strategy, universe_size, date_from, date_to,
               total_trades, win_rate, avg_return_pct, total_return_pct,
               max_drawdown_pct, sharpe_ratio, vs_buy_hold_pct, notes, metadata)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            strategy,
            len(tickers),
            date_from,
            date_to,
            metrics["total_trades"],
            round(metrics["win_rate"], 6),
            round(metrics["avg_return_pct"], 6),
            round(metrics["total_return_pct"], 4),
            round(metrics["max_drawdown_pct"], 6),
            round(metrics["sharpe_ratio"], 6),
            round(metrics["vs_buy_hold_pct"], 4),
            f"run {date.today()}",
            json.dumps({"bh_avg_pct": round(avg_bh, 4)}),
        ))

    conn2.commit()
    cur2.close()
    conn2.close()
    print(f"\n  Results stored in backtest_flip_results table.")


if __name__ == "__main__":
    main()
