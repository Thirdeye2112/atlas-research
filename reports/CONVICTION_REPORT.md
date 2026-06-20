# Atlas Conviction Layer Backtest Report
**Date generated:** 2026-06-19
**Backtest period:** 2015-01-01 to 2026-06-19
**Total observations:** 884,794

> **Methodology:** Walk-forward V1 ML artifacts (out-of-sample). Conviction score is a parallel
> output — it does NOT change confluence score, weights, or component logic.
> Probability component: ACTIVE — 2 promoted ml_rank_bucket signals.
> Maximum alignment count: 5 (ML + Pattern + Probability + Feature IC + Regime).

---

## Key Findings

| Finding | Value |
|---------|-------|
| VERY_HIGH conviction 5d HR | 54.2% (n=156,439) |
| VERY_HIGH conviction 5d avg return | +0.305% |
| Score 60-80 bucket 5d HR | 53.3% (n=119,222) |
| VERY_HIGH beats Score 60-80 (HR) | YES |
| VERY_HIGH beats Score 60-80 (avg return) | YES |
| Conviction spread (VERY_HIGH - LOW) 5d HR | 4.2% |
| Score spread (60-80 - 0-20) 5d HR | 3.3% |
| Conviction levels monotone (LOW<MOD<HIGH<VH) | YES |
| Permutation: VERY_HIGH conviction significant | NO |
| Permutation: Score >= 60 significant | NO |

---

## 1. Alignment Study (1–5 Aligned)

How many components agree → forward return gradient.

### Hit Rates

| aligned_grp    |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |    48.4% |    49.3% |    49.2% |    49.7% |    50.2% |
| 2              |    49.1% |    50.5% |    51.0% |    51.4% |    52.4% |
| 3              |    50.7% |    52.4% |    53.2% |    54.7% |    55.0% |
| 4              |    51.6% |    53.3% |    54.1% |    55.8% |    57.7% |
| 5+             |    51.5% |    53.4% |    54.4% |    56.3% |    58.9% |

### Average Returns

| aligned_grp    |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |  +0.093% |  +0.175% |  +0.297% |  +0.554% |  +1.107% |
| 2              |  +0.108% |  +0.263% |  +0.399% |  +0.696% |  +1.344% |
| 3              |  +0.111% |  +0.333% |  +0.567% |  +1.017% |  +1.621% |
| 4              |  +0.077% |  +0.199% |  +0.306% |  +0.679% |  +1.438% |
| 5+             |  +0.056% |  +0.177% |  +0.296% |  +0.670% |  +1.461% |

### Max Drawdown and Runup

| aligned_grp    |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 1              |  -4.879% |  +6.125% |  -6.922% |  +9.521% |    64841 |
| 2              |  -4.270% |  +5.371% |  -6.091% |  +8.053% |   336219 |
| 3              |  -3.596% |  +4.488% |  -5.039% |  +6.699% |   327295 |
| 4              |  -2.974% |  +3.325% |  -4.191% |  +4.941% |   130909 |
| 5+             |  -2.553% |  +2.825% |  -3.643% |  +4.254% |    25530 |

---

## 2. Score Bucket Study (Baseline)

### Hit Rates

| score_bucket   |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |    46.4% |    49.1% |    50.0% |    51.8% |    52.6% |
| 20-40          |    49.6% |    51.1% |    51.8% |    52.7% |    53.6% |
| 40-60          |    50.2% |    51.8% |    52.4% |    53.5% |    54.3% |
| 60-80          |    51.4% |    52.7% |    53.3% |    54.2% |    55.3% |

### Average Returns

| score_bucket   |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  +0.101% |  +0.285% |  +0.508% |  +1.346% |  +2.620% |
| 20-40          |  +0.128% |  +0.292% |  +0.475% |  +0.837% |  +1.515% |
| 40-60          |  +0.100% |  +0.289% |  +0.462% |  +0.825% |  +1.487% |
| 60-80          |  +0.051% |  +0.141% |  +0.227% |  +0.489% |  +0.850% |

### Max Drawdown and Runup

