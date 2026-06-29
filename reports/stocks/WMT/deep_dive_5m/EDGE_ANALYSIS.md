# WMT edge analysis (intraday)

Bars 105,574 (2021-01-04->2026-06-18). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.000%, 3bars:+0.001%, 6bars:+0.002%, 12bars:+0.004%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| piercing             | long  |   809 |   52.5 |  0.0315 |  0.0296 |  2.23 |
| hammer               | long  |  2766 |   50.7 |  0.0163 |  0.0144 |  1.93 |
| morning_star         | long  |   898 |   52   |  0.0245 |  0.0227 |  1.85 |
| dark_cloud_cover     | short |   820 |   44.1 |  0.0624 |  0.0643 |  0.76 |
| double_bottom        | long  |  5524 |   49.7 |  0.0046 |  0.0027 |  0.73 |
| bullish_engulfing    | long  |  5111 |   50   |  0.0041 |  0.0022 |  0.71 |
| bullish_harami       | long  |  4056 |   51   |  0.0011 | -0.0008 |  0.18 |
| tweezer_top          | short | 25434 |   47.1 |  0.001  |  0.0028 |  0.17 |
| three_black_crows    | short |   362 |   45.6 |  0.0012 |  0.0031 |  0.07 |
| marubozu             | short | 11162 |   46.7 |  0.0003 |  0.0022 |  0.03 |
| three_white_soldiers | long  |   364 |   47   | -0.0009 | -0.0028 | -0.06 |
| marubozu             | long  | 11749 |   48.9 | -0.0006 | -0.0024 | -0.22 |
| evening_star         | short |   919 |   47   | -0.0034 | -0.0015 | -0.33 |
| inverted_hammer      | long  |  2747 |   50.9 | -0.0121 | -0.014  | -0.48 |
| tweezer_bottom       | long  | 23901 |   50.2 | -0.0025 | -0.0044 | -0.67 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 528 |  0.0065 |   48.9 |  0.0443 |   49.4 |  0.0286 |   49.6 |   0.0295 |    49.8 |
| after BIG DOWN bar | 528 |  0.0353 |   53.2 |  0.0498 |   56.1 |  0.0579 |   51.5 |   0.0794 |    52.8 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 467 |          0.014 | 50.321 |
| mid(3-4) | 749 |         -0.015 | 50.467 |
| high(5+) | 895 |         -0.055 | 45.14  |
