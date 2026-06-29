# MSFT edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.085%, 3days:+0.252%, 5days:+0.418%, 10days:+0.832%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| hammer            | long  |  78 |   71.8 |  1.1293 |  0.7112 |  2.64 |
| bullish_harami    | long  | 110 |   65.5 |  0.7749 |  0.3568 |  2.32 |
| tweezer_bottom    | long  | 184 |   61.4 |  0.5725 |  0.1544 |  2.25 |
| inverted_hammer   | long  |  58 |   67.2 |  1.0613 |  0.6432 |  2.19 |
| bull_flag         | long  |  30 |   63.3 |  0.4569 |  0.0388 |  1.07 |
| bearish_harami    | short | 170 |   47.6 |  0.2405 |  0.6586 |  0.96 |
| evening_star      | short |  41 |   51.2 |  0.3181 |  0.7362 |  0.45 |
| bullish_engulfing | long  | 133 |   58.6 |  0.1266 | -0.2915 |  0.45 |
| double_bottom     | long  | 130 |   56.9 |  0.0366 | -0.3816 |  0.13 |
| marubozu          | long  |  73 |   50.7 |  0.0144 | -0.4037 |  0.04 |
| morning_star      | long  |  41 |   56.1 | -0.1805 | -0.5987 | -0.38 |
| hanging_man       | short | 139 |   40.3 | -0.2897 |  0.1284 | -0.99 |
| shooting_star     | short |  85 |   49.4 | -0.3591 |  0.059  | -1.06 |
| double_top        | short |  95 |   37.9 | -0.6261 | -0.208  | -1.63 |
| marubozu          | short |  48 |   39.6 | -1.0606 | -0.6425 | -2.04 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -1.1181 |   47.4 | -1.4045 |   42.1 | -1.9722 |   42.1 |   0.0569 |    57.9 |
| after BIG DOWN bar |  19 |  1.1967 |   42.1 |  1.2219 |   52.6 |  1.5224 |   63.2 |   2.5045 |    57.9 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  36 |         -1.604 | 44.444 |
| mid(3-4) |  34 |         -1.838 | 29.412 |
| high(5+) |   6 |         -0.809 | 66.667 |
