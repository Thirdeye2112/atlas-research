#!/usr/bin/env python
"""
run_pattern_fulfillment_measurement.py
=========================================
ATLAS-RESEARCH pattern-fulfillment backtest. MEASURE & REPORT ONLY -- not a
predictor, not a trading signal. See reports/research/PATTERN_FULFILLMENT_REPORT.md.

Usage (cwd = C:\\Atlas\\atlas-research, the main checkout):
    .venv\\Scripts\\python.exe \
        C:\\Atlas\\atlas-research-pattern-fulfillment\\scripts\\research\\run_pattern_fulfillment_measurement.py \
        [--no-db-write] [--limit-rows N] [--tickers AAPL,NKE,INTC]

Writes:
    - research_pattern_fulfillment table
    - reports/research/pattern_fulfillment_run_log.jsonl
    - reports/research/pattern_fulfillment_summary.json
"""
from __future__ import annotations

import argparse
import gc
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values

from pattern_fulfillment_common import (
    TICKERS, STAGE_WINDOW, R_MULTIPLES, ATR_STOP_MULT, TRAIN_FRACTION, MIN_CELL_N,
    BH_FDR_Q, DATABASE_URL, Candidate, stage_a_scan, r_bracket_outcome,
    baseline_outcomes, expectancy_stats, welch_t_pvalue, bh_fdr, walk_forward_split_mask,
)
from pattern_fulfillment_candlesticks import build_candlestick_candidates
from pattern_fulfillment_chartpatterns import build_chartpattern_candidates
from pattern_fulfillment_channels import build_channel_candidates
from pattern_fulfillment_indicators import (
    build_macd_candidates, build_rsi_candidates, build_vwap_candidates,
    build_omni82_candidates, build_oscar87_candidates, build_sma_stack_candidates,
)
from pattern_fulfillment_gaps import build_classic_gap_candidates, build_fvg_candidates
from pattern_fulfillment_supplemental import build_supplemental_candidates

from atlas_research.intraday.features import compute_features

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

# Patterns with a codeable inversion (invalidation_becomes), per pattern_reference,
# MINUS hs_top (source text itself disclaims a clean signal -- see report).
INVERSION_PATTERNS = {
    "channel_ascending", "channel_break", "channel_descending", "channel_horizontal",
    "marubozu", "classic_gap_down", "classic_gap_up", "fvg_bearish", "fvg_bullish",
    "omni_82", "sma_stack", "bear_flag", "bull_flag", "three_black_crows",
    "three_white_soldiers", "bearish_engulfing", "bullish_engulfing",
    "double_bottom", "double_top", "tweezer_bottom", "tweezer_top",
}

# Patterns excluded from the whole Step 2/3/4 framework: no self-contained
# direction/confirm/invalidate per pattern_reference's own text.
CONTEXT_ONLY_EXCLUDED = {"adx", "atr", "swing_leg", "volume_ratio"}

INSERT_COLS = [
    "run_id", "pattern_type", "ticker", "timeframe", "instance_ts", "direction",
    "stage_a_outcome", "stage_a_event_ts",
    "outcome_b", "max_r_b", "realized_r_b",
    "inversion_tested", "inversion_direction", "outcome_c", "max_r_c", "realized_r_c",
    "in_sample_flag",
]


def get_git_info() -> dict:
    def _git(*args):
        try:
            return subprocess.check_output(["git", *args], cwd=str(WORKTREE_ROOT), text=True).strip()
        except Exception as exc:
            return f"<unavailable: {exc}>"
    return {"commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD")}


