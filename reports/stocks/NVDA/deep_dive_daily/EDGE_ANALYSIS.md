# NVDA edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.202%, 3days:+0.602%, 5days:+1.006%, 10days:+2.024%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| bullish_engulfing | long  | 129 |   62   |  0.9289 | -0.0774 |  2.14 |
| inverted_hammer   | long  |  54 |   66.7 |  1.6688 |  0.6625 |  1.9  |
| marubozu          | long  |  87 |   60.9 |  1.0478 |  0.0414 |  1.64 |
| piercing          | long  |  25 |   68   |  1.6548 |  0.6485 |  1.56 |
| tweezer_bottom    | long  | 110 |   58.2 |  0.8532 | -0.1532 |  1.55 |
| bullish_harami    | long  | 129 |   60.5 |  0.6584 | -0.3479 |  1.22 |
| double_bottom     | long  |  90 |   46.7 |  0.6945 | -0.3119 |  1.2  |
| bull_flag         | long  |  67 |   59.7 |  0.471  | -0.5353 |  0.98 |
| morning_star      | long  |  38 |   50   |  0.4701 | -0.5363 |  0.42 |
| hammer            | long  |  58 |   55.2 |  0.2196 | -0.7867 |  0.27 |
| shooting_star     | short |  89 |   51.7 |  0.0399 |  1.0462 |  0.07 |
| bearish_harami    | short | 160 |   43.1 | -0.3505 |  0.6559 | -0.78 |
| evening_star      | short |  44 |   45.5 | -0.8265 |  0.1799 | -0.9  |
| hanging_man       | short | 138 |   47.1 | -0.6783 |  0.328  | -1.43 |
| marubozu          | short |  61 |   37.7 | -1.6124 | -0.6061 | -1.93 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -0.8437 |   42.1 |  1.742  |   63.2 |  3.7185 |   73.7 |   4.469  |    63.2 |
| after BIG DOWN bar |  19 |  1.9825 |   63.2 |  1.0289 |   47.4 |  1.2235 |   57.9 |   5.0995 |    78.9 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |     win |
|:---------|----:|---------------:|--------:|
| low(0-2) |  37 |          1.28  |  62.162 |
| mid(3-4) |  36 |         -2.06  |  41.667 |
| high(5+) |   3 |          4.531 | 100     |
