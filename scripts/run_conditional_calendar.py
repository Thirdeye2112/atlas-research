#!/usr/bin/env python3
"""
run_conditional_calendar.py -- Calendar-aware conditional state detector

Detects which calendar patterns are active TODAY and shows their
historical backtest results. Also runs backtests if --run-backtests is set.

Usage:
    python scripts/run_conditional_calendar.py
    python scripts/run_conditional_calendar.py --run-backtests
    python scripts/run_conditional_calendar.py --date 2026-06-21
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")

from sqlalchemy import text

from atlas_research.db.connection import get_raw_engine
from atlas_research.utils.logging import configure_logging, get_logger
from config import settings

configure_logging(level="WARNING", fmt=settings.LOG_FORMAT)
log = get_logger("cal_conditional")


def load_events_window(as_of: date, window_days: int = 30) -> list[dict]:
    engine = get_raw_engine()
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT date, event_type, description
            FROM market_calendar
            WHERE date BETWEEN :start AND :end
            ORDER BY date
        """), {
            "start": as_of - timedelta(days=window_days),
            "end": as_of + timedelta(days=window_days),
        }).fetchall()
    return [{"date": r.date, "event_type": r.event_type, "description": r.description}
            for r in rows]


def build_calendar_context(as_of: date, events: list[dict]) -> dict:
    """Compute calendar state flags for as_of date."""

    # FOMC proximity
    fomc_dates = [e["date"] for e in events if e["event_type"] == "fomc_meeting"]
    days_to_fomc: int | None = None
    fomc_direction: str | None = None
    for fd in fomc_dates:
        diff = (fd - as_of).days
        if days_to_fomc is None or abs(diff) < abs(days_to_fomc):
            days_to_fomc = diff
            fomc_direction = "upcoming" if diff >= 0 else "past"
    is_fomc_window = days_to_fomc is not None and abs(days_to_fomc) <= 3
    is_fomc_day = days_to_fomc == 0

    # Options expiry week
    opex_dates = [e["date"] for e in events if e["event_type"] == "options_expiry"]
    is_opex_week = any(
        as_of - timedelta(days=as_of.weekday()) == od - timedelta(days=od.weekday())
        for od in opex_dates
    )

    # Triple witching week
    tw_dates = [e["date"] for e in events if e["event_type"] == "triple_witching"]
    is_triple_witching_week = any(
        as_of - timedelta(days=as_of.weekday()) == td - timedelta(days=td.weekday())
        for td in tw_dates
    )

    # Month-end (last 3 trading days of month) — approximate via day-of-month
    # A day is "month-end" if it's in the last 5 calendar days of the month
    import calendar
    last_day = calendar.monthrange(as_of.year, as_of.month)[1]
    is_month_end = as_of.day >= last_day - 4

    # Quarter-end
    qend_dates = [e["date"] for e in events if e["event_type"] == "quarter_end"]
    is_quarter_end = any(abs((qd - as_of).days) <= 5 for qd in qend_dates)

    # Next upcoming event (any type)
    future = sorted([e for e in events if e["date"] > as_of], key=lambda x: x["date"])
    next_event = None
    if future:
        nxt = future[0]
        next_event = {
            "type": nxt["event_type"],
            "date": nxt["date"].isoformat(),
            "days_away": (nxt["date"] - as_of).days,
            "description": nxt["description"],
        }

    return {
        "as_of": as_of.isoformat(),
        "days_to_fomc": days_to_fomc,
        "fomc_direction": fomc_direction,
        "is_fomc_window": is_fomc_window,
        "is_fomc_day": is_fomc_day,
        "is_opex_week": is_opex_week,
        "is_triple_witching_week": is_triple_witching_week,
        "is_month_end": is_month_end,
        "is_quarter_end": is_quarter_end,
        "next_event": next_event,
    }


def active_patterns(ctx: dict) -> list[str]:
    patterns = []
    if ctx["is_fomc_day"]:
        patterns.append("fomc_day")
    if ctx["is_fomc_window"]:
        patterns.append("fomc_proximity_3d")
    if ctx["is_opex_week"]:
        patterns.append("opex_week")
    if ctx["is_month_end"]:
        patterns.append("month_end_3d")
    if ctx["is_triple_witching_week"]:
        patterns.append("triple_witching_week")
    return patterns


