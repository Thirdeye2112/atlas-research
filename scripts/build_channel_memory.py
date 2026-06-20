#!/usr/bin/env python
"""
build_channel_memory.py — additive channel backfill into pattern_memory.

Detects price channels (ta/channels.py) and logs channel FORMATION rows
(pattern_type = channel_ascending|channel_descending|channel_horizontal) and
channel BREAK events (pattern_type = channel_break) with the SAME enrichment
context as every other pattern. Reuses build_candle_memory.py (import, no edits)
for the Frame/enrichment/after-story/upsert; reuses ta/channels for detection.

ADDITIVE + IDEMPOTENT: inserts only channel rows; never touches existing
non-channel instances. On (re)start it skips tickers that already have channel
rows for the chosen timeframe — so it is fully resumable and safe to run while
the base 5m pattern pass keeps going (channels are separate rows).

LOOK-AHEAD: channels are fit on past swings only; the break is logged at the bar
it occurs (forward event). See ta/channels.py.

Usage:
    python scripts/build_channel_memory.py --timeframe daily --limit 3   # smoke
    python scripts/build_channel_memory.py --timeframe daily             # full daily backfill
    python scripts/build_channel_memory.py --timeframe 5m --min-bars 30  # full 5m backfill
"""
from __future__ import annotations
import argparse, sys, time, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np, pandas as pd
from sqlalchemy import text

import build_candle_memory as B
from atlas_research.ta.channels import detect_channels
from atlas_research.db import connection
from config import settings

WIDTH = 5
WATCHDOG_S = 600
DIRMAP = {"ascending": "long", "descending": "short", "horizontal": "neutral"}


def log(msg, fh):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    fh.write(line + "\n"); fh.flush()


def build_spy_ctx():
    with connection.get_connection() as c:
        spy = pd.read_sql(text("SELECT date, adjusted_close FROM raw_bars WHERE ticker='SPY' ORDER BY date"), c)
    spy = spy.set_index(pd.to_datetime(spy["date"]))["adjusted_close"].astype(float)
    return (spy / spy.shift(20) - 1, spy / spy.shift(60) - 1,
            pd.Series(np.where(spy > B.sma(spy, 50), "up", "down"), index=spy.index))


def channel_rows(tk, tf, F, channels, slow_override=None, sr_window=None):
    rows = []
    cl, dates = F.cl, F.dates

    def ctx_at(idx, si, width_pct):
        if idx < 60 or (slow_override is None and not np.isfinite(F.s200[idx])):
            return None
        cx = F.ctx(idx, si, width_pct, sr_window=sr_window)
        if slow_override is not None:
            so = slow_override(dates.iloc[idx])
            if so is None:
                return None
            cx.update(so)
        return cx

    for ch in channels:
        di, si = ch.detect_idx, ch.start_idx
        cx = ctx_at(di, si, ch.width_pct)
        if cx is None:
            continue
        d = DIRMAP[ch.ctype]
        sdir = "short" if d == "short" else "long"
        entry = float(cl[di])
        stop = float(ch.res_at(di) if d == "short" else ch.sup_at(di))
        story = B.after_story(sdir, entry, None, F.h, F.l, F.cl, di)
        extra = {"channel_type": ch.ctype, "sup_slope": ch.sup_slope, "res_slope": ch.res_slope,
                 "touches_sup": ch.touches_sup, "touches_res": ch.touches_res,
                 "width_pct": ch.width_pct, "has_break": ch.break_idx is not None,
                 "break_dir": ch.break_dir}
        rows.append(B._row(tk, tf, "channel_" + ch.ctype, d, dates.iloc[di].date(),
                           dates.iloc[si].date(), dates.iloc[di].date(), cx,
                           entry, stop, None, None, story, extra))

        if ch.break_idx is not None:
            bi = ch.break_idx
            cxb = ctx_at(bi, si, ch.width_pct)
            if cxb is None:
                continue
            bdir = "long" if ch.break_dir == "up" else "short"
            storyb = B.after_story(bdir, float(cl[bi]), None, F.h, F.l, F.cl, bi)
            extrab = {"channel_type": ch.ctype, "break_dir": ch.break_dir,
                      "prior_channel_bars": int(di - si), "width_pct": ch.width_pct}
            rows.append(B._row(tk, tf, "channel_break", bdir, dates.iloc[bi].date(),
                               dates.iloc[si].date(), dates.iloc[bi].date(), cxb,
                               float(cl[bi]), None, None, None, storyb, extrab))
    return rows


