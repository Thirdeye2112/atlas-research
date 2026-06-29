# 5-Minute Candle Mutual Exclusivity Report

**Generated:** 2026-06-27 17:14 UTC  
**Tickers:** 10  |  **Candles:** 939,238  |  **Date range:** 2021-01-04 14:30:00 -> 2026-06-18 17:20:00
**Rise events:** 93,930  |  **Drop events:** 93,929  |  **Labelling:** top/bottom 10% candle return per ticker

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
| consec_dir | continuous | — | — | 2000001.0000 | 1.0000 | 0.0000 | True |
| rsi_reclaim50 | binary | 1.9400 | 0.0600 | 32.2130 | 0.3053 | 0.0000 | True |
| macd_bull_cross | binary | 1.8520 | 0.1480 | 12.4930 | 0.2057 | 0.0000 | True |
| above_bb_upper | binary | 1.8440 | 0.1560 | 11.8070 | 0.3029 | 0.0000 | True |
| rsi_slope | continuous | — | — | 10.7780 | 0.8302 | 0.0000 | True |
| macd_hist_rising | binary | 1.7350 | 0.2650 | 6.5480 | 0.7355 | 0.0000 | True |
| dist_ema9_pct | continuous | — | — | 5.5280 | 0.6936 | 0.0000 | True |
| rsi_above70 | binary | 1.6630 | 0.3370 | 4.9270 | 0.2192 | 0.0000 | True |
| above_ema9 | binary | 1.6210 | 0.3790 | 4.2710 | 0.6052 | 0.0000 | True |
| bb_pct | continuous | — | — | 3.7970 | 0.5831 | 0.0000 | True |
| above_all_emas | binary | 1.5750 | 0.4250 | 3.7100 | 0.4336 | 0.0000 | True |
| dist_ema20_pct | continuous | — | — | 3.0030 | 0.5004 | 0.0000 | True |
| rsi | continuous | — | — | 2.8740 | 0.4838 | 0.0000 | True |
| vwap_dist_pct | continuous | — | — | 2.7600 | 0.4681 | 0.0000 | True |
| above_ema20 | binary | 1.4350 | 0.5650 | 2.5400 | 0.4182 | 0.0000 | True |
| above_vwap | binary | 1.4300 | 0.5700 | 2.5070 | 0.4095 | 0.0000 | True |
| rsi_above50 | binary | 1.3760 | 0.6240 | 2.2070 | 0.3607 | 0.0000 | True |

---
## 2. Drop Predictors (ME ≤ 0.5, FDR pass)
| feature | type | rise_lift | drop_lift | me_score | effect_size | p_value | fdr_pass |
|---|---|---|---|---|---|---|---|
| rsi_lose50 | binary | 0.0620 | 1.9380 | 0.0320 | 0.3045 | 0.0000 | True |
| below_bb_lower | binary | 0.1380 | 1.8620 | 0.0740 | 0.3240 | 0.0000 | True |
| macd_bear_cross | binary | 0.1420 | 1.8580 | 0.0760 | 0.2070 | 0.0000 | True |
| rsi_below30 | binary | 0.3300 | 1.6700 | 0.1970 | 0.2293 | 0.0000 | True |
| below_all_emas | binary | 0.4510 | 1.5490 | 0.2910 | 0.4483 | 0.0000 | True |

---
## 3. Neutral Features (0.8 < ME < 1.25)
| feature | type | me_score | p_value |
|---|---|---|---|
| upper_dom | binary | 1.2190 | 0.0000 |
| upper_wick_pct | continuous | 1.1680 | 0.0000 |
| inside_bar | binary | 1.1230 | 0.0000 |
| body_to_range | continuous | 1.0760 | 0.0000 |
| vol_dry | binary | 1.0500 | 0.0017 |
| bb_squeeze | binary | 1.0360 | 0.0000 |
| shooting_star | binary | 1.0220 | 0.8157 |
| prior2_aligned_bear | binary | 1.0200 | 0.0146 |
| prev1_vol_ratio | continuous | 1.0180 | 0.0009 |
| vol_climax | binary | 1.0150 | 0.4099 |

