# Exit Optimization Report

**Generated:** 2026-06-15 20:49  
**Trades analyzed:** 847,333  
**Date range:** 2015-01-02 -> 2026-06-05  
**Status:** ANALYSIS ONLY. No live trades executed. No signals altered. No retraining.

## Strategy Comparison (All 847K Trades)

| Strategy | N | Win Rate | Expectancy | Profit Factor | Avg Winner | Avg Loser | MFE Capture | P10 Loss |
|---|---|---|---|---|---|---|---|---|
| Base 5d Hold | 847,333 | 51.96% | +0.396% | 1.204 | +4.500% | -4.045% | -0.192 | -5.769% |
| Base 10d Hold | 839,707 | 52.9% | +0.722% | 1.266 | +6.496% | -5.763% | -0.079 | -8.188% |
| Base 20d Hold | 829,652 | 53.8% | +1.306% | 1.348 | +9.401% | -8.120% | 0.007 | -11.367% |
| T1 Only | 847,333 | 82.42% | +8.287% | 9.944 | +11.180% | -5.271% | 0.511 | -3.487% |
| T1 + Runner | 847,333 | 82.42% | +9.182% | 10.909 | +12.265% | -5.271% | 0.605 | -3.487% |
| T1/T2/T3 Ladder | 847,333 | 77.11% | +4.407% | 5.226 | +7.067% | -4.556% | 0.268 | -3.839% |
| Break-Even After T1 | 847,333 | 51.86% | +1.411% | 2.522 | +4.507% | -1.925% | -0.028 | -3.487% |
| ATR Trailing Stop | 847,333 | 52.8% | +0.904% | 1.597 | +4.581% | -3.210% | -0.136 | -4.924% |
| 20d (HIGH/VH only) | 834,190 | 53.57% | +1.141% | 1.413 | +7.290% | -5.955% | -0.064 | -8.431% |
| Tight MAE Stop | 847,333 | 81.59% | +8.414% | 11.753 | +11.271% | -4.251% | 0.500 | -2.936% |

## Specific Test Results


### Test 1: T1 Only Exit

**Overall:** n=847,333  WR=82.42%  Exp=+8.287%  PF=9.944  AvgW=+11.180%  AvgL=-5.271%

| Sector Regime | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| bull | 468,777 | 83.56% | +9.056% | 12.548 |
| bear | 72,795 | 81.2% | +9.838% | 9.848 |
| range | 305,761 | 80.96% | +6.740% | 7.122 |

| Conviction | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| VERY_HIGH | 192,007 | 85.0% | +9.067% | 14.039 |
| HIGH | 304,434 | 85.02% | +9.938% | 14.728 |
| MODERATE | 304,118 | 79.88% | +6.848% | 6.759 |
| LOW | 46,774 | 71.39% | +3.704% | 3.489 |

| VIX Regime | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| low | 261,699 | 86.69% | +11.144% | 32.900 |
| moderate | 339,121 | 83.82% | +8.340% | 13.828 |
| high | 239,610 | 75.95% | +5.203% | 3.692 |

### Test 2: T1 Then Trail Remainder

**Overall:** n=847,333  WR=82.42%  Exp=+9.182%  PF=10.909  AvgW=+12.265%  AvgL=-5.271%

Logic: exit 50% at T1 (+1 ATR), trail remaining 50% — if T2 hit exit there, else lock T1 as floor for runner.

| Sector Regime | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| bull | 468,777 | 83.56% | +9.774% | 13.464 |
| bear | 72,795 | 81.2% | +10.875% | 10.780 |
| range | 305,761 | 80.96% | +7.871% | 8.150 |

### Test 3: T1 + Break-Even Stop

**Overall:** n=847,333  WR=51.86%  Exp=+1.411%  PF=2.522  AvgW=+4.507%  AvgL=-1.925%

Logic: once T1 hit, stop moves to entry price (0%). If 5d close is negative, assume stopped at 0%. If 5d close positive, hold to 5d close.

| Conviction | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| VERY_HIGH | 192,007 | 54.07% | +1.256% | 2.806 |
| HIGH | 304,434 | 53.8% | +1.696% | 3.344 |
| MODERATE | 304,118 | 49.08% | +1.312% | 2.104 |
| LOW | 46,774 | 48.19% | +0.825% | 1.554 |

### Test 4: Hold 20d Only for HIGH/VERY_HIGH Conviction (else 5d)

**Overall:** n=834,190  WR=53.57%  Exp=+1.141%  PF=1.413  AvgW=+7.290%  AvgL=-5.955%

HIGH/VH on 20d (n=483,298): WR=56.81%  Exp=+1.903%  PF=1.626
Other conviction on 5d (n=350,892): WR=49.11%  Exp=+0.091%  PF=1.038

