# META edge analysis (intraday)

Bars 106,573 (2021-01-04->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.003%, 6bars:+0.007%, 12bars:+0.014%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| hanging_man          | short |  3092 |   50.1 |  0.0222 |  0.029  |  1.55 |
| piercing             | long  |   951 |   50.8 |  0.037  |  0.0302 |  1.45 |
| bullish_engulfing    | long  |  5023 |   49.2 |  0.0138 |  0.007  |  1.29 |
| inverted_hammer      | long  |  2841 |   51.5 |  0.0125 |  0.0057 |  1.15 |
| double_bottom        | long  |  5448 |   49.6 |  0.012  |  0.0053 |  1.08 |
| bullish_harami       | long  |  3848 |   50.2 |  0.0105 |  0.0037 |  0.88 |
| tweezer_bottom       | long  | 24500 |   50.1 |  0.0038 | -0.003  |  0.87 |
| bearish_harami       | short |  3945 |   50.2 |  0.0059 |  0.0127 |  0.51 |
| three_white_soldiers | long  |   465 |   52   |  0.0148 |  0.008  |  0.47 |
| dark_cloud_cover     | short |   922 |   50.2 |  0.0089 |  0.0157 |  0.44 |
| hammer               | long  |  3016 |   51.3 |  0.0053 | -0.0015 |  0.39 |
| three_black_crows    | short |   446 |   50   |  0.0086 |  0.0154 |  0.32 |
| marubozu             | long  |  9302 |   49.3 |  0.0012 | -0.0055 |  0.21 |
| shooting_star        | short |  3003 |   50   | -0.0006 |  0.0062 | -0.04 |
| morning_star         | long  |  1001 |   49   | -0.0015 | -0.0083 | -0.08 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 533 |  0.0152 |   47.8 |  0.0291 |   49.7 |  0.0389 |   48.2 |   0.0129 |    48.2 |
| after BIG DOWN bar | 533 |  0.0153 |   51.8 |  0.0391 |   51.2 |  0.0792 |   51.8 |   0.0943 |    52   |

## Confluence vs follow-through @ 6bars

| bucket   |    n |   mean_dir_fwd |    win |
|:---------|-----:|---------------:|-------:|
| low(0-2) |  409 |          0.04  | 49.633 |
| mid(3-4) |  700 |         -0.046 | 48.857 |
| high(5+) | 1022 |         -0.034 | 49.022 |
