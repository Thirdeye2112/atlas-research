# Fewest candles to forecast the run height A (1473 runs, peak ≥6 bars out, 10 names)

Target A = full run % (low→peak); median 7.2%. Fixed sample, vary how many early candles we feed.

## Predictive power vs candles used

| candles | n | GBM R² | linear R² | Δ vs prev |
|---|---|---|---|---|
| 1..1 | 1377 | 0.103 | 0.177 | +0.103 |
| 1..2 | 1377 | 0.132 | 0.232 | +0.029 |
| 1..3 | 1377 | 0.256 | 0.295 | +0.125 |
| 1..4 | 1377 | 0.253 | 0.323 | -0.004 |
| 1..5 | 1377 | 0.292 | 0.361 | +0.039 |

## Most predictive early features (|Spearman| with A)

|        |   leg_amp |
|:-------|----------:|
| c2_cum |     0.467 |
| L_atr  |     0.455 |
| c1_rng |     0.447 |
| c2_rng |     0.433 |
| c1_cum |     0.373 |
| c1_ret |     0.373 |
| L_de20 |     0.232 |
| L_mr   |     0.226 |

## Simple formula (candles 1..2)

`A ≈ 9.37 + +9.58·c2_cum + -8.41·c2_ret + -4.34·c1_ret + -4.34·c1_cum + +1.43·L_atr`

Top standardized drivers: `c2_cum` +2.68, `c2_ret` -1.64, `c1_ret` -1.00, `c1_cum` -1.00, `L_atr` +0.23.

_Knee = the candle count after which extra candles add little R²: that's the fewest you need._