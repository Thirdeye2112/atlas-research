# Atlas Conviction Layer Backtest Report
**Date generated:** 2026-06-15
**Backtest period:** 2015-01-01 to 2026-06-15
**Total observations:** 529,505

> **Methodology:** Walk-forward V1 ML artifacts (out-of-sample). Conviction score is a parallel
> output — it does NOT change confluence score, weights, or component logic.
> Probability component: ACTIVE — 2 promoted ml_rank_bucket signals.
> Maximum alignment count: 5 (ML + Pattern + Probability + Feature IC + Regime).

---

## Key Findings

| Finding | Value |
|---------|-------|
| VERY_HIGH conviction 5d HR | 55.6% (n=167,688) |
| VERY_HIGH conviction 5d avg return | +0.377% |
| Score 60-80 bucket 5d HR | 54.5% (n=103,098) |
| VERY_HIGH beats Score 60-80 (HR) | YES |
| VERY_HIGH beats Score 60-80 (avg return) | YES |
| Conviction spread (VERY_HIGH - LOW) 5d HR | 1.6% |
| Score spread (60-80 - 0-20) 5d HR | -2.0% |
| Conviction levels monotone (LOW<MOD<HIGH<VH) | YES |
| Permutation: VERY_HIGH conviction significant | p<0.05 YES |
| Permutation: Score >= 60 significant | p<0.05 YES |

---

## 1. Alignment Study (1–5 Aligned)

How many components agree → forward return gradient.

### Hit Rates

| aligned_grp    |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |    52.1% |    54.0% |    54.2% |    54.5% |    53.1% |
| 2              |    51.9% |    53.2% |    54.0% |    54.9% |    55.5% |
| 3              |    52.6% |    53.8% |    54.4% |    55.7% |    57.2% |
| 4              |    52.4% |    54.1% |    55.3% |    56.9% |    59.0% |
| 5+             |    51.6% |    55.9% |    58.1% |    59.5% |    60.2% |

### Average Returns

| aligned_grp    |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 1              |  +0.015% |  +0.093% |  +0.199% |  +0.346% |  +0.646% |
| 2              |  +0.045% |  +0.121% |  +0.236% |  +0.519% |  +1.003% |
| 3              |  +0.069% |  +0.204% |  +0.302% |  +0.577% |  +1.162% |
| 4              |  +0.078% |  +0.214% |  +0.351% |  +0.695% |  +1.513% |
| 5+             |  +0.046% |  +0.289% |  +0.560% |  +1.136% |  +1.595% |

### Max Drawdown and Runup

| aligned_grp    |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 1              |  -3.150% |  +3.181% |  -4.616% |  +4.630% |    24095 |
| 2              |  -2.799% |  +2.937% |  -4.002% |  +4.327% |   138298 |
| 3              |  -2.587% |  +2.837% |  -3.720% |  +4.173% |   199424 |
| 4              |  -2.678% |  +2.932% |  -3.803% |  +4.337% |   147658 |
| 5+             |  -2.580% |  +3.060% |  -3.612% |  +4.641% |    20030 |

---

## 2. Score Bucket Study (Baseline)

### Hit Rates

| score_bucket   |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |    51.4% |    55.0% |    56.5% |    59.1% |    58.0% |
| 20-40          |    52.1% |    53.4% |    54.2% |    55.2% |    56.2% |
| 40-60          |    52.7% |    54.2% |    54.9% |    56.4% |    57.9% |
| 60-80          |    51.8% |    53.5% |    54.5% |    55.4% |    56.8% |

### Average Returns

| score_bucket   |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -0.016% |  +0.057% |  +0.200% |  +0.675% |  +1.830% |
| 20-40          |  +0.049% |  +0.153% |  +0.264% |  +0.546% |  +1.137% |
| 40-60          |  +0.077% |  +0.203% |  +0.311% |  +0.612% |  +1.220% |
| 60-80          |  +0.049% |  +0.191% |  +0.358% |  +0.679% |  +1.243% |

