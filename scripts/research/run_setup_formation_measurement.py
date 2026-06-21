#!/usr/bin/env python
"""
run_setup_formation_measurement.py
====================================
ATLAS-RESEARCH setup-formation measurement (5m, N-window sweep).
MEASURE & REPORT ONLY -- this is a foundation measurement, not a predictor
and not a trading signal. See reports/research/SETUP_FORMATION_REPORT.md.

Usage (run with cwd = C:\\Atlas\\atlas-research, the main checkout, so the
real .env is discoverable -- see setup_formation_common.py for why):

    C:\\Atlas\\atlas-research\\.venv\\Scripts\\python.exe \
        C:\\Atlas\\atlas-research-setup-formation\\scripts\\research\\run_setup_formation_measurement.py \
        [--no-db-write] [--limit-rows N]

Writes:
    - research_setup_formation table (one row per ticker, n_window, decision_ts, forward_k)
    - reports/research/setup_formation_run_log.jsonl  (append one record per run)
    - reports/research/SETUP_FORMATION_REPORT.md       (overwritten each run)
    - reports/research/setup_formation_summary.json    (raw aggregates, for the chart script / re-reporting)
"""
from __future__ import annotations

import argparse
import gc
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values

import setup_formation_common as cfg
from setup_formation_common import (
    TICKERS, N_VALUES, K_VALUES, MAX_K, DATABASE_URL,
    FLAT_RANGE_ATR_MULT, FLAT_VOL_RATIO_MAX, GEOM_BODY_PCT_MIN, GEOM_SIZE_ATR_MULT,
    SR_NEAR_TOL, ATR_HIT_MULT, FORWARD_RETURN_FLAT_EPS, TRAIN_FRACTION, MIN_CELL_N,
    load_intraday_bars, load_daily_pattern_context, attach_daily_context,
    vectorized_daily_loc, build_pattern_lookup, classify_window_state,
)
from setup_formation_outcomes import compute_forward_outcomes, hit_target_for
from atlas_research.intraday.features import compute_features

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

INSERT_COLS = [
    "ticker", "n_window", "decision_ts", "setup_state", "setup_type", "direction",
    "daily_trend", "daily_market_trend", "daily_loc", "daily_context",
    "forward_k", "forward_return", "forward_direction", "hit_target",
    "in_sample_flag", "run_id",
]


# ---------------------------------------------------------------------------
# Reproducibility metadata
# ---------------------------------------------------------------------------

def get_git_info() -> dict:
    def _git(*args):
        try:
            return subprocess.check_output(
                ["git", *args], cwd=str(WORKTREE_ROOT), text=True
            ).strip()
        except Exception as exc:
            return f"<unavailable: {exc}>"
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
    }


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------

