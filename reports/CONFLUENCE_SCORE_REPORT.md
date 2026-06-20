# Confluence Engine v2 Backtest Report
**Date generated:** 2026-06-19
**Backtest period:** 2015-01-01 to 2026-06-19
**Total observations:** 884,794

> **Methodology note:** Walk-forward V1 model artifacts used for ML scoring (out-of-sample).
> Pattern stats and regime IC stats are calibrated on full history (mild look-ahead in those components).
> Probability component ACTIVE — 2 promoted ML-tier signals (ml_rank_bucket, ml_direction, ml_conviction).
> ML-tier signals use walk-forward ML predictions (same look-ahead caveat as ML component).
> Maximum alignment count = 5 (ML + Pattern + Probability + Feature IC + Regime).

---

## 1. Alignment Study

Do more aligned signals produce better forward returns?

### Hit Rates by Aligned Signal Count

| aligned_grp    |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |    48.4% |    49.3% |    49.2% |    49.7% |    50.2% |
| 2              |    49.1% |    50.5% |    51.0% |    51.4% |    52.4% |
| 3              |    50.7% |    52.4% |    53.2% |    54.7% |    55.0% |
| 4              |    51.6% |    53.3% |    54.1% |    55.8% |    57.7% |
| 5+             |    51.5% |    53.4% |    54.4% |    56.3% |    58.9% |

### Average Returns by Aligned Signal Count

| aligned_grp    |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |  +0.093% |  +0.175% |  +0.297% |  +0.554% |  +1.107% |
| 2              |  +0.108% |  +0.263% |  +0.399% |  +0.696% |  +1.344% |
| 3              |  +0.111% |  +0.333% |  +0.567% |  +1.017% |  +1.621% |
| 4              |  +0.077% |  +0.199% |  +0.306% |  +0.679% |  +1.438% |
| 5+             |  +0.056% |  +0.177% |  +0.296% |  +0.670% |  +1.461% |

### Max Drawdown and Runup (5d, 10d)

| aligned_grp    |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 1              |  -4.879% |  +6.125% |  -6.922% |  +9.521% |    64841 |
| 2              |  -4.270% |  +5.371% |  -6.091% |  +8.053% |   336219 |
| 3              |  -3.596% |  +4.488% |  -5.039% |  +6.699% |   327295 |
| 4              |  -2.974% |  +3.325% |  -4.191% |  +4.941% |   130909 |
| 5+             |  -2.553% |  +2.825% |  -3.643% |  +4.254% |    25530 |

---

## 2. Confluence Score Bucket Study

### Hit Rates by Score Bucket

| score_bucket   |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |    46.4% |    49.1% |    50.0% |    51.8% |    52.6% |
| 20-40          |    49.6% |    51.1% |    51.8% |    52.7% |    53.6% |
| 40-60          |    50.2% |    51.8% |    52.4% |    53.5% |    54.3% |
| 60-80          |    51.4% |    52.7% |    53.3% |    54.2% |    55.3% |

### Average Returns by Score Bucket

| score_bucket   |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  +0.101% |  +0.285% |  +0.508% |  +1.346% |  +2.620% |
| 20-40          |  +0.128% |  +0.292% |  +0.475% |  +0.837% |  +1.515% |
| 40-60          |  +0.100% |  +0.289% |  +0.462% |  +0.825% |  +1.487% |
| 60-80          |  +0.051% |  +0.141% |  +0.227% |  +0.489% |  +0.850% |

### Max Drawdown and Runup by Score Bucket

| score_bucket   |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -4.685% |  +6.201% |  -6.547% | +10.293% |    24674 |
| 20-40          |  -4.109% |  +5.307% |  -5.820% |  +7.999% |   271065 |
| 40-60          |  -3.768% |  +4.611% |  -5.348% |  +6.871% |   469833 |
| 60-80          |  -3.230% |  +3.548% |  -4.522% |  +5.244% |   119222 |

---

## 3. Component Comparison

> Measures how well each standalone signal filters for quality.

### Hit Rates

| signal         |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |    IC 5d |
|----------------|----------|----------|----------|----------|----------|----------|
| ML only (top quintile) |    50.4% |    51.3% |    51.9% |    52.5% |    53.4% |  -0.188% |
| ML only (all, IC) |    50.1% |    51.6% |    52.3% |    53.3% |    54.2% |  +3.805% |
| Pattern bullish |    50.1% |    51.6% |    52.3% |    53.3% |    54.2% |      n/a |
| Probability bullish |    50.6% |    52.4% |    53.2% |    54.2% |    54.7% |  +1.397% |
| Feature IC bullish |    50.1% |    51.9% |    52.6% |    54.1% |    55.0% |  +0.546% |
| Confluence 60-80 |    51.4% |    52.7% |    53.4% |    54.1% |    55.0% |  +0.957% |
| Confluence 80-100 |      n/a |      n/a |      n/a |      n/a |      n/a |  +0.957% |

### Average Returns

