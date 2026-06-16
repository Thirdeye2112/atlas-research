# Atlas Meta-Signal Engine Report v1

**Generated:** 2026-06-15 22:06
**Status:** ANALYSIS ONLY. No live trades. No signals changed.

## Overview

Compares 6 prediction filter strategies using look-ahead-free monthly walk-forward scoring.
Training window: 60 calendar days before each test month.
Exit strategy: Break-Even After T1 (production template exit).

## Filter Definitions

- **A:** All Predictions (Baseline)
- **B:** ML Q5 Only (strength >= 0.8)
- **C:** Conviction HIGH/VERY_HIGH
- **D:** Trade Template (long+HIGH/VH+regime+conf)
- **E:** Template + Combo PROMOTED
- **F:** Template + Meta Top 20%

## Overall Backtest Results (Full Walk-Forward Period)

| Filter | N | Win Rate | Expectancy | PF | Avg Winner | Avg Loser |
|---|---|---|---|---|---|---|
| **A** All Predictions (Baseline) | 833,461 | 51.8% | +1.418% | 2.513 | +4.543% | -1.944% |
| **B** ML Q5 Only (strength >= 0.8) | 0 | 0.0% | +0.000% | 0.000 | +0.000% | +0.000% |
| **C** Conviction HIGH/VERY_HIGH | 488,300 | 53.9% | +1.536% | 3.135 | +4.183% | -1.561% |
| **D** Trade Template (long+HIGH/VH+regime+conf) | 488,300 | 53.9% | +1.536% | 3.135 | +4.183% | -1.561% |
| **E** Template + Combo PROMOTED | 153,670 | 54.0% | +1.278% | 3.066 | +3.510% | -1.345% |
| **F** Template + Meta Top 20% | 38,277 | 55.1% | +2.342% | 3.462 | +5.973% | -2.120% |

## Improvement vs Baseline (Filter A)

| Filter | Exp Delta | PF Delta | N Reduction |
|---|---|---|---|
| **B** | -1.418% | -2.513 | -100.0% (0 trades) |
| **C** | +0.118% | +0.622 | -41.4% (488,300 trades) |
| **D** | +0.118% | +0.622 | -41.4% (488,300 trades) |
| **E** | -0.140% | +0.552 | -81.6% (153,670 trades) |
| **F** | +0.924% | +0.949 | -95.4% (38,277 trades) |

## Monthly PF by Filter (Selective Months)

_Full monthly table omitted for brevity. Shows first 24 and last 12 months._