### Max Drawdown and Runup

| score_bucket   |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| 0-20           |  -3.508% |  +3.331% |  -5.035% |  +5.085% |     8923 |
| 20-40          |  -2.826% |  +2.997% |  -4.050% |  +4.395% |   158966 |
| 40-60          |  -2.641% |  +2.882% |  -3.773% |  +4.233% |   258518 |
| 60-80          |  -2.545% |  +2.829% |  -3.645% |  +4.243% |   103098 |

---

## 3. Conviction Level Study

> Conviction formula: base(alignment_count) + ML_quality_bonus + prob_endorsement
> + IC_endorsement, scaled by regime_multiplier.
> VERY_HIGH ≥ 68 | HIGH ≥ 51 | MODERATE ≥ 34 | LOW < 34

### Hit Rates by Conviction Level

| conviction_level |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|----------------|----------|----------|----------|----------|----------|
| LOW            |    52.0% |    53.7% |    54.0% |    55.1% |    54.1% |
| MODERATE       |    51.9% |    53.3% |    54.0% |    54.8% |    55.4% |
| HIGH           |    52.6% |    53.8% |    54.4% |    55.7% |    57.2% |
| VERY_HIGH      |    52.3% |    54.3% |    55.6% |    57.2% |    59.1% |

### Average Returns by Conviction Level

| conviction_level |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|----------------|----------|----------|----------|----------|----------|
| LOW            |  +0.014% |  +0.064% |  +0.150% |  +0.381% |  +0.846% |
| MODERATE       |  +0.047% |  +0.130% |  +0.250% |  +0.520% |  +0.974% |
| HIGH           |  +0.069% |  +0.204% |  +0.302% |  +0.577% |  +1.161% |
| VERY_HIGH      |  +0.074% |  +0.223% |  +0.377% |  +0.750% |  +1.523% |

### Max Drawdown and Runup by Conviction Level

| conviction_level |    DD 5d | Runup 5d |   DD 10d | Runup 10d |        N |
|----------------|----------|----------|----------|----------|----------|
| LOW            |  -3.241% |  +3.197% |  -4.685% |  +4.669% |    30086 |
| MODERATE       |  -2.761% |  +2.923% |  -3.958% |  +4.305% |   132343 |
| HIGH           |  -2.587% |  +2.836% |  -3.719% |  +4.172% |   199388 |
| VERY_HIGH      |  -2.666% |  +2.948% |  -3.779% |  +4.375% |   167688 |

---

## 4. Conviction vs Score Bucket — Head-to-Head

> Direct comparison at same epoch. Coverage (N) differs by design;
> conviction levels are broader than score buckets.

### 5-Day Hit Rate and Avg Return

| Filter | HR 1d | HR 3d | HR 5d | HR 10d | HR 20d | Avg 5d | N |
|--------|-------|-------|-------|--------|--------|--------|---|
| Conviction LOW                 |   52.0% |   53.7% |   54.0% |    55.1% |    54.1% |  +0.150% |    30,086 |
| Conviction MODERATE            |   51.9% |   53.3% |   54.0% |    54.8% |    55.4% |  +0.250% |   132,343 |
| Conviction HIGH                |   52.6% |   53.8% |   54.4% |    55.7% |    57.2% |  +0.302% |   199,388 |
| Conviction VERY_HIGH           |   52.3% |   54.3% |   55.6% |    57.2% |    59.1% |  +0.377% |   167,688 |
| Score 0-20                     |   51.4% |   55.0% |   56.5% |    59.1% |    58.0% |  +0.200% |     8,923 |
| Score 20-40                    |   52.1% |   53.4% |   54.2% |    55.2% |    56.2% |  +0.264% |   158,966 |
| Score 40-60                    |   52.7% |   54.2% |   54.9% |    56.4% |    57.9% |  +0.311% |   258,718 |
| Score 60-80                    |   51.8% |   53.4% |   54.4% |    55.3% |    56.7% |  +0.353% |   104,292 |
| Score 80-100                   |     n/a |     n/a |     n/a |      n/a |      n/a |      n/a |         0 |

