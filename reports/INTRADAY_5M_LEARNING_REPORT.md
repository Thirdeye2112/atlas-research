# Atlas Intraday 5-Minute Learning Report v1

**Generated:** 2026-06-16 08:10
**Horizon:** 6 bars (30 minutes)
**Status:** ANALYSIS ONLY. No live trades. No signals changed.
**Slippage:** 5 bps per side applied to all expectancy figures.

---

## Data Overview

- Total 5-min bars in DB: **49,257** (approximate, via setups join)
- Total setups detected:   **49,257**
- Unique setup types:      **27**
- Tickers:                 **AAPL, AMD, AMZN, GOOGL, META, MSFT, NVDA, QQQ, SPY, TSLA**
- Date range:              **2026-03-23 to 2026-06-16**

**Limitation:** Free Yahoo Finance 5m data covers ~60 trading days per ticker.
Sample sizes are small for some setups. Results require ~6 months of data
to be statistically robust. Treat these findings as directional, not definitive.

## 1. Overall Setup Baseline

| Metric | Value |
|---|---|
| Total setups | 49,257 |
| Win rate | 36.8% |
| Expectancy (after slip) | -0.08% per trade |
| Profit factor | 0.68 |
| Avg winner | +0.45% |
| Avg loser | -0.39% |
| Max drawdown (cumulative) | +3935.56% |

## 2. Walk-Forward Validation Results (all setups)

70% in-sample / 30% out-of-sample chronological split.

| Setup | Dir | IS n | IS WR | IS Exp | IS PF | OOS n | OOS WR | OOS Exp | OOS PF | WF? |
|---|---|---|---|---|---|---|---|---|---|---|
| hvol_reversal_bull | long | 136 | 52.2% | -0.08% | 0.82 | 59 | 52.5% | +0.24% | 1.80 | no |
| vol_squeeze_bear | short | 25 | 48.0% | +0.03% | 1.20 | 12 | 58.3% | +0.20% | 1.86 | no |
| engulf_bull | long | 224 | 49.1% | +0.01% | 1.06 | 97 | 48.5% | +0.12% | 1.39 | no |
| rsi_reclaim_bull | long | 282 | 50.0% | +0.01% | 1.05 | 121 | 48.8% | +0.04% | 1.20 | no |
| engulf_bear | short | 214 | 41.6% | -0.04% | 0.89 | 93 | 44.1% | +0.03% | 1.06 | no |
| inside_bar_bear | short | 1195 | 39.5% | -0.10% | 0.56 | 513 | 44.4% | +0.02% | 1.09 | no |
| orb_bull | long | 751 | 50.1% | +0.20% | 1.89 | 323 | 39.3% | +0.00% | 1.00 | no |
| inside_bar_bull | long | 1254 | 43.5% | +0.01% | 1.08 | 538 | 42.6% | -0.02% | 0.90 | no |
| exhaustion_rev_bull | long | 686 | 44.9% | -0.02% | 0.92 | 294 | 40.1% | -0.03% | 0.85 | no |
| lower_high_rej_bear | short | 3060 | 40.3% | -0.07% | 0.66 | 1312 | 47.9% | -0.04% | 0.85 | no |
| macd_cross_bear | short | 604 | 43.0% | -0.10% | 0.63 | 260 | 45.4% | -0.04% | 0.83 | no |
| exhaustion_rev_bear | short | 764 | 41.2% | -0.06% | 0.71 | 328 | 43.9% | -0.05% | 0.81 | no |
| rsi_reclaim_bear | short | 278 | 36.0% | -0.14% | 0.55 | 120 | 41.7% | -0.05% | 0.79 | no |
| first_green_rev_bear | short | 1198 | 39.6% | -0.09% | 0.59 | 514 | 48.4% | -0.06% | 0.77 | no |
| ema_pullback_bull | long | 5449 | 45.4% | +0.01% | 1.08 | 2336 | 40.5% | -0.06% | 0.73 | no |
| higher_low_cont_bull | long | 3926 | 44.9% | +0.01% | 1.08 | 1684 | 40.2% | -0.07% | 0.70 | no |
| momentum_cont_bear | short | 2257 | 39.1% | -0.08% | 0.66 | 968 | 47.1% | -0.07% | 0.72 | no |
| first_red_rev_bull | long | 1407 | 44.9% | -0.01% | 0.92 | 603 | 40.8% | -0.07% | 0.70 | no |
| ema_pullback_bear | short | 4376 | 40.2% | -0.07% | 0.68 | 1876 | 43.9% | -0.08% | 0.66 | no |
| macd_cross_bull | long | 705 | 44.8% | +0.01% | 1.07 | 303 | 44.9% | -0.09% | 0.69 | no |
| vwap_reclaim_bull | long | 1633 | 51.3% | +0.18% | 1.72 | 701 | 37.1% | -0.10% | 0.76 | no |
| momentum_cont_bull | long | 2837 | 45.8% | +0.02% | 1.10 | 1216 | 39.8% | -0.12% | 0.57 | no |
| failed_breakout_bear | short | 479 | 41.3% | -0.04% | 0.80 | 206 | 37.9% | -0.14% | 0.51 | no |
| orb_bear | short | 480 | 34.8% | -0.11% | 0.63 | 206 | 43.7% | -0.15% | 0.65 | no |
| vol_squeeze_bull | long | 34 | 44.1% | +0.01% | 1.09 | 15 | 20.0% | -0.17% | 0.45 | no |
| vwap_reject_bear | short | 104 | 37.5% | +0.02% | 1.07 | 45 | 44.4% | -0.22% | 0.53 | no |
| hvol_reversal_bear | short | 109 | 35.8% | -0.26% | 0.57 | 47 | 42.6% | -0.42% | 0.40 | no |