### Test 5: Avoid All Shorts (Long-Only)

**Long trades (n=821,235):** WR=52.2%  Exp=+0.428%  PF=1.224  AvgW=+4.489%  AvgL=-4.006%

**Short trades (n=26,098):** WR=44.48%  Exp=-0.639%  PF=0.774  AvgW=+4.921%  AvgL=-5.093%

**Verdict:** Eliminating shorts removes 26,098 trades (3.1% of universe) with negative expectancy (-0.639%). Net portfolio expectancy improves from +0.396% -> +0.428%.

### Test 6: Avoid Unknown Sector Regime

**Known regime (n=847,333):** WR=51.96%  Exp=+0.396%  PF=1.204

**Unknown regime (n=0):** WR=0.0%  Exp=+0.000%  PF=0.000

**Verdict:** Removing unknown-regime trades eliminates 0 trades (0.0%) with sub-market expectancy.

### Test 7: Avoid LOW Conviction

**Not-LOW conviction (n=800,559):** WR=52.16%  Exp=+0.427%  PF=1.223

**LOW conviction (n=46,774):** WR=48.56%  Exp=-0.145%  PF=0.941

**Verdict:** LOW conviction trades are the only conviction bucket with negative expectancy (-0.145%). Remove them unconditionally.

## Entry Filter Impact

Cumulative effect of stacking entry filters on base 5d return.

| Filter | N Trades | N Removed | Expectancy | PF | Win Rate |
|---|---|---|---|---|---|
| All trades | 847,333 | 0 | +0.396% | 1.204 | 51.96% |
| Long-only | 821,235 | 26,098 | +0.428% | 1.224 | 52.2% |
| Known regime | 847,333 | 0 | +0.396% | 1.204 | 51.96% |
| Not-LOW conviction | 800,559 | 46,774 | +0.427% | 1.223 | 52.16% |
| HIGH/VH conviction | 496,441 | 350,892 | +0.611% | 1.375 | 53.98% |
| Optimized (long+regime+conv) | 794,851 | 52,482 | +0.437% | 1.229 | 52.25% |
| Best template (long+regime+HIGH/VH) | 496,441 | 350,892 | +0.611% | 1.375 | 53.98% |

## Combined Strategy + Filter Results

Best exit strategy applied within each entry filter.

| Filter | Strategy | N | Win Rate | Expectancy | PF | Avg Win | Avg Loss |
|---|---|---|---|---|---|---|---|
| All trades | Base 5d Hold | 847,333 | 51.96% | +0.396% | 1.204 | +4.500% | -4.045% |
| All trades | T1 Only | 847,333 | 82.42% | +8.287% | 9.944 | +11.180% | -5.271% |
| All trades | T1 + Runner | 847,333 | 82.42% | +9.182% | 10.909 | +12.265% | -5.271% |
| All trades | Break-Even After T1 | 847,333 | 51.86% | +1.411% | 2.522 | +4.507% | -1.925% |
| Long-only | Base 5d Hold | 821,235 | 52.2% | +0.428% | 1.224 | +4.489% | -4.006% |
| Long-only | T1 Only | 821,235 | 83.19% | +8.531% | 10.581 | +11.325% | -5.297% |
| Long-only | T1 + Runner | 821,235 | 83.19% | +9.435% | 11.596 | +12.411% | -5.297% |
| Long-only | Break-Even After T1 | 821,235 | 52.12% | +1.452% | 2.631 | +4.495% | -1.859% |
| Known regime | Base 5d Hold | 847,333 | 51.96% | +0.396% | 1.204 | +4.500% | -4.045% |
| Known regime | T1 Only | 847,333 | 82.42% | +8.287% | 9.944 | +11.180% | -5.271% |
| Known regime | T1 + Runner | 847,333 | 82.42% | +9.182% | 10.909 | +12.265% | -5.271% |
| Known regime | Break-Even After T1 | 847,333 | 51.86% | +1.411% | 2.522 | +4.507% | -1.925% |
| Not-LOW conviction | Base 5d Hold | 800,559 | 52.16% | +0.427% | 1.223 | +4.486% | -3.998% |
| Not-LOW conviction | T1 Only | 800,559 | 83.06% | +8.555% | 10.572 | +11.376% | -5.277% |
| Not-LOW conviction | T1 + Runner | 800,559 | 83.06% | +9.453% | 11.575 | +12.456% | -5.277% |
| Not-LOW conviction | Break-Even After T1 | 800,559 | 52.07% | +1.445% | 2.617 | +4.491% | -1.865% |
| HIGH/VH conviction | Base 5d Hold | 496,441 | 53.98% | +0.611% | 1.375 | +4.149% | -3.540% |
| HIGH/VH conviction | T1 Only | 496,441 | 85.01% | +9.601% | 14.468 | +12.132% | -4.756% |
| HIGH/VH conviction | T1 + Runner | 496,441 | 85.01% | +10.451% | 15.661 | +13.133% | -4.756% |
| HIGH/VH conviction | Break-Even After T1 | 496,441 | 53.91% | +1.526% | 3.141 | +4.153% | -1.547% |
| Optimized (long+regime+conv) | Base 5d Hold | 794,851 | 52.25% | +0.437% | 1.229 | +4.485% | -3.993% |
| Optimized (long+regime+conv) | T1 Only | 794,851 | 83.28% | +8.617% | 10.754 | +11.408% | -5.284% |
| Optimized (long+regime+conv) | T1 + Runner | 794,851 | 83.28% | +9.517% | 11.774 | +12.489% | -5.284% |
| Optimized (long+regime+conv) | Break-Even After T1 | 794,851 | 52.16% | +1.459% | 2.651 | +4.490% | -1.847% |
| Best template (long+regime+HIGH/VH) | Base 5d Hold | 496,441 | 53.98% | +0.611% | 1.375 | +4.149% | -3.540% |
| Best template (long+regime+HIGH/VH) | T1 Only | 496,441 | 85.01% | +9.601% | 14.468 | +12.132% | -4.756% |
| Best template (long+regime+HIGH/VH) | T1 + Runner | 496,441 | 85.01% | +10.451% | 15.661 | +13.133% | -4.756% |
| Best template (long+regime+HIGH/VH) | Break-Even After T1 | 496,441 | 53.91% | +1.526% | 3.141 | +4.153% | -1.547% |