def _clean_obj(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    return v


def build_records(df: pd.DataFrame) -> list:
    d = df[INSERT_COLS]
    arrays = {}
    arrays["ticker"] = [_clean_obj(v) for v in d["ticker"].tolist()]
    arrays["n_window"] = d["n_window"].astype(int).tolist()
    arrays["decision_ts"] = pd.to_datetime(d["decision_ts"], utc=True).dt.to_pydatetime().tolist()
    arrays["setup_state"] = [_clean_obj(v) for v in d["setup_state"].tolist()]
    arrays["setup_type"] = [_clean_obj(v) for v in d["setup_type"].tolist()]
    arrays["direction"] = [_clean_obj(v) for v in d["direction"].tolist()]
    arrays["daily_trend"] = [_clean_obj(v) for v in d["daily_trend"].tolist()]
    arrays["daily_market_trend"] = [_clean_obj(v) for v in d["daily_market_trend"].tolist()]
    arrays["daily_loc"] = [_clean_obj(v) for v in d["daily_loc"].tolist()]
    arrays["daily_context"] = [_clean_obj(v) for v in d["daily_context"].tolist()]
    arrays["forward_k"] = d["forward_k"].astype(int).tolist()
    arrays["forward_return"] = [
        None if (v is None or (isinstance(v, float) and np.isnan(v))) else float(v)
        for v in d["forward_return"].tolist()
    ]
    arrays["forward_direction"] = [_clean_obj(v) for v in d["forward_direction"].tolist()]
    arrays["hit_target"] = [None if v is None else bool(v) for v in d["hit_target"].tolist()]
    arrays["in_sample_flag"] = d["in_sample_flag"].astype(bool).tolist()
    arrays["run_id"] = [_clean_obj(v) for v in d["run_id"].tolist()]

    return list(zip(*[arrays[c] for c in INSERT_COLS]))


def write_rows(engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    records = build_records(df)
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        sql = f"INSERT INTO research_setup_formation ({', '.join(INSERT_COLS)}) VALUES %s"
        execute_values(cur, sql, records, page_size=10000)
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(records)


# ---------------------------------------------------------------------------
# Aggregation helpers (built from in-memory per-ticker frames, not re-queried)
# ---------------------------------------------------------------------------

def _ci95_mean(x: pd.Series) -> tuple[float, float, float, int]:
    x = x.dropna()
    n = len(x)
    if n == 0:
        return (np.nan, np.nan, np.nan, 0)
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return (m, m - 1.96 * se, m + 1.96 * se, n)


def _ci95_rate(x: pd.Series) -> tuple[float, float, float, int]:
    x = x.dropna()
    n = len(x)
    if n == 0:
        return (np.nan, np.nan, np.nan, 0)
    p = x.mean()
    se = np.sqrt(p * (1 - p) / n) if n > 0 else np.nan
    return (p, max(0.0, p - 1.96 * se), min(1.0, p + 1.96 * se), n)


def summarize_ticker(ticker: str, df: pd.DataFrame) -> dict:
    """Build all aggregates needed for the report from one ticker's full
    long-format frame (all N, all K, all states)."""
    summary = {"ticker": ticker, "by_n": {}}

    for n_window, g in df.groupby("n_window"):
        # state frequency uses k=1 rows only (one row per decision point at k=1)
        g1 = g[g["forward_k"] == K_VALUES[0]]
        state_counts = {}
        for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
            sub = g1[g1["in_sample_flag"] == sample_flag]
            total = len(sub)
            counts = sub["setup_state"].value_counts().to_dict()
            state_counts[label] = {
                "total": total,
                "SETUP_FORMING": counts.get("SETUP_FORMING", 0),
                "NEUTRAL": counts.get("NEUTRAL", 0),
                "FLAT": counts.get("FLAT", 0),
            }

        setup_type_counts = (
            g1[g1["setup_state"] == "SETUP_FORMING"]["setup_type"]
            .value_counts().to_dict()
        )

        curves = {}
        for state_label, state_filter in (
            ("SETUP_FORMING", g["setup_state"] == "SETUP_FORMING"),
            ("NEUTRAL_FLAT", g["setup_state"] != "SETUP_FORMING"),
            ("ALL", pd.Series(True, index=g.index)),
        ):
            curves[state_label] = {}
            for k, gk in g[state_filter].groupby("forward_k"):
                row = {}
                for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
                    sub = gk[gk["in_sample_flag"] == sample_flag]
                    ret_m, ret_lo, ret_hi, ret_n = _ci95_mean(sub["forward_return"])
                    hit_series = sub["hit_target"].dropna().astype(bool) if sub["hit_target"].notna().any() else pd.Series(dtype=float)
                    hit_m, hit_lo, hit_hi, hit_n = _ci95_rate(hit_series)
                    row[label] = {
                        "n": ret_n,
                        "mean_return": ret_m, "ci_lo": ret_lo, "ci_hi": ret_hi,
                        "hit_rate": hit_m, "hit_ci_lo": hit_lo, "hit_ci_hi": hit_hi, "hit_n": hit_n,
                    }
                curves[state_label][int(k)] = row

        # (setup-forming x daily_context) cells, k=1..5
        ctx_cells = {}
        sf = g[g["setup_state"] == "SETUP_FORMING"]
        for (ctx, k), gk in sf.groupby(["daily_context", "forward_k"]):
            row = {}
            for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
                sub = gk[gk["in_sample_flag"] == sample_flag]
                ret_m, ret_lo, ret_hi, ret_n = _ci95_mean(sub["forward_return"])
                row[label] = {"n": ret_n, "mean_return": ret_m, "ci_lo": ret_lo, "ci_hi": ret_hi}
            ctx_cells.setdefault(ctx, {})[int(k)] = row

        summary["by_n"][int(n_window)] = {
            "state_counts": state_counts,
            "setup_type_counts": setup_type_counts,
            "curves": curves,
            "context_cells": ctx_cells,
        }

    return summary


# ---------------------------------------------------------------------------
# Per-ticker pipeline
# ---------------------------------------------------------------------------

def process_ticker(engine, ticker: str, run_id: str, do_write: bool, limit_rows: int | None) -> tuple[dict, dict]:
    t0 = time.time()
    bars = load_intraday_bars(engine, ticker)
    n_bars = len(bars)
    if limit_rows:
        bars = bars.iloc[-limit_rows:].reset_index(drop=True)
        n_bars = len(bars)

    feat_df = compute_features(bars)

    daily_ctx = load_daily_pattern_context(engine, ticker)
    feat_df = attach_daily_context(feat_df, daily_ctx)
    feat_df["daily_loc"] = vectorized_daily_loc(
        feat_df["daily_dist_support"].to_numpy(), feat_df["daily_dist_resistance"].to_numpy()
    )
    feat_df["daily_trend"] = feat_df["daily_trend"].where(feat_df["daily_trend"].notna(), "unknown")
    feat_df["daily_market_trend"] = feat_df["daily_market_trend"].where(feat_df["daily_market_trend"].notna(), "unknown")
    feat_df["daily_context"] = (
        feat_df["daily_trend"].astype(str) + "/" + feat_df["daily_loc"].astype(str)
        + "/mkt_" + feat_df["daily_market_trend"].astype(str)
    )

    o = feat_df["open"].to_numpy(float); h = feat_df["high"].to_numpy(float)
    lo = feat_df["low"].to_numpy(float); c = feat_df["close"].to_numpy(float)
    pattern_lookup = build_pattern_lookup(o, h, lo, c)

    fwd = compute_forward_outcomes(feat_df)
    atr14 = feat_df["atr14"].to_numpy(float)
    close = feat_df["close"].to_numpy(float)
    ts_vals = feat_df["ts"].to_numpy()

    n = len(feat_df)
    split_idx = int(n * TRAIN_FRACTION)
    in_sample_flag_full = np.arange(n) < split_idx
    split_ts = feat_df["ts"].iloc[split_idx] if 0 <= split_idx < n else None

    daily_context_arr = feat_df["daily_context"].to_numpy()
    daily_trend_arr = feat_df["daily_trend"].to_numpy()
    daily_market_trend_arr = feat_df["daily_market_trend"].to_numpy()
    daily_loc_arr = feat_df["daily_loc"].to_numpy()

    frames = []
    rows_written = 0
    n_window_counts = {}

    for n_window in N_VALUES:
        cls = classify_window_state(feat_df, pattern_lookup, n_window)
        valid = cls["_valid"].to_numpy().copy()
        valid[: n_window - 1] = False
        if n - MAX_K > 0:
            valid[n - MAX_K:] = False
        else:
            valid[:] = False

        idx = np.where(valid)[0]
        n_window_counts[n_window] = len(idx)
        if len(idx) == 0:
            continue

        direction = cls["direction"].to_numpy()[idx]
        setup_state = cls["setup_state"].to_numpy()[idx]
        setup_type = cls["setup_type"].to_numpy()[idx]
        decision_ts = ts_vals[idx]
        d_context = daily_context_arr[idx]
        d_trend = daily_trend_arr[idx]
        d_mkt = daily_market_trend_arr[idx]
        d_loc = daily_loc_arr[idx]
        in_sample_flag = in_sample_flag_full[idx]
        close_T = close[idx]
        atr_T = atr14[idx]

        for k in K_VALUES:
            fr = fwd[k]["forward_return"][idx]
            fd = fwd[k]["forward_direction"][idx]
            fh = fwd[k]["fwd_high"][idx]
            fl = fwd[k]["fwd_low"][idx]
            hit = hit_target_for(direction, close_T, atr_T, fh, fl)

            frame = pd.DataFrame({
                "ticker": ticker,
                "n_window": n_window,
                "decision_ts": decision_ts,
                "setup_state": setup_state,
                "setup_type": setup_type,
                "direction": direction,
                "daily_trend": d_trend,
                "daily_market_trend": d_mkt,
                "daily_loc": d_loc,
                "daily_context": d_context,
                "forward_k": k,
                "forward_return": fr,
                "forward_direction": fd,
                "hit_target": hit,
                "in_sample_flag": in_sample_flag,
                "run_id": run_id,
            })
            frames.append(frame)

    full = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=INSERT_COLS)

    if do_write and not full.empty:
        rows_written = write_rows(engine, full)

    summary = summarize_ticker(ticker, full) if not full.empty else {"ticker": ticker, "by_n": {}}

    meta = {
        "ticker": ticker,
        "n_bars": n_bars,
        "date_min": str(bars["ts"].min()),
        "date_max": str(bars["ts"].max()),
        "split_ts": str(split_ts),
        "n_window_decision_counts": n_window_counts,
        "rows_written": rows_written,
        "elapsed_sec": round(time.time() - t0, 1),
    }

    del full, frames, fwd, feat_df, bars
    gc.collect()

    return summary, meta


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db-write", action="store_true", help="Skip writing to research_setup_formation")
    ap.add_argument("--limit-rows", type=int, default=None, help="Use only the last N bars per ticker (smoke-test)")
    ap.add_argument("--tickers", default=",".join(TICKERS))
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git_info = get_git_info()

    print(f"[run_id={run_id}] tickers={tickers} N={N_VALUES} K={K_VALUES} "
          f"db_write={not args.no_db_write} git={git_info}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    t_start = time.time()
    all_summaries = {}
    all_meta = {}
    for ticker in tickers:
        print(f"  -- processing {ticker} ...")
        summary, meta = process_ticker(engine, ticker, run_id, do_write=not args.no_db_write,
                                        limit_rows=args.limit_rows)
        all_summaries[ticker] = summary
        all_meta[ticker] = meta
        print(f"     {ticker}: {meta['n_bars']} bars [{meta['date_min']} .. {meta['date_max']}], "
              f"rows_written={meta['rows_written']}, elapsed={meta['elapsed_sec']}s")

    total_elapsed = round(time.time() - t_start, 1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    run_record = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_info,
        "tickers": tickers,
        "n_values": N_VALUES,
        "k_values": K_VALUES,
        "thresholds": {
            "FLAT_RANGE_ATR_MULT": FLAT_RANGE_ATR_MULT,
            "FLAT_VOL_RATIO_MAX": FLAT_VOL_RATIO_MAX,
            "GEOM_BODY_PCT_MIN": GEOM_BODY_PCT_MIN,
            "GEOM_SIZE_ATR_MULT": GEOM_SIZE_ATR_MULT,
            "SR_NEAR_TOL": SR_NEAR_TOL,
            "ATR_HIT_MULT": ATR_HIT_MULT,
            "FORWARD_RETURN_FLAT_EPS": FORWARD_RETURN_FLAT_EPS,
            "TRAIN_FRACTION": TRAIN_FRACTION,
            "MIN_CELL_N": MIN_CELL_N,
        },
        "per_ticker_meta": all_meta,
        "db_write": not args.no_db_write,
        "limit_rows": args.limit_rows,
        "total_elapsed_sec": total_elapsed,
    }

    log_path = REPORTS_DIR / "setup_formation_run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record) + "\n")
    print(f"[run log] appended to {log_path}")

    summary_path = REPORTS_DIR / "setup_formation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"run": run_record, "summaries": all_summaries}, f, indent=2, default=str)
    print(f"[summary] wrote {summary_path}")

    print(f"\nDone. total_elapsed={total_elapsed}s")


if __name__ == "__main__":
    main()