def show_backtest_results(pattern_names: list[str]) -> None:
    if not pattern_names:
        return
    engine = get_raw_engine()
    with engine.connect() as conn:
        names_sql = ", ".join(f"'{n}'" for n in pattern_names)
        rows = conn.execute(text(f"""
            SELECT cp.name, cpr.horizon_days, cpr.sample_size,
                   cpr.hit_rate, cpr.avg_return, cpr.sharpe, cpr.p_value
            FROM conditional_pattern_results cpr
            JOIN conditional_patterns cp ON cp.id = cpr.pattern_id
            WHERE cp.name IN ({names_sql})
              AND cpr.ticker IS NULL
            ORDER BY cp.name, cpr.horizon_days
        """)).fetchall()

    if not rows:
        print("  (no backtest results yet — run with --run-backtests)")
        return

    current_pattern = None
    for r in rows:
        if r.name != current_pattern:
            print(f"\n  {r.name}")
            print(f"  {'Horizon':>8}  {'N':>6}  {'HitRate':>8}  {'AvgRet':>8}  {'Sharpe':>7}  {'p':>6}")
            print(f"  {'-'*54}")
            current_pattern = r.name
        hr = f"{r.hit_rate*100:.1f}%" if r.hit_rate is not None else "  —"
        ar = f"{r.avg_return*100:+.2f}%" if r.avg_return is not None else "  —"
        sh = f"{r.sharpe:.2f}" if r.sharpe is not None else "  —"
        pv = f"{r.p_value:.3f}" if r.p_value is not None else "  —"
        print(f"  {r.horizon_days:>6}d  {r.sample_size:>6}  {hr:>8}  {ar:>8}  {sh:>7}  {pv:>6}")


def run_backtests(pattern_names: list[str]) -> None:
    from atlas_research.conditional.engine import ConditionalEngine
    eng = ConditionalEngine()
    for name in pattern_names:
        print(f"  Running backtest: {name}...")
        try:
            n = eng.run_pattern(name)
            print(f"    → {n} signals found")
        except Exception as exc:
            print(f"    → ERROR: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calendar conditional context detector")
    parser.add_argument("--date", default=None, help="Reference date YYYY-MM-DD (default: today)")
    parser.add_argument("--run-backtests", action="store_true", help="Run backtests for all calendar patterns")
    parser.add_argument("--run-active-only", action="store_true", help="Only backtest currently active patterns")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.date) if args.date else date.today()
    events = load_events_window(as_of)
    ctx = build_calendar_context(as_of, events)

    print(f"\n{'='*60}")
    print(f"CALENDAR CONTEXT — {as_of.strftime('%A, %B %d, %Y')}")
    print(f"{'='*60}")

    # FOMC
    dtf = ctx["days_to_fomc"]
    if dtf is None:
        print("  FOMC:           no date found in DB")
    elif dtf == 0:
        print("  FOMC:           *** TODAY IS FOMC DAY ***")
    elif -3 <= dtf <= 3:
        direction = "in" if dtf > 0 else "ago"
        print(f"  FOMC:           {abs(dtf)} calendar days {direction} *** IN WINDOW ***")
    else:
        direction = "upcoming" if dtf > 0 else "past"
        print(f"  FOMC:           {abs(dtf)} calendar days away ({direction})")

    print(f"  OPEX week:      {'YES ✓' if ctx['is_opex_week'] else 'no'}")
    print(f"  Triple witch:   {'YES ✓' if ctx['is_triple_witching_week'] else 'no'}")
    print(f"  Month-end 3d:   {'YES ✓' if ctx['is_month_end'] else 'no'}")
    print(f"  Quarter-end:    {'YES ✓' if ctx['is_quarter_end'] else 'no'}")

    if ctx["next_event"]:
        ne = ctx["next_event"]
        print(f"\n  Next event:     {ne['type']}  ({ne['date']}, {ne['days_away']}d away)")
        print(f"                  {ne['description']}")

    ap = active_patterns(ctx)
    print(f"\n  Active patterns: {', '.join(ap) if ap else 'none'}")

    # Backtest results
    all_cal_patterns = [
        "fomc_day", "fomc_proximity_3d", "opex_week", "month_end_3d", "triple_witching_week"
    ]
    targets = ap if args.run_active_only else all_cal_patterns

    if args.run_backtests:
        print(f"\n{'='*60}")
        print("RUNNING BACKTESTS")
        print(f"{'='*60}")
        run_backtests(all_cal_patterns)  # always run all

    print(f"\n{'='*60}")
    print("BACKTEST RESULTS (aggregate, null-ticker)")
    print(f"{'='*60}")
    show_backtest_results(all_cal_patterns)
    print()


if __name__ == "__main__":
    main()
