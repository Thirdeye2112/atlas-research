# TSLA edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.204%, 3days:+0.613%, 5days:+1.035%, 10days:+2.100%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| double_bottom     | long  |  54 |   63   |  1.9554 |  0.9203 |  2.61 |
| bull_flag         | long  |  51 |   58.8 |  2.0299 |  0.9948 |  1.61 |
| tweezer_top       | short | 130 |   57.7 |  0.9297 |  1.9649 |  1.53 |
| bullish_engulfing | long  | 140 |   52.9 |  0.7797 | -0.2554 |  1.45 |
| hammer            | long  |  91 |   56   |  0.9491 | -0.086  |  1.07 |
| inverted_hammer   | long  |  52 |   55.8 |  0.795  | -0.2401 |  0.68 |
| bullish_harami    | long  | 140 |   53.6 |  0.4496 | -0.5855 |  0.68 |
| tweezer_bottom    | long  |  76 |   50   |  0.272  | -0.7632 |  0.33 |
| morning_star      | long  |  33 |   57.6 |  0.237  | -0.7981 |  0.15 |
| marubozu          | long  |  74 |   52.7 | -0.2575 | -1.2927 | -0.33 |
| dark_cloud_cover  | short |  34 |   44.1 | -0.7157 |  0.3194 | -0.39 |
| double_top        | short |  60 |   50   | -0.5602 |  0.475  | -0.6  |
| hanging_man       | short |  86 |   48.8 | -0.5999 |  0.4352 | -0.76 |
| bear_flag         | short |  27 |   40.7 | -1.7585 | -0.7233 | -1.14 |
| evening_star      | short |  37 |   48.6 | -1.4962 | -0.4611 | -1.3  |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 |  1.399  |   42.1 |  1.5383 |   68.4 |  2.5347 |   63.2 |   5.0267 |    68.4 |
| after BIG DOWN bar |  19 |  3.9281 |   89.5 |  8.0898 |   84.2 |  9.0594 |   84.2 |  14.4628 |    84.2 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  25 |         -0.067 | 60     |
| mid(3-4) |  39 |         -2.073 | 43.59  |
| high(5+) |  12 |         -0.419 | 41.667 |
