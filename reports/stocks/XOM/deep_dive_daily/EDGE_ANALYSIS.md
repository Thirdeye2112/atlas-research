# XOM edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.028%, 3days:+0.082%, 5days:+0.135%, 10days:+0.275%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| bullish_engulfing | long  | 122 |   58.2 |  0.4928 |  0.3575 |  1.92 |
| hs_bottom         | long  |  32 |   59.4 |  0.6116 |  0.4763 |  1.08 |
| inverted_hammer   | long  |  89 |   56.2 |  0.3353 |  0.1999 |  0.83 |
| hanging_man       | short | 117 |   48.7 |  0.2245 |  0.3598 |  0.76 |
| bullish_harami    | long  | 107 |   54.2 |  0.2711 |  0.1358 |  0.73 |
| marubozu          | long  |  68 |   52.9 |  0.2355 |  0.1001 |  0.69 |
| morning_star      | long  |  35 |   54.3 |  0.2349 |  0.0996 |  0.58 |
| bull_flag         | long  |  27 |   48.1 |  0.3927 |  0.2573 |  0.5  |
| piercing          | long  |  32 |   56.2 |  0.3107 |  0.1754 |  0.42 |
| tweezer_bottom    | long  | 211 |   48.8 | -0.0923 | -0.2276 | -0.38 |
| double_bottom     | long  | 134 |   48.5 | -0.1192 | -0.2546 | -0.45 |
| evening_star      | short |  48 |   47.9 | -0.2364 | -0.1011 | -0.46 |
| marubozu          | short |  48 |   47.9 | -0.3056 | -0.1702 | -0.58 |
| tweezer_top       | short | 292 |   46.9 | -0.0944 |  0.041  | -0.63 |
| hammer            | long  |  81 |   51.9 | -0.4316 | -0.567  | -0.81 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -1.0334 |   26.3 | -0.6884 |   52.6 | -0.57   |   52.6 |   0.2963 |    57.9 |
| after BIG DOWN bar |  19 | -0.3823 |   52.6 | -1.143  |   42.1 | -1.4052 |   42.1 |  -2.3629 |    42.1 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  40 |         -1.189 | 40     |
| mid(3-4) |  26 |         -0.24  | 50     |
| high(5+) |   9 |          2.215 | 55.556 |
