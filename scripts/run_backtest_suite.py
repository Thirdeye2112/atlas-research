"""
run_backtest_suite.py — Canonical backtest suite runner.

Runs condition specs in parallel via ProcessPoolExecutor and writes
aggregate results to conditional_pattern_results.

Usage
-----
    python scripts/run_backtest_suite.py --suite core
    python scripts/run_backtest_suite.py --suite patterns
    python scripts/run_backtest_suite.py --suite omni
    python scripts/run_backtest_suite.py --suite all
    python scripts/run_backtest_suite.py --suite core --validate
    python scripts/run_backtest_suite.py --suite core --workers 8
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from atlas_research.backtest import BacktestEngine, ConditionSpec, OutcomeSpec, BacktestResult
from atlas_research.backtest.runner import run_suite


# ── Suite definitions ─────────────────────────────────────────────────────────

CORE_SPECS: list[ConditionSpec] = [
    # SPY directional streaks
    ConditionSpec("consecutive_down", {"n_days": 2}, universe="SPY", name="spy_down_2d"),
    ConditionSpec("consecutive_down", {"n_days": 3}, universe="SPY", name="spy_down_3d"),
    ConditionSpec("consecutive_down", {"n_days": 4}, universe="SPY", name="spy_down_4d"),
    ConditionSpec("consecutive_down", {"n_days": 5}, universe="SPY", name="spy_down_5d"),
    ConditionSpec("consecutive_up",   {"n_days": 3}, universe="SPY", name="spy_up_3d"),
    ConditionSpec("consecutive_up",   {"n_days": 4}, universe="SPY", name="spy_up_4d"),
    ConditionSpec("consecutive_up",   {"n_days": 5}, universe="SPY", name="spy_up_5d"),
    # SPY gaps
    ConditionSpec("gap_down", {"min_gap_pct": 0.5}, universe="SPY", name="spy_gap_down_0.5pct"),
    ConditionSpec("gap_down", {"min_gap_pct": 1.0}, universe="SPY", name="spy_gap_down_1pct"),
    ConditionSpec("gap_down", {"min_gap_pct": 2.0}, universe="SPY", name="spy_gap_down_2pct"),
    ConditionSpec("gap_up",   {"min_gap_pct": 0.5}, universe="SPY", name="spy_gap_up_0.5pct"),
    ConditionSpec("gap_up",   {"min_gap_pct": 1.0}, universe="SPY", name="spy_gap_up_1pct"),
    # Calendar
    ConditionSpec("end_of_month",  {"n_days": 3}, universe="SPY", name="month_end_3d"),
    ConditionSpec("turn_of_month", {"n_days": 3}, universe="SPY", name="month_turn_3d"),
    ConditionSpec("opex_week",     {},            universe="SPY", name="opex_week"),
    # RSI extremes
    ConditionSpec("oversold_rsi",   {"threshold": 30}, universe="SPY", name="spy_rsi_oversold_30"),
    ConditionSpec("overbought_rsi", {"threshold": 70}, universe="SPY", name="spy_rsi_overbought_70"),
    # Volatility
    ConditionSpec("nr7", {"lookback": 7}, universe="SPY", name="spy_nr7"),
    # Sector rotation
    ConditionSpec("sector_leading_nd", {"sector_ticker": "XLV", "rank_threshold": 2, "n_days": 20},
                  universe="SPY", name="xlv_leading_20d"),
    ConditionSpec("xly_vs_xlp", {}, universe="SPY", name="xly_vs_xlp"),
]

PATTERNS_SPECS: list[ConditionSpec] = [
    # All-universe candlestick patterns
    ConditionSpec("candle", {"pattern": "bullish_engulfing"},  universe="ALL", name="bullish_engulfing"),
    ConditionSpec("candle", {"pattern": "bearish_engulfing"},  universe="ALL", name="bearish_engulfing"),
    ConditionSpec("candle", {"pattern": "hammer"},             universe="ALL", name="hammer"),
    ConditionSpec("candle", {"pattern": "shooting_star"},      universe="ALL", name="shooting_star"),
    ConditionSpec("candle", {"pattern": "doji"},               universe="ALL", name="doji"),
    ConditionSpec("candle", {"pattern": "inside_day"},         universe="ALL", name="inside_day"),
    ConditionSpec("candle", {"pattern": "outside_day"},        universe="ALL", name="outside_day"),
    # SPY-specific patterns
    ConditionSpec("candle", {"pattern": "bullish_engulfing"},  universe="SPY", name="spy_bullish_engulfing"),
    ConditionSpec("candle", {"pattern": "inside_day"},         universe="SPY", name="spy_inside_day"),
    # Volume patterns
    ConditionSpec("volume_climax_down", {"multiplier": 2.0}, universe="ALL", name="vol_climax_down_2x"),
    ConditionSpec("volume_climax_up",   {"multiplier": 2.0}, universe="ALL", name="vol_climax_up_2x"),
    ConditionSpec("high_volume",        {"multiplier": 3.0}, universe="ALL", name="high_volume_3x"),
    # Compression / expansion
    ConditionSpec("nr7", {"lookback": 7},  universe="ALL", name="nr7_all"),
    # Gap patterns (all universe)
    ConditionSpec("gap_down", {"min_gap_pct": 2.0}, universe="ALL", name="gap_down_2pct_all"),
    ConditionSpec("gap_up",   {"min_gap_pct": 2.0}, universe="ALL", name="gap_up_2pct_all"),
    # Near extremes
    ConditionSpec("near_52w_low",      {"within_pct": 5.0}, universe="ALL", name="near_52w_low_5pct"),
    ConditionSpec("breakout_52w_high", {},                   universe="ALL", name="breakout_52w_high"),
]

OMNI_SPECS: list[ConditionSpec] = [
    # EMA-lows (OMNI) — SPY reference
    ConditionSpec("ema_lows_cross_up",   {"period": 82}, universe="SPY", name="spy_ema_lows_82_cross_up"),
    ConditionSpec("ema_lows_cross_down", {"period": 82}, universe="SPY", name="spy_ema_lows_82_cross_down"),
    ConditionSpec("ema_lows_above_nd",   {"period": 82, "n_days": 3}, universe="SPY", name="spy_omni_green_3d"),
    ConditionSpec("ema_lows_green_slope",{"period": 82, "slope_bars": 5}, universe="SPY", name="spy_omni_green_slope"),
    # OMNI cross all-universe
    ConditionSpec("ema_lows_cross_up",   {"period": 82}, universe="ALL", name="omni_82_cross_up_all"),
    ConditionSpec("ema_lows_cross_down", {"period": 82}, universe="ALL", name="omni_82_cross_down_all"),
    # Oscar
    ConditionSpec("oscar_cross_up",   {"period": 87}, universe="SPY", name="spy_oscar_cross_up"),
    ConditionSpec("oscar_cross_down", {"period": 87}, universe="SPY", name="spy_oscar_cross_down"),
    ConditionSpec("oscar_above_50",   {"period": 87}, universe="SPY", name="spy_oscar_above_50"),
    # HMA
    ConditionSpec("hma_cross_up",   {"period": 87}, universe="SPY", name="spy_hma_cross_up"),
    ConditionSpec("hma_cross_down", {"period": 87}, universe="SPY", name="spy_hma_cross_down"),
]

SUITE_MAP: dict[str, list[ConditionSpec]] = {
    "core":     CORE_SPECS,
    "patterns": PATTERNS_SPECS,
    "omni":     OMNI_SPECS,
    "all":      CORE_SPECS + PATTERNS_SPECS + OMNI_SPECS,
}


# ── Validation ────────────────────────────────────────────────────────────────

VALIDATION_CASES = [
    ("spy_down_4d",        "SPY", "consecutive_down", {"n_days": 4},             5),
    ("gap_down_1pct",      "SPY", "gap_down",         {"min_gap_pct": 1.0},      5),
    ("bullish_engulfing",  "SPY", "candle",           {"pattern": "bullish_engulfing"}, 5),
    ("inside_day",         "SPY", "candle",           {"pattern": "inside_day"},  5),
]


def run_validation(engine: BacktestEngine) -> bool:
    """Compare new engine results against stored conditional_pattern_results."""
    from sqlalchemy import text
    from atlas_research.db.connection import get_raw_engine

    db = get_raw_engine()
    print(f"\n{'Validation: canonical engine vs stored results':^72}")
    print("─" * 72)
    print(f"  {'Pattern':<28} {'Hz':>3}  {'Stored%':>8}  {'New%':>8}  {'Delta':>7}  Status")
    print("  " + "─" * 68)

    all_pass = True
    TOLERANCE = 1.5  # percentage points

    for label, ticker, ctype, params, horizon in VALIDATION_CASES:
        # New engine result
        result = engine.run(ticker=ticker, condition_type=ctype, params=params,
                            horizons=[horizon])
        new_hr = result.stats.get(horizon, {}).get("hit_rate")
        new_n  = result.stats.get(horizon, {}).get("n", 0)

        # Stored result (from conditional_pattern_results)
        with db.connect() as conn:
            row = conn.execute(text("""
                SELECT r.hit_rate, r.sample_size
                FROM conditional_pattern_results r
                JOIN conditional_patterns cp ON cp.id = r.pattern_id
                WHERE cp.name ILIKE :pat
                  AND r.horizon_days = :h
                  AND r.ticker IS NULL
                ORDER BY r.evaluated_at DESC
                LIMIT 1
            """), {"pat": f"%{label.replace('_', '%')}%", "h": horizon}).fetchone()

        if row and row[0] is not None:
            stored_hr = float(row[0])
            stored_n  = row[1]
            if new_hr is not None:
                delta    = (new_hr - stored_hr) * 100
                passed   = abs(delta) <= TOLERANCE
                status   = "PASS" if passed else "FAIL"
                if not passed:
                    all_pass = False
                print(f"  {label:<28} {horizon:>3}d  "
                      f"{stored_hr*100:>7.1f}%  {new_hr*100:>7.1f}%  "
                      f"{delta:>+6.1f}pp  {status}")
            else:
                print(f"  {label:<28} {horizon:>3}d  "
                      f"{stored_hr*100:>7.1f}%  {'n/a':>8}  {'n/a':>7}  SKIP (no new data)")
        else:
            # No stored result — just show new
            hr_str = f"{new_hr*100:.1f}%" if new_hr is not None else "n/a"
            print(f"  {label:<28} {horizon:>3}d  {'no stored':>8}  {hr_str:>8}  "
                  f"{'n/a':>7}  INFO (no prior)")

    print()
    verdict = "ALL PASS" if all_pass else "SOME FAIL — check delta > 1.5pp"
    print(f"  Validation result: {verdict}")
    print()
    return all_pass


# ── DB persistence for suite results ─────────────────────────────────────────

def _persist_result(result: BacktestResult, engine_db) -> None:
    """Write aggregate stats to conditional_pattern_results (best-effort)."""
    from sqlalchemy import text

    for horizon, stats in result.stats.items():
        n = stats.get("n", 0)
        if n < 10:
            continue
        try:
            with engine_db.begin() as conn:
                # Upsert by pattern name + horizon (no pattern_id for suite results)
                conn.execute(text("""
                    INSERT INTO conditional_pattern_results
                        (pattern_id, ticker, horizon_days, sample_size, hit_rate,
                         avg_return, median_return, std_return, sharpe, p_value, evaluated_at)
                    SELECT
                        COALESCE((SELECT id FROM conditional_patterns WHERE name = :name LIMIT 1), -1),
                        NULL, :horizon, :n, :hr, :avg, :med, :std, :sh, :pv, now()
                    ON CONFLICT (pattern_id, COALESCE(ticker,''), horizon_days)
                    DO UPDATE SET
                        sample_size   = EXCLUDED.sample_size,
                        hit_rate      = EXCLUDED.hit_rate,
                        avg_return    = EXCLUDED.avg_return,
                        median_return = EXCLUDED.median_return,
                        std_return    = EXCLUDED.std_return,
                        sharpe        = EXCLUDED.sharpe,
                        p_value       = EXCLUDED.p_value,
                        evaluated_at  = now()
                """), {
                    "name":    result.name or result.condition_type,
                    "horizon": horizon,
                    "n":       n,
                    "hr":      stats.get("hit_rate"),
                    "avg":     stats.get("avg_return"),
                    "med":     stats.get("median_return"),
                    "std":     stats.get("std_return"),
                    "sh":      stats.get("sharpe"),
                    "pv":      stats.get("p_value"),
                })
        except Exception:
            pass  # pattern_id=-1 may not exist; non-fatal


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas canonical backtest suite runner")
    parser.add_argument("--suite",    choices=["core", "patterns", "omni", "all"],
                        default="core", help="Which suite to run")
    parser.add_argument("--validate", action="store_true",
                        help="Compare new results against stored results")
    parser.add_argument("--workers",  type=int, default=4,
                        help="Parallel worker processes (default 4)")
    parser.add_argument("--no-db",    action="store_true",
                        help="Skip writing results to DB")
    args = parser.parse_args()

    specs = SUITE_MAP[args.suite]
    print(f"\nAtlas Backtest Suite — {args.suite.upper()}")
    print(f"  Specs:   {len(specs)}")
    print(f"  Workers: {args.workers}")
    print()

    engine = BacktestEngine()

    # Optional validation first (serial, uses stored DB values)
    if args.validate:
        run_validation(engine)

    # Parallel execution
    t0 = time.monotonic()
    outcome = OutcomeSpec(horizons=[1, 5, 10, 20], runup_windows=[5, 10, 20])

    if args.no_db:
        write_cb = None
    else:
        from atlas_research.db.connection import get_raw_engine
        db = get_raw_engine()
        def write_cb(r: BacktestResult) -> None:
            _persist_result(r, db)

    results = run_suite(specs, outcome=outcome, n_workers=args.workers,
                        on_result=write_cb, verbose=True)

    elapsed = time.monotonic() - t0

    # Summary
    print(f"\n{'Suite Results':^72}")
    print("─" * 72)
    print(f"  {'Name':<36} {'n':>6}  {'5d HR':>6}  {'5d Avg':>7}  {'5d p':>7}")
    print("  " + "─" * 68)
    for r in results:
        s5   = r.stats.get(5, {})
        n    = s5.get("n", 0)
        hr   = s5.get("hit_rate")
        avg  = s5.get("avg_return")
        pv   = s5.get("p_value")
        label = r.name or r.condition_type
        hr_str  = f"{hr*100:.1f}%"  if hr  is not None else "n/a"
        avg_str = f"{avg:+.2f}%"    if avg is not None else "n/a"
        pv_str  = f"{pv:.3f}"       if pv  is not None else "n/a"
        print(f"  {label:<36} {n:>6}  {hr_str:>6}  {avg_str:>7}  {pv_str:>7}")

    print(f"\n  Total: {len(results)} specs | {elapsed:.1f}s elapsed")

    # Runtime comparison note
    serial_est = elapsed * args.workers if args.workers > 1 else elapsed
    if args.workers > 1:
        print(f"  Serial estimate: ~{serial_est:.0f}s  |  Speedup: ~{serial_est/elapsed:.1f}x")


if __name__ == "__main__":
    main()
