# 5-minute confirmation of daily mean-reversion trades (2023+)

Tickers: AAPL, NVDA, MSFT, GOOGL, AMZN, META, TSLA, JPM, XOM, WMT | hold H=5d | entry score>train p85 | cost 5.0bps. Daily signal at close of D, acted on session D1; 5m confirmation = D1 reclaims VWAP intraday.

**Signals: 312  |  5m-confirmed: 151 (48%)**

| variant                                      |   n |   mean% |   median% |   win% |    t |
|:---------------------------------------------|----:|--------:|----------:|-------:|-----:|
| A. all daily signals                         | 312 |   1.413 |     1.242 |   59   | 4.58 |
| B. 5m-CONFIRMED (bounce held: closed > VWAP) | 151 |   2.285 |     2.115 |   64.9 | 4.98 |
| C. 5m-FAILED (closed < VWAP, falling knife)  | 159 |   0.565 |     0.517 |   53.5 | 1.39 |

_If B (confirmed) > A (daily-only) > C (unconfirmed), the 5m layer corroborates and improves the daily setup._