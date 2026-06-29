# Swing-leg / pullback study (10 names, 1442 run→pullback→run sequences)

Up-legs via swing_pivots(width=5), min leg 5%. Net of 5.0bps/round-trip.

## Pullback statistics

- Leg-1 gain: median 7.9% | Pullback depth: median 5.6% (7 bars) | Leg-2 gain: median 7.9%
- Run resumes to a higher high **61%** of the time
- At leg-1 peak: RSI ~61, mr_score -0.62 (overbought); at pullback low: mr_score +0.68 (oversold)

## Sell-the-top / rebuy-the-dip vs hold

| strategy                           |   mean% |   median% |   win% |
|:-----------------------------------|--------:|----------:|-------:|
| HOLD through                       |   14.07 |     10.54 |  88.7  |
| SWING perfect (sell top/rebuy dip) |   23.46 |     17.99 |  99.93 |
| SIGNAL-timed swing                 |    9.72 |      8.31 |  90.08 |

SIGNAL-timed beat HOLD in **21%** of sequences (avg -4.35%/seq).

## Resume rate & leg-2 by pullback depth

| pb_bucket   |   n |   resume_rate |   avg_leg2 |
|:------------|----:|--------------:|-----------:|
| 0-5%        | 603 |            86 |       8.88 |
| 5-10%       | 447 |            54 |      11.69 |
| 10-20%      | 283 |            24 |      12.77 |
| >20%        |  71 |            11 |      19.38 |

_SWING-perfect is hindsight (upper bound). SIGNAL-timed exits on overbought/extended (RSI>70 or mr_score<=-1) and rebuys on oversold (mr_score>=1) — what the validated signals achieve._