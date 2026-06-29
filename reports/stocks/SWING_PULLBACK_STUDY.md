# First run → first pullback (2749 legs, 10 names)

Pullback measured as a TRUE % OF THE RUN: retrace_frac = (peak−pullback_low)/(peak−start).

## How deep is the first pullback (as % of the first run)?

- **Q1 0.47 / median 0.70 / Q3 0.98** of the run.
- Full reversals (gives back >100% of the run): **38%** of legs.
- Drop from high: median 5.5%; pullback lasts ~4 bars.

## Does leg-1 speed/rise predict the pullback?

- speed → retrace_frac: **+0.069** | run_pct → retrace: **-0.389** | early_slope → retrace: -0.127
- speed → bars-to-peak (timing): **-0.566**

### By leg-1 speed

| sp_b   |   n |   median_retrace |   median_run_bars |   reversal_rate |
|:-------|----:|-----------------:|------------------:|----------------:|
| slow   | 549 |            0.696 |              10   |           0.199 |
| med    | 549 |            0.654 |               7   |           0.226 |
| fast   | 548 |            0.721 |               5.5 |           0.243 |
| v.fast | 549 |            0.739 |               4   |           0.253 |

### By leg-1 run size

| rn_b   |   n |   median_retrace |   reversal_rate |
|:-------|----:|-----------------:|----------------:|
| small  | 549 |            0.87  |           0.348 |
| med    | 549 |            0.779 |           0.29  |
| big    | 548 |            0.619 |           0.181 |
| huge   | 549 |            0.489 |           0.102 |

## Predictability (OOS R²)

- pullback **DEPTH** retrace_frac: R²=0.187 — drivers `run_pct` -0.45, `start_atr` +0.26, `speed` +0.26, `early_slope` -0.20, `start_mr` -0.06
- pullback **TIMING** bars-to-peak: R²=0.553 — drivers `run_pct` +0.78, `speed` -0.57, `start_atr` -0.22, `early_slope` +0.01

_Add-to-position level ≈ peak − retrace_frac × (peak − start). Reliable only as far as R² allows._