| score_bucket   |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -4.685% |  +6.201% |  -6.547% | +10.293% |    24674 |
| 20-40          |  -4.109% |  +5.307% |  -5.820% |  +7.999% |   271065 |
| 40-60          |  -3.768% |  +4.611% |  -5.348% |  +6.871% |   469833 |
| 60-80          |  -3.230% |  +3.548% |  -4.522% |  +5.244% |   119222 |

---

## 3. Conviction Level Study

> Conviction formula: base(alignment_count) + ML_quality_bonus + prob_endorsement
> + IC_endorsement, scaled by regime_multiplier.
> VERY_HIGH ≥ 68 | HIGH ≥ 51 | MODERATE ≥ 34 | LOW < 34

### Hit Rates by Conviction Level

| conviction_level |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| LOW            |    48.8% |    49.9% |    49.9% |    50.8% |    51.4% |
| MODERATE       |    49.0% |    50.4% |    50.9% |    51.2% |    52.2% |
| HIGH           |    50.7% |    52.4% |    53.2% |    54.7% |    55.0% |
| VERY_HIGH      |    51.6% |    53.3% |    54.2% |    55.9% |    57.9% |

### Average Returns by Conviction Level

| conviction_level |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| LOW            |  +0.105% |  +0.205% |  +0.331% |  +0.678% |  +1.287% |
| MODERATE       |  +0.106% |  +0.258% |  +0.394% |  +0.671% |  +1.308% |
| HIGH           |  +0.111% |  +0.333% |  +0.567% |  +1.017% |  +1.622% |
| VERY_HIGH      |  +0.074% |  +0.196% |  +0.305% |  +0.677% |  +1.442% |

### Max Drawdown and Runup by Conviction Level

| conviction_level |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| LOW            |  -4.770% |  +5.969% |  -6.759% |  +9.269% |    71646 |
| MODERATE       |  -4.281% |  +5.390% |  -6.110% |  +8.078% |   329445 |
| HIGH           |  -3.596% |  +4.488% |  -5.039% |  +6.699% |   327264 |
| VERY_HIGH      |  -2.903% |  +3.242% |  -4.099% |  +4.825% |   156439 |

---

## 4. Conviction vs Score Bucket — Head-to-Head

> Direct comparison at same epoch. Coverage (N) differs by design;
> conviction levels are broader than score buckets.

### 5-Day Hit Rate and Avg Return

| Filter | HR 1d | HR 3d | HR 5d | HR 10d | HR 20d | Avg 5d | N |
|--------|-------|-------|-------|--------|--------|--------|---|
| Conviction LOW                 |   48.8% |   49.9% |   49.9% |    50.8% |    51.4% |  +0.331% |    71,646 |
| Conviction MODERATE            |   49.0% |   50.4% |   50.9% |    51.2% |    52.2% |  +0.394% |   329,445 |
| Conviction HIGH                |   50.7% |   52.4% |   53.2% |    54.7% |    55.0% |  +0.567% |   327,264 |
| Conviction VERY_HIGH           |   51.6% |   53.3% |   54.2% |    55.9% |    57.9% |  +0.305% |   156,439 |
| Score 0-20                     |   46.4% |   49.1% |   50.0% |    51.8% |    52.6% |  +0.508% |    24,674 |
| Score 20-40                    |   49.6% |   51.1% |   51.8% |    52.7% |    53.6% |  +0.475% |   271,065 |
| Score 40-60                    |   50.2% |   51.8% |   52.4% |    53.5% |    54.3% |  +0.462% |   469,936 |
| Score 60-80                    |   51.4% |   52.7% |   53.4% |    54.1% |    55.0% |  +0.231% |   132,962 |
| Score 80-100                   |     n/a |     n/a |     n/a |      n/a |      n/a |      n/a |         0 |

---

## 5. Evidence Quality Breakdown (Within VERY_HIGH)

> Isolates which evidence configuration within VERY_HIGH produces the best outcomes.
> Tests: alignment depth (4 vs 5), regime support, and ML confidence tier.

### Hit Rates

