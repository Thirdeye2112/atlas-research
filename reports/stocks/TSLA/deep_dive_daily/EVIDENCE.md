# TSLA — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **140/140** (100%)
- bearish_engulfing meets definition: **160/160** (100%)
- long candlesticks that are above 200-EMA: **365/631** (58%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=9.0%) the old open->close detector under-saw: **27/38** (71%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 27 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -3.5% · **close-to-close -11.6%** · gap -8.4% · RSI 36 · patterns —
- **2020-03-13** (COVID rebound): candle -8.1% · **close-to-close -2.5%** · gap +6.1% · RSI 35 · patterns —
- **2022-09-13** (CPI selloff): candle -0.3% · **close-to-close -4.0%** · gap -3.8% · RSI 53 · patterns ['evening_star']
- **2025-04-03** (tariff crash): candle +0.8% · **close-to-close -5.5%** · gap -6.2% · RSI 47 · patterns ['bearish_harami']
- **2025-04-09** (tariff-pause rally): candle +21.1% · **close-to-close +22.7%** · gap +1.3% · RSI 51 · patterns ['marubozu']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2013-05-09 significant RISE (+24.4% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +32.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+84.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +31.2% | ❌ against |
| Momentum | RSI | 80 (overbought) | ❌ against |
| Momentum | RSI slope | +14.3 | ✅ supports |
| Momentum | MACD hist | +0.065 | ✅ supports |
| Momentum | Stochastic %K | 77 | · context |
| Volatility | Bollinger %B | 1.23 | ❌ against |
| Volatility | ATR% | 5.95 | · context |
| Volume | Volume vs 20d | 5.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 75 | · context |
| Structure | Dist to 20d low/high | lo +38.7% / hi -9.2% | · context |
| Candle | Body / wicks | body 1.03%  up-wick 47%  lo-wick 47% | · context |
| Candle | Overnight gap | +25.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-09 significant RISE (+22.7% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -11.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +4.5% | ❌ against |
| Momentum | RSI | 51 (neutral) | · context |
| Momentum | RSI slope | +12.9 | ✅ supports |
| Momentum | MACD hist | +1.994 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 75 | · context |
| Volatility | Bollinger %B | 0.72 | · context |
| Volatility | ATR% | 9.16 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 54 | · context |
| Structure | Dist to 20d low/high | lo +21.3% / hi -7.2% | · context |
| Candle | Body / wicks | body 21.14%  up-wick 5%  lo-wick 2% | · context |
| Candle | Overnight gap | +1.3% | ✅ supports |
| Candle | Patterns firing | marubozu | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-09 14:15 px $231.71 (RSI 86, vol 0.6x)

### 2024-10-24 significant RISE (+21.9% close-to-close)

**Corroborating: 6  |  Contradicting: 1**  → next 5d: -4.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+21.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +12.7% | ❌ against |
| Momentum | RSI | 65 (neutral) | · context |
| Momentum | RSI slope | +25.7 | ✅ supports |
| Momentum | MACD hist | +0.105 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 97 | · context |
| Volatility | Bollinger %B | 0.86 | · context |
| Volatility | ATR% | 4.34 | · context |
| Volume | Volume vs 20d | 2.6x | ✅ supports |
| Volume | MFI | 35 | · context |
| Structure | Dist to 20d low/high | lo +18.6% / hi -1.7% | · context |
| Candle | Body / wicks | body 6.46%  up-wick 8%  lo-wick 10% | · context |
| Candle | Overnight gap | +14.5% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2024-10-24 14:10 px $248.92 (RSI 90, vol 0.4x)

### 2020-09-08 significant DROP (-21.1% close-to-close)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: +36.20%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+58.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bull | ❌ against |
| Trend | Dist from 20-EMA | -16.0% | ❌ against |
| Momentum | RSI | 42 (neutral) | · context |
| Momentum | RSI slope | -14.0 | ✅ supports |
| Momentum | MACD hist | -3.078 | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | 0.23 | · context |
| Volatility | ATR% | 10.88 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 56 | · context |
| Structure | Dist to 20d low/high | lo +17.3% / hi -52.2% | · context |
| Candle | Body / wicks | body 7.24%  up-wick 33%  lo-wick 1% | · context |
| Candle | Overnight gap | -14.9% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-02-03 significant RISE (+19.9% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -1.12%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+128.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +38.7% | ❌ against |
| Momentum | RSI | 91 (overbought) | ❌ against |
| Momentum | RSI slope | +7.0 | ✅ supports |
| Momentum | MACD hist | +1.049 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 4.22 | · context |
| Volume | Volume vs 20d | 2.2x | ✅ supports |
| Volume | MFI | 74 | · context |
| Structure | Dist to 20d low/high | lo +43.6% / hi -0.8% | · context |
| Candle | Body / wicks | body 15.78%  up-wick 5%  lo-wick 0% | · context |
| Candle | Overnight gap | +3.6% | ✅ supports |
| Candle | Patterns firing | marubozu | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2021-03-09 significant RISE (+19.6% close-to-close)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +0.49%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+29.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.3% | · context |
| Momentum | RSI | 45 (neutral) | · context |
| Momentum | RSI slope | +15.0 | ✅ supports |
| Momentum | MACD hist | -4.275 | ❌ against |
| Momentum | Stochastic %K | 52 | · context |
| Volatility | Bollinger %B | 0.34 | · context |
| Volatility | ATR% | 7.98 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 22 | ✅ supports |
| Structure | Dist to 20d low/high | lo +19.9% / hi -27.6% | · context |
| Candle | Body / wicks | body 10.75%  up-wick 5%  lo-wick 16% | · context |
| Candle | Overnight gap | +8.0% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2021-03-10 14:40 px $705.42 (RSI 69, vol 2.3x)

### 2012-01-13 significant DROP (-19.3% close-to-close)

**Corroborating: 7  |  Contradicting: 4**  → next 5d: +17.46%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-19.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -18.3% | ❌ against |
| Momentum | RSI | 24 (oversold) | ❌ against |
| Momentum | RSI slope | -21.8 | ✅ supports |
| Momentum | MACD hist | -0.014 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.47 | ❌ against |
| Volatility | ATR% | 6.71 | · context |
| Volume | Volume vs 20d | 5.2x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 32 | · context |
| Structure | Dist to 20d low/high | lo +0.7% / hi -29.4% | · context |
| Candle | Body / wicks | body 19.75%  up-wick 2%  lo-wick 3% | · context |
| Candle | Overnight gap | +0.5% | ❌ against |
| Candle | Patterns firing | marubozu, evening_star, double_top, bear_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-16 significant DROP (-18.6% close-to-close)

**Corroborating: 3  |  Contradicting: 4**  → next 5d: -2.42%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -32.8% | ❌ against |
| Momentum | RSI | 28 (oversold) | ❌ against |
| Momentum | RSI slope | -7.3 | ✅ supports |
| Momentum | MACD hist | -2.502 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.04 | ❌ against |
| Volatility | ATR% | 15.28 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +0.7% / hi -112.3% | · context |
| Candle | Body / wicks | body 5.20%  up-wick 48%  lo-wick 6% | · context |
| Candle | Overnight gap | -14.1% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-19 significant RISE (+18.4% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +23.51%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-2.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -28.3% | · context |
| Momentum | RSI | 33 (neutral) | ✅ supports |
| Momentum | RSI slope | +5.1 | ✅ supports |
| Momentum | MACD hist | -2.620 | ❌ against |
| Momentum | Stochastic %K | 17 | ✅ supports |
| Volatility | Bollinger %B | 0.13 | ✅ supports |
| Volatility | ATR% | 16.63 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 36 | · context |
| Structure | Dist to 20d low/high | lo +18.0% / hi -113.5% | · context |
| Candle | Body / wicks | body 14.13%  up-wick 26%  lo-wick 17% | · context |
| Candle | Overnight gap | +3.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2019-10-24 significant RISE (+17.7% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +5.09%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +18.1% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +19.1 | ✅ supports |
| Momentum | MACD hist | +0.207 | ✅ supports |
| Momentum | Stochastic %K | 93 | · context |
| Volatility | Bollinger %B | 1.34 | ❌ against |
| Volatility | ATR% | 3.66 | · context |
| Volume | Volume vs 20d | 3.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 87 | · context |
| Structure | Dist to 20d low/high | lo +25.2% / hi -1.8% | · context |
| Candle | Body / wicks | body 0.44%  up-wick 33%  lo-wick 58% | · context |
| Candle | Overnight gap | +17.2% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2013-05-09 GAP RISE (gap +25.7%, day +24.4%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +32.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+84.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +31.2% | ❌ against |
| Momentum | RSI | 80 (overbought) | ❌ against |
| Momentum | RSI slope | +14.3 | ✅ supports |
| Momentum | MACD hist | +0.065 | ✅ supports |
| Momentum | Stochastic %K | 77 | · context |
| Volatility | Bollinger %B | 1.23 | ❌ against |
| Volatility | ATR% | 5.95 | · context |
| Volume | Volume vs 20d | 5.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 75 | · context |
| Structure | Dist to 20d low/high | lo +38.7% / hi -9.2% | · context |
| Candle | Body / wicks | body 1.03%  up-wick 47%  lo-wick 47% | · context |
| Candle | Overnight gap | +25.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2019-10-24 GAP RISE (gap +17.2%, day +17.7%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +5.09%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +18.1% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +19.1 | ✅ supports |
| Momentum | MACD hist | +0.207 | ✅ supports |
| Momentum | Stochastic %K | 93 | · context |
| Volatility | Bollinger %B | 1.34 | ❌ against |
| Volatility | ATR% | 3.66 | · context |
| Volume | Volume vs 20d | 3.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 87 | · context |
| Structure | Dist to 20d low/high | lo +25.2% / hi -1.8% | · context |
| Candle | Body / wicks | body 0.44%  up-wick 33%  lo-wick 58% | · context |
| Candle | Overnight gap | +17.2% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2012-01-17 GAP RISE (gap +16.8%, day +16.7%)

**Corroborating: 3  |  Contradicting: 4**  → next 5d: +3.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.2% | · context |
| Momentum | RSI | 44 (neutral) | · context |
| Momentum | RSI slope | -1.7 | ❌ against |
| Momentum | MACD hist | -0.009 | ❌ against |
| Momentum | Stochastic %K | 58 | · context |
| Volatility | Bollinger %B | 0.30 | · context |
| Volatility | ATR% | 6.56 | · context |
| Volume | Volume vs 20d | 3.7x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +14.9% / hi -10.9% | · context |
| Candle | Body / wicks | body 0.08%  up-wick 77%  lo-wick 20% | · context |
| Candle | Overnight gap | +16.8% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2018-10-01 GAP RISE (gap +15.5%, day +17.3%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -19.36%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-0.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +4.2% | ❌ against |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | +0.1 | ✅ supports |
| Momentum | MACD hist | +0.125 | ✅ supports |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 0.87 | · context |
| Volatility | ATR% | 5.72 | · context |
| Volume | Volume vs 20d | 2.0x | ✅ supports |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +18.8% / hi -1.4% | · context |
| Candle | Body / wicks | body 1.61%  up-wick 7%  lo-wick 45% | · context |
| Candle | Overnight gap | +15.5% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2013-08-08 GAP RISE (gap +15.0%, day +14.3%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -9.00%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+110.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +16.7% | ❌ against |
| Momentum | RSI | 70 (overbought) | ❌ against |
| Momentum | RSI slope | +1.3 | ✅ supports |
| Momentum | MACD hist | +0.076 | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 1.07 | ❌ against |
| Volatility | ATR% | 4.99 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 68 | · context |
| Structure | Dist to 20d low/high | lo +31.9% / hi -3.5% | · context |
| Candle | Body / wicks | body 0.56%  up-wick 54%  lo-wick 36% | · context |
| Candle | Overnight gap | +15.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (51 fulfillments in 15y)

### 2025-10-01 bull_flag (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -4.52%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+40.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +11.6% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +3.6 | ✅ supports |
| Momentum | MACD hist | +2.651 | ✅ supports |
| Momentum | Stochastic %K | 97 | · context |
| Volatility | Bollinger %B | 0.84 | · context |
| Volatility | ATR% | 3.51 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 82 | · context |
| Structure | Dist to 20d low/high | lo +27.9% / hi -0.6% | · context |
| Candle | Body / wicks | body 3.53%  up-wick 13%  lo-wick 14% | · context |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-01 14:00 px $446.80 (RSI 96, vol 0.6x)

### 2025-05-27 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -5.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+24.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.4% | ❌ against |
| Momentum | RSI | 71 (overbought) | ❌ against |
| Momentum | RSI slope | +5.3 | ✅ supports |
| Momentum | MACD hist | +2.737 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 0.88 | · context |
| Volatility | ATR% | 4.62 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 74 | · context |
| Structure | Dist to 20d low/high | lo +25.4% / hi -0.2% | · context |
| Candle | Body / wicks | body 4.47%  up-wick 5%  lo-wick 0% | · context |
| Candle | Overnight gap | +2.4% | ✅ supports |
| Candle | Patterns firing | marubozu, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-05-27 13:55 px $353.23 (RSI 92, vol 0.5x)

### 2025-05-09 bull_flag (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +17.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+4.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +9.0% | ❌ against |
| Momentum | RSI | 61 (neutral) | · context |
| Momentum | RSI slope | +7.7 | ✅ supports |
| Momentum | MACD hist | +3.254 | ✅ supports |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.87 | · context |
| Volatility | ATR% | 5.90 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 81 | · context |
| Structure | Dist to 20d low/high | lo +25.3% / hi -2.9% | · context |
| Candle | Body / wicks | body 2.77%  up-wick 52%  lo-wick 1% | · context |
| Candle | Overnight gap | +1.9% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-05-09 14:45 px $301.50 (RSI 71, vol 0.4x)

### Setup: double_bottom (54 fulfillments in 15y)

### 2025-11-28 double_bottom (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +5.77%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +1.9% | · context |
| Momentum | RSI | 52 (neutral) | · context |
| Momentum | RSI slope | +3.7 | ✅ supports |
| Momentum | MACD hist | +0.676 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 71 | · context |
| Volatility | Bollinger %B | 0.54 | · context |
| Volatility | ATR% | 4.61 | · context |
| Volume | Volume vs 20d | 0.4x | ❌ against |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +11.0% / hi -10.2% | · context |
| Candle | Body / wicks | body 0.84%  up-wick 41%  lo-wick 6% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-11-28 15:45 px $429.62 (RSI 48, vol 0.7x)

### 2025-10-27 double_bottom (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +3.53%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+31.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.1% | ❌ against |
| Momentum | RSI | 58 (neutral) | · context |
| Momentum | RSI slope | -0.4 | ❌ against |
| Momentum | MACD hist | -1.735 | ❌ against |
| Momentum | Stochastic %K | 84 | · context |
| Volatility | Bollinger %B | 0.83 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 4.30 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +9.1% / hi -4.1% | · context |
| Candle | Body / wicks | body 2.83%  up-wick 36%  lo-wick 6% | · context |
| Candle | Overnight gap | +1.4% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-27 13:50 px $443.91 (RSI 94, vol 0.5x)

### 2024-04-29 double_bottom (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -4.79%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-5.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +16.8% | ❌ against |
| Momentum | RSI | 65 (neutral) | · context |
| Momentum | RSI slope | +12.0 | ✅ supports |
| Momentum | MACD hist | +3.479 | ✅ supports |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 1.09 | ❌ against |
| Volatility | ATR% | 5.19 | · context |
| Volume | Volume vs 20d | 2.1x | ✅ supports |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +28.5% / hi -2.5% | · context |
| Candle | Body / wicks | body 2.99%  up-wick 34%  lo-wick 27% | · context |
| Candle | Overnight gap | +12.0% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2024-04-29 14:10 px $188.22 (RSI 83, vol 0.7x)

### Setup: inverted_hammer (52 fulfillments in 15y)

### 2026-06-04 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -4.61%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -0.4% | · context |
| Momentum | RSI | 51 (neutral) | · context |
| Momentum | RSI slope | -2.5 | ❌ against |
| Momentum | MACD hist | -2.394 | ❌ against |
| Momentum | Stochastic %K | 48 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 3.53 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +5.9% / hi -8.4% | · context |
| Candle | Body / wicks | body 0.33%  up-wick 71%  lo-wick 14% | · context |
| Candle | Overnight gap | -0.9% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-04 14:10 px $425.11 (RSI 82, vol 1.0x)

### 2025-06-30 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -6.25%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -2.4% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | -3.2 | ❌ against |
| Momentum | MACD hist | -1.615 | ❌ against |
| Momentum | Stochastic %K | 15 | ✅ supports |
| Volatility | Bollinger %B | 0.40 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 5.32 | · context |
| Volume | Volume vs 20d | 0.6x | · context |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +14.0% / hi -12.6% | · context |
| Candle | Body / wicks | body 0.70%  up-wick 63%  lo-wick 12% | · context |
| Candle | Overnight gap | -1.2% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-06-30 15:55 px $321.20 (RSI 47, vol 0.8x)

### 2025-06-26 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -3.20%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+8.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -0.3% | · context |
| Momentum | RSI | 51 (neutral) | · context |
| Momentum | RSI slope | -5.7 | ❌ against |
| Momentum | MACD hist | -0.590 | ❌ against |
| Momentum | Stochastic %K | 58 | · context |
| Volatility | Bollinger %B | 0.48 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 5.51 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 77 | · context |
| Structure | Dist to 20d low/high | lo +16.1% / hi -12.9% | · context |
| Candle | Body / wicks | body 0.36%  up-wick 71%  lo-wick 13% | · context |
| Candle | Overnight gap | -0.9% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-06-26 18:55 px $327.61 (RSI 48, vol 0.8x)

### Setup: bullish_harami (140 fulfillments in 15y)

### 2026-06-08 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +0.54%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -1.8% | · context |
| Momentum | RSI | 48 (neutral) | · context |
| Momentum | RSI slope | -3.0 | ❌ against |
| Momentum | MACD hist | -4.461 | ❌ against |
| Momentum | Stochastic %K | 36 | · context |
| Volatility | Bollinger %B | 0.23 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 4.09 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +5.0% / hi -10.9% | · context |
| Candle | Body / wicks | body 3.18%  up-wick 22%  lo-wick 9% | · context |
| Candle | Overnight gap | +1.4% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-08 15:35 px $401.42 (RSI 68, vol 0.9x)

### 2026-06-02 bullish_harami (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -6.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +0.9% | · context |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | -6.5 | ❌ against |
| Momentum | MACD hist | -1.455 | ❌ against |
| Momentum | Stochastic %K | 50 | · context |
| Volatility | Bollinger %B | 0.49 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 3.55 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 64 | · context |
| Structure | Dist to 20d low/high | lo +9.4% / hi -7.0% | · context |
| Candle | Body / wicks | body 1.32%  up-wick 6%  lo-wick 42% | · context |
| Candle | Overnight gap | +0.6% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-02 13:55 px $417.27 (RSI 84, vol 0.6x)

### 2026-03-16 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -3.72%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-0.1%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.1% | · context |
| Momentum | RSI | 43 (neutral) | · context |
| Momentum | RSI slope | +1.2 | ✅ supports |
| Momentum | MACD hist | +0.054 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 36 | · context |
| Volatility | Bollinger %B | 0.22 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 3.50 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +3.6% / hi -6.3% | · context |
| Candle | Body / wicks | body 0.17%  up-wick 81%  lo-wick 12% | · context |
| Candle | Overnight gap | +1.3% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-16 14:45 px $400.67 (RSI 60, vol 0.5x)
