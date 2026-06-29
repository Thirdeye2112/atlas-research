# XOM — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **123/123** (100%)
- bearish_engulfing meets definition: **124/124** (100%)
- long candlesticks that are above 200-EMA: **373/753** (50%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=3.7%) the old open->close detector under-saw: **22/38** (58%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 22 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -6.8% · **close-to-close -11.4%** · gap -5.0% · RSI 19 · patterns —
- **2020-03-13** (COVID rebound): candle -4.7% · **close-to-close +2.5%** · gap +7.6% · RSI 22 · patterns —
- **2022-09-13** (CPI selloff): candle -1.3% · **close-to-close -2.3%** · gap -1.0% · RSI 52 · patterns —
- **2025-04-03** (tariff crash): candle -1.7% · **close-to-close -5.3%** · gap -3.6% · RSI 45 · patterns —
- **2025-04-09** (tariff-pause rally): candle +6.5% · **close-to-close +5.0%** · gap -1.4% · RSI 40 · patterns ['bullish_engulfing']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2020-03-24 significant RISE (+12.7% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +7.14%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-45.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -14.9% | · context |
| Momentum | RSI | 34 (neutral) | ✅ supports |
| Momentum | RSI slope | +9.0 | ✅ supports |
| Momentum | MACD hist | -0.366 | ❌ against |
| Momentum | Stochastic %K | 26 | · context |
| Volatility | Bollinger %B | 0.28 | · context |
| Volatility | ATR% | 9.15 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 25 | ✅ supports |
| Structure | Dist to 20d low/high | lo +15.0% / hi -54.7% | · context |
| Candle | Body / wicks | body 2.96%  up-wick 26%  lo-wick 38% | · context |
| Candle | Overnight gap | +9.4% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-11-09 significant RISE (+12.7% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +3.33%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +9.0% | ❌ against |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +17.4 | ✅ supports |
| Momentum | MACD hist | +0.364 | ✅ supports |
| Momentum | Stochastic %K | 84 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 3.99 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +15.8% / hi -2.9% | · context |
| Candle | Body / wicks | body 1.40%  up-wick 55%  lo-wick 18% | · context |
| Candle | Overnight gap | +11.1% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, hs_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-09 significant DROP (-12.2% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -17.61%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-38.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -22.6% | ❌ against |
| Momentum | RSI | 20 (oversold) | ❌ against |
| Momentum | RSI slope | -9.4 | ✅ supports |
| Momentum | MACD hist | -0.899 | ✅ supports |
| Momentum | Stochastic %K | 5 | · context |
| Volatility | Bollinger %B | -0.11 | ❌ against |
| Volatility | ATR% | 5.64 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 10 | · context |
| Structure | Dist to 20d low/high | lo +2.5% / hi -47.0% | · context |
| Candle | Body / wicks | body 0.36%  up-wick 72%  lo-wick 24% | · context |
| Candle | Overnight gap | -12.5% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-12 significant DROP (-11.4% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -7.40%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-44.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -26.5% | ❌ against |
| Momentum | RSI | 19 (oversold) | ❌ against |
| Momentum | RSI slope | -5.5 | ✅ supports |
| Momentum | MACD hist | -1.252 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 7.14 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 15 | · context |
| Structure | Dist to 20d low/high | lo +0.5% / hi -65.2% | · context |
| Candle | Body / wicks | body 6.82%  up-wick 21%  lo-wick 5% | · context |
| Candle | Overnight gap | -5.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-04-17 significant RISE (+10.4% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +1.18%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-29.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +5.4% | ❌ against |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +6.8 | ✅ supports |
| Momentum | MACD hist | +0.922 | ✅ supports |
| Momentum | Stochastic %K | 68 | · context |
| Volatility | Bollinger %B | 0.80 | · context |
| Volatility | ATR% | 6.96 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 64 | · context |
| Structure | Dist to 20d low/high | lo +30.3% / hi -8.1% | · context |
| Candle | Body / wicks | body 8.38%  up-wick 3%  lo-wick 0% | · context |
| Candle | Overnight gap | +1.9% | ✅ supports |
| Candle | Patterns firing | marubozu | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-18 significant DROP (-10.0% close-to-close)

**Corroborating: 4  |  Contradicting: 4**  → next 5d: +12.59%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-49.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -27.4% | ❌ against |
| Momentum | RSI | 23 (oversold) | ❌ against |
| Momentum | RSI slope | +3.4 | ❌ against |
| Momentum | MACD hist | -1.174 | ✅ supports |
| Momentum | Stochastic %K | 8 | · context |
| Volatility | Bollinger %B | 0.07 | ❌ against |
| Volatility | ATR% | 9.60 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 19 | · context |
| Structure | Dist to 20d low/high | lo +5.7% / hi -82.8% | · context |
| Candle | Body / wicks | body 4.14%  up-wick 39%  lo-wick 34% | · context |
| Candle | Overnight gap | -6.1% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-16 significant DROP (-9.5% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -8.81%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-48.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -28.1% | ❌ against |
| Momentum | RSI | 19 (oversold) | ❌ against |
| Momentum | RSI slope | -0.0 | ✅ supports |
| Momentum | MACD hist | -1.358 | ✅ supports |
| Momentum | Stochastic %K | 6 | · context |
| Volatility | Bollinger %B | 0.02 | ❌ against |
| Volatility | ATR% | 8.64 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 14 | · context |
| Structure | Dist to 20d low/high | lo +3.6% / hi -75.8% | · context |
| Candle | Body / wicks | body 0.26%  up-wick 73%  lo-wick 25% | · context |
| Candle | Overnight gap | -9.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-06-11 significant DROP (-8.8% close-to-close)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.60%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ❌ against |
| Trend | Dist from 20-EMA | -3.6% | · context |
| Momentum | RSI | 48 (neutral) | · context |
| Momentum | RSI slope | -21.4 | ✅ supports |
| Momentum | MACD hist | +0.192 | ❌ against |
| Momentum | Stochastic %K | 23 | · context |
| Volatility | Bollinger %B | 0.44 | · context |
| Volatility | ATR% | 5.00 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +12.9% / hi -19.9% | · context |
| Candle | Body / wicks | body 2.84%  up-wick 48%  lo-wick 3% | · context |
| Candle | Overnight gap | -6.2% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-06-05 significant RISE (+8.1% close-to-close)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: -11.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-5.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.4% | ❌ against |
| Momentum | RSI | 71 (overbought) | ❌ against |
| Momentum | RSI slope | +7.4 | ✅ supports |
| Momentum | MACD hist | +0.684 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.21 | ❌ against |
| Volatility | ATR% | 3.85 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +24.3% / hi -0.7% | · context |
| Candle | Body / wicks | body 2.77%  up-wick 20%  lo-wick 3% | · context |
| Candle | Overnight gap | +5.2% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-05-18 significant RISE (+8.0% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +1.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-21.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +3.9% | · context |
| Momentum | RSI | 55 (neutral) | · context |
| Momentum | RSI slope | +8.5 | ✅ supports |
| Momentum | MACD hist | -0.167 | ❌ against |
| Momentum | Stochastic %K | 69 | · context |
| Volatility | Bollinger %B | 0.68 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 5.07 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +12.6% / hi -5.2% | · context |
| Candle | Body / wicks | body 2.12%  up-wick 16%  lo-wick 22% | · context |
| Candle | Overnight gap | +5.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2020-03-09 GAP DROP (gap -12.5%, day -12.2%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -17.61%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-38.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -22.6% | ❌ against |
| Momentum | RSI | 20 (oversold) | ❌ against |
| Momentum | RSI slope | -9.4 | ✅ supports |
| Momentum | MACD hist | -0.899 | ✅ supports |
| Momentum | Stochastic %K | 5 | · context |
| Volatility | Bollinger %B | -0.11 | ❌ against |
| Volatility | ATR% | 5.64 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 10 | · context |
| Structure | Dist to 20d low/high | lo +2.5% / hi -47.0% | · context |
| Candle | Body / wicks | body 0.36%  up-wick 72%  lo-wick 24% | · context |
| Candle | Overnight gap | -12.5% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-11-09 GAP RISE (gap +11.1%, day +12.7%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +3.33%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +9.0% | ❌ against |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +17.4 | ✅ supports |
| Momentum | MACD hist | +0.364 | ✅ supports |
| Momentum | Stochastic %K | 84 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 3.99 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +15.8% / hi -2.9% | · context |
| Candle | Body / wicks | body 1.40%  up-wick 55%  lo-wick 18% | · context |
| Candle | Overnight gap | +11.1% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, hs_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-10 GAP RISE (gap +10.3%, day +3.7%)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: -15.20%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-35.9%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -18.2% | · context |
| Momentum | RSI | 25 (oversold) | ✅ supports |
| Momentum | RSI slope | -1.0 | ❌ against |
| Momentum | MACD hist | -0.961 | ❌ against |
| Momentum | Stochastic %K | 13 | ✅ supports |
| Volatility | Bollinger %B | 0.04 | ✅ supports |
| Volatility | ATR% | 5.84 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 16 | ✅ supports |
| Structure | Dist to 20d low/high | lo +6.0% / hi -41.7% | · context |
| Candle | Body / wicks | body 5.98%  up-wick 2%  lo-wick 41% | · context |
| Candle | Overnight gap | +10.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-16 GAP DROP (gap -9.8%, day -9.5%)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -8.81%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-48.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -28.1% | ❌ against |
| Momentum | RSI | 19 (oversold) | ❌ against |
| Momentum | RSI slope | -0.0 | ✅ supports |
| Momentum | MACD hist | -1.358 | ✅ supports |
| Momentum | Stochastic %K | 6 | · context |
| Volatility | Bollinger %B | 0.02 | ❌ against |
| Volatility | ATR% | 8.64 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 14 | · context |
| Structure | Dist to 20d low/high | lo +3.6% / hi -75.8% | · context |
| Candle | Body / wicks | body 0.26%  up-wick 73%  lo-wick 25% | · context |
| Candle | Overnight gap | -9.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-24 GAP RISE (gap +9.4%, day +12.7%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +7.14%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-45.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -14.9% | · context |
| Momentum | RSI | 34 (neutral) | ✅ supports |
| Momentum | RSI slope | +9.0 | ✅ supports |
| Momentum | MACD hist | -0.366 | ❌ against |
| Momentum | Stochastic %K | 26 | · context |
| Volatility | Bollinger %B | 0.28 | · context |
| Volatility | ATR% | 9.15 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 25 | ✅ supports |
| Structure | Dist to 20d low/high | lo +15.0% / hi -54.7% | · context |
| Candle | Body / wicks | body 2.96%  up-wick 26%  lo-wick 38% | · context |
| Candle | Overnight gap | +9.4% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (27 fulfillments in 15y)

### 2026-03-16 bull_flag (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +2.48%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+25.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.3% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +4.9 | ✅ supports |
| Momentum | MACD hist | -0.090 | ❌ against |
| Momentum | Stochastic %K | 81 | · context |
| Volatility | Bollinger %B | 1.06 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.43 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 62 | · context |
| Structure | Dist to 20d low/high | lo +7.7% / hi -1.5% | · context |
| Candle | Body / wicks | body 0.79%  up-wick 18%  lo-wick 41% | · context |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-16 17:20 px $157.03 (RSI 55, vol 0.5x)

### 2025-05-13 bull_flag (long)

**Corroborating: 2  |  Contradicting: 1**  → next 5d: -4.12%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-1.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +2.2% | · context |
| Momentum | RSI | 56 (neutral) | · context |
| Momentum | RSI slope | +5.1 | ✅ supports |
| Momentum | MACD hist | +0.541 | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 0.86 | · context |
| Volatility | ATR% | 2.60 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 70 | · context |
| Structure | Dist to 20d low/high | lo +5.9% / hi -1.0% | · context |
| Candle | Body / wicks | body 0.13%  up-wick 70%  lo-wick 20% | · context |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-05-13 14:00 px $109.53 (RSI 92, vol 0.7x)

### 2024-03-01 bull_flag (long)

**Corroborating: 6  |  Contradicting: 1**  → next 5d: +2.40%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +2.3% | · context |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +5.2 | ✅ supports |
| Momentum | MACD hist | +0.158 | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 0.97 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.74 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 73 | · context |
| Structure | Dist to 20d low/high | lo +5.1% / hi -0.5% | · context |
| Candle | Body / wicks | body 0.11%  up-wick 54%  lo-wick 34% | · context |
| Candle | Overnight gap | +1.1% | ✅ supports |
| Candle | Patterns firing | hs_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2024-03-01 14:45 px $106.06 (RSI 92, vol 1.1x)

### Setup: double_bottom (134 fulfillments in 15y)

### 2026-05-15 double_bottom (long)

**Corroborating: 6  |  Contradicting: 1**  → next 5d: -1.90%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.9% | · context |
| Momentum | RSI | 59 (neutral) | · context |
| Momentum | RSI slope | +9.6 | ✅ supports |
| Momentum | MACD hist | +0.767 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 1.04 | ❌ against |
| Volatility | ATR% | 2.60 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +8.9% / hi -0.1% | · context |
| Candle | Body / wicks | body 2.71%  up-wick 2%  lo-wick 15% | · context |
| Candle | Overnight gap | +0.6% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2026-03-20 double_bottom (long)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +7.09%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+26.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.1% | ❌ against |
| Momentum | RSI | 68 (neutral) | · context |
| Momentum | RSI slope | +2.8 | ✅ supports |
| Momentum | MACD hist | +0.250 | ✅ supports |
| Momentum | Stochastic %K | 81 | · context |
| Volatility | Bollinger %B | 0.95 | ❌ against |
| Volatility | ATR% | 2.40 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 61 | · context |
| Structure | Dist to 20d low/high | lo +8.1% / hi -1.7% | · context |
| Candle | Body / wicks | body 0.20%  up-wick 83%  lo-wick 7% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | shooting_star, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-20 14:00 px $160.80 (RSI 84, vol 0.9x)

### 2026-03-02 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -2.45%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+26.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.6% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +7.2 | ✅ supports |
| Momentum | MACD hist | -0.544 | ❌ against |
| Momentum | Stochastic %K | 63 | · context |
| Volatility | Bollinger %B | 0.84 | · context |
| Volatility | ATR% | 2.53 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 53 | · context |
| Structure | Dist to 20d low/high | lo +10.5% / hi -3.5% | · context |
| Candle | Body / wicks | body 3.22%  up-wick 4%  lo-wick 18% | · context |
| Candle | Overnight gap | +4.5% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-02 20:45 px $154.68 (RSI 58, vol 2.3x)

### Setup: inverted_hammer (90 fulfillments in 15y)

### 2026-06-17 inverted_hammer (long)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -2.27%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.9% | · context |
| Momentum | RSI | 36 (neutral) | ✅ supports |
| Momentum | RSI slope | +0.5 | ✅ supports |
| Momentum | MACD hist | -1.023 | ❌ against |
| Momentum | Stochastic %K | 18 | ✅ supports |
| Volatility | Bollinger %B | 0.04 | ✅ supports |
| Volatility | ATR% | 2.93 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 38 | · context |
| Structure | Dist to 20d low/high | lo +2.1% / hi -16.3% | · context |
| Candle | Body / wicks | body 0.34%  up-wick 55%  lo-wick 21% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-17 16:30 px $141.65 (RSI 47, vol 0.9x)

### 2026-06-08 inverted_hammer (long)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -7.14%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +0.2% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | -0.3 | ❌ against |
| Momentum | MACD hist | -0.026 | ❌ against |
| Momentum | Stochastic %K | 37 | · context |
| Volatility | Bollinger %B | 0.47 | · context |
| Volatility | ATR% | 2.62 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +4.6% / hi -7.9% | · context |
| Candle | Body / wicks | body 0.39%  up-wick 71%  lo-wick 9% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-08 18:05 px $151.97 (RSI 64, vol 0.7x)

### 2026-06-02 inverted_hammer (long)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -0.43%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+8.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -1.2% | · context |
| Momentum | RSI | 46 (neutral) | · context |
| Momentum | RSI slope | +7.6 | ✅ supports |
| Momentum | MACD hist | -0.652 | ❌ against |
| Momentum | Stochastic %K | 26 | · context |
| Volatility | Bollinger %B | 0.39 | · context |
| Volatility | ATR% | 2.74 | · context |
| Volume | Volume vs 20d | 0.6x | ❌ against |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +3.8% / hi -9.4% | · context |
| Candle | Body / wicks | body 0.36%  up-wick 55%  lo-wick 23% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-02 15:35 px $149.27 (RSI 70, vol 0.6x)

### Setup: bullish_harami (107 fulfillments in 15y)

### 2026-06-08 bullish_harami (long)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -7.14%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +0.2% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | -0.3 | ❌ against |
| Momentum | MACD hist | -0.026 | ❌ against |
| Momentum | Stochastic %K | 37 | · context |
| Volatility | Bollinger %B | 0.47 | · context |
| Volatility | ATR% | 2.62 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +4.6% / hi -7.9% | · context |
| Candle | Body / wicks | body 0.39%  up-wick 71%  lo-wick 9% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-08 18:05 px $151.97 (RSI 64, vol 0.7x)

### 2025-12-19 bullish_harami (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +3.29%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -0.3% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | -2.1 | ❌ against |
| Momentum | MACD hist | -0.189 | ❌ against |
| Momentum | Stochastic %K | 35 | · context |
| Volatility | Bollinger %B | 0.47 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.89 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 60 | · context |
| Structure | Dist to 20d low/high | lo +2.1% / hi -3.2% | · context |
| Candle | Body / wicks | body 0.05%  up-wick 51%  lo-wick 45% | · context |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2025-10-13 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +0.41%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -0.6% | · context |
| Momentum | RSI | 48 (neutral) | · context |
| Momentum | RSI slope | -1.5 | ❌ against |
| Momentum | MACD hist | -0.347 | ❌ against |
| Momentum | Stochastic %K | 20 | ✅ supports |
| Volatility | Bollinger %B | 0.28 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.85 | · context |
| Volume | Volume vs 20d | 0.6x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +1.4% / hi -5.5% | ✅ supports |
| Candle | Body / wicks | body 0.63%  up-wick 6%  lo-wick 22% | · context |
| Candle | Overnight gap | +0.7% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-13 16:50 px $111.67 (RSI 48, vol 1.3x)
