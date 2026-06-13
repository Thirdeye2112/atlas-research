"""
atlas_research.probability.reports
-------------------------------------
Console output formatting for backtest results.

Includes print_signal_report() which reads from DB and produces a
three-section report: PROMOTED / CANDIDATE / REJECTED.
"""

from __future__ import annotations

import json
from typing import Optional

from .outcomes import HORIZONS


def _pct(v: float | None, decimals: int = 1) -> str:
    if v is None:
        return "   N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def _rate(v: float | None) -> str:
    if v is None:
        return " N/A"
    return f"{v * 100:.0f}%"


def print_report(result: dict) -> None:
    ticker         = result["ticker"]
    condition_type = result["condition_type"]
    params         = result["params"]
    events         = result["events"]
    stats          = result["stats"]
    data_start     = result.get("data_start", "?")
    data_end       = result.get("data_end", "?")

    param_str = "  ".join(f"{k}={v}" for k, v in params.items())
    label     = f"{ticker} — {condition_type.upper().replace('_', ' ')}  [{param_str}]"

    print()
    print("=" * 72)
    print(f"  {label}")
    print("=" * 72)
    print(f"  Signals:    {len(events)} occurrences")
    print(f"  Data range: {data_start} → {data_end}")

    if not events:
        print("  No signal occurrences found.")
        print()
        return

    recent = sorted(events, key=lambda e: e["signal_date"], reverse=True)[:5]
    dates_str = "  ".join(str(e["signal_date"]) for e in recent)
    print(f"  Recent:     {dates_str}")
    print()

    hdr = f"  {'Horizon':<8}  {'N':>4}  {'Hit%':>5}  {'Avg':>7}  {'Med':>7}  {'P25':>7}  {'P75':>7}  {'Runup':>7}  {'MaxDD':>7}"
    print(hdr)
    print("  " + "-" * 66)

    for h in HORIZONS:
        s = stats.get(h, {})
        n = s.get("n", 0)
        if n == 0:
            continue
        print(
            f"  {str(h) + 'd':<8}  {n:>4}  {_rate(s.get('hit_rate')):>5}"
            f"  {_pct(s.get('avg_return')):>7}"
            f"  {_pct(s.get('median_return')):>7}"
            f"  {_pct(s.get('p25_return')):>7}"
            f"  {_pct(s.get('p75_return')):>7}"
            f"  {_pct(s.get('avg_max_runup')):>7}"
            f"  {_pct(s.get('avg_max_dd')):>7}"
        )

    print()


def _classify_signal(n: int, avg5: Optional[float], promoted: bool) -> str:
    """
    Three-tier classification:
      promoted   — passed all criteria
      candidate  — positive direction but not enough sample or narrowly below threshold
      rejected   — negative or zero edge
    """
    if promoted:
        return "promoted"
    if avg5 is None or avg5 <= 0:
        return "rejected"
    if n < 30:
        return "candidate"    # small sample, positive direction
    return "candidate"        # large sample but narrowly failed threshold


