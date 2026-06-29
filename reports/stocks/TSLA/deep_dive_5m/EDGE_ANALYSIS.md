# TSLA edge analysis (intraday)

Bars 106,799 (2021-01-04->2026-06-26). Entry=confirm-bar close, exit=+H bars. In-sample, no costs.

Unconditional drift: 1bars:+0.001%, 3bars:+0.002%, 6bars:+0.004%, 12bars:+0.007%

## Most repeatable + profitable setups (ranked by t-stat @ 6bars)

| setup                | dir   |    n |   win6 |    ret6 |   edge6 |    t6 |
|:---------------------|:------|-----:|-------:|--------:|--------:|------:|
| double_bottom        | long  | 5042 |   50.4 |  0.0594 |  0.0558 |  3.84 |
| double_top           | short | 5055 |   49.6 |  0.0736 |  0.0771 |  3.49 |
| shooting_star        | short | 2750 |   51.3 |  0.0247 |  0.0283 |  1.48 |
| piercing             | long  |  765 |   53.1 |  0.0516 |  0.048  |  1.48 |
| inverted_hammer      | long  | 2688 |   52.6 |  0.0265 |  0.023  |  1.38 |
| three_black_crows    | short |  459 |   54.9 |  0.0579 |  0.0615 |  1.18 |
| hs_bottom            | long  |  184 |   56   |  0.0719 |  0.0684 |  1.02 |
| three_white_soldiers | long  |  461 |   50.3 |  0.028  |  0.0244 |  0.62 |
| marubozu             | long  | 6233 |   49.8 |  0.0055 |  0.002  |  0.35 |
| bearish_engulfing    | short | 5430 |   48   | -0.0002 |  0.0034 | -0.01 |
| hammer               | long  | 2984 |   52.1 | -0.001  | -0.0046 | -0.06 |
| hs_top               | short |  157 |   51   | -0.0574 | -0.0538 | -0.7  |
| bullish_engulfing    | long  | 5485 |   49.8 | -0.0158 | -0.0193 | -0.9  |
| marubozu             | short | 6158 |   48.5 | -0.0112 | -0.0076 | -0.95 |
| dark_cloud_cover     | short |  791 |   49.7 | -0.0433 | -0.0397 | -1.2  |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean6 |   win6 |   mean12 |   win12 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   | 534 |  0.0329 |   48.9 |  0.1293 |   52.6 |  0.2266 |   55.4 |   0.3783 |    53.9 |
| after BIG DOWN bar | 534 |  0.0735 |   53.2 |  0.1532 |   53.6 |  0.2345 |   55.4 |   0.3636 |    56.7 |

## Confluence vs follow-through @ 6bars

| bucket   |    n |   mean_dir_fwd |    win |
|:---------|-----:|---------------:|-------:|
| low(0-2) |  367 |          0.21  | 51.226 |
| mid(3-4) |  690 |          0.012 | 50.435 |
| high(5+) | 1077 |         -0.064 | 47.911 |
