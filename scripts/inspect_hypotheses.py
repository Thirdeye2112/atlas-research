#!/usr/bin/env python
"""
scripts/inspect_hypotheses.py
================================
Inspection tool for the Transcript Intelligence Pipeline.

Sections
--------
1. Pipeline health (source / chunk / hypothesis counts)
2. Hypothesis queue status
3. Top-ranked backtest results
4. Promoted features
5. Individual hypothesis detail (--hypothesis-id)

Usage
-----
    python scripts/inspect_hypotheses.py
    python scripts/inspect_hypotheses.py --top 20
    python scripts/inspect_hypotheses.py --hypothesis-id <uuid>
    python scripts/inspect_hypotheses.py --promoted
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import configure_logging


def section(title: str) -> None:
    print()
    print("─" * 64)
    print(f"  {title}")
    print("─" * 64)


def fmt(v, decimals: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


# ---------------------------------------------------------------------------
# Section 1: Pipeline health
# ---------------------------------------------------------------------------

def inspect_pipeline_health() -> None:
    section("PIPELINE HEALTH")
    with get_connection() as conn:
        src = conn.execute(text(
            "SELECT COUNT(*), COUNT(processed_at) FROM transcript_sources"
        )).fetchone()
        chunks = conn.execute(text("SELECT COUNT(*) FROM transcript_chunks")).scalar()
        hyp_total = conn.execute(text("SELECT COUNT(*) FROM research_hypotheses")).scalar()
        results = conn.execute(text("SELECT COUNT(*) FROM hypothesis_results")).scalar()
        promoted = conn.execute(text("SELECT COUNT(*) FROM promoted_features")).scalar()

    print(f"  Sources:          {src[1]:>6} processed  /  {src[0]:>6} total")
    print(f"  Chunks:           {chunks:>6}")
    print(f"  Hypotheses:       {hyp_total:>6}")
    print(f"  Backtest results: {results:>6}")
    print(f"  Promoted:         {promoted:>6}")

    with get_connection() as conn:
        status_rows = conn.execute(text("""
            SELECT test_status, COUNT(*)
            FROM research_hypotheses
            GROUP BY test_status ORDER BY test_status
        """)).fetchall()

    print()
    print("  Hypothesis status breakdown:")
    for status, count in status_rows:
        bar = "█" * min(count, 40)
        print(f"    {status:<12}  {count:>5}  {bar}")


# ---------------------------------------------------------------------------
# Section 2: Queue
# ---------------------------------------------------------------------------

def inspect_queue() -> None:
    section("HYPOTHESIS QUEUE")
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT h.hypothesis_id, h.market_object, h.condition,
                   h.confidence_prior, h.created_at
            FROM research_hypotheses h
            WHERE test_status = 'queued'
            ORDER BY confidence_prior DESC, created_at ASC
            LIMIT 20
        """)).fetchall()

    if not rows:
        print("  Queue is empty.")
        return

    print(f"  {'ID':<38} {'Object':<12} {'Condition':<30} {'Prior':>6}")
    print("  " + "─" * 92)
    for r in rows:
        print(f"  {r[0]:<38} {(r[1] or '—'):<12} {(r[2] or '—'):<30} {fmt(r[3]):>6}")


# ---------------------------------------------------------------------------
# Section 3: Top backtest results
# ---------------------------------------------------------------------------

def inspect_top_results(top_n: int = 15) -> None:
    section(f"TOP {top_n} BACKTEST RESULTS")
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT
                h.extracted_claim,
                h.market_object,
                h.condition,
                r.horizon_days,
                r.sample_size,
                r.hit_rate,
                r.avg_return,
                r.sharpe,
                r.p_value,
                r.rank_ic,
                r.composite_score,
                h.promoted,
                h.hypothesis_id
            FROM hypothesis_results r
            JOIN research_hypotheses h ON h.hypothesis_id = r.hypothesis_id
            WHERE r.sample_size >= 15
            ORDER BY r.composite_score DESC NULLS LAST
            LIMIT :n
        """), {"n": top_n}).fetchall()

    if not rows:
        print("  No backtest results yet.")
        return

    header = f"  {'Claim':<42} {'Obj':<8} {'Hz':>3} {'n':>5} {'HR':>5} {'Ret%':>6} {'Sh':>6} {'p':>6} {'Score':>6} {'Prom':>4}"
    print(header)
    print("  " + "─" * len(header))

    for r in rows:
        claim    = (r[0] or "")[:41]
        obj      = (r[1] or "—")[:7]
        hz       = r[3]
        n        = r[4]
        hr       = fmt(r[5])
        avg_ret  = f"{(r[6] or 0)*100:>5.2f}"
        sh       = fmt(r[7], 2)
        pval     = fmt(r[8], 4)
        score    = fmt(r[10])
        prom     = "✓" if r[11] else " "
        print(f"  {claim:<42} {obj:<8} {hz:>3} {n:>5} {hr:>5} {avg_ret}% {sh:>6} {pval:>6} {score:>6} {prom:>4}")


# ---------------------------------------------------------------------------
# Section 4: Promoted features
# ---------------------------------------------------------------------------

def inspect_promoted() -> None:
    section("PROMOTED FEATURES")
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT feature_name, feature_description, feature_category,
                   best_horizon_days, best_hit_rate, best_rank_ic,
                   best_sharpe, sample_size, p_value,
                   promotion_status, promoted_at
            FROM promoted_features
            ORDER BY promoted_at DESC
        """)).fetchall()

    if not rows:
        print("  No promoted features yet.")
        return

    for r in rows:
        print(f"\n  Feature: {r[0]}")
        print(f"    Description: {(r[1] or '—')[:80]}")
        print(f"    Category:    {r[2]}   Status: {r[9]}")
        print(f"    Horizon:     {r[3]}d   Hit rate: {fmt(r[4])}   "
              f"Rank IC: {fmt(r[5])}   Sharpe: {fmt(r[6], 2)}")
        print(f"    Sample:      {r[7]}   p-value: {fmt(r[8], 4)}")


