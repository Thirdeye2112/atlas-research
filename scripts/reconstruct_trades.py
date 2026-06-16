#!/usr/bin/env python
"""
reconstruct_trades.py — Atlas Trade Attribution Engine v1, Part 1.

Reconstructs hypothetical trades from prediction_outcomes + raw_bars.
Computes MFE, MAE, stop/target detection, and writes to trade_attribution.

ANALYSIS ONLY. No trading. No signal changes. No model mutations.

Usage:
    python scripts/reconstruct_trades.py
    python scripts/reconstruct_trades.py --limit 50000
    python scripts/reconstruct_trades.py --start-date 2024-01-01
"""

from __future__ import annotations

import argparse
import sys
import os
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
PARQUET_DIR = Path("exports/parquet")
REPORT_PATH = Path("reports/TRADE_RECONSTRUCTION_REPORT.md")

# Exit strategy parameters
ATR_STOP_MULT    = 1.5   # stop at -1.5R
ATR_T1_MULT      = 1.0   # T1 at +1R
ATR_T2_MULT      = 2.0   # T2 at +2R
ATR_T3_MULT      = 3.0   # T3 at +3R

# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────

def load_predictions(engine, start_date=None, limit=None) -> pd.DataFrame:
    where = "WHERE po.predicted_direction != 0 AND po.actual_return_5d IS NOT NULL"
    if start_date:
        where += f" AND po.prediction_date >= '{start_date}'"

    limit_clause = f"LIMIT {limit}" if limit else ""

    sql = f"""
    SELECT
        po.ticker, po.prediction_date,
        po.predicted_direction, po.predicted_rank, po.predicted_prob,
        po.actual_return_5d, po.actual_return_10d, po.actual_return_20d,
        po.direction_correct_5d,
        po.jarvis_green, po.quality_tier, po.above_sma200,
        po.sector_regime, po.vix_regime,
        po.confluence_score, po.conviction_level, po.ml_signal_strength,
        p.calibrated_confidence
    FROM prediction_outcomes po
    LEFT JOIN predictions p
        ON p.ticker = po.ticker AND p.date = po.prediction_date
    {where}
    ORDER BY po.prediction_date, po.ticker
    {limit_clause}
    """
    df = pd.read_sql(sql, engine, parse_dates=["prediction_date"])
    df["prediction_date"] = pd.to_datetime(df["prediction_date"]).dt.date
    print(f"  Loaded {len(df):,} directional predictions")
    return df


