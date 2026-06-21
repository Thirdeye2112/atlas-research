#!/usr/bin/env python
"""
run_dome_leg_signature_measurement.py
========================================
ATLAS-RESEARCH dome/leg early-signature study. MEASURE & REPORT ONLY -- not
a predictor, not a trading signal. See reports/research/DOME_LEG_SIGNATURE_REPORT.md.

Usage (cwd = C:\\Atlas\\atlas-research, the main checkout):
    .venv\\Scripts\\python.exe \
        C:\\Atlas\\atlas-research-dome-leg-signature\\scripts\\research\\run_dome_leg_signature_measurement.py \
        [--no-db-write] [--limit-rows N]

Writes:
    - research_dome_leg_signature, research_dome_leg_realtime tables
    - reports/research/dome_leg_signature_run_log.jsonl
"""
from __future__ import annotations

import argparse
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

from dome_leg_signature_common import (
    TICKERS, PIVOT_WIDTH, AMP_MULT, EARLY_N, WICK_PCT_MIN, RNG_ATR_MIN, VOL_RATIO_MIN,
    FORWARD_K_LIST, TRAIN_FRACTION, DATABASE_URL,
    build_feature_frame, walk_forward_split_mask, significant_pivots, build_legs,
)
from atlas_research.intraday.features import compute_features
from atlas_research.ta.structure import swing_pivots

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

LEG_COLS = [
    "run_id", "ticker", "timeframe", "leg_dir", "start_ts", "peak_ts", "corr_ts",
    "leg_amp", "leg_bars", "corr_depth", "corr_bars",
    "early_gain", "early_bars", "early_slope",
    "start_body_pct", "start_upper_wick_pct", "start_lower_wick_pct",
    "start_rng_atr_ratio", "start_vol_ratio", "start_close_loc", "start_is_green",
    "peak_body_pct", "peak_upper_wick_pct", "peak_lower_wick_pct",
    "peak_rng_atr_ratio", "peak_vol_ratio", "peak_close_loc", "peak_is_green",
    "in_sample_flag",
]

RT_COLS = ["run_id", "ticker", "timeframe", "bar_ts", "filter_type", "forward_k", "forward_r", "in_sample_flag"]


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


def _clean(v):
    if v is None:
        return None
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return None if np.isnan(v) else v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    return v


def write_table(engine, table: str, cols: list[str], records: list[tuple]) -> int:
    if not records:
        return 0
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s"
        execute_values(cur, sql, records, page_size=10000)
        raw_conn.commit()
    finally:
        raw_conn.close()
    return len(records)


def build_leg_records(legs: list[dict], ticker: str, run_id: str, ts_vals, feats: pd.DataFrame,
                       in_sample_full: np.ndarray) -> list[tuple]:
    recs = []
    for leg in legs:
        s_idx, p_idx = leg["start_idx"], leg["peak_idx"]
        s_row, p_row = feats.iloc[s_idx], feats.iloc[p_idx]
        recs.append((
            run_id, ticker, "5m", leg["leg_dir"],
            pd.Timestamp(ts_vals[s_idx]).to_pydatetime(), pd.Timestamp(ts_vals[p_idx]).to_pydatetime(),
            pd.Timestamp(ts_vals[leg["corr_idx"]]).to_pydatetime() if leg["corr_idx"] is not None else None,
            leg["leg_amp"], leg["leg_bars"], _clean(leg["corr_depth"]), leg["corr_bars"],
            _clean(leg["early_gain"]), leg["early_bars"], _clean(leg["early_slope"]),
            _clean(s_row["body_pct"]), _clean(s_row["upper_wick_pct"]), _clean(s_row["lower_wick_pct"]),
            _clean(s_row["rng_atr_ratio"]), _clean(s_row["vol_ratio"]), _clean(s_row["close_loc"]), bool(s_row["is_green"]),
            _clean(p_row["body_pct"]), _clean(p_row["upper_wick_pct"]), _clean(p_row["lower_wick_pct"]),
            _clean(p_row["rng_atr_ratio"]), _clean(p_row["vol_ratio"]), _clean(p_row["close_loc"]), bool(p_row["is_green"]),
            bool(in_sample_full[s_idx]),
        ))
    return recs


def build_realtime_records(ticker: str, run_id: str, ts_vals, close: np.ndarray, atr: np.ndarray,
                            filter_idx: np.ndarray, filter_type: str, in_sample_full: np.ndarray) -> list[tuple]:
    n = len(close)
    recs = []
    for i0 in filter_idx:
        for k in FORWARD_K_LIST:
            if i0 + k >= n or atr[i0] <= 0 or np.isnan(atr[i0]):
                continue
            fwd_r = (close[i0 + k] - close[i0]) / atr[i0]
            recs.append((
                run_id, ticker, "5m", pd.Timestamp(ts_vals[i0]).to_pydatetime(), filter_type, k,
                float(fwd_r), bool(in_sample_full[i0]),
            ))
    return recs