## T1 Exit Performance by Context


### By Sector Regime

| Regime | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| bull | 468,777 | 83.56% | +9.056% | 12.548 |
| bear | 72,795 | 81.2% | +9.838% | 9.848 |
| range | 305,761 | 80.96% | +6.740% | 7.122 |

### By VIX Regime

| VIX | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| low | 261,699 | 86.69% | +11.144% | 32.900 |
| moderate | 339,121 | 83.82% | +8.340% | 13.828 |
| high | 239,610 | 75.95% | +5.203% | 3.692 |

### By Conviction Level

| Conviction | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| VERY_HIGH | 192,007 | 85.0% | +9.067% | 14.039 |
| HIGH | 304,434 | 85.02% | +9.938% | 14.728 |
| MODERATE | 304,118 | 79.88% | +6.848% | 6.759 |
| LOW | 46,774 | 71.39% | +3.704% | 3.489 |

### By Quality Tier

| Tier | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| Tier 1 | 59,163 | 78.35% | +1.965% | 3.083 |
| Tier 2 | 44,005 | 78.76% | +3.004% | 3.539 |
| Tier 3 | 83,162 | 75.95% | +3.383% | 3.161 |
| Tier 4 | 158,811 | 76.08% | +3.958% | 3.404 |

## Hold Period x Regime Matrix

| Exit | Bull Exp | Bear Exp | Range Exp | All Exp |
|---|---|---|---|---|
| 5d Hold | +0.204% | +0.509% | +0.663% | +0.396% |
| 10d Hold | +0.433% | +1.062% | +1.075% | +0.722% |
| 20d Hold | +0.926% | +2.382% | +1.610% | +1.306% |
| T1 Only | +9.056% | +9.838% | +6.740% | +8.287% |
| T1+Runner | +9.774% | +10.875% | +7.871% | +9.182% |

## Signal Flip Exit Analysis

A 'signal flip' occurs when the next prediction for the same ticker reverses direction. These trades can be exited early.

**Flip trades — base 5d** (n=22,443): WR=54.07%  Exp=+1.085%  PF=1.526
**No-flip trades — base 5d** (n=824,890): WR=51.91%  Exp=+0.377%  PF=1.194
**Flip trades — T1 exit** (n=22,443): WR=74.22%  Exp=+3.907%  PF=4.010
**No-flip trades — T1 exit** (n=824,890): WR=82.64%  Exp=+8.407%  PF=10.173

Signal-flip trades outperform non-flip in both 5d and T1 modes, suggesting the model reverses when a trade has already run — the flip is a useful trailing exit signal.

## Best Trade Template — Full Metrics

**Entry filters:** Long-only + Known regime + HIGH or VERY_HIGH conviction

