"""
run_score_decomposition.py
--------------------------
Break the Atlas Score into per-component calibration rows and print the
full decomposition table.

For EVERY historical observation in alpha_signal_snapshots, the script
groups by:
  - score_total (5 buckets: 0-20 / 20-40 / 40-60 / 60-80 / 80-100)
  - bull_flags  (0-6, computed from component scores >60)
  - bear_flags  (0-6, computed from component scores <40)
  - trend_score tier  (high ≥70 / mid 40-69 / low ≤39)
  - momentum_score tier
  - volume_score tier
  - rs_score tier
  - regime_score tier
  - exhaustion_score tier
  - rsi_raw zone  (<30 / 30-40 / 40-50 / 50-60 / 60-70 / 70-80 / >80)
  - adx_raw zone  (weak <15 / moderate 15-25 / trending 25-35 / strong >35)
  - alignment_score tier (high ≥70 / mid 40-69 / low ≤39)
  - macd_histogram sign (positive / negative)
  - rsi_divergence value (bullish / bearish / none)
  - golden_cross flag (yes / no)
  - death_cross  flag (yes / no)
  - vol_squeeze  flag (yes / no)
  - pullback_class value

Output: component | N | 1d Hit | 3d Hit | 5d Hit | 10d Hit | 20d Hit |
        Avg 5d% | Median 5d% | Edge | Sharpe | P-val | Perm Pass

Usage:
    python scripts/run_score_decomposition.py
    python scripts/run_score_decomposition.py --no-db      # skip DB write
    python scripts/run_score_decomposition.py --min-n 20   # override min samples
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

import numpy as np
import psycopg2
import psycopg2.extras
from scipy.stats import binomtest

# ── Config ────────────────────────────────────────────────────────────────────

MIN_N_DEFAULT   = 10
PERM_ITERS      = 5_000
PROMO_N         = 50
PROMO_HIT       = 0.54
PROMO_P         = 0.05
PROMO_YEARS     = 3
CAND_N          = 20
CAND_HIT        = 0.52
CAND_P          = 0.10


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class DecompRow:
    component: str
    bucket: str
    n: int
    hit_1d: float | None
    hit_3d: float | None
    hit_5d: float | None
    hit_10d: float | None
    hit_20d: float | None
    avg_5d: float | None
    median_5d: float | None
    edge_5d: float | None       # vs universe baseline
    sharpe_5d: float | None
    perm_p: float | None
    perm_pass: bool | None      # p < 0.05
    sanity_pass: bool | None    # binomial vs 50%
    status: str
    year_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pct(a: np.ndarray | None) -> float | None:
    if a is None or len(a) == 0:
        return None
    return float(np.mean(a > 0))

def _mean(a: np.ndarray | None) -> float | None:
    if a is None or len(a) == 0:
        return None
    return float(np.mean(a))

def _bootstrap_p(arr: np.ndarray, universe: np.ndarray, iters: int) -> float:
    obs = float(np.mean(arr > 0))
    n = len(arr)
    idx = np.random.choice(len(universe), size=(iters, n), replace=True)
    null_hits = np.mean(universe[idx] > 0, axis=1)
    return float(np.mean(null_hits >= obs))

def _classify(n: int, hit5: float, p: float, yrs: int) -> str:
    if n >= PROMO_N and hit5 > PROMO_HIT and p < PROMO_P and yrs >= PROMO_YEARS:
        return "promoted"
    if n >= CAND_N and hit5 > CAND_HIT and p < CAND_P:
        return "candidate"
    return "rejected"

def _score_bucket(score: float) -> str:
    if score < 20:  return "0-20"
    if score < 40:  return "20-40"
    if score < 60:  return "40-60"
    if score < 80:  return "60-80"
    return "80-100"

def _tier(val: float | None, lo: int = 40, hi: int = 70) -> str | None:
    if val is None:
        return None
    return "high" if val >= hi else ("low" if val < lo else "mid")

def _rsi_zone(rsi: float | None) -> str | None:
    if rsi is None:
        return None
    if rsi < 20:  return "<20"
    if rsi < 30:  return "20-30"
    if rsi < 40:  return "30-40"
    if rsi < 50:  return "40-50"
    if rsi < 60:  return "50-60"
    if rsi < 70:  return "60-70"
    if rsi < 80:  return "70-80"
    return ">80"

def _adx_zone(adx: float | None) -> str | None:
    if adx is None:
        return None
    if adx < 15:  return "weak<15"
    if adx < 25:  return "mod 15-25"
    if adx < 35:  return "trend 25-35"
    return "strong>35"

def _macd_sign(h: float | None) -> str | None:
    if h is None:
        return None
    return "positive" if h > 0 else "negative"

def _vol_tier(atr_pct: float | None) -> str | None:
    if atr_pct is None:
        return None
    # atr_pct stored as percentage (e.g. 3.5 = 3.5% ATR)
    # p25=2.51%, median=3.55%, p75=5.54% across the scanner universe
    if atr_pct < 2.0:  return "low<2%"
    if atr_pct < 4.0:  return "mid 2-4%"
    if atr_pct < 7.0:  return "high 4-7%"
    return "extreme>7%"

def _parse_patterns(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(p) for p in raw]
    if isinstance(raw, str):
        try:
            import json as _json
            return _json.loads(raw)
        except Exception:
            return []
    return []

# Patterns that indicate price breakout/momentum (historically bearish at 5d — overextended)
BREAKOUT_PATTERNS = {
    "BB Breakout", "Golden Cross", "Death Cross",
    "High Relative Volume", "Ascending Triangle", "Cup and Handle",
    "Flat Base Breakout", "52-Week High", "New 52W High",
}

# Patterns that indicate compression/mean-reversion setup (historically bullish at 5d)
COMPRESSION_PATTERNS = {
    "NR7 Compression", "Inside Day", "Volatility Squeeze",
    "Rectangle Base", "Bear Flag", "Bull Flag",
    "Descending Channel", "Falling Wedge",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def run(research_url: str, min_n: int = MIN_N_DEFAULT, write_db: bool = True) -> list[DecompRow]:
    with psycopg2.connect(research_url) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                ticker,
                snapshot_date::text AS snapshot_date,
                atlas_score,
                trend_score, momentum_score, volume_score,
                rs_score, regime_score, exhaustion_score,
                rsi, adx, alignment_score,
                macd_histogram, rsi_divergence,
                golden_cross, death_cross, vol_squeeze,
                pullback_class, atr_pct,
                patterns,
                bull_flags, bear_flags,
                return_1d, return_3d, return_5d, return_10d, return_20d
            FROM alpha_signal_snapshots
            WHERE return_5d IS NOT NULL
            ORDER BY snapshot_date
        """)
        rows = cur.fetchall()

    if not rows:
        print("[decomp] No resolved snapshots found in alpha_signal_snapshots.")
        return []

    universe_5d = np.array([float(r["return_5d"]) for r in rows], dtype=float)
    baseline    = float(np.mean(universe_5d > 0))
    print(f"\n[decomp] {len(rows)} resolved snapshots | "
          f"universe 5d baseline: {baseline:.1%} | "
          f"median 5d ret: {float(np.median(universe_5d))*100:+.2f}%\n")

    # ── Build groups ─────────────────────────────────────────────────────────
    # groups[("component", "bucket")] = list of signal records
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for r in rows:
        score   = float(r["atlas_score"] or 0)
        year    = (r["snapshot_date"] or "2000-01-01")[:4]
        rec = {
            "r1": r["return_1d"],
            "r3": r["return_3d"],
            "r5": r["return_5d"],
            "r10": r["return_10d"],
            "r20": r["return_20d"],
            "year": year,
        }

        # score_total
        groups[("score_total", _score_bucket(score))].append(rec)

        # bull_flags / bear_flags (generated columns — may be NULL for old rows)
        bf = r["bull_flags"]
        if bf is not None:
            groups[("bull_flags", str(int(bf)))].append(rec)
        brf = r["bear_flags"]
        if brf is not None:
            groups[("bear_flags", str(int(brf)))].append(rec)

        # Component score tiers
        for comp, val in [
            ("trend_score",     r["trend_score"]),
            ("momentum_score",  r["momentum_score"]),
            ("volume_score",    r["volume_score"]),
            ("rs_score",        r["rs_score"]),
            ("regime_score",    r["regime_score"]),
            ("exhaustion_score",r["exhaustion_score"]),
        ]:
            t = _tier(float(val) if val is not None else None)
            if t:
                groups[(comp, t)].append(rec)

        # RSI raw zones
        rz = _rsi_zone(float(r["rsi"]) if r["rsi"] is not None else None)
        if rz:
            groups[("rsi_raw", rz)].append(rec)

        # ADX raw zones (may be NULL for pre-migration snapshots)
        az = _adx_zone(float(r["adx"]) if r["adx"] is not None else None)
        if az:
            groups[("adx_raw", az)].append(rec)

        # Alignment score tiers
        at = _tier(float(r["alignment_score"]) if r["alignment_score"] is not None else None)
        if at:
            groups[("alignment_score", at)].append(rec)

        # MACD histogram sign
        ms = _macd_sign(float(r["macd_histogram"]) if r["macd_histogram"] is not None else None)
        if ms:
            groups[("macd_histogram", ms)].append(rec)

        # RSI divergence
        rd = r["rsi_divergence"]
        if rd is not None:
            groups[("rsi_divergence", str(rd))].append(rec)
        else:
            groups[("rsi_divergence", "none")].append(rec)

        # Boolean flags
        for flag_name, flag_val in [
            ("golden_cross", r["golden_cross"]),
            ("death_cross",  r["death_cross"]),
            ("vol_squeeze",  r["vol_squeeze"]),
        ]:
            if flag_val is not None:
                groups[(flag_name, "yes" if flag_val else "no")].append(rec)

        # Pullback class
        pc = r["pullback_class"]
        if pc:
            groups[("pullback_class", str(pc))].append(rec)

        # ── New composite components ─────────────────────────────────────
        pats = _parse_patterns(r.get("patterns"))

        # Pattern score: raw count bucketed
        n_pats = len(pats)
        if n_pats == 0:    pat_bucket = "0"
        elif n_pats <= 2:  pat_bucket = "1-2"
        elif n_pats <= 4:  pat_bucket = "3-4"
        else:              pat_bucket = "5+"
        groups[("pattern_score", pat_bucket)].append(rec)

        # Breakout score: presence of breakout vs compression vs neither
        has_breakout    = any(p in BREAKOUT_PATTERNS    for p in pats)
        has_compression = any(p in COMPRESSION_PATTERNS for p in pats)
        if has_breakout:
            groups[("breakout_score", "has_breakout")].append(rec)
        if has_compression:
            groups[("breakout_score", "has_compression")].append(rec)
        if not has_breakout and not has_compression:
            groups[("breakout_score", "no_signal")].append(rec)

        # Volatility score: ATR% bucketed
        vt = _vol_tier(float(r["atr_pct"]) if r.get("atr_pct") is not None else None)
        if vt:
            groups[("volatility_score", vt)].append(rec)

    # ── Compute stats per group ───────────────────────────────────────────────
    def _arr(items: list[dict], key: str) -> np.ndarray | None:
        vals = [x[key] for x in items if x[key] is not None]
        return np.array(vals, dtype=float) if len(vals) >= min_n else None

    results: list[DecompRow] = []

    for (comp, bucket), items in sorted(groups.items()):
        a5 = _arr(items, "r5")
        if a5 is None:
            continue

        a1  = _arr(items, "r1")
        a3  = _arr(items, "r3")
        a10 = _arr(items, "r10")
        a20 = _arr(items, "r20")

        n       = len(a5)
        hit5    = float(np.mean(a5 > 0))
        avg5    = float(np.mean(a5))
        med5    = float(np.median(a5))
        std5    = float(np.std(a5, ddof=1)) if n > 1 else 0.0
        sharpe  = (avg5 / std5) * np.sqrt(252 / 5) if std5 > 0 else 0.0
        edge    = hit5 - baseline

        years   = [x["year"] for x in items if x["r5"] is not None]
        yr_set  = sorted(set(years))

        perm_p  = _bootstrap_p(a5, universe_5d, PERM_ITERS)
        k       = int(np.sum(a5 > 0))
        bt      = binomtest(k, n, 0.50, alternative="greater")
        sanity  = bool(bt.pvalue < 0.05)
        status  = _classify(n, hit5, perm_p, len(yr_set))

        results.append(DecompRow(
            component  = comp,
            bucket     = bucket,
            n          = n,
            hit_1d     = _pct(a1),
            hit_3d     = _pct(a3),
            hit_5d     = hit5,
            hit_10d    = _pct(a10),
            hit_20d    = _pct(a20),
            avg_5d     = avg5,
            median_5d  = med5,
            edge_5d    = edge,
            sharpe_5d  = sharpe,
            perm_p     = perm_p,
            perm_pass  = perm_p < 0.05,
            sanity_pass= sanity,
            status     = status,
            year_count = len(yr_set),
        ))

    return results


