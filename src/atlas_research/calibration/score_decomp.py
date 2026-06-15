"""
atlas_research.calibration.score_decomp
=========================================
Score component decomposition — for every resolved alpha snapshot:

  1. populate_components()  — derives component scores from alpha_signal_snapshots,
                               computes scanner_rank, writes to alpha_score_components
                               and alpha_score_component_outcomes.

  2. run_calibration()      — groups by (component, bucket), computes outcomes
                               at 1d/3d/5d/10d/20d with permutation testing,
                               writes to alpha_score_calibration_runs.

  3. print_ranking_table()  — prints the component ranking table sorted by 5d alpha.

Design: no DB access inside stat computation; all reads up-front, all writes at end.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import numpy as np
import psycopg2
import psycopg2.extras

# ── Thresholds ────────────────────────────────────────────────────────────────

PERM_ITERS  = 5_000
MIN_N       = 10
PROMO_N     = 50
PROMO_HIT   = 0.54
PROMO_P     = 0.05
PROMO_YEARS = 3
CAND_N      = 20
CAND_HIT    = 0.52
CAND_P      = 0.10

# Breakout patterns → usually overbought/extended
BREAKOUT_PATTERNS = {
    "BB Breakout", "Golden Cross", "Ascending Triangle",
    "Cup and Handle", "Flat Base Breakout", "52-Week High", "New 52W High",
    "Death Cross", "BB Breakdown",
}


# ── Component derivation ──────────────────────────────────────────────────────

def _volatility_component(atr_pct: float | None) -> float | None:
    """Invert ATR% into a 0-100 stability score (higher = more stable)."""
    if atr_pct is None:
        return None
    capped = max(0.0, min(float(atr_pct), 15.0))
    return round((1.0 - capped / 15.0) * 100.0, 1)


def _pattern_component(patterns: list[str]) -> float:
    """Score based on pattern count (0-100)."""
    n = len(patterns)
    if n == 0: return 0.0
    if n == 1: return 30.0
    if n == 2: return 55.0
    if n == 3: return 70.0
    return min(85.0 + (n - 4) * 5.0, 100.0)


def _breakout_component(patterns: list[str]) -> float:
    """Score based on breakout pattern presence (0-100)."""
    n = sum(1 for p in patterns if p in BREAKOUT_PATTERNS)
    if n == 0: return 0.0
    if n == 1: return 60.0
    return 100.0


def _support_resistance_component(pullback_class: str | None, rs_score: float | None) -> float:
    """Composite: pullback structure + relative strength."""
    base = {"pullback": 70.0, "ambiguous": 45.0, "reversal": 20.0}.get(
        (pullback_class or "").lower(), 45.0
    )
    if rs_score is not None:
        return round(base * 0.6 + float(rs_score) * 0.4, 1)
    return round(base, 1)


def _parse_patterns(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(p) for p in raw]
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _flag_counts(scores: dict[str, float | None]) -> tuple[int, int]:
    """Count component buckets above 70 (bull) and below 30 (bear)."""
    bull = sum(1 for v in scores.values() if v is not None and v >= 70)
    bear = sum(1 for v in scores.values() if v is not None and v <= 30)
    return bull, bear


# ── Population ────────────────────────────────────────────────────────────────

def populate_components(research_url: str) -> tuple[int, int]:
    """
    Read alpha_signal_snapshots (all rows with returns), derive component scores,
    compute scanner_rank per date, upsert into alpha_score_components and
    alpha_score_component_outcomes.

    Returns (n_components, n_outcomes) rows upserted.
    """
    with psycopg2.connect(research_url) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                ticker, snapshot_date::text AS snapshot_date,
                atlas_score, atr_pct,
                trend_score, momentum_score, volume_score,
                rs_score, regime_score, exhaustion_score,
                pullback_class, rsi, patterns,
                return_1d, return_3d, return_5d, return_10d, return_20d
            FROM alpha_signal_snapshots
            WHERE return_5d IS NOT NULL
            ORDER BY snapshot_date, atlas_score DESC
        """)
        rows = cur.fetchall()

    if not rows:
        return 0, 0

    # ── Compute scanner_rank per date ─────────────────────────────────────
    date_rank: dict[str, int] = {}
    rank_counters: dict[str, int] = defaultdict(int)
    for r in rows:                         # already sorted score DESC per date
        d = r["snapshot_date"]
        rank_counters[d] += 1
        date_rank[(r["ticker"], d)] = rank_counters[d]

    comp_rows: list[dict] = []
    out_rows:  list[dict] = []

    for r in rows:
        ticker   = r["ticker"]
        sdate    = r["snapshot_date"]
        pats     = _parse_patterns(r["patterns"])
        score    = float(r["atlas_score"] or 0)
        trend    = float(r["trend_score"]) if r["trend_score"] is not None else None
        mom      = float(r["momentum_score"]) if r["momentum_score"] is not None else None
        vol_c    = float(r["volume_score"]) if r["volume_score"] is not None else None
        rs_s     = float(r["rs_score"]) if r["rs_score"] is not None else None
        reg      = float(r["regime_score"]) if r["regime_score"] is not None else None
        exh      = float(r["exhaustion_score"]) if r["exhaustion_score"] is not None else None
        atr      = float(r["atr_pct"]) if r["atr_pct"] is not None else None
        rsi_raw  = float(r["rsi"]) if r["rsi"] is not None else None

        vol_comp = _volatility_component(atr)
        pat_comp = _pattern_component(pats)
        brk_comp = _breakout_component(pats)
        sr_comp  = _support_resistance_component(r["pullback_class"], rs_s)

        core_scores = {
            "trend":      trend,
            "momentum":   mom,
            "volume":     vol_c,
            "rs":         rs_s,
            "regime":     reg,
            "volatility": vol_comp,
        }
        bull_flags, bear_flags = _flag_counts(core_scores)

        rank = date_rank.get((ticker, sdate), 0)

        comp_rows.append({
            "ticker":                       ticker,
            "snapshot_date":                sdate,
            "score_total":                  score,
            "trend_component":              trend,
            "momentum_component":           mom,
            "volume_component":             vol_c,
            "volatility_component":         vol_comp,
            "pattern_component":            pat_comp,
            "breakout_component":           brk_comp,
            "support_resistance_component": sr_comp,
            "bull_flag_count":              bull_flags,
            "bear_flag_count":              bear_flags,
            "patterns_detected":            json.dumps(pats),
            "scanner_rank":                 rank,
            "atr_pct_raw":                  atr,
            "rs_score":                     rs_s,
            "regime_score":                 reg,
            "exhaustion_score":             exh,
            "pullback_class":               r["pullback_class"],
            "rsi_raw":                      rsi_raw,
        })
        out_rows.append({
            "ticker":        ticker,
            "snapshot_date": sdate,
            "return_1d":     r["return_1d"],
            "return_3d":     r["return_3d"],
            "return_5d":     r["return_5d"],
            "return_10d":    r["return_10d"],
            "return_20d":    r["return_20d"],
        })

    # ── Upsert components ─────────────────────────────────────────────────
    n_comp = n_out = 0
    with psycopg2.connect(research_url) as conn, conn.cursor() as cur:
        for c in comp_rows:
            cur.execute("""
                INSERT INTO alpha_score_components (
                    ticker, snapshot_date,
                    score_total, trend_component, momentum_component, volume_component,
                    volatility_component, pattern_component, breakout_component,
                    support_resistance_component,
                    bull_flag_count, bear_flag_count,
                    patterns_detected, scanner_rank,
                    atr_pct_raw, rs_score, regime_score, exhaustion_score,
                    pullback_class, rsi_raw
                ) VALUES (
                    %(ticker)s, %(snapshot_date)s,
                    %(score_total)s, %(trend_component)s, %(momentum_component)s, %(volume_component)s,
                    %(volatility_component)s, %(pattern_component)s, %(breakout_component)s,
                    %(support_resistance_component)s,
                    %(bull_flag_count)s, %(bear_flag_count)s,
                    %(patterns_detected)s, %(scanner_rank)s,
                    %(atr_pct_raw)s, %(rs_score)s, %(regime_score)s, %(exhaustion_score)s,
                    %(pullback_class)s, %(rsi_raw)s
                )
                ON CONFLICT (ticker, snapshot_date) DO UPDATE SET
                    score_total                  = EXCLUDED.score_total,
                    trend_component              = EXCLUDED.trend_component,
                    momentum_component           = EXCLUDED.momentum_component,
                    volume_component             = EXCLUDED.volume_component,
                    volatility_component         = EXCLUDED.volatility_component,
                    pattern_component            = EXCLUDED.pattern_component,
                    breakout_component           = EXCLUDED.breakout_component,
                    support_resistance_component = EXCLUDED.support_resistance_component,
                    bull_flag_count              = EXCLUDED.bull_flag_count,
                    bear_flag_count              = EXCLUDED.bear_flag_count,
                    patterns_detected            = EXCLUDED.patterns_detected,
                    scanner_rank                 = EXCLUDED.scanner_rank,
                    atr_pct_raw                  = EXCLUDED.atr_pct_raw,
                    rs_score                     = EXCLUDED.rs_score,
                    regime_score                 = EXCLUDED.regime_score,
                    exhaustion_score             = EXCLUDED.exhaustion_score,
                    pullback_class               = EXCLUDED.pullback_class,
                    rsi_raw                      = EXCLUDED.rsi_raw,
                    created_at                   = NOW()
            """, c)
            n_comp += 1

        for o in out_rows:
            cur.execute("""
                INSERT INTO alpha_score_component_outcomes (
                    ticker, snapshot_date,
                    return_1d, return_3d, return_5d, return_10d, return_20d
                ) VALUES (
                    %(ticker)s, %(snapshot_date)s,
                    %(return_1d)s, %(return_3d)s, %(return_5d)s, %(return_10d)s, %(return_20d)s
                )
                ON CONFLICT (ticker, snapshot_date) DO UPDATE SET
                    return_1d   = COALESCE(EXCLUDED.return_1d,  alpha_score_component_outcomes.return_1d),
                    return_3d   = COALESCE(EXCLUDED.return_3d,  alpha_score_component_outcomes.return_3d),
                    return_5d   = EXCLUDED.return_5d,
                    return_10d  = COALESCE(EXCLUDED.return_10d, alpha_score_component_outcomes.return_10d),
                    return_20d  = COALESCE(EXCLUDED.return_20d, alpha_score_component_outcomes.return_20d),
                    resolved_at = NOW()
            """, o)
            n_out += 1

        conn.commit()

    return n_comp, n_out


