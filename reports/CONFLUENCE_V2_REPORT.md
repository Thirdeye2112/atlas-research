# Confluence Engine v2 Backtest Report
**Date generated:** 2026-06-15
**Backtest period:** 2015-01-01 to 2026-06-15
**Total observations:** 529,505

> **Methodology note:** Walk-forward V1 model artifacts used for ML scoring (out-of-sample).
> Pattern stats and regime IC stats are calibrated on full history (mild look-ahead in those components).
> Probability component ACTIVE — 2 promoted ml_rank_bucket signals (60-80 and 40-60 percentile tiers).
> ml_direction and ml_conviction signals were excluded: 100% correlated with ML component direction threshold.
> ML-tier signals use walk-forward ML predictions (same look-ahead caveat as ML component).
> Maximum alignment count = 5 (ML + Pattern + Probability + Feature IC + Regime).

---

## Key Findings

| Finding | Value |
|---------|-------|
| 5-aligned 5d HR | **58.1%** (vs v1 4-aligned: 56.5%) — new full-consensus bar |
| 5-aligned 5d avg return | **+0.56%** (vs v1 4-aligned: +0.43%) — +30% improvement |
| 5-aligned 20d avg return | **+1.60%** (vs v1 4-aligned: +1.74%) — slightly lower, smaller n |
| 80-100 score bucket | **STILL EMPTY** — structural limitation (see below) |
| 60-80 score bucket 5d HR | 54.5% vs v1 56.7% — bucket diluted (n=103,098 vs 29,534) |
| Probability standalone 5d HR | **55.3%** — beats ML top-quintile (54.8%) and pattern (54.7%) |
| Permutation test (5+ aligned) | p=0.0000 — highly significant |
| Permutation test (60+ score) | p=0.0000 — highly significant |

**Why 80-100 is still empty (structural):**
The two promoted probability signals fire for stocks in the 40th–80th ML rank percentile. These are
moderate-ranked stocks by definition. The Confluence score formula weights avg\_aligned\_strength
(`score ≈ (0.65 × avg_strength + 0.35 × alignment_ratio) × 100`), so reaching score ≥ 80
requires avg component strength ≥ 0.69. Moderate-rank stocks (where probability fires) have lower
ML strength than top-quintile stocks. Top-quintile stocks (rank ≥ 0.80) have high ML strength but
fall outside the probability trigger range. The two groups are mutually exclusive — the combination
needed for score ≥ 80 (high rank + probability fired) is structurally impossible under the current signal
design. The 80-100 bucket can only be populated if a non-rank-based probability signal (e.g., live
pattern hit rate, live component score) is promoted with 3+ years of Atlas Alpha data.

**Anomaly notes:**
- The **0-20 bucket** HR (56.5%) again exceeds the 60-80 bucket (54.5%). This is the same
  neutral-floor effect from v1: stocks with no strong directional component alignment drift up with
  market beta in a predominantly bull regime. Not a signal.
- The **5-aligned group is the true top bucket** in v2. The score bucket study is misleading in v2
  because adding the probability component shifted bucket boundaries — the 60-80 score range now
  contains ~19.5% of observations (vs 5.6% in v1). Use alignment count as the primary filter.
- **Probability component adds genuine independent information:** its standalone 55.3% HR (rank-based)
  reflects cross-sectional strength relative to peers, not absolute ML probability direction — a stock
  with ML prob=0.52 (neutral) but rank_pct=0.72 triggers probability bullish but NOT ML bullish.

---

## 1. Alignment Study

Do more aligned signals produce better forward returns?

### Hit Rates by Aligned Signal Count

| aligned_grp    |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |    52.1% |    54.0% |    54.2% |    54.5% |    53.1% |
| 2              |    51.9% |    53.2% |    54.0% |    54.9% |    55.5% |
| 3              |    52.6% |    53.8% |    54.4% |    55.7% |    57.2% |
| 4              |    52.4% |    54.1% |    55.3% |    56.9% |    59.0% |
| 5+             |    51.6% |    55.9% |    58.1% |    59.5% |    60.2% |

### Average Returns by Aligned Signal Count

| aligned_grp    |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |  +0.015% |  +0.093% |  +0.199% |  +0.346% |  +0.646% |
| 2              |  +0.045% |  +0.121% |  +0.236% |  +0.519% |  +1.003% |
| 3              |  +0.069% |  +0.204% |  +0.302% |  +0.577% |  +1.162% |
| 4              |  +0.078% |  +0.214% |  +0.351% |  +0.695% |  +1.513% |
| 5+             |  +0.046% |  +0.289% |  +0.560% |  +1.136% |  +1.595% |

### Max Drawdown and Runup (5d, 10d)

