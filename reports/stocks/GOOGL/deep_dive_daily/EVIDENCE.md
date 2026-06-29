# GOOGL — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **144/144** (100%)
- bearish_engulfing meets definition: **149/149** (100%)
- long candlesticks that are above 200-EMA: **520/688** (76%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=5.0%) the old open->close detector under-saw: **21/38** (55%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 21 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -1.0% · **close-to-close -8.2%** · gap -7.3% · RSI 27 · patterns ['inverted_hammer', 'hs_top']
- **2020-03-13** (COVID rebound): candle +3.3% · **close-to-close +9.2%** · gap +5.7% · RSI 39 · patterns —
- **2022-09-13** (CPI selloff): candle -3.2% · **close-to-close -5.9%** · gap -2.8% · RSI 36 · patterns ['evening_star', 'hs_top', 'bear_flag']
- **2025-04-03** (tariff crash): candle -0.3% · **close-to-close -4.0%** · gap -3.8% · RSI 32 · patterns ['inverted_hammer']
- **2025-04-09** (tariff-pause rally): candle +9.9% · **close-to-close +9.7%** · gap -0.2% · RSI 47 · patterns ['marubozu', 'bullish_engulfing']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2015-07-17 significant RISE (+16.3% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -6.41%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+26.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +21.8% | ❌ against |
| Momentum | RSI | 89 (overbought) | ❌ against |
| Momentum | RSI slope | +19.2 | ✅ supports |
| Momentum | MACD hist | +0.616 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.44 | ❌ against |
| Volatility | ATR% | 2.39 | · context |
| Volume | Volume vs 20d | 4.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 86 | · context |
| Structure | Dist to 20d low/high | lo +22.9% / hi -0.5% | · context |
| Candle | Body / wicks | body 2.89%  up-wick 14%  lo-wick 8% | · context |
| Candle | Overnight gap | +13.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2013-10-18 significant RISE (+13.8% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +0.37%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+20.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.5% | ❌ against |
| Momentum | RSI | 81 (overbought) | ❌ against |
| Momentum | RSI slope | +19.8 | ✅ supports |
| Momentum | MACD hist | +0.253 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.50 | ❌ against |
| Volatility | ATR% | 2.02 | · context |
| Volume | Volume vs 20d | 5.0x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +16.7% / hi -0.4% | · context |
| Candle | Body / wicks | body 3.57%  up-wick 10%  lo-wick 6% | · context |
| Candle | Overnight gap | +9.9% | ✅ supports |
| Candle | Patterns firing | hs_bottom, double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2011-07-15 significant RISE (+13.0% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +3.45%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.8% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +9.3 | ✅ supports |
| Momentum | MACD hist | +0.164 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.18 | ❌ against |
| Volatility | ATR% | 2.62 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 76 | · context |
| Structure | Dist to 20d low/high | lo +20.8% / hi -0.4% | · context |
| Candle | Body / wicks | body 0.02%  up-wick 22%  lo-wick 77% | · context |
| Candle | Overnight gap | +13.0% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-16 significant DROP (-11.6% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -1.76%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -17.3% | ❌ against |
| Momentum | RSI | 31 (neutral) | · context |
| Momentum | RSI slope | +4.3 | ❌ against |
| Momentum | MACD hist | -1.332 | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.01 | ❌ against |
| Volatility | ATR% | 6.14 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +0.6% / hi -42.7% | · context |
| Candle | Body / wicks | body 1.52%  up-wick 71%  lo-wick 8% | · context |
| Candle | Overnight gap | -10.3% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2024-04-26 significant RISE (+10.2% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -2.74%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+24.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +10.1% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +9.9 | ✅ supports |
| Momentum | MACD hist | +0.621 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 2.69 | · context |
| Volume | Volume vs 20d | 2.2x | ✅ supports |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +13.0% / hi -1.6% | · context |
| Candle | Body / wicks | body 1.39%  up-wick 7%  lo-wick 45% | · context |
| Candle | Overnight gap | +11.8% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2024-04-26 13:45 px $172.78 (RSI 94, vol 0.8x)

### 2026-04-30 significant RISE (+10.0% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +3.43%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+36.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.4% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +11.2 | ✅ supports |
| Momentum | MACD hist | +3.929 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 1.14 | ❌ against |
| Volatility | ATR% | 2.65 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 90 | · context |
| Structure | Dist to 20d low/high | lo +24.8% / hi -0.3% | · context |
| Candle | Body / wicks | body 2.87%  up-wick 5%  lo-wick 41% | · context |
| Candle | Overnight gap | +6.9% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2026-05-01 13:50 px $382.14 (RSI 49, vol 0.7x)

### 2025-04-09 significant RISE (+9.7% close-to-close)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -3.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-7.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +0.2% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | +17.4 | ✅ supports |
| Momentum | MACD hist | -0.196 | ❌ against |
| Momentum | Stochastic %K | 60 | · context |
| Volatility | Bollinger %B | 0.49 | · context |
| Volatility | ATR% | 4.11 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 37 | · context |
| Structure | Dist to 20d low/high | lo +11.5% / hi -7.5% | · context |
| Candle | Body / wicks | body 9.89%  up-wick 5%  lo-wick 3% | · context |
| Candle | Patterns firing | marubozu, bullish_engulfing | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-09 14:15 px $145.51 (RSI 85, vol 0.8x)

### 2019-07-26 significant RISE (+9.6% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -3.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+9.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +9.0% | ❌ against |
| Momentum | RSI | 76 (overbought) | ❌ against |
| Momentum | RSI slope | +21.5 | ✅ supports |
| Momentum | MACD hist | +0.330 | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 1.36 | ❌ against |
| Volatility | ATR% | 2.05 | · context |
| Volume | Volume vs 20d | 3.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 59 | · context |
| Structure | Dist to 20d low/high | lo +13.8% / hi -1.9% | · context |
| Candle | Body / wicks | body 1.40%  up-wick 57%  lo-wick 0% | · context |
| Candle | Overnight gap | +8.1% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2023-10-25 significant DROP (-9.5% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +0.67%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -7.4% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -17.5 | ✅ supports |
| Momentum | MACD hist | -0.909 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.23 | ❌ against |
| Volatility | ATR% | 2.95 | · context |
| Volume | Volume vs 20d | 2.9x | ✅ supports |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +0.4% / hi -12.4% | · context |
| Candle | Body / wicks | body 1.99%  up-wick 5%  lo-wick 17% | · context |
| Candle | Overnight gap | -7.7% | ✅ supports |
| Candle | Patterns firing | double_top | · context |

- **5m confirmation:** VWAP loss at 2023-10-25 14:25 px $126.19 (RSI 13, vol 0.5x)

### 2020-03-13 significant RISE (+9.2% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -12.03%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -8.1% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | +6.1 | ✅ supports |
| Momentum | MACD hist | -1.107 | ❌ against |
| Momentum | Stochastic %K | 32 | · context |
| Volatility | Bollinger %B | 0.20 | ✅ supports |
| Volatility | ATR% | 4.91 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 27 | ✅ supports |
| Structure | Dist to 20d low/high | lo +8.7% / hi -26.1% | · context |
| Candle | Body / wicks | body 3.34%  up-wick 0%  lo-wick 61% | · context |
| Candle | Overnight gap | +5.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2015-07-17 GAP RISE (gap +13.0%, day +16.3%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -6.41%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+26.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +21.8% | ❌ against |
| Momentum | RSI | 89 (overbought) | ❌ against |
| Momentum | RSI slope | +19.2 | ✅ supports |
| Momentum | MACD hist | +0.616 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.44 | ❌ against |
| Volatility | ATR% | 2.39 | · context |
| Volume | Volume vs 20d | 4.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 86 | · context |
| Structure | Dist to 20d low/high | lo +22.9% / hi -0.5% | · context |
| Candle | Body / wicks | body 2.89%  up-wick 14%  lo-wick 8% | · context |
| Candle | Overnight gap | +13.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2011-07-15 GAP RISE (gap +13.0%, day +13.0%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +3.45%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.8% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +9.3 | ✅ supports |
| Momentum | MACD hist | +0.164 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.18 | ❌ against |
| Volatility | ATR% | 2.62 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 76 | · context |
| Structure | Dist to 20d low/high | lo +20.8% / hi -0.4% | · context |
| Candle | Body / wicks | body 0.02%  up-wick 22%  lo-wick 77% | · context |
| Candle | Overnight gap | +13.0% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2024-04-26 GAP RISE (gap +11.8%, day +10.2%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -2.74%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+24.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +10.1% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +9.9 | ✅ supports |
| Momentum | MACD hist | +0.621 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 2.69 | · context |
| Volume | Volume vs 20d | 2.2x | ✅ supports |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +13.0% / hi -1.6% | · context |
| Candle | Body / wicks | body 1.39%  up-wick 7%  lo-wick 45% | · context |
| Candle | Overnight gap | +11.8% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2024-04-26 13:45 px $172.78 (RSI 94, vol 0.8x)

### 2020-03-16 GAP DROP (gap -10.3%, day -11.6%)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: -1.76%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -17.3% | ❌ against |
| Momentum | RSI | 31 (neutral) | · context |
| Momentum | RSI slope | +4.3 | ❌ against |
| Momentum | MACD hist | -1.332 | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.01 | ❌ against |
| Volatility | ATR% | 6.14 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +0.6% / hi -42.7% | · context |
| Candle | Body / wicks | body 1.52%  up-wick 71%  lo-wick 8% | · context |
| Candle | Overnight gap | -10.3% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-10-23 GAP RISE (gap +10.1%, day +5.6%)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +2.51%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +6.2% | ❌ against |
| Momentum | RSI | 67 (neutral) | · context |
| Momentum | RSI slope | +15.8 | ✅ supports |
| Momentum | MACD hist | +0.129 | ✅ supports |
| Momentum | Stochastic %K | 66 | · context |
| Volatility | Bollinger %B | 1.00 | ❌ against |
| Volatility | ATR% | 2.70 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 76 | · context |
| Structure | Dist to 20d low/high | lo +14.1% / hi -4.6% | · context |
| Candle | Body / wicks | body 4.10%  up-wick 7%  lo-wick 4% | · context |
| Candle | Overnight gap | +10.1% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (52 fulfillments in 15y)

### 2026-04-24 bull_flag (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +11.99%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+23.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +6.1% | ❌ against |
| Momentum | RSI | 69 (neutral) | · context |
| Momentum | RSI slope | +2.3 | ✅ supports |
| Momentum | MACD hist | +2.614 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 0.80 | · context |
| Volatility | ATR% | 2.29 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 80 | · context |
| Structure | Dist to 20d low/high | lo +21.0% / hi -0.3% | · context |
| Candle | Body / wicks | body 1.67%  up-wick 9%  lo-wick 34% | · context |
| Candle | Patterns firing | bullish_engulfing, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-24 15:15 px $337.94 (RSI 81, vol 1.2x)

### 2026-02-02 bull_flag (long)

**Corroborating: 4  |  Contradicting: 4**  → next 5d: -5.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+34.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.1% | ❌ against |
| Momentum | RSI | 70 (overbought) | ❌ against |
| Momentum | RSI slope | +3.9 | ✅ supports |
| Momentum | MACD hist | +0.467 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 0.95 | ❌ against |
| Volatility | ATR% | 2.37 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +9.3% / hi -0.3% | · context |
| Candle | Body / wicks | body 2.22%  up-wick 12%  lo-wick 6% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | bullish_engulfing, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-02-03 14:50 px $346.32 (RSI 62, vol 0.9x)

### 2025-11-19 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +9.27%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+37.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +5.4% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +4.4 | ✅ supports |
| Momentum | MACD hist | -0.565 | ❌ against |
| Momentum | Stochastic %K | 67 | · context |
| Volatility | Bollinger %B | 0.84 | · context |
| Volatility | ATR% | 3.22 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 54 | · context |
| Structure | Dist to 20d low/high | lo +14.0% / hi -3.8% | · context |
| Candle | Body / wicks | body 1.97%  up-wick 64%  lo-wick 3% | · context |
| Candle | Overnight gap | +1.0% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-11-20 14:35 px $301.91 (RSI 76, vol 5.1x)

### Setup: double_bottom (131 fulfillments in 15y)

### 2026-04-13 double_bottom (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: +5.01%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+17.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +5.6% | ❌ against |
| Momentum | RSI | 64 (neutral) | · context |
| Momentum | RSI slope | +1.2 | ✅ supports |
| Momentum | MACD hist | +4.242 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 0.87 | · context |
| Volatility | ATR% | 2.62 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +15.3% / hi -0.2% | · context |
| Candle | Body / wicks | body 1.31%  up-wick 5%  lo-wick 27% | · context |
| Candle | Patterns firing | bullish_engulfing, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-13 13:45 px $317.40 (RSI 48, vol 0.5x)

### 2026-04-08 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +6.24%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +6.1% | ❌ against |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +11.1 | ✅ supports |
| Momentum | MACD hist | +3.048 | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 0.90 | ❌ against |
| Volatility | ATR% | 2.79 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 42 | · context |
| Structure | Dist to 20d low/high | lo +14.2% / hi -1.5% | · context |
| Candle | Body / wicks | body 0.98%  up-wick 23%  lo-wick 33% | · context |
| Candle | Overnight gap | +4.9% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-08 15:35 px $317.70 (RSI 55, vol 1.0x)

### 2025-10-16 double_bottom (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +0.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+28.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.0% | · context |
| Momentum | RSI | 63 (neutral) | · context |
| Momentum | RSI slope | +5.9 | ✅ supports |
| Momentum | MACD hist | -0.903 | ❌ against |
| Momentum | Stochastic %K | 74 | · context |
| Volatility | Bollinger %B | 0.78 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.35 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +6.2% / hi -2.2% | · context |
| Candle | Body / wicks | body 0.12%  up-wick 76%  lo-wick 20% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-16 14:20 px $255.25 (RSI 77, vol 0.8x)

### Setup: inverted_hammer (61 fulfillments in 15y)

### 2026-06-15 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: -6.29%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+19.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -0.2% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | +9.1 | ✅ supports |
| Momentum | MACD hist | -2.876 | ❌ against |
| Momentum | Stochastic %K | 48 | · context |
| Volatility | Bollinger %B | 0.39 | · context |
| Volatility | ATR% | 2.94 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 39 | · context |
| Structure | Dist to 20d low/high | lo +6.2% / hi -10.6% | · context |
| Candle | Body / wicks | body 0.39%  up-wick 57%  lo-wick 21% | · context |
| Candle | Overnight gap | +2.3% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-16 13:30 px $370.13 (RSI 48, vol 4.1x)

### 2026-03-10 inverted_hammer (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: +1.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+14.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.8% | · context |
| Momentum | RSI | 45 (neutral) | · context |
| Momentum | RSI slope | +10.5 | ✅ supports |
| Momentum | MACD hist | +0.015 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 51 | · context |
| Volatility | Bollinger %B | 0.48 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.71 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 53 | · context |
| Structure | Dist to 20d low/high | lo +4.2% / hi -4.8% | · context |
| Candle | Body / wicks | body 0.28%  up-wick 63%  lo-wick 15% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-10 14:30 px $307.64 (RSI 77, vol 0.7x)

### 2025-04-03 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 5**  → next 5d: +1.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-12.3%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -7.4% | · context |
| Momentum | RSI | 32 (neutral) | ✅ supports |
| Momentum | RSI slope | -5.4 | ❌ against |
| Momentum | MACD hist | -0.489 | ❌ against |
| Momentum | Stochastic %K | 2 | ✅ supports |
| Volatility | Bollinger %B | -0.03 | ✅ supports |
| Volatility | ATR% | 3.32 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 38 | · context |
| Structure | Dist to 20d low/high | lo +0.2% / hi -16.1% | ✅ supports |
| Candle | Body / wicks | body 0.26%  up-wick 70%  lo-wick 14% | · context |
| Candle | Overnight gap | -3.8% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-03 15:10 px $151.68 (RSI 47, vol 0.6x)

### Setup: bullish_harami (118 fulfillments in 15y)

### 2026-03-25 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +2.22%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.3% | · context |
| Momentum | RSI | 34 (neutral) | ✅ supports |
| Momentum | RSI slope | -8.5 | ❌ against |
| Momentum | MACD hist | -0.912 | ❌ against |
| Momentum | Stochastic %K | 7 | ✅ supports |
| Volatility | Bollinger %B | -0.07 | ✅ supports |
| Volatility | ATR% | 2.60 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +0.6% / hi -7.6% | ✅ supports |
| Candle | Body / wicks | body 0.86%  up-wick 38%  lo-wick 25% | · context |
| Candle | Overnight gap | +1.0% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2026-03-23 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -9.46%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -1.6% | · context |
| Momentum | RSI | 43 (neutral) | · context |
| Momentum | RSI slope | -4.6 | ❌ against |
| Momentum | MACD hist | +0.389 | ✅ supports |
| Momentum | Stochastic %K | 43 | · context |
| Volatility | Bollinger %B | 0.26 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.42 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +2.6% / hi -3.8% | · context |
| Candle | Body / wicks | body 0.02%  up-wick 77%  lo-wick 22% | · context |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-23 14:45 px $304.14 (RSI 63, vol 0.6x)

### 2026-03-16 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: -1.15%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+13.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.8% | · context |
| Momentum | RSI | 45 (neutral) | · context |
| Momentum | RSI slope | +3.0 | ✅ supports |
| Momentum | MACD hist | +0.463 | ✅ supports |
| Momentum | Stochastic %K | 59 | · context |
| Volatility | Bollinger %B | 0.46 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.55 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +3.8% / hi -4.6% | · context |
| Candle | Body / wicks | body 0.40%  up-wick 27%  lo-wick 38% | · context |
| Candle | Overnight gap | +0.7% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-16 16:50 px $304.41 (RSI 60, vol 0.8x)
