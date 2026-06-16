# Trade Reconstruction Report

**Generated:** 2026-06-15 20:06  
**Source:** `prediction_outcomes` + `raw_bars` (5d hold, directionally adjusted)  
**Status:** ANALYSIS ONLY — no trades executed, no signals altered.

---

## Summary

| Metric | Value |
|---|---|
| Total reconstructed trades | 847,333 |
| Date range | 2015-01-02 → 2026-06-05 |
| Unique tickers | 1,283 |
| Long trades | 821,235 (97%) |
| Short trades | 26,098 (3%) |
| Win rate (5d) | **52.0%** |
| Expectancy (5d) | **+0.396%** |
| Profit factor (5d) | **1.204** |
| Avg winner | +4.500% |
| Avg loser | -4.126% |
| Avg MFE | 12.877% |
| Avg MAE | 2.819% |
| Stops triggered | 103,412 (12.2%) |
| T1 reached (1R) | 682,482 (80.5%) |
| T2 reached (2R) | 282,274 (33.3%) |
| T3 reached (3R) | 165,328 (19.5%) |
| Signal flip exits | 22,443 (2.6%) |

---

## Hold Period Comparison

| Hold Period | N | Win Rate | Expectancy | Profit Factor |
|---|---|---|---|---|
| 5d (base) | 847,333 | 52.0% | +0.396% | 1.204 |
| 10d | 839,707 | 52.9% | +0.722% | 1.266 |
| 20d | 829,652 | 53.8% | +1.306% | 1.348 |

---

## By Quality Tier

| Tier | N | Win Rate | Expectancy |
|---|---|---|---|
| Tier 1 | 59,163 | 50.7% | +0.09% |
| Tier 2 | 44,005 | 51.1% | +0.20% |
| Tier 3 | 83,162 | 48.0% | +0.40% |
| Tier 4 | 158,811 | 47.2% | +0.86% |

## By Conviction Level

| Conviction | N | Win Rate | Expectancy |
|---|---|---|---|
| VERY_HIGH | 192,007 | 54.2% | +0.35% |
| HIGH | 304,434 | 53.9% | +0.77% |
| LOW | 46,774 | 48.6% | -0.14% |

## By Sector Regime

| Regime | N | Win Rate | Expectancy |
|---|---|---|---|
| Bull | 468,777 | 51.6% | +0.20% |
| Bear | 72,795 | 54.0% | +0.51% |
| Range | 305,761 | 52.1% | +0.66% |

---

## Key Findings

1. **Expectancy**: +0.396% per trade — positive edge exists
2. **Profit factor 1.204**: above 1.0 — system earns more on winners than it loses on losers
3. **MFE/MAE ratio**: 4.57x on average — trades move 12.88% favorably vs 2.82% adversely
4. **Stop rate 12.2%**: ATR-based stops (1.5R) triggered on 103,412 trades
5. **T1 hit rate 80.5%**: 1.0R targets reached on 682,482 trades — solid target reach rate
6. **Signal flips**: 22,443 trades had direction reverse within next prediction cycle

---

*Run `python scripts/analyze_expectancy.py` for detailed context slicing, exit study, and discovery questions.*