| aligned_grp    |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 1              |  -3.150% |  +3.181% |  -4.616% |  +4.630% |    24095 |
| 2              |  -2.799% |  +2.937% |  -4.002% |  +4.327% |   138298 |
| 3              |  -2.587% |  +2.837% |  -3.720% |  +4.173% |   199424 |
| 4              |  -2.678% |  +2.932% |  -3.803% |  +4.337% |   147658 |
| 5+             |  -2.580% |  +3.060% |  -3.612% |  +4.641% |    20030 |

---

## 2. Confluence Score Bucket Study

### Hit Rates by Score Bucket

| score_bucket   |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |    51.4% |    55.0% |    56.5% |    59.1% |    58.0% |
| 20-40          |    52.1% |    53.4% |    54.2% |    55.2% |    56.2% |
| 40-60          |    52.7% |    54.2% |    54.9% |    56.4% |    57.9% |
| 60-80          |    51.8% |    53.5% |    54.5% |    55.4% |    56.8% |

### Average Returns by Score Bucket

| score_bucket   |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -0.016% |  +0.057% |  +0.200% |  +0.675% |  +1.830% |
| 20-40          |  +0.049% |  +0.153% |  +0.264% |  +0.546% |  +1.137% |
| 40-60          |  +0.077% |  +0.203% |  +0.311% |  +0.612% |  +1.220% |
| 60-80          |  +0.049% |  +0.191% |  +0.358% |  +0.679% |  +1.243% |

### Max Drawdown and Runup by Score Bucket

| score_bucket   |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -3.508% |  +3.331% |  -5.035% |  +5.085% |     8923 |
| 20-40          |  -2.826% |  +2.997% |  -4.050% |  +4.395% |   158966 |
| 40-60          |  -2.641% |  +2.882% |  -3.773% |  +4.233% |   258518 |
| 60-80          |  -2.545% |  +2.829% |  -3.645% |  +4.243% |   103098 |

---

## 3. Component Comparison

> Measures how well each standalone signal filters for quality.

### Hit Rates

| signal         |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |    IC 5d |
|----------------|----------|----------|----------|----------|----------|----------|
| ML only (top quintile) |    52.5% |    54.0% |    54.8% |    55.9% |    57.4% |  +0.823% |
| ML only (all, IC) |    52.3% |    53.8% |    54.7% |    55.9% |    57.2% |  +5.450% |
| Pattern bullish |    52.3% |    53.8% |    54.7% |    55.9% |    57.2% |      n/a |
| Probability bullish |    52.6% |    54.4% |    55.3% |    56.7% |    57.6% |  +1.431% |
| Feature IC bullish |    52.4% |    54.4% |    55.4% |    57.2% |    59.0% |  +1.809% |
| Confluence 60-80 |    51.8% |    53.4% |    54.4% |    55.3% |    56.7% |  -1.043% |
| Confluence 80-100 |      n/a |      n/a |      n/a |      n/a |      n/a |  -1.043% |

### Average Returns

| signal         |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| ML only (top quintile) |  +0.046% |  +0.140% |  +0.245% |  +0.505% |  +1.118% |
| ML only (all, IC) |  +0.062% |  +0.183% |  +0.304% |  +0.605% |  +1.210% |
| Pattern bullish |  +0.062% |  +0.183% |  +0.304% |  +0.605% |  +1.210% |
| Probability bullish |  +0.075% |  +0.232% |  +0.378% |  +0.700% |  +1.336% |
| Feature IC bullish |  +0.088% |  +0.259% |  +0.429% |  +0.893% |  +1.897% |
| Confluence 60-80 |  +0.049% |  +0.187% |  +0.353% |  +0.672% |  +1.229% |
| Confluence 80-100 |      n/a |      n/a |      n/a |      n/a |      n/a |

---

## 4. Atlas Score vs Confluence Comparison

| signal         |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| Atlas Score 60+ |    38.0% |    30.1% |    38.4% |      n/a |      n/a |
| Atlas Score 80+ |      n/a |      n/a |      n/a |      n/a |      n/a |
| ML only top quintile |    38.3% |    42.6% |    61.7% |      n/a |      n/a |
| Confluence 60+ |    44.9% |    38.7% |    46.6% |      n/a |      n/a |
| Confluence 80+ |      n/a |      n/a |      n/a |      n/a |      n/a |

---

## 5. Permutation Tests

### 5+ aligned
- Observed 5d avg return: +0.560%
- Permuted mean: +0.300%, 95th pct: +0.347%
- p-value: 0.0000
- Result: **SIGNIFICANT (p < 0.05)**

