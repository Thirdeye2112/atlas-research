# Candlestick Pattern Memory — counts by pattern_type & timeframe

_Generated 2026-06-20 12:58 UTC. Recognition + logging only (no earnings/news)._

The 19 named candlestick patterns logged into the same pattern_memory table as the
chart patterns (commit 8aacd83), with identical enrichment context. Built by
scripts/build_candle_memory.py using src/atlas_research/ta/candlesticks.py.

## Daily (timeframe=daily) — 2,577,719 instances across 3,361 tickers

| pattern_type | instances |
|---|---:|
| spinning_top | 466,481 |
| doji | 415,711 |
| tweezer_top | 231,717 |
| marubozu | 176,091 |
| tweezer_bottom | 163,957 |
| bearish_engulfing | 163,398 |
| bullish_engulfing | 148,532 |
| bullish_harami | 146,925 |
| bearish_harami | 144,214 |
| hanging_man | 104,685 |
| shooting_star | 97,789 |
| inverted_hammer | 93,432 |
| hammer | 85,043 |
| evening_star | 36,705 |
| morning_star | 34,195 |
| dark_cloud_cover | 27,776 |
| piercing | 23,658 |
| three_black_crows | 9,432 |
| three_white_soldiers | 7,978 |

## 5-min (timeframe=5m)

_5m pass runs next (full clean universe, denoised: tighter tweezer tolerance +
doji/spinning_top dropped as they fire on most 5-min bars). Counts to follow._
