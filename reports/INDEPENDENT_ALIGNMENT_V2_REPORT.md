# Independent Alignment V2 Report

**Generated:** 2026-06-15
**Period:** 2015-01-01 to 2026-06-15
**Total rows scored:** 884,794

## 1. Overall Performance Comparison

| Model | N (directional) | Hit Rate 5d | Expectancy |
|---|---|---|---|
| Original 5-component | 847,333 | 0.520 | +0.00435 |
| V2 4-group | 797,457 | 0.516 | +0.00436 |

## 2. By Aligned Count

### Original (5-component scale)

| Aligned | N | Hit Rate | Expectancy |
|---|---|---|---|
| 1/5 | 46,774 | 0.486 | +0.00340 |
| 2/5 | 304,118 | 0.492 | +0.00162 |
| 3/5 | 304,434 | 0.539 | +0.00773 |
| 4/5 | 170,849 | 0.538 | +0.00338 |
| 5/5 | 21,158 | 0.572 | +0.00477 |

### V2 (4-group scale)

| Aligned | N | Hit Rate | Expectancy |
|---|---|---|---|
| 1/4 | 207,184 | 0.485 | +0.00392 |
| 2/4 | 250,015 | 0.514 | +0.00590 |
| 3/4 | 285,067 | 0.532 | +0.00337 |
| 4/4 | 55,191 | 0.562 | +0.00412 |

## 3. By Conviction Level

### Original conviction levels

| Level | N | Hit Rate | Expectancy |
|---|---|---|---|
| VERY_HIGH | 192,007 | 0.542 | +0.00354 |
| HIGH | 304,434 | 0.539 | +0.00773 |
| MODERATE | 304,118 | 0.492 | +0.00162 |
| LOW | 46,774 | 0.486 | +0.00340 |

### V2 conviction levels (4-group)

| Level | N | Hit Rate | Expectancy |
|---|---|---|---|
| VERY_HIGH | 60,375 | 0.564 | +0.00683 |
| HIGH | 369,471 | 0.524 | +0.00458 |
| MODERATE | 160,456 | 0.520 | +0.00384 |
| LOW | 207,155 | 0.485 | +0.00365 |

## 4. Momentum Group (Group 4) Analysis

Group 4 fires when pattern OR probability agrees with core direction.

| Momentum Group | N (directional) | Hit Rate | Expectancy |
|---|---|---|---|
| Momentum agrees (4/4 or 3/4) | 574,280 | 0.529 | +0.00456 |
| Momentum silent (3/4 or less) | 223,177 | 0.482 | +0.00384 |

## 5. Direction Mismatch Analysis (V2 vs Original)

Rows where original and V2 directions disagree: **273,439**

| Model | HR on mismatch rows |
|---|---|
| Original 5-component | 0.505 |
| V2 4-group | 0.488 |

## 6. Signal Redundancy Verification

- Pattern × Probability agreement (when both fire): **100.0%**
- Pattern × ML rank agreement (when both fire): **99.3%**
- Probability × ML rank agreement (when both fire): **99.3%**

These correlations confirm why Pattern and Probability must be grouped
as a single evidence vote rather than counted as independent signals.

## 7. OMNI/Jarvis Column Coverage After Rebuild

- `oscar_87_above_50`: 803,098/884,794 rows non-null (90.8%)
- `jarvis_quality_adjusted`: 283,747/884,794 rows non-null (32.1%)
- `quality_tier`: 364,514/884,794 rows non-null (41.2%)
- `hma_87_above`: 786,436/884,794 rows non-null (88.9%)

## 8. Recommendations

### Alignment architecture

V2 4-group model is **-0.003** HR vs original (worse). The original's momentum double-count adds real predictive value. Consider keeping momentum as a higher-weight group (0.15) rather than 0.10.

### Component weights

| Group | Components | V2 Weight | Original Weight |
|---|---|---|---|
| 1 — ML rank | LightGBM model output | 0.40 | 0.30 |
| 2 — Feature IC | Regime-specific IC | 0.30 | 0.10 |
| 3 — Regime | SPY / market context | 0.20 | 0.15 |
| 4 — Momentum | Pattern + Probability combined | 0.10 | 0.40 (split 0.20+0.20) |

### Next steps (before recalibrating thresholds)

1. Fix OMNI/OSCAR NaN bug (done in this session)
2. Rebuild parquets with `oscar_87_above_50` and `jarvis_quality_adjusted`
3. Re-run edge hierarchy — OMNI/OSCAR layer should move from 45.2% to ~54%
4. Promote bearish patterns to enable bidirectional pattern/prob votes
5. Once OMNI/Jarvis validated, add as Group 5 with weight 0.10