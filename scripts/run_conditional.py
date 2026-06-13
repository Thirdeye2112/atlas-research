import argparse, math, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv; load_dotenv(ROOT / ".env")


def _binomial_p(n: int, k: int, p0: float = 0.5) -> float:
    """One-tailed p-value: P(X >= k) under Binomial(n, p0), normal approximation."""
    if n == 0:
        return 1.0
    mu = n * p0
    sigma = math.sqrt(n * p0 * (1 - p0))
    if sigma == 0:
        return 1.0
    z = (k - 0.5 - mu) / sigma  # continuity correction
    # Phi complement using Abramowitz & Stegun
    if z < 0:
        return 1.0
    b = 1 / (1 + 0.2316419 * z)
    poly = b * (0.319381530 + b * (-0.356563782 + b * (1.781477937 + b * (-1.821255978 + b * 1.330274429))))
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return pdf * poly


def cmd_sanity_check(db):
    """Binomial significance test on every stored pattern at 5d and 20d."""
    from sqlalchemy import text
    with db.connect() as c:
        rows = c.execute(text("""
            SELECT cp.name, r.horizon_days, r.sample_size, r.hit_rate, r.p_value, r.sharpe
            FROM conditional_pattern_results r
            JOIN conditional_patterns cp ON cp.id = r.pattern_id
            WHERE r.ticker IS NULL AND r.horizon_days IN (5, 20)
            ORDER BY cp.name, r.horizon_days
        """)).fetchall()

    if not rows:
        print("\nNo stored results. Run: python scripts/run_conditional.py first.\n")
        return 1

    CHECK_HORIZONS = {5, 20}
    P_THRESHOLD = 0.05
    MIN_N = 30

    # Aggregate per pattern: PASS only if both checked horizons pass
    from collections import defaultdict
    by_pattern: dict[str, list] = defaultdict(list)
    for r in rows:
        if r.horizon_days in CHECK_HORIZONS:
            by_pattern[r.name].append(r)

    header = f"  {'Pattern':<34} {'Hz':>4}  {'n':>6}  {'Hit%':>6}  {'p-bin':>7}  {'Sharpe':>7}  Status"
    print(f"\n{'Permutation Sanity Check — Conditional Patterns':^80}")
    print(f"{'Binomial H0: hit_rate = 0.5 | a=0.05 | min n = ' + str(MIN_N):^80}")
    print("─" * 80)
    print(header)
    print("  " + "─" * 76)

    pass_count = fail_count = skip_count = 0
    pattern_verdicts: dict[str, str] = {}

    for pat_name in sorted(by_pattern):
        results = sorted(by_pattern[pat_name], key=lambda r: r.horizon_days)
        pat_pass = True
        pat_rows = []
        for r in results:
            n = r.sample_size or 0
            hr = float(r.hit_rate or 0)
            k = int(round(hr * n))
            p_bin = _binomial_p(n, k)
            sh = r.sharpe

            if n < MIN_N:
                status = "SKIP (n<30)"
                skip_count += 1
                pat_pass = False
            elif hr <= 0.50:
                status = "FAIL (hr≤50%)"
                fail_count += 1
                pat_pass = False
            elif p_bin >= P_THRESHOLD:
                status = f"FAIL (p={p_bin:.3f})"
                fail_count += 1
                pat_pass = False
            else:
                status = f"PASS (p={p_bin:.4f})"
                pass_count += 1

            pat_rows.append((r.horizon_days, n, hr * 100, p_bin, sh or 0.0, status))

        for hz, n, hr_pct, p_bin, sh, status in pat_rows:
            print(f"  {pat_name:<34} {hz:>4}d {n:>6}  {hr_pct:>5.1f}%  {p_bin:>7.4f}  {sh:>7.3f}  {status}")

        pattern_verdicts[pat_name] = "PASS" if pat_pass else "FAIL/SKIP"

    print()
    print("─" * 80)
    n_total = pass_count + fail_count + skip_count
    print(f"  Rows checked : {n_total}  |  PASS: {pass_count}  FAIL: {fail_count}  SKIP: {skip_count}")
    pat_pass_ct = sum(1 for v in pattern_verdicts.values() if v == "PASS")
    pat_fail_ct = len(pattern_verdicts) - pat_pass_ct
    print(f"  Patterns     : {len(pattern_verdicts)} total  |  {pat_pass_ct} fully pass  |  {pat_fail_ct} have failures")
    print()
    return 0 if fail_count == 0 else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--results", action="store_true")
    parser.add_argument("--sanity-check", action="store_true")
    args = parser.parse_args()
    from atlas_research.conditional.engine import ConditionalEngine
    from atlas_research.db.connection import get_raw_engine
    from sqlalchemy import text
    db = get_raw_engine()
    if args.sanity_check:
        return cmd_sanity_check(db)
    if args.list:
        with db.connect() as c:
            rows = c.execute(text("SELECT name, condition_type, universe FROM conditional_patterns ORDER BY id")).fetchall()
        print(f"\n{'Name':<30} {'Type':<22} Universe"); print("-"*60)
        for r in rows: print(f"  {r.name:<28} {r.condition_type:<22} {r.universe}")
        print(f"\n{len(rows)} patterns\n"); return 0
    if args.results:
        with db.connect() as c:
            rows = c.execute(text("""
                SELECT cp.name, r.horizon_days, r.sample_size,
                       ROUND((r.hit_rate*100)::numeric,1) AS hit_pct,
                       ROUND((r.avg_return*100)::numeric,3) AS avg_pct,
                       ROUND((r.median_return*100)::numeric,3) AS med_pct
                FROM conditional_pattern_results r
                JOIN conditional_patterns cp ON cp.id=r.pattern_id
                WHERE r.ticker IS NULL ORDER BY cp.name, r.horizon_days LIMIT 100
            """)).fetchall()
        if not rows: print("\nNo results yet.\n"); return 0
        print(f"\n{'Pattern':<28} {'Days':>5} {'n':>6} {'Hit%':>6} {'Avg%':>8} {'Med%':>8}")
        print("-"*65)
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