# MSFT edge analysis (intraday)

Bars 67,609 (2023-01-03->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.002%, 6bars:+0.005%, 12bars:+0.010%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |    n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|-----:|-------:|--------:|--------:|------:|
| hanging_man          | short | 1940 |   50.9 |  0.0259 |  0.0307 |  2.85 |
| inverted_hammer      | long  | 1773 |   51.2 |  0.0223 |  0.0175 |  2.2  |
| evening_star         | short |  643 |   50.5 |  0.0299 |  0.0347 |  1.83 |
| double_bottom        | long  | 3388 |   50   |  0.0198 |  0.015  |  1.8  |
| three_black_crows    | short |  253 |   51   |  0.0201 |  0.0249 |  1.04 |
| dark_cloud_cover     | short |  611 |   47.3 |  0.0081 |  0.0129 |  0.49 |
| bullish_harami       | long  | 2462 |   50.8 |  0.0019 | -0.0028 |  0.24 |
| hammer               | long  | 1969 |   52.6 |  0.0011 | -0.0037 |  0.12 |
| bullish_engulfing    | long  | 3449 |   49.9 | -0.0012 | -0.006  | -0.13 |
| bearish_engulfing    | short | 3436 |   48.5 | -0.0011 |  0.0037 | -0.15 |
| marubozu             | long  | 5599 |   48.9 | -0.0012 | -0.006  | -0.24 |
| bearish_harami       | short | 2426 |   48.3 | -0.0024 |  0.0024 | -0.3  |
| three_white_soldiers | long  |  297 |   49.2 | -0.0138 | -0.0186 | -0.51 |
| morning_star         | long  |  642 |   50.3 | -0.0113 | -0.0161 | -0.52 |
| piercing             | long  |  586 |   49.3 | -0.0117 | -0.0165 | -0.64 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 337 | -0.01   |   45.1 |  0.013  |   51.3 |  0.0258 |   49.9 |   0.0795 |    53.7 |
| after BIG DOWN bar | 338 |  0.0174 |   52.4 |  0.0243 |   53.6 |  0.0529 |   54.4 |   0.0849 |    54.4 |

## Confluence vs follow-through @ 6bars

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) | 239 |          0.027 | 46.444 |
| mid(3-4) | 463 |         -0.036 | 47.516 |
| high(5+) | 648 |         -0.014 | 45.062 |
