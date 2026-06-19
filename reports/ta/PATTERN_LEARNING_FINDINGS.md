# Chart-Pattern Learning — Findings (full universe)

Built the system you described: SEE structure (swings/trend/S&R) -> RECOGNIZE
patterns (flags, H&S, double tops/bottoms) -> LEARN which win.
Walk-forward on 172,372 patterns, 4,025 tickers, 2012-2026 daily.
WIN = measured-move target hit before invalidation stop (plain win rate).
exp(R) = expectancy in reward:risk units (the profit truth-check).

## By pattern
| pattern | n | win% | exp(R) | med R:R |
|---|---|---|---|---|
| double_bottom | 49,238 | 67.5 | +0.099 | 0.74 |
| hs_bottom (inv H&S) | 15,120 | 57.5 | +0.216 | 1.22 |
| double_top | 47,682 | 57.8 | -0.058 | 0.73 |
| hs_top | 15,240 | 46.4 | -0.002 | 1.25 |
| bull_flag | 22,672 | 35.5 | +0.065 | 2.04 |
| bear_flag | 22,420 | 19.2 | -0.310 | 2.14 |

## High win-rate setups that HOLD at scale
- double_bottom + volume + NOT trend-aligned: **74.1% win** (n=13,569)
- double_bottom + volume + above 200SMA: 67.0% win, +0.102R (n=14,849)
- double_bottom + volume: 66.5% win, +0.094R (n=19,982)

## Honest read
1. double_bottom + volume is real and holds: ~67-74% win across 14 years / 4,025
   tickers. Approaching the 70%+ bar.
2. BUT R:R is the cap: double_bottom target (measured move) < its stop (med R:R
   0.74), so even 67% win only makes +0.10R. WIN RATE alone isn't enough.
3. hs_bottom is the most PROFITABLE per trade (+0.216R) because its R:R>1, even at
   57% win. (Win rate vs reward tradeoff, made concrete.)
4. Bearish patterns lose (bull-era 2012-2026): bear_flag -0.31R, double_top -0.06R.

## Next (clear): fix entry/stop to lift BOTH win% and profit
- Tighter structure stop (just beyond the 2nd low, not the pattern average) and/or
  RETEST entry (enter on the pullback to the neckline) -> smaller risk -> higher
  R:R -> the 67-74% win double_bottom becomes strongly profitable.
- Multi-timeframe confirmation (weekly/daily agree, 5m time the entry).
- More patterns: triangles, wedges, cup-and-handle.
