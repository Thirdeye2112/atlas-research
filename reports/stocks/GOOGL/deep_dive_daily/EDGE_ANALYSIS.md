# GOOGL edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.103%, 3days:+0.307%, 5days:+0.514%, 10days:+1.032%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| tweezer_bottom    | long  | 144 |   56.9 |  0.6917 |  0.1779 |  2.14 |
| bullish_harami    | long  | 118 |   60.2 |  0.6979 |  0.1841 |  2.1  |
| bullish_engulfing | long  | 144 |   59   |  0.6292 |  0.1154 |  2.05 |
| hammer            | long  |  70 |   60   |  0.9284 |  0.4146 |  1.93 |
| inverted_hammer   | long  |  60 |   68.3 |  0.6762 |  0.1624 |  1.42 |
| hs_bottom         | long  |  32 |   62.5 |  0.6506 |  0.1368 |  1.24 |
| double_bottom     | long  | 131 |   57.3 |  0.3662 | -0.1476 |  1.03 |
| morning_star      | long  |  44 |   45.5 |  0.3106 | -0.2032 |  0.77 |
| bull_flag         | long  |  52 |   51.9 |  0.2417 | -0.2722 |  0.53 |
| marubozu          | long  |  71 |   56.3 | -0.0082 | -0.522  | -0.02 |
| dark_cloud_cover  | short |  29 |   48.3 | -0.0547 |  0.4591 | -0.06 |
| hs_top            | short |  29 |   51.7 | -0.2454 |  0.2684 | -0.37 |
| evening_star      | short |  41 |   56.1 | -0.3011 |  0.2128 | -0.42 |
| hanging_man       | short | 110 |   45.5 | -0.1307 |  0.3831 | -0.42 |
| shooting_star     | short |  80 |   45   | -0.4607 |  0.0531 | -1.16 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -1.2106 |   31.6 | -1.7269 |   36.8 | -3.1308 |   26.3 |  -2.0855 |    47.4 |
| after BIG DOWN bar |  19 |  1.2702 |   52.6 |  1.9978 |   63.2 |  2.5887 |   73.7 |   3.59   |    63.2 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  33 |         -1.324 | 33.333 |
| mid(3-4) |  31 |         -1.997 | 38.71  |
| high(5+) |  12 |          0.359 | 50     |
