#!/usr/bin/env python
"""
run_foundation_retest_measurement.py
=======================================
ATLAS-RESEARCH foundation retest: one stock (AAPL), 5m, deep. Conditional
per-tool triggers (not kitchen-sink averaging), R-bracket expectancy vs.
baseline, daily-timeframe corroboration. MEASURE & REPORT ONLY.
See reports/research/FOUNDATION_RETEST_REPORT.md.

Usage (cwd = C:\\Atlas\\atlas-research, the main checkout):
    .venv\\Scripts\\python.exe \
        C:\\Atlas\\atlas-research-foundation-retest\\scripts\\research\\run_foundation_retest_measurement.py \
        [--no-db-write] [--limit-rows N]
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

from foundation_retest_common import (
    TICKER, TIMEFRAME, K_VALUES, R_MULTIPLES, ATR_STOP_MULT, FORWARD_WINDOW,
    TRAIN_FRACTION, DATABASE_URL,
    r_bracket_outcome, simple_forward_return, baseline_outcomes_for_k, walk_forward_split_mask,
)
from foundation_retest_triggers import build_all_triggers
from foundation_retest_daily import load_daily_pattern_context, attach_daily_context, daily_agrees

from atlas_research.intraday.features import compute_features

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

TRIG_COLS = [
    "run_id", "ticker", "timeframe", "trigger_type", "decision_ts", "direction",
    "daily_trend", "daily_market_trend", "daily_dist_support", "daily_dist_resistance", "daily_agrees",
    "forward_k", "fwd_return", "fwd_direction", "outcome_b", "max_r", "realized_r",
    "in_sample_flag",
]
BASE_COLS = [
    "run_id", "ticker", "timeframe", "decision_ts", "direction",
    "forward_k", "fwd_return", "fwd_direction", "outcome_b", "max_r", "realized_r",
    "in_sample_flag",
]


def get_git_info() -> dict:
    def _git(*a):
        try:
            return subprocess.check_output(["git", *a], cwd=str(WORKTREE_ROOT), text=True).strip()
        except Exception as e:
            return f"<unavailable: {e}>"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-db-write", action="store_true")
    ap.add_argument("--limit-rows", type=int, default=None)
    args = ap.parse_args()

    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    git_info = get_git_info()
    print(f"[run_id={run_id}] ticker={TICKER} git={git_info}")

    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=2)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    t0 = time.time()
    bars = load_5m_bars(engine, TICKER)
    if args.limit_rows:
        bars = bars.iloc[-args.limit_rows:].reset_index(drop=True)
    feat_df = compute_features(bars)
    n = len(feat_df)
    print(f"Loaded {n} bars [{feat_df['ts'].iloc[0]} .. {feat_df['ts'].iloc[-1]}]")

    daily_ctx = load_daily_pattern_context(engine, TICKER)
    feat_df = attach_daily_context(feat_df, daily_ctx)
    print(f"Daily context rows available: {len(daily_ctx)}")

    h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
    c = feat_df["close"].to_numpy(float)
    atr = feat_df["atr14"].to_numpy(float)
    ts_vals = feat_df["ts"].to_numpy()
    daily_trend_arr = feat_df["daily_trend"].to_numpy()
    daily_mkt_arr = feat_df["daily_market_trend"].to_numpy()
    daily_dsup_arr = feat_df["daily_dist_support"].to_numpy()
    daily_dres_arr = feat_df["daily_dist_resistance"].to_numpy()

    in_sample_full = walk_forward_split_mask(n, TRAIN_FRACTION)
    split_idx = int(n * TRAIN_FRACTION)
    print(f"Walk-forward split: in-sample bars 0..{split_idx} ({feat_df['ts'].iloc[split_idx-1]}), "
          f"held-out {split_idx}..{n} ({feat_df['ts'].iloc[split_idx]} .. {feat_df['ts'].iloc[-1]})")

    triggers = build_all_triggers(feat_df, atr)
    print(f"Total trigger instances (all 16 trigger_types pooled): {len(triggers)}")
    by_type = {}
    for t in triggers:
        by_type[t.trigger_type] = by_type.get(t.trigger_type, 0) + 1
    for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]):
        print(f"  {k:32s} {v:6d}")

    trig_records = []
    for trig in triggers:
        i0 = trig.decision_idx
        if i0 >= n:
            continue
        entry = c[i0]
        atr_t = atr[i0]
        dtrend = daily_trend_arr[i0]
        dmkt = daily_mkt_arr[i0]
        dsup = daily_dsup_arr[i0]
        dres = daily_dres_arr[i0]
        agrees = daily_agrees(trig.direction, dtrend)

        for k in K_VALUES:
            res = r_bracket_outcome(trig.direction, entry, atr_t, h, l, c, i0, k_cap=k)
            fwd_ret, fwd_dir = simple_forward_return(c, i0, k)
            trig_records.append((
                run_id, TICKER, TIMEFRAME, trig.trigger_type,
                pd.Timestamp(ts_vals[i0]).to_pydatetime(), trig.direction,
                _clean(dtrend), _clean(dmkt), _clean(dsup), _clean(dres), agrees,
                k, _clean(fwd_ret), _clean(fwd_dir), res["outcome"],
                None if res["max_r"] is None else int(res["max_r"]), _clean(res["realized_R"]),
                bool(in_sample_full[i0]),
            ))

    print(f"Built {len(trig_records)} trigger x K rows")

    # ---- baseline (random direction, same bracket), per K -------------------
    valid = ~np.isnan(atr)
    base_records = []
    for k in K_VALUES:
        bdf = baseline_outcomes_for_k(c, h, l, atr, valid, k, sample_every=2)
        for _, r in bdf.iterrows():
            i0 = int(r["idx"])
            base_records.append((
                run_id, TICKER, TIMEFRAME, pd.Timestamp(ts_vals[i0]).to_pydatetime(), r["direction"],
                k, _clean(r["fwd_return"]), _clean(r["fwd_direction"]), r["outcome"],
                None if r["max_r"] is None else int(r["max_r"]), _clean(r["realized_R"]),
                bool(in_sample_full[i0]),
            ))
    print(f"Built {len(base_records)} baseline rows")

    n_trig_written = n_base_written = 0
    if not args.no_db_write:
        n_trig_written = write_table(engine, "research_foundation_retest", TRIG_COLS, trig_records)
        n_base_written = write_table(engine, "research_foundation_retest_baseline", BASE_COLS, base_records)

    elapsed = round(time.time() - t0, 1)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    run_record = {
        "run_id": run_id, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "git": git_info,
        "ticker": TICKER, "timeframe": TIMEFRAME, "n_bars": n,
        "date_min": str(feat_df["ts"].iloc[0]), "date_max": str(feat_df["ts"].iloc[-1]),
        "split_ts": str(feat_df["ts"].iloc[split_idx]), "train_fraction": TRAIN_FRACTION,
        "k_values": K_VALUES, "r_multiples": R_MULTIPLES, "atr_stop_mult": ATR_STOP_MULT,
        "forward_window": FORWARD_WINDOW,
        "trigger_counts": by_type, "n_trigger_rows": len(trig_records), "n_baseline_rows": len(base_records),
        "n_trig_written": n_trig_written, "n_base_written": n_base_written,
        "db_write": not args.no_db_write, "limit_rows": args.limit_rows, "elapsed_sec": elapsed,
    }
    log_path = REPORTS_DIR / "foundation_retest_run_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(run_record, default=str) + "\n")
    print(f"[run log] appended to {log_path}")
    print(f"\nDone. elapsed={elapsed}s  run_id={run_id}")


if __name__ == "__main__":
    main()
