# JPM — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **132/132** (100%)
- bearish_engulfing meets definition: **143/143** (100%)
- long candlesticks that are above 200-EMA: **484/675** (72%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=4.0%) the old open->close detector under-saw: **17/38** (45%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 17 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -1.7% · **close-to-close -8.2%** · gap -6.6% · RSI 23 · patterns —
- **2020-03-13** (COVID rebound): candle +8.3% · **close-to-close +18.0%** · gap +9.0% · RSI 40 · patterns —
- **2022-09-13** (CPI selloff): candle -1.4% · **close-to-close -3.5%** · gap -2.1% · RSI 49 · patterns —
- **2025-04-03** (tariff crash): candle -2.4% · **close-to-close -7.0%** · gap -4.7% · RSI 34 · patterns —
- **2025-04-09** (tariff-pause rally): candle +10.3% · **close-to-close +8.1%** · gap -2.0% · RSI 47 · patterns ['bullish_engulfing']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2020-03-13 significant RISE (+18.0% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -19.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-15.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -8.8% | · context |
| Momentum | RSI | 40 (neutral) | ✅ supports |
| Momentum | RSI slope | +13.6 | ✅ supports |
| Momentum | MACD hist | -2.432 | ❌ against |
| Momentum | Stochastic %K | 38 | · context |
| Volatility | Bollinger %B | 0.27 | · context |
| Volatility | ATR% | 6.30 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 20 | ✅ supports |
| Structure | Dist to 20d low/high | lo +16.9% / hi -33.2% | · context |
| Candle | Body / wicks | body 8.25%  up-wick 1%  lo-wick 33% | · context |
| Candle | Overnight gap | +9.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-16 significant DROP (-15.0% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -10.56%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-27.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -20.8% | ❌ against |
| Momentum | RSI | 32 (neutral) | · context |
| Momentum | RSI slope | +9.5 | ❌ against |
| Momentum | MACD hist | -2.563 | ✅ supports |
| Momentum | Stochastic %K | 9 | · context |
| Volatility | Bollinger %B | 0.08 | ❌ against |
| Volatility | ATR% | 8.44 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 20 | · context |
| Structure | Dist to 20d low/high | lo +4.3% / hi -56.6% | · context |
| Candle | Body / wicks | body 3.71%  up-wick 60%  lo-wick 7% | · context |
| Candle | Overnight gap | -18.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-09 significant DROP (-13.5% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -5.44%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-24.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -23.5% | ❌ against |
| Momentum | RSI | 18 (oversold) | ❌ against |
| Momentum | RSI slope | -11.0 | ✅ supports |
| Momentum | MACD hist | -3.185 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.16 | ❌ against |
| Volatility | ATR% | 5.58 | · context |
| Volume | Volume vs 20d | 2.1x | ✅ supports |
| Volume | MFI | 13 | · context |
| Structure | Dist to 20d low/high | lo +0.5% / hi -49.1% | · context |
| Candle | Body / wicks | body 3.24%  up-wick 43%  lo-wick 7% | · context |
| Candle | Overnight gap | -10.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-11-09 significant RISE (+13.5% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +0.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+13.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.4% | ❌ against |
| Momentum | RSI | 72 (overbought) | ❌ against |
| Momentum | RSI slope | +13.2 | ✅ supports |
| Momentum | MACD hist | +1.192 | ✅ supports |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 3.30 | · context |
| Volume | Volume vs 20d | 2.9x | ✅ supports |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +18.5% / hi -1.7% | · context |
| Candle | Body / wicks | body 3.31%  up-wick 23%  lo-wick 33% | · context |
| Candle | Overnight gap | +9.9% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-24 significant RISE (+11.9% close-to-close)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: +1.81%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-26.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -11.3% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | +6.2 | ✅ supports |
| Momentum | MACD hist | -0.980 | ❌ against |
| Momentum | Stochastic %K | 29 | · context |
| Volatility | Bollinger %B | 0.29 | · context |
| Volatility | ATR% | 9.30 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +13.0% / hi -45.8% | · context |
| Candle | Body / wicks | body 4.16%  up-wick 23%  lo-wick 28% | · context |
| Candle | Overnight gap | +7.4% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2024-11-06 significant RISE (+11.5% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -2.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+23.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +10.6% | ❌ against |
| Momentum | RSI | 76 (overbought) | ❌ against |
| Momentum | RSI slope | +26.2 | ✅ supports |
| Momentum | MACD hist | +0.969 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 97 | · context |
| Volatility | Bollinger %B | 1.45 | ❌ against |
| Volatility | ATR% | 2.24 | · context |
| Volume | Volume vs 20d | 2.8x | ✅ supports |
| Volume | MFI | 56 | · context |
| Structure | Dist to 20d low/high | lo +14.4% / hi -0.4% | · context |
| Candle | Body / wicks | body 5.13%  up-wick 7%  lo-wick 2% | · context |
| Candle | Overnight gap | +6.1% | ✅ supports |
| Candle | Patterns firing | marubozu, double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2024-11-06 15:15 px $240.59 (RSI 91, vol 0.7x)

### 2020-03-18 significant DROP (-10.5% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +9.35%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-31.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -21.9% | ❌ against |
| Momentum | RSI | 32 (neutral) | · context |
| Momentum | RSI slope | +0.3 | ❌ against |
| Momentum | MACD hist | -2.236 | ✅ supports |
| Momentum | Stochastic %K | 8 | · context |
| Volatility | Bollinger %B | 0.09 | ❌ against |
| Volatility | ATR% | 9.60 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +4.2% / hi -64.9% | · context |
| Candle | Body / wicks | body 4.31%  up-wick 30%  lo-wick 34% | · context |
| Candle | Overnight gap | -6.5% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2011-08-08 significant DROP (-9.4% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +8.28%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -13.8% | ❌ against |
| Momentum | RSI | 19 (oversold) | ❌ against |
| Momentum | RSI slope | -11.7 | ✅ supports |
| Momentum | MACD hist | -0.601 | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.31 | ❌ against |
| Volatility | ATR% | 3.79 | · context |
| Volume | Volume vs 20d | 2.5x | ✅ supports |
| Volume | MFI | 23 | · context |
| Structure | Dist to 20d low/high | lo +1.1% / hi -24.9% | · context |
| Candle | Body / wicks | body 5.99%  up-wick 37%  lo-wick 9% | · context |
| Candle | Overnight gap | -3.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2012-05-11 significant DROP (-9.3% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -9.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-5.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -12.1% | ❌ against |
| Momentum | RSI | 22 (oversold) | ❌ against |
| Momentum | RSI slope | -11.8 | ✅ supports |
| Momentum | MACD hist | -0.556 | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.35 | ❌ against |
| Volatility | ATR% | 3.28 | · context |
| Volume | Volume vs 20d | 5.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +0.9% / hi -19.7% | · context |
| Candle | Body / wicks | body 0.48%  up-wick 62%  lo-wick 25% | · context |
| Candle | Overnight gap | -8.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-04-17 significant RISE (+9.0% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -4.70%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.9%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +1.5% | · context |
| Momentum | RSI | 49 (neutral) | · context |
| Momentum | RSI slope | +4.1 | ✅ supports |
| Momentum | MACD hist | +1.538 | ✅ supports |
| Momentum | Stochastic %K | 57 | · context |
| Volatility | Bollinger %B | 0.69 | · context |
| Volatility | ATR% | 7.24 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +18.0% / hi -9.7% | · context |
| Candle | Body / wicks | body 3.46%  up-wick 11%  lo-wick 22% | · context |
| Candle | Overnight gap | +5.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2020-03-16 GAP DROP (gap -18.0%, day -15.0%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -10.56%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-27.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -20.8% | ❌ against |
| Momentum | RSI | 32 (neutral) | · context |
| Momentum | RSI slope | +9.5 | ❌ against |
| Momentum | MACD hist | -2.563 | ✅ supports |
| Momentum | Stochastic %K | 9 | · context |
| Volatility | Bollinger %B | 0.08 | ❌ against |
| Volatility | ATR% | 8.44 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 20 | · context |
| Structure | Dist to 20d low/high | lo +4.3% / hi -56.6% | · context |
| Candle | Body / wicks | body 3.71%  up-wick 60%  lo-wick 7% | · context |
| Candle | Overnight gap | -18.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-09 GAP DROP (gap -10.6%, day -13.5%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -5.44%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-24.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -23.5% | ❌ against |
| Momentum | RSI | 18 (oversold) | ❌ against |
| Momentum | RSI slope | -11.0 | ✅ supports |
| Momentum | MACD hist | -3.185 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.16 | ❌ against |
| Volatility | ATR% | 5.58 | · context |
| Volume | Volume vs 20d | 2.1x | ✅ supports |
| Volume | MFI | 13 | · context |
| Structure | Dist to 20d low/high | lo +0.5% / hi -49.1% | · context |
| Candle | Body / wicks | body 3.24%  up-wick 43%  lo-wick 7% | · context |
| Candle | Overnight gap | -10.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-11-09 GAP RISE (gap +9.9%, day +13.5%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +0.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+13.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.4% | ❌ against |
| Momentum | RSI | 72 (overbought) | ❌ against |
| Momentum | RSI slope | +13.2 | ✅ supports |
| Momentum | MACD hist | +1.192 | ✅ supports |
| Momentum | Stochastic %K | 92 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 3.30 | · context |
| Volume | Volume vs 20d | 2.9x | ✅ supports |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +18.5% / hi -1.7% | · context |
| Candle | Body / wicks | body 3.31%  up-wick 23%  lo-wick 33% | · context |
| Candle | Overnight gap | +9.9% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-13 GAP RISE (gap +9.0%, day +18.0%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -19.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-15.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -8.8% | · context |
| Momentum | RSI | 40 (neutral) | ✅ supports |
| Momentum | RSI slope | +13.6 | ✅ supports |
| Momentum | MACD hist | -2.432 | ❌ against |
| Momentum | Stochastic %K | 38 | · context |
| Volatility | Bollinger %B | 0.27 | · context |
| Volatility | ATR% | 6.30 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 20 | ✅ supports |
| Structure | Dist to 20d low/high | lo +16.9% / hi -33.2% | · context |
| Candle | Body / wicks | body 8.25%  up-wick 1%  lo-wick 33% | · context |
| Candle | Overnight gap | +9.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2012-05-11 GAP DROP (gap -8.8%, day -9.3%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -9.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-5.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -12.1% | ❌ against |
| Momentum | RSI | 22 (oversold) | ❌ against |
| Momentum | RSI slope | -11.8 | ✅ supports |
| Momentum | MACD hist | -0.556 | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.35 | ❌ against |
| Volatility | ATR% | 3.28 | · context |
| Volume | Volume vs 20d | 5.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 26 | · context |
| Structure | Dist to 20d low/high | lo +0.9% / hi -19.7% | · context |
| Candle | Body / wicks | body 0.48%  up-wick 62%  lo-wick 25% | · context |
| Candle | Overnight gap | -8.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (40 fulfillments in 15y)

### 2025-12-22 bull_flag (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +0.10%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+12.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.1% | · context |
| Momentum | RSI | 61 (neutral) | · context |
| Momentum | RSI slope | +8.7 | ✅ supports |
| Momentum | MACD hist | +0.738 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 0.91 | ❌ against |
| Volatility | ATR% | 2.03 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 66 | · context |
| Structure | Dist to 20d low/high | lo +8.8% / hi -0.0% | · context |
| Candle | Body / wicks | body 1.76%  up-wick 2%  lo-wick 0% | · context |
| Candle | Patterns firing | marubozu, double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-12-23 14:35 px $324.58 (RSI 82, vol 0.4x)

### 2025-07-23 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +0.97%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.4% | · context |
| Momentum | RSI | 69 (neutral) | · context |
| Momentum | RSI slope | +6.1 | ✅ supports |
| Momentum | MACD hist | -0.252 | ❌ against |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 1.01 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.76 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +5.5% / hi -0.1% | · context |
| Candle | Body / wicks | body 1.34%  up-wick 5%  lo-wick 7% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-07-23 13:45 px $294.02 (RSI 90, vol 1.1x)

### 2025-06-16 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +4.03%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+12.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +2.3% | · context |
| Momentum | RSI | 64 (neutral) | · context |
| Momentum | RSI slope | +0.1 | ✅ supports |
| Momentum | MACD hist | -0.375 | ❌ against |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.00 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.75 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +5.3% / hi -0.5% | · context |
| Candle | Body / wicks | body 1.26%  up-wick 28%  lo-wick 3% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-06-16 19:40 px $270.58 (RSI 46, vol 3.3x)

### Setup: double_bottom (125 fulfillments in 15y)

### 2026-06-04 double_bottom (long)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +0.84%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+4.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +2.7% | · context |
| Momentum | RSI | 58 (neutral) | · context |
| Momentum | RSI slope | +10.1 | ✅ supports |
| Momentum | MACD hist | +0.563 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 1.10 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.06 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +5.5% / hi -1.7% | · context |
| Candle | Body / wicks | body 1.68%  up-wick 24%  lo-wick 15% | · context |
| Candle | Overnight gap | +1.6% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-05 13:50 px $312.22 (RSI 57, vol 0.7x)

### 2026-04-08 double_bottom (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -0.66%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+4.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +4.7% | ❌ against |
| Momentum | RSI | 65 (neutral) | · context |
| Momentum | RSI slope | +12.0 | ✅ supports |
| Momentum | MACD hist | +2.393 | ✅ supports |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 1.20 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.40 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +9.4% / hi -1.1% | · context |
| Candle | Body / wicks | body 0.00%  up-wick 55%  lo-wick 45% | · context |
| Candle | Overnight gap | +3.6% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-08 17:55 px $307.76 (RSI 58, vol 1.2x)

### 2026-01-05 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -2.86%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+15.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.1% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +10.0 | ✅ supports |
| Momentum | MACD hist | +0.783 | ✅ supports |
| Momentum | Stochastic %K | 87 | · context |
| Volatility | Bollinger %B | 0.98 | ❌ against |
| Volatility | ATR% | 1.79 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 61 | · context |
| Structure | Dist to 20d low/high | lo +10.7% / hi -1.0% | · context |
| Candle | Body / wicks | body 2.62%  up-wick 27%  lo-wick 3% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-07 16:55 px $327.15 (RSI 50, vol 0.8x)

### Setup: inverted_hammer (71 fulfillments in 15y)

### 2026-03-13 inverted_hammer (long)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: +1.10%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.1%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.2% | · context |
| Momentum | RSI | 32 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.5 | ❌ against |
| Momentum | MACD hist | -1.498 | ❌ against |
| Momentum | Stochastic %K | 15 | ✅ supports |
| Volatility | Bollinger %B | 0.08 | ✅ supports |
| Volatility | ATR% | 2.78 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 33 | · context |
| Structure | Dist to 20d low/high | lo +1.5% / hi -10.2% | ✅ supports |
| Candle | Body / wicks | body 0.43%  up-wick 59%  lo-wick 12% | · context |
| Candle | Overnight gap | +0.6% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-13 13:50 px $286.56 (RSI 93, vol 1.8x)

### 2026-01-22 inverted_hammer (long)

**Corroborating: 7  |  Contradicting: 1**  → next 5d: +0.92%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -3.6% | · context |
| Momentum | RSI | 38 (neutral) | ✅ supports |
| Momentum | RSI slope | +1.4 | ✅ supports |
| Momentum | MACD hist | -3.154 | ❌ against |
| Momentum | Stochastic %K | 7 | ✅ supports |
| Volatility | Bollinger %B | 0.11 | ✅ supports |
| Volatility | ATR% | 2.24 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +0.8% / hi -11.1% | ✅ supports |
| Candle | Body / wicks | body 0.40%  up-wick 63%  lo-wick 14% | · context |
| Candle | Overnight gap | +0.9% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-22 15:00 px $305.91 (RSI 85, vol 1.4x)

### 2026-01-16 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: -3.66%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -2.2% | · context |
| Momentum | RSI | 44 (neutral) | · context |
| Momentum | RSI slope | +5.1 | ✅ supports |
| Momentum | MACD hist | -2.680 | ❌ against |
| Momentum | Stochastic %K | 20 | · context |
| Volatility | Bollinger %B | 0.19 | ✅ supports |
| Volatility | ATR% | 2.16 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +2.0% / hi -7.9% | · context |
| Candle | Body / wicks | body 0.68%  up-wick 66%  lo-wick 5% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-16 14:50 px $311.66 (RSI 95, vol 0.7x)

### Setup: bullish_harami (108 fulfillments in 15y)

### 2026-05-05 bullish_harami (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -1.46%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +0.3% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | -4.7 | ❌ against |
| Momentum | MACD hist | -0.720 | ❌ against |
| Momentum | Stochastic %K | 28 | · context |
| Volatility | Bollinger %B | 0.36 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.91 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 69 | · context |
| Structure | Dist to 20d low/high | lo +1.7% / hi -3.5% | ✅ supports |
| Candle | Body / wicks | body 0.55%  up-wick 38%  lo-wick 22% | · context |
| Candle | Patterns firing | bullish_harami, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-06 14:15 px $314.93 (RSI 69, vol 0.7x)

### 2026-03-30 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: +4.80%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-3.7%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.4% | · context |
| Momentum | RSI | 38 (neutral) | ✅ supports |
| Momentum | RSI slope | -7.8 | ❌ against |
| Momentum | MACD hist | +0.447 | ✅ supports |
| Momentum | Stochastic %K | 25 | · context |
| Volatility | Bollinger %B | 0.22 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.50 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +1.6% / hi -6.6% | ✅ supports |
| Candle | Body / wicks | body 0.34%  up-wick 51%  lo-wick 29% | · context |
| Candle | Overnight gap | +0.7% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-30 16:10 px $286.15 (RSI 46, vol 0.7x)

### 2025-10-23 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +5.06%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -2.6% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.1 | ❌ against |
| Momentum | MACD hist | -1.664 | ❌ against |
| Momentum | Stochastic %K | 19 | ✅ supports |
| Volatility | Bollinger %B | 0.11 | ✅ supports |
| Volatility | ATR% | 2.25 | · context |
| Volume | Volume vs 20d | 0.6x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +1.4% / hi -8.0% | ✅ supports |
| Candle | Body / wicks | body 0.05%  up-wick 47%  lo-wick 48% | · context |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-23 14:45 px $295.53 (RSI 85, vol 0.1x)
