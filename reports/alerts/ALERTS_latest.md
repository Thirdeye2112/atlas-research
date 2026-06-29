# Trade alerts — 2026-06-25 (act next session on 5m VWAP reclaim)

90 setups fired across 75 names (500 universe), all methods. Long-only; ranked by conviction (historical base-rate edge x win-rate + mr_score + trend + confluence).

## Top 30 alerts

| ticker   | method         | name             | direction   |   mr_score |   confluence_n |   above_ema200 |   base_n |   base_avg_fwd5 |   base_win5 |   conviction |
|:---------|:---------------|:-----------------|:------------|-----------:|---------------:|---------------:|---------:|----------------:|------------:|-------------:|
| AAPL     | move           | significant_drop | long        |    1.52161 |              5 |              1 |    31377 |           9.835 |        51.9 |       11.972 |
| CTSH     | move           | significant_drop | long        |    3.25748 |              3 |              0 |    31377 |           9.835 |        51.9 |       11.967 |
| ROST     | move           | significant_drop | long        |    1.37521 |              4 |              1 |    31377 |           9.835 |        51.9 |       11.764 |
| MCD      | move           | significant_drop | long        |    1.90726 |              4 |              0 |    31377 |           9.835 |        51.9 |       11.576 |
| MSCI     | move           | significant_drop | long        |    1.78972 |              4 |              0 |    31377 |           9.835 |        51.9 |       11.529 |
| ACN      | mean_reversion | mr_oversold      | long        |    3.5979  |              4 |              0 |   314770 |           3.263 |        53   |        5.499 |
| AAPL     | mean_reversion | mr_oversold      | long        |    1.52161 |              5 |              1 |   314770 |           3.263 |        53   |        5.219 |
| CTSH     | mean_reversion | mr_oversold      | long        |    3.25748 |              3 |              0 |   314770 |           3.263 |        53   |        5.213 |
| ORCL     | mean_reversion | mr_oversold      | long        |    2.84948 |              3 |              0 |   314770 |           3.263 |        53   |        5.05  |
| MSFT     | mean_reversion | mr_oversold      | long        |    2.41337 |              4 |              0 |   314770 |           3.263 |        53   |        5.026 |
| ROST     | mean_reversion | mr_oversold      | long        |    1.37521 |              4 |              1 |   314770 |           3.263 |        53   |        5.01  |
| CME      | mean_reversion | mr_oversold      | long        |    2.70668 |              3 |              0 |   314770 |           3.263 |        53   |        4.993 |
| GOOGL    | mean_reversion | mr_oversold      | long        |    1.25806 |              4 |              1 |   314770 |           3.263 |        53   |        4.963 |
| NVDA     | mean_reversion | mr_oversold      | long        |    1.05657 |              4 |              1 |   314770 |           3.263 |        53   |        4.883 |
| INTU     | mean_reversion | mr_oversold      | long        |    2.76114 |              2 |              0 |   314770 |           3.263 |        53   |        4.865 |
| MCD      | mean_reversion | mr_oversold      | long        |    1.90726 |              4 |              0 |   314770 |           3.263 |        53   |        4.823 |
| MSCI     | mean_reversion | mr_oversold      | long        |    1.78972 |              4 |              0 |   314770 |           3.263 |        53   |        4.776 |
| QCOM     | mean_reversion | mr_oversold      | long        |    1.12453 |              3 |              1 |   314770 |           3.263 |        53   |        4.76  |
| CDNS     | mean_reversion | mr_oversold      | long        |    1.08094 |              3 |              1 |   314770 |           3.263 |        53   |        4.743 |
| KLAC     | mean_reversion | mr_oversold      | long        |    1.92287 |              3 |              0 |   314770 |           3.263 |        53   |        4.679 |
| PEP      | mean_reversion | mr_oversold      | long        |    1.49839 |              4 |              0 |   314770 |           3.263 |        53   |        4.66  |
| ADBE     | mean_reversion | mr_oversold      | long        |    2.23728 |              2 |              0 |   314770 |           3.263 |        53   |        4.655 |
| AMZN     | mean_reversion | mr_oversold      | long        |    1.46664 |              4 |              0 |   314770 |           3.263 |        53   |        4.647 |
| AVGO     | mean_reversion | mr_oversold      | long        |    1.19983 |              2 |              1 |   314770 |           3.263 |        53   |        4.64  |
| BLK      | mean_reversion | mr_oversold      | long        |    1.43511 |              4 |              0 |   314770 |           3.263 |        53   |        4.634 |
| SPGI     | mean_reversion | mr_oversold      | long        |    1.73522 |              3 |              0 |   314770 |           3.263 |        53   |        4.604 |
| NKE      | mean_reversion | mr_oversold      | long        |    1.71563 |              3 |              0 |   314770 |           3.263 |        53   |        4.596 |
| CRM      | mean_reversion | mr_oversold      | long        |    1.91937 |              2 |              0 |   314770 |           3.263 |        53   |        4.528 |
| XLC      | mean_reversion | mr_oversold      | long        |    1.48692 |              3 |              0 |   314770 |           3.263 |        53   |        4.505 |
| NFLX     | mean_reversion | mr_oversold      | long        |    1.42842 |              3 |              0 |   314770 |           3.263 |        53   |        4.482 |

## By method

| method         |   n |   avg_conv |
|:---------------|----:|-----------:|
| candlestick    |  27 |       1.2  |
| mean_reversion |  47 |       4.56 |
| move           |   5 |      11.76 |
| structure      |  11 |       0.44 |

_Each alert carries its mined base rate (base_n trades, base_avg_fwd5 %, base_win5 %). Confirm intraday next session: enter only if price reclaims & closes above VWAP._