def load_bars(engine, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Load OHLCV bars for all tickers, return dict: ticker → sorted DataFrame."""
    tickers_sql = "','".join(tickers)
    sql = f"""
    SELECT ticker, date::date AS date, adjusted_close, high, low
    FROM raw_bars
    WHERE ticker IN ('{tickers_sql}')
    ORDER BY ticker, date
    """
    print(f"  Loading raw_bars for {len(tickers):,} tickers...")
    t0 = time.time()
    all_bars = pd.read_sql(sql, engine)
    all_bars["date"] = pd.to_datetime(all_bars["date"]).dt.date
    print(f"  Loaded {len(all_bars):,} bar rows in {time.time()-t0:.1f}s")
    return {ticker: grp.reset_index(drop=True)
            for ticker, grp in all_bars.groupby("ticker")}


def load_atr(parquet_dir: Path, tickers: set[str]) -> pd.DataFrame:
    """Load atr_14 from all parquets; return indexed by (ticker, date)."""
    print("  Loading ATR from parquets...")
    frames = []
    for f in sorted(parquet_dir.glob("*.parquet")):
        df = pd.read_parquet(f, columns=["ticker", "date", "atr_14"])
        df = df[df["ticker"].isin(tickers)]
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["ticker", "date", "atr_14"])
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.drop_duplicates(subset=["ticker", "date"])
    print(f"  ATR rows: {len(out):,}")
    return out.set_index(["ticker", "date"])


def detect_signal_flips(preds: pd.DataFrame) -> set[tuple]:
    """Return set of (ticker, date) where the NEXT prediction changes direction."""
    preds_sorted = preds.sort_values(["ticker", "prediction_date"])
    shifted = preds_sorted.groupby("ticker")["predicted_direction"].shift(-1)
    flip_mask = (shifted != preds_sorted["predicted_direction"]) & shifted.notna()
    flips = preds_sorted[flip_mask]
    dates = flips["prediction_date"]
    if hasattr(dates.iloc[0] if len(dates) > 0 else None, "date"):
        dates = dates.dt.date
    return set(zip(flips["ticker"], dates))


# ──────────────────────────────────────────────────────────────────────────────
# Per-ticker vectorized reconstruction
# ──────────────────────────────────────────────────────────────────────────────

def compute_ticker_trades(
    ticker: str,
    ticker_preds: pd.DataFrame,
    bars: pd.DataFrame,
    atr_data: pd.DataFrame,
    flip_set: set[tuple],
) -> list[dict]:
    """Reconstruct trades for a single ticker using vectorized bar lookups."""
    if bars is None or len(bars) == 0:
        return []

    # Build date → bar-index map for O(1) lookups
    date_to_idx: dict = {d: i for i, d in enumerate(bars["date"])}

    ac    = bars["adjusted_close"].values
    highs = bars["high"].values
    lows  = bars["low"].values

    results = []
    for _, row in ticker_preds.iterrows():
        entry_date = row["prediction_date"].date() if hasattr(row["prediction_date"], "date") else pd.to_datetime(row["prediction_date"]).date()
        direction  = int(row["predicted_direction"])

        entry_idx = date_to_idx.get(entry_date)
        if entry_idx is None:
            continue

        entry_price = ac[entry_idx]
        if entry_price is None or np.isnan(entry_price) or entry_price <= 0:
            continue

        n = len(bars)

        # ── 5d / 10d / 20d windows ──────────────────────────────────────────
        def _window(days: int):
            s = entry_idx + 1
            e = min(entry_idx + days + 1, n)
            if s >= n:
                return None, None, None
            w_high = highs[s:e]
            w_low  = lows[s:e]
            exit_i = min(entry_idx + days, n - 1)
            return w_high, w_low, ac[exit_i]

        h5, l5, exit_p5   = _window(5)
        h10, l10, exit_p10 = _window(10)
        h20, l20, exit_p20 = _window(20)

        if h5 is None or len(h5) == 0:
            continue

        max_h5  = float(np.nanmax(h5))
        min_l5  = float(np.nanmin(l5))
        max_h20 = float(np.nanmax(h20)) if h20 is not None and len(h20) > 0 else np.nan
        min_l20 = float(np.nanmin(l20)) if l20 is not None and len(l20) > 0 else np.nan

        # ── MFE / MAE (5d window, directional) ─────────────────────────────
        if direction == 1:   # long
            mfe = (max_h5  - entry_price) / entry_price * 100
            mae = (entry_price - min_l5) / entry_price * 100
        else:                 # short
            mfe = (entry_price - min_l5) / entry_price * 100
            mae = (max_h5 - entry_price)  / entry_price * 100

        mfe = max(mfe, 0.0)
        mae = max(mae, 0.0)
        per_trade_pf = mfe / mae if mae > 1e-6 else np.nan

        # ── Returns (decimal × direction → pct) ────────────────────────────
        r5  = float(row["actual_return_5d"]) * direction * 100 if pd.notna(row["actual_return_5d"]) else np.nan
        r10 = float(row["actual_return_10d"]) * direction * 100 if pd.notna(row["actual_return_10d"]) else np.nan
        r20 = float(row["actual_return_20d"]) * direction * 100 if pd.notna(row["actual_return_20d"]) else np.nan

        exit_idx_5d = min(entry_idx + 5, n - 1)
        _exit_d = bars["date"].iloc[exit_idx_5d]
        exit_date = _exit_d.date() if hasattr(_exit_d, "date") else _exit_d
        exit_price  = float(exit_p5) if exit_p5 is not None and not np.isnan(exit_p5) else None

        # ── ATR stop / targets ──────────────────────────────────────────────
        atr_val  = np.nan
        atr_key  = (ticker, entry_date)
        if atr_key in atr_data.index:
            atr_val = float(atr_data.loc[atr_key, "atr_14"])

        atr_pct = atr_val / entry_price * 100 if not np.isnan(atr_val) else np.nan
        stop_pct = ATR_STOP_MULT * atr_pct if not np.isnan(atr_pct) else np.nan
        t1_pct   = ATR_T1_MULT  * atr_pct if not np.isnan(atr_pct) else np.nan
        t2_pct   = ATR_T2_MULT  * atr_pct if not np.isnan(atr_pct) else np.nan
        t3_pct   = ATR_T3_MULT  * atr_pct if not np.isnan(atr_pct) else np.nan

        stop_hit   = False
        t1_hit     = False
        t2_hit     = False
        t3_hit     = False
        atr_stop_ret = np.nan

        if not np.isnan(stop_pct):
            stop_price  = entry_price * (1 - stop_pct / 100) if direction == 1 else entry_price * (1 + stop_pct / 100)
            t1_price    = entry_price * (1 + t1_pct  / 100) if direction == 1 else entry_price * (1 - t1_pct  / 100)
            t2_price    = entry_price * (1 + t2_pct  / 100) if direction == 1 else entry_price * (1 - t2_pct  / 100)
            t3_price    = entry_price * (1 + t3_pct  / 100) if direction == 1 else entry_price * (1 - t3_pct  / 100)

            # Use 20d window for target checks (gives targets room to hit)
            check_h = max_h20 if not np.isnan(max_h20) else max_h5
            check_l = min_l20 if not np.isnan(min_l20) else min_l5

            if direction == 1:
                stop_hit = min_l5 <= stop_price
                t1_hit   = check_h >= t1_price
                t2_hit   = check_h >= t2_price
                t3_hit   = check_h >= t3_price
            else:
                stop_hit = max_h5 >= stop_price
                t1_hit   = check_l <= t1_price
                t2_hit   = check_l <= t2_price
                t3_hit   = check_l <= t3_price

            atr_stop_ret = -stop_pct if stop_hit else np.nan

        signal_flip = (ticker, entry_date) in flip_set

        results.append({
            "ticker":                   ticker,
            "entry_date":               entry_date,
            "exit_date":                exit_date,
            "entry_price":              round(entry_price, 4),
            "exit_price":               round(exit_price, 4) if exit_price else None,
            "return_pct":               round(r5,  4) if not np.isnan(r5)  else None,
            "return_pct_10d":           round(r10, 4) if not np.isnan(r10) else None,
            "return_pct_20d":           round(r20, 4) if not np.isnan(r20) else None,
            "holding_days":             5,
            "max_favorable_excursion":  round(mfe, 4),
            "max_adverse_excursion":    round(mae, 4),
            "profit_factor":            round(per_trade_pf, 4) if not np.isnan(per_trade_pf) else None,
            "exit_reason":              "5d_hold",
            "stop_hit":                 bool(stop_hit),
            "target1_hit":              bool(t1_hit),
            "target2_hit":              bool(t2_hit),
            "target3_hit":              bool(t3_hit),
            "signal_flip_exit":         bool(signal_flip),
            "time_exit":                True,
            "atr_stop_return_pct":      round(float(atr_stop_ret), 4) if not np.isnan(atr_stop_ret) else None,
            "atr_pct":                  round(float(atr_pct), 4) if not np.isnan(atr_pct) else None,
            "prediction_rank":          float(row["predicted_rank"]) if pd.notna(row["predicted_rank"]) else None,
            "prediction_prob":          float(row["predicted_prob"]) if pd.notna(row["predicted_prob"]) else None,
            "calibrated_confidence":    float(row["calibrated_confidence"]) if pd.notna(row.get("calibrated_confidence")) else None,
            "predicted_direction":      direction,
            "jarvis_green":             bool(row["jarvis_green"]) if pd.notna(row["jarvis_green"]) else None,
            "quality_tier":             int(row["quality_tier"]) if pd.notna(row["quality_tier"]) else None,
            "sector_regime":            str(row["sector_regime"]) if pd.notna(row["sector_regime"]) else None,
            "vix_regime":               str(row["vix_regime"]) if pd.notna(row["vix_regime"]) else None,
            "confluence_score":         float(row["confluence_score"]) if pd.notna(row["confluence_score"]) else None,
            "conviction_level":         str(row["conviction_level"]) if pd.notna(row["conviction_level"]) else None,
            "ml_signal_strength":       float(row["ml_signal_strength"]) if pd.notna(row["ml_signal_strength"]) else None,
        })

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Upsert
# ──────────────────────────────────────────────────────────────────────────────

def upsert_trades(trades: list[dict], engine, batch_size: int = 5000) -> int:
    if not trades:
        return 0
    df = pd.DataFrame(trades)

    INT_COLS = {"quality_tier", "predicted_direction", "holding_days"}

    cols = list(df.columns)
    values_clause = ", ".join([f":{c}" for c in cols])
    update_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c not in ("ticker", "entry_date")])
    sql = text(f"""
    INSERT INTO trade_attribution ({', '.join(cols)})
    VALUES ({values_clause})
    ON CONFLICT (ticker, entry_date) DO UPDATE SET {update_clause}
    """)
    total = 0
    for start in range(0, len(df), batch_size):
        chunk = df.iloc[start:start + batch_size]
        raw_rows = chunk.to_dict(orient="records")
        rows = []
        for row in raw_rows:
            clean = {}
            for k, v in row.items():
                if isinstance(v, float) and v != v:  # float NaN
                    clean[k] = None
                elif k in INT_COLS:
                    clean[k] = None if (v is None) else int(v)
                elif hasattr(v, "item"):  # numpy scalar -> Python scalar
                    clean[k] = v.item()
                else:
                    clean[k] = v
            rows.append(clean)
        with engine.begin() as conn:
            conn.execute(sql, rows)
        total += len(rows)
    return total


# ──────────────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────────────

def build_report(trades: pd.DataFrame, as_of: str) -> str:
    total = len(trades)
    wins  = (trades["return_pct"] > 0).sum()
    losses = (trades["return_pct"] < 0).sum()
    wr    = wins / total * 100 if total > 0 else 0
    avg_w = trades.loc[trades["return_pct"] > 0, "return_pct"].mean()
    avg_l = trades.loc[trades["return_pct"] < 0, "return_pct"].mean()
    exp   = trades["return_pct"].mean()

    sum_w = trades.loc[trades["return_pct"] > 0, "return_pct"].sum()
    sum_l = abs(trades.loc[trades["return_pct"] < 0, "return_pct"].sum())
    pf    = sum_w / sum_l if sum_l > 0 else float("inf")

    longs  = trades[trades["predicted_direction"] ==  1]
    shorts = trades[trades["predicted_direction"] == -1]

    stop_n   = trades["stop_hit"].sum()
    t1_n     = trades["target1_hit"].sum()
    t2_n     = trades["target2_hit"].sum()
    t3_n     = trades["target3_hit"].sum()
    flip_n   = trades["signal_flip_exit"].sum()

    avg_mfe = trades["max_favorable_excursion"].mean()
    avg_mae = trades["max_adverse_excursion"].mean()

    by_tier = []
    for tier in [1, 2, 3, 4]:
        g = trades[trades["quality_tier"] == tier]
        if len(g) > 0:
            g_wr = (g["return_pct"] > 0).mean() * 100
            g_exp = g["return_pct"].mean()
            by_tier.append(f"| Tier {tier} | {len(g):,} | {g_wr:.1f}% | {g_exp:+.2f}% |")

    by_conv = []
    for cv in ["VERY_HIGH", "HIGH", "MEDIUM", "LOW"]:
        g = trades[trades["conviction_level"] == cv]
        if len(g) > 0:
            g_wr = (g["return_pct"] > 0).mean() * 100
            g_exp = g["return_pct"].mean()
            by_conv.append(f"| {cv} | {len(g):,} | {g_wr:.1f}% | {g_exp:+.2f}% |")

    by_regime = []
    for reg in ["bull", "bear", "range"]:
        g = trades[trades["sector_regime"] == reg]
        if len(g) > 0:
            g_wr = (g["return_pct"] > 0).mean() * 100
            g_exp = g["return_pct"].mean()
            by_regime.append(f"| {reg.title()} | {len(g):,} | {g_wr:.1f}% | {g_exp:+.2f}% |")

    # 10d vs 20d
    r10 = trades["return_pct_10d"].dropna()
    r20 = trades["return_pct_20d"].dropna()
    wr10 = (r10 > 0).mean() * 100
    wr20 = (r20 > 0).mean() * 100
    exp10 = r10.mean()
    exp20 = r20.mean()
    pf10 = r10[r10 > 0].sum() / abs(r10[r10 < 0].sum()) if (r10 < 0).sum() > 0 else np.nan
    pf20 = r20[r20 > 0].sum() / abs(r20[r20 < 0].sum()) if (r20 < 0).sum() > 0 else np.nan

    lines = [
        f"# Trade Reconstruction Report",
        f"",
        f"**Generated:** {as_of}  ",
        f"**Source:** `prediction_outcomes` + `raw_bars` (5d hold, directionally adjusted)  ",
        f"**Status:** ANALYSIS ONLY — no trades executed, no signals altered.",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|---|---|",
        f"| Total reconstructed trades | {total:,} |",
        f"| Date range | {trades['entry_date'].min()} → {trades['entry_date'].max()} |",
        f"| Unique tickers | {trades['ticker'].nunique():,} |",
        f"| Long trades | {len(longs):,} ({len(longs)/total*100:.0f}%) |",
        f"| Short trades | {len(shorts):,} ({len(shorts)/total*100:.0f}%) |",
        f"| Win rate (5d) | **{wr:.1f}%** |",
        f"| Expectancy (5d) | **{exp:+.3f}%** |",
        f"| Profit factor (5d) | **{pf:.3f}** |",
        f"| Avg winner | {avg_w:+.3f}% |",
        f"| Avg loser | {avg_l:+.3f}% |",
        f"| Avg MFE | {avg_mfe:.3f}% |",
        f"| Avg MAE | {avg_mae:.3f}% |",
        f"| Stops triggered | {stop_n:,} ({stop_n/total*100:.1f}%) |",
        f"| T1 reached (1R) | {t1_n:,} ({t1_n/total*100:.1f}%) |",
        f"| T2 reached (2R) | {t2_n:,} ({t2_n/total*100:.1f}%) |",
        f"| T3 reached (3R) | {t3_n:,} ({t3_n/total*100:.1f}%) |",
        f"| Signal flip exits | {flip_n:,} ({flip_n/total*100:.1f}%) |",
        f"",
        f"---",
        f"",
        f"## Hold Period Comparison",
        f"",
        f"| Hold Period | N | Win Rate | Expectancy | Profit Factor |",
        f"|---|---|---|---|---|",
        f"| 5d (base) | {total:,} | {wr:.1f}% | {exp:+.3f}% | {pf:.3f} |",
        f"| 10d | {len(r10):,} | {wr10:.1f}% | {exp10:+.3f}% | {pf10:.3f} |",
        f"| 20d | {len(r20):,} | {wr20:.1f}% | {exp20:+.3f}% | {pf20:.3f} |",
        f"",
        f"---",
        f"",
        f"## By Quality Tier",
        f"",
        f"| Tier | N | Win Rate | Expectancy |",
        f"|---|---|---|---|",
    ] + by_tier + [
        f"",
        f"## By Conviction Level",
        f"",
        f"| Conviction | N | Win Rate | Expectancy |",
        f"|---|---|---|---|",
    ] + by_conv + [
        f"",
        f"## By Sector Regime",
        f"",
        f"| Regime | N | Win Rate | Expectancy |",
        f"|---|---|---|---|",
    ] + by_regime + [
        f"",
        f"---",
        f"",
        f"## Key Findings",
        f"",
    ]

    best_tier = max(by_tier, key=lambda l: float(l.split("|")[3].strip().replace("%","").replace("+",""))) if by_tier else ""
    worst_tier = min(by_tier, key=lambda l: float(l.split("|")[3].strip().replace("%","").replace("+",""))) if by_tier else ""

    lines += [
        f"1. **Expectancy**: {exp:+.3f}% per trade — {'positive edge exists' if exp > 0 else 'NEGATIVE edge — review urgently'}",
        f"2. **Profit factor {pf:.3f}**: {'above 1.0 — system earns more on winners than it loses on losers' if pf > 1 else 'below 1.0 — losses outweigh gains'}",
        f"3. **MFE/MAE ratio**: {avg_mfe/avg_mae:.2f}x on average — trades move {avg_mfe:.2f}% favorably vs {avg_mae:.2f}% adversely",
        f"4. **Stop rate {stop_n/total*100:.1f}%**: ATR-based stops ({ATR_STOP_MULT}R) triggered on {stop_n:,} trades",
        f"5. **T1 hit rate {t1_n/total*100:.1f}%**: {ATR_T1_MULT}R targets reached on {t1_n:,} trades — {'solid target reach rate' if t1_n/total > 0.3 else 'low target reach rate'}",
        f"6. **Signal flips**: {flip_n:,} trades had direction reverse within next prediction cycle",
        f"",
        f"---",
        f"",
        f"*Run `python scripts/analyze_expectancy.py` for detailed context slicing, exit study, and discovery questions.*",
    ]

    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=None, help="Only reconstruct trades from this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows for testing")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    as_of  = datetime.now().strftime("%Y-%m-%d %H:%M")
    t_start = time.time()

    print("\n=== Atlas Trade Reconstruction ===")
    print(f"As-of: {as_of}")
    if args.start_date:
        print(f"Start date: {args.start_date}")
    if args.limit:
        print(f"Row limit: {args.limit:,}")

    # 1. Load predictions
    print("\n[1/5] Loading prediction_outcomes...")
    preds = load_predictions(engine, start_date=args.start_date, limit=args.limit)
    if preds.empty:
        print("No directional predictions found.")
        return

    tickers = preds["ticker"].unique().tolist()

    # 2. Load bars
    print(f"\n[2/5] Loading raw_bars for {len(tickers):,} tickers...")
    bars_by_ticker = load_bars(engine, tickers)

    # 3. Load ATR
    print("\n[3/5] Loading ATR from parquets...")
    ticker_set = set(tickers)
    atr_data = load_atr(PARQUET_DIR, ticker_set)

    # 4. Detect signal flips
    print("\n[4/5] Detecting signal flips...")
    flip_set = detect_signal_flips(preds)
    print(f"  Signal flips: {len(flip_set):,}")

    # 5. Reconstruct ticker by ticker
    print(f"\n[5/5] Reconstructing {len(preds):,} trades...")
    all_trades = []
    processed = 0
    skipped = 0
    for ticker, group in preds.groupby("ticker"):
        bars = bars_by_ticker.get(ticker)
        rows = compute_ticker_trades(ticker, group, bars, atr_data, flip_set)
        all_trades.extend(rows)
        processed += 1
        if processed % 200 == 0:
            print(f"  {processed:,}/{len(tickers):,} tickers, {len(all_trades):,} trades...")

    print(f"  Reconstructed {len(all_trades):,} trades ({skipped} skipped)")

    # Upsert
    print("\nUpserting to trade_attribution...")
    n = upsert_trades(all_trades, engine)
    print(f"  Wrote {n:,} rows")

    # Report
    print("\nGenerating report...")
    REPORT_PATH.parent.mkdir(exist_ok=True)
    trades_df = pd.DataFrame(all_trades)
    report_text = build_report(trades_df, as_of)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"  Report -> {REPORT_PATH}")

    elapsed = time.time() - t_start
    print(f"\nDone in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
