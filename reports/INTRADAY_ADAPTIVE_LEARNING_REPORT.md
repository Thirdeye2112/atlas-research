# Atlas Intraday Adaptive Learning Report v1

**Generated:** 2026-06-16 08:47
**Horizon:** 6 bars (30 minutes)
**Status:** ANALYSIS ONLY. No live trades. No signals changed.
**Method:** 70/30 chronological walk-forward. Slippage: 5 bps/side.

**Data limitation:** ~60 trading days per ticker (Yahoo Finance free tier).
Results are directional, not statistically definitive.
Most refinements will be rejected or marked 'candidate' due to small OOS samples.
Re-run after 90+ trading days for reliable promotion.

---

## 1. Which Setups Failed?

Setups with OOS expectancy < -0.02% after slippage:

| Setup | Dir | OOS Exp | OOS PF | n |
|---|---|---|---|---|
| hvol_reversal_bear | short | -0.417% | 0.40 | 156 |
| vwap_reject_bear | short | -0.219% | 0.53 | 149 |
| vol_squeeze_bull | long | -0.172% | 0.45 | 49 |
| orb_bear | short | -0.145% | 0.65 | 686 |
| failed_breakout_bear | short | -0.143% | 0.51 | 685 |
| momentum_cont_bull | long | -0.116% | 0.57 | 4053 |
| vwap_reclaim_bull | long | -0.097% | 0.76 | 2334 |
| macd_cross_bull | long | -0.088% | 0.69 | 1008 |
| ema_pullback_bear | short | -0.081% | 0.66 | 6252 |
| first_red_rev_bull | long | -0.071% | 0.70 | 2010 |

## 2. Why Did They Fail?

Top attribution signals for failed setups (|effect size| rank):

| Setup | Dir | Condition | Winner Avg | Loser Avg | Effect | Confidence |
|---|---|---|---|---|---|---|
| hvol_reversal_bear | short | time=open_30m | 0.425 | 0.378 | 1.124 | 39.6% |
| hvol_reversal_bear | short | time=15_16 | 0.400 | 0.378 | 1.058 | 40.5% |
| hvol_reversal_bear | short | daily_vix_regime=low|moderate | 0.383 | 0.366 | 1.012 | 0.2% |
| vwap_reject_bear | short | daily_conviction=VERY_HIGH | 0.571 | 0.378 | 1.443 | 73.9% |
| vwap_reject_bear | short | time=14_15 | 0.500 | 0.396 | 1.263 | 72.6% |
| vwap_reject_bear | short | daily_jarvis=True|true|1 | 0.439 | 0.380 | 1.109 | 36.5% |
| vol_squeeze_bull | long | daily_jarvis=True|true|1 | 0.400 | 0.353 | 1.089 | 0.0% |
| vol_squeeze_bull | long | time=1030_14 | 0.382 | 0.367 | 1.041 | 0.5% |
| vol_squeeze_bull | long | daily_regime=bull | 0.367 | 0.367 | 1.000 | 0.0% |
| orb_bear | short | time=14_15 | 0.495 | 0.375 | 1.321 | 99.0% |
| orb_bear | short | time=930_10 | 0.440 | 0.375 | 1.174 | 36.7% |
| orb_bear | short | daily_conviction=VERY_HIGH | 0.421 | 0.370 | 1.124 | 46.0% |
| failed_breakout_bear | short | daily_conviction=VERY_HIGH | 0.566 | 0.389 | 1.405 | 98.2% |
| failed_breakout_bear | short | time=14_15 | 0.489 | 0.403 | 1.215 | 91.6% |
| failed_breakout_bear | short | time=930_10 | 0.425 | 0.403 | 1.056 | 26.5% |

## 3. What Conditions Separate Winners from Losers?

Top 20 attribution signals by absolute effect size (all setups combined):