## 3. Which 5-Minute Setups Work?

No setups met all promotion thresholds with current data volume.
More history (>6 months) is needed for reliable promotion.

## 4. Which Setups Fail?

Setups with negative OOS expectancy after slippage:

| Setup | Direction | OOS Exp | Reason |
|---|---|---|---|
| ema_pullback_bear | short | -0.08% | IS WR=40.2%<50.0%; IS exp=-0.07%<0.1%; IS PF=0.68<1.2; OOS W |
| ema_pullback_bull | long | -0.06% | IS WR=45.4%<50.0%; IS exp=+0.01%<0.1%; IS PF=1.08<1.2; OOS W |
| exhaustion_rev_bear | short | -0.05% | IS WR=41.2%<50.0%; IS exp=-0.06%<0.1%; IS PF=0.71<1.2; OOS W |
| exhaustion_rev_bull | long | -0.03% | IS WR=44.9%<50.0%; IS exp=-0.02%<0.1%; IS PF=0.92<1.2; OOS W |
| failed_breakout_bear | short | -0.14% | IS WR=41.3%<50.0%; IS exp=-0.04%<0.1%; IS PF=0.80<1.2; OOS W |
| first_green_rev_bear | short | -0.06% | IS WR=39.6%<50.0%; IS exp=-0.09%<0.1%; IS PF=0.59<1.2; OOS e |
| first_red_rev_bull | long | -0.07% | IS WR=44.9%<50.0%; IS exp=-0.01%<0.1%; IS PF=0.92<1.2; OOS W |
| higher_low_cont_bull | long | -0.07% | IS WR=44.9%<50.0%; IS exp=+0.01%<0.1%; IS PF=1.08<1.2; OOS W |
| hvol_reversal_bear | short | -0.42% | IS WR=35.8%<50.0%; IS exp=-0.26%<0.1%; IS PF=0.57<1.2; OOS W |
| inside_bar_bull | long | -0.02% | IS WR=43.5%<50.0%; IS exp=+0.01%<0.1%; IS PF=1.08<1.2; OOS W |
| lower_high_rej_bear | short | -0.04% | IS WR=40.3%<50.0%; IS exp=-0.07%<0.1%; IS PF=0.66<1.2; OOS e |
| macd_cross_bear | short | -0.04% | IS WR=43.0%<50.0%; IS exp=-0.10%<0.1%; IS PF=0.63<1.2; OOS W |
| macd_cross_bull | long | -0.09% | IS WR=44.8%<50.0%; IS exp=+0.01%<0.1%; IS PF=1.07<1.2; OOS W |
| momentum_cont_bear | short | -0.07% | IS WR=39.1%<50.0%; IS exp=-0.08%<0.1%; IS PF=0.66<1.2; OOS e |
| momentum_cont_bull | long | -0.12% | IS WR=45.8%<50.0%; IS exp=+0.02%<0.1%; IS PF=1.10<1.2; OOS W |
| orb_bear | short | -0.15% | IS WR=34.8%<50.0%; IS exp=-0.11%<0.1%; IS PF=0.63<1.2; OOS W |
| rsi_reclaim_bear | short | -0.05% | IS WR=36.0%<50.0%; IS exp=-0.14%<0.1%; IS PF=0.55<1.2; OOS W |
| vol_squeeze_bull | long | -0.17% | IS WR=44.1%<50.0%; IS exp=+0.01%<0.1%; IS PF=1.09<1.2; OOS W |
| vwap_reclaim_bull | long | -0.10% | OOS WR=37.1%<47.0%; OOS exp=-0.10%<0.05%; OOS PF=0.76<1.1 |
| vwap_reject_bear | short | -0.22% | IS WR=37.5%<50.0%; IS exp=+0.02%<0.1%; IS PF=1.07<1.2; OOS W |

