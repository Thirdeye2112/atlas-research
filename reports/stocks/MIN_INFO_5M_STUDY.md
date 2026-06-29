# Does 5-minute forecast the first-leg run better than daily? (min-info, Step 2)

Same 10 tickers, same methodology, two timeframes. Target A = first-leg amplitude (low→next swing high). 5m legs are restricted to a single session (no overnight gap in the leg or its early window). Peak ≥ 6 bars out. OOS R² via 70/30 split; target & features winsorized to [1%,99%].

- DAILY: 1,463 legs, median A **10.4%** (min_amp 3%).
- 5-MIN: 9,304 legs, median A **1.5%** (min_amp 1%).

## OOS R² by early candles used — daily vs 5-minute

| candles | DAILY (lin/GBM) | 5-MIN (lin/GBM) |
|---|---|---|
| 1..1 | 0.316/0.238 (n=1377) | 0.399/0.433 (n=9277) |
| 1..2 | 0.366/0.286 (n=1377) | 0.451/0.474 (n=9277) |
| 1..3 | 0.432/0.337 (n=1377) | 0.48/0.5 (n=9277) |
| 1..4 | 0.461/0.375 (n=1377) | 0.511/0.53 (n=9277) |
| 1..5 | 0.483/0.442 (n=1377) | 0.537/0.565 (n=9277) |

## Simple formula at the knee (candles 1..2)

- **DAILY** (n=1,377): `A ≈ 8.13 + +2.45·L_atr + +1.28·c2_ret + -2.65·L_mr + +1.43·c2_rng + -0.16·L_rsi`
  - top standardized drivers: `L_atr` +0.35, `c2_ret` +0.22, `L_mr` -0.22, `c2_rng` +0.19, `L_rsi` -0.18
- **5-MIN** (n=9,277): `A ≈ 0.66 + +0.86·c2_cum + +1.08·c1_rng + +1.05·c2_rng + -0.39·c2_ret + -0.19·c2_batr`
  - top standardized drivers: `c2_cum` +0.33, `c1_rng` +0.32, `c2_rng` +0.27, `c2_ret` -0.11, `c2_batr` -0.10

**Verdict:** at candles 1..2, 5-minute is **BETTER** than daily (GBM R² 0.474 vs 0.286). The finer timeframe does forecast the first-leg run earlier.

**Caveat — different target sizes.** A 5m first leg is a much smaller move (median 1.5%) than a daily one (median 10.4%). The higher 5m R² means the intraday leg is more predictable *as a fraction of itself* (intraday momentum is more mechanical within a session), not that 5m forecasts a bigger move. Operational read: use 5m to time/size the **intraday entry leg** inside a daily setup (complements the next-session-close>VWAP layer that already doubles the edge), and treat it as evidence that finer-still data (1-minute, not in the DB) would likely sharpen entry timing further — while the **daily** model remains the right tool for the size of the multi-day swing.