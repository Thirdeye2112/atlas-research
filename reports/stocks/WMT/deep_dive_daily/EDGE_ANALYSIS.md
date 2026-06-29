# WMT edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.058%, 3days:+0.175%, 5days:+0.290%, 10days:+0.578%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| bullish_harami    | long  | 127 |   66.1 |  0.8768 |  0.587  |  3.96 |
| tweezer_bottom    | long  | 301 |   57.5 |  0.4184 |  0.1286 |  2.5  |
| inverted_hammer   | long  |  64 |   54.7 |  0.9115 |  0.6217 |  2.39 |
| hammer            | long  |  76 |   61.8 |  0.6162 |  0.3264 |  1.55 |
| bullish_engulfing | long  | 168 |   56   |  0.3489 |  0.0591 |  1.48 |
| hs_top            | short |  29 |   55.2 |  0.3068 |  0.5966 |  0.79 |
| morning_star      | long  |  32 |   53.1 |  0.2482 | -0.0416 |  0.49 |
| dark_cloud_cover  | short |  29 |   48.3 |  0.1567 |  0.4465 |  0.27 |
| bull_flag         | long  |  26 |   57.7 |  0.0484 | -0.2413 |  0.12 |
| hanging_man       | short |  87 |   42.5 |  0.0277 |  0.3175 |  0.11 |
| piercing          | long  |  30 |   43.3 | -0.031  | -0.3208 | -0.08 |
| double_bottom     | long  | 137 |   56.9 | -0.0333 | -0.3231 | -0.13 |
| marubozu          | long  |  57 |   43.9 | -0.1317 | -0.4214 | -0.44 |
| double_top        | short | 124 |   52.4 | -0.2509 |  0.0389 | -0.84 |
| shooting_star     | short | 112 |   42.9 | -0.2139 |  0.0759 | -0.87 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -0.3927 |   47.4 |  0.9212 |   57.9 |  0.5899 |   52.6 |   1.147  |    63.2 |
| after BIG DOWN bar |  19 |  0.3106 |   63.2 |  0.2707 |   52.6 |  0.3789 |   47.4 |   2.8073 |    52.6 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  25 |          0.275 | 56     |
| mid(3-4) |  38 |         -0.902 | 39.474 |
| high(5+) |  13 |         -0.552 | 46.154 |