## 5. Performance by Time of Day

| Time Bucket | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| 9:30-10:00 (Opening 30m) | 3606 | 45.0% | -0.07% | 0.76 |
| 9:30-10:00 | 3578 | 46.5% | -0.01% | 0.97 |
| 10:00-10:30 | 3553 | 47.6% | -0.02% | 0.91 |
| 10:30-14:00 | 21396 | 41.4% | -0.05% | 0.71 |
| 14:00-15:00 | 7327 | 41.3% | -0.05% | 0.66 |
| 15:00-16:00 (Power Hour) | 9797 | 44.6% | +0.02% | 1.06 |

## 6. Cross-Ticker Robustness

| Ticker | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| AMZN | 4867 | 44.6% | +0.00% | 1.01 |
| MSFT | 4807 | 44.4% | -0.01% | 0.94 |
| TSLA | 4425 | 46.4% | -0.02% | 0.95 |
| AMD | 4513 | 48.1% | -0.02% | 0.96 |
| META | 4791 | 41.2% | -0.03% | 0.89 |
| all | 49257 | 43.1% | -0.03% | 0.86 |
| AAPL | 4994 | 42.7% | -0.04% | 0.77 |
| GOOGL | 4968 | 43.4% | -0.04% | 0.80 |
| NVDA | 4595 | 44.9% | -0.04% | 0.82 |
| QQQ | 5611 | 41.7% | -0.05% | 0.67 |
| SPY | 5686 | 35.8% | -0.05% | 0.55 |

## 7. High-Volume Environments

| Volume Level | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| — | — | — | — | Not available |

## 8. After-Gap Performance

| Gap Type | N | Win Rate | Expectancy | PF |
|---|---|---|---|---|
| — | — | — | — | Not available |

## 9. Daily Context Alignment (Part 8: Intraday + Daily Connection)

Does intraday setup performance improve when daily conviction agrees?

| Context | N | Expectancy | PF |
|---|---|---|---|
| conviction_VERY_HIGH | 4867 | +0.00% | 1.01 |
| regime_bull | 49257 | -0.03% | 0.86 |
| all_setups | 49257 | -0.03% | 0.86 |
| conviction_HIGH | 44390 | -0.03% | 0.85 |

## 10. Top 10 Setups by OOS Expectancy

