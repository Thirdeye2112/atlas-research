# Atlas Edge Hierarchy Report
**Period:** 2015-01-01 → 2026-06-15  |  **Universe rows:** 884,794  |  **Directional calls:** 867,162
**Generated:** 2026-06-15

> This report quantifies the marginal predictive contribution of each Atlas subsystem.
> Hit rate = % of directional calls where price moved in the predicted direction (5d horizon).
> IC = Spearman rank correlation between signal strength and actual return.
> Ablation = what happens to hit rate if this component is removed from alignment.
> All metrics are out-of-sample (walk-forward models, no look-ahead).

---

## 1. Per-Layer Performance

| Layer | N (directional) | Hit Rate 5d | Expectancy 5d | Sharpe | IC | Coverage |
|---|---|---|---|---|---|---|
| ml_rank | 289,238 | 56.8% | +0.518% | 0.788 | 0.0068 | 32.7% |
| conviction | 496,441 | 54.0% | +0.611% | 0.343 | 0.0001 | 57.7% |
| probability | 407,841 | 52.9% | +0.672% | 0.345 | n/a | 47.3% |
| pattern | 864,965 | 52.2% | +0.436% | 0.278 | 0.0164 | 100.0% |
| confluence | 847,333 | 52.0% | +0.435% | 0.279 | 0.0160 | 98.0% |
| feature_ic | 683,413 | 50.2% | +0.460% | 0.268 | 0.0067 | 79.3% |
| regime | 549,082 | 50.1% | +0.295% | 0.322 | n/a | 64.3% |
| technical | 369,004 | 49.5% | +0.388% | 0.464 | -0.0091 | 42.8% |
| jarvis | 205,814 | 49.3% | +0.737% | 0.486 | 0.0040 | 24.3% |
| omni_oscar | 710,314 | 48.2% | +0.441% | 0.451 | -0.0018 | 82.1% |
| quality_tier | 780,120 | 47.0% | +0.435% | 0.280 | -0.0012 | 90.1% |

> **Coverage** = % of all rows where the layer produces a directional signal.

---

## 2. Ablation Testing (5d Horizon)

**Baseline (all components):** HR=52.0%, Expectancy=+0.435%, N=847,333

Ablation removes one component from alignment, re-applies the 1.15× weight rule, and measures the change.
Negative delta = removal **hurt** performance (component adds value).
Positive delta = removal **helped** performance (component subtracts value).

| Component Removed | Ablated HR | Delta HR | Ablated Exp | Delta Exp | Ablated N |
|---|---|---|---|---|---|
| ml_rank | 51.6% | -0.4% | +0.431% | -0.0% | 859,162 |
| pattern | 51.8% | -0.2% | +0.441% | +0.0% | 857,349 |
| probability | 52.0% | +0.0% | +0.432% | -0.0% | 843,864 |
| feature_ic | 51.8% | -0.2% | +0.436% | +0.0% | 882,324 |
| regime | 52.6% | +0.6% | +0.436% | +0.0% | 828,603 |

---

## 3. Ranked Contribution Table

Ranked by absolute ablation impact (how much performance changes when removed).

| Rank | Component | Delta HR | Direction | Confidence |
|---|---|---|---|---|
| 1 | regime | +0.6% | NEGATIVE (removes edge) | medium |
| 2 | ml_rank | -0.4% | POSITIVE (adds edge) | medium |
| 3 | pattern | -0.2% | NEUTRAL (no measurable impact) | medium |
| 4 | feature_ic | -0.2% | NEUTRAL (no measurable impact) | medium |
| 5 | probability | +0.0% | NEUTRAL (no measurable impact) | medium |

### All Layers Ranked by Hit Rate

| Rank | Layer | Hit Rate | IC | Notes |
|---|---|---|---|---|
| 1 | ml_rank | 56.8% | 0.0068 | ablation Δ=-0.4% |
| 2 | conviction | 54.0% | 0.0001 | ablation: N/A (not in alignment) |
| 3 | probability | 52.9% | n/a | ablation Δ=+0.0% |
| 4 | pattern | 52.2% | 0.0164 | ablation Δ=-0.2% |
| 5 | confluence | 52.0% | 0.0160 | ablation: N/A (not in alignment) |
| 6 | feature_ic | 50.2% | 0.0067 | ablation Δ=-0.2% |
| 7 | regime | 50.1% | n/a | ablation Δ=+0.6% |
| 8 | technical | 49.5% | -0.0091 | ablation: N/A (not in alignment) |
| 9 | jarvis | 49.3% | 0.0040 | ablation: N/A (not in alignment) |
| 10 | omni_oscar | 48.2% | -0.0018 | ablation: N/A (not in alignment) |
| 11 | quality_tier | 47.0% | -0.0012 | ablation: N/A (not in alignment) |

---

## 4. Best Component Combinations (both must agree)

Measures hit rate when two components independently agree on direction.

| Combo | N | Hit Rate | Expectancy |
|---|---|---|---|
| ml_rank + feature_ic | 93,902 | 57.7% | +0.733% |
| ml_rank + probability | 128,024 | 57.3% | +0.509% |
| ml_rank + pattern | 287,210 | 56.8% | +0.504% |
| ml_rank + regime | 185,710 | 55.2% | +0.287% |
| probability + feature_ic | 168,725 | 54.1% | +1.120% |
| pattern + probability | 407,841 | 52.9% | +0.672% |
| pattern + feature_ic | 351,822 | 52.6% | +0.626% |
| probability + regime | 189,073 | 52.2% | +0.251% |
| pattern + regime | 469,079 | 51.6% | +0.202% |
| feature_ic + regime | 194,583 | 51.1% | +0.257% |

