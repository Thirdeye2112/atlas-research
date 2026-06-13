"""
atlas_research.probability.ipo.reports
-----------------------------------------
Formatted console output for IPO outcome studies.
"""

from __future__ import annotations

from typing import Optional


def _pct(v: Optional[float], dec: int = 1) -> str:
    if v is None:
        return "  N/A"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{dec}f}%"


def _days(v: Optional[float]) -> str:
    if v is None:
        return "  N/A"
    return f"{v:.0f}d"


def _n(v: Optional[int]) -> str:
    if v is None:
        return "  N/A"
    return f"{v}"


def print_event_summary(ev: dict) -> None:
    """Print a single IPO's computed metrics."""
    ticker   = ev.get("ticker", "?")
    ipo_date = ev.get("ipo_date", "?")
    lockup   = ev.get("lockup_expiration", "?")

    offer    = ev.get("offer_price")
    opening  = ev.get("opening_price")
    d1_close = ev.get("day1_close")

    print()
    print("=" * 62)
    print(f"  IPO EVENT — {ticker}  [{ipo_date}]")
    print("=" * 62)

    if offer:
        print(f"  Offer price:     ${offer:.2f}")
    if opening:
        print(f"  Opening price:   ${opening:.2f}   "
              f"({_pct(ev.get('open_vs_offer'))} vs offer)")
    if d1_close:
        print(f"  Day 1 close:     ${d1_close:.2f}   "
              f"({_pct(ev.get('close_vs_open'))} vs open)")

    print(f"  Day 1 range:     ${ev.get('day1_low', 0):.2f} – ${ev.get('day1_high', 0):.2f}")

    w1c = ev.get("week1_close")
    if w1c:
        print(f"  Week 1 close:    ${w1c:.2f}   ({_pct(ev.get('week1_return'))} vs open)")
        print(f"  Week 1 range:    ${ev.get('week1_low', 0):.2f} – ${ev.get('week1_high', 0):.2f}")

    m1c = ev.get("month1_close")
    if m1c:
        print(f"  Month 1 close:   ${m1c:.2f}   ({_pct(ev.get('month1_return'))} vs open)")

    print()
    print(f"  Peak expansion:  {_pct(ev.get('peak_vs_open'))} vs open  "
          f"(day {ev.get('days_to_peak', 'N/A')})")
    print(f"  Retracement:     {_pct(ev.get('retracement_from_peak'))} from peak")

    drvo = ev.get("days_to_revisit_open")
    drvo_str = f"{drvo}d" if drvo is not None else "Never (still above)"
    print(f"  Revisit open:    {drvo_str}")

    drvo2 = ev.get("days_to_revisit_offer")
    drvo2_str = f"{drvo2}d" if drvo2 is not None else "Never (still above)"
    print(f"  Revisit offer:   {drvo2_str}")

    print(f"  Lockup expiry:   {lockup}")
    print()


def print_revisit_overall(study_rows: list[dict]) -> None:
    open_row  = next((r for r in study_rows if r["study_name"] == "revisit_open_overall"),  None)
    offer_row = next((r for r in study_rows if r["study_name"] == "revisit_offer_overall"), None)

    n = open_row["n"] if open_row else "?"
    print()
    print("=" * 66)
    print("  IPO STUDY — REVISIT RATES")
    print(f"  Universe: {n} IPOs with opening price data")
    print("=" * 66)

    if open_row:
        print(f"  % revisit opening price:  {open_row.get('pct_positive', 'N/A')}%  "
              f"  median {_days(open_row.get('median_value'))}")
        print(f"     P25 {_days(open_row.get('p25_value'))}  "
              f"P75 {_days(open_row.get('p75_value'))}")

    if offer_row:
        print(f"  % revisit offer price:    {offer_row.get('pct_positive', 'N/A')}%  "
              f"  median {_days(offer_row.get('median_value'))}")
        print(f"     P25 {_days(offer_row.get('p25_value'))}  "
              f"P75 {_days(offer_row.get('p75_value'))}")
    print()


def print_revisit_by_gap(rows: list[dict]) -> None:
    if not rows:
        return
    print()
    print("  REVISIT OPEN — BY OPENING GAP BUCKET")
    print(f"  {'Bucket':<22}  {'N':>4}  {'% Revisit':>9}  {'Med Days':>8}  {'P25':>5}  {'P75':>5}")
    print("  " + "-" * 58)
    for r in rows:
        label  = r.get("bucket_label", r["bucket_name"])
        n      = r.get("n", 0)
        pct    = r.get("pct_positive")
        med    = r.get("median_value")
        p25    = r.get("p25_value")
        p75    = r.get("p75_value")
        pct_s  = f"{pct}%" if pct is not None else " N/A"
        med_s  = f"{med:.0f}d" if med is not None else "N/A"
        p25_s  = f"{p25:.0f}d" if p25 is not None else "N/A"
        p75_s  = f"{p75:.0f}d" if p75 is not None else "N/A"
        print(f"  {label:<22}  {n:>4}  {pct_s:>9}  {med_s:>8}  {p25_s:>5}  {p75_s:>5}")
    print()