| Rank | Setup | Dir | OOS Exp | OOS WR | OOS n |
|---|---|---|---|---|---|
| 1 | hvol_reversal_bull | long | +0.24% | 52.5% | 59 |
| 2 | vol_squeeze_bear | short | +0.20% | 58.3% | 12 |
| 3 | engulf_bull | long | +0.12% | 48.5% | 97 |
| 4 | rsi_reclaim_bull | long | +0.04% | 48.8% | 121 |
| 5 | engulf_bear | short | +0.03% | 44.1% | 93 |
| 6 | inside_bar_bear | short | +0.02% | 44.4% | 513 |
| 7 | orb_bull | long | +0.00% | 39.3% | 323 |
| 8 | inside_bar_bull | long | -0.02% | 42.6% | 538 |
| 9 | exhaustion_rev_bull | long | -0.03% | 40.1% | 294 |
| 10 | lower_high_rej_bear | short | -0.04% | 47.9% | 1312 |

## 11. Bottom 10 Setups by OOS Expectancy

| Rank | Setup | Dir | OOS Exp | OOS WR | OOS n |
|---|---|---|---|---|---|
| 1 | hvol_reversal_bear | short | -0.42% | 42.6% | 47 |
| 2 | vwap_reject_bear | short | -0.22% | 44.4% | 45 |
| 3 | vol_squeeze_bull | long | -0.17% | 20.0% | 15 |
| 4 | orb_bear | short | -0.15% | 43.7% | 206 |
| 5 | failed_breakout_bear | short | -0.14% | 37.9% | 206 |
| 6 | momentum_cont_bull | long | -0.12% | 39.8% | 1216 |
| 7 | vwap_reclaim_bull | long | -0.10% | 37.1% | 701 |
| 8 | macd_cross_bull | long | -0.09% | 44.9% | 303 |
| 9 | ema_pullback_bear | short | -0.08% | 43.9% | 1876 |
| 10 | first_red_rev_bull | long | -0.07% | 40.8% | 603 |

## 12. Setup Detection Frequency

| Setup | Count | % of Total |
|---|---|---|
| ema_pullback_bull | 7,785 | 15.8% |
| ema_pullback_bear | 6,252 | 12.7% |
| higher_low_cont_bull | 5,610 | 11.4% |
| lower_high_rej_bear | 4,372 | 8.9% |
| momentum_cont_bull | 4,053 | 8.2% |
| momentum_cont_bear | 3,225 | 6.5% |
| vwap_reclaim_bull | 2,334 | 4.7% |
| first_red_rev_bull | 2,010 | 4.1% |
| inside_bar_bull | 1,792 | 3.6% |
| first_green_rev_bear | 1,712 | 3.5% |
| inside_bar_bear | 1,708 | 3.5% |
| exhaustion_rev_bear | 1,092 | 2.2% |
| orb_bull | 1,074 | 2.2% |
| macd_cross_bull | 1,008 | 2.0% |
| exhaustion_rev_bull | 980 | 2.0% |
| macd_cross_bear | 864 | 1.8% |
| orb_bear | 686 | 1.4% |
| failed_breakout_bear | 685 | 1.4% |
| rsi_reclaim_bull | 403 | 0.8% |
| rsi_reclaim_bear | 398 | 0.8% |
| engulf_bull | 321 | 0.7% |
| engulf_bear | 307 | 0.6% |
| hvol_reversal_bull | 195 | 0.4% |
| hvol_reversal_bear | 156 | 0.3% |
| vwap_reject_bear | 149 | 0.3% |
| vol_squeeze_bull | 49 | 0.1% |
| vol_squeeze_bear | 37 | 0.1% |

## 13. Recommendations

No setups met all promotion thresholds at current data volume.

**Next steps:**
1. Run ingestion daily for 60-90 days to accumulate data
2. Re-run walk-forward when total setups per type >= 50
3. Focus on time-of-day and daily context filtering to improve signal quality

**Best entry conditions (based on this data):**
- Best time of day: **15_close** (Exp=+0.02%, n=9797)
- Best daily context: **conviction_VERY_HIGH** (Exp=+0.00%)

---
_Generated by run_intraday_walkforward.py on 2026-06-16 08:10_
_Promotion thresholds: IS WR>=50%, IS Exp>=0.1%, IS PF>=1.2, OOS WR>=47%, OOS PF>=1.1_