| signal         |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| ML only (top quintile) |  +0.098% |  +0.239% |  +0.460% |  +0.870% |  +1.512% |
| ML only (all, IC) |  +0.102% |  +0.270% |  +0.436% |  +0.799% |  +1.444% |
| Pattern bullish |  +0.102% |  +0.270% |  +0.436% |  +0.799% |  +1.444% |
| Probability bullish |  +0.124% |  +0.337% |  +0.530% |  +0.901% |  +1.421% |
| Feature IC bullish |  +0.147% |  +0.386% |  +0.627% |  +1.172% |  +2.103% |
| Confluence 60-80 |  +0.052% |  +0.143% |  +0.231% |  +0.462% |  +0.781% |
| Confluence 80-100 |      n/a |      n/a |      n/a |      n/a |      n/a |

---

## 4. Atlas Score vs Confluence Comparison

| signal         |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| Atlas Score 60+ |    41.1% |    34.1% |    46.2% |      n/a |      n/a |
| Atlas Score 80+ |      n/a |      n/a |      n/a |      n/a |      n/a |
| ML only top quintile |    54.7% |    56.0% |    72.0% |      n/a |      n/a |
| Confluence 60+ |    52.3% |    47.0% |    61.6% |      n/a |      n/a |
| Confluence 80+ |      n/a |      n/a |      n/a |      n/a |      n/a |

---

## 5. Permutation Tests

### 5+ aligned
- Observed 5d avg return: +0.296%
- Permuted mean: +0.435%, 95th pct: +0.720%
- p-value: 0.8440
- Result: NOT significant

### 60+ score bucket
- Observed 5d avg return: +0.231%
- Permuted mean: +0.443%, 95th pct: +0.553%
- p-value: 1.0000
- Result: NOT significant

---

## 6. Regime Breakdown (Confluence >= 60)

| regime_grp     |    HR 1d |    HR 3d |    HR 5d |   Avg 1d |   Avg 3d |   Avg 5d |        N |
|----------------|----------|----------|----------|----------|----------|----------|----------|
| bull_high_vol  |    50.4% |    52.2% |    52.6% |  +0.097% |  +0.381% |  +0.351% |    13233 |
| bull_low_vol   |    51.3% |    52.5% |    53.2% |  +0.032% |  +0.095% |  +0.186% |   112537 |
| range_high_vol |    58.2% |    70.0% |    72.1% |  +0.666% |  +1.910% |  +2.758% |     1292 |
| range_low_vol  |    53.5% |    53.4% |    53.7% |  +0.201% |  +0.124% |  +0.245% |     5900 |

---

## 7. Yearly Breakdown (Confluence >= 60)

| year           |    HR 1d |    HR 3d |   Avg 1d |   Avg 3d |        N |
|----------------|----------|----------|----------|----------|----------|
| 2015           |    44.8% |    44.1% |  -0.095% |  -0.308% |     5639 |
| 2016           |    52.9% |    53.7% |  +0.059% |  +0.188% |     7282 |
| 2017           |    53.5% |    56.4% |  +0.088% |  +0.272% |    10675 |
| 2018           |    53.4% |    54.3% |  +0.016% |  +0.023% |     4019 |
| 2019           |    52.8% |    55.3% |  +0.052% |  +0.210% |     9998 |
| 2020           |    53.2% |    55.5% |  +0.088% |  +0.233% |    10933 |
| 2021           |    51.9% |    54.8% |  +0.040% |  +0.227% |    13715 |
| 2022           |    46.6% |    37.4% |  -0.205% |  -0.914% |     1892 |
| 2023           |    50.9% |    51.4% |  +0.023% |  +0.053% |    12931 |
| 2024           |    52.5% |    53.2% |  +0.073% |  +0.182% |    12596 |
| 2025           |    51.2% |    52.3% |  +0.042% |  +0.141% |    24003 |
| 2026           |    49.3% |    49.9% |  +0.122% |  +0.220% |    19279 |

---

## 8. Promotion Criteria Assessment

| Criterion | Result |
|-----------|--------|
| Top score bucket (60-80) best HR | YES |
| Monotonic score -> hit rate (20-80) | YES |
| Confluence 60-80 HR 5d | 53.3% |
| ML only top quintile HR 5d | 51.9% |
| Confluence beats ML (5d) | YES |
| Permutation p < 0.05 (alignment) | NO |
| Permutation p < 0.05 (score) | NO |

## 9. Recommendation

**KEEP EXPERIMENTAL** — Some criteria met. Needs more data or signal improvement.

> Recommend running after probability component has promoted signals and Atlas Score comparison has >500 observations.

---

## Appendix: Key Caveats

1. **Probability component — ML-tier signals**: 2 signals promoted from backtest-history calibration (ml_rank_bucket, ml_direction, ml_conviction). These are derived from the same ML model — they validate tier-specific effects but share information with the ML component. Look-ahead present (calibrated on full history).
2. **Pattern stats look-ahead**: conditional_pattern_results uses full-history aggregate stats.
   In a strict out-of-sample study, these would be calibrated walk-forward.
3. **Feature IC look-ahead**: feature_regime_performance uses full-history IC computation.
4. **Atlas Score comparison limited**: Only a few days of alpha_signal_snapshots overlap available.
5. **ML is out-of-sample**: Walk-forward model artifacts ensure no ML look-ahead bias.
6. **Max drawdown uses intraday low**: Slightly more pessimistic than close-to-close.