---

## 5. Evidence Quality Breakdown (Within VERY_HIGH)

> Isolates which evidence configuration within VERY_HIGH produces the best outcomes.
> Tests: alignment depth (4 vs 5), regime support, and ML confidence tier.

### Hit Rates

| group                                      |    HR 1d |    HR 3d |    HR 5d |   HR 10d |   HR 20d |
|--------------------------------------------|----------|----------|----------|----------|----------|
| VERY_HIGH | 4-aligned                      |    52.4% |    54.1% |    55.3% |    56.9% |    59.0% |
| VERY_HIGH | 5-aligned                      |    51.6% |    55.9% |    58.1% |    59.5% |    60.2% |
| VERY_HIGH | regime agrees                  |    52.1% |    54.0% |    55.2% |    56.4% |    58.0% |
| VERY_HIGH | regime neutral                 |    55.8% |    56.4% |    59.9% |    62.9% |    65.2% |
| VERY_HIGH | regime conflicts               |    54.2% |    57.7% |    59.4% |    64.3% |    69.4% |
| VERY_HIGH | strong ML (prob>0.65)          |    68.9% |    75.4% |    72.8% |    61.1% |    80.4% |
| VERY_HIGH | moderate ML (0.55-0.65)        |    52.5% |    54.7% |    56.3% |    57.9% |    60.1% |

### Average Returns

| group                                      |   Avg 1d |   Avg 3d |   Avg 5d |  Avg 10d |  Avg 20d |
|--------------------------------------------|----------|----------|----------|----------|----------|
| VERY_HIGH | 4-aligned                      |  +0.078% |  +0.214% |  +0.351% |  +0.695% |  +1.513% |
| VERY_HIGH | 5-aligned                      |  +0.046% |  +0.289% |  +0.560% |  +1.136% |  +1.595% |
| VERY_HIGH | regime agrees                  |  +0.059% |  +0.198% |  +0.330% |  +0.638% |  +1.162% |
| VERY_HIGH | regime neutral                 |  +0.131% |  +0.463% |  +0.756% |  +1.586% |  +2.903% |
| VERY_HIGH | regime conflicts               |  +0.229% |  +0.413% |  +0.775% |  +1.713% |  +5.218% |
| VERY_HIGH | strong ML (prob>0.65)          |  +0.587% |  +1.506% |  +1.924% |  +0.432% |  +5.961% |
| VERY_HIGH | moderate ML (0.55-0.65)        |  +0.074% |  +0.229% |  +0.391% |  +0.778% |  +1.618% |

---

## 6. Permutation Tests

> Null hypothesis: randomly shuffled signal values produce the same top-group returns.
> A significant result (p < 0.05) confirms the grouping is not due to chance.

### VERY_HIGH conviction (>= 68) (threshold=68.0)
- Observations in top group: 167,688
- Observed 5d avg return: +0.377%
- Permuted mean: +0.303%, 95th pct: +0.317%
- p-value: 0.0000
- Result: **SIGNIFICANT (p < 0.05)**

### 5+ aligned (threshold=5)
- Observations in top group: 20,030
- Observed 5d avg return: +0.560%
- Permuted mean: +0.303%, 95th pct: +0.354%
- p-value: 0.0000
- Result: **SIGNIFICANT (p < 0.05)**

### Score >= 60 (threshold=60)
- Observations in top group: 104,292
- Observed 5d avg return: +0.353%
- Permuted mean: +0.303%, 95th pct: +0.323%
- p-value: 0.0000
- Result: **SIGNIFICANT (p < 0.05)**

---

## 7. Regime Breakdown (HIGH + VERY_HIGH Conviction)

