"""
atlas_research.calibration.engine
-----------------------------------
Calibration bridge: syncs Atlas Alpha signal snapshots into atlas_research,
enriches with 1d/3d forward returns from raw_bars, then computes calibration
stats per score bucket, pattern, exhaustion flag, smart-gate, and direction.

Two-phase operation:
  Phase 1 — sync_snapshots()
    Reads atlas_alpha.signal_snapshots (resolved outcomes only) and upserts
    into atlas_research.alpha_signal_snapshots. Fills return_1d / return_3d
    from atlas_research.raw_bars since atlas_alpha only resolves 5d/10d/20d.

  Phase 2 — run_calibration()
    Loads all resolved alpha_signal_snapshots, groups by signal_type × key,
    computes hit rates / avg returns / Sharpe / year breakdown / robustness,
    writes results to alpha_signal_calibrations with a promotion status.

Promotion rules (applied at 5d horizon):
  promoted   n >= 50  AND hit_rate > 0.54 AND p < 0.05  AND year_count >= 3
  candidate  n >= 20  AND hit_rate > 0.52 AND p < 0.10
  rejected   everything else
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np
import psycopg2
import psycopg2.extras
from scipy.stats import binomtest

# ── Promotion thresholds ─────────────────────────────────────────────────────

PROMO_N         = 50
PROMO_HIT       = 0.54
PROMO_P         = 0.05
PROMO_YEARS     = 3

CAND_N          = 20
CAND_HIT        = 0.52
CAND_P          = 0.10

PERM_ITERS      = 5_000
MIN_N_REPORT    = 10     # minimum sample to include in any analysis


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class CalibrationRow:
    signal_type: str
    signal_key: str
    n_signals: int
    n_resolved: int
    hit_rate_1d: float | None
    hit_rate_3d: float | None
    hit_rate_5d: float | None
    hit_rate_10d: float | None
    hit_rate_20d: float | None
    avg_return_1d: float | None
    avg_return_3d: float | None
    avg_return_5d: float | None
    avg_return_10d: float | None
    avg_return_20d: float | None
    median_return_5d: float | None
    std_return_5d: float | None
    avg_drawdown_5d: float | None
    sharpe_5d: float | None
    year_breakdown: dict
    min_n_per_year: int | None
    sanity_pass: bool | None
    permutation_p_value: float | None
    year_count: int
    status: str
    notes: str


# ── Database helpers ─────────────────────────────────────────────────────────

def _alpha_conn(url: str):
    return psycopg2.connect(url)

def _research_conn(url: str):
    return psycopg2.connect(url)


# ── Phase 1: Sync snapshots ──────────────────────────────────────────────────

def sync_snapshots(alpha_url: str, research_url: str) -> int:
    """Pull signal_snapshots from atlas_alpha and compute all returns from atlas_research.raw_bars.

    We do NOT rely on atlas_alpha's outcome resolution (which requires 20d to pass and
    an active server). Instead, we pull all snapshots at least 7 calendar days old and
    compute 1d/3d/5d/10d/20d returns ourselves from raw_bars.
    """

    with _alpha_conn(alpha_url) as aconn, aconn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as acur:
        acur.execute("""
            SELECT
                ticker,
                snapshot_date::text        AS snapshot_date,
                score                      AS atlas_score,
                direction,
                bullish_probability        AS bull_probability,
                trend_score,
                momentum_score,
                volume_score,
                rs_score,
                regime_score,
                exhaustion_score,
                rsi,
                rsi_zone,
                rvol,
                atr_pct,
                exhaustion_signal,
                distribution_top,
                parabolic_rise,
                patterns,
                smart_gate_enter,
                pullback_class,
                -- decomposition columns (NULL for rows saved before migration)
                options_score,
                adx,
                adx_trending,
                alignment_score,
                macd_histogram,
                rsi_divergence,
                golden_cross,
                death_cross,
                vol_squeeze
            FROM signal_snapshots
            WHERE snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
        """)
        rows = acur.fetchall()

    if not rows:
        print("  [sync] No snapshots older than 7 days found in atlas_alpha.signal_snapshots.")
        return 0

    print(f"  [sync] Pulled {len(rows)} snapshots from atlas_alpha; computing returns from raw_bars...")

    tickers = list({r["ticker"] for r in rows})
    min_date = min(r["snapshot_date"] for r in rows)

    # Load raw_bars for all relevant tickers from atlas_research
    bar_map: dict[str, dict[str, float]] = {}   # bar_map[ticker][date_str] = close

    with _research_conn(research_url) as rconn, rconn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as rcur:
        rcur.execute("""
            SELECT ticker, date::text AS date, close
            FROM raw_bars
            WHERE ticker = ANY(%s)
              AND date >= %s::date - INTERVAL '1 day'
            ORDER BY ticker, date
        """, (tickers, min_date))
        for br in rcur.fetchall():
            t = br["ticker"]
            if t not in bar_map:
                bar_map[t] = {}
            bar_map[t][br["date"]] = float(br["close"])

    enriched = []
    no_bars = 0
    for r in rows:
        ticker   = r["ticker"]
        sig_date = r["snapshot_date"]

        ticker_bars  = bar_map.get(ticker, {})
        entry_close  = ticker_bars.get(sig_date)

        if entry_close is None or entry_close == 0:
            no_bars += 1
            continue   # skip tickers not in atlas_research (e.g. indices, ETFs not yet ingested)

        sorted_after = sorted(d for d in ticker_bars if d > sig_date)

        def pct_ret(n: int) -> float | None:
            if len(sorted_after) < n:
                return None
            exit_close = ticker_bars[sorted_after[n - 1]]
            return None if exit_close == 0 else (exit_close - entry_close) / entry_close

        enriched.append({
            "ticker":           ticker,
            "snapshot_date":    sig_date,
            "atlas_score":      r["atlas_score"],
            "direction":        r["direction"],
            "bull_probability": r["bull_probability"],
            "trend_score":      r["trend_score"],
            "momentum_score":   r["momentum_score"],
            "volume_score":     r["volume_score"],
            "rs_score":         r["rs_score"],
            "regime_score":     r["regime_score"],
            "exhaustion_score": r["exhaustion_score"],
            "rsi":              r["rsi"],
            "rsi_zone":         r["rsi_zone"],
            "rvol":             r["rvol"],
            "atr_pct":          r["atr_pct"],
            "exhaustion_signal": r["exhaustion_signal"],
            "distribution_top": r["distribution_top"],
            "parabolic_rise":   r["parabolic_rise"],
            "patterns":         r["patterns"],
            "smart_gate_enter": r["smart_gate_enter"],
            "pullback_class":   r["pullback_class"],
            "options_score":    r.get("options_score"),
            "adx":              r.get("adx"),
            "adx_trending":     r.get("adx_trending"),
            "alignment_score":  r.get("alignment_score"),
            "macd_histogram":   r.get("macd_histogram"),
            "rsi_divergence":   r.get("rsi_divergence"),
            "golden_cross":     r.get("golden_cross"),
            "death_cross":      r.get("death_cross"),
            "vol_squeeze":      r.get("vol_squeeze"),
            "return_1d":        pct_ret(1),
            "return_3d":        pct_ret(3),
            "return_5d":        pct_ret(5),
            "return_10d":       pct_ret(10),
            "return_20d":       pct_ret(20),
        })

    if no_bars > 0:
        print(f"  [sync] Skipped {no_bars} snapshots (ticker not in atlas_research raw_bars)")

    with_5d = sum(1 for e in enriched if e["return_5d"] is not None)
    print(f"  [sync] {len(enriched)} snapshots enriched; {with_5d} have 5d returns available")

    if not enriched:
        return 0

    # Upsert into atlas_research.alpha_signal_snapshots
    with _research_conn(research_url) as rconn:
        with rconn.cursor() as rcur:
            for row in enriched:
                rcur.execute("""
                    INSERT INTO alpha_signal_snapshots (
                        ticker, snapshot_date, atlas_score, direction, bull_probability,
                        trend_score, momentum_score, volume_score, rs_score, regime_score, exhaustion_score,
                        rsi, rsi_zone, rvol, atr_pct,
                        exhaustion_signal, distribution_top, parabolic_rise,
                        patterns, smart_gate_enter, pullback_class,
                        options_score, adx, adx_trending, alignment_score,
                        macd_histogram, rsi_divergence, golden_cross, death_cross, vol_squeeze,
                        return_1d, return_3d, return_5d, return_10d, return_20d
                    ) VALUES (
                        %(ticker)s, %(snapshot_date)s, %(atlas_score)s, %(direction)s, %(bull_probability)s,
                        %(trend_score)s, %(momentum_score)s, %(volume_score)s, %(rs_score)s, %(regime_score)s, %(exhaustion_score)s,
                        %(rsi)s, %(rsi_zone)s, %(rvol)s, %(atr_pct)s,
                        %(exhaustion_signal)s, %(distribution_top)s, %(parabolic_rise)s,
                        %(patterns)s, %(smart_gate_enter)s, %(pullback_class)s,
                        %(options_score)s, %(adx)s, %(adx_trending)s, %(alignment_score)s,
                        %(macd_histogram)s, %(rsi_divergence)s, %(golden_cross)s, %(death_cross)s, %(vol_squeeze)s,
                        %(return_1d)s, %(return_3d)s, %(return_5d)s, %(return_10d)s, %(return_20d)s
                    )
                    ON CONFLICT (ticker, snapshot_date) DO UPDATE SET
                        return_1d        = EXCLUDED.return_1d,
                        return_3d        = EXCLUDED.return_3d,
                        return_5d        = EXCLUDED.return_5d,
                        return_10d       = EXCLUDED.return_10d,
                        return_20d       = EXCLUDED.return_20d,
                        atlas_score      = EXCLUDED.atlas_score,
                        direction        = EXCLUDED.direction,
                        bull_probability = EXCLUDED.bull_probability,
                        patterns         = EXCLUDED.patterns,
                        smart_gate_enter = EXCLUDED.smart_gate_enter,
                        -- update decomposition fields when re-syncing (non-NULL overwrites NULL)
                        options_score    = COALESCE(EXCLUDED.options_score,   alpha_signal_snapshots.options_score),
                        adx              = COALESCE(EXCLUDED.adx,             alpha_signal_snapshots.adx),
                        adx_trending     = COALESCE(EXCLUDED.adx_trending,    alpha_signal_snapshots.adx_trending),
                        alignment_score  = COALESCE(EXCLUDED.alignment_score, alpha_signal_snapshots.alignment_score),
                        macd_histogram   = COALESCE(EXCLUDED.macd_histogram,  alpha_signal_snapshots.macd_histogram),
                        rsi_divergence   = COALESCE(EXCLUDED.rsi_divergence,  alpha_signal_snapshots.rsi_divergence),
                        golden_cross     = COALESCE(EXCLUDED.golden_cross,    alpha_signal_snapshots.golden_cross),
                        death_cross      = COALESCE(EXCLUDED.death_cross,     alpha_signal_snapshots.death_cross),
                        vol_squeeze      = COALESCE(EXCLUDED.vol_squeeze,     alpha_signal_snapshots.vol_squeeze),
                        synced_at        = NOW()
                """, {
                    **row,
                    "patterns": json.dumps(row["patterns"]) if isinstance(row["patterns"], (list, dict)) else row["patterns"],
                })
        rconn.commit()

    return len(enriched)


# ── Phase 2: Calibration computation ────────────────────────────────────────

def _stat_block(arr_5d: np.ndarray,
                arr_1d: np.ndarray | None,
                arr_3d: np.ndarray | None,
                arr_10d: np.ndarray | None,
                arr_20d: np.ndarray | None,
                years: list[str],
                universe_5d: np.ndarray | None = None,
                perm_iters: int = PERM_ITERS) -> dict:
    """Compute all calibration statistics for a group of signals.

    universe_5d: the full universe of 5d returns (used as the null distribution
    for the permutation test). If None, falls back to binomial test against 0.5.
    """
    n = len(arr_5d)
    if n < MIN_N_REPORT:
        return {}

    def _safe_mean(a: np.ndarray | None) -> float | None:
        return float(np.mean(a)) if a is not None and len(a) > 0 else None

    def _hit(a: np.ndarray | None) -> float | None:
        return float(np.mean(a > 0)) if a is not None and len(a) > 0 else None

    # Core 5d stats
    hit_5d      = float(np.mean(arr_5d > 0))
    avg_5d      = float(np.mean(arr_5d))
    med_5d      = float(np.median(arr_5d))
    std_5d      = float(np.std(arr_5d, ddof=1)) if n > 1 else 0.0
    neg_5d      = arr_5d[arr_5d < 0]
    drawdown_5d = float(np.mean(neg_5d)) if len(neg_5d) > 0 else 0.0

    # Sharpe annualized (5-trading-day hold → 252/5 periods per year)
    sharpe_5d = (avg_5d / std_5d) * np.sqrt(252 / 5) if std_5d > 0 else 0.0

    # Permutation test: bootstrap from universe null distribution.
    # Under the null hypothesis "any random draw from the universe",
    # how often do we draw n signals with hit_rate >= observed?
    # This tests for ALPHA above the market baseline, not above 50%.
    if universe_5d is not None and len(universe_5d) > n:
        perm_p = _bootstrap_p(arr_5d, universe_5d, perm_iters)
    else:
        k = int(np.sum(arr_5d > 0))
        bt = binomtest(k, n, 0.50, alternative="greater")
        perm_p = float(bt.pvalue)

    # Binomial sanity test (vs 50% — conservative signal-validity check)
    k = int(np.sum(arr_5d > 0))
    bt = binomtest(k, n, 0.50, alternative="greater")
    sanity_pass = bool(bt.pvalue < 0.05)

    # Year breakdown
    year_bd: dict[str, dict] = {}
    for yr in sorted(set(years)):
        mask = np.array([y == yr for y in years])
        sub = arr_5d[mask]
        if len(sub) >= 3:
            year_bd[yr] = {
                "n":             int(len(sub)),
                "hit_rate_5d":   round(float(np.mean(sub > 0)), 4),
                "avg_return_5d": round(float(np.mean(sub)), 6),
            }

    min_n_yr   = min((v["n"] for v in year_bd.values()), default=None)
    year_count = len(year_bd)

    status = _classify(n, hit_5d, perm_p, year_count)

    return {
        "n_resolved":          n,
        "hit_rate_1d":         _hit(arr_1d),
        "hit_rate_3d":         _hit(arr_3d),
        "hit_rate_5d":         round(hit_5d, 4),
        "hit_rate_10d":        _hit(arr_10d),
        "hit_rate_20d":        _hit(arr_20d),
        "avg_return_1d":       _safe_mean(arr_1d),
        "avg_return_3d":       _safe_mean(arr_3d),
        "avg_return_5d":       round(avg_5d, 6),
        "avg_return_10d":      _safe_mean(arr_10d),
        "avg_return_20d":      _safe_mean(arr_20d),
        "median_return_5d":    round(med_5d, 6),
        "std_return_5d":       round(std_5d, 6),
        "avg_drawdown_5d":     round(drawdown_5d, 6),
        "sharpe_5d":           round(float(sharpe_5d), 4),
        "year_breakdown":      year_bd,
        "min_n_per_year":      min_n_yr,
        "sanity_pass":         sanity_pass,
        "permutation_p_value": round(perm_p, 6),
        "year_count":          year_count,
        "status":              status,
    }


def _bootstrap_p(arr: np.ndarray, universe: np.ndarray, iters: int) -> float:
    """
    Bootstrap permutation test: under the null 'any random n draws from the universe',
    how often does the hit_rate >= the observed hit_rate?
    This tests for alpha above the market baseline rather than above 50%.
    """
    obs = float(np.mean(arr > 0))
    n = len(arr)
    indices = np.random.choice(len(universe), size=(iters, n), replace=True)
    null_hits = np.mean(universe[indices] > 0, axis=1)
    return float(np.mean(null_hits >= obs))


def _classify(n: int, hit_5d: float, p: float, year_count: int) -> str:
    if n >= PROMO_N and hit_5d > PROMO_HIT and p < PROMO_P and year_count >= PROMO_YEARS:
        return "promoted"
    if n >= CAND_N and hit_5d > CAND_HIT and p < CAND_P:
        return "candidate"
    return "rejected"


def _score_bucket(score: float) -> str:
    if score < 20:    return "0-20"
    if score < 40:    return "20-40"
    if score < 60:    return "40-60"
    if score < 80:    return "60-80"
    return "80-100"


def run_calibration(research_url: str, min_samples: int = MIN_N_REPORT) -> list[CalibrationRow]:
    """Load alpha_signal_snapshots, compute calibration per group, return rows."""
    with _research_conn(research_url) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT
                ticker, snapshot_date::text AS snapshot_date,
                atlas_score, direction, bull_probability,
                trend_score, momentum_score, volume_score, rs_score,
                regime_score, exhaustion_score,
                rsi, exhaustion_signal, distribution_top, parabolic_rise,
                patterns, smart_gate_enter, pullback_class,
                return_1d, return_3d, return_5d, return_10d, return_20d
            FROM alpha_signal_snapshots
            WHERE return_5d IS NOT NULL
            ORDER BY snapshot_date
        """)
        rows = cur.fetchall()

    if not rows:
        return []

    # ── Build universe null distribution ────────────────────────────────────
    # The baseline 5d return pool for permutation tests.
    # We use all resolved 5d returns as the null — i.e., "what happens if you
    # randomly pick any signal from our universe?"
    universe_5d_vals = [float(r["return_5d"]) for r in rows if r["return_5d"] is not None]
    universe_5d = np.array(universe_5d_vals, dtype=float) if universe_5d_vals else None
    baseline_hit = float(np.mean(universe_5d > 0)) if universe_5d is not None else 0.5
    print(f"  [calibration] {len(rows)} snapshots loaded | "
          f"universe baseline 5d hit: {baseline_hit:.1%} | "
          f"median 5d ret: {float(np.median(universe_5d))*100:+.2f}%")

    # Build arrays indexed by grouping keys
    # Group schemas: score_bucket, pattern, direction, exhaustion, smart_gate, component
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for r in rows:
        score = r["atlas_score"] or 0.0
        year  = (r["snapshot_date"] or "2000-01-01")[:4]
        base  = {
            "r1":   r["return_1d"],
            "r3":   r["return_3d"],
            "r5":   r["return_5d"],
            "r10":  r["return_10d"],
            "r20":  r["return_20d"],
            "year": year,
        }

        # Score bucket
        groups[("score_bucket", _score_bucket(score))].append(base)

        # Direction
        direction = (r["direction"] or "neutral").lower()
        groups[("direction", direction)].append(base)

        # Patterns — explode JSONB array
        pats = r["patterns"]
        if isinstance(pats, list):
            pat_list = pats
        elif isinstance(pats, str):
            try:
                pat_list = json.loads(pats)
            except (json.JSONDecodeError, TypeError):
                pat_list = []
        else:
            pat_list = []
        for pat in pat_list:
            groups[("pattern", str(pat))].append(base)

        # Exhaustion
        exh = r["exhaustion_signal"]
        has_exh = exh is not None and exh not in ("none", "")
        groups[("exhaustion", "with_exhaustion" if has_exh else "no_exhaustion")].append(base)

        # Smart gate
        if r["smart_gate_enter"] is not None:
            groups[("smart_gate", "gate_enter" if r["smart_gate_enter"] else "gate_block")].append(base)

        # Component score tiers (trend, momentum)
        for comp_name, comp_val in [
            ("trend",    r["trend_score"]),
            ("momentum", r["momentum_score"]),
            ("volume",   r["volume_score"]),
            ("rs",       r["rs_score"]),
        ]:
            if comp_val is None:
                continue
            tier = "high" if comp_val >= 70 else ("low" if comp_val <= 30 else "mid")
            groups[(f"component_{comp_name}", tier)].append(base)

        # Bull probability tiers
        bp = r["bull_probability"]
        if bp is not None:
            bp_tier = "strong_bull" if bp > 0.70 else ("mild_bull" if bp > 0.55 else ("neutral_bp" if bp >= 0.45 else "bear_bp"))
            groups[("bull_prob_tier", bp_tier)].append(base)

    def _extract(items: list[dict], key: str) -> np.ndarray | None:
        vals = [x[key] for x in items if x[key] is not None]
        return np.array(vals, dtype=float) if vals else None

    today = date.today().isoformat()
    results: list[CalibrationRow] = []

    for (sig_type, sig_key), items in groups.items():
        n_total = len(items)
        arr_5d  = _extract(items, "r5")
        if arr_5d is None or len(arr_5d) < min_samples:
            continue

        arr_1d  = _extract(items, "r1")
        arr_3d  = _extract(items, "r3")
        arr_10d = _extract(items, "r10")
        arr_20d = _extract(items, "r20")
        years   = [x["year"] for x in items if x["r5"] is not None]

        stats = _stat_block(arr_5d, arr_1d, arr_3d, arr_10d, arr_20d, years,
                            universe_5d=universe_5d)
        if not stats:
            continue

        results.append(CalibrationRow(
            signal_type       = sig_type,
            signal_key        = sig_key,
            n_signals         = n_total,
            n_resolved        = stats["n_resolved"],
            hit_rate_1d       = stats["hit_rate_1d"],
            hit_rate_3d       = stats["hit_rate_3d"],
            hit_rate_5d       = stats["hit_rate_5d"],
            hit_rate_10d      = stats["hit_rate_10d"],
            hit_rate_20d      = stats["hit_rate_20d"],
            avg_return_1d     = stats["avg_return_1d"],
            avg_return_3d     = stats["avg_return_3d"],
            avg_return_5d     = stats["avg_return_5d"],
            avg_return_10d    = stats["avg_return_10d"],
            avg_return_20d    = stats["avg_return_20d"],
            median_return_5d  = stats["median_return_5d"],
            std_return_5d     = stats["std_return_5d"],
            avg_drawdown_5d   = stats["avg_drawdown_5d"],
            sharpe_5d         = stats["sharpe_5d"],
            year_breakdown    = stats["year_breakdown"],
            min_n_per_year    = stats["min_n_per_year"],
            sanity_pass       = stats["sanity_pass"],
            permutation_p_value = stats["permutation_p_value"],
            year_count        = stats["year_count"],
            status            = stats["status"],
            notes             = _notes(sig_type, sig_key, stats),
        ))

    return results


