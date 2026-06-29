# META edge analysis (daily)

Bars 3,545 (2012-05-18->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.106%, 3days:+0.327%, 5days:+0.547%, 10days:+1.110%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| hammer            | long  |  59 |   66.1 |  1.7026 |  1.1559 |  2.38 |
| inverted_hammer   | long  |  53 |   75.5 |  1.4495 |  0.9028 |  1.89 |
| bull_flag         | long  |  51 |   64.7 |  1.1024 |  0.5558 |  1.7  |
| evening_star      | short |  41 |   51.2 |  0.5032 |  1.0499 |  0.9  |
| bullish_harami    | long  | 118 |   58.5 |  0.3927 | -0.154  |  0.75 |
| bullish_engulfing | long  | 131 |   58.8 |  0.203  | -0.3437 |  0.46 |
| hs_top            | short |  25 |   56   |  0.228  |  0.7747 |  0.26 |
| double_bottom     | long  |  96 |   52.1 |  0.1016 | -0.4451 |  0.23 |
| tweezer_bottom    | long  | 113 |   51.3 |  0.11   | -0.4367 |  0.23 |
| morning_star      | long  |  36 |   55.6 |  0.0185 | -0.5282 |  0.03 |
| bear_flag         | short |  27 |   48.1 | -0.0102 |  0.5365 | -0.01 |
| marubozu          | long  |  77 |   53.2 | -0.1095 | -0.6562 | -0.24 |
| dark_cloud_cover  | short |  36 |   44.4 | -0.4772 |  0.0695 | -0.56 |
| hanging_man       | short | 100 |   48   | -0.3924 |  0.1543 | -1.06 |
| shooting_star     | short |  87 |   39.1 | -0.8472 | -0.3005 | -1.29 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  18 | -1.4793 |   38.9 | -1.0858 |   44.4 | -1.8554 |   33.3 |   0.0239 |    44.4 |
| after BIG DOWN bar |  18 | -1.1136 |   27.8 |  0.7143 |   55.6 | -0.3145 |   55.6 |   1.3411 |    61.1 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  30 |         -2.45  | 36.667 |
| mid(3-4) |  31 |         -0.312 | 45.161 |
| high(5+) |   8 |          0.587 | 50     |
