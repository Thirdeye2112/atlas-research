# NVDA edge analysis (intraday)

Bars 67,665 (2023-01-03->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.003%, 3bars:+0.009%, 6bars:+0.018%, 12bars:+0.037%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| tweezer_bottom       | long  | 14564 |   52.6 |  0.0192 |  0.0009 |  2.9  |
| hammer               | long  |  1811 |   53.1 |  0.0333 |  0.015  |  1.72 |
| inverted_hammer      | long  |  1470 |   52.6 |  0.0361 |  0.0178 |  1.5  |
| bullish_harami       | long  |  2457 |   51.8 |  0.0174 | -0.0009 |  1.06 |
| morning_star         | long  |   510 |   49.2 |  0.0362 |  0.018  |  1.05 |
| bullish_engulfing    | long  |  3763 |   51.9 |  0.0124 | -0.0059 |  0.9  |
| piercing             | long  |   426 |   53.3 |  0.0174 | -0.0008 |  0.62 |
| bearish_harami       | short |  2639 |   48.5 |  0.0157 |  0.034  |  0.43 |
| marubozu             | long  |  3685 |   52.3 |  0.0015 | -0.0168 |  0.05 |
| double_bottom        | long  |  3412 |   51.1 |  0.0001 | -0.0182 |  0    |
| marubozu             | short |  3101 |   46.1 | -0.0027 |  0.0156 | -0.08 |
| shooting_star        | short |  1815 |   50.9 | -0.0037 |  0.0145 | -0.2  |
| dark_cloud_cover     | short |   402 |   44.5 | -0.0262 | -0.008  | -0.64 |
| three_white_soldiers | long  |   233 |   45.9 | -0.0361 | -0.0544 | -0.7  |
| double_top           | short |  3144 |   48.7 | -0.0169 |  0.0014 | -0.95 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 339 | -0.0707 |   42.2 | -0.0345 |   47.8 | -0.0245 |   46   |  -0.0415 |    49.3 |
| after BIG DOWN bar | 339 |  0.0374 |   51.6 |  0.1126 |   51.9 |  0.1258 |   51.9 |   0.095  |    49.3 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 253 |          0.126 | 52.964 |
| mid(3-4) | 427 |         -0.059 | 50.351 |
| high(5+) | 671 |         -0.128 | 46.349 |
