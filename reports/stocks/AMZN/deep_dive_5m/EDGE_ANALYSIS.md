# AMZN edge analysis (intraday)

Bars 104,870 (2021-01-04->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:-0.000%, 3bars:-0.001%, 6bars:-0.002%, 12bars:-0.003%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| double_bottom        | long  |  5154 |   50.8 |  0.0246 |  0.0262 |  2.58 |
| inverted_hammer      | long  |  2571 |   51.9 |  0.0098 |  0.0115 |  0.7  |
| shooting_star        | short |  2637 |   49.1 |  0.0048 |  0.0032 |  0.41 |
| bullish_harami       | long  |  3585 |   50.5 |  0.0016 |  0.0033 |  0.15 |
| hanging_man          | short |  2852 |   50.7 |  0.0016 | -0.0001 |  0.14 |
| piercing             | long  |   731 |   50.1 |  0.0006 |  0.0023 |  0.03 |
| evening_star         | short |   968 |   49.4 | -0.0001 | -0.0018 | -0.01 |
| morning_star         | long  |   974 |   49.5 | -0.0034 | -0.0017 | -0.21 |
| three_white_soldiers | long  |   389 |   50.1 | -0.0075 | -0.0058 | -0.25 |
| hammer               | long  |  2700 |   50.3 | -0.0044 | -0.0027 | -0.35 |
| three_black_crows    | short |   336 |   48.8 | -0.0153 | -0.017  | -0.48 |
| bearish_harami       | short |  3627 |   49.5 | -0.0083 | -0.01   | -0.84 |
| marubozu             | short |  8708 |   48.6 | -0.0053 | -0.007  | -0.86 |
| double_top           | short |  5055 |   48.3 | -0.0106 | -0.0123 | -1.11 |
| tweezer_top          | short | 24492 |   48.4 | -0.0062 | -0.0079 | -1.14 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 524 |  0.0277 |   50.8 |  0.0074 |   47.9 |  0.0448 |   50.4 |   0.0238 |    50.2 |
| after BIG DOWN bar | 524 |  0.0078 |   47.5 |  0.0175 |   51.3 |  0.074  |   51.1 |   0.0904 |    50.2 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 395 |          0.071 | 51.899 |
| mid(3-4) | 739 |         -0.02  | 48.038 |
| high(5+) | 962 |         -0.077 | 48.025 |
