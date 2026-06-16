# Exit Study Report

**Generated:** 2026-06-15 20:21  
**Status:** ANALYSIS ONLY. Simulated exits only. No trades executed.

---

## Exit Strategy Comparison

**Parameters:**
- ATR Stop: 1.5× ATR (risk-per-trade R-unit)
- T1 = +1R, T2 = +2R, T3 = +3R
- Signal flip = next prediction has opposing direction

| Exit Strategy | N | Win Rate | Expectancy | Profit Factor | Max Drawdown |
|---|---|---|---|---|---|
| 5d Hold | 847,333 | 52.0% | +0.396% | 1.204 | -89144.10% |
| 10d Hold | 839,707 | 52.9% | +0.722% | 1.266 | -162715.24% |
| 20d Hold | 829,652 | 53.8% | +1.306% | 1.348 | -260649.47% |
| ATR Stop (1.5R) + 5d | 847,333 | 50.8% | +0.409% | 1.219 | -79079.60% |
| 5d Hold (signal-flipped) | 22,443 | 54.1% | +1.085% | 1.526 | -2631.01% |
| 5d Hold (no flip) | 824,890 | 51.9% | +0.377% | 1.194 | -95535.84% |
| Exit at T1 (1R) when hit | 847,333 | 82.5% | +8.160% | 8.727 | -7471.41% |
| Exit at T2 (2R) when hit | 847,333 | 60.8% | +2.561% | 2.565 | -28786.99% |
| Exit at T3 (3R) when hit | 847,333 | 56.7% | +2.116% | 2.197 | -35698.12% |

---

## Recommendation

- **Best expectancy**: Exit at T1 (1R) when hit (+8.160%)
- **Best profit factor**: Exit at T1 (1R) when hit (PF=8.727)

---

## Expectancy by Regime and Hold Period

| Exit | 5d Exp | 10d Exp | 20d Exp |
|---|---|---|---|
| Bull | +0.204% | +0.433% | +0.926% |
| Bear | +0.509% | +1.062% | +2.382% |
| Range | +0.663% | +1.075% | +1.610% |

---

## Key Takeaways

1. **Hold period matters per regime**: Bull markets often reward patience (20d > 5d), bear markets often benefit from faster exits
2. **ATR stops protect capital** on adverse excursions but may cut winners short in trending markets
3. **Target ladder (T1/T2/T3)** allows partial profit-taking while running winners — most effective for high-conviction trades
4. **Signal flip exits** deserve investigation: if flipped trades significantly underperform, the model is reversing correctly and early exit is valuable
5. **Combine best exit with best context**: apply the optimal exit strategy specifically within the top-performing signal combinations

*Run `python scripts/reconstruct_trades.py` first to refresh trade data before this study.*