# AAPL edge analysis (intraday)

Bars 67,664 (2023-01-03->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.004%, 6bars:+0.008%, 12bars:+0.016%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| double_bottom        | long  |  3463 |   50.7 |  0.0143 |  0.0063 |  1.68 |
| bullish_harami       | long  |  2451 |   51.2 |  0.013  |  0.005  |  1.45 |
| inverted_hammer      | long  |  1715 |   52.4 |  0.0135 |  0.0055 |  1.29 |
| tweezer_bottom       | long  | 16020 |   51   |  0.0024 | -0.0055 |  0.69 |
| three_black_crows    | short |   236 |   49.6 |  0.0114 |  0.0194 |  0.47 |
| hammer               | long  |  1867 |   50.8 |  0.0019 | -0.0061 |  0.16 |
| marubozu             | long  |  3594 |   49.2 |  0.0002 | -0.0078 |  0.02 |
| bullish_engulfing    | long  |  3795 |   50.3 |  0.0001 | -0.0079 |  0.01 |
| shooting_star        | short |  1893 |   46.2 | -0.0028 |  0.0051 | -0.26 |
| evening_star         | short |   565 |   47.1 | -0.0048 |  0.0031 | -0.27 |
| three_white_soldiers | long  |   214 |   49.5 | -0.0068 | -0.0148 | -0.29 |
| piercing             | long  |   424 |   47.9 | -0.0103 | -0.0183 | -0.35 |
| dark_cloud_cover     | short |   473 |   45.5 | -0.0154 | -0.0074 | -0.85 |
| bearish_engulfing    | short |  3887 |   48.1 | -0.0083 | -0.0004 | -1.04 |
| bearish_harami       | short |  2611 |   46   | -0.0113 | -0.0033 | -1.2  |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 338 | -0.0237 |   49.4 |  0.0309 |   46.4 |  0.0683 |   49.4 |   0.0434 |    50   |
| after BIG DOWN bar | 338 | -0.0071 |   50.3 |  0.0025 |   51.8 |  0.0598 |   53.6 |   0.0844 |    55.3 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 241 |         -0.111 | 38.589 |
| mid(3-4) | 436 |         -0.016 | 51.147 |
| high(5+) | 673 |         -0.02  | 45.914 |