| Setup | Dir | Condition | Winner | Loser | Effect | n |
|---|---|---|---|---|---|---|
| vwap_reject_bear | short | daily_conviction=VERY_HIGH | 0.571 | 0.378 | 1.443 | 149 |
| failed_breakout_bear | short | daily_conviction=VERY_HIGH | 0.566 | 0.389 | 1.405 | 685 |
| rsi_reclaim_bear | short | time=15_16 | 0.521 | 0.377 | 1.382 | 398 |
| macd_cross_bull | long | time=10_1030 | 0.616 | 0.448 | 1.374 | 1008 |
| orb_bear | short | time=14_15 | 0.495 | 0.375 | 1.321 | 686 |
| momentum_cont_bull | long | time=10_1030 | 0.579 | 0.440 | 1.317 | 4053 |
| vwap_reclaim_bull | long | time=10_1030 | 0.607 | 0.470 | 1.291 | 2334 |
| macd_cross_bear | short | time=930_10 | 0.554 | 0.438 | 1.267 | 864 |
| higher_low_cont_bull | long | time=10_1030 | 0.550 | 0.435 | 1.265 | 5610 |
| vwap_reject_bear | short | time=14_15 | 0.500 | 0.396 | 1.263 | 149 |
| orb_bull | long | time=10_1030 | 0.591 | 0.468 | 1.262 | 1074 |
| ema_pullback_bull | long | time=10_1030 | 0.541 | 0.439 | 1.233 | 7785 |
| ema_pullback_bear | short | time=930_10 | 0.503 | 0.413 | 1.218 | 6252 |
| failed_breakout_bear | short | time=14_15 | 0.489 | 0.403 | 1.215 | 685 |
| exhaustion_rev_bear | short | daily_conviction=VERY_HIGH | 0.510 | 0.411 | 1.213 | 1092 |
| exhaustion_rev_bull | long | time=15_16 | 0.526 | 0.435 | 1.211 | 980 |
| first_green_rev_bear | short | time=open_30m | 0.508 | 0.423 | 1.202 | 1712 |
| orb_bear | short | time=930_10 | 0.440 | 0.375 | 1.174 | 686 |
| rsi_reclaim_bull | long | time=1030_14 | 0.581 | 0.496 | 1.170 | 403 |
| hvol_reversal_bull | long | daily_jarvis=True|true|1 | 0.609 | 0.481 | 1.165 | 195 |

## 4. Which Refinements Improved Results?

**PROMOTED** (all walk-forward criteria met):

| Rule | IS Exp | IS PF | OOS Exp | OOS PF | Tickers | Weeks |
|---|---|---|---|---|---|---|
| **rsi_reclaim_bull/long: Power hour** | +0.091% | 1.32 | +0.358% | 3.01 | 5 | 5 |
| **inside_bar_bull/long: Power hour** | +0.178% | 1.77 | +0.356% | 3.08 | 10 | 5 |
| **hvol_reversal_bull/long: After 10:00** | -0.046% | 0.90 | +0.314% | 2.27 | 8 | 5 |
| **engulf_bull/long: Power hour** | +0.112% | 1.33 | +0.263% | 1.75 | 10 | 5 |
| **exhaustion_rev_bull/long: Power hour** | +0.134% | 1.42 | +0.233% | 2.21 | 10 | 5 |
| **engulf_bull/long: After 10:00** | +0.060% | 1.24 | +0.155% | 1.51 | 10 | 5 |

**CANDIDATE** (OOS positive but not all criteria met):

| Rule | Orig Exp | Refined Exp | OOS Exp | OOS PF | Tickers | Weeks | Notes |
|---|---|---|---|---|---|---|---|
| hvol_reversal_bull/long: Power hour | -0.079% | -0.085% | +0.409% | 2.57 | 7 | 5 |  |
| hvol_reversal_bull/long: VIX low or moderate | -0.079% | -0.132% | +0.262% | 2.10 | 7 | 5 |  |
| hvol_reversal_bull/long: Daily conviction HIGH+ + VIX low or moderate | -0.079% | -0.132% | +0.262% | 2.10 | 7 | 5 |  |
| hvol_reversal_bull/long: Daily regime bull + VIX low or moderate | -0.079% | -0.132% | +0.262% | 2.10 | 7 | 5 |  |
| rsi_reclaim_bull/long: After 10:00 | +0.011% | +0.009% | +0.116% | 1.71 | 10 | 5 |  |

## 5. Which Refinements Were Overfit?

Improved IS but failed OOS:

| Rule | IS Exp | OOS Exp | Reject Reason |
|---|---|---|---|
| orb_bull/long: Daily conviction VH | +0.354% | -0.246% | OOS exp=-0.246% <= 0; OOS PF 0.41 not > original 1.00; ticker breadth  |
| vwap_reclaim_bull/long: Power hour | +0.325% | -0.110% | OOS exp=-0.110% <= 0 |
| vwap_reclaim_bull/long: Daily conviction VH | +0.247% | -0.160% | OOS exp=-0.160% <= 0; OOS PF 0.60 not > original 0.76; ticker breadth  |
| macd_cross_bull/long: Power hour | +0.205% | -0.183% | OOS exp=-0.183% <= 0; OOS PF 0.65 not > original 0.69 |
| higher_low_cont_bull/long: Power hour | +0.153% | -0.078% | OOS exp=-0.078% <= 0 |
| vwap_reject_bear/short: Power hour | +0.139% | -0.495% | OOS exp=-0.495% <= 0; OOS PF 0.35 not > original 0.53 |
| first_green_rev_bear/short: First 30 min | +0.102% | -0.031% | OOS exp=-0.031% <= 0 |
| exhaustion_rev_bull/long: Daily conviction VH | +0.100% | -0.156% | OOS exp=-0.156% <= 0; OOS PF 0.37 not > original 0.85; ticker breadth  |
| momentum_cont_bull/long: Power hour | +0.097% | -0.288% | OOS exp=-0.288% <= 0; OOS PF 0.48 not > original 0.57 |
| failed_breakout_bear/short: Daily conviction VH | +0.092% | -0.042% | OOS exp=-0.042% <= 0; ticker breadth 1<3 |