def _fmt_pct(v: float | None, width: int = 7) -> str:
    if v is None: return " " * (width - 1) + "-"
    s = f"{v:.1%}"
    return s.rjust(width)

def _fmt_ret(v: float | None, width: int = 8) -> str:
    if v is None: return " " * (width - 1) + "-"
    s = f"{v*100:+.2f}%"
    return s.rjust(width)

def _fmt_p(v: float | None) -> str:
    if v is None: return "   -  "
    return f"{v:.3f}".rjust(6)

def _fmt_sharpe(v: float | None) -> str:
    if v is None: return "   -  "
    return f"{v:+.2f}".rjust(6)


def print_decomposition(results: list[DecompRow], baseline: float) -> None:
    # Group by component
    by_comp: dict[str, list[DecompRow]] = defaultdict(list)
    for r in results:
        by_comp[r.component].append(r)

    # Ordered display
    component_order = [
        "score_total",
        "bull_flags", "bear_flags",
        "trend_score", "momentum_score", "volume_score",
        "rs_score", "regime_score", "exhaustion_score",
        "rsi_raw", "adx_raw", "alignment_score",
        "pattern_score", "breakout_score", "volatility_score",
        "macd_histogram", "rsi_divergence",
        "golden_cross", "death_cross", "vol_squeeze",
        "pullback_class",
    ]

    print("\n" + "=" * 110)
    print("  ATLAS SCORE DECOMPOSITION — Per-Component Calibration")
    print(f"  Universe 5d baseline: {baseline:.1%}  |  Edge = signal hit rate minus baseline")
    print("=" * 110)

    HDR = (f"  {'Bucket':<16}  {'N':>5}  "
           f"{'1d Hit':>7}  {'3d Hit':>7}  {'5d Hit':>7}  {'10d Hit':>8}  {'20d Hit':>8}  "
           f"{'Avg 5d%':>8}  {'Med 5d%':>8}  {'Edge':>6}  "
           f"{'Sharpe':>7}  {'P-val':>7}  {'Pass':>4}  {'Status'}")

    promoted  = [r for r in results if r.status == "promoted"]
    candidate = [r for r in results if r.status == "candidate"]
    rejected  = [r for r in results if r.status == "rejected"]

    for comp in component_order:
        rows = by_comp.get(comp, [])
        if not rows:
            continue

        # Sort by 5d hit descending
        rows = sorted(rows, key=lambda r: -(r.hit_5d or 0))
        print(f"\n--- {comp.upper().replace('_', ' ')} ---")
        print(HDR)
        print("  " + "-" * 106)

        for r in rows:
            pass_str = "PASS" if r.perm_pass else "FAIL"
            star = "*" if r.status == "promoted" else ("o" if r.status == "candidate" else " ")
            print(f"  {r.bucket:<16}  {r.n:>5}  "
                  f"{_fmt_pct(r.hit_1d):>7}  {_fmt_pct(r.hit_3d):>7}  {_fmt_pct(r.hit_5d):>7}  "
                  f"{_fmt_pct(r.hit_10d):>8}  {_fmt_pct(r.hit_20d):>8}  "
                  f"{_fmt_ret(r.avg_5d):>8}  {_fmt_ret(r.median_5d):>8}  "
                  f"{_fmt_pct(r.edge_5d, 6):>6}  "
                  f"{_fmt_sharpe(r.sharpe_5d):>7}  {_fmt_p(r.perm_p):>7}  {pass_str:>4}  "
                  f"{star}{r.status}")

    # Summary
    print("\n" + "=" * 110)
    print(f"  DECOMPOSITION SUMMARY: {len(promoted)} promoted  |  {len(candidate)} candidate  |  {len(rejected)} rejected")

    if promoted:
        print("\n  CREATES ALPHA (promoted):")
        for r in sorted(promoted, key=lambda x: -(x.hit_5d or 0)):
            print(f"    [{r.component}] bucket={r.bucket:12s}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  p={r.perm_p:.3f}")

    if candidate:
        print("\n  PROMISING (candidate — needs more data):")
        for r in sorted(candidate, key=lambda x: -(x.hit_5d or 0)):
            print(f"    [{r.component}] bucket={r.bucket:12s}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  p={r.perm_p:.3f}")

    # False-edge signals: below 48% with n >= CAND_N
    false_edge = [r for r in rejected
                  if r.n >= CAND_N and r.hit_5d is not None and r.hit_5d < 0.48]
    if false_edge:
        print("\n  DESTROYS ALPHA (false-edge / strongly bearish):")
        for r in sorted(false_edge, key=lambda x: (x.hit_5d or 1.0)):
            print(f"    [{r.component}] bucket={r.bucket:12s}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  p={r.perm_p:.3f}")

    print("=" * 110 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Atlas Score Decomposition")
    parser.add_argument("--no-db",    action="store_true", help="Skip writing results to DB")
    parser.add_argument("--min-n",    type=int, default=MIN_N_DEFAULT, help="Minimum sample size")
    args = parser.parse_args()

    research_url = os.environ.get("DATABASE_URL")
    if not research_url:
        sys.exit("ERROR: DATABASE_URL not set. Run: $env:DATABASE_URL='postgresql://...'")

    print("[decomp] Loading alpha_signal_snapshots...")
    results = run(research_url, min_n=args.min_n, write_db=not args.no_db)

    if not results:
        sys.exit("[decomp] No data available — run run_alpha_calibration.py --sync-only first.")

    # Compute baseline for display
    with psycopg2.connect(research_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT AVG(CASE WHEN return_5d > 0 THEN 1.0 ELSE 0.0 END) FROM alpha_signal_snapshots WHERE return_5d IS NOT NULL")
        baseline = float(cur.fetchone()[0] or 0.5)

    print_decomposition(results, baseline)