| Month | A PF | D PF | E PF | F PF | D n | E n | F n |
|---|---|---|---|---|---|---|---|
| 2015-05-01 | 3.087 | 3.598 | 5.000 | 1.345 | 2870 | 498 | 17 |
| 2015-06-01 | 1.745 | 1.501 | 1.248 | 3.451 | 2175 | 1225 | 549 |
| 2015-07-01 | 2.462 | 2.802 | 3.789 | 5.000 | 2254 | 563 | 72 |
| 2015-08-01 | 0.711 | 0.754 | 0.461 | 0.439 | 2376 | 305 | 18 |
| 2015-09-01 | 5.000 | 5.000 | 4.981 | 5.000 | 3068 | 807 | 621 |
| 2015-10-01 | 5.000 | 5.000 | 5.000 | 5.000 | 2106 | 75 | 7 |
| 2015-11-01 | 2.275 | 2.493 | 4.001 | 5.000 | 2555 | 683 | 404 |
| 2015-12-01 | 0.689 | 0.708 | 0.825 | 2.159 | 3004 | 745 | 611 |
| 2016-01-01 | 1.139 | 1.091 | 0.347 | 5.000 | 2782 | 165 | 14 |
| 2016-02-01 | 5.000 | 5.000 | 5.000 | 0.000 | 2457 | 42 | 0 |
| 2016-03-01 | 5.000 | 5.000 | 5.000 | 5.000 | 2875 | 230 | 106 |
| 2016-04-01 | 3.762 | 3.258 | 5.000 | 3.726 | 2199 | 450 | 158 |
| 2016-05-01 | 4.759 | 3.969 | 5.000 | 5.000 | 1874 | 697 | 468 |
| 2016-06-01 | 3.866 | 3.668 | 5.000 | 5.000 | 1801 | 229 | 128 |
| 2016-07-01 | 5.000 | 5.000 | 5.000 | 0.000 | 2807 | 839 | 0 |
| 2016-08-01 | 3.641 | 2.949 | 3.607 | 3.661 | 2346 | 537 | 13 |
| 2016-09-01 | 2.520 | 1.864 | 1.437 | 1.362 | 2363 | 429 | 38 |
| 2016-10-01 | 1.913 | 1.594 | 2.068 | 2.354 | 1828 | 1543 | 167 |
| 2016-11-01 | 5.000 | 5.000 | 4.610 | 2.171 | 3203 | 10 | 42 |
| 2016-12-01 | 5.000 | 5.000 | 5.000 | 5.000 | 3675 | 2212 | 11 |
| 2017-01-01 | 5.000 | 5.000 | 5.000 | 0.264 | 3291 | 1979 | 26 |
| 2017-02-01 | 5.000 | 5.000 | 5.000 | 4.294 | 2758 | 2247 | 368 |
| 2017-03-01 | 1.940 | 1.981 | 1.655 | 3.511 | 3155 | 2676 | 240 |
| 2017-04-01 | 4.168 | 4.194 | 3.150 | 2.624 | 2584 | 297 | 78 |
| 2025-07-01 | 2.480 | 2.512 | 2.216 | 1.766 | 9445 | 5634 | 952 |
| 2025-08-01 | 3.506 | 3.612 | 4.623 | 4.906 | 10813 | 1168 | 316 |
| 2025-09-01 | 3.647 | 3.796 | 1.804 | 0.431 | 10025 | 2592 | 54 |
| 2025-10-01 | 1.420 | 1.453 | 2.503 | 2.412 | 14305 | 3276 | 1476 |
| 2025-11-01 | 2.268 | 1.800 | 2.164 | 2.667 | 8567 | 503 | 222 |
| 2025-12-01 | 2.861 | 3.293 | 3.943 | 5.000 | 15546 | 1115 | 10 |
| 2026-01-01 | 2.134 | 3.264 | 5.000 | 5.000 | 15858 | 572 | 218 |
| 2026-02-01 | 1.747 | 1.681 | 1.827 | 2.219 | 10782 | 4025 | 1264 |
| 2026-03-01 | 1.543 | 3.059 | 0.872 | 0.786 | 7018 | 569 | 281 |
| 2026-04-01 | 2.976 | 3.579 | 5.000 | 5.000 | 16843 | 1346 | 679 |
| 2026-05-01 | 3.035 | 2.707 | 3.557 | 3.559 | 17742 | 9973 | 3768 |
| 2026-06-01 | 1.010 | 1.101 | 1.599 | 1.393 | 4763 | 1826 | 696 |

## Key Findings

1. **Best single filter by expectancy:** Filter F (Template + Meta Top 20%)
   - Expectancy: +2.342%  PF: 3.462  WR: 55.1%
   - Trades: 38,277 (vs baseline 833,461)

2. **Meta PROMOTED (E) vs Template (D):**
   - D: Exp=+1.536%  PF=3.135  n=488,300
   - E: Exp=+1.278%  PF=3.066  n=153,670
   - PROMOTED filter selects 31.5% of template trades

3. **Meta Top-20% (F) vs Template (D):**
   - D: Exp=+1.536%  PF=3.135
   - F: Exp=+2.342%  PF=3.462  n=38,277

## Recommendation

**DEPLOY META FILTER F (TOP 20% META SCORE)** as an additional gate.

Top-20% meta-score filter improves expectancy from +1.536% to +2.342% (+0.807%).

## Implementation Notes

- Meta scores are updated nightly by `compute_signal_combination_scores.py`
- Scores are attached to predictions via the nightly pipeline meta-tagging step
- BotLab displays current combo status and meta score per prediction
- Status tiers: PROMOTED (n>=30, PF>=1.5, WR>=50%, exp>0) | CANDIDATE (n>=15, PF>=1.2)
  | REJECTED (PF<1.0 or exp<=0) | INSUFFICIENT (n<15)

---
_Generated by backtest_meta_signal_filter.py on 2026-06-15 22:06_