## 6. Which Refined Rules Should Be Watched?

Candidates and near-candidates (positive OOS, not yet promoted):

| Rule | OOS Exp | OOS PF | Tickers | Weeks | Missing Criteria |
|---|---|---|---|---|---|
| hvol_reversal_bull/long: Power hour | +0.409% | 2.57 | 7 | 5 |  |
| orb_bear/short: First hour | +0.374% | 5.00 | 0 | 2 | refined OOS n=3<5; ticker breadth 0<3; week breadt |
| orb_bear/short: Daily conviction HIGH+ + First hour | +0.374% | 5.00 | 0 | 2 | refined OOS n=3<5; ticker breadth 0<3; week breadt |
| rsi_reclaim_bear/short: Daily conviction VH | +0.263% | 3.35 | 1 | 4 | ticker breadth 1<3; outlier sensitivity 75%>40% |
| hvol_reversal_bull/long: VIX low or moderate | +0.262% | 2.10 | 7 | 5 |  |
| hvol_reversal_bull/long: Daily conviction HIGH+ + VIX l | +0.262% | 2.10 | 7 | 5 |  |
| hvol_reversal_bull/long: Daily regime bull + VIX low or | +0.262% | 2.10 | 7 | 5 |  |
| orb_bear/short: Daily conviction VH | +0.238% | 1.98 | 1 | 3 | ticker breadth 1<3 |
| hvol_reversal_bull/long: Daily conviction HIGH+ | +0.232% | 1.77 | 9 | 5 | OOS PF 1.77 not > original 1.77 |
| hvol_reversal_bull/long: Daily regime bull | +0.232% | 1.77 | 9 | 5 | OOS PF 1.77 not > original 1.77 |
| hvol_reversal_bull/long: Daily conviction HIGH+ + Daily | +0.232% | 1.77 | 9 | 5 | OOS PF 1.77 not > original 1.77 |
| exhaustion_rev_bull/long: First 30 min | +0.195% | 2.28 | 1 | 3 | ticker breadth 1<3 |

## 7. Which Rules Are Promotable?

**6 rule(s) are promotable:**
- **engulf_bull/long: After 10:00**: OOS Exp=+0.155%, OOS PF=1.51, 10 tickers, 5 weeks
- **engulf_bull/long: Power hour**: OOS Exp=+0.263%, OOS PF=1.75, 10 tickers, 5 weeks
- **exhaustion_rev_bull/long: Power hour**: OOS Exp=+0.233%, OOS PF=2.21, 10 tickers, 5 weeks
- **hvol_reversal_bull/long: After 10:00**: OOS Exp=+0.314%, OOS PF=2.27, 8 tickers, 5 weeks
- **inside_bar_bull/long: Power hour**: OOS Exp=+0.356%, OOS PF=3.08, 10 tickers, 5 weeks
- **rsi_reclaim_bull/long: Power hour**: OOS Exp=+0.358%, OOS PF=3.01, 5 tickers, 5 weeks

## 8. Refinement Summary Statistics

| Metric | Value |
|---|---|
| Total setup types analyzed | 27 |
| Setup types with enough IS data (n>=30) | 26 |
| Attribution conditions tested | 432 |
| Refinements generated | 301 |
| Promoted | 6 |
| Candidate (watch) | 5 |
| Rejected (overfit/low sample) | 290 |

## 9. Top Setups Baseline (OOS Expectancy)

| Setup | Dir | IS Exp | OOS Exp | OOS PF | n |
|---|---|---|---|---|---|
| hvol_reversal_bull | long | -0.079% | +0.232% | 1.77 | 195 |
| vol_squeeze_bear | short | +0.029% | +0.200% | 1.86 | 37 |
| engulf_bull | long | +0.015% | +0.122% | 1.39 | 321 |
| rsi_reclaim_bull | long | +0.011% | +0.043% | 1.21 | 403 |
| engulf_bear | short | -0.041% | +0.026% | 1.06 | 307 |
| inside_bar_bear | short | -0.103% | +0.016% | 1.09 | 1708 |
| orb_bull | long | +0.203% | +0.002% | 1.00 | 1074 |
| inside_bar_bull | long | +0.014% | -0.020% | 0.90 | 1792 |
| exhaustion_rev_bull | long | -0.015% | -0.031% | 0.85 | 980 |
| lower_high_rej_bear | short | -0.068% | -0.035% | 0.85 | 4372 |

---
_Generated by run_intraday_rule_refinement.py on 2026-06-16 08:47_
_Analysis only. No live trading. No signals changed._
_Promotion criteria: OOS exp>0, OOS PF>original PF, >=30 IS samples, >=3 tickers, >=3 weeks, outlier sensitivity<40%_