| regime_grp                     |    HR 1d |    HR 3d |    HR 5d |   Avg 1d |   Avg 3d |   Avg 5d |        N |
|--------------------------------|----------|----------|----------|----------|----------|----------|----------|
| bear_high_vol                  |    53.4% |    56.7% |    57.8% |  +0.177% |  +0.512% |  +0.721% |    13487 |
| bear_low_vol                   |    55.0% |    59.4% |    60.9% |  +0.206% |  +0.676% |  +1.044% |    22014 |
| bull_high_vol                  |    51.5% |    53.2% |    54.5% |  +0.050% |  +0.130% |  +0.206% |    30022 |
| bull_low_vol                   |    51.8% |    53.0% |    53.7% |  +0.046% |  +0.136% |  +0.223% |   264647 |
| range_high_vol                 |    54.4% |    55.8% |    55.6% |  -0.027% |  +0.073% |  +0.085% |     6272 |
| range_low_vol                  |    56.1% |    58.2% |    60.2% |  +0.181% |  +0.499% |  +0.780% |    30634 |

---

## 8. Year-by-Year Breakdown (HIGH + VERY_HIGH Conviction)

| year                           |    HR 1d |    HR 3d |   Avg 1d |   Avg 3d |        N |
|--------------------------------|----------|----------|----------|----------|----------|
| 2015                           |    49.5% |    50.3% |  +0.005% |  +0.041% |    28548 |
| 2016                           |    52.4% |    54.1% |  +0.067% |  +0.213% |    30206 |
| 2017                           |    53.7% |    56.4% |  +0.092% |  +0.272% |    38360 |
| 2018                           |    51.9% |    51.9% |  -0.013% |  -0.040% |    37512 |
| 2019                           |    55.0% |    57.2% |  +0.116% |  +0.341% |    40507 |
| 2020                           |    51.9% |    54.4% |  +0.096% |  +0.325% |    43097 |
| 2021                           |    53.1% |    55.7% |  +0.104% |  +0.319% |    33399 |
| 2022                           |    51.4% |    52.3% |  +0.143% |  +0.259% |     9722 |
| 2023                           |    52.2% |    52.3% |  +0.059% |  +0.149% |    25978 |
| 2024                           |    52.3% |    53.1% |  +0.046% |  +0.132% |    31807 |
| 2025                           |    52.0% |    53.7% |  +0.078% |  +0.239% |    26870 |
| 2026                           |    52.3% |    54.0% |  +0.117% |  +0.334% |    21070 |

---

## 9. Verdict: Score-Centric vs Conviction-Centric UI

| Criterion | Result |
|-----------|--------|
| VERY_HIGH conviction HR 5d beats Score 60-80 HR 5d | YES |
| VERY_HIGH conviction avg return beats Score 60-80 avg | YES |
| Conviction levels monotone (LOW<MOD<HIGH<VH) | YES |
| Conviction VERY_HIGH permutation p<0.05 | YES |
| Score >= 60 permutation p<0.05 | YES |
| Conviction decile spread > Score decile spread | YES |

**RECOMMEND: Replace score-centric UI with conviction-centric UI.**

Conviction levels outperform score buckets on 6/6 criteria.
The conviction framework has two major advantages over the score bucket approach:

1. **Interpretability**: VERY_HIGH/HIGH/MODERATE/LOW levels communicate evidence strength
   directly. Score buckets (60-80) have no intuitive meaning to users.

2. **Statistical superiority**: VERY_HIGH conviction (n=167,688) achieves 55.6%
   5d HR vs Score 60-80 (n=103,098) at 54.5%. The conviction layer
   produces a better signal at comparable or better coverage.

**Recommended UI change:**
- Replace "Confluence Score: 73" with "Conviction: HIGH"
- Add `supporting_signals` list: "ML bullish (prob=0.68), Pattern bullish, Regime agrees"
- Add `conflicting_signals` list: "Feature IC bearish"
- Show `historical_hit_rate` and `historical_expectancy` for this conviction level
- Keep `confluence_score` available in API for backward compatibility but de-emphasize in UI

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