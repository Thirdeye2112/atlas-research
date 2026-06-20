"""Gather DB stats for CONSENSUS.md update."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv; load_dotenv()
from sqlalchemy import text
from atlas_research.db.connection import get_raw_engine

e = get_raw_engine()
with e.connect() as c:
    cols = c.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_name='model_registry' ORDER BY ordinal_position"
    )).fetchall()
    print("model_registry cols:", [r[0] for r in cols])
    r = c.execute(text("""
        SELECT COUNT(*) as folds,
               ROUND(AVG(rank_ic)::numeric, 4) as avg_ic,
               MAX(training_end)::text as trained_through
        FROM model_registry
    """)).fetchone()
    print(f"Model: {r.folds} folds | IC={r.avg_ic} | trained_through={r.trained_through}")

    n_preds = c.execute(text("SELECT COUNT(*) FROM predictions WHERE date=CURRENT_DATE")).scalar()
    n_preds_total = c.execute(text("SELECT COUNT(*) FROM predictions")).scalar()
    print(f"Predictions: {n_preds} today | {n_preds_total} total")

    n_pat  = c.execute(text("SELECT COUNT(*) FROM conditional_patterns")).scalar()
    n_res  = c.execute(text("SELECT COUNT(DISTINCT pattern_id) FROM conditional_pattern_results WHERE ticker IS NULL")).scalar()
    print(f"Patterns: {n_pat} defined | {n_res} with aggregate results")

    n_rs   = c.execute(text("SELECT COUNT(*) FROM sector_relative_strength")).scalar()
    n_cal  = c.execute(text("SELECT COUNT(*) FROM market_calendar")).scalar()
    print(f"Sector RS rows: {n_rs:,} | Calendar events: {n_cal}")

    n_src  = c.execute(text("SELECT COUNT(*) FROM transcript_sources")).scalar()
    n_chk  = c.execute(text("SELECT COUNT(*) FROM transcript_chunks")).scalar()
    print(f"Transcript sources: {n_src} | chunks: {n_chk}")

    n_mig  = c.execute(text("SELECT COUNT(*) FROM schema_migrations")).scalar()
    n_tbl  = c.execute(text(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'"
    )).scalar()
    print(f"Migrations: {n_mig} | Tables: {n_tbl}")

    n_bars = c.execute(text("SELECT COUNT(*) FROM raw_bars")).scalar()
    n_tick = c.execute(text("SELECT COUNT(DISTINCT ticker) FROM raw_bars")).scalar()
    n_sec  = c.execute(text("SELECT COUNT(*) FROM securities WHERE active=true")).scalar()
    n_ipo  = c.execute(text("SELECT COUNT(*) FROM ipo_registry")).scalar()
    print(f"raw_bars: {n_bars:,} rows | {n_tick} distinct tickers")
    print(f"securities (active): {n_sec} | ipo_registry: {n_ipo}")

    n_fs   = c.execute(text("SELECT COUNT(*) FROM feature_snapshots")).scalar()
    n_fsd  = c.execute(text("SELECT COUNT(DISTINCT date) FROM feature_snapshots")).scalar()
    n_lab  = c.execute(text("SELECT COUNT(*) FROM labels")).scalar()
    print(f"feature_snapshots: {n_fs:,} | {n_fsd} dates | labels: {n_lab:,}")

    # Top predictions today
    top = c.execute(text("""
        SELECT ticker, rank_percentile, confidence, expected_return
        FROM predictions
        WHERE date = CURRENT_DATE
        ORDER BY rank_percentile DESC
        LIMIT 10
    """)).fetchall()
    print("\nTop 10 predictions today (by rank_pct):")
    for r in top:
        print(f"  {r.ticker:<8} rank={r.rank_percentile:.3f} conf={r.confidence:.3f} exp_ret={r.expected_return:.4f}")
