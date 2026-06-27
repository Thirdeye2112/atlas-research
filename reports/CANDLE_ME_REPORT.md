# 5-Minute Candle Mutual Exclusivity Report

**Generated:** 2026-06-27 20:13 UTC  
**Tickers:** 5,561  |  **Candles:** 210,351,471  |  **Date range:** 2021-01-04 14:30:00 -> 2026-06-26 19:55:00
**Rise events:** 21,165,344  |  **Drop events:** 24,694,159  |  **Labelling:** top/bottom 10% candle return per ticker

---
## Method
- Features extracted from **C-2** and **C-1** (2 bars before the event candle C-0)
- **ME score** = rise_lift ÷ drop_lift
  - ME ≥ 2 → fires ≥2× more before rises → **Rise signal**
  - ME ≤ 0.5 → fires ≥2× more before drops → **Drop signal**
- Stats: χ² (binary) / Mann-Whitney U (continuous) + BH FDR α=0.05
- Effect size: Cramér's V (binary) / Cliff's δ (continuous)
---
## 1. Rise Predictors (ME ≥ 2.0, FDR pass)
| feature | type | rise_lift | drop_lift | me_score | effect_size | p_value | fdr_pass |
|---|---|---|---|---|---|---|---|
| consec_dir | continuous | — | — | 1214.9820 | 0.9984 | 0.0000 | True |
| rsi_reclaim50 | binary | 1.9160 | 0.2150 | 8.9140 | 0.2461 | 0.0000 | True |
| above_bb_upper | binary | 1.8010 | 0.3130 | 5.7450 | 0.2404 | 0.0000 | True |
| macd_bull_cross | binary | 1.7670 | 0.3430 | 5.1560 | 0.1611 | 0.0000 | True |
| rsi_slope | continuous | — | — | 4.6290 | 0.6447 | 0.0000 | True |
| macd_hist_rising | binary | 1.5580 | 0.5210 | 2.9890 | 0.5173 | 0.0000 | True |
| dist_ema9_pct | continuous | — | — | 2.9430 | 0.4927 | 0.0000 | True |
| rsi_above70 | binary | 1.5380 | 0.5390 | 2.8520 | 0.1571 | 0.0000 | True |
| bb_pct | continuous | — | — | 2.4390 | 0.4184 | 0.0000 | True |
| above_ema9 | binary | 1.4550 | 0.6100 | 2.3830 | 0.4200 | 0.0000 | True |
| above_all_emas | binary | 1.4200 | 0.6400 | 2.2170 | 0.2996 | 0.0000 | True |
| vwap_dist_pct | continuous | — | — | 2.1720 | 0.3694 | 0.0000 | True |
| dist_ema20_pct | continuous | — | — | 2.0370 | 0.3414 | 0.0000 | True |

---
## 2. Drop Predictors (ME ≤ 0.5, FDR pass)
| feature | type | rise_lift | drop_lift | me_score | effect_size | p_value | fdr_pass |
|---|---|---|---|---|---|---|---|
| rsi_lose50 | binary | 0.1440 | 1.7340 | 0.0830 | 0.2292 | 0.0000 | True |
| below_bb_lower | binary | 0.2650 | 1.6300 | 0.1630 | 0.2189 | 0.0000 | True |
| macd_bear_cross | binary | 0.2690 | 1.6260 | 0.1660 | 0.1524 | 0.0000 | True |
| rsi_below30 | binary | 0.4910 | 1.4370 | 0.3420 | 0.1492 | 0.0000 | True |
| below_all_emas | binary | 0.5820 | 1.3580 | 0.4290 | 0.3013 | 0.0000 | True |

---
## 3. Neutral Features (0.8 < ME < 1.25)
| feature | type | me_score | p_value |
|---|---|---|---|
| outside_bar | binary | 1.1860 | 0.0000 |
| prev1_body_pct | continuous | 1.1830 | 0.0000 |
| prev2_body_pct | continuous | 1.1770 | 0.0000 |
| range_expanding_into | binary | 1.1690 | 0.0000 |
| vol_climax | binary | 1.1640 | 0.0000 |
| prior2_aligned_bull | binary | 1.1560 | 0.0000 |
| prior2_aligned_bear | binary | 1.1530 | 0.0000 |
| ema9_bull_stack | binary | 1.1440 | 0.0000 |
| prev2_body_dir | binary | 1.1380 | 0.0000 |
| compression_breakout | binary | 1.1310 | 0.0000 |

