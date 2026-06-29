# Cross-stock summary — do the setups generalize?

Tickers: AAPL, NVDA, MSFT, GOOGL, AMZN, META, TSLA, JPM, XOM, WMT  |  horizon 5 days  |  in-sample, no costs.

## Setup generalization (daily, +5d edge over drift)

`works_in` = # of stocks where the setup had **positive edge AND t>1**.

| setup             | dir   |   stocks |   works_in/_10 |   mean_win |   mean_edge |   mean_t |   mean_n |
|:------------------|:------|---------:|---------------:|-----------:|------------:|---------:|---------:|
| inverted_hammer   | long  |       10 |              7 |       61.9 |       0.461 |     1.69 |       60 |
| hs_bottom         | long  |        5 |              5 |       64.3 |       0.648 |     1.81 |       30 |
| hammer            | long  |       10 |              5 |       58.7 |       0.13  |     1.17 |       73 |
| bullish_harami    | long  |       10 |              5 |       59.7 |       0.128 |     1.81 |      118 |
| bull_flag         | long  |       10 |              4 |       59.4 |       0.151 |     1.14 |       46 |
| double_bottom     | long  |       10 |              4 |       56.6 |       0.058 |     1.35 |      111 |
| bullish_engulfing | long  |       10 |              4 |       56.9 |      -0.092 |     1.22 |      133 |
| tweezer_bottom    | long  |       10 |              4 |       54.6 |      -0.156 |     1.17 |      154 |
| marubozu          | long  |       10 |              2 |       53.6 |      -0.403 |     0.31 |       74 |
| hs_top            | short |        5 |              1 |       55.5 |       0.872 |     0.61 |       27 |
| tweezer_top       | short |       10 |              1 |       45.9 |       0.271 |    -1.64 |      299 |
| morning_star      | long  |       10 |              1 |       53.4 |      -0.291 |     0.36 |       37 |
| hanging_man       | short |       10 |              0 |       44.8 |       0.237 |    -0.74 |      110 |
| bearish_harami    | short |       10 |              0 |       45   |       0.205 |    -0.96 |      154 |
| evening_star      | short |        9 |              0 |       47.1 |       0.055 |    -0.71 |       41 |
| double_top        | short |       10 |              0 |       44.2 |      -0.029 |    -1.25 |       93 |
| shooting_star     | short |       10 |              0 |       44.3 |      -0.045 |    -1.4  |       91 |
| dark_cloud_cover  | short |       10 |              0 |       43.4 |      -0.156 |    -0.85 |       33 |
| bearish_engulfing | short |       10 |              0 |       42.7 |      -0.371 |    -2.5  |      149 |
| marubozu          | short |       10 |              0 |       40.7 |      -0.691 |    -1.85 |       52 |

### Per-ticker edge (+5d %) for the top setups

|                               |   AAPL |   AMZN |   GOOGL |   JPM |   META |   MSFT |   NVDA |   TSLA |    WMT |   XOM |
|:------------------------------|-------:|-------:|--------:|------:|-------:|-------:|-------:|-------:|-------:|------:|
| ('bull_flag', 'long')         |   1.12 |  -0.04 |   -0.27 | -0.37 |   0.56 |   0.04 |  -0.54 |   0.99 |  -0.24 |  0.26 |
| ('bullish_engulfing', 'long') |  -0.33 |   0.04 |    0.12 | -0.19 |  -0.34 |  -0.29 |  -0.08 |  -0.26 |   0.06 |  0.36 |
| ('bullish_harami', 'long')    |   0.54 |   0.73 |    0.18 | -0.16 |  -0.15 |   0.36 |  -0.35 |  -0.59 |   0.59 |  0.14 |
| ('double_bottom', 'long')     |   0.42 |   0.73 |   -0.15 |  0.37 |  -0.45 |  -0.38 |  -0.31 |   0.92 |  -0.32 | -0.25 |
| ('hammer', 'long')            |  -0.42 |   1.12 |    0.41 | -0.57 |   1.16 |   0.71 |  -0.79 |  -0.09 |   0.33 | -0.57 |
| ('hs_bottom', 'long')         |   0.6  |   0.99 |    0.14 |  1.03 | nan    | nan    | nan    | nan    | nan    |  0.48 |
| ('inverted_hammer', 'long')   |   0.73 |   0.02 |    0.16 |  0.9  |   0.9  |   0.64 |   0.66 |  -0.24 |   0.62 |  0.2  |
| ('tweezer_bottom', 'long')    |  -0.58 |  -0.26 |    0.18 |  0.4  |  -0.44 |   0.15 |  -0.15 |  -0.76 |   0.13 | -0.23 |

## Univariate IC consensus across stocks

Features whose forward-return correlation is **consistent across names** (agree = # of stocks sharing the dominant sign).

**Most bullish (consensus):**

| feature        |   mean_ic |   pos_stocks |   neg_stocks |   stocks |   agree |
|:---------------|----------:|-------------:|-------------:|---------:|--------:|
| rsi_oversold   |    0.044  |           10 |            0 |       10 |      10 |
| atr_pct        |    0.0335 |            9 |            1 |       10 |       9 |
| ema_stack_bear |    0.0279 |            8 |            2 |       10 |       8 |
| bb_break_dn    |    0.0258 |           10 |            0 |       10 |      10 |
| range_pct      |    0.0236 |            9 |            1 |       10 |       9 |
| upper_wick     |    0.0197 |            9 |            1 |       10 |       9 |
| bb_width       |    0.0186 |            7 |            3 |       10 |       7 |
| body_pct       |    0.0097 |            8 |            2 |       10 |       8 |

**Most bearish (consensus):**

| feature     |   mean_ic |   pos_stocks |   neg_stocks |   stocks |   agree |
|:------------|----------:|-------------:|-------------:|---------:|--------:|
| williams_r  |   -0.0338 |            2 |            8 |       10 |       8 |
| stoch_k     |   -0.0338 |            2 |            8 |       10 |       8 |
| ema9_slope  |   -0.0335 |            2 |            8 |       10 |       8 |
| dist_ema9   |   -0.0334 |            2 |            8 |       10 |       8 |
| dist_ema200 |   -0.0326 |            1 |            9 |       10 |       9 |
| dist_ema20  |   -0.0321 |            2 |            8 |       10 |       8 |
| mfi         |   -0.032  |            3 |            7 |       10 |       7 |
| rsi         |   -0.0317 |            2 |            8 |       10 |       8 |
