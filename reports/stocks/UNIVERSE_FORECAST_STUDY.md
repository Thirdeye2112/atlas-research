# Whole-universe run-height forecast, liquidity-tiered

Daily candles, 5,535 tickers (≥250 bars), 2011–2026. Finest data available is 5-minute; no 1-minute in the DB.

Targets: **first-leg** A = low→next-swing-high amplitude (min_amp 3%); **whole-run** A = low→ultimate-high riding pullbacks (≥5%). OOS R² via 70/30 split; linear & GBM. ALL vs consolidation-breakout subset. Target & features winsorized to [1%,99%] per group (microcap fat tails otherwise dominate the fit).

## Key findings

- **The first-leg run height is broadly forecastable** from ~2–3 early candles (pooled OOS R² ≈ 0.43→0.48→0.54 for candles 1→2→3), and across all four liquidity tiers — not just mega-caps.
- **The consolidation-breakout context is the cleaner setup**: it beats the unfiltered set in *every* tier and *every* candle count (pooled breakout R² ≈ 0.51→0.59→0.64 vs 0.43→0.48→0.54). This confirms the breakout context is the more forecastable launch, at scale.
- **Whole-run height is harder** (pooled R² ≈ 0.30→0.36→0.38) than the first leg, consistent with prior work — target the first-leg high, then re-forecast leg-by-leg.
- **Robust drivers match the 10-name basket study**: early cumulative gain (`c2_cum`) and the ATR vol regime (`L_atr`) dominate, with early candle range (`c?_rng`) secondary — now validated across 5,535 tickers.

## Liquidity tiers (median daily $-volume per ticker)

| tier | n tickers | $-vol range |
|---|---|---|
| T1 | 1384 | $44.7M – $46.3B |
| T2 | 1383 | $4.4M – $44.7M |
| T3 | 1384 | $350.3K – $4.4M |
| T4 | 1384 | $0 – $347.8K |

## First-leg run (target A = first-leg run %; median 11.7%, n=482,867)

OOS R² by candles used, pooled then per tier:

| group | candles | ALL (lin/GBM) | consol-breakout (lin/GBM) |
|---|---|---|---|
| POOLED | 1..1 | 0.426/0.450 (n=405948) | 0.514/0.533 (n=59684) |
| POOLED | 1..2 | 0.481/0.509 (n=405943) | 0.587/0.609 (n=59684) |
| POOLED | 1..3 | 0.538/0.569 (n=405941) | 0.641/0.663 (n=59684) |
| T1 | 1..1 | 0.443/0.447 (n=137862) | 0.528/0.525 (n=20049) |
| T1 | 1..2 | 0.488/0.496 (n=137862) | 0.579/0.577 (n=20049) |
| T1 | 1..3 | 0.549/0.556 (n=137862) | 0.633/0.631 (n=20049) |
| T2 | 1..1 | 0.399/0.406 (n=105562) | 0.484/0.484 (n=15708) |
| T2 | 1..2 | 0.453/0.462 (n=105562) | 0.559/0.563 (n=15708) |
| T2 | 1..3 | 0.519/0.527 (n=105562) | 0.613/0.619 (n=15708) |
| T3 | 1..1 | 0.405/0.419 (n=91893) | 0.486/0.480 (n=13415) |
| T3 | 1..2 | 0.458/0.482 (n=91892) | 0.557/0.550 (n=13415) |
| T3 | 1..3 | 0.536/0.556 (n=91891) | 0.619/0.616 (n=13415) |
| T4 | 1..1 | 0.314/0.378 (n=70631) | 0.467/0.475 (n=10512) |
| T4 | 1..2 | 0.390/0.466 (n=70627) | 0.549/0.571 (n=10512) |
| T4 | 1..3 | 0.449/0.534 (n=70626) | 0.606/0.649 (n=10512) |

### Robust target formula (first-leg run, candles 1..2, linear)

- **POOLED** (n=405,943): `A ≈ 2.76 + +1.65·c2_cum + +1.79·L_atr + -0.94·c2_ret + +0.78·c2_rng + +0.70·c1_rng`
  - top standardized drivers: `c2_cum` +0.41, `L_atr` +0.38, `c2_ret` -0.16, `c2_rng` +0.15, `c1_rng` +0.14