def print_signal_report(ticker: Optional[str] = None) -> None:
    """
    Full signal report from DB — promoted / candidate / rejected sections,
    each promoted signal with per-year breakdown.

    Parameters
    ----------
    ticker : if given, filter to this ticker; otherwise report all tickers
    """
    from sqlalchemy import text
    from atlas_research.db.connection import get_connection
    from .robustness import load_yearly_breakdown_from_db, print_yearly_breakdown

    where = "WHERE ts.ticker = :t" if ticker else ""
    bind  = {"t": ticker.upper()} if ticker else {}

    with get_connection() as conn:
        rows = conn.execute(text(f"""
            SELECT
                ts.id               AS spec_id,
                ts.ticker,
                ts.condition_type,
                ts.params,
                br.n_events,
                br.promoted,
                br.promoted_at,
                bres5.hit_rate      AS hr5,
                bres5.avg_return    AS avg5,
                bres5.median_return AS med5,
                bres20.hit_rate     AS hr20,
                bres20.avg_return   AS avg20
            FROM test_specifications ts
            JOIN LATERAL (
                SELECT * FROM backtest_runs
                WHERE spec_id = ts.id
                ORDER BY run_date DESC, id DESC
                LIMIT 1
            ) br ON TRUE
            LEFT JOIN backtest_results bres5
                ON bres5.run_id = br.id AND bres5.horizon_days = 5
            LEFT JOIN backtest_results bres20
                ON bres20.run_id = br.id AND bres20.horizon_days = 20
            {where}
            ORDER BY ts.ticker, ts.condition_type, ts.params
        """), bind).fetchall()

    if not rows:
        subject = f"ticker {ticker}" if ticker else "any ticker"
        print(f"\n  No backtest runs found for {subject}.")
        return

    # ── Classify ──────────────────────────────────────────────────────────────
    promoted_rows:  list[tuple] = []
    candidate_rows: list[tuple] = []
    rejected_rows:  list[tuple] = []

    for row in rows:
        n       = row[4] or 0
        promo   = bool(row[5])
        avg5    = float(row[8]) if row[8] is not None else None
        tier    = _classify_signal(n, avg5, promo)

        if tier == "promoted":
            promoted_rows.append(row)
        elif tier == "candidate":
            candidate_rows.append(row)
        else:
            rejected_rows.append(row)

    title = f"SIGNAL REPORT — {ticker}" if ticker else "SIGNAL REPORT — ALL"
    print()
    print("=" * 72)
    print(f"  {title}")
    print(f"  {len(rows)} spec(s): "
          f"{len(promoted_rows)} promoted, "
          f"{len(candidate_rows)} candidate, "
          f"{len(rejected_rows)} rejected")
    print("=" * 72)

    def _row_summary(row) -> str:
        n     = row[4] or 0
        hr5   = (row[7] or 0) * 100
        avg5  = row[8] or 0
        hr20  = (row[10] or 0) * 100
        avg20 = row[11] or 0
        ps    = json.loads(row[3])
        ctype = row[2].replace("_", " ")
        ptag  = " ".join(f"{k}={v}" for k, v in ps.items())
        t     = row[1]
        return (
            f"{t} {ctype} [{ptag}]",
            n, hr5, avg5, hr20, avg20,
        )

    COL_HDR = (
        f"  {'Spec':<36}  {'N':>4}  "
        f"{'Hit5d':>6}  {'Avg5d':>7}  "
        f"{'Hit20d':>6}  {'Avg20d':>7}"
    )
    DIVIDER = "  " + "-" * 70

    # ── PROMOTED ──────────────────────────────────────────────────────────────
    print()
    print(f"  ── PROMOTED SIGNALS  ({len(promoted_rows)} specs) ──────────────────────────────")
    if promoted_rows:
        print(COL_HDR)
        print(DIVIDER)
        for row in promoted_rows:
            lbl, n, hr5, avg5, hr20, avg20 = _row_summary(row)
            print(
                f"  {lbl:<36}  {n:>4}  "
                f"{hr5:>5.1f}%  {avg5:>+7.2f}%  "
                f"{hr20:>5.1f}%  {avg20:>+7.2f}%"
            )
            spec_id = row[0]
            try:
                breakdown = load_yearly_breakdown_from_db(spec_id, horizon=5)
                print_yearly_breakdown(breakdown)
            except Exception:
                pass
    else:
        print("  (none)")

    # ── CANDIDATE ─────────────────────────────────────────────────────────────
    print()
    print(f"  ── CANDIDATE SIGNALS  ({len(candidate_rows)} specs, positive direction) ──────────")
    if candidate_rows:
        print(COL_HDR)
        print(DIVIDER)
        for row in candidate_rows:
            lbl, n, hr5, avg5, hr20, avg20 = _row_summary(row)
            note = "[small sample: n<30]" if n < 30 else "[marginal: below threshold]"
            print(
                f"  {lbl:<36}  {n:>4}  "
                f"{hr5:>5.1f}%  {avg5:>+7.2f}%  "
                f"{hr20:>5.1f}%  {avg20:>+7.2f}%  {note}"
            )
    else:
        print("  (none)")

    # ── REJECTED ──────────────────────────────────────────────────────────────
    print()
    print(f"  ── REJECTED SIGNALS  ({len(rejected_rows)} specs, negative or zero edge) ────────")
    if rejected_rows:
        print(COL_HDR)
        print(DIVIDER)
        for row in rejected_rows:
            lbl, n, hr5, avg5, hr20, avg20 = _row_summary(row)
            reasons = []
            if n < 30:
                reasons.append(f"n={n}<30")
            if avg5 <= 0:
                reasons.append("negative 5d avg")
            note = "; ".join(reasons)
            print(
                f"  {lbl:<36}  {n:>4}  "
                f"{hr5:>5.1f}%  {avg5:>+7.2f}%  "
                f"{hr20:>5.1f}%  {avg20:>+7.2f}%  [{note}]"
            )
    else:
        print("  (none)")

    print()


def print_comparison(results: list[dict]) -> None:
    """Compact summary table across multiple conditions — 5d and 20d columns."""
    if not results:
        return

    ticker = results[0]["ticker"]
    print()
    print(f"  {ticker} — COMPARISON  (5d and 20d forward returns)")
    print("  " + "=" * 72)
    print(f"  {'Condition':<38}  {'N':>4}  {'5d Hit':>6}  {'5d Avg':>7}  {'20d Hit':>7}  {'20d Avg':>7}")
    print("  " + "-" * 72)

    for r in results:
        params   = r["params"]
        ctype    = r["condition_type"].replace("_", " ")
        pstr     = "  ".join(f"{k}={v}" for k, v in params.items())
        label    = f"{ctype} [{pstr}]"

        s5  = r["stats"].get(5, {})
        s20 = r["stats"].get(20, {})

        print(
            f"  {label:<38}  {r['n_events']:>4}"
            f"  {_rate(s5.get('hit_rate')):>6}  {_pct(s5.get('avg_return')):>7}"
            f"  {_rate(s20.get('hit_rate')):>7}  {_pct(s20.get('avg_return')):>7}"
        )

    print()
