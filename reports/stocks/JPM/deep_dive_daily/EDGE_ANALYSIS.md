# JPM edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.070%, 3days:+0.208%, 5days:+0.344%, 10days:+0.685%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| double_bottom     | long  | 125 |   60   |  0.7158 |  0.3719 |  2.63 |
| tweezer_bottom    | long  | 143 |   58   |  0.7446 |  0.4007 |  2.6  |
| inverted_hammer   | long  |  71 |   62   |  1.2428 |  0.899  |  2.58 |
| hs_bottom         | long  |  26 |   65.4 |  1.3771 |  1.0332 |  2.55 |
| piercing          | long  |  30 |   66.7 |  1.6949 |  1.351  |  2.03 |
| hs_top            | short |  26 |   57.7 |  1.1317 |  1.4756 |  1.47 |
| bullish_engulfing | long  | 132 |   53   |  0.1532 | -0.1907 |  0.49 |
| bullish_harami    | long  | 108 |   57.4 |  0.1801 | -0.1637 |  0.41 |
| morning_star      | long  |  40 |   55   |  0.1468 | -0.1971 |  0.31 |
| bearish_harami    | short | 159 |   42.1 |  0.0653 |  0.4092 |  0.25 |
| bull_flag         | long  |  40 |   50   | -0.0279 | -0.3718 | -0.07 |
| hammer            | long  |  75 |   53.3 | -0.222  | -0.5659 | -0.44 |
| shooting_star     | short |  98 |   50   | -0.1891 |  0.1547 | -0.56 |
| double_top        | short | 110 |   37.3 | -0.2105 |  0.1333 | -0.62 |
| marubozu          | short |  54 |   44.4 | -0.4142 | -0.0704 | -0.77 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -1.752  |   42.1 | -0.9213 |   52.6 | -0.3707 |   52.6 |   1.4563 |    57.9 |
| after BIG DOWN bar |  19 |  2.2148 |   73.7 |  3.8954 |   73.7 |  3.8106 |   78.9 |   1.9251 |    63.2 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  36 |         -0.805 | 44.444 |
| mid(3-4) |  31 |         -1.3   | 45.161 |
| high(5+) |   9 |         -2.908 | 33.333 |
