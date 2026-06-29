# Swing dynamics — speed/volume/candle vs run & pullback (2698 up-legs, 10 names)

## Early features vs outcomes (Spearman)

|                  |   leg_amp |   leg_velocity |   corr_depth |   pb_frac |
|:-----------------|----------:|---------------:|-------------:|----------:|
| early_slope      |     0.584 |          0.885 |        0.199 |    -0.199 |
| early_gain       |     0.744 |          0.782 |        0.186 |    -0.311 |
| early_vol_ratio  |     0.163 |          0.241 |        0.03  |    -0.091 |
| early_body_atr   |     0.189 |          0.154 |        0.007 |    -0.133 |
| early_accel      |    -0.018 |         -0.044 |        0.041 |     0.063 |
| early_green_frac |     0.094 |          0.157 |        0.039 |    -0.014 |
| start_rsi        |    -0.168 |         -0.192 |       -0.11  |     0.014 |
| start_atr_pct    |     0.354 |          0.481 |        0.333 |     0.036 |
| start_dist_ema20 |    -0.22  |         -0.253 |       -0.154 |     0.013 |
| start_mr         |     0.202 |          0.231 |        0.143 |    -0.01  |
| early_volz       |     0.157 |          0.236 |        0.016 |    -0.098 |

## Rise -> pullback

- corr(leg_amp, pullback depth) = **+0.158**
- **pullback is ~65% of the run** (median pb_frac 0.65, IQR 0.28-1.41) -> rebuy target.

## Long candle (early body / ATR) -> run / pullback / parabolic %

| lc_bucket   |    n |   avg_leg |   avg_pull |   parab |
|:------------|-----:|----------:|-----------:|--------:|
| <1x         | 1667 |      6.43 |       4.85 |   20.88 |
| 1-2x        |  974 |      8.03 |       5.18 |   16.84 |
| 2-3x        |   53 |     12.41 |       5.22 |   11.32 |
| >3x         |    4 |     23.27 |       7.28 |   25    |

## Early speed -> run

| sp_bucket   |   n |   avg_leg |   avg_vel |   avg_pull |
|:------------|----:|----------:|----------:|-----------:|
| slow        | 675 |      3.74 |      0.37 |       4.3  |
| med         | 674 |      5.24 |      0.67 |       4.27 |
| fast        | 674 |      7.16 |      1.04 |       4.7  |
| v.fast      | 675 |     12.44 |      2.21 |       6.67 |

## Parabolic vs not

|   parabolic |    n |   avg_leg |   avg_pull |   pb_frac |
|------------:|-----:|----------:|-----------:|----------:|
|           0 | 2179 |      6.76 |       4.86 |      1.55 |
|           1 |  519 |      8.78 |       5.49 |      1.02 |

## Fitted formulas

**Target (leg size)** OOS R^2 = 0.434. Strongest drivers (std-beta): `early_gain` +0.98, `early_slope` -0.40, `start_atr_pct` +0.18, `start_mr` -0.18, `start_rsi` -0.14, `early_accel` -0.03.

**Pullback depth** OOS R^2 = 0.037; coefs `leg_amp` +0.042, `early_slope` +0.886, `early_vol_ratio` -0.372, `parabolic` +0.899.

_Target exit ≈ entry × (1 + predicted leg%); rebuy level ≈ peak × (1 − pb_frac×leg%). R^2 shows how much of the run/pullback is actually predictable from the early signature._