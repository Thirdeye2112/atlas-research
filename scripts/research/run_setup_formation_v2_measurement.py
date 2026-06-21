#!/usr/bin/env python
"""
run_setup_formation_v2_measurement.py
========================================
ATLAS-RESEARCH setup-formation v2 measurement (5m, full tool-state snapshot,
N=2 only). MEASURE & REPORT ONLY -- not a predictor, not a trading signal.
See reports/research/SETUP_FORMATION_V2_REPORT.md.

Usage (run with cwd = C:\\Atlas\\atlas-research, the main checkout, so the
real .env is discoverable -- see setup_formation_v2_common.py for why):

    C:\\Atlas\\atlas-research\\.venv\\Scripts\\python.exe \
        C:\\Atlas\\atlas-research-setup-formation-v2\\scripts\\research\\run_setup_formation_v2_measurement.py \
        [--no-db-write] [--limit-rows N]

Writes:
    - research_setup_formation_v2 table (one row per ticker, decision_ts, forward_k)
    - reports/research/setup_formation_v2_run_log.jsonl  (append one record per run)
    - reports/research/setup_formation_v2_summary.json   (raw aggregates)
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

from setup_formation_v2_common import (
    TICKERS, N_WINDOW, K_VALUES, MAX_K, DATABASE_URL, TOOL_NAMES,
    GEOM_BODY_PCT_MIN, GEOM_SIZE_ATR_MULT, ATR_EXPAND_MULT, PIVOT_WIDTH,
    SWING_TREND_LOOKBACK, ATR_HIT_MULT, FORWARD_RETURN_FLAT_EPS,
    TRAIN_FRACTION, MIN_CELL_N,
    load_intraday_bars, build_pattern_lookup, build_swing_lookup, build_tool_snapshot,
)
from setup_formation_v2_outcomes import compute_forward_outcomes, hit_target_for
from atlas_research.intraday.features import compute_features

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

INSERT_COLS = [
    "ticker", "n_window", "decision_ts",
    "state_candle", "direction_candle", "active_candle",
    "state_volume", "active_volume",
    "state_macd", "active_macd",
    "state_rsi", "active_rsi",
    "state_ema", "active_ema",
    "state_vwap", "active_vwap",
    "state_atr", "active_atr",
    "state_swing", "active_swing",
    "state_orb", "active_orb",
    "confluence_count", "active_tools_csv",
    "forward_k", "forward_return", "forward_direction", "hit_target",
    "in_sample_flag", "run_id",
]

STATE_COLS = ["state_candle", "state_volume", "state_macd", "state_rsi", "state_ema",
              "state_vwap", "state_atr", "state_swing", "state_orb"]
ACTIVE_COLS = ["active_" + t for t in TOOL_NAMES]

# Pre-specified pairwise tool combinations to test (NOT an exhaustive 2^9
# search -- that would be an uncontrolled multiple-testing fishing expedition.
# "Both active" means active_X & active_Y, regardless of what else fires --
# this keeps sample sizes usable while still answering "does X-plus-Y relate
# to outcome differently than X alone or baseline."
COMBOS_TO_TEST = [
    ("candle", "volume"), ("candle", "macd"), ("candle", "rsi"), ("candle", "ema"),
    ("candle", "vwap"), ("candle", "atr"), ("candle", "swing"), ("candle", "orb"),
    ("volume", "macd"),   # explicitly named in the v2 brief as an example
    ("volume", "ema"),
    ("macd", "ema"),
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

    for c in STATE_COLS:
        arrays[c] = [_clean_obj(v) for v in d[c].tolist()]
    arrays["direction_candle"] = [_clean_obj(v) for v in d["direction_candle"].tolist()]

    for c in ACTIVE_COLS:
        arrays[c] = d[c].astype(bool).tolist()

    arrays["confluence_count"] = d["confluence_count"].astype(int).tolist()
    arrays["active_tools_csv"] = [_clean_obj(v) for v in d["active_tools_csv"].tolist()]

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
        sql = f"INSERT INTO research_setup_formation_v2 ({', '.join(INSERT_COLS)}) VALUES %s"
        execute_values(cur, sql, records, page_size=10000)
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(records)


# ---------------------------------------------------------------------------
# Aggregation helpers
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


def _curve_row(sub: pd.DataFrame) -> dict:
    ret_m, ret_lo, ret_hi, ret_n = _ci95_mean(sub["forward_return"])
    hit_series = sub["hit_target"].dropna().astype(bool) if sub["hit_target"].notna().any() else pd.Series(dtype=float)
    hit_m, hit_lo, hit_hi, hit_n = _ci95_rate(hit_series)
    dir_up_rate = (sub["forward_direction"] == "up").mean() if len(sub) else np.nan
    return {
        "n": ret_n,
        "mean_return": ret_m, "ci_lo": ret_lo, "ci_hi": ret_hi,
        "hit_rate": hit_m, "hit_ci_lo": hit_lo, "hit_ci_hi": hit_hi, "hit_n": hit_n,
        "pct_up": dir_up_rate,
    }


def summarize_ticker(ticker: str, df: pd.DataFrame) -> dict:
    summary = {"ticker": ticker}

    # k=1 rows only -- one row per decision point
    g1 = df[df["forward_k"] == K_VALUES[0]]
    confluence_dist = {}
    for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
        sub = g1[g1["in_sample_flag"] == sample_flag]
        confluence_dist[label] = sub["confluence_count"].value_counts().sort_index().to_dict()
    summary["confluence_dist"] = confluence_dist

    summary["tool_active_rate"] = {
        t: float(g1["active_" + t].mean()) if len(g1) else np.nan for t in TOOL_NAMES
    }

    summary["candle_setup_type_counts"] = (
        g1[g1["active_candle"]]["state_candle"].value_counts().to_dict()
    )

    # forward curves by confluence_count bucket (0,1,2,3,4,5+) and ALL baseline
    curves = {}
    bucket = df["confluence_count"].clip(upper=5).astype(str)
    bucket = bucket.where(df["confluence_count"] < 5, "5plus")
    df = df.assign(_bucket=bucket)
    for bucket_label, gk_all in df.groupby("_bucket"):
        curves[bucket_label] = {}
        for k, gk in gk_all.groupby("forward_k"):
            row = {}
            for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
                row[label] = _curve_row(gk[gk["in_sample_flag"] == sample_flag])
            curves[bucket_label][int(k)] = row
    curves["ALL"] = {}
    for k, gk in df.groupby("forward_k"):
        row = {}
        for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
            row[label] = _curve_row(gk[gk["in_sample_flag"] == sample_flag])
        curves["ALL"][int(k)] = row
    summary["curves_by_confluence"] = curves

    # forward curves by pre-specified pairwise combos (both active), k=5 only
    # (k=5 chosen as the headline horizon, matching v1's report convention)
    combo_curves = {}
    K_HEADLINE = K_VALUES[-1]
    gk5 = df[df["forward_k"] == K_HEADLINE]
    for t1, t2 in COMBOS_TO_TEST:
        both = gk5[gk5["active_" + t1] & gk5["active_" + t2]]
        row = {}
        for sample_flag, label in ((True, "in_sample"), (False, "held_out")):
            row[label] = _curve_row(both[both["in_sample_flag"] == sample_flag])
        combo_curves[f"{t1}+{t2}"] = row
    summary["combo_curves_k5"] = combo_curves

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

    o = feat_df["open"].to_numpy(float); h = feat_df["high"].to_numpy(float)
    lo = feat_df["low"].to_numpy(float); c = feat_df["close"].to_numpy(float)
    pattern_lookup = build_pattern_lookup(o, h, lo, c)
    swing_lookup = build_swing_lookup(h, lo)

    snap = build_tool_snapshot(feat_df, pattern_lookup, swing_lookup)

    fwd = compute_forward_outcomes(feat_df)
    atr14 = feat_df["atr14"].to_numpy(float)
    close = feat_df["close"].to_numpy(float)
    ts_vals = feat_df["ts"].to_numpy()

    n = len(feat_df)
    split_idx = int(n * TRAIN_FRACTION)
    in_sample_flag_full = np.arange(n) < split_idx
    split_ts = feat_df["ts"].iloc[split_idx] if 0 <= split_idx < n else None

    valid = snap["_valid"].to_numpy().copy()
    valid[: N_WINDOW - 1] = False
    if n - MAX_K > 0:
        valid[n - MAX_K:] = False
    else:
        valid[:] = False

    idx = np.where(valid)[0]
    n_decisions = len(idx)

    frames = []
    rows_written = 0

    if n_decisions > 0:
        decision_ts = ts_vals[idx]
        in_sample_flag = in_sample_flag_full[idx]
        close_T = close[idx]
        atr_T = atr14[idx]
        direction_candle = snap["direction_candle"].to_numpy()[idx]

        snap_idx = {col: snap[col].to_numpy()[idx] for col in snap.columns if col != "_valid"}

        for k in K_VALUES:
            fr = fwd[k]["forward_return"][idx]
            fd = fwd[k]["forward_direction"][idx]
            fh = fwd[k]["fwd_high"][idx]
            fl = fwd[k]["fwd_low"][idx]
            hit = hit_target_for(direction_candle, close_T, atr_T, fh, fl)

            frame = pd.DataFrame({
                "ticker": ticker,
                "n_window": N_WINDOW,
                "decision_ts": decision_ts,
                **snap_idx,
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

    summary = summarize_ticker(ticker, full) if not full.empty else {"ticker": ticker}

    meta = {
        "ticker": ticker,
        "n_bars": n_bars,
        "date_min": str(bars["ts"].min()),
        "date_max": str(bars["ts"].max()),
        "split_ts": str(split_ts),
        "n_decisions": n_decisions,
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
    ap.add_argument("--no-db-write", action="store_true")
    ap.add_argument("--limit-rows", type=int, default=None)
    ap.add_argument("--tickers", default=",".join(TICKERS))
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git_info = get_git_info()

    print(f"[run_id={run_id}] tickers={tickers} N_WINDOW={N_WINDOW} K={K_VALUES} "
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
              f"decisions={meta['n_decisions']}, rows_written={meta['rows_written']}, elapsed={meta['elapsed_sec']}s")

    total_elapsed = round(time.time() - t_start, 1)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    run_record = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_info,
        "tickers": tickers,
        "n_window": N_WINDOW,
        "k_values": K_VALUES,
        "tool_names": TOOL_NAMES,
        "combos_tested": [f"{a}+{b}" for a, b in COMBOS_TO_TEST],
        "thresholds": {
            "GEOM_BODY_PCT_MIN": GEOM_BODY_PCT_MIN,
            "GEOM_SIZE_ATR_MULT": GEOM_SIZE_ATR_MULT,
            "ATR_EXPAND_MULT": ATR_EXPAND_MULT,
            "PIVOT_WIDTH": PIVOT_WIDTH,
            "SWING_TREND_LOOKBACK": SWING_TREND_LOOKBACK,
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

    log_path = REPORTS_DIR / "setup_formation_v2_run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record) + "\n")
    print(f"[run log] appended to {log_path}")

    summary_path = REPORTS_DIR / "setup_formation_v2_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"run": run_record, "summaries": all_summaries}, f, indent=2, default=str)
    print(f"[summary] wrote {summary_path}")

    print(f"\nDone. total_elapsed={total_elapsed}s")


if __name__ == "__main__":
    main()