### 60+ score bucket
- Observed 5d avg return: +0.353%
- Permuted mean: +0.303%, 95th pct: +0.324%
- p-value: 0.0000
- Result: **SIGNIFICANT (p < 0.05)**

---

## 6. Regime Breakdown (Confluence >= 60)

| regime_grp     |    HR 1d |    HR 3d |    HR 5d |   Avg 1d |   Avg 3d |   Avg 5d |        N |
|----------------|----------|----------|----------|----------|----------|----------|----------|
| bull_high_vol  |    51.5% |    54.4% |    55.8% |  +0.056% |  +0.193% |  +0.380% |    10765 |
| bull_low_vol   |    51.8% |    53.4% |    54.3% |  +0.046% |  +0.187% |  +0.353% |    92874 |
| range_high_vol |    53.2% |    38.0% |    41.8% |  +0.096% |  -0.549% |  -0.746% |       79 |
| range_low_vol  |    59.9% |    52.3% |    51.9% |  +0.268% |  +0.073% |  +0.110% |      574 |

---

## 7. Yearly Breakdown (Confluence >= 60)

| year           |    HR 1d |    HR 3d |   Avg 1d |   Avg 3d |        N |
|----------------|----------|----------|----------|----------|----------|
| 2015           |    44.4% |    43.1% |  -0.140% |  -0.276% |     4832 |
| 2016           |    50.5% |    50.2% |  +0.030% |  +0.122% |     4142 |
| 2017           |    53.0% |    56.9% |  +0.065% |  +0.270% |     7854 |
| 2018           |    50.2% |    51.9% |  -0.084% |  -0.114% |     4893 |
| 2019           |    53.8% |    56.6% |  +0.087% |  +0.286% |     6225 |
| 2020           |    52.5% |    57.0% |  +0.071% |  +0.324% |     9864 |
| 2021           |    52.3% |    55.0% |  +0.047% |  +0.256% |    11863 |
| 2022           |    48.7% |    41.8% |  -0.147% |  -0.492% |     1461 |
| 2023           |    53.0% |    53.6% |  +0.092% |  +0.217% |    12491 |
| 2024           |    52.4% |    53.3% |  +0.063% |  +0.174% |    12131 |
| 2025           |    51.4% |    52.0% |  +0.047% |  +0.129% |    16493 |
| 2026           |    52.1% |    55.4% |  +0.149% |  +0.525% |    12043 |

---

## 8. V1 vs V2 Comparison

### Alignment Study (5d)

| Group | v1 HR 5d | v1 Avg 5d | v1 N | v2 HR 5d | v2 Avg 5d | v2 N |
|-------|----------|-----------|------|----------|-----------|------|
| 1-aligned | 55.1% | +0.28% | 38,925 | 54.2% | +0.20% | 24,095 |
| 2-aligned | 54.0% | +0.28% | 197,300 | 54.0% | +0.24% | 138,298 |
| 3-aligned | 54.7% | +0.30% | 238,701 | 54.4% | +0.30% | 199,424 |
| 4-aligned | **56.5%** | **+0.43%** | 54,579 | 55.3% | +0.35% | 147,658 |
| **5+ aligned** | n/a | n/a | n/a | **58.1%** | **+0.56%** | 20,030 |

> Note: v1 4-aligned = 100% consensus (4/4 components). v2 4-aligned = 80% consensus (4/5 components).
> The correct like-for-like comparison is v1 4-aligned vs v2 **5-aligned** (both 100% consensus).
> On that basis: HR improved 56.5% → 58.1% (+1.6pp), avg return improved +0.43% → +0.56% (+30%).

### Score Bucket Study (5d)

| Bucket | v1 HR 5d | v1 Avg 5d | v1 N | v2 HR 5d | v2 Avg 5d | v2 N | Change |
|--------|----------|-----------|------|----------|-----------|------|--------|
| 0-20 | 57.4% | +0.38% | 14,752 | 56.5% | +0.20% | 8,923 | -0.9pp HR |
| 20-40 | 54.9% | +0.34% | 267,670 | 54.2% | +0.26% | 158,966 | -0.7pp HR |
| 40-60 | 53.9% | +0.24% | 217,549 | 54.9% | +0.31% | 258,518 | +1.0pp HR |
| 60-80 | **56.7%** | **+0.47%** | **29,534** | 54.5% | +0.36% | **103,098** | **-2.2pp HR** |
| 80-100 | EMPTY | — | — | EMPTY | — | — | no change |

> The 60-80 bucket grew 3.5× in size (29K → 103K) while HR fell -2.2pp. This is not signal degradation
> — it is **bucket boundary dilution**: the probability component pushed more observations into 60-80
> (any stock reaching 4+ aligned with probability can now reach score 60+). The 60-80 score range in v2
> covers 19.5% of all observations vs 5.6% in v1, making it a weaker concentration filter.