# ── Calibration ───────────────────────────────────────────────────────────────

@dataclass
class CalibRow:
    component: str
    bucket: str
    n: int
    hit_1d: float | None
    hit_3d: float | None
    hit_5d: float | None
    hit_10d: float | None
    hit_20d: float | None
    avg_1d: float | None
    avg_3d: float | None
    avg_5d: float | None
    avg_10d: float | None
    avg_20d: float | None
    median_5d: float | None
    drawdown_5d: float | None
    sharpe_5d: float | None
    perm_p: float | None
    perm_pass: bool | None
    yearly: dict
    year_count: int
    status: str
    edge_5d: float | None


def _safe_hit(a: np.ndarray | None) -> float | None:
    return float(np.mean(a > 0)) if a is not None and len(a) > 0 else None

def _safe_mean(a: np.ndarray | None) -> float | None:
    return float(np.mean(a)) if a is not None and len(a) > 0 else None

def _bootstrap_p(arr: np.ndarray, universe: np.ndarray, iters: int = PERM_ITERS) -> float:
    obs  = float(np.mean(arr > 0))
    idx  = np.random.choice(len(universe), size=(iters, len(arr)), replace=True)
    null = np.mean(universe[idx] > 0, axis=1)
    return float(np.mean(null >= obs))

def _classify(n: int, hit5: float, p: float, yrs: int) -> str:
    if n >= PROMO_N and hit5 > PROMO_HIT and p < PROMO_P and yrs >= PROMO_YEARS:
        return "promoted"
    if n >= CAND_N and hit5 > CAND_HIT and p < CAND_P:
        return "candidate"
    return "rejected"


