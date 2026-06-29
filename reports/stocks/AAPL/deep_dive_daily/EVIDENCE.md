# AAPL — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **128/128** (100%)
- bearish_engulfing meets definition: **151/151** (100%)
- long candlesticks that are above 200-EMA: **488/667** (73%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=4.7%) the old open->close detector under-saw: **25/38** (66%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 25 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -3.0% · **close-to-close -9.9%** · gap -7.1% · RSI 34 · patterns —
- **2020-03-13** (COVID rebound): candle +4.9% · **close-to-close +12.0%** · gap +6.7% · RSI 45 · patterns —
- **2022-09-13** (CPI selloff): candle -3.8% · **close-to-close -5.9%** · gap -2.2% · RSI 41 · patterns —
- **2025-04-03** (tariff crash): candle -1.1% · **close-to-close -9.2%** · gap -8.2% · RSI 32 · patterns ['bear_flag']
- **2025-04-09** (tariff-pause rally): candle +15.6% · **close-to-close +15.3%** · gap -0.3% · RSI 42 · patterns ['marubozu', 'bullish_engulfing']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2025-04-09 significant RISE (+15.3% close-to-close)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -2.30%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-10.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -5.1% | · context |
| Momentum | RSI | 42 (neutral) | · context |
| Momentum | RSI slope | +19.1 | ✅ supports |
| Momentum | MACD hist | -3.136 | ❌ against |
| Momentum | Stochastic %K | 53 | · context |
| Volatility | Bollinger %B | 0.30 | · context |
| Volatility | ATR% | 5.45 | · context |
| Volume | Volume vs 20d | 2.6x | ✅ supports |
| Volume | MFI | 50 | · context |
| Structure | Dist to 20d low/high | lo +14.9% / hi -13.5% | · context |
| Candle | Body / wicks | body 15.64%  up-wick 6%  lo-wick 0% | · context |
| Candle | Patterns firing | marubozu, bullish_engulfing | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-09 14:55 px $177.72 (RSI 82, vol 0.7x)

### 2020-03-16 significant DROP (-12.9% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -7.37%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -14.8% | ❌ against |
| Momentum | RSI | 37 (neutral) | · context |
| Momentum | RSI slope | +3.2 | ❌ against |
| Momentum | MACD hist | -1.025 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 7.23 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +0.9% / hi -34.0% | · context |
| Candle | Body / wicks | body 0.11%  up-wick 88%  lo-wick 10% | · context |
| Candle | Overnight gap | -13.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2013-01-24 significant DROP (-12.4% close-to-close)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +1.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-19.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -11.6% | ❌ against |
| Momentum | RSI | 30 (neutral) | · context |
| Momentum | RSI slope | -12.3 | ✅ supports |
| Momentum | MACD hist | -0.101 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | -0.25 | ❌ against |
| Volatility | ATR% | 3.85 | · context |
| Volume | Volume vs 20d | 2.5x | ✅ supports |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +0.1% / hi -23.2% | · context |
| Candle | Body / wicks | body 2.07%  up-wick 37%  lo-wick 2% | · context |
| Candle | Overnight gap | -10.5% | ✅ supports |
| Candle | Patterns firing | bear_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-13 significant RISE (+12.0% close-to-close)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -17.53%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.7% | · context |
| Momentum | RSI | 45 (neutral) | · context |
| Momentum | RSI slope | +4.1 | ✅ supports |
| Momentum | MACD hist | -0.693 | ❌ against |
| Momentum | Stochastic %K | 54 | · context |
| Volatility | Bollinger %B | 0.32 | · context |
| Volatility | ATR% | 5.73 | · context |
| Volume | Volume vs 20d | 1.5x | ✅ supports |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +10.8% / hi -17.3% | · context |
| Candle | Body / wicks | body 4.94%  up-wick 7%  lo-wick 44% | · context |
| Candle | Overnight gap | +6.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-07-31 significant RISE (+10.5% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +4.57%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+40.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +11.4% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +17.9 | ✅ supports |
| Momentum | MACD hist | +0.142 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 1.37 | ❌ against |
| Volatility | ATR% | 2.81 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +16.1% / hi -0.1% | · context |
| Candle | Body / wicks | body 3.28%  up-wick 3%  lo-wick 37% | · context |
| Candle | Overnight gap | +7.0% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-24 significant RISE (+10.0% close-to-close)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: +3.00%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-3.9%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -6.6% | · context |
| Momentum | RSI | 43 (neutral) | · context |
| Momentum | RSI slope | +7.3 | ✅ supports |
| Momentum | MACD hist | -0.770 | ❌ against |
| Momentum | Stochastic %K | 39 | · context |
| Volatility | Bollinger %B | 0.28 | · context |
| Volatility | ATR% | 7.22 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 36 | · context |
| Structure | Dist to 20d low/high | lo +13.9% / hi -23.1% | · context |
| Candle | Body / wicks | body 4.45%  up-wick 6%  lo-wick 15% | · context |
| Candle | Overnight gap | +5.3% | ✅ supports |
| Candle | Patterns firing | morning_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2019-01-03 significant DROP (-10.0% close-to-close)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: +8.17%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-24.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -12.1% | ❌ against |
| Momentum | RSI | 28 (oversold) | ❌ against |
| Momentum | RSI slope | -9.9 | ✅ supports |
| Momentum | MACD hist | +0.021 | ❌ against |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.04 | ❌ against |
| Volatility | ATR% | 4.66 | · context |
| Volume | Volume vs 20d | 1.9x | ✅ supports |
| Volume | MFI | 36 | · context |
| Structure | Dist to 20d low/high | lo +0.1% / hi -28.3% | · context |
| Candle | Body / wicks | body 1.24%  up-wick 47%  lo-wick 5% | · context |
| Candle | Overnight gap | -8.8% | ✅ supports |
| Candle | Patterns firing | bear_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-12 significant DROP (-9.9% close-to-close)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: -1.39%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-3.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -14.3% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -10.7 | ✅ supports |
| Momentum | MACD hist | -0.988 | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | -0.04 | ❌ against |
| Volatility | ATR% | 5.93 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 36 | · context |
| Structure | Dist to 20d low/high | lo +0.1% / hi -31.4% | · context |
| Candle | Body / wicks | body 3.01%  up-wick 64%  lo-wick 1% | · context |
| Candle | Overnight gap | -7.1% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-02 significant RISE (+9.3% close-to-close)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: -10.92%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -1.7% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | +17.9 | ✅ supports |
| Momentum | MACD hist | -1.182 | ❌ against |
| Momentum | Stochastic %K | 60 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | ATR% | 3.95 | · context |
| Volume | Volume vs 20d | 2.0x | ✅ supports |
| Volume | MFI | 33 | · context |
| Structure | Dist to 20d low/high | lo +14.2% / hi -9.5% | · context |
| Candle | Body / wicks | body 5.86%  up-wick 11%  lo-wick 19% | · context |
| Candle | Overnight gap | +3.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-03 significant DROP (-9.2% close-to-close)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: -6.28%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -8.2% | ❌ against |
| Momentum | RSI | 32 (neutral) | · context |
| Momentum | RSI slope | -16.2 | ✅ supports |
| Momentum | MACD hist | -0.044 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 8 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 3.49 | · context |
| Volume | Volume vs 20d | 1.9x | ✅ supports |
| Volume | MFI | 69 | · context |
| Structure | Dist to 20d low/high | lo +1.0% / hi -18.8% | · context |
| Candle | Body / wicks | body 1.14%  up-wick 31%  lo-wick 31% | · context |
| Candle | Overnight gap | -8.2% | ✅ supports |
| Candle | Patterns firing | bear_flag | · context |

- **5m confirmation:** VWAP loss at 2025-04-03 13:35 px $204.54 (RSI 0, vol 0.7x)

## 3. Gap events (overnight gaps the old detector missed)

### 2020-03-16 GAP DROP (gap -13.0%, day -12.9%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -7.37%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -14.8% | ❌ against |
| Momentum | RSI | 37 (neutral) | · context |
| Momentum | RSI slope | +3.2 | ❌ against |
| Momentum | MACD hist | -1.025 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 7.23 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +0.9% / hi -34.0% | · context |
| Candle | Body / wicks | body 0.11%  up-wick 88%  lo-wick 10% | · context |
| Candle | Overnight gap | -13.0% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2013-01-24 GAP DROP (gap -10.5%, day -12.4%)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +1.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-19.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -11.6% | ❌ against |
| Momentum | RSI | 30 (neutral) | · context |
| Momentum | RSI slope | -12.3 | ✅ supports |
| Momentum | MACD hist | -0.101 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 0 | · context |
| Volatility | Bollinger %B | -0.25 | ❌ against |
| Volatility | ATR% | 3.85 | · context |
| Volume | Volume vs 20d | 2.5x | ✅ supports |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +0.1% / hi -23.2% | · context |
| Candle | Body / wicks | body 2.07%  up-wick 37%  lo-wick 2% | · context |
| Candle | Overnight gap | -10.5% | ✅ supports |
| Candle | Patterns firing | bear_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-08-24 GAP DROP (gap -10.3%, day -2.5%)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +9.35%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-13.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -10.6% | ❌ against |
| Momentum | RSI | 24 (oversold) | ❌ against |
| Momentum | RSI slope | -11.0 | ✅ supports |
| Momentum | MACD hist | -0.249 | ✅ supports |
| Momentum | Stochastic %K | 40 | · context |
| Volatility | Bollinger %B | -0.13 | ❌ against |
| Volatility | ATR% | 4.03 | · context |
| Volume | Volume vs 20d | 2.4x | ✅ supports |
| Volume | MFI | 28 | · context |
| Structure | Dist to 20d low/high | lo +10.8% / hi -20.2% | · context |
| Candle | Body / wicks | body 8.70%  up-wick 34%  lo-wick 17% | · context |
| Candle | Overnight gap | -10.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2012-04-25 GAP RISE (gap +9.9%, day +8.9%)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: -3.94%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+31.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +2.4% | · context |
| Momentum | RSI | 55 (neutral) | · context |
| Momentum | RSI slope | +13.4 | ✅ supports |
| Momentum | MACD hist | -0.241 | ❌ against |
| Momentum | Stochastic %K | 62 | · context |
| Volatility | Bollinger %B | 0.53 | · context |
| Volatility | ATR% | 3.36 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 35 | · context |
| Structure | Dist to 20d low/high | lo +9.0% / hi -5.6% | · context |
| Candle | Body / wicks | body 0.92%  up-wick 20%  lo-wick 33% | · context |
| Candle | Overnight gap | +9.9% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2024-08-05 GAP DROP (gap -9.4%, day -4.8%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +3.95%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+8.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -4.7% | ❌ against |
| Momentum | RSI | 38 (neutral) | · context |
| Momentum | RSI slope | -10.5 | ✅ supports |
| Momentum | MACD hist | -2.138 | ✅ supports |
| Momentum | Stochastic %K | 37 | · context |
| Volatility | Bollinger %B | -0.04 | ❌ against |
| Volatility | ATR% | 3.22 | · context |
| Volume | Volume vs 20d | 2.1x | ✅ supports |
| Volume | MFI | 35 | · context |
| Structure | Dist to 20d low/high | lo +6.3% / hi -13.4% | · context |
| Candle | Body / wicks | body 5.11%  up-wick 24%  lo-wick 18% | · context |
| Candle | Overnight gap | -9.4% | ✅ supports |
| Candle | Patterns firing | hs_top, bear_flag | · context |

- **5m confirmation:** VWAP loss at 2024-08-05 18:40 px $207.48 (RSI 36, vol 3.4x)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (59 fulfillments in 15y)

### 2026-05-01 bull_flag (long)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +4.70%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.8% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +8.9 | ✅ supports |
| Momentum | MACD hist | +0.908 | ✅ supports |
| Momentum | Stochastic %K | 76 | · context |
| Volatility | Bollinger %B | 1.00 | ❌ against |
| Volatility | ATR% | 2.36 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 77 | · context |
| Structure | Dist to 20d low/high | lo +12.3% / hi -2.5% | · context |
| Candle | Body / wicks | body 0.46%  up-wick 80%  lo-wick 6% | · context |
| Candle | Overnight gap | +2.8% | ✅ supports |
| Candle | Patterns firing | shooting_star, double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-01 14:45 px $283.14 (RSI 61, vol 0.4x)

### 2025-11-26 bull_flag (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+17.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +2.7% | · context |
| Momentum | RSI | 67 (neutral) | · context |
| Momentum | RSI slope | +1.8 | ✅ supports |
| Momentum | MACD hist | -0.036 | ❌ against |
| Momentum | Stochastic %K | 81 | · context |
| Volatility | Bollinger %B | 0.99 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.03 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 65 | · context |
| Structure | Dist to 20d low/high | lo +4.4% / hi -1.0% | · context |
| Candle | Body / wicks | body 0.21%  up-wick 68%  lo-wick 11% | · context |
| Candle | Patterns firing | shooting_star, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-11-26 19:55 px $278.43 (RSI 49, vol 1.3x)

### 2025-10-20 bull_flag (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +2.51%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.5% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +16.4 | ✅ supports |
| Momentum | MACD hist | -0.693 | ❌ against |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.98 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.05 | · context |
| Volume | Volume vs 20d | 2.0x | ✅ supports |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +7.0% / hi -0.8% | · context |
| Candle | Body / wicks | body 2.48%  up-wick 24%  lo-wick 3% | · context |
| Candle | Overnight gap | +1.4% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-21 13:55 px $263.81 (RSI 53, vol 1.3x)

### Setup: double_bottom (94 fulfillments in 15y)

### 2026-05-01 double_bottom (long)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +4.70%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.8% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +8.9 | ✅ supports |
| Momentum | MACD hist | +0.908 | ✅ supports |
| Momentum | Stochastic %K | 76 | · context |
| Volatility | Bollinger %B | 1.00 | ❌ against |
| Volatility | ATR% | 2.36 | · context |
| Volume | Volume vs 20d | 1.7x | ✅ supports |
| Volume | MFI | 77 | · context |
| Structure | Dist to 20d low/high | lo +12.3% / hi -2.5% | · context |
| Candle | Body / wicks | body 0.46%  up-wick 80%  lo-wick 6% | · context |
| Candle | Overnight gap | +2.8% | ✅ supports |
| Candle | Patterns firing | shooting_star, double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-01 14:45 px $283.14 (RSI 61, vol 0.4x)

### 2026-04-15 double_bottom (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: +2.53%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +3.4% | · context |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +8.6 | ✅ supports |
| Momentum | MACD hist | +1.561 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 1.07 | ❌ against |
| Volatility | ATR% | 2.21 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 63 | · context |
| Structure | Dist to 20d low/high | lo +7.9% / hi -0.0% | · context |
| Candle | Body / wicks | body 3.20%  up-wick 1%  lo-wick 4% | · context |
| Candle | Patterns firing | marubozu, bullish_engulfing, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-15 14:00 px $259.10 (RSI 78, vol 0.5x)

### 2026-04-06 double_bottom (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +0.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +1.6% | · context |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | +4.5 | ✅ supports |
| Momentum | MACD hist | +1.144 | ✅ supports |
| Momentum | Stochastic %K | 80 | · context |
| Volatility | Bollinger %B | 0.82 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.18 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 45 | · context |
| Structure | Dist to 20d low/high | lo +5.2% / hi -1.4% | · context |
| Candle | Body / wicks | body 0.92%  up-wick 58%  lo-wick 1% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-07 16:00 px $249.29 (RSI 53, vol 1.4x)

### Setup: inverted_hammer (60 fulfillments in 15y)

### 2026-03-24 inverted_hammer (long)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: +0.85%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -1.8% | · context |
| Momentum | RSI | 41 (neutral) | · context |
| Momentum | RSI slope | +6.0 | ✅ supports |
| Momentum | MACD hist | -0.721 | ❌ against |
| Momentum | Stochastic %K | 34 | · context |
| Volatility | Bollinger %B | 0.28 | · context |
| Volatility | ATR% | 2.21 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 35 | · context |
| Structure | Dist to 20d low/high | lo +2.2% / hi -9.7% | · context |
| Candle | Body / wicks | body 0.52%  up-wick 60%  lo-wick 15% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | inverted_hammer, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-24 17:55 px $253.21 (RSI 52, vol 1.8x)

### 2026-01-27 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +4.34%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.2% | · context |
| Momentum | RSI | 46 (neutral) | · context |
| Momentum | RSI slope | +23.3 | ✅ supports |
| Momentum | MACD hist | -0.106 | ❌ against |
| Momentum | Stochastic %K | 73 | · context |
| Volatility | Bollinger %B | 0.45 | · context |
| Volatility | ATR% | 2.03 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 40 | · context |
| Structure | Dist to 20d low/high | lo +5.7% / hi -7.6% | · context |
| Candle | Body / wicks | body 0.35%  up-wick 74%  lo-wick 2% | · context |
| Candle | Overnight gap | +1.5% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-27 16:00 px $260.78 (RSI 74, vol 0.3x)

### 2026-01-22 inverted_hammer (long)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +4.00%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.6% | · context |
| Momentum | RSI | 23 (oversold) | ✅ supports |
| Momentum | RSI slope | +4.7 | ✅ supports |
| Momentum | MACD hist | -1.673 | ❌ against |
| Momentum | Stochastic %K | 14 | ✅ supports |
| Volatility | Bollinger %B | 0.10 | ✅ supports |
| Volatility | ATR% | 1.97 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 30 | · context |
| Structure | Dist to 20d low/high | lo +2.0% / hi -11.9% | ✅ supports |
| Candle | Body / wicks | body 0.34%  up-wick 63%  lo-wick 7% | · context |
| Candle | Overnight gap | +0.6% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### Setup: bullish_harami (105 fulfillments in 15y)

### 2026-06-10 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +1.50%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -3.0% | · context |
| Momentum | RSI | 44 (neutral) | · context |
| Momentum | RSI slope | -9.5 | ❌ against |
| Momentum | MACD hist | -3.333 | ❌ against |
| Momentum | Stochastic %K | 14 | ✅ supports |
| Volatility | Bollinger %B | 0.04 | ✅ supports |
| Volatility | ATR% | 2.50 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +1.4% / hi -8.9% | ✅ supports |
| Candle | Body / wicks | body 0.29%  up-wick 43%  lo-wick 46% | · context |
| Candle | Patterns firing | bullish_harami, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-10 13:55 px $289.49 (RSI 86, vol 0.7x)

### 2026-03-16 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -0.53%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.1% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | -1.1 | ❌ against |
| Momentum | MACD hist | -1.454 | ❌ against |
| Momentum | Stochastic %K | 12 | ✅ supports |
| Volatility | Bollinger %B | 0.10 | ✅ supports |
| Volatility | ATR% | 2.37 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 36 | · context |
| Structure | Dist to 20d low/high | lo +1.3% / hi -9.2% | ✅ supports |
| Candle | Body / wicks | body 0.28%  up-wick 27%  lo-wick 56% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | bullish_harami, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-16 16:45 px $252.77 (RSI 55, vol 0.7x)

### 2026-01-21 bullish_harami (long)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +3.55%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -5.4% | · context |
| Momentum | RSI | 21 (oversold) | ✅ supports |
| Momentum | RSI slope | -4.6 | ❌ against |
| Momentum | MACD hist | -1.763 | ❌ against |
| Momentum | Stochastic %K | 12 | ✅ supports |
| Volatility | Bollinger %B | 0.02 | ✅ supports |
| Volatility | ATR% | 2.02 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 25 | ✅ supports |
| Structure | Dist to 20d low/high | lo +1.7% / hi -12.2% | ✅ supports |
| Candle | Body / wicks | body 0.42%  up-wick 45%  lo-wick 39% | · context |
| Candle | Overnight gap | +0.8% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-21 15:15 px $247.11 (RSI 46, vol 0.5x)