- **Base 5d Hold** (n=496,441): WR=53.98%  Exp=+0.611%  PF=1.375  AvgW=+4.149%  AvgL=-3.540%  MFE-capture=-0.140
- **T1 Only** (n=496,441): WR=85.01%  Exp=+9.601%  PF=14.468  AvgW=+12.132%  AvgL=-4.756%  MFE-capture=0.576
- **T1 + Runner** (n=496,441): WR=85.01%  Exp=+10.451%  PF=15.661  AvgW=+13.133%  AvgL=-4.756%  MFE-capture=0.671
- **Break-Even After T1** (n=496,441): WR=53.91%  Exp=+1.526%  PF=3.141  AvgW=+4.153%  AvgL=-1.547%  MFE-capture=0.012
- **ATR Trailing Stop** (n=496,441): WR=54.69%  Exp=+1.083%  PF=1.886  AvgW=+4.214%  AvgL=-2.698%  MFE-capture=-0.088
- **T1/T2/T3 Ladder** (n=496,441): WR=80.18%  Exp=+4.884%  PF=7.045  AvgW=+7.098%  AvgL=-4.077%  MFE-capture=0.319

**Best template by regime (T1 exit):**

| Regime | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| bull | 360,233 | 84.46% | +9.481% | 14.980 |
| bear | 39,732 | 88.78% | +14.001% | 18.434 |
| range | 96,476 | 85.51% | +8.236% | 11.228 |

## Recommendations


### Production Entry Filters

Apply ALL of the following before entering a trade:

1. **Long-only** — `predicted_direction == 1`  
   Shorts have negative expectancy (-0.639%). Exclude unconditionally.

2. **Known sector regime** — `sector_regime IN ('bull', 'bear', 'range')`  
   Unknown-regime trades: Exp=+0.000%  PF=0.000. These destroy edge.

3. **Conviction >= MODERATE** — `conviction_level != 'LOW'`  
   LOW conviction: Exp=-0.145%  PF=0.941. Only conviction bucket with negative expectancy.

4. **Confluence >= 5** (recommended) — `confluence_score >= 5`  
   Trades with confluence < 5 have markedly lower expectancy.

### Production Exit Logic

**Primary recommendation: T1 Exit**
- Baseline (all trades): Exp=+0.396%  PF=1.204
- T1 exit (all trades):  Exp=+8.287%  PF=9.944
- T1 + entry filters:    Exp=+8.617%  PF=10.754
- T1 + best template:    Exp=+9.601%  PF=14.468

**Exit rules:**
1. Set hard stop at entry_price - 1.5 x ATR_14 (short: + 1.5 x ATR)
2. Set T1 target at entry_price + 1.0 x ATR_14
3. If T1 hit: move stop to break-even (entry price)
4. If neither T1 nor stop triggered by market close day 5: exit at market

**Enhanced: T1 + Break-Even Stop**
- Best template + Break-Even After T1: Exp=+1.526%  PF=3.141
- Floors all T1-hit trades at 0%, eliminates negative outcomes after T1
- Slightly reduces expectancy vs pure 5d close but dramatically improves worst-trade distribution

### Conditions to Avoid

| Condition | Expectancy | PF | Action |
|---|---|---|---|
| Short trades (direction==-1) | -0.639% | 0.774 | Skip entirely |
| Unknown sector regime | +0.000% | 0.000 | Skip entirely |
| LOW conviction | -0.145% | 0.941 | Skip entirely |
| VIX high (atr extreme) | (wider ranges, larger losses) | — | Reduce size 50% |
| Confluence < 5 | (below threshold) | — | Skip |

### Best Trade Template

```
ENTRY CRITERIA (all must be true):
  predicted_direction  == 1           (long only)
  conviction_level     IN ('HIGH', 'VERY_HIGH')
  sector_regime        IN ('bull', 'bear', 'range')
  confluence_score     >= 5

EXIT RULES:
  1. Hard stop:       entry_price - (1.5 x ATR_14)
  2. T1 target:       entry_price + (1.0 x ATR_14)
  3. After T1 hit:    move stop to entry_price (break-even)
  4. Time stop:       exit at open of day 6 if neither triggered

EXPECTED PERFORMANCE (backtest):
  Win rate:      53.91%
  Expectancy:    +1.526% per trade
  Profit factor: 3.141
  Avg winner:    +4.153%
  Avg loser:     -1.547%
  Sample size:   496,441 trades
```

### Notes and Caveats

- ATR values in pre-2020 data are elevated (fewer bars -> wider ATR), making T1 targets appear further and T1 hit rates inflated. Filter to 2022+ for cleaner regime-based testing.
- Exit strategies marked 'approximation' (ATR trail, break-even) require intra-day price data for exact simulation; current model uses 5d close as proxy.
- Conviction downgrade exit and confluence deterioration exit require day-level signal tracking not yet in the pipeline; flag for data collection.
- All figures are hypothetical backtest results. Live performance will differ due to slippage, spread, and market impact.