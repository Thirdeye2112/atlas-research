import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--results", action="store_true")
    args = parser.parse_args()
    from atlas_research.conditional.engine import ConditionalEngine
    from atlas_research.db.connection import get_connection
    from sqlalchemy import text
    db = get_connection()
    if args.list:
        with db.connect() as c:
            rows = c.execute(text("SELECT name, condition_type, universe FROM conditional_patterns ORDER BY id")).fetchall()
        print(f"\n{'Name':<30} {'Type':<22} Universe"); print("─"*60)
        for r in rows: print(f"  {r.name:<28} {r.condition_type:<22} {r.universe}")
        print(f"\n{len(rows)} patterns\n"); return 0
    if args.results:
        with db.connect() as c:
            rows = c.execute(text("""
                SELECT cp.name, r.horizon_days, r.sample_size,
                       ROUND(r.hit_rate*100,1) AS hit_pct,
                       ROUND(r.avg_return*100,3) AS avg_pct,
                       ROUND(r.median_return*100,3) AS med_pct
                FROM conditional_pattern_results r
                JOIN conditional_patterns cp ON cp.id=r.pattern_id
                WHERE r.ticker IS NULL ORDER BY cp.name, r.horizon_days LIMIT 100
            """)).fetchall()
        if not rows: print("\nNo results yet.\n"); return 0
        print(f"\n{'Pattern':<28} {'Days':>5} {'n':>6} {'Hit%':>6} {'Avg%':>8} {'Med%':>8}")
        print("─"*65)
        for r in rows: print(f"  {r.name:<26} {r.horizon_days:>5}d {r.sample_size:>6} {r.hit_pct:>6.1f} {r.avg_pct:>8.3f} {r.med_pct:>8.3f}")
        print(); return 0
    ce = ConditionalEngine()
    if args.pattern:
        print(f"\nRunning: {args.pattern}")
        n = ce.run_pattern(args.pattern)
        print(f"  {n} signals processed\n")
    else:
        print("\nRunning all patterns...")
        s = ce.run_all()
        print(f"  run={s['run']} failed={s['failed']} signals={s['total_signals']}\n")
    return 0

if __name__ == "__main__": sys.exit(main())