def print_day1_range(rows: list[dict]) -> None:
    if not rows:
        return
    n = rows[0]["n"] if rows else 0
    print(f"  DAY 1 CLOSE vs OPEN  (n={n})")
    print(f"  {'Condition':<30}  {'Count':>6}  {'%':>6}  {'Median':>7}  {'P25':>7}  {'P75':>7}")
    print("  " + "-" * 66)
    for r in rows:
        cnt_frac = round(r.get("pct_positive", 0) * n / 100) if r.get("pct_positive") else 0
        print(
            f"  {r.get('bucket_label', r['bucket_name']):<30}  {cnt_frac:>6}"
            f"  {r.get('pct_positive', 0):>5.1f}%"
            f"  {_pct(r.get('median_value')):>7}"
            f"  {_pct(r.get('p25_value')):>7}"
            f"  {_pct(r.get('p75_value')):>7}"
        )
    print()


def print_peak_expansion(rows: list[dict]) -> None:
    if not rows:
        return
    print("  PEAK EXPANSION ANALYSIS")
    print(f"  {'Bucket':<26}  {'N':>4}  {'Med DayPeak':>11}  "
          f"{'Avg Retrace':>11}  {'P25 Retrace':>11}  {'P75 Retrace':>11}  {'%RevOpen':>8}")
    print("  " + "-" * 86)
    for r in rows:
        label = r.get("bucket_label", r["bucket_name"])
        print(
            f"  {label:<26}  {r.get('n', 0):>4}"
            f"  {_days(r.get('median_value')):>11}"
            f"  {_pct(r.get('avg_value')):>11}"
            f"  {_pct(r.get('p25_value')):>11}"
            f"  {_pct(r.get('p75_value')):>11}"
            f"  {str(r.get('pct_positive', 'N/A')) + '%':>8}"
        )
    print()


def print_week1_momentum(rows: list[dict]) -> None:
    if not rows:
        return
    print("  WEEK 1 MOMENTUM → FUTURE OUTCOMES")
    print(f"  {'Week1 Return':<26}  {'N':>4}  "
          f"{'Med Post-20d':>12}  {'P25':>7}  {'P75':>7}  {'Avg Retrace':>11}")
    print("  " + "-" * 76)
    for r in rows:
        label = r.get("bucket_label", r["bucket_name"])
        print(
            f"  {label:<26}  {r.get('n', 0):>4}"
            f"  {_pct(r.get('median_value')):>12}"
            f"  {_pct(r.get('p25_value')):>7}"
            f"  {_pct(r.get('p75_value')):>7}"
            f"  {_pct(r.get('avg_value')):>11}"
        )
    print()


def print_month1_momentum(rows: list[dict]) -> None:
    if not rows:
        return
    print("  MONTH 1 MOMENTUM → EVENTUAL RETRACEMENT")
    print(f"  {'Month1 Return':<26}  {'N':>4}  "
          f"{'Med Retrace':>11}  {'P25':>7}  {'P75':>7}  {'%RevOpen':>8}")
    print("  " + "-" * 72)
    for r in rows:
        label = r.get("bucket_label", r["bucket_name"])
        print(
            f"  {label:<26}  {r.get('n', 0):>4}"
            f"  {_pct(r.get('median_value')):>11}"
            f"  {_pct(r.get('p25_value')):>7}"
            f"  {_pct(r.get('p75_value')):>7}"
            f"  {str(r.get('pct_positive', 'N/A')) + '%':>8}"
        )
    print()


def print_all_studies(study_results: dict[str, list[dict]]) -> None:
    """Print all study results in a single formatted report."""
    # Combine revisit_open_overall + revisit_offer_overall
    overall = (
        study_results.get("revisit_open_overall", []) +
        study_results.get("revisit_offer_overall", [])
    )
    print_revisit_overall(overall)
    print_revisit_by_gap(study_results.get("revisit_open_by_gap", []))
    print_day1_range(study_results.get("day1_close_range", []))
    print_peak_expansion(study_results.get("peak_expansion", []))
    print_week1_momentum(study_results.get("week1_momentum", []))
    print_month1_momentum(study_results.get("month1_momentum", []))