def _notes(sig_type: str, sig_key: str, stats: dict) -> str:
    hit = stats.get("hit_rate_5d", 0.5)
    p   = stats.get("permutation_p_value", 1.0)
    n   = stats.get("n_resolved", 0)
    yrs = stats.get("year_count", 0)
    status = stats.get("status", "rejected")

    if status == "promoted":
        return f"Validated edge: {hit:.1%} 5d hit rate over {n} signals across {yrs} years (p={p:.3f})"
    if status == "candidate":
        return f"Promising: {hit:.1%} 5d hit rate over {n} signals — needs more data (p={p:.3f})"
    if hit > 0.52 and n < CAND_N:
        return f"Insufficient sample size: only {n} signals (need {CAND_N}+)"
    if p >= CAND_P:
        return f"Not statistically significant: p={p:.3f} (need < {CAND_P})"
    return f"Below edge threshold: {hit:.1%} 5d hit rate (need > {CAND_HIT:.0%})"


# ── Write calibration to DB ──────────────────────────────────────────────────

def write_calibration(research_url: str, rows: list[CalibrationRow], cal_date: str | None = None) -> int:
    if not rows:
        return 0
    today = cal_date or date.today().isoformat()

    with _research_conn(research_url) as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute("""
                INSERT INTO alpha_signal_calibrations (
                    calibration_date, signal_type, signal_key,
                    n_signals, n_resolved,
                    hit_rate_1d, hit_rate_3d, hit_rate_5d, hit_rate_10d, hit_rate_20d,
                    avg_return_1d, avg_return_3d, avg_return_5d, avg_return_10d, avg_return_20d,
                    median_return_5d, std_return_5d, avg_drawdown_5d, sharpe_5d,
                    year_breakdown, min_n_per_year,
                    sanity_pass, permutation_p_value, year_count,
                    status, notes
                ) VALUES (
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (calibration_date, signal_type, signal_key) DO UPDATE SET
                    n_signals           = EXCLUDED.n_signals,
                    n_resolved          = EXCLUDED.n_resolved,
                    hit_rate_5d         = EXCLUDED.hit_rate_5d,
                    hit_rate_1d         = EXCLUDED.hit_rate_1d,
                    hit_rate_3d         = EXCLUDED.hit_rate_3d,
                    hit_rate_10d        = EXCLUDED.hit_rate_10d,
                    hit_rate_20d        = EXCLUDED.hit_rate_20d,
                    avg_return_5d       = EXCLUDED.avg_return_5d,
                    avg_return_1d       = EXCLUDED.avg_return_1d,
                    avg_return_3d       = EXCLUDED.avg_return_3d,
                    avg_return_10d      = EXCLUDED.avg_return_10d,
                    avg_return_20d      = EXCLUDED.avg_return_20d,
                    median_return_5d    = EXCLUDED.median_return_5d,
                    std_return_5d       = EXCLUDED.std_return_5d,
                    avg_drawdown_5d     = EXCLUDED.avg_drawdown_5d,
                    sharpe_5d           = EXCLUDED.sharpe_5d,
                    year_breakdown      = EXCLUDED.year_breakdown,
                    min_n_per_year      = EXCLUDED.min_n_per_year,
                    sanity_pass         = EXCLUDED.sanity_pass,
                    permutation_p_value = EXCLUDED.permutation_p_value,
                    year_count          = EXCLUDED.year_count,
                    status              = EXCLUDED.status,
                    notes               = EXCLUDED.notes,
                    updated_at          = NOW()
            """, (
                today, r.signal_type, r.signal_key,
                r.n_signals, r.n_resolved,
                r.hit_rate_1d, r.hit_rate_3d, r.hit_rate_5d, r.hit_rate_10d, r.hit_rate_20d,
                r.avg_return_1d, r.avg_return_3d, r.avg_return_5d, r.avg_return_10d, r.avg_return_20d,
                r.median_return_5d, r.std_return_5d, r.avg_drawdown_5d, r.sharpe_5d,
                json.dumps(r.year_breakdown), r.min_n_per_year,
                r.sanity_pass, r.permutation_p_value, r.year_count,
                r.status, r.notes,
            ))
        conn.commit()

    return len(rows)


