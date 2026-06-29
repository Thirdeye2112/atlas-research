# WMT — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **168/168** (100%)
- bearish_engulfing meets definition: **153/153** (100%)
- long candlesticks that are above 200-EMA: **611/877** (70%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=3.0%) the old open->close detector under-saw: **23/38** (61%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 23 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -1.9% · **close-to-close -9.1%** · gap -7.3% · RSI 34 · patterns ['inverted_hammer', 'double_top']
- **2020-03-13** (COVID rebound): candle +5.4% · **close-to-close +9.7%** · gap +4.0% · RSI 49 · patterns —
- **2022-09-13** (CPI selloff): candle -1.2% · **close-to-close -2.1%** · gap -0.9% · RSI 54 · patterns ['tweezer_top']
- **2025-04-03** (tariff crash): candle +1.1% · **close-to-close -2.8%** · gap -3.9% · RSI 45 · patterns ['shooting_star']
- **2025-04-09** (tariff-pause rally): candle +7.5% · **close-to-close +9.5%** · gap +1.9% · RSI 53 · patterns —

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2020-03-17 significant RISE (+11.7% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -3.55%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +4.3% | ❌ against |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | +5.3 | ✅ supports |
| Momentum | MACD hist | -0.024 | ❌ against |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 0.77 | · context |
| Volatility | ATR% | 4.92 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +14.5% / hi -1.2% | · context |
| Candle | Body / wicks | body 5.76%  up-wick 0%  lo-wick 26% | · context |
| Candle | Overnight gap | +5.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-05-17 significant DROP (-11.4% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -5.50%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -12.0% | ❌ against |
| Momentum | RSI | 22 (oversold) | ❌ against |
| Momentum | RSI slope | -19.5 | ✅ supports |
| Momentum | MACD hist | -0.662 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.33 | ❌ against |
| Volatility | ATR% | 3.30 | · context |
| Volume | Volume vs 20d | 4.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 25 | · context |
| Structure | Dist to 20d low/high | lo +0.5% / hi -22.4% | · context |
| Candle | Body / wicks | body 3.72%  up-wick 15%  lo-wick 10% | · context |
| Candle | Overnight gap | -7.9% | ✅ supports |

- **5m confirmation:** VWAP loss at 2022-05-17 13:35 px $135.19 (RSI 0, vol 0.7x)

### 2017-11-16 significant RISE (+10.9% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -3.01%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+26.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +11.2% | ❌ against |
| Momentum | RSI | 83 (overbought) | ❌ against |
| Momentum | RSI slope | +9.6 | ✅ supports |
| Momentum | MACD hist | +0.154 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.44 | ❌ against |
| Volatility | ATR% | 1.86 | · context |
| Volume | Volume vs 20d | 4.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 73 | · context |
| Structure | Dist to 20d low/high | lo +13.4% / hi -0.1% | · context |
| Candle | Body / wicks | body 4.73%  up-wick 1%  lo-wick 8% | · context |
| Candle | Overnight gap | +5.9% | ✅ supports |
| Candle | Patterns firing | marubozu | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2018-02-20 significant DROP (-10.2% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -2.75%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -7.6% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -18.9 | ✅ supports |
| Momentum | MACD hist | -0.244 | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | -0.11 | ❌ against |
| Volatility | ATR% | 3.24 | · context |
| Volume | Volume vs 20d | 4.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 31 | · context |
| Structure | Dist to 20d low/high | lo +0.0% / hi -16.9% | · context |
| Candle | Body / wicks | body 2.97%  up-wick 25%  lo-wick 0% | · context |
| Candle | Overnight gap | -7.4% | ✅ supports |
| Candle | Patterns firing | hs_top, double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-10-14 significant DROP (-10.0% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -2.32%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -7.7% | ❌ against |
| Momentum | RSI | 29 (oversold) | ❌ against |
| Momentum | RSI slope | -31.1 | ✅ supports |
| Momentum | MACD hist | -0.007 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | -0.19 | ❌ against |
| Volatility | ATR% | 2.38 | · context |
| Volume | Volume vs 20d | 7.2x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 31 | · context |
| Structure | Dist to 20d low/high | lo +0.0% / hi -13.2% | · context |
| Candle | Body / wicks | body 9.88%  up-wick 17%  lo-wick 0% | · context |
| Candle | Patterns firing | double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-13 significant RISE (+9.7% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -0.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.5% | · context |
| Momentum | RSI | 49 (neutral) | · context |
| Momentum | RSI slope | +1.7 | ✅ supports |
| Momentum | MACD hist | -0.116 | ❌ against |
| Momentum | Stochastic %K | 63 | · context |
| Volatility | Bollinger %B | 0.44 | · context |
| Volatility | ATR% | 4.24 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 58 | · context |
| Structure | Dist to 20d low/high | lo +9.7% / hi -5.8% | · context |
| Candle | Body / wicks | body 5.41%  up-wick 5%  lo-wick 41% | · context |
| Candle | Overnight gap | +4.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2016-05-19 significant RISE (+9.6% close-to-close)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +2.38%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +3.1% | · context |
| Momentum | RSI | 56 (neutral) | · context |
| Momentum | RSI slope | +17.8 | ✅ supports |
| Momentum | MACD hist | -0.047 | ❌ against |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 0.75 | · context |
| Volatility | ATR% | 2.44 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +9.4% / hi -1.0% | · context |
| Candle | Body / wicks | body 1.62%  up-wick 7%  lo-wick 33% | · context |
| Candle | Overnight gap | +7.8% | ✅ supports |
| Candle | Patterns firing | morning_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-09 significant RISE (+9.5% close-to-close)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +1.77%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +2.8% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +14.4 | ✅ supports |
| Momentum | MACD hist | +0.376 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.93 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 3.78 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +10.9% / hi -1.3% | · context |
| Candle | Body / wicks | body 7.52%  up-wick 15%  lo-wick 4% | · context |
| Candle | Overnight gap | +1.9% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2025-04-09 14:15 px $84.95 (RSI 87, vol 0.8x)

### 2018-08-16 significant RISE (+9.3% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -3.51%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+12.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +9.7% | ❌ against |
| Momentum | RSI | 81 (overbought) | ❌ against |
| Momentum | RSI slope | +15.5 | ✅ supports |
| Momentum | MACD hist | +0.180 | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.48 | ❌ against |
| Volatility | ATR% | 1.85 | · context |
| Volume | Volume vs 20d | 5.7x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 74 | · context |
| Structure | Dist to 20d low/high | lo +11.7% / hi -1.6% | · context |
| Candle | Body / wicks | body 1.47%  up-wick 4%  lo-wick 32% | · context |
| Candle | Overnight gap | +11.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-12 significant DROP (-9.1% close-to-close)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +14.80%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-8.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -9.3% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -24.0 | ✅ supports |
| Momentum | MACD hist | -0.169 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 6 | · context |
| Volatility | Bollinger %B | -0.20 | ❌ against |
| Volatility | ATR% | 4.22 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +1.0% / hi -16.0% | · context |
| Candle | Body / wicks | body 1.86%  up-wick 64%  lo-wick 13% | · context |
| Candle | Overnight gap | -7.3% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2018-08-16 GAP RISE (gap +11.0%, day +9.3%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -3.51%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+12.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +9.7% | ❌ against |
| Momentum | RSI | 81 (overbought) | ❌ against |
| Momentum | RSI slope | +15.5 | ✅ supports |
| Momentum | MACD hist | +0.180 | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.48 | ❌ against |
| Volatility | ATR% | 1.85 | · context |
| Volume | Volume vs 20d | 5.7x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 74 | · context |
| Structure | Dist to 20d low/high | lo +11.7% / hi -1.6% | · context |
| Candle | Body / wicks | body 1.47%  up-wick 4%  lo-wick 32% | · context |
| Candle | Overnight gap | +11.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-07-26 GAP DROP (gap -8.2%, day -7.6%)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +8.77%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-11.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -4.2% | ❌ against |
| Momentum | RSI | 38 (neutral) | · context |
| Momentum | RSI slope | -29.5 | ✅ supports |
| Momentum | MACD hist | +0.092 | ❌ against |
| Momentum | Stochastic %K | 14 | · context |
| Volatility | Bollinger %B | 0.19 | · context |
| Volatility | ATR% | 2.50 | · context |
| Volume | Volume vs 20d | 4.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +1.7% / hi -9.4% | · context |
| Candle | Body / wicks | body 0.70%  up-wick 27%  lo-wick 41% | · context |
| Candle | Overnight gap | -8.2% | ✅ supports |

- **5m confirmation:** VWAP loss at 2022-07-26 13:45 px $121.22 (RSI 89, vol 1.0x)

### 2024-08-15 GAP RISE (gap +8.0%, day +6.6%)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +3.28%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +5.9% | ❌ against |
| Momentum | RSI | 69 (neutral) | · context |
| Momentum | RSI slope | +22.5 | ✅ supports |
| Momentum | MACD hist | +0.188 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 84 | · context |
| Volatility | Bollinger %B | 1.17 | ❌ against |
| Volatility | ATR% | 1.99 | · context |
| Volume | Volume vs 20d | 2.6x | ✅ supports |
| Volume | MFI | 53 | · context |
| Structure | Dist to 20d low/high | lo +8.9% / hi -1.7% | · context |
| Candle | Body / wicks | body 1.27%  up-wick 19%  lo-wick 24% | · context |
| Candle | Overnight gap | +8.0% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2024-08-15 17:45 px $73.36 (RSI 63, vol 2.2x)

### 2022-05-17 GAP DROP (gap -7.9%, day -11.4%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -5.50%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -12.0% | ❌ against |
| Momentum | RSI | 22 (oversold) | ❌ against |
| Momentum | RSI slope | -19.5 | ✅ supports |
| Momentum | MACD hist | -0.662 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.33 | ❌ against |
| Volatility | ATR% | 3.30 | · context |
| Volume | Volume vs 20d | 4.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 25 | · context |
| Structure | Dist to 20d low/high | lo +0.5% / hi -22.4% | · context |
| Candle | Body / wicks | body 3.72%  up-wick 15%  lo-wick 10% | · context |
| Candle | Overnight gap | -7.9% | ✅ supports |

- **5m confirmation:** VWAP loss at 2022-05-17 13:35 px $135.19 (RSI 0, vol 0.7x)

### 2016-05-19 GAP RISE (gap +7.8%, day +9.6%)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +2.38%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +3.1% | · context |
| Momentum | RSI | 56 (neutral) | · context |
| Momentum | RSI slope | +17.8 | ✅ supports |
| Momentum | MACD hist | -0.047 | ❌ against |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 0.75 | · context |
| Volatility | ATR% | 2.44 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +9.4% / hi -1.0% | · context |
| Candle | Body / wicks | body 1.62%  up-wick 7%  lo-wick 33% | · context |
| Candle | Overnight gap | +7.8% | ✅ supports |
| Candle | Patterns firing | morning_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (26 fulfillments in 15y)

### 2026-02-02 bull_flag (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +4.00%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+19.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +5.5% | ❌ against |
| Momentum | RSI | 72 (overbought) | ❌ against |
| Momentum | RSI slope | +16.2 | ✅ supports |
| Momentum | MACD hist | +0.158 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.07 | ❌ against |
| Volatility | ATR% | 1.99 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 26 | ✅ supports |
| Structure | Dist to 20d low/high | lo +11.5% / hi -0.1% | · context |
| Candle | Body / wicks | body 3.82%  up-wick 3%  lo-wick 9% | · context |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-02-03 14:55 px $125.42 (RSI 67, vol 0.7x)

### 2026-01-12 bull_flag (long)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +0.63%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+15.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.2% | ❌ against |
| Momentum | RSI | 67 (neutral) | · context |
| Momentum | RSI slope | +13.1 | ✅ supports |
| Momentum | MACD hist | +0.103 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 1.03 | ❌ against |
| Volatility | ATR% | 1.91 | · context |
| Volume | Volume vs 20d | 2.4x | ✅ supports |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +6.9% / hi -0.7% | · context |
| Candle | Body / wicks | body 0.40%  up-wick 36%  lo-wick 45% | · context |
| Candle | Overnight gap | +2.6% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-13 15:15 px $119.39 (RSI 59, vol 0.7x)

### 2025-10-14 bull_flag (long)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -0.92%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+12.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.4% | ❌ against |
| Momentum | RSI | 71 (overbought) | ❌ against |
| Momentum | RSI slope | +21.8 | ✅ supports |
| Momentum | MACD hist | +0.115 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 1.39 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.88 | · context |
| Volume | Volume vs 20d | 1.9x | ✅ supports |
| Volume | MFI | 60 | · context |
| Structure | Dist to 20d low/high | lo +6.8% / hi -0.7% | · context |
| Candle | Body / wicks | body 3.04%  up-wick 14%  lo-wick 23% | · context |
| Candle | Overnight gap | +1.9% | ✅ supports |
| Candle | Patterns firing | double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-14 13:55 px $104.01 (RSI 93, vol 0.7x)

### Setup: double_bottom (137 fulfillments in 15y)

### 2026-05-19 double_bottom (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: -11.67%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+15.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +2.9% | · context |
| Momentum | RSI | 63 (neutral) | · context |
| Momentum | RSI slope | +6.0 | ✅ supports |
| Momentum | MACD hist | +0.226 | ✅ supports |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.99 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.00 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 73 | · context |
| Structure | Dist to 20d low/high | lo +6.2% / hi -0.7% | · context |
| Candle | Body / wicks | body 0.95%  up-wick 31%  lo-wick 28% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-19 18:50 px $134.26 (RSI 48, vol 0.7x)

### 2026-05-18 double_bottom (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: -11.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+14.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +2.5% | · context |
| Momentum | RSI | 61 (neutral) | · context |
| Momentum | RSI slope | +1.0 | ✅ supports |
| Momentum | MACD hist | +0.123 | ✅ supports |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 0.95 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.99 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 66 | · context |
| Structure | Dist to 20d low/high | lo +5.6% / hi -0.5% | · context |
| Candle | Body / wicks | body 1.38%  up-wick 6%  lo-wick 17% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-18 14:15 px $132.10 (RSI 79, vol 1.6x)

### 2026-04-09 double_bottom (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: -3.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+15.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.5% | · context |
| Momentum | RSI | 60 (neutral) | · context |
| Momentum | RSI slope | +14.2 | ✅ supports |
| Momentum | MACD hist | +0.591 | ✅ supports |
| Momentum | Stochastic %K | 95 | · context |
| Volatility | Bollinger %B | 1.01 | ❌ against |
| Volatility | ATR% | 2.29 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 68 | · context |
| Structure | Dist to 20d low/high | lo +8.6% / hi -0.4% | · context |
| Candle | Body / wicks | body 1.61%  up-wick 20%  lo-wick 9% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-09 15:05 px $128.40 (RSI 61, vol 0.5x)

### Setup: inverted_hammer (64 fulfillments in 15y)

### 2026-06-05 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +1.82%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+2.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.3% | · context |
| Momentum | RSI | 41 (neutral) | · context |
| Momentum | RSI slope | +4.9 | ✅ supports |
| Momentum | MACD hist | -0.738 | ❌ against |
| Momentum | Stochastic %K | 27 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | ATR% | 2.61 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 32 | · context |
| Structure | Dist to 20d low/high | lo +5.2% / hi -13.7% | · context |
| Candle | Body / wicks | body 0.45%  up-wick 72%  lo-wick 9% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-05 14:20 px $120.34 (RSI 81, vol 0.5x)

### 2025-07-21 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: +2.03%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -0.5% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | +3.3 | ✅ supports |
| Momentum | MACD hist | -0.192 | ❌ against |
| Momentum | Stochastic %K | 28 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | ATR% | 1.57 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +1.5% / hi -3.8% | ✅ supports |
| Candle | Body / wicks | body 0.43%  up-wick 63%  lo-wick 10% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-07-21 17:00 px $96.08 (RSI 50, vol 1.0x)

### 2025-06-16 inverted_hammer (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +3.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -2.4% | · context |
| Momentum | RSI | 38 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.0 | ❌ against |
| Momentum | MACD hist | -0.624 | ❌ against |
| Momentum | Stochastic %K | 12 | ✅ supports |
| Volatility | Bollinger %B | 0.05 | ✅ supports |
| Volatility | ATR% | 1.96 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +0.9% / hi -7.0% | ✅ supports |
| Candle | Body / wicks | body 0.49%  up-wick 61%  lo-wick 11% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-06-17 18:55 px $94.36 (RSI 55, vol 0.4x)

### Setup: bullish_harami (127 fulfillments in 15y)

### 2026-06-05 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +1.82%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+2.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.3% | · context |
| Momentum | RSI | 41 (neutral) | · context |
| Momentum | RSI slope | +4.9 | ✅ supports |
| Momentum | MACD hist | -0.738 | ❌ against |
| Momentum | Stochastic %K | 27 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | ATR% | 2.61 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 32 | · context |
| Structure | Dist to 20d low/high | lo +5.2% / hi -13.7% | · context |
| Candle | Body / wicks | body 0.45%  up-wick 72%  lo-wick 9% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-05 14:20 px $120.34 (RSI 81, vol 0.5x)

### 2025-10-10 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +5.78%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -0.4% | · context |
| Momentum | RSI | 49 (neutral) | · context |
| Momentum | RSI slope | -6.6 | ❌ against |
| Momentum | MACD hist | -0.228 | ❌ against |
| Momentum | Stochastic %K | 48 | · context |
| Volatility | Bollinger %B | 0.16 | ✅ supports |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.73 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +1.9% / hi -4.2% | ✅ supports |
| Candle | Body / wicks | body 0.21%  up-wick 75%  lo-wick 15% | · context |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-10 14:50 px $102.82 (RSI 83, vol 0.6x)

### 2025-03-26 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +5.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.2% | · context |
| Momentum | RSI | 37 (neutral) | ✅ supports |
| Momentum | RSI slope | -3.7 | ❌ against |
| Momentum | MACD hist | -0.112 | ❌ against |
| Momentum | Stochastic %K | 13 | ✅ supports |
| Volatility | Bollinger %B | 0.29 | · context |
| Volatility | ATR% | 2.60 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 20 | ✅ supports |
| Structure | Dist to 20d low/high | lo +1.6% / hi -16.8% | ✅ supports |
| Candle | Body / wicks | body 0.02%  up-wick 35%  lo-wick 63% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | bullish_harami, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-03-26 13:55 px $85.10 (RSI 65, vol 1.2x)
