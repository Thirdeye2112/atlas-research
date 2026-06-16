# Atlas Intraday Similarity Engine Report v1
Generated: 2026-06-16 09:08

## Summary
- IS candles: 32,353
- OOS candles: 13,866
- Best K: 100
- Baseline hit rate (no filter): 49.1%
- Baseline expectancy (no filter): +0.001%

## Q1: What K produces the best direction prediction?
| K | N (OOS) | Hit Rate | Top-Q Exp | MSE | Corr |
|---|---------|----------|-----------|-----|------|
| 25 | 13806 | 50.2% | +0.000% | 0.50974 | -0.023 |
| 50 | 13806 | 50.2% | +0.001% | 0.49471 | -0.015 |
| 100 | 13806 | 50.2% | +0.025% | 0.48600 | -0.002 |
| 200 | 13806 | 50.7% | +0.004% | 0.48109 | 0.009 |

**Best K = 100** (hit_rate=50.2%  top_q=+0.025%)

## Q2: Does gating by time + regime improve accuracy?
- Ungated: hit_rate=50.2%  top_q=+0.025%
- Gated:   hit_rate=50.2%  top_q=+0.025%
- Lift: +0.0 pp hit rate

## Q3: Which time-of-day segment has best similarity accuracy?
| Time Bucket | N | Hit Rate | Top-Q Exp |
|-------------|---|----------|-----------|
| 930_10 | 1080 | 55.7% | +0.008% |
| 10_1030 | 1039 | 50.7% | +0.097% |
| open_30m | 1080 | 50.6% | +0.011% |
| 1030_14 | 6287 | 50.4% | -0.001% |
| 15_16 | 2160 | 49.7% | -0.101% |
| 14_15 | 2160 | 46.9% | -0.082% |

## Q4: Which market regime benefits most from similarity?
| Regime | N | Hit Rate | Top-Q Exp |
|--------|---|----------|-----------|
| NaN | 4819 | 50.6% | +0.078% |
| bull | 8987 | 50.0% | -0.003% |

## Q5: Does weighting context features more improve accuracy?
- Default weights:       hit_rate=50.2%  top_q=+0.025%
- Context-heavy weights: hit_rate=49.8%  top_q=-0.001%

## Q6: What are the primary limitations?
1. **Data volume**: 60 days x 10 tickers = ~46K candles. KNN accuracy improves
   with more history -- expect improvement as data accumulates.
2. **Feature version lock**: v1 vectors are stored in DB; changing feature
   definitions requires a full rebuild (run --full).
3. **No ticker filtering**: similar candles may come from a different ticker's
   sector -- cross-ticker patterns may not generalize.
4. **Overnight gap risk**: future_return_24 spans overnight; MFE/MAE do not
   account for gap risk at session open.
5. **Regime stationarity**: regime labels from prediction_outcomes lag by 1 day.

## Q7: Is this ready to inform live trade decisions?
- Similarity engine is **analysis-only** in v1.
- It provides historical context (what happened after similar candles) but
  does NOT replace setup detection, conviction scoring, or risk management.
- Use as a supplementary signal: high-conviction setup + similarity agreement
  -> elevated confidence; divergence -> caution.

## Q8: Next Steps
- Expand universe to all 1,326 tickers to grow the memory bank
- Add ticker-sector filter to keep matches within same sector
- Test similarity as an additive feature in the daily ML model
- Auto-promote setups where similarity confirms direction