# ── Report printing ──────────────────────────────────────────────────────────

def print_report(rows: list[CalibrationRow]) -> None:
    if not rows:
        print("\n[CALIBRATION] No data to report.")
        return

    by_type: dict[str, list[CalibrationRow]] = defaultdict(list)
    for r in rows:
        by_type[r.signal_type].append(r)

    print("\n" + "=" * 80)
    print("  ATLAS ALPHA CALIBRATION REPORT")
    print("=" * 80)

    # Compute baseline hit rate from all rows
    all_hit5 = [r.hit_rate_5d for r in rows if r.hit_rate_5d is not None]
    # Weighted baseline by n_resolved
    if all_hit5:
        weights = [r.n_resolved or 0 for r in rows if r.hit_rate_5d is not None]
        baseline = sum(h * w for h, w in zip(all_hit5, weights)) / max(sum(weights), 1)
    else:
        baseline = 0.50

    total_n = sum(r.n_resolved or 0 for r in rows if r.signal_type == "score_bucket") or 1

    print(f"\n  Market baseline 5d hit rate: {baseline:.1%}  "
          f"(avg across all {total_n} resolved signals)")
    print(f"  Signals above baseline = ALPHA | Below baseline = NEGATIVE ALPHA\n")

    for sig_type in ["score_bucket", "direction", "pattern", "exhaustion", "smart_gate",
                     "bull_prob_tier", "component_trend", "component_momentum",
                     "component_volume", "component_rs"]:
        type_rows = sorted(by_type.get(sig_type, []), key=lambda r: -(r.hit_rate_5d or 0))
        if not type_rows:
            continue

        print(f"\n-- {sig_type.upper().replace('_', ' ')} --")
        header = f"  {'Signal Key':<28}  {'N':>6}  {'5d Hit%':>8}  {'Edge':>6}  {'Avg 5d%':>8}  "
        header += f"{'Sharpe':>7}  {'P-val':>7}  {'Status':<12}"
        print(header)
        print("  " + "-" * (len(header) - 2))

        for r in type_rows:
            hit5  = f"{r.hit_rate_5d:.1%}"      if r.hit_rate_5d  is not None else "   —  "
            edge  = f"{(r.hit_rate_5d or 0) - baseline:+.1%}" if r.hit_rate_5d is not None else "   — "
            avg5  = f"{r.avg_return_5d*100:+.2f}%" if r.avg_return_5d is not None else "   —  "
            sh5   = f"{r.sharpe_5d:+.2f}"        if r.sharpe_5d    is not None else "   — "
            pv    = f"{r.permutation_p_value:.3f}" if r.permutation_p_value is not None else "   — "
            star  = "*" if r.status == "promoted" else ("o" if r.status == "candidate" else "-")
            status = f"{star} {r.status}"
            print(f"  {r.signal_key:<28}  {r.n_resolved:>6}  {hit5:>8}  {edge:>6}  {avg5:>8}  "
                  f"{sh5:>7}  {pv:>7}  {status:<12}")

    # Summary
    promoted  = [r for r in rows if r.status == "promoted"]
    candidate = [r for r in rows if r.status == "candidate"]
    rejected  = [r for r in rows if r.status == "rejected"]

    print("\n" + "=" * 80)
    print(f"  SUMMARY: {len(promoted)} promoted  |  {len(candidate)} candidate  |  {len(rejected)} rejected")

    if promoted:
        print("\n  ★ VALIDATED SIGNALS (promoted):")
        for r in sorted(promoted, key=lambda x: -(x.hit_rate_5d or 0)):
            print(f"    [{r.signal_type}] {r.signal_key:<28}  "
                  f"n={r.n_resolved}  hit5d={r.hit_rate_5d:.1%}  "
                  f"avg5d={r.avg_return_5d*100:+.2f}%  p={r.permutation_p_value:.3f}")
            print(f"      → {r.notes}")

    if rejected:
        false_edge = [r for r in rejected
                      if r.n_resolved and r.n_resolved >= CAND_N
                      and r.hit_rate_5d is not None and r.hit_rate_5d < 0.48]
        if false_edge:
            print("\n  ✗ FALSE-EDGE SIGNALS (rejected, bearish bias):")
            for r in sorted(false_edge, key=lambda x: (x.hit_rate_5d or 1.0)):
                print(f"    [{r.signal_type}] {r.signal_key:<28}  "
                      f"n={r.n_resolved}  hit5d={r.hit_rate_5d:.1%}  "
                      f"avg5d={r.avg_return_5d*100:+.2f}%")
                print(f"      → {r.notes}")

    print("=" * 80 + "\n")