| group                                      |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|--------------------------------------------|----------|----------|----------|----------|----------|
| VERY_HIGH | 4-aligned                      |    51.6% |    53.3% |    54.1% |    55.8% |    57.7% |
| VERY_HIGH | 5-aligned                      |    51.5% |    53.4% |    54.4% |    56.3% |    58.9% |
| VERY_HIGH | regime agrees                  |    51.3% |    52.7% |    53.3% |    54.7% |    56.6% |
| VERY_HIGH | regime neutral                 |    55.8% |    58.4% |    61.8% |    68.8% |    68.1% |
| VERY_HIGH | regime conflicts               |    52.5% |    56.8% |    58.9% |    61.4% |    65.2% |
| VERY_HIGH | strong ML (prob>0.65)          |    55.0% |    58.2% |    59.5% |    61.2% |    61.5% |
| VERY_HIGH | moderate ML (0.55-0.65)        |    51.7% |    53.4% |    54.4% |    56.6% |    58.5% |

### Average Returns

| group                                      |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|--------------------------------------------|----------|----------|----------|----------|----------|
| VERY_HIGH | 4-aligned                      |  +0.077% |  +0.199% |  +0.306% |  +0.679% |  +1.438% |
| VERY_HIGH | 5-aligned                      |  +0.056% |  +0.177% |  +0.296% |  +0.670% |  +1.461% |
| VERY_HIGH | regime agrees                  |  +0.044% |  +0.131% |  +0.202% |  +0.493% |  +1.069% |
| VERY_HIGH | regime neutral                 |  +0.405% |  +0.840% |  +1.311% |  +2.751% |  +3.825% |
| VERY_HIGH | regime conflicts               |  +0.207% |  +0.515% |  +0.821% |  +1.483% |  +3.784% |
| VERY_HIGH | strong ML (prob>0.65)          |  +0.167% |  +0.490% |  +0.721% |  +1.261% |  +2.092% |
| VERY_HIGH | moderate ML (0.55-0.65)        |  +0.075% |  +0.198% |  +0.331% |  +0.734% |  +1.587% |

---

## 6. Permutation Tests

> Null hypothesis: randomly shuffled signal values produce the same top-group returns.
> A significant result (p < 0.05) confirms the grouping is not due to chance.

### VERY_HIGH conviction (>= 68) (threshold=68.0)
- Observations in top group: 156,439
- Observed 5d avg return: +0.305%
- Permuted mean: +0.436%, 95th pct: +0.530%
- p-value: 1.0000
- Result: NOT significant

### 5+ aligned (threshold=5)
- Observations in top group: 25,530
- Observed 5d avg return: +0.296%
- Permuted mean: +0.446%, 95th pct: +0.779%
- p-value: 0.8580
- Result: NOT significant

### Score >= 60 (threshold=60)
- Observations in top group: 132,962
- Observed 5d avg return: +0.231%
- Permuted mean: +0.436%, 95th pct: +0.540%
- p-value: 1.0000
- Result: NOT significant

---

## 7. Regime Breakdown (HIGH + VERY_HIGH Conviction)

| regime_grp                     |    HR 1d |    HR 3d |    HR 5d |   Avg 1d |   Avg 3d |   Avg 5d |        N |
|--------------------------------|----------|----------|----------|----------|----------|----------|----------|
| bear_high_vol                  |    53.2% |    55.5% |    57.1% |  +0.224% |  +0.664% |  +0.888% |    13361 |
| bear_low_vol                   |    53.5% |    57.6% |    59.6% |  +0.217% |  +0.645% |  +1.200% |    32725 |
| bull_high_vol                  |    49.0% |    50.3% |    51.3% |  +0.027% |  +0.161% |  +0.236% |    40722 |
| bull_low_vol                   |    50.4% |    51.5% |    52.1% |  +0.038% |  +0.113% |  +0.188% |   319290 |
| range_high_vol                 |    55.2% |    61.0% |    63.4% |  +0.348% |  +1.149% |  +1.955% |    11760 |
| range_low_vol                  |    52.7% |    55.0% |    56.3% |  +0.298% |  +0.778% |  +1.292% |    65845 |

---

## 8. Year-by-Year Breakdown (HIGH + VERY_HIGH Conviction)