---
## 4. Session-of-Day Stratification (top 10 features)
| session | feature | rise_mean | drop_mean | effect_size | p_value | n_rise | n_drop |
|---|---|---|---|---|---|---|---|
| lunch | consec_dir | 1.7374 | -1.6029 | 0.9995 | 0.0000 | 86164 | 93551 |
| lunch | rsi_reclaim50 | 0.1602 | 0.0416 | 0.1186 | 0.0000 | 86164 | 93551 |
| lunch | above_bb_upper | 0.3748 | 0.1109 | 0.2639 | 0.0000 | 86164 | 93551 |
| lunch | macd_bull_cross | 0.1097 | 0.0325 | 0.0771 | 0.0000 | 86164 | 93551 |
| lunch | rsi_slope | 6.4486 | -5.4410 | 0.4827 | 0.0000 | 86153 | 93535 |
| lunch | below_all_emas | 0.2940 | 0.5456 | 0.2515 | 0.0000 | 86164 | 93551 |
| lunch | rsi_below30 | 0.1015 | 0.2538 | 0.1523 | 0.0000 | 86164 | 93551 |
| lunch | macd_bear_cross | 0.0272 | 0.0990 | 0.0718 | 0.0000 | 86164 | 93551 |
| lunch | below_bb_lower | 0.1036 | 0.3361 | 0.2324 | 0.0000 | 86164 | 93551 |
| lunch | rsi_lose50 | 0.0324 | 0.1499 | 0.1175 | 0.0000 | 86164 | 93551 |
| other | consec_dir | 1.5810 | -1.3434 | 0.9980 | 0.0000 | 682713 | 809125 |
| other | rsi_reclaim50 | 0.1533 | 0.0148 | 0.1384 | 0.0000 | 682713 | 809125 |
| other | above_bb_upper | 0.1613 | 0.0227 | 0.1386 | 0.0000 | 682713 | 809125 |
| other | macd_bull_cross | 0.0866 | 0.0152 | 0.0714 | 0.0000 | 682713 | 809125 |
| other | rsi_slope | 4.6848 | -3.9591 | 0.6700 | 0.0000 | 682597 | 808887 |
| other | below_all_emas | 0.2093 | 0.5130 | 0.3037 | 0.0000 | 682713 | 809125 |
| other | rsi_below30 | 0.0364 | 0.1171 | 0.0807 | 0.0000 | 682713 | 809125 |
| other | macd_bear_cross | 0.0117 | 0.0781 | 0.0664 | 0.0000 | 682713 | 809125 |
| other | below_bb_lower | 0.0178 | 0.1446 | 0.1268 | 0.0000 | 682713 | 809125 |
| other | rsi_lose50 | 0.0094 | 0.1369 | 0.1275 | 0.0000 | 682713 | 809125 |
| power_hour | consec_dir | 1.6349 | -1.4275 | 0.9988 | 0.0000 | 153804 | 174643 |
| power_hour | rsi_reclaim50 | 0.1191 | 0.0125 | 0.1067 | 0.0000 | 153804 | 174643 |
| power_hour | above_bb_upper | 0.0974 | 0.0189 | 0.0785 | 0.0000 | 153804 | 174643 |
| power_hour | macd_bull_cross | 0.0737 | 0.0154 | 0.0583 | 0.0000 | 153804 | 174643 |
| power_hour | rsi_slope | 4.0137 | -3.5485 | 0.6571 | 0.0000 | 153777 | 174590 |
| power_hour | below_all_emas | 0.2281 | 0.4953 | 0.2673 | 0.0000 | 153804 | 174643 |
| power_hour | rsi_below30 | 0.0484 | 0.1261 | 0.0777 | 0.0000 | 153804 | 174643 |
| power_hour | macd_bear_cross | 0.0116 | 0.0687 | 0.0572 | 0.0000 | 153804 | 174643 |
| power_hour | below_bb_lower | 0.0115 | 0.0936 | 0.0821 | 0.0000 | 153804 | 174643 |
| power_hour | rsi_lose50 | 0.0071 | 0.1118 | 0.1046 | 0.0000 | 153804 | 174643 |

---
_Full table: `reports/candle_me_full.csv`  |  Session table: `reports/candle_me_session.csv`_

_Generated by `scripts/candle_me_study.py`_