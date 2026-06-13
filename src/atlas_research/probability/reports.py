"""
atlas_research.probability.reports
-------------------------------------
Console output formatting for backtest results.
"""

from __future__ import annotations

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
