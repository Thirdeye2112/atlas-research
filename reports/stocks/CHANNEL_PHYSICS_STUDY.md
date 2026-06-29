# Channel-physics study — the thrown-ball hypothesis on 5-minute candles (10 names)

Tests whether the **angle** of the channel (highs/lows-line slope) and the **intensity** of the first 1–3 candles set the **arc** of an intraday run — apex height, time-to-top, and the drop before the next rise — like a projectile's launch angle + velocity. 9,304 single-session up-legs (apex ≥ 6 bars, 5m, swing width 3); 8,664 have a same-session drop.

## A. Does the channel/launch correlate with the run? (Spearman)

| relationship | ρ |
|---|---|
| angle (close-slope/ATR, 3 bars) -> apex height | 0.122 |
| early velocity v3 -> apex height | 0.351 |
| acceleration -> apex height | -0.057 |
| lows-line slope (3) -> apex height | 0.418 |
| highs-line slope (3) -> apex height | 0.322 |
| channel widening (3) -> apex height | -0.147 |
| angle3 -> apex TIME (bars) | -0.125 |
| velocity v3 -> apex TIME (bars) | -0.248 |
| apex height -> drop depth | 0.218 |
| angle3 -> drop depth | -0.023 |
| apex height -> retrace fraction | -0.142 |

## B. Is the path actually an arc?

- Ascent traces a concave dome (β₂<0) in **58%** of legs; the full launch→drop is concave in **96%**.
- A downward parabola fits the full arc well: median R² **0.73** (quadratic) vs **0.53** (straight line) — price traces a ball-arc, not a line.

## C. Ballistic signature (height grows with velocity²)

- Apex height vs launch velocity: adding a **v²** term lifts R² 0.227 → 0.323 (v² coef +9.401). A positive v² term is the projectile signature: faster launches top **disproportionately** higher.

## D. Symmetry of the arc (does the drop mirror the rise?)

- Median retrace = **0.35** of the run; descent/ascent bar-ratio = **0.45** (1.0 = perfectly symmetric ballistic arc). 

## E. Forecasting the arc from the first k candles (OOS R²)

PHYSICS features = launch velocity, acceleration, channel angle, channel-widening, ATR. RAW = the per-candle returns/body/volume/cum used in the min-info study.

| target | k | raw (lin/GBM) | physics (lin/GBM) |
|---|---|---|---|
| apex HEIGHT | 1 | 0.341/0.387 | 0.265/0.301 |
| apex HEIGHT | 2 | 0.378/0.434 | 0.346/0.377 |
| apex HEIGHT | 3 | 0.414/0.465 | 0.38/0.428 |
| apex TIME | 1 | 0.065/0.093 | 0.07/0.1 |
| apex TIME | 2 | 0.072/0.117 | 0.078/0.128 |
| apex TIME | 3 | 0.079/0.143 | 0.091/0.149 |
| DROP depth | 1 | 0.131/0.123 | 0.137/0.139 |
| DROP depth | 2 | 0.138/0.134 | 0.14/0.116 |
| DROP depth | 3 | 0.137/0.132 | 0.14/0.133 |

_5m only (2023+, finest data in the DB). Survivorship: legs are confirmed swing highs, so real-time you must gate with the oversold/5m-VWAP entry confirmation._