def process_ticker(engine, ticker: str, run_id: str, do_write: bool, limit_rows: int | None) -> dict:
    t0 = time.time()
    bars = load_5m_bars(engine, ticker)
    if limit_rows:
        bars = bars.iloc[-limit_rows:].reset_index(drop=True)
    feat_df = compute_features(bars)
    feats = build_feature_frame(feat_df)
    h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
    c = feat_df["close"].to_numpy(float); atr = feat_df["atr14"].to_numpy(float)
    ts_vals = feat_df["ts"].to_numpy()
    n = len(feat_df)
    in_sample_full = walk_forward_split_mask(n, TRAIN_FRACTION)

    piv = swing_pivots(h, l, width=PIVOT_WIDTH)
    sig = significant_pivots(piv, atr, AMP_MULT)
    legs = build_legs(sig, c, EARLY_N)
    leg_records = build_leg_records(legs, ticker, run_id, ts_vals, feats, in_sample_full)

    rng_ratio = feats["rng_atr_ratio"].to_numpy()
    vol_ratio = feats["vol_ratio"].to_numpy()
    lw = feats["lower_wick_pct"].to_numpy()
    uw = feats["upper_wick_pct"].to_numpy()
    valid = ~(np.isnan(rng_ratio) | np.isnan(vol_ratio) | np.isnan(lw) | np.isnan(atr))

    bottom_like = valid & (lw > WICK_PCT_MIN) & (rng_ratio > RNG_ATR_MIN) & (vol_ratio > VOL_RATIO_MIN)
    top_like = valid & (uw > WICK_PCT_MIN) & (rng_ratio > RNG_ATR_MIN) & (vol_ratio > VOL_RATIO_MIN)

    rng = np.random.default_rng(20260623)
    valid_idx = np.where(valid)[0]
    base_idx = rng.choice(valid_idx, size=min(20000, len(valid_idx)), replace=False)

    rt_records = []
    rt_records += build_realtime_records(ticker, run_id, ts_vals, c, atr, np.where(bottom_like)[0], "bottom_like", in_sample_full)
    rt_records += build_realtime_records(ticker, run_id, ts_vals, c, atr, np.where(top_like)[0], "top_like", in_sample_full)
    rt_records += build_realtime_records(ticker, run_id, ts_vals, c, atr, base_idx, "__BASELINE__", in_sample_full)

    n_leg_written = n_rt_written = 0
    if do_write:
        n_leg_written = write_table(engine, "research_dome_leg_signature", LEG_COLS, leg_records)
        n_rt_written = write_table(engine, "research_dome_leg_realtime", RT_COLS, rt_records)

    n_up = sum(1 for x in legs if x["leg_dir"] == "up")
    n_down = sum(1 for x in legs if x["leg_dir"] == "down")
    meta = {
        "ticker": ticker, "n_bars": n, "n_legs": len(legs), "n_up": n_up, "n_down": n_down,
        "n_bottom_like": int(bottom_like.sum()), "n_top_like": int(top_like.sum()),
        "n_leg_rows_written": n_leg_written, "n_rt_rows_written": n_rt_written,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db-write", action="store_true")
    ap.add_argument("--limit-rows", type=int, default=None)
    ap.add_argument("--tickers", default=",".join(TICKERS))
    args = ap.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git_info = get_git_info()
    print(f"[run_id={run_id}] tickers={tickers} db_write={not args.no_db_write} git={git_info}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    t_start = time.time()
    all_meta = []
    for ticker in tickers:
        print(f"  -- {ticker} ...")
        meta = process_ticker(engine, ticker, run_id, do_write=not args.no_db_write, limit_rows=args.limit_rows)
        all_meta.append(meta)
        print(f"     {meta}")

    total_elapsed = round(time.time() - t_start, 1)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_record = {
        "run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "git": git_info,
        "tickers": tickers, "pivot_width": PIVOT_WIDTH, "amp_mult": AMP_MULT, "early_n": EARLY_N,
        "wick_pct_min": WICK_PCT_MIN, "rng_atr_min": RNG_ATR_MIN, "vol_ratio_min": VOL_RATIO_MIN,
        "forward_k_list": FORWARD_K_LIST, "train_fraction": TRAIN_FRACTION,
        "per_ticker_meta": all_meta, "db_write": not args.no_db_write,
        "limit_rows": args.limit_rows, "total_elapsed_sec": total_elapsed,
    }
    log_path = REPORTS_DIR / "dome_leg_signature_run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record, default=str) + "\n")
    print(f"[run log] appended to {log_path}")
    print(f"\nDone. total_elapsed={total_elapsed}s")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
