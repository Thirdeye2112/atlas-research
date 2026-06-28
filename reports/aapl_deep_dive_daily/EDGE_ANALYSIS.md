# AAPL edge analysis (daily)

Bars 3,781 (2011-06-13->2026-06-25). Entry=confirm-bar close, exit=+H days. In-sample, no costs.

Unconditional drift: 1days:+0.100%, 3days:+0.300%, 5days:+0.501%, 10days:+1.005%

## Most repeatable + profitable setups (ranked by t-stat @ 5days)

| setup             | dir   |   n |   win5 |    ret5 |   edge5 |    t5 |
|:------------------|:------|----:|-------:|--------:|--------:|------:|
| bull_flag         | long  |  59 |   76.3 |  1.6208 |  1.1193 |  3.84 |
| double_bottom     | long  |  94 |   63.8 |  0.9231 |  0.4216 |  3.14 |
| marubozu          | long  |  94 |   60.6 |  0.7352 |  0.2337 |  2.49 |
| bullish_harami    | long  | 105 |   60   |  1.0394 |  0.5379 |  2.4  |
| inverted_hammer   | long  |  60 |   68.3 |  1.2325 |  0.731  |  2.23 |
| hs_bottom         | long  |  26 |   65.4 |  1.0987 |  0.5972 |  1.96 |
| bullish_engulfing | long  | 128 |   53.1 |  0.1714 | -0.3301 |  0.53 |
| bear_flag         | short |  26 |   50   |  0.1289 |  0.6304 |  0.15 |
| hammer            | long  |  67 |   46.3 |  0.0779 | -0.4236 |  0.15 |
| dark_cloud_cover  | short |  50 |   50   |  0.047  |  0.5485 |  0.12 |
| tweezer_bottom    | long  | 142 |   50   | -0.0776 | -0.5791 | -0.23 |
| double_top        | short |  77 |   54.5 | -0.2433 |  0.2582 | -0.49 |
| morning_star      | long  |  39 |   35.9 | -0.5382 | -1.0397 | -0.84 |
| bearish_harami    | short | 148 |   44.6 | -0.2653 |  0.2362 | -1.01 |
| marubozu          | short |  45 |   35.6 | -1.07   | -0.5685 | -1.92 |

## After significant 1-bar moves

| setup              |   n |   mean1 |   win1 |   mean3 |   win3 |   mean5 |   win5 |   mean10 |   win10 |
|:-------------------|----:|--------:|-------:|--------:|-------:|--------:|-------:|---------:|--------:|
| after BIG UP bar   |  19 | -0.6228 |   42.1 | -0.2347 |   52.6 | -2.0458 |   52.6 |  -0.1322 |    57.9 |
| after BIG DOWN bar |  18 |  0.7879 |   50   |  0.8051 |   50   |  0.3678 |   50   |   0.4159 |    55.6 |

## Confluence vs follow-through @ 5days

| bucket   |   n |   mean_dir_fwd |    win |
|:---------|----:|---------------:|-------:|
| low(0-2) |  37 |         -1.064 | 48.649 |
| mid(3-4) |  31 |         -0.638 | 58.065 |
| high(5+) |   7 |         -0.771 | 57.143 |