# ── Tier/bucket helpers ───────────────────────────────────────────────────────

def _score_bucket(v: float) -> str:
    if v < 20: return "0-20"
    if v < 40: return "20-40"
    if v < 60: return "40-60"
    if v < 80: return "60-80"
    return "80-100"

def _tier(v: float | None, lo: float = 40.0, hi: float = 70.0) -> str | None:
    if v is None: return None
    return "high" if v >= hi else ("low" if v < lo else "mid")

def _rsi_zone(v: float | None) -> str | None:
    if v is None: return None
    if v < 30: return "oversold<30"
    if v < 50: return "neutral 30-50"
    if v < 70: return "neutral 50-70"
    return "overbought>70"

def _atr_zone(v: float | None) -> str | None:
    if v is None: return None
    if v < 2.0: return "low<2%"
    if v < 4.0: return "mid 2-4%"
    if v < 7.0: return "high 4-7%"
    return "extreme>7%"

def _pat_bucket(n_pats: int) -> str:
    if n_pats == 0: return "0"
    if n_pats <= 2: return "1-2"
    if n_pats <= 4: return "3-4"
    return "5+"

def _rank_bucket(rank: int | None, total_per_date: float) -> str | None:
    """Quartile of scanner_rank."""
    if rank is None or total_per_date <= 0: return None
    pct = rank / total_per_date
    if pct <= 0.25: return "top_quartile"
    if pct <= 0.50: return "2nd_quartile"
    if pct <= 0.75: return "3rd_quartile"
    return "bottom_quartile"


