# JPM edge analysis (intraday)

Bars 105,402 (2021-01-04->2026-06-18). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.003%, 6bars:+0.006%, 12bars:+0.013%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| hammer               | long  |  2757 |   50.8 |  0.0167 |  0.0103 |  1.87 |
| double_bottom        | long  |  5565 |   50.5 |  0.0122 |  0.0058 |  1.81 |
| piercing             | long  |   961 |   51.4 |  0.0221 |  0.0157 |  1.79 |
| tweezer_bottom       | long  | 23510 |   50.7 |  0.0028 | -0.0036 |  0.94 |
| marubozu             | long  | 12733 |   50   |  0.0025 | -0.0039 |  0.78 |
| three_white_soldiers | long  |   405 |   50.6 |  0.0117 |  0.0053 |  0.57 |
| bullish_harami       | long  |  3658 |   51.4 |  0.0037 | -0.0027 |  0.51 |
| bullish_engulfing    | long  |  4721 |   50.4 |  0.0028 | -0.0036 |  0.4  |
| inverted_hammer      | long  |  2624 |   50.9 | -0.0017 | -0.0081 | -0.21 |
| dark_cloud_cover     | short |   968 |   46.8 | -0.0033 |  0.0031 | -0.23 |
| double_top           | short |  5115 |   49.2 | -0.0027 |  0.0037 | -0.36 |
| evening_star         | short |   993 |   46   | -0.0074 | -0.001  | -0.58 |
| three_black_crows    | short |   365 |   47.1 | -0.014  | -0.0076 | -0.7  |
| morning_star         | long  |   910 |   49.7 | -0.0198 | -0.0262 | -1.39 |
| bearish_harami       | short |  3950 |   47.9 | -0.0112 | -0.0048 | -1.46 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 528 | -0.0204 |   48.1 | -0.026  |   49.6 | -0.0071 |   50.4 |  -0.0208 |    48.5 |
| after BIG DOWN bar | 528 |  0.0095 |   50.2 |  0.0348 |   53   |  0.0466 |   51.7 |   0.0392 |    49.8 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 452 |          0.014 | 49.115 |
| mid(3-4) | 765 |         -0.002 | 49.281 |
| high(5+) | 893 |         -0.054 | 47.144 |
