# GOOGL edge analysis (intraday)

Bars 101,927 (2021-01-04->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.002%, 6bars:+0.004%, 12bars:+0.008%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| bullish_harami       | long  |  3306 |   51   |  0.0209 |  0.017  |  2.12 |
| hammer               | long  |  2644 |   53.2 |  0.0218 |  0.0179 |  1.98 |
| morning_star         | long  |   923 |   51.9 |  0.0277 |  0.0238 |  1.32 |
| marubozu             | short |  9436 |   48.1 |  0.0175 |  0.0215 |  0.96 |
| inverted_hammer      | long  |  2358 |   52.4 |  0.0074 |  0.0034 |  0.62 |
| dark_cloud_cover     | short |   763 |   45.2 |  0.0749 |  0.0788 |  0.59 |
| hanging_man          | short |  2802 |   48.1 |  0.0027 |  0.0066 |  0.25 |
| evening_star         | short |   918 |   48.4 |  0.0014 |  0.0054 |  0.07 |
| tweezer_bottom       | long  | 22291 |   51.5 |  0.0002 | -0.0037 |  0.03 |
| shooting_star        | short |  2617 |   49.2 | -0.0011 |  0.0029 | -0.1  |
| double_bottom        | long  |  5195 |   50.9 | -0.0057 | -0.0097 | -0.28 |
| three_white_soldiers | long  |   343 |   48.4 | -0.0108 | -0.0148 | -0.28 |
| piercing             | long  |   716 |   47.6 | -0.0059 | -0.0098 | -0.3  |
| marubozu             | long  | 10258 |   50.2 | -0.0068 | -0.0108 | -0.64 |
| tweezer_top          | short | 23516 |   48.5 | -0.0038 |  0.0002 | -0.68 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 510 |  0.0018 |   49.2 |  0.0119 |   49.6 | -0.0175 |   48.6 |  -0.031  |    50.4 |
| after BIG DOWN bar | 509 |  0.0135 |   48.5 |  0.0006 |   48.7 |  0.0226 |   49.7 |   0.0159 |    51.1 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 363 |          0.038 | 54.27  |
| mid(3-4) | 701 |          0.003 | 49.929 |
| high(5+) | 975 |         -0.05  | 46.564 |