def run_calibration(research_url: str) -> list[CalibRow]:
    """
    Load all resolved component rows, group by (component, bucket),
    compute statistics, return CalibRow list.
    """
    with psycopg2.connect(research_url) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                c.ticker,
                c.snapshot_date::text AS snapshot_date,
                c.score_total,
                c.trend_component, c.momentum_component, c.volume_component,
                c.volatility_component, c.pattern_component, c.breakout_component,
                c.support_resistance_component,
                c.bull_flag_count, c.bear_flag_count,
                c.scanner_rank,
                c.atr_pct_raw, c.rs_score, c.regime_score, c.exhaustion_score,
                c.pullback_class, c.rsi_raw,
                c.patterns_detected,
                o.return_1d, o.return_3d, o.return_5d, o.return_10d, o.return_20d
            FROM alpha_score_components c
            JOIN alpha_score_component_outcomes o
              ON o.ticker = c.ticker AND o.snapshot_date = c.snapshot_date
            WHERE o.return_5d IS NOT NULL
            ORDER BY c.snapshot_date
        """)
        rows = cur.fetchall()

    if not rows:
        return []

    # Universe null distribution (all 5d returns)
    universe_5d = np.array([float(r["return_5d"]) for r in rows], dtype=float)
    baseline    = float(np.mean(universe_5d > 0))
    n_total     = len(rows)

    # Compute total tickers per date for rank_bucket
    per_date_totals: dict[str, int] = defaultdict(int)
    for r in rows:
        per_date_totals[r["snapshot_date"]] += 1

    # Build groups
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for r in rows:
        year = (r["snapshot_date"] or "2000-01-01")[:4]
        base = {
            "r1": r["return_1d"],  "r3": r["return_3d"],
            "r5": r["return_5d"],  "r10": r["return_10d"],
            "r20": r["return_20d"], "year": year,
        }

        score    = float(r["score_total"] or 0)
        pats     = _parse_patterns(r["patterns_detected"])
        n_pats   = len(pats)

        # ── Core score buckets ───────────────────────────────────────────
        groups[("score_total", _score_bucket(score))].append(base)

        # ── Component tiers ──────────────────────────────────────────────
        for comp, val in [
            ("trend_component",              r["trend_component"]),
            ("momentum_component",           r["momentum_component"]),
            ("volume_component",             r["volume_component"]),
            ("volatility_component",         r["volatility_component"]),
            ("pattern_component",            r["pattern_component"]),
            ("breakout_component",           r["breakout_component"]),
            ("support_resistance_component", r["support_resistance_component"]),
            ("rs_score",                     r["rs_score"]),
            ("regime_score",                 r["regime_score"]),
            ("exhaustion_score",             r["exhaustion_score"]),
        ]:
            t = _tier(float(val) if val is not None else None)
            if t:
                groups[(comp, t)].append(base)

        # ── Bull / bear flag counts ──────────────────────────────────────
        bf  = r["bull_flag_count"]
        brf = r["bear_flag_count"]
        if bf is not None:
            groups[("bull_flag_count", str(int(bf)))].append(base)
        if brf is not None:
            groups[("bear_flag_count", str(int(brf)))].append(base)

        # ── RSI zones ────────────────────────────────────────────────────
        rz = _rsi_zone(float(r["rsi_raw"]) if r["rsi_raw"] is not None else None)
        if rz:
            groups[("rsi_zone", rz)].append(base)

        # ── ATR zones ────────────────────────────────────────────────────
        az = _atr_zone(float(r["atr_pct_raw"]) if r["atr_pct_raw"] is not None else None)
        if az:
            groups[("volatility_raw", az)].append(base)

        # ── Pattern count ────────────────────────────────────────────────
        groups[("pattern_count", _pat_bucket(n_pats))].append(base)

        # ── Breakout presence ────────────────────────────────────────────
        has_brk = any(p in BREAKOUT_PATTERNS for p in pats)
        groups[("breakout_presence", "has_breakout" if has_brk else "no_breakout")].append(base)

        # ── Pullback class ───────────────────────────────────────────────
        pc = r["pullback_class"]
        if pc:
            groups[("pullback_class", str(pc))].append(base)

        # ── Scanner rank quartile ────────────────────────────────────────
        total_that_day = per_date_totals.get(r["snapshot_date"], 1)
        rq = _rank_bucket(r["scanner_rank"], total_that_day)
        if rq:
            groups[("scanner_rank", rq)].append(base)

    # ── Compute stats per group ───────────────────────────────────────────
    def _arr(items: list[dict], key: str) -> np.ndarray | None:
        vals = [x[key] for x in items if x[key] is not None]
        return np.array(vals, dtype=float) if len(vals) >= MIN_N else None

    results: list[CalibRow] = []

    for (comp, bucket), items in sorted(groups.items()):
        a5 = _arr(items, "r5")
        if a5 is None:
            continue

        a1  = _arr(items, "r1")
        a3  = _arr(items, "r3")
        a10 = _arr(items, "r10")
        a20 = _arr(items, "r20")

        n      = len(a5)
        hit5   = float(np.mean(a5 > 0))
        avg5   = float(np.mean(a5))
        med5   = float(np.median(a5))
        std5   = float(np.std(a5, ddof=1)) if n > 1 else 0.0
        neg5   = a5[a5 < 0]
        dd5    = float(np.mean(neg5)) if len(neg5) > 0 else 0.0
        sharpe = float((avg5 / std5) * float(np.sqrt(252 / 5))) if std5 > 0 else 0.0
        edge   = hit5 - baseline

        years  = [x["year"] for x in items if x["r5"] is not None]
        yr_set = sorted(set(years))

        # Yearly breakdown
        yearly: dict[str, dict] = {}
        for yr in yr_set:
            sub = a5[[y == yr for y in years]]
            if len(sub) >= 3:
                yearly[yr] = {
                    "n":      int(len(sub)),
                    "hit5d":  round(float(np.mean(sub > 0)), 4),
                    "avg5d":  round(float(np.mean(sub)), 6),
                }

        perm_p = _bootstrap_p(a5, universe_5d)
        status = _classify(n, hit5, perm_p, len(yr_set))

        results.append(CalibRow(
            component  = comp,
            bucket     = bucket,
            n          = n,
            hit_1d     = _safe_hit(a1),
            hit_3d     = _safe_hit(a3),
            hit_5d     = round(hit5, 4),
            hit_10d    = _safe_hit(a10),
            hit_20d    = _safe_hit(a20),
            avg_1d     = _safe_mean(a1),
            avg_3d     = _safe_mean(a3),
            avg_5d     = round(avg5, 6),
            avg_10d    = _safe_mean(a10),
            avg_20d    = _safe_mean(a20),
            median_5d  = round(med5, 6),
            drawdown_5d= round(dd5, 6),
            sharpe_5d  = round(sharpe, 4),
            perm_p     = round(perm_p, 6),
            perm_pass  = perm_p < 0.05,
            yearly     = yearly,
            year_count = len(yr_set),
            status     = status,
            edge_5d    = round(edge, 4),
        ))

    return results


# ── DB write ──────────────────────────────────────────────────────────────────

def write_calibration(research_url: str, rows: list[CalibRow], run_date: str | None = None) -> int:
    if not rows:
        return 0
    today = run_date or date.today().isoformat()

    with psycopg2.connect(research_url) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("""
                INSERT INTO alpha_score_calibration_runs (
                    run_date, component, bucket, n_signals,
                    hit_rate_1d, hit_rate_3d, hit_rate_5d, hit_rate_10d, hit_rate_20d,
                    avg_return_1d, avg_return_3d, avg_return_5d, avg_return_10d, avg_return_20d,
                    median_return_5d, avg_drawdown_5d, sharpe_5d,
                    permutation_p, permutation_pass,
                    yearly_breakdown, year_count, status, edge_5d
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (run_date, component, bucket) DO UPDATE SET
                    n_signals        = EXCLUDED.n_signals,
                    hit_rate_5d      = EXCLUDED.hit_rate_5d,
                    hit_rate_1d      = EXCLUDED.hit_rate_1d,
                    hit_rate_3d      = EXCLUDED.hit_rate_3d,
                    hit_rate_10d     = EXCLUDED.hit_rate_10d,
                    hit_rate_20d     = EXCLUDED.hit_rate_20d,
                    avg_return_5d    = EXCLUDED.avg_return_5d,
                    avg_return_1d    = EXCLUDED.avg_return_1d,
                    avg_return_3d    = EXCLUDED.avg_return_3d,
                    avg_return_10d   = EXCLUDED.avg_return_10d,
                    avg_return_20d   = EXCLUDED.avg_return_20d,
                    median_return_5d = EXCLUDED.median_return_5d,
                    avg_drawdown_5d  = EXCLUDED.avg_drawdown_5d,
                    sharpe_5d        = EXCLUDED.sharpe_5d,
                    permutation_p    = EXCLUDED.permutation_p,
                    permutation_pass = EXCLUDED.permutation_pass,
                    yearly_breakdown = EXCLUDED.yearly_breakdown,
                    year_count       = EXCLUDED.year_count,
                    status           = EXCLUDED.status,
                    edge_5d          = EXCLUDED.edge_5d,
                    created_at       = NOW()
            """, (
                today, r.component, r.bucket, r.n,
                r.hit_1d, r.hit_3d, r.hit_5d, r.hit_10d, r.hit_20d,
                r.avg_1d, r.avg_3d, r.avg_5d, r.avg_10d, r.avg_20d,
                r.median_5d, r.drawdown_5d, r.sharpe_5d,
                r.perm_p, r.perm_pass,
                json.dumps(r.yearly), r.year_count, r.status, r.edge_5d,
            ))
        conn.commit()

    return len(rows)


# ── Report ────────────────────────────────────────────────────────────────────

# Display order for the ranking table
COMPONENT_ORDER = [
    "score_total",
    "trend_component", "momentum_component", "volume_component",
    "volatility_component", "pattern_component",
    "breakout_component", "support_resistance_component",
    "rs_score", "regime_score", "exhaustion_score",
    "bull_flag_count", "bear_flag_count",
    "rsi_zone", "volatility_raw",
    "pattern_count", "breakout_presence",
    "pullback_class", "scanner_rank",
]


def print_ranking_table(results: list[CalibRow], baseline: float) -> None:
    from collections import defaultdict as dd

    by_comp: dict[str, list[CalibRow]] = dd(list)
    for r in results:
        by_comp[r.component].append(r)

    print()
    print("=" * 116)
    print("  ATLAS SCORE — COMPONENT ALPHA DECOMPOSITION")
    print(f"  Universe 5d baseline: {baseline:.1%}  |  "
          f"Edge = component hit rate minus universe baseline  |  "
          f"PASS = permutation p < 0.05")
    print("=" * 116)

    HDR = (f"  {'Bucket':<22}  {'N':>5}  "
           f"{'1d Hit':>7}  {'3d Hit':>7}  {'5d Hit':>7}  {'10d Hit':>8}  {'20d Hit':>8}  "
           f"{'Avg5d%':>8}  {'Med5d%':>8}  {'Edge':>6}  {'Sharpe':>7}  {'P-val':>7}  {'Pass':>4}  Status")

    promoted:  list[CalibRow] = []
    candidate: list[CalibRow] = []
    destroyer: list[CalibRow] = []

    seen = set(by_comp.keys())
    order = COMPONENT_ORDER + sorted(seen - set(COMPONENT_ORDER))

    for comp in order:
        rows = by_comp.get(comp)
        if not rows:
            continue
        rows = sorted(rows, key=lambda r: -(r.hit_5d or 0))

        print(f"\n--- {comp.upper().replace('_', ' ')} ---")
        print(HDR)
        print("  " + "-" * 112)

        for r in rows:
            def pct(v, w=7):
                return (f"{v:.1%}").rjust(w) if v is not None else " " * (w - 1) + "-"
            def ret(v, w=8):
                return (f"{v*100:+.2f}%").rjust(w) if v is not None else " " * (w - 1) + "-"
            def pv(v, w=7):
                return (f"{v:.3f}").rjust(w) if v is not None else " " * (w - 1) + "-"
            def sh(v, w=7):
                return (f"{v:+.2f}").rjust(w) if v is not None else " " * (w - 1) + "-"
            def edge_s(v, w=6):
                return (f"{v:+.1%}").rjust(w) if v is not None else " " * (w - 1) + "-"

            pass_str = "PASS" if r.perm_pass else "FAIL"
            star = "*" if r.status == "promoted" else ("o" if r.status == "candidate" else " ")
            print(f"  {r.bucket:<22}  {r.n:>5}  "
                  f"{pct(r.hit_1d)}  {pct(r.hit_3d)}  {pct(r.hit_5d)}  "
                  f"{pct(r.hit_10d, 8)}  {pct(r.hit_20d, 8)}  "
                  f"{ret(r.avg_5d)}  {ret(r.median_5d)}  "
                  f"{edge_s(r.edge_5d)}  {sh(r.sharpe_5d)}  {pv(r.perm_p)}  {pass_str}  "
                  f"{star}{r.status}")

            if r.status == "promoted":
                promoted.append(r)
            elif r.status == "candidate":
                candidate.append(r)
            if r.n >= CAND_N and r.hit_5d is not None and r.hit_5d < 0.48:
                destroyer.append(r)

    # Summary
    print()
    print("=" * 116)
    print(f"  SUMMARY: {len(promoted)} PROMOTED  |  {len(candidate)} CANDIDATE  |  "
          f"{len(destroyer)} ALPHA DESTROYERS")
    print()

    if promoted:
        print("  ALPHA GENERATORS (promoted):")
        for r in sorted(promoted, key=lambda x: -(x.edge_5d or 0)):
            print(f"    [{r.component}] {r.bucket:<22}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  "
                  f"sharpe={r.sharpe_5d:+.2f}  p={r.perm_p:.3f}")

    if candidate:
        print()
        print("  PROMISING (needs more data):")
        for r in sorted(candidate, key=lambda x: -(x.edge_5d or 0)):
            print(f"    [{r.component}] {r.bucket:<22}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  p={r.perm_p:.3f}")

    if destroyer:
        print()
        print("  ALPHA DESTROYERS (hit_5d < 48%, n >= 20):")
        for r in sorted(destroyer, key=lambda x: (x.hit_5d or 1.0)):
            print(f"    [{r.component}] {r.bucket:<22}  "
                  f"n={r.n:4d}  5d={r.hit_5d:.1%}  edge={r.edge_5d:+.1%}  p={r.perm_p:.3f}")

    print("=" * 116)


# ── Nightly entry point ───────────────────────────────────────────────────────

def run_nightly_calibration(run_date: date | None = None, research_url: str | None = None) -> dict:
    """
    Nightly pipeline entry point.  Populates components then runs calibration.
    Returns a stats dict.  Never raises — caller wraps in try/except.
    """
    import os
    url = research_url or os.environ.get("DATABASE_URL", "")
    if not url:
        return {"status": "skipped", "reason": "DATABASE_URL not set"}

    rd = (run_date or date.today()).isoformat()

    n_comp, n_out = populate_components(url)
    rows = run_calibration(url)
    n_written = write_calibration(url, rows, run_date=rd)

    promoted  = sum(1 for r in rows if r.status == "promoted")
    candidate = sum(1 for r in rows if r.status == "candidate")

    return {
        "status":     "complete",
        "n_components": n_comp,
        "n_outcomes":   n_out,
        "n_cal_rows":   n_written,
        "promoted":     promoted,
        "candidate":    candidate,
    }