# ---------------------------------------------------------------------------
# Section 5: Individual hypothesis detail
# ---------------------------------------------------------------------------

def inspect_hypothesis(hid: str) -> None:
    section(f"HYPOTHESIS DETAIL: {hid[:16]}…")
    with get_connection() as conn:
        hyp = conn.execute(text("""
            SELECT h.*, s.file_path, s.event_date
            FROM research_hypotheses h
            LEFT JOIN transcript_sources s ON s.source_id = h.source_id
            WHERE h.hypothesis_id = :hid
        """), {"hid": hid}).mappings().fetchone()

    if not hyp:
        print(f"  Hypothesis {hid} not found.")
        return

    print(f"  Claim:      {hyp['extracted_claim']}")
    print(f"  Source:     {hyp.get('file_path', '—')}")
    print(f"  Object:     {hyp['market_object']}   Condition: {hyp['condition']}")
    print(f"  Direction:  {hyp['direction']}   Regime: {hyp.get('regime_filter') or 'all'}")
    print(f"  Status:     {hyp['test_status']}   Promoted: {hyp['promoted']}")
    if hyp.get("skip_reason"):
        print(f"  Skip reason: {hyp['skip_reason']}")

    print(f"\n  Source text excerpt:")
    excerpt = (hyp.get("source_text") or "")[:300]
    for line in excerpt.split("\n"):
        print(f"    {line}")

    with get_connection() as conn:
        results = conn.execute(text("""
            SELECT r.horizon_days, r.sample_size, r.hit_rate, r.avg_return,
                   r.sharpe, r.p_value, r.composite_score, r.regime_breakdown
            FROM hypothesis_results r
            JOIN hypothesis_tests t ON t.id = r.test_id
            WHERE r.hypothesis_id = :hid
            ORDER BY r.horizon_days
        """), {"hid": hid}).fetchall()

    if results:
        print(f"\n  Backtest results:")
        print(f"    {'Hz':>3} {'n':>5} {'HR':>5} {'Ret%':>6} {'Sh':>6} {'p':>6} {'Score':>6}")
        for r in results:
            avg_ret = f"{(r[3] or 0)*100:>5.2f}"
            print(f"    {r[0]:>3} {r[1]:>5} {fmt(r[2]):>5} {avg_ret}% "
                  f"{fmt(r[4], 2):>6} {fmt(r[5], 4):>6} {fmt(r[6]):>6}")
            if r[7]:
                regime = r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}")
                for regime_name, stats in regime.items():
                    print(f"      {regime_name}: n={stats.get('n')}, "
                          f"hr={fmt(stats.get('hit_rate'))}, "
                          f"avg={fmt(stats.get('avg_ret'))}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(description="Inspect transcript hypothesis pipeline")
    parser.add_argument("--top", type=int, default=15, help="Number of top results to show")
    parser.add_argument("--hypothesis-id", type=str, help="Show detail for a specific hypothesis")
    parser.add_argument("--promoted", action="store_true", help="Show promoted features only")
    args = parser.parse_args()

    if args.hypothesis_id:
        inspect_hypothesis(args.hypothesis_id)
        return

    if args.promoted:
        inspect_promoted()
        return

    inspect_pipeline_health()
    inspect_queue()
    inspect_top_results(args.top)
    inspect_promoted()
    print()


if __name__ == "__main__":
    main()