### Component Standalone Performance (unchanged v1 → v2)

| Component | HR 5d | Avg 5d |
|-----------|-------|--------|
| ML top quintile | 54.8% | +0.25% |
| ML all (IC) | 54.7% | +0.30% |
| Pattern bullish | 54.7% | +0.30% |
| **Probability bullish (NEW)** | **55.3%** | **+0.38%** |
| Feature IC bullish | 55.4% | +0.43% |

---

## 9. Promotion Criteria Assessment

| Criterion | v1 | v2 | Verdict |
|-----------|----|----|---------|
| Top bucket quality improves (80-100 populated) | ❌ | ❌ | FAIL |
| Full-consensus group HR improves | 56.5% (4-aligned) | **58.1%** (5-aligned) | ✅ PASS |
| Full-consensus group expectancy improves | +0.43% | **+0.56%** | ✅ PASS |
| Score bucket 60-80 HR improves | 56.7% | 54.5% (-2.2pp) | ❌ FAIL (dilution) |
| Confluence beats ML top-quintile (5d) | YES (56.7% vs 54.8%) | NO (54.5% vs 54.8%) | ❌ REGRESSED |
| Monotonic score → hit rate | NO | NO | FAIL |
| Permutation p < 0.05 (alignment) | YES | YES | ✅ PASS |
| Permutation p < 0.05 (score) | YES | YES | ✅ PASS |
| Robustness not reduced | — | p=0.0000 | ✅ PASS |

## 10. Recommendation

**DO NOT PROMOTE v2 as default engine. Keep v1 as baseline. Run v2 in parallel (experimental).**

**Rationale:**

The probability component adds genuine independent information (probability standalone HR=55.3%,
beats ML and pattern) and the 5-aligned group is meaningfully better than v1's 4-aligned
(58.1% HR, +0.56% avg return). However, two promotion criteria explicitly fail:

1. **80-100 bucket still empty.** This was the primary test condition. It is structurally unreachable
   with ml_rank_bucket signals alone — the geometry of rank-based probability vs. score formula
   strength requirements creates a fundamental incompatibility.

2. **Score bucket 60-80 quality regressed.** The bucket went from n=29,534 (elite, concentrated) to
   n=103,098 (broad, diluted). Confluence v2 no longer outperforms ML top-quintile in the 60-80
   score range (54.5% vs 54.8%). This is the core operational filter for signal selection.

**Path to v2 promotion:**

- Wait for Atlas Alpha to accumulate 3+ years of live data (target: mid-2029)
- Re-run `run_alpha_calibration.py` on live `signal_snapshots` data — this will calibrate
  real direction, pattern, and component-score signals (not ML-derived proxies)
- Live pattern and component signals are NOT correlated with the ML component (they come from
  independent sources), so a live probability signal can independently endorse top-quintile stocks
  — enabling 5-component consensus for high-rank stocks and potentially populating the 80-100 bucket
- Score formula may also need recalibration for 5 components (threshold scaling)

**Current recommendation for live trading:** Use alignment count ≥ 4 (v1 basis) or alignment count = 5
(v2 experimental) as the primary signal filter. Do NOT rely on score bucket boundaries in v2 — they
have shifted. Continue producing v2 backtest reports as live data accumulates.

> Previously generated by: `scripts/run_confluence_backtest.py --out reports/CONFLUENCE_V2_REPORT.md`

---

## Appendix: Key Caveats

1. **Probability component — ML-rank-bucket signals**: 2 signals promoted from backtest-history calibration: `ml_rank_bucket/60-80` (HR=55.4%, n=121K) and `ml_rank_bucket/40-60` (HR=55.3%, n=95K). `ml_direction/bullish` and `ml_conviction/moderate` were excluded — 100% correlated with the ML component's prob≥0.55 threshold. ml_rank_bucket provides partial independence (rank fires for relative strength regardless of absolute prob). Calibrated on 2015-2026 history with walk-forward ML predictions; look-ahead present only in calibration stats computation (not in ML scoring itself).
2. **Pattern stats look-ahead**: conditional_pattern_results uses full-history aggregate stats.
   In a strict out-of-sample study, these would be calibrated walk-forward.
3. **Feature IC look-ahead**: feature_regime_performance uses full-history IC computation.
4. **Atlas Score comparison limited**: Only a few days of alpha_signal_snapshots overlap available.
5. **ML is out-of-sample**: Walk-forward model artifacts ensure no ML look-ahead bias.
6. **Max drawdown uses intraday low**: Slightly more pessimistic than close-to-close.