def load_5m_bars(engine, ticker: str) -> pd.DataFrame:
    df = pd.read_sql(
        text("SELECT ticker, ts, open, high, low, close, volume FROM intraday_bars "
             "WHERE ticker = :t AND timeframe = '5m' ORDER BY ts"),
        engine, params={"t": ticker},
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.reset_index(drop=True)


def load_daily_bars(engine, ticker: str) -> pd.DataFrame:
    df = pd.read_sql(
        text("SELECT ticker, date, open, high, low, close, volume FROM raw_bars "
             "WHERE ticker = :t ORDER BY date"),
        engine, params={"t": ticker},
    )
    df["ts"] = pd.to_datetime(df["date"], utc=True)
    return df.reset_index(drop=True)


def _atr14(high, low, close, period=14):
    close_s = pd.Series(close)
    prev_close = close_s.shift(1)
    high_s, low_s = pd.Series(high), pd.Series(low)
    tr = pd.concat([
        high_s - low_s, (high_s - prev_close).abs(), (low_s - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean().to_numpy()


def _resolve_direction(cand: Candidate, t_event, resolved_dir):
    return resolved_dir if resolved_dir is not None else cand.direction


def process_instances(candidates: list[Candidate], ticker: str, timeframe: str,
                       high, low, close, atr, ts_vals, n: int, in_sample_full: np.ndarray) -> list[dict]:
    window = STAGE_WINDOW[timeframe]
    rows = []
    for cand in candidates:
        if cand.idx >= n:
            continue
        stage_a_out, t_event, resolved_dir = stage_a_scan(cand, close, window)
        direction = _resolve_direction(cand, t_event, resolved_dir)

        row = {
            "pattern_type": cand.pattern_type, "ticker": ticker, "timeframe": timeframe,
            "instance_ts": ts_vals[cand.idx], "direction": direction,
            "stage_a_outcome": stage_a_out,
            "stage_a_event_ts": ts_vals[t_event] if t_event is not None else None,
            "outcome_b": None, "max_r_b": None, "realized_r_b": None,
            "inversion_tested": False, "inversion_direction": None,
            "outcome_c": None, "max_r_c": None, "realized_r_c": None,
            "in_sample_flag": bool(in_sample_full[cand.idx]),
        }

        if stage_a_out == "CONFIRMED" and direction in ("long", "short") and t_event is not None:
            entry = close[t_event]
            atr_t = atr[t_event]
            res_b = r_bracket_outcome(direction, entry, atr_t, high, low, close, t_event, window)
            row["outcome_b"] = res_b["outcome"]
            row["max_r_b"] = res_b["max_r"]
            row["realized_r_b"] = res_b["realized_R"]

        if stage_a_out == "INVALIDATED" and cand.pattern_type in INVERSION_PATTERNS and t_event is not None:
            base_dir = direction if direction in ("long", "short") else cand.direction
            if base_dir in ("long", "short"):
                inv_dir = "short" if base_dir == "long" else "long"
                entry = close[t_event]
                atr_t = atr[t_event]
                res_c = r_bracket_outcome(inv_dir, entry, atr_t, high, low, close, t_event, window)
                row["inversion_tested"] = True
                row["inversion_direction"] = inv_dir
                row["outcome_c"] = res_c["outcome"]
                row["max_r_c"] = res_c["max_r"]
                row["realized_r_c"] = res_c["realized_R"]

        rows.append(row)
    return rows


def build_all_candidates_5m(feat_df: pd.DataFrame, ticker: str) -> list[Candidate]:
    o = feat_df["open"].to_numpy(float); h = feat_df["high"].to_numpy(float)
    l = feat_df["low"].to_numpy(float); c = feat_df["close"].to_numpy(float)
    window = STAGE_WINDOW["5m"]
    out = []
    out += build_candlestick_candidates(o, h, l, c, ticker, "5m")
    out += build_macd_candidates(feat_df, ticker)
    out += build_rsi_candidates(feat_df, ticker, window)
    out += build_vwap_candidates(feat_df, ticker)
    out += build_fvg_candidates(h, l, c, ticker, "5m", window)
    out += build_supplemental_candidates(o, h, l, c, ticker, "5m")
    return out


def build_all_candidates_daily(bars: pd.DataFrame, ticker: str) -> list[Candidate]:
    o = bars["open"].to_numpy(float); h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float); c = bars["close"].to_numpy(float)
    window = STAGE_WINDOW["daily"]
    out = []
    out += build_candlestick_candidates(o, h, l, c, ticker, "daily")
    out += build_chartpattern_candidates(h, l, c, ticker, "daily")
    out += build_channel_candidates(h, l, c, ticker, "daily", window)
    out += build_omni82_candidates(h, l, c, o, ticker)
    out += build_oscar87_candidates(h, l, c, ticker)
    out += build_sma_stack_candidates(c, ticker)
    out += build_classic_gap_candidates(o, h, l, c, ticker)
    out += build_supplemental_candidates(o, h, l, c, ticker, "daily")
    return out


def _clean(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    return v


def build_records(rows: list[dict], run_id: str) -> list[tuple]:
    recs = []
    for r in rows:
        recs.append((
            run_id, r["pattern_type"], r["ticker"], r["timeframe"],
            pd.Timestamp(r["instance_ts"]).to_pydatetime(), _clean(r["direction"]),
            r["stage_a_outcome"],
            pd.Timestamp(r["stage_a_event_ts"]).to_pydatetime() if r["stage_a_event_ts"] is not None else None,
            _clean(r["outcome_b"]),
            None if r["max_r_b"] is None else int(r["max_r_b"]),
            _clean(r["realized_r_b"]),
            bool(r["inversion_tested"]), _clean(r["inversion_direction"]),
            _clean(r["outcome_c"]),
            None if r["max_r_c"] is None else int(r["max_r_c"]),
            _clean(r["realized_r_c"]),
            bool(r["in_sample_flag"]),
        ))
    return recs


def write_rows(engine, rows: list[dict], run_id: str) -> int:
    if not rows:
        return 0
    records = build_records(rows, run_id)
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        sql = f"INSERT INTO research_pattern_fulfillment ({', '.join(INSERT_COLS)}) VALUES %s"
        execute_values(cur, sql, records, page_size=10000)
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(records)


def process_ticker_timeframe(engine, ticker: str, timeframe: str, run_id: str,
                              do_write: bool, limit_rows: int | None) -> tuple[list[dict], dict]:
    t0 = time.time()
    if timeframe == "5m":
        bars = load_5m_bars(engine, ticker)
        if limit_rows:
            bars = bars.iloc[-limit_rows:].reset_index(drop=True)
        feat_df = compute_features(bars)
        h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
        c = feat_df["close"].to_numpy(float)
        atr = feat_df["atr14"].to_numpy(float)
        ts_vals = feat_df["ts"].to_numpy()
        n = len(feat_df)
        candidates = build_all_candidates_5m(feat_df, ticker)
    else:
        bars = load_daily_bars(engine, ticker)
        if limit_rows:
            bars = bars.iloc[-limit_rows:].reset_index(drop=True)
        h = bars["high"].to_numpy(float); l = bars["low"].to_numpy(float)
        c = bars["close"].to_numpy(float)
        atr = _atr14(h, l, c)
        ts_vals = bars["ts"].to_numpy()
        n = len(bars)
        candidates = build_all_candidates_daily(bars, ticker)

    in_sample_full = walk_forward_split_mask(n, TRAIN_FRACTION)
    rows = process_instances(candidates, ticker, timeframe, h, l, c, atr, ts_vals, n, in_sample_full)

    if do_write and rows:
        write_rows(engine, rows, run_id)

    meta = {
        "ticker": ticker, "timeframe": timeframe, "n_bars": n,
        "n_candidates": len(candidates), "n_rows": len(rows),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    return rows, meta


def process_baseline(engine, ticker: str, timeframe: str, run_id: str, do_write: bool,
                      limit_rows: int | None) -> dict:
    t0 = time.time()
    if timeframe == "5m":
        bars = load_5m_bars(engine, ticker)
        if limit_rows:
            bars = bars.iloc[-limit_rows:].reset_index(drop=True)
        feat_df = compute_features(bars)
        h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
        c = feat_df["close"].to_numpy(float)
        atr = feat_df["atr14"].to_numpy(float)
        ts_vals = feat_df["ts"].to_numpy()
        n = len(feat_df)
        valid = ~np.isnan(atr)
        sample_every = 5
    else:
        bars = load_daily_bars(engine, ticker)
        if limit_rows:
            bars = bars.iloc[-limit_rows:].reset_index(drop=True)
        h = bars["high"].to_numpy(float); l = bars["low"].to_numpy(float)
        c = bars["close"].to_numpy(float)
        atr = _atr14(h, l, c)
        ts_vals = bars["ts"].to_numpy()
        n = len(bars)
        valid = ~np.isnan(atr)
        sample_every = 1

    in_sample_full = walk_forward_split_mask(n, TRAIN_FRACTION)
    window = STAGE_WINDOW[timeframe]
    bdf = baseline_outcomes(ticker, timeframe, n, atr, h, l, c, window, valid, sample_every=sample_every)

    rows = []
    for _, r in bdf.iterrows():
        i0 = int(r["idx"])
        rows.append({
            "pattern_type": "__BASELINE__", "ticker": ticker, "timeframe": timeframe,
            "instance_ts": ts_vals[i0], "direction": r["direction"],
            "stage_a_outcome": "CONFIRMED", "stage_a_event_ts": ts_vals[i0],
            "outcome_b": r["outcome"], "max_r_b": r["max_r"], "realized_r_b": r["realized_R"],
            "inversion_tested": False, "inversion_direction": None,
            "outcome_c": None, "max_r_c": None, "realized_r_c": None,
            "in_sample_flag": bool(in_sample_full[i0]),
        })

    if do_write and rows:
        write_rows(engine, rows, run_id)

    return {"rows": rows, "meta": {"ticker": ticker, "timeframe": timeframe,
                                    "n_baseline": len(rows), "elapsed_sec": round(time.time() - t0, 2)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db-write", action="store_true")
    ap.add_argument("--limit-rows", type=int, default=None)
    ap.add_argument("--tickers", default=",".join(TICKERS))
    ap.add_argument("--timeframes", default="5m,daily")
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git_info = get_git_info()

    print(f"[run_id={run_id}] tickers={tickers} timeframes={timeframes} "
          f"db_write={not args.no_db_write} git={git_info}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    t_start = time.time()
    all_meta = []
    all_rows = []
    for ticker in tickers:
        for timeframe in timeframes:
            print(f"  -- {ticker} {timeframe} ...")
            rows, meta = process_ticker_timeframe(engine, ticker, timeframe, run_id,
                                                    do_write=not args.no_db_write, limit_rows=args.limit_rows)
            all_meta.append(meta)
            all_rows.extend(rows)
            print(f"     {meta}")
            bmeta = process_baseline(engine, ticker, timeframe, run_id,
                                      do_write=not args.no_db_write, limit_rows=args.limit_rows)
            print(f"     baseline: {bmeta['meta']}")
            all_meta.append({"baseline": True, **bmeta["meta"]})
            del rows
            gc.collect()

    total_elapsed = round(time.time() - t_start, 1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_record = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_info,
        "tickers": tickers,
        "timeframes": timeframes,
        "stage_window": STAGE_WINDOW,
        "r_multiples": R_MULTIPLES,
        "atr_stop_mult": ATR_STOP_MULT,
        "train_fraction": TRAIN_FRACTION,
        "min_cell_n": MIN_CELL_N,
        "bh_fdr_q": BH_FDR_Q,
        "inversion_patterns": sorted(INVERSION_PATTERNS),
        "context_only_excluded": sorted(CONTEXT_ONLY_EXCLUDED),
        "per_ticker_timeframe_meta": all_meta,
        "db_write": not args.no_db_write,
        "limit_rows": args.limit_rows,
        "total_elapsed_sec": total_elapsed,
        "total_rows": len(all_rows),
    }

    log_path = REPORTS_DIR / "pattern_fulfillment_run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record, default=str) + "\n")
    print(f"[run log] appended to {log_path}")

    print(f"\nDone. total_elapsed={total_elapsed}s total_rows={len(all_rows)}")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
