# Embargoed walk-forward — mean-reversion signal across the basket

Tickers: AAPL, NVDA, MSFT, GOOGL, AMZN, META, TSLA, JPM, XOM, WMT  |  hold H=5d  |  entry: reversion score in top 15% (threshold fit on TRAIN)  |  cost 5.0bps round-trip  |  5 expanding folds, 5-day embargo.

## Pooled OOS (net of costs)

| strategy                            |    n |   mean_net% |   median% |   win% |    t |   baseline% |   excess% |   ann_sharpe~ |
|:------------------------------------|-----:|------------:|----------:|-------:|-----:|------------:|----------:|--------------:|
| mean-reversion LONG (oversold)      | 1492 |       0.696 |     0.683 |   57   | 4.49 |       0.477 |     0.219 |          1.85 |
| inverse: momentum LONG (overbought) | 1559 |       0.432 |     0.353 |   55.2 | 3.73 |       0.477 |    -0.045 |          1.5  |
| baseline: any H-day hold            | 6210 |       0.477 |     0.457 |   55.7 | 7.6  |       0.477 |     0     |          1.53 |

## Per stock — does the reversion edge generalize OOS?

| ticker   |   n_trades |   mean_net% |   win% |   excess% |
|:---------|-----------:|------------:|-------:|----------:|
| MSFT     |        148 |       1.021 |   61.5 |     0.647 |
| TSLA     |        173 |       1.372 |   54.9 |     0.478 |
| META     |        125 |       0.753 |   57.6 |     0.321 |
| AAPL     |        120 |       0.773 |   56.7 |     0.315 |
| JPM      |        130 |       0.561 |   62.3 |     0.266 |
| XOM      |        186 |       0.293 |   52.2 |     0.216 |
| GOOGL    |        162 |       0.602 |   58.6 |     0.179 |
| WMT      |        164 |       0.404 |   56.1 |     0.178 |
| NVDA     |        131 |       1.144 |   59.5 |    -0.007 |
| AMZN     |        153 |       0.146 |   52.9 |    -0.296 |

## Stability by test window

| window           |   trades |   mean_net |     win |
|:-----------------|---------:|-----------:|--------:|
| 2014-01->2016-07 |      276 |      1.083 |  61.078 |
| 2014-10->2017-02 |        6 |      3.602 | 100     |
| 2016-07->2018-12 |      192 |      0.415 |  59.3   |
| 2017-02->2019-06 |       23 |      0.747 |  60.9   |
| 2018-12->2021-06 |      269 |      1.409 |  64.122 |
| 2019-06->2021-10 |       23 |      1.114 |  56.5   |
| 2021-06->2023-12 |      388 |      0.29  |  54.789 |
| 2021-10->2024-02 |       45 |      0.527 |  55.6   |
| 2023-12->2026-06 |      242 |      1.09  |  56.589 |
| 2024-02->2026-06 |       28 |      0.213 |  50     |

## Cost sensitivity (pooled reversion long)

|   cost_bps |   mean_net% |   win% |
|-----------:|------------:|-------:|
|          0 |       0.746 |   57.4 |
|          5 |       0.696 |   57   |
|         10 |       0.646 |   56.2 |
|         20 |       0.546 |   55.2 |

_Note: long-only; the inverse (overbought) bucket is shown for contrast. Non-overlapping trades, close-to-close, in-sample standardization is per-fold train-only._