---
## 4. Session-of-Day Stratification (top 10 features)
| session | feature | rise_mean | drop_mean | effect_size | p_value | n_rise | n_drop |
|---|---|---|---|---|---|---|---|
| other | consec_dir | 1.9484 | -1.9998 | 1.0000 | 0.0000 | 64361 | 64788 |
| other | rsi_reclaim50 | 0.1940 | 0.0029 | 0.1911 | 0.0000 | 64361 | 64788 |
| other | macd_bull_cross | 0.1041 | 0.0056 | 0.0985 | 0.0000 | 64361 | 64788 |
| other | above_bb_upper | 0.2016 | 0.0091 | 0.1925 | 0.0000 | 64361 | 64788 |
| other | rsi_slope | 6.3073 | -6.4518 | 0.8733 | 0.0000 | 64355 | 64772 |
| other | below_all_emas | 0.1662 | 0.6353 | 0.4691 | 0.0000 | 64361 | 64788 |
| other | rsi_below30 | 0.0270 | 0.1613 | 0.1343 | 0.0000 | 64361 | 64788 |
| other | macd_bear_cross | 0.0058 | 0.1059 | 0.1001 | 0.0000 | 64361 | 64788 |
| other | below_bb_lower | 0.0106 | 0.2296 | 0.2190 | 0.0000 | 64361 | 64788 |
| other | rsi_lose50 | 0.0032 | 0.1941 | 0.1909 | 0.0000 | 64361 | 64788 |
| power_hour | consec_dir | 1.9180 | -1.9762 | 1.0000 | 0.0000 | 17544 | 17477 |
| power_hour | rsi_reclaim50 | 0.1594 | 0.0002 | 0.1591 | 0.0000 | 17544 | 17477 |
| power_hour | macd_bull_cross | 0.0876 | 0.0048 | 0.0827 | 0.0000 | 17544 | 17477 |
| power_hour | above_bb_upper | 0.1000 | 0.0005 | 0.0995 | 0.0000 | 17544 | 17477 |
| power_hour | rsi_slope | 5.3331 | -5.5279 | 0.8975 | 0.0000 | 17544 | 17477 |
| power_hour | below_all_emas | 0.1791 | 0.5975 | 0.4184 | 0.0000 | 17544 | 17477 |
| power_hour | rsi_below30 | 0.0287 | 0.1568 | 0.1282 | 0.0000 | 17544 | 17477 |
| power_hour | macd_bear_cross | 0.0056 | 0.0872 | 0.0816 | 0.0000 | 17544 | 17477 |
| power_hour | below_bb_lower | 0.0006 | 0.1351 | 0.1345 | 0.0000 | 17544 | 17477 |
| power_hour | rsi_lose50 | 0.0001 | 0.1584 | 0.1583 | 0.0000 | 17544 | 17477 |
| lunch | consec_dir | 2.0083 | -1.9534 | 1.0000 | 0.0000 | 12025 | 11664 |
| lunch | rsi_reclaim50 | 0.1755 | 0.0297 | 0.1458 | 0.0000 | 12025 | 11664 |
| lunch | macd_bull_cross | 0.1122 | 0.0275 | 0.0847 | 0.0000 | 12025 | 11664 |
| lunch | above_bb_upper | 0.4185 | 0.0920 | 0.3265 | 0.0000 | 12025 | 11664 |
| lunch | rsi_slope | 7.4818 | -6.8965 | 0.5800 | 0.0000 | 12025 | 11664 |
| lunch | below_all_emas | 0.2579 | 0.5652 | 0.3073 | 0.0000 | 12025 | 11664 |
| lunch | rsi_below30 | 0.0834 | 0.2780 | 0.1946 | 0.0000 | 12025 | 11664 |
| lunch | macd_bear_cross | 0.0215 | 0.1037 | 0.0822 | 0.0000 | 12025 | 11664 |
| lunch | below_bb_lower | 0.0750 | 0.3772 | 0.3022 | 0.0000 | 12025 | 11664 |
| lunch | rsi_lose50 | 0.0290 | 0.1731 | 0.1441 | 0.0000 | 12025 | 11664 |

---
_Full table: `reports/candle_me_full.csv`  |  Session table: `reports/candle_me_session.csv`_

_Generated by `scripts/candle_me_study.py`_