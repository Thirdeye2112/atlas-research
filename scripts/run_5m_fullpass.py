#!/usr/bin/env python
"""
run_5m_fullpass.py — resumable batch runner to extend the 5-min pattern pass to
the full clean universe.

Coverage/throughput task ONLY. It reuses build_candle_memory.py's pass verbatim
(import, no edits) — same detection, same enrichment, same denoise (eq_tol=0.0008,
skip_neutral, sr_window=40 bisect S/R path; no O(n^2) regression). It just drives
it ticker-by-ticker, safely and resumably:

  - worklist = clean_universe.csv  MINUS  tickers already in pattern_memory(5m).
    (Never a full-table SELECT DISTINCT over intraday_bars.)
  - one ticker per committed transaction (build_candle_memory._flush commits each).
    Crash at ticker N keeps 1..N-1. Restart re-queries the skip-set and resumes.
  - per-ticker watchdog: any ticker over --timeout seconds is logged & skipped.
  - per-ticker log line (ticker, instances, seconds) + running N/M, %, ETA, to
    reports/validity/5m_fullpass.log and console.

Usage:
    python scripts/run_5m_fullpass.py --limit 5        # smoke test
    python scripts/run_5m_fullpass.py                  # full (resumable)
"""
from __future__ import annotations
import argparse, sys, time, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))   # to import build_candle_memory

import numpy as np, pandas as pd
from sqlalchemy import text

import build_candle_memory as B          # reuse the pass; load_dotenv already done on import
from atlas_research.ta import candlesticks as K
from atlas_research.db import connection
from config import settings

LOG_PATH = ROOT / "reports" / "validity" / "5m_fullpass.log"
WIDTH = 5
MIN_BARS = 260
WATCHDOG_S = 600         # skip any single ticker that runs longer than this
BAR_CAP = 400_000        # pathological-size guard (none observed; max seen ~106k)


def log(msg, fh):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    fh.write(line + "\n"); fh.flush()


def build_spy_ctx():
    """SPY daily context (rs/trend), same construction as build_candle_memory.main()."""
    with connection.get_connection() as c:
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"), c)
    spy = spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    return (spy / spy.shift(20) - 1, spy / spy.shift(60) - 1,
            pd.Series(np.where(spy > B.sma(spy, 50), "up", "down"), index=spy.index))


def process_one(tk, spy_ctx, eng):
    """One ticker, its own committed write. Returns (instances, skipped_nobars)."""
    with connection.get_connection() as conn:
        IF = B.intraday_frame(tk, conn, WIDTH)
        if IF is None:
            return 0, True                       # no / <MIN_BARS 5m bars
        if len(IF.cl) > BAR_CAP:
            return -1, False                     # pathological size -> caller logs & skips
        DF = B.daily_frame(tk, conn, spy_ctx, WIDTH)
    slow = B.slow_map_from_daily(DF) if DF is not None else (lambda ts: {})
    rows = B.candles_to_rows(tk, "5m", IF,
                             K.detect_all_candles(IF.o, IF.h, IF.l, IF.cl,
                                                  eq_tol=0.0008, skip_neutral=True),
                             slow_override=slow, sr_window=40)
    rows += B.chartpat_to_rows(tk, "5m", IF, slow_override=slow, sr_window=40)
    return B._flush(eng, rows), False            # _flush commits this ticker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="process only first N of the worklist (smoke)")
    ap.add_argument("--resume", action="store_true", default=True, help="(default) skip tickers already at 5m")
    ap.add_argument("--timeout", type=int, default=WATCHDOG_S)
    args = ap.parse_args()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOG_PATH, "a", encoding="utf-8")

    clean = pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"].astype(str).str.upper().tolist()
    with connection.get_connection() as c:
        done = {r[0] for r in c.execute(text("SELECT DISTINCT ticker FROM pattern_memory WHERE timeframe='5m'"))}
    worklist = [tk for tk in clean if tk not in done]
    if args.limit:
        worklist = worklist[:args.limit]
    M = len(worklist)

    log(f"=== run_5m_fullpass START === clean={len(clean)} done={len(done)} worklist={M} "
        f"limit={args.limit} timeout={args.timeout}s", fh)
    if M == 0:
        log("worklist empty — nothing to do (all clean tickers already patterned at 5m).", fh)
        fh.close(); return

    log("building SPY daily context...", fh)
    spy_ctx = build_spy_ctx()

    eng = connection.get_raw_engine()
    done_n = skip_nobars = errors = total_inst = 0
    times = []
    for i, tk in enumerate(worklist, 1):
        t0 = time.time()
        box = {}
        th = threading.Thread(target=lambda: box.update(_safe(process_one, tk, spy_ctx, eng)), daemon=True)
        th.start(); th.join(timeout=args.timeout)
        secs = time.time() - t0
        if th.is_alive():
            log(f"[{i}/{M}] {tk} TIMEOUT >{args.timeout}s — skipped (thread abandoned)", fh)
            errors += 1; continue
        if "err" in box:
            errors += 1
            log(f"[{i}/{M}] {tk} ERROR {box['err'][:120]}", fh); continue
        inst, nobars = box.get("inst", 0), box.get("nobars", False)
        if inst == -1:
            log(f"[{i}/{M}] {tk} SKIP pathological bar count (> {BAR_CAP:,})", fh); continue
        if nobars:
            skip_nobars += 1
        else:
            total_inst += inst
        done_n += 1
        times.append(secs)
        avg = sum(times) / len(times)
        eta_h = avg * (M - i) / 3600
        log(f"[{i}/{M} {100*i/M:.1f}%] {tk} inst={inst:,} {secs:.1f}s "
            f"| avg={avg:.1f}s ETA={eta_h:.1f}h total_inst={total_inst:,} nobars={skip_nobars} err={errors}", fh)

    log(f"=== run_5m_fullpass END === processed={done_n} nobars={skip_nobars} errors={errors} "
        f"total_instances={total_inst:,}", fh)
    fh.close()


def _safe(fn, *a):
    try:
        inst, nobars = fn(*a)
        return {"inst": inst, "nobars": nobars}
    except Exception as e:
        return {"err": repr(e)}


if __name__ == "__main__":
    main()
