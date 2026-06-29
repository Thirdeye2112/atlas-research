# AMZN edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.106%, 3days:+0.318%, 5days:+0.529%, 10days:+1.055%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| bullish_harami    | long  | 113 |   61.1 |  1.2601 |  0.7309 |  3.53 |
| double_bottom     | long  | 120 |   60.8 |  1.2559 |  0.7266 |  3.14 |
| hammer            | long  |  79 |   64.6 |  1.6488 |  1.1195 |  2.97 |
| hs_bottom         | long  |  32 |   68.8 |  1.5241 |  0.9949 |  2.21 |
| morning_star      | long  |  31 |   71   |  1.4603 |  0.931  |  2.06 |
| bullish_engulfing | long  | 105 |   57.1 |  0.5651 |  0.0359 |  1.21 |
| bull_flag         | long  |  57 |   63.2 |  0.4922 | -0.037  |  1.08 |
| hs_top            | short |  28 |   57.1 |  0.7179 |  1.2471 |  0.89 |
| inverted_hammer   | long  |  41 |   43.9 |  0.5539 |  0.0246 |  0.81 |
| tweezer_bottom    | long  | 117 |   53.8 |  0.2716 | -0.2576 |  0.72 |
| bearish_harami    | short | 145 |   49.7 |  0.0628 |  0.5921 |  0.18 |
| marubozu          | long  |  73 |   52.1 |  0.0602 | -0.4691 |  0.13 |
| evening_star      | short |  34 |   44.1 |  0.0756 |  0.6049 |  0.13 |
| double_top        | short |  70 |   51.4 | -0.0592 |  0.47   | -0.1  |
| hanging_man       | short | 103 |   49.5 | -0.1254 |  0.4038 | -0.32 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -0.3969 |   42.1 | -0.762  |   42.1 | -0.4714 |   42.1 |   0.688  |    52.6 |
| after BIG DOWN bar |  19 |  0.6364 |   42.1 |  0.6259 |   47.4 |  1.7072 |   63.2 |   4.1383 |    68.4 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  37 |         -1.003 | 40.541 |
| mid(3-4) |  31 |         -0.032 | 45.161 |
| high(5+) |   8 |         -3.743 | 25     |