### Worst Combinations (agreement is actually harmful)

| Combo | N | Hit Rate | Expectancy |
|---|---|---|---|
| feature_ic + regime | 194,583 | 51.1% | +0.257% |
| pattern + regime | 469,079 | 51.6% | +0.202% |
| probability + regime | 189,073 | 52.2% | +0.251% |
| pattern + feature_ic | 351,822 | 52.6% | +0.626% |
| pattern + probability | 407,841 | 52.9% | +0.672% |

---

## 5. Redundancy Analysis

Two components are **redundant** if their agreement rate is high (> 70%) and adding the second
component produces negligible incremental IC.

| Component Pair | Agreement Rate | Notes |
|---|---|---|
| ml_rank × pattern | 99.3% | ⚠️ high overlap |
| ml_rank × probability | 99.3% | ⚠️ high overlap |
| ml_rank × feature_ic | 45.9% |  |
| ml_rank × regime | 84.7% | ⚠️ high overlap |
| pattern × probability | 100.0% | ⚠️ high overlap |
| pattern × feature_ic | 51.7% |  |
| pattern × regime | 85.9% | ⚠️ high overlap |
| probability × feature_ic | 53.7% |  |
| probability × regime | 84.4% | ⚠️ high overlap |
| feature_ic × regime | 44.8% |  |

---

## 6. Regime Breakdown (Confluence, HIGH+ conviction)

| Regime | N | Hit Rate 5d | Avg Return 5d |
|---|---|---|---|
| bear_high_vol | 13,717 | 57.4% | +0.933% |
| bear_low_vol | 26,015 | 60.2% | +1.287% |
| bull_high_vol | 40,498 | 51.9% | +0.262% |
| bull_low_vol | 319,735 | 52.7% | +0.240% |
| range_high_vol | 17,015 | 59.6% | +2.260% |
| range_low_vol | 79,461 | 56.5% | +1.650% |

---

## 7. Yearly Stability (Confluence Direction, All Rows)

| Year | N | Hit Rate 5d | Avg Return 5d |
|---|---|---|---|
| 2015 | 43,073 | 51.7% | +0.026% |
| 2016 | 43,446 | 55.2% | +0.421% |
| 2017 | 44,072 | 58.7% | +0.462% |
| 2018 | 43,748 | 52.6% | -0.053% |
| 2019 | 45,184 | 59.3% | +0.713% |
| 2020 | 46,094 | 55.8% | +0.519% |
| 2021 | 46,582 | 56.4% | +0.519% |
| 2022 | 43,076 | 49.9% | -0.049% |
| 2023 | 46,260 | 52.8% | +0.309% |
| 2024 | 47,377 | 52.7% | +0.192% |
| 2025 | 270,894 | 49.8% | +0.560% |
| 2026 | 127,527 | 47.5% | +0.611% |

---

## 8. Recommendations by Subsystem

| # | Component | Recommendation | Rationale |
|---|---|---|---|
| 1 | ml_rank | **PROMOTE** | Strong contributor: HR=56.8%, removal drops HR by -0.4% |
| 2 | conviction | **KEEP** | Aggregation layer; removing individual components is more precise than removing this |
| 3 | pattern | **KEEP** | Neutral ablation impact but non-zero IC=0.0164 |
| 4 | confluence | **KEEP** | Aggregation layer; removing individual components is more precise than removing this |
| 5 | technical | **KEEP** | HR=49.5%, IC=-0.0091 |
| 6 | jarvis | **KEEP** | Implicit quality gate; no clean ablation path but protects from micro-cap noise |
| 7 | quality_tier | **KEEP** | Implicit quality gate; no clean ablation path but protects from micro-cap noise |
| 8 | probability | **REWORK** | No measurable ablation delta (+0.0%); may add noise |
| 9 | feature_ic | **REWORK** | No measurable ablation delta (-0.2%); may add noise |
| 10 | regime | **REWORK** | Removing this component improves HR by +0.6% |
| 11 | omni_oscar | **EXPERIMENTAL** | Regime-sensitive; test with bull/bear regime split |

---

## 9. Summary Verdict

| | |
|---|---|
| **PROMOTE** (1) | ml_rank |
| **KEEP** (6) | conviction, pattern, confluence, technical, jarvis, quality_tier |
| **REWORK** (3) | probability, feature_ic, regime |
| **EXPERIMENTAL** (1) | omni_oscar |
| **REMOVE** (0) | none |

### Key Findings

1. **regime** has the largest marginal impact on alignment quality (removal changes HR by +0.6%).
2. Worst component agreement: **feature_ic + regime** — when these two agree, HR=51.1% (n=194,583). May indicate co-linear noise.
3. Best component agreement: **ml_rank + feature_ic** — HR=57.7% (n=93,902).
4. HIGH/VERY_HIGH conviction universe: HR=54.0%, n=496,441. Conviction filter is the primary quality gate.

---

## Appendix: Methodology

- **Walk-forward models:** Each date uses only a model trained ≥7 days prior (no look-ahead).
- **Hit rate:** Fraction of directional calls (bullish or bearish, neutral excluded) where price moved in predicted direction over 5 trading days.
- **Expectancy:** Mean actual 5d return for all directional rows (not direction-signed).
- **Sharpe:** Annualised mean/std of 5d returns for directional rows × √252.
- **IC:** Spearman rank correlation between signal strength and actual 5d return.
- **Ablation:** Remove one component from the alignment weight calculation. Re-apply 1.15× threshold rule. Measure change in hit rate vs full-model baseline.
- **Combination:** Restrict to rows where both components produce the same directional signal. Measure hit rate of the joint signal.
- **Coverage:** % of all (ticker, date) rows where the layer produces a non-neutral directional signal.
