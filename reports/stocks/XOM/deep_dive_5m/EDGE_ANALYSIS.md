# XOM edge analysis (intraday)

Bars 106,039 (2021-01-04->2026-06-18). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.004%, 6bars:+0.008%, 12bars:+0.016%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |     n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|------:|-------:|--------:|--------:|------:|
| tweezer_bottom       | long  | 24102 |   50.9 |  0.0122 |  0.0042 |  3.85 |
| double_bottom        | long  |  5491 |   50.2 |  0.0187 |  0.0107 |  2.38 |
| inverted_hammer      | long  |  2814 |   50.9 |  0.0148 |  0.0068 |  1.56 |
| bullish_engulfing    | long  |  5574 |   50.8 |  0.0103 |  0.0023 |  1.55 |
| marubozu             | long  |  8830 |   51.3 |  0.007  | -0.001  |  1.53 |
| hammer               | long  |  2989 |   50.8 |  0.0122 |  0.0043 |  1.29 |
| shooting_star        | short |  3056 |   49.8 |  0.0097 |  0.0177 |  1.12 |
| bullish_harami       | long  |  4118 |   51.6 |  0.0074 | -0.0006 |  0.98 |
| morning_star         | long  |   878 |   50.5 |  0.0122 |  0.0043 |  0.77 |
| hanging_man          | short |  3201 |   47.9 |  0.0068 |  0.0148 |  0.75 |
| piercing             | long  |   801 |   53.3 |  0.0106 |  0.0026 |  0.6  |
| three_black_crows    | short |   362 |   48.3 |  0.0076 |  0.0155 |  0.28 |
| double_top           | short |  5182 |   48.6 | -0.0022 |  0.0057 | -0.26 |
| evening_star         | short |   828 |   47.3 | -0.0056 |  0.0023 | -0.34 |
| three_white_soldiers | long  |   420 |   49   | -0.0149 | -0.0228 | -0.59 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 531 |  0.0439 |     55 |  0.0389 |   51.4 |  0.0755 |   51.6 |    0.06  |    52.9 |
| after BIG DOWN bar | 531 |  0.0225 |     52 |  0.0507 |   53.5 |  0.0584 |   54   |    0.089 |    54   |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 446 |         -0.014 | 50     |
| mid(3-4) | 770 |         -0.017 | 47.792 |
| high(5+) | 906 |         -0.006 | 48.234 |