- **T1** (n=137,862): `A ≈ 3.49 + +2.37·L_atr + +0.71·c2_cum + +0.32·L_de20 + +0.66·c1_rng + +0.63·c2_rng`
- **T2** (n=105,562): `A ≈ 4.21 + +2.66·L_atr + +1.10·c2_cum + +0.40·L_de20 + +0.76·c1_rng + +0.70·c2_rng`
- **T3** (n=91,892): `A ≈ 4.62 + +1.70·c2_cum + +1.72·L_atr + -1.00·c2_ret + +0.90·c2_rng + +0.85·c1_rng`
- **T4** (n=70,627): `A ≈ -1.56 + +3.07·c2_cum + -2.36·c2_ret + +1.16·L_atr + -1.19·c1_cum + -1.19·c1_ret`

## Whole run (target A = whole run %; median 17.4%, n=211,794)

OOS R² by candles used, pooled then per tier:

| group | candles | ALL (lin/GBM) | consol-breakout (lin/GBM) |
|---|---|---|---|
| POOLED | 1..1 | 0.301/0.321 (n=176958) | 0.349/0.341 (n=27817) |
| POOLED | 1..2 | 0.337/0.358 (n=176956) | 0.406/0.415 (n=27817) |
| POOLED | 1..3 | 0.361/0.384 (n=176955) | 0.421/0.421 (n=27817) |
| T1 | 1..1 | 0.305/0.315 (n=55336) | 0.357/0.361 (n=9272) |
| T1 | 1..2 | 0.339/0.353 (n=55336) | 0.387/0.391 (n=9272) |
| T1 | 1..3 | 0.359/0.368 (n=55336) | 0.396/0.396 (n=9272) |
| T2 | 1..1 | 0.267/0.272 (n=45830) | 0.316/0.293 (n=7616) |
| T2 | 1..2 | 0.302/0.305 (n=45830) | 0.352/0.298 (n=7616) |
| T2 | 1..3 | 0.329/0.334 (n=45830) | 0.367/0.323 (n=7616) |
| T3 | 1..1 | 0.274/0.280 (n=41076) | 0.350/0.299 (n=6176) |
| T3 | 1..2 | 0.315/0.321 (n=41075) | 0.400/0.367 (n=6176) |
| T3 | 1..3 | 0.340/0.350 (n=41075) | 0.408/0.391 (n=6176) |
| T4 | 1..1 | 0.263/0.308 (n=34716) | 0.291/0.285 (n=4753) |
| T4 | 1..2 | 0.294/0.352 (n=34715) | 0.378/0.359 (n=4753) |
| T4 | 1..3 | 0.330/0.381 (n=34714) | 0.406/0.411 (n=4753) |

### Robust target formula (whole run, candles 1..2, linear)

- **POOLED** (n=176,956): `A ≈ 7.95 + +2.17·c2_cum + +1.38·L_atr + +0.99·c2_rng + -0.34·L_de20 + -0.78·c2_ret`
  - top standardized drivers: `c2_cum` +0.37, `L_atr` +0.18, `c2_rng` +0.09, `L_de20` -0.07, `c2_ret` -0.07
- **T1** (n=55,336): `A ≈ 11.63 + +2.62·L_atr + +0.92·c2_cum + +1.30·c2_rng + -1.39·prior_rng + +0.69·c1_cum`
- **T2** (n=45,830): `A ≈ 16.45 + +2.36·L_atr + +1.16·c2_cum + +1.36·c2_rng + -0.35·L_rsi + +0.84·c1_rng`
- **T3** (n=41,075): `A ≈ 16.18 + +1.65·c2_cum + +1.58·L_atr + +1.57·c2_rng + -0.38·L_rsi + +0.73·c1_rng`
- **T4** (n=34,715): `A ≈ 1.37 + +3.89·c2_cum + -1.34·c1_cum + -2.44·c2_ret + -0.80·L_de20 + +0.96·L_atr`

_R² that is usefully >0 and stops climbing marks the fewest candles needed. Compare ALL vs consolidation-breakout and across tiers to see which context/liquidity regime is the cleaner, more forecastable setup._