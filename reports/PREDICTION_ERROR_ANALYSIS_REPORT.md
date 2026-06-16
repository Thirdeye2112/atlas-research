# Prediction Error Analysis Report

**Generated:** 2026-06-15
**Rows analysed:** 847,333  (directional predictions with resolved 5d labels)
**Date range:** 2015-01-02 to 2026-06-05

## 0. Overall Baseline

- **5d hit rate:** 52.0% (n=847,333)
- **10d hit rate:** 52.9%
- **20d hit rate:** 53.8%
- **Expectancy (5d):** +0.0043
- **Rank hit rate:** 6.1%

## 1. Accuracy by Context

| Context | N | HR 5d | HR 10d | HR 20d | Expectancy | Rank Hit |
|---|---|---|---|---|---|---|
| **Jarvis signal** | | | | | | |
| Jarvis green | 111,934 | 49.2% | 49.9% | 51.2% | +0.0077 | 3.8% |
| Jarvis red | 154,631 | 48.4% | 49.3% | 50.6% | +0.0063 | 3.9% |
| **Market regime** | | | | | | |
| Bull regime | 468,777 | 51.6% | 52.5% | 53.9% | +0.0020 | 6.9% |
| Bear regime | 72,795 | 54.0% | 55.8% | 57.7% | +0.0088 | 7.1% |
| Range regime | 305,761 | 52.1% | 52.8% | 52.7% | +0.0069 | 4.6% |
| **Volatility regime** | | | | | | |
| VIX low | 261,699 | 53.1% | 54.3% | 55.6% | +0.0013 | 6.5% |
| VIX moderate | 339,121 | 53.1% | 53.7% | 54.8% | +0.0025 | 6.4% |
| VIX high | 239,610 | 49.3% | 50.3% | 50.9% | +0.0101 | 5.3% |
| **Confluence** | | | | | | |
| Confluence ≥ 3 (5-comp) | 148,739 | 53.1% | 54.2% | 55.0% | +0.0042 | 3.7% |
| Confluence < 2 (5-comp) | 77,183 | 47.9% | 47.3% | 48.5% | +0.0030 | 11.1% |
| **Quality tier** | | | | | | |
| Quality Tier 1 | 59,163 | 50.7% | 50.6% | 50.6% | +0.0017 | 4.0% |
| Quality Tier 2 | 44,005 | 51.1% | 51.6% | 51.8% | +0.0032 | 4.2% |
| Quality Tier 3 | 83,162 | 48.0% | 48.5% | 48.7% | +0.0045 | 4.0% |
| Quality Tier 4 | 158,811 | 47.2% | 47.8% | 48.2% | +0.0096 | 4.1% |
| **Price vs SMA200** | | | | | | |
| Above SMA200 | 426,361 | 52.9% | 53.7% | 55.2% | +0.0025 | 7.0% |
| Below SMA200 | 222,007 | 52.2% | 53.8% | 55.0% | +0.0051 | 6.5% |
| **Conviction level** | | | | | | |
| Conviction VERY_HIGH | 192,007 | 54.2% | 55.8% | 57.6% | +0.0035 | 3.1% |
| Conviction HIGH | 304,434 | 53.9% | 55.2% | 56.3% | +0.0077 | 5.9% |
| Conviction MODERATE | 304,118 | 49.2% | 49.6% | 49.8% | +0.0016 | 6.6% |
| Conviction LOW | 46,774 | 48.6% | 47.8% | 48.1% | +0.0034 | 15.7% |
| **ML signal strength** | | | | | | |
| ML strong (rank ≥ 0.80) | 127,474 | 51.9% | 52.7% | 54.7% | +0.0028 | 39.8% |
| ML moderate (0.60-0.80) | 192,561 | 53.3% | 53.9% | 54.0% | +0.0046 | 0.4% |
| ML weak (< 0.60) | 527,842 | 51.5% | 52.6% | 53.5% | +0.0046 | 0.0% |

## 2. Accuracy by Signal Strength

| Context | N | HR 5d | HR 10d | HR 20d | Expectancy | Rank Hit |
|---|---|---|---|---|---|---|
| ML strong (rank ≥ 0.80) | 127,474 | 51.9% | 52.7% | 54.7% | +0.0028 | 39.8% |
| ML moderate (0.60-0.80) | 192,561 | 53.3% | 53.9% | 54.0% | +0.0046 | 0.4% |
| ML weak (< 0.60) | 527,842 | 51.5% | 52.6% | 53.5% | +0.0046 | 0.0% |
| Rank Q5 (top predictions) | 126,635 | 52.0% | 52.9% | 54.7% | +0.0027 | 40.7% |
| Rank Q1 (bottom predictions) | 108,944 | 51.1% | 52.0% | 53.3% | +0.0048 | 0.0% |

## 3. Best Performing Contexts (Top 25 combinations)

| Context | N | HR 5d | HR 10d | HR 20d | Expectancy | Rank Hit |
|---|---|---|---|---|---|---|
| regime=range + conviction=VERY_HIGH | 7,019 | 60.2% | 63.0% | 64.2% | +0.0139 | 0.0% |
| regime=bear + conviction=VERY_HIGH | 12,206 | 59.9% | 64.7% | 69.8% | +0.0084 | 0.7% |
| regime=bear + conviction=HIGH | 27,526 | 59.0% | 62.1% | 63.5% | +0.0131 | 4.1% |
| conviction=VERY_HIGH + rank_q=5 | 13,492 | 58.5% | 58.6% | 61.7% | +0.0056 | 43.9% |
| regime=bear + rank_q=3 | 20,141 | 58.2% | 62.4% | 67.1% | +0.0103 | 0.0% |
| regime=bear + rank_q=4 | 13,862 | 57.8% | 59.8% | 58.9% | +0.0101 | 0.0% |
| regime=bear + above_sma200=below | 46,973 | 57.4% | 61.0% | 63.1% | +0.0105 | 3.8% |
| regime=range + conviction=HIGH | 89,457 | 56.8% | 58.7% | 59.1% | +0.0179 | 1.8% |
| regime=range + above_sma200=above | 75,226 | 56.6% | 57.1% | 57.8% | +0.0050 | 8.6% |
| quality=2 + conviction=HIGH | 13,366 | 56.3% | 57.4% | 58.0% | +0.0096 | 1.8% |
| quality=1 + conviction=HIGH | 17,876 | 56.0% | 56.2% | 55.9% | +0.0079 | 1.7% |
| conviction=VERY_HIGH + rank_q=1 | 5,096 | 55.6% | 58.8% | 60.3% | +0.0023 | 0.0% |
| above_sma200=below + conviction=VERY_HIGH | 29,726 | 55.3% | 58.0% | 60.7% | +0.0048 | 0.8% |
| vix=moderate + rank_q=4 | 78,100 | 55.3% | 55.8% | 55.5% | +0.0041 | 0.0% |
| vix=moderate + conviction=VERY_HIGH | 83,705 | 55.2% | 56.4% | 58.1% | +0.0039 | 3.2% |
| vix=low + conviction=VERY_HIGH | 69,790 | 55.1% | 56.8% | 58.4% | +0.0020 | 3.7% |
| regime=range + rank_q=4 | 51,769 | 55.1% | 54.1% | 52.7% | +0.0080 | 0.0% |
| conviction=VERY_HIGH + rank_q=3 | 58,625 | 54.9% | 57.2% | 58.6% | +0.0033 | 0.0% |
| regime=bear + vix=high | 25,780 | 54.6% | 59.6% | 62.4% | +0.0161 | 6.2% |
| conviction=HIGH + rank_q=3 | 87,752 | 54.6% | 55.9% | 56.8% | +0.0159 | 0.0% |
| above_sma200=below + rank_q=4 | 35,737 | 54.5% | 55.8% | 55.0% | +0.0086 | 0.0% |
| vix=moderate + conviction=HIGH | 123,184 | 54.5% | 55.1% | 56.5% | +0.0037 | 6.5% |
| conviction=HIGH + rank_q=4 | 57,561 | 54.5% | 55.6% | 56.1% | +0.0066 | 0.0% |
| above_sma200=below + conviction=HIGH | 78,604 | 54.4% | 56.5% | 58.3% | +0.0080 | 5.3% |
| above_sma200=below + rank_q=3 | 40,605 | 54.2% | 57.1% | 61.1% | +0.0073 | 0.0% |

## 4. Worst Performing Contexts (Bottom 25 combinations)

| Context | N | HR 5d | HR 10d | HR 20d | Expectancy | Rank Hit |
|---|---|---|---|---|---|---|
| regime=bear + conviction=LOW | 8,332 | 39.9% | 34.3% | 34.0% | +0.0093 | 20.8% |
| quality=4 + rank_q=2 | 35,799 | 43.1% | 42.5% | 40.3% | -0.0034 | 0.0% |
| jarvis=red + rank_q=1 | 13,814 | 43.7% | 44.4% | 48.3% | +0.0090 | 0.0% |
| quality=4 + above_sma200=below | 30,280 | 44.3% | 44.7% | 45.8% | +0.0084 | 7.3% |
| jarvis=green + rank_q=1 | 9,577 | 44.3% | 44.2% | 49.7% | +0.0003 | 0.0% |
| quality=3 + rank_q=2 | 17,882 | 44.4% | 43.6% | 41.5% | -0.0033 | 0.0% |
| regime=bear + quality=1 | 1,966 | 44.5% | 48.2% | 52.5% | +0.0234 | 10.6% |
| quality=4 + conviction=MODERATE | 80,728 | 44.7% | 44.7% | 44.9% | +0.0015 | 4.1% |
| jarvis=green + above_sma200=below | 28,471 | 44.9% | 45.5% | 46.9% | +0.0069 | 7.5% |
| jarvis=green + regime=bear | 4,609 | 45.0% | 50.0% | 54.7% | +0.0358 | 9.0% |
| quality=3 + rank_q=1 | 9,188 | 45.0% | 45.8% | 48.6% | +0.0109 | 0.0% |
| jarvis=green + conviction=LOW | 6,191 | 45.4% | 42.7% | 46.4% | +0.0095 | 11.8% |
| quality=1 + rank_q=1 | 4,899 | 45.5% | 47.0% | 53.0% | +0.0021 | 0.0% |
| vix=high + quality=4 | 89,199 | 45.5% | 45.8% | 45.9% | +0.0150 | 4.7% |
| quality=3 + above_sma200=below | 17,111 | 45.7% | 46.6% | 47.6% | +0.0092 | 7.0% |
| quality=3 + conviction=MODERATE | 42,059 | 45.7% | 45.6% | 45.4% | +0.0038 | 4.4% |
| regime=bull + quality=4 | 54,558 | 45.7% | 46.4% | 46.6% | +0.0031 | 4.6% |
| vix=high + rank_q=2 | 56,978 | 45.8% | 46.0% | 45.4% | -0.0009 | 0.0% |
| regime=bull + quality=3 | 31,585 | 45.8% | 46.1% | 46.3% | +0.0031 | 4.8% |
| quality=4 + rank_q=1 | 14,639 | 45.9% | 46.8% | 50.8% | +0.0088 | 0.0% |
| above_sma200=above + conviction=LOW | 13,766 | 46.0% | 45.7% | 49.8% | +0.0065 | 16.0% |
| vix=high + conviction=MODERATE | 106,361 | 46.3% | 46.3% | 46.2% | +0.0039 | 5.8% |
| jarvis=red + conviction=VERY_HIGH | 24,256 | 46.4% | 47.6% | 48.6% | +0.0013 | 0.0% |
| quality=4 + conviction=VERY_HIGH | 16,020 | 46.6% | 48.5% | 49.1% | +0.0049 | 0.0% |
| regime=bull + vix=high | 94,526 | 46.6% | 46.4% | 47.1% | +0.0039 | 6.5% |

## 5. Key Findings

### 5.1 Where does Atlas perform best?

- **Conviction VERY_HIGH**: HR=54.2%, n=192,007, exp=+0.0035
- **Bear regime**: HR=54.0%, n=72,795, exp=+0.0088
- **Conviction HIGH**: HR=53.9%, n=304,434, exp=+0.0077
- **ML moderate (0.60-0.80)**: HR=53.3%, n=192,561, exp=+0.0046
- **VIX moderate**: HR=53.1%, n=339,121, exp=+0.0025

### 5.2 Where does Atlas perform worst?

- **Quality Tier 4**: HR=47.2%, n=158,811, exp=+0.0096
- **Confluence < 2 (5-comp)**: HR=47.9%, n=77,183, exp=+0.0030
- **Quality Tier 3**: HR=48.0%, n=83,162, exp=+0.0045
- **Jarvis red**: HR=48.4%, n=154,631, exp=+0.0063
- **Conviction LOW**: HR=48.6%, n=46,774, exp=+0.0034

### 5.3 Which contexts reliably increase accuracy?

- **Conviction VERY_HIGH**: +2.2% above baseline (HR=54.2%, n=192,007)
- **Bear regime**: +2.0% above baseline (HR=54.0%, n=72,795)

### 5.4 Which contexts reliably decrease accuracy?

- **Quality Tier 4**: -4.8% below baseline (HR=47.2%, n=158,811)
- **Confluence < 2 (5-comp)**: -4.1% below baseline (HR=47.9%, n=77,183)
- **Quality Tier 3**: -4.0% below baseline (HR=48.0%, n=83,162)
- **Jarvis red**: -3.5% below baseline (HR=48.4%, n=154,631)
- **Conviction LOW**: -3.4% below baseline (HR=48.6%, n=46,774)
- **Conviction MODERATE**: -2.8% below baseline (HR=49.2%, n=304,118)
- **Jarvis green**: -2.7% below baseline (HR=49.2%, n=111,934)
- **VIX high**: -2.7% below baseline (HR=49.3%, n=239,610)

### 5.5 Recommended confidence adjustments

Contexts where HR significantly exceeds baseline — candidates for positive confidence multipliers:

- **regime=range + conviction=VERY_HIGH**: +8.2% above baseline, n=7,019
- **regime=bear + conviction=VERY_HIGH**: +7.9% above baseline, n=12,206
- **regime=bear + conviction=HIGH**: +7.0% above baseline, n=27,526
- **conviction=VERY_HIGH + rank_q=5**: +6.5% above baseline, n=13,492
- **regime=bear + rank_q=3**: +6.2% above baseline, n=20,141
- **regime=bear + rank_q=4**: +5.9% above baseline, n=13,862
- **regime=bear + above_sma200=below**: +5.4% above baseline, n=46,973
- **regime=range + conviction=HIGH**: +4.9% above baseline, n=89,457
- **regime=range + above_sma200=above**: +4.6% above baseline, n=75,226
- **quality=2 + conviction=HIGH**: +4.3% above baseline, n=13,366

Contexts where HR significantly underperforms — candidates for confidence reduction or exclusion:

- **regime=bear + conviction=LOW**: -12.0% below baseline, n=8,332
- **quality=4 + rank_q=2**: -8.9% below baseline, n=35,799
- **jarvis=red + rank_q=1**: -8.2% below baseline, n=13,814
- **quality=4 + above_sma200=below**: -7.7% below baseline, n=30,280
- **jarvis=green + rank_q=1**: -7.7% below baseline, n=9,577
- **quality=3 + rank_q=2**: -7.6% below baseline, n=17,882
- **regime=bear + quality=1**: -7.5% below baseline, n=1,966
- **quality=4 + conviction=MODERATE**: -7.2% below baseline, n=80,728
- **jarvis=green + above_sma200=below**: -7.0% below baseline, n=28,471
- **jarvis=green + regime=bear**: -7.0% below baseline, n=4,609

## 6. Yearly Accuracy Stability

| Year | N | HR 5d | HR 10d | HR 20d | Expectancy |
|---|---|---|---|---|---|
| 2015 | 43,073 | 51.7% | 51.2% | 49.3% | +0.0003 |
| 2016 | 43,446 | 55.2% | 57.4% | 61.5% | +0.0042 |
| 2017 | 44,072 | 58.7% | 61.5% | 66.2% | +0.0046 |
| 2018 | 43,748 | 52.6% | 52.4% | 51.1% | -0.0005 |
| 2019 | 45,184 | 59.3% | 62.3% | 65.0% | +0.0071 |
| 2020 | 46,094 | 55.8% | 57.9% | 60.6% | +0.0052 |
| 2021 | 46,582 | 56.4% | 58.3% | 59.8% | +0.0052 |
| 2022 | 43,076 | 49.9% | 49.7% | 47.6% | -0.0005 |
| 2023 | 46,260 | 52.8% | 53.6% | 54.0% | +0.0031 |
| 2024 | 47,377 | 52.7% | 53.6% | 55.7% | +0.0019 |
| 2025 | 270,894 | 49.8% | 50.6% | 50.9% | +0.0056 |
| 2026 | 127,527 | 47.5% | 47.2% | 47.3% | +0.0061 |
