#!/usr/bin/env python
"""
scripts/run_transcript_pipeline.py
=====================================
Nightly Transcript Intelligence Pipeline.

Steps
-----
1. Scan TRANSCRIPT_DIR for new/updated transcript files.
2. Extract candidate hypotheses via Claude API.
3. Backtest queued hypotheses against historical price data.
4. Promote statistically validated hypotheses to promoted_features.
5. Print a summary report.

Usage
-----
    # Extract + backtest + promote (full nightly run)
    python scripts/run_transcript_pipeline.py

    # Only extract new files (no backtesting)
    python scripts/run_transcript_pipeline.py --extract-only

    # Only backtest queued hypotheses (no new extraction)
    python scripts/run_transcript_pipeline.py --backtest-only

    # Only run promotion pass
    python scripts/run_transcript_pipeline.py --promote-only

    # Specify transcript directory
    python scripts/run_transcript_pipeline.py --transcript-dir /path/to/transcripts

    # Limit backtest batch size
    python scripts/run_transcript_pipeline.py --backtest-limit 20

Environment
-----------
    TRANSCRIPT_DIR  : path to directory containing .jsonl / .txt transcript files
                      Default: data/transcripts/ relative to repo root
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Ensure src/ is on the path when run as a script
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import structlog

from atlas_research.db.connection import get_connection
from atlas_research.transcripts.extractor import TranscriptExtractor
from atlas_research.transcripts.backtester import HypothesisBacktester
from atlas_research.transcripts.promoter import HypothesisPromoter
from atlas_research.utils.logging import configure_logging

log = structlog.get_logger("transcript_pipeline")


def _default_transcript_dir() -> Path:
    d = ROOT / "data" / "transcripts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _summary_report() -> None:
    """Print a concise summary of the research hypothesis pipeline state."""
    from sqlalchemy import text
    print()
    print("=" * 68)
    print("  TRANSCRIPT INTELLIGENCE PIPELINE — SUMMARY")
    print("=" * 68)

    with get_connection() as conn:
        sources = conn.execute(text(
            "SELECT COUNT(*), COUNT(processed_at) FROM transcript_sources"
        )).fetchone()
        print(f"  Sources:       {sources[1]:>5} processed  /  {sources[0]:>5} total")

        chunks = conn.execute(text("SELECT COUNT(*) FROM transcript_chunks")).scalar()
        print(f"  Chunks:        {chunks:>5}")

        hyp_stats = conn.execute(text("""
            SELECT test_status, COUNT(*) FROM research_hypotheses
            GROUP BY test_status ORDER BY test_status
        """)).fetchall()
        total_hyp = sum(r[1] for r in hyp_stats)
        print(f"\n  Hypotheses:    {total_hyp:>5} total")
        for status, count in hyp_stats:
            print(f"    {status:<12} {count:>5}")

        results = conn.execute(text("""
            SELECT COUNT(*),
                   ROUND(AVG(hit_rate)::numeric, 3),
                   ROUND(AVG(composite_score)::numeric, 3)
            FROM hypothesis_results
            WHERE sample_size >= 20
        """)).fetchone()
        print(f"\n  Tested results: {results[0]:>4}  "
              f"mean hit_rate={results[1]}  mean composite={results[2]}")

        # Top 5 by composite score
        top = conn.execute(text("""
            SELECT h.extracted_claim, r.horizon_days, r.hit_rate,
                   r.sharpe, r.p_value, r.sample_size, r.composite_score
            FROM hypothesis_results r
            JOIN research_hypotheses h ON h.hypothesis_id = r.hypothesis_id
            WHERE r.sample_size >= 20
            ORDER BY r.composite_score DESC NULLS LAST
            LIMIT 5
        """)).fetchall()

        if top:
            print("\n  TOP 5 HYPOTHESES BY COMPOSITE SCORE:")
            print(f"  {'Claim':<45} {'Hz':>3} {'HR':>5} {'Sh':>6} {'p':>6} {'n':>5} {'Score':>6}")
            print("  " + "─" * 78)
            for r in top:
                claim = (r[0] or "")[:44]
                print(f"  {claim:<45} {r[1]:>3}  "
                      f"{(r[2] or 0):>4.3f} {(r[3] or 0):>6.2f} "
                      f"{(r[4] or 1):>6.4f} {(r[5] or 0):>5} {(r[6] or 0):>6.3f}")

        promoted = conn.execute(text(
            "SELECT COUNT(*), promotion_status FROM promoted_features GROUP BY promotion_status"
        )).fetchall()
        total_prom = sum(r[0] for r in promoted)
        print(f"\n  Promoted features: {total_prom:>4}")
        for count, status in promoted:
            print(f"    {status:<20} {count:>4}")

    print("=" * 68)
    print()


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Atlas Research Transcript Intelligence Pipeline"
    )
    parser.add_argument(
        "--transcript-dir",
        type=str,
        default=os.environ.get("TRANSCRIPT_DIR", str(_default_transcript_dir())),
        help="Directory containing transcript files",
    )
    parser.add_argument("--extract-only",  action="store_true")
    parser.add_argument("--backtest-only", action="store_true")
    parser.add_argument("--promote-only",  action="store_true")
    parser.add_argument(
        "--backtest-limit",
        type=int,
        default=int(os.environ.get("BACKTEST_LIMIT", "50")),
        help="Max hypotheses to backtest per run",
    )
    args = parser.parse_args()

    transcript_dir = Path(args.transcript_dir)
    run_extract  = not (args.backtest_only or args.promote_only)
    run_backtest = not (args.extract_only  or args.promote_only)
    run_promote  = not (args.extract_only  or args.backtest_only)

    t0 = time.time()

    # ── Step 1: Extract ────────────────────────────────────────────────
    if run_extract:
        log.info("pipeline.extract_start", directory=str(transcript_dir))
        extractor = TranscriptExtractor()
        n_extracted = extractor.process_directory(transcript_dir)
        log.info("pipeline.extract_done", n_hypotheses=n_extracted)
    else:
        log.info("pipeline.extract_skipped")

    # ── Step 2: Backtest ───────────────────────────────────────────────
    if run_backtest:
        log.info("pipeline.backtest_start", limit=args.backtest_limit)
        backtester = HypothesisBacktester()
        n_tested = backtester.run_queued(limit=args.backtest_limit)
        log.info("pipeline.backtest_done", n_tested=n_tested)
    else:
        log.info("pipeline.backtest_skipped")

    # ── Step 3: Promote ────────────────────────────────────────────────
    if run_promote:
        log.info("pipeline.promote_start")
        promoter = HypothesisPromoter()
        n_promoted = promoter.promote_passing()
        log.info("pipeline.promote_done", n_promoted=n_promoted)
    else:
        log.info("pipeline.promote_skipped")

    elapsed = time.time() - t0
    log.info("pipeline.complete", elapsed_s=round(elapsed, 1))

    _summary_report()


if __name__ == "__main__":
    main()