def process_one(tk, tf, spy_ctx, min_bars, slope_thr, eng):
    with connection.get_connection() as conn:
        if tf == "5m":
            IF = B.intraday_frame(tk, conn, WIDTH)
            if IF is None:
                return 0, True
            DF = B.daily_frame(tk, conn, spy_ctx, WIDTH)
            slow = B.slow_map_from_daily(DF) if DF is not None else (lambda ts: {})
            F, sov, srw = IF, slow, 40
        else:
            F = B.daily_frame(tk, conn, spy_ctx, WIDTH)
            if F is None:
                return 0, True
            sov, srw = None, None
    chans = detect_channels(F.h, F.l, F.cl, min_bars=min_bars, slope_thr=slope_thr)
    rows = channel_rows(tk, tf, F, chans, slow_override=sov, sr_window=srw)
    return B._flush(eng, rows), False


def _safe(fn, *a):
    try:
        inst, nobars = fn(*a)
        return {"inst": inst, "nobars": nobars}
    except Exception as e:
        return {"err": repr(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", choices=["daily", "5m"], required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tickers", nargs="+", default=None)
    ap.add_argument("--min-bars", type=int, default=None, help="default 10 daily / 30 5m")
    ap.add_argument("--slope-thr", type=float, default=None,
                    help="per-bar normalized slope for asc/desc vs horizontal; default 0.0008 daily / 0.0001 5m")
    ap.add_argument("--timeout", type=int, default=WATCHDOG_S)
    args = ap.parse_args()
    tf = args.timeframe
    min_bars = args.min_bars if args.min_bars is not None else (30 if tf == "5m" else 10)
    # slope_thr is a per-BAR threshold; scale it down for 5m (bars ~78x shorter than daily)
    # so the asc/desc/horizontal split stays meaningful instead of collapsing to horizontal.
    slope_thr = args.slope_thr if args.slope_thr is not None else (0.0001 if tf == "5m" else 0.0008)

    log_path = ROOT / "reports" / "validity" / f"channel_backfill_{tf}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(log_path, "a", encoding="utf-8")

    clean = pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"].astype(str).str.upper().tolist()
    with connection.get_connection() as c:
        done = {r[0] for r in c.execute(text(
            "SELECT DISTINCT ticker FROM pattern_memory WHERE timeframe=:tf AND pattern_type LIKE 'channel\\_%'"
        ), {"tf": tf})}
    work = args.tickers if args.tickers else [tk for tk in clean if tk not in done]
    if args.tickers:
        work = [tk for tk in work if tk not in done]
    if args.limit:
        work = work[:args.limit]
    M = len(work)
    log(f"=== channel backfill {tf} START === clean={len(clean)} channel-done={len(done)} "
        f"worklist={M} min_bars={min_bars}", fh)
    if M == 0:
        log("worklist empty — all tickers already channel-scanned for this timeframe.", fh)
        fh.close(); return

    log("building SPY daily context...", fh)
    spy_ctx = build_spy_ctx()
    eng = connection.get_raw_engine()
    done_n = nobars = errors = total = 0
    times = []
    for i, tk in enumerate(work, 1):
        t0 = time.time(); box = {}
        th = threading.Thread(target=lambda: box.update(_safe(process_one, tk, tf, spy_ctx, min_bars, slope_thr, eng)), daemon=True)
        th.start(); th.join(timeout=args.timeout)
        secs = time.time() - t0
        if th.is_alive():
            errors += 1; log(f"[{i}/{M}] {tk} TIMEOUT >{args.timeout}s — skipped", fh); continue
        if "err" in box:
            errors += 1; log(f"[{i}/{M}] {tk} ERROR {box['err'][:120]}", fh); continue
        inst, nb = box.get("inst", 0), box.get("nobars", False)
        if nb:
            nobars += 1
        else:
            total += inst; done_n += 1
        times.append(secs)
        avg = sum(times) / len(times); eta_h = avg * (M - i) / 3600
        log(f"[{i}/{M} {100*i/M:.1f}%] {tk} ch_rows={inst:,} {secs:.1f}s | avg={avg:.1f}s "
            f"ETA={eta_h:.1f}h total={total:,} nobars={nobars} err={errors}", fh)

    log(f"=== channel backfill {tf} END === processed={done_n} nobars={nobars} errors={errors} "
        f"total_channel_rows={total:,}", fh)
    fh.close()


if __name__ == "__main__":
    main()