| year                           |    HR 1d |    HR 3d |   Avg 1d |   Avg 3d |        N |
|--------------------------------|----------|----------|----------|----------|----------|
| 2015                           |    49.3% |    50.4% |  +0.004% |  +0.040% |    30924 |
| 2016                           |    52.8% |    54.2% |  +0.079% |  +0.241% |    25447 |
| 2017                           |    53.6% |    56.5% |  +0.085% |  +0.262% |    26168 |
| 2018                           |    52.0% |    52.4% |  -0.006% |  -0.027% |    32080 |
| 2019                           |    55.2% |    57.8% |  +0.165% |  +0.492% |    33839 |
| 2020                           |    52.1% |    54.3% |  +0.118% |  +0.311% |    38503 |
| 2021                           |    53.3% |    55.8% |  +0.108% |  +0.328% |    41274 |
| 2022                           |    49.7% |    51.4% |  +0.031% |  +0.132% |    27373 |
| 2023                           |    52.6% |    53.6% |  +0.101% |  +0.258% |    26572 |
| 2024                           |    52.1% |    52.8% |  +0.041% |  +0.128% |    37310 |
| 2025                           |    48.5% |    49.8% |  +0.154% |  +0.441% |    81222 |
| 2026                           |    48.3% |    50.2% |  +0.143% |  +0.415% |    82991 |

---

## 9. Verdict: Score-Centric vs Conviction-Centric UI

| Criterion | Result |
|-----------|--------|
| VERY_HIGH conviction HR 5d beats Score 60-80 HR 5d | YES |
| VERY_HIGH conviction avg return beats Score 60-80 avg | YES |
| Conviction levels monotone (LOW<MOD<HIGH<VH) | YES |
| Conviction VERY_HIGH permutation p<0.05 | NO |
| Score >= 60 permutation p<0.05 | NO |
| Conviction decile spread > Score decile spread | YES |

**PARTIAL: Conviction levels are competitive with score buckets. Recommend parallel display.**

Conviction levels meet 4/6 superiority criteria. Neither approach
clearly dominates. Recommendation: display BOTH in the UI — show conviction level as the
primary label with score bucket as secondary context. Monitor live data for 60+ days to
determine if conviction superiority becomes consistent.

Current status:
- VERY_HIGH conviction HR 5d: 54.2% (n=156,439)
- Score 60-80 HR 5d: 53.3% (n=119,222)

---

## 10. Per-Ticker Evidence Summary (Schema)

Each scored ticker now outputs the following conviction fields:

```json
{
  "ticker": "AAPL",
  "conviction_score": 84.2,
  "conviction_level": "VERY_HIGH",
  "supporting_signals": [
    {"name": "ml",         "signal": "bullish", "strength": 0.72, "note": "prob=0.68, rank_pct=0.88"},
    {"name": "pattern",    "signal": "bullish", "strength": 0.45, "note": "strength=0.45"},
    {"name": "feature_ic", "signal": "bullish", "strength": 0.68, "note": "74% of regime IC features agree"},
    {"name": "regime",     "signal": "bullish", "strength": 0.70, "note": "bull market environment"}
  ],
  "conflicting_signals": [],
  "neutral_signals": ["probability"],
  "historical_hit_rate": 0.581,
  "historical_expectancy": 0.0056,
  "sample_size": 20030
}
```

The `conviction_level` is the recommended primary UI label.
`supporting_signals` and `conflicting_signals` are the evidence summary.
`historical_hit_rate` and `historical_expectancy` are populated from the
conviction-level backtest calibration table above.

---

## Appendix: Conviction Score Formula

```
conviction_score = (base + ml_bonus + prob_bonus + ic_bonus)
                   × regime_multiplier × neutral_penalty

base (primary driver, 0-80):
  0-aligned → 0    | 1-aligned → 15  | 2-aligned → 30
  3-aligned → 48   | 4-aligned → 65  | 5-aligned → 80

ml_bonus (0-8):   ML distance from neutral × 8
  = (0.6 × |prob-0.5| × 2 + 0.4 × |rank_pct-0.5| × 2) × 8

prob_bonus (0-5): +5 if probability component voted same direction
ic_bonus   (0-4): +4 if feature IC component voted same direction

regime_multiplier:
  regime agrees    → 1.05
  regime neutral   → 0.90
  regime conflicts → 0.85

neutral_penalty: × 0.5 if dominant_direction == 0 (no consensus)

Level thresholds:
  VERY_HIGH ≥ 75  |  HIGH ≥ 55  |  MODERATE ≥ 30  |  LOW < 30
```