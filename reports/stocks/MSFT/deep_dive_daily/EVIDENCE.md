# MSFT — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **133/133** (100%)
- bearish_engulfing meets definition: **144/144** (100%)
- long candlesticks that are above 200-EMA: **525/715** (73%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=4.0%) the old open->close detector under-saw: **26/38** (68%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 26 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -4.3% · **close-to-close -9.5%** · gap -5.4% · RSI 33 · patterns —
- **2020-03-13** (COVID rebound): candle +7.7% · **close-to-close +14.2%** · gap +6.1% · RSI 46 · patterns —
- **2022-09-13** (CPI selloff): candle -2.6% · **close-to-close -5.5%** · gap -2.9% · RSI 36 · patterns ['evening_star', 'hs_top']
- **2025-04-03** (tariff crash): candle -0.4% · **close-to-close -2.4%** · gap -1.9% · RSI 36 · patterns —
- **2025-04-09** (tariff-pause rally): candle +10.5% · **close-to-close +10.1%** · gap -0.3% · RSI 54 · patterns ['marubozu', 'bullish_engulfing']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2020-03-16 significant DROP (-14.7% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +0.41%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -15.9% | ❌ against |
| Momentum | RSI | 37 (neutral) | · context |
| Momentum | RSI slope | +4.0 | ❌ against |
| Momentum | MACD hist | -3.037 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 7.53 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +0.3% / hi -39.0% | · context |
| Candle | Body / wicks | body 3.27%  up-wick 65%  lo-wick 3% | · context |
| Candle | Overnight gap | -11.9% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-13 significant RISE (+14.2% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -13.52%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.0% | · context |
| Momentum | RSI | 46 (neutral) | · context |
| Momentum | RSI slope | +6.6 | ✅ supports |
| Momentum | MACD hist | -2.271 | ❌ against |
| Momentum | Stochastic %K | 56 | · context |
| Volatility | Bollinger %B | 0.33 | · context |
| Volatility | ATR% | 5.76 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +12.7% / hi -18.5% | · context |
| Candle | Body / wicks | body 7.68%  up-wick 15%  lo-wick 32% | · context |
| Candle | Overnight gap | +6.1% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2013-07-19 significant DROP (-11.4% close-to-close)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: +0.70%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -9.4% | ❌ against |
| Momentum | RSI | 29 (oversold) | ❌ against |
| Momentum | RSI slope | -31.8 | ✅ supports |
| Momentum | MACD hist | -0.168 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 7 | · context |
| Volatility | Bollinger %B | -0.19 | ❌ against |
| Volatility | ATR% | 3.00 | · context |
| Volume | Volume vs 20d | 4.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 45 | · context |
| Structure | Dist to 20d low/high | lo +1.2% / hi -16.0% | · context |
| Candle | Body / wicks | body 3.09%  up-wick 16%  lo-wick 23% | · context |
| Candle | Overnight gap | -8.6% | ✅ supports |
| Candle | Patterns firing | double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-04-24 significant RISE (+10.5% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +1.65%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+10.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +12.1% | ❌ against |
| Momentum | RSI | 80 (overbought) | ❌ against |
| Momentum | RSI slope | +20.8 | ✅ supports |
| Momentum | MACD hist | +0.549 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.41 | ❌ against |
| Volatility | ATR% | 2.17 | · context |
| Volume | Volume vs 20d | 3.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 79 | · context |
| Structure | Dist to 20d low/high | lo +16.2% / hi -0.6% | · context |
| Candle | Body / wicks | body 4.84%  up-wick 11%  lo-wick 0% | · context |
| Candle | Overnight gap | +5.4% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-09 significant RISE (+10.1% close-to-close)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: -4.83%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +2.7% | · context |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | +24.7 | ✅ supports |
| Momentum | MACD hist | -0.368 | ❌ against |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.69 | · context |
| Volatility | ATR% | 3.49 | · context |
| Volume | Volume vs 20d | 1.9x | ✅ supports |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +11.7% / hi -1.5% | · context |
| Candle | Body / wicks | body 10.45%  up-wick 7%  lo-wick 1% | · context |
| Candle | Patterns firing | marubozu, bullish_engulfing | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-09 15:15 px $360.38 (RSI 75, vol 0.9x)

### 2015-10-23 significant RISE (+10.1% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -0.44%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+17.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +12.2% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +20.7 | ✅ supports |
| Momentum | MACD hist | +0.396 | ✅ supports |
| Momentum | Stochastic %K | 85 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 2.49 | · context |
| Volume | Volume vs 20d | 3.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 82 | · context |
| Structure | Dist to 20d low/high | lo +18.6% / hi -2.3% | · context |
| Candle | Body / wicks | body 1.09%  up-wick 66%  lo-wick 3% | · context |
| Candle | Overnight gap | +8.9% | ✅ supports |
| Candle | Patterns firing | shooting_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2026-01-29 significant DROP (-10.0% close-to-close)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: -9.19%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -7.2% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -21.9 | ✅ supports |
| Momentum | MACD hist | -0.189 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 20 | · context |
| Volatility | Bollinger %B | -0.10 | ❌ against |
| Volatility | ATR% | 3.10 | · context |
| Volume | Volume vs 20d | 4.0x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 44 | · context |
| Structure | Dist to 20d low/high | lo +2.9% / hi -13.0% | · context |
| Candle | Body / wicks | body 1.48%  up-wick 12%  lo-wick 58% | · context |
| Candle | Overnight gap | -8.6% | ✅ supports |
| Candle | Patterns firing | evening_star, double_top | · context |

- **5m confirmation:** VWAP loss at 2026-01-29 14:45 px $432.44 (RSI 94, vol 0.5x)

### 2020-03-12 significant DROP (-9.5% close-to-close)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +2.62%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -15.3% | ❌ against |
| Momentum | RSI | 33 (neutral) | · context |
| Momentum | RSI slope | -11.1 | ✅ supports |
| Momentum | MACD hist | -3.196 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.07 | ❌ against |
| Volatility | ATR% | 5.82 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 33 | · context |
| Structure | Dist to 20d low/high | lo +0.3% / hi -35.3% | · context |
| Candle | Body / wicks | body 4.29%  up-wick 55%  lo-wick 3% | · context |
| Candle | Overnight gap | -5.4% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-01-27 significant DROP (-9.3% close-to-close)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: -2.48%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-3.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -7.9% | ❌ against |
| Momentum | RSI | 31 (neutral) | · context |
| Momentum | RSI slope | -22.1 | ✅ supports |
| Momentum | MACD hist | -0.164 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 9 | · context |
| Volatility | Bollinger %B | -0.38 | ❌ against |
| Volatility | ATR% | 2.95 | · context |
| Volume | Volume vs 20d | 4.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +1.3% / hi -12.3% | · context |
| Candle | Body / wicks | body 0.68%  up-wick 23%  lo-wick 50% | · context |
| Candle | Overnight gap | -8.6% | ✅ supports |
| Candle | Patterns firing | double_top, double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-24 significant RISE (+9.1% close-to-close)

**Corroborating: 2  |  Contradicting: 3**  → next 5d: +6.32%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-0.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.6% | · context |
| Momentum | RSI | 46 (neutral) | · context |
| Momentum | RSI slope | +6.6 | ✅ supports |
| Momentum | MACD hist | -0.993 | ❌ against |
| Momentum | Stochastic %K | 41 | · context |
| Volatility | Bollinger %B | 0.39 | · context |
| Volatility | ATR% | 7.15 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 38 | · context |
| Structure | Dist to 20d low/high | lo +10.7% / hi -18.0% | · context |
| Candle | Body / wicks | body 3.19%  up-wick 15%  lo-wick 30% | · context |
| Candle | Overnight gap | +5.7% | ✅ supports |
| Candle | Patterns firing | morning_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2020-03-16 GAP DROP (gap -11.9%, day -14.7%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +0.41%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -15.9% | ❌ against |
| Momentum | RSI | 37 (neutral) | · context |
| Momentum | RSI slope | +4.0 | ❌ against |
| Momentum | MACD hist | -3.037 | ✅ supports |
| Momentum | Stochastic %K | 1 | · context |
| Volatility | Bollinger %B | -0.03 | ❌ against |
| Volatility | ATR% | 7.53 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +0.3% / hi -39.0% | · context |
| Candle | Body / wicks | body 3.27%  up-wick 65%  lo-wick 3% | · context |
| Candle | Overnight gap | -11.9% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-05-01 GAP RISE (gap +9.1%, day +7.6%)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +3.00%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+4.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +10.0% | ❌ against |
| Momentum | RSI | 69 (neutral) | · context |
| Momentum | RSI slope | +12.3 | ✅ supports |
| Momentum | MACD hist | +5.179 | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 1.16 | ❌ against |
| Volatility | ATR% | 3.24 | · context |
| Volume | Volume vs 20d | 2.0x | ✅ supports |
| Volume | MFI | 66 | · context |
| Structure | Dist to 20d low/high | lo +18.9% / hi -2.7% | · context |
| Candle | Body / wicks | body 1.32%  up-wick 49%  lo-wick 4% | · context |
| Candle | Overnight gap | +9.1% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-05-01 18:45 px $431.80 (RSI 58, vol 0.8x)

### 2015-10-23 GAP RISE (gap +8.9%, day +10.1%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -0.44%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+17.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +12.2% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +20.7 | ✅ supports |
| Momentum | MACD hist | +0.396 | ✅ supports |
| Momentum | Stochastic %K | 85 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 2.49 | · context |
| Volume | Volume vs 20d | 3.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 82 | · context |
| Structure | Dist to 20d low/high | lo +18.6% / hi -2.3% | · context |
| Candle | Body / wicks | body 1.09%  up-wick 66%  lo-wick 3% | · context |
| Candle | Overnight gap | +8.9% | ✅ supports |
| Candle | Patterns firing | shooting_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2026-01-29 GAP DROP (gap -8.6%, day -10.0%)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: -9.19%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -7.2% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -21.9 | ✅ supports |
| Momentum | MACD hist | -0.189 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 20 | · context |
| Volatility | Bollinger %B | -0.10 | ❌ against |
| Volatility | ATR% | 3.10 | · context |
| Volume | Volume vs 20d | 4.0x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 44 | · context |
| Structure | Dist to 20d low/high | lo +2.9% / hi -13.0% | · context |
| Candle | Body / wicks | body 1.48%  up-wick 12%  lo-wick 58% | · context |
| Candle | Overnight gap | -8.6% | ✅ supports |
| Candle | Patterns firing | evening_star, double_top | · context |

- **5m confirmation:** VWAP loss at 2026-01-29 14:45 px $432.44 (RSI 94, vol 0.5x)

### 2015-01-27 GAP DROP (gap -8.6%, day -9.3%)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: -2.48%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-3.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -7.9% | ❌ against |
| Momentum | RSI | 31 (neutral) | · context |
| Momentum | RSI slope | -22.1 | ✅ supports |
| Momentum | MACD hist | -0.164 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 9 | · context |
| Volatility | Bollinger %B | -0.38 | ❌ against |
| Volatility | ATR% | 2.95 | · context |
| Volume | Volume vs 20d | 4.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +1.3% / hi -12.3% | · context |
| Candle | Body / wicks | body 0.68%  up-wick 23%  lo-wick 50% | · context |
| Candle | Overnight gap | -8.6% | ✅ supports |
| Candle | Patterns firing | double_top, double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (30 fulfillments in 15y)

### 2024-07-02 bull_flag (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.52%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.6% | · context |
| Momentum | RSI | 71 (overbought) | ❌ against |
| Momentum | RSI slope | +8.7 | ✅ supports |
| Momentum | MACD hist | +0.825 | ✅ supports |
| Momentum | Stochastic %K | 99 | · context |
| Volatility | Bollinger %B | 0.86 | · context |
| Volatility | ATR% | 1.50 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 71 | · context |
| Structure | Dist to 20d low/high | lo +10.8% / hi -0.1% | · context |
| Candle | Body / wicks | body 1.34%  up-wick 5%  lo-wick 1% | · context |
| Candle | Overnight gap | -0.8% | ❌ against |
| Candle | Patterns firing | marubozu, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2024-07-02 16:45 px $456.22 (RSI 53, vol 0.2x)

### 2024-03-14 bull_flag (long)

**Corroborating: 7  |  Contradicting: 1**  → next 5d: +0.98%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.7% | · context |
| Momentum | RSI | 65 (neutral) | · context |
| Momentum | RSI slope | +6.9 | ✅ supports |
| Momentum | MACD hist | +0.680 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 1.17 | ❌ against |
| Volatility | ATR% | 1.75 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 61 | · context |
| Structure | Dist to 20d low/high | lo +6.6% / hi -0.6% | · context |
| Candle | Body / wicks | body 1.19%  up-wick 26%  lo-wick 23% | · context |
| Candle | Overnight gap | +1.2% | ✅ supports |
| Candle | Patterns firing | double_bottom, double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2024-03-14 13:55 px $422.71 (RSI 94, vol 0.7x)

### 2023-05-25 bull_flag (long)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: +2.91%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+20.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +4.9% | ❌ against |
| Momentum | RSI | 70 (overbought) | ❌ against |
| Momentum | RSI slope | +7.1 | ✅ supports |
| Momentum | MACD hist | +0.058 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 95 | · context |
| Volatility | Bollinger %B | 1.11 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 1.80 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 60 | · context |
| Structure | Dist to 20d low/high | lo +6.9% / hi -0.3% | · context |
| Candle | Body / wicks | body 0.83%  up-wick 14%  lo-wick 47% | · context |
| Candle | Overnight gap | +3.0% | ✅ supports |
| Candle | Patterns firing | morning_star, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2023-05-25 14:05 px $321.80 (RSI 83, vol 0.3x)

### Setup: double_bottom (130 fulfillments in 15y)

### 2026-05-29 double_bottom (long)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: -7.46%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +7.4% | ❌ against |
| Momentum | RSI | 70 (neutral) | · context |
| Momentum | RSI slope | +20.0 | ✅ supports |
| Momentum | MACD hist | +1.678 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.37 | ❌ against |
| Volatility | ATR% | 2.61 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 59 | · context |
| Structure | Dist to 20d low/high | lo +11.0% / hi -0.0% | · context |
| Candle | Body / wicks | body 4.09%  up-wick 1%  lo-wick 1% | · context |
| Candle | Overnight gap | +1.3% | ✅ supports |
| Candle | Patterns firing | marubozu, double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-29 14:25 px $439.89 (RSI 75, vol 0.5x)

### 2026-05-29 double_bottom (long)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: -7.46%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +7.4% | ❌ against |
| Momentum | RSI | 70 (neutral) | · context |
| Momentum | RSI slope | +20.0 | ✅ supports |
| Momentum | MACD hist | +1.678 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.37 | ❌ against |
| Volatility | ATR% | 2.61 | · context |
| Volume | Volume vs 20d | 2.3x | ✅ supports |
| Volume | MFI | 59 | · context |
| Structure | Dist to 20d low/high | lo +11.0% / hi -0.0% | · context |
| Candle | Body / wicks | body 4.09%  up-wick 1%  lo-wick 1% | · context |
| Candle | Overnight gap | +1.3% | ✅ supports |
| Candle | Patterns firing | marubozu, double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-29 14:25 px $439.89 (RSI 75, vol 0.5x)

### 2026-04-21 double_bottom (long)

**Corroborating: 2  |  Contradicting: 4**  → next 5d: +1.20%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.1%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +7.2% | ❌ against |
| Momentum | RSI | 70 (neutral) | · context |
| Momentum | RSI slope | -1.8 | ❌ against |
| Momentum | MACD hist | +7.157 | ✅ supports |
| Momentum | Stochastic %K | 89 | · context |
| Volatility | Bollinger %B | 0.95 | ❌ against |
| Volatility | ATR% | 2.29 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 78 | · context |
| Structure | Dist to 20d low/high | lo +16.0% / hi -1.7% | · context |
| Candle | Body / wicks | body 0.93%  up-wick 30%  lo-wick 30% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-21 17:20 px $424.41 (RSI 48, vol 0.9x)

### Setup: inverted_hammer (58 fulfillments in 15y)

### 2026-06-10 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 4**  → next 5d: -4.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-8.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -5.2% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | -5.9 | ❌ against |
| Momentum | MACD hist | -4.172 | ❌ against |
| Momentum | Stochastic %K | 0 | ✅ supports |
| Volatility | Bollinger %B | 0.11 | ✅ supports |
| Volatility | ATR% | 3.10 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +0.1% / hi -17.4% | ✅ supports |
| Candle | Body / wicks | body 0.30%  up-wick 82%  lo-wick 3% | · context |
| Candle | Overnight gap | -1.2% | ❌ against |
| Candle | Patterns firing | inverted_hammer, double_top, double_top | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-10 15:35 px $401.80 (RSI 78, vol 0.7x)

### 2026-02-27 inverted_hammer (long)

**Corroborating: 2  |  Contradicting: 4**  → next 5d: +4.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-15.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.9% | · context |
| Momentum | RSI | 36 (neutral) | ✅ supports |
| Momentum | RSI slope | -3.2 | ❌ against |
| Momentum | MACD hist | +1.707 | ✅ supports |
| Momentum | Stochastic %K | 26 | · context |
| Volatility | Bollinger %B | 0.26 | · context |
| Volatility | ATR% | 2.79 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 42 | · context |
| Structure | Dist to 20d low/high | lo +2.8% / hi -11.9% | · context |
| Candle | Body / wicks | body 0.48%  up-wick 59%  lo-wick 14% | · context |
| Candle | Overnight gap | -2.7% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-02-27 14:45 px $393.85 (RSI 78, vol 0.4x)

### 2026-02-20 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 5**  → next 5d: -1.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-15.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.9% | · context |
| Momentum | RSI | 32 (neutral) | ✅ supports |
| Momentum | RSI slope | -0.9 | ❌ against |
| Momentum | MACD hist | -0.144 | ❌ against |
| Momentum | Stochastic %K | 13 | ✅ supports |
| Volatility | Bollinger %B | 0.29 | · context |
| Volatility | ATR% | 2.77 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +1.2% / hi -21.8% | ✅ supports |
| Candle | Body / wicks | body 0.28%  up-wick 58%  lo-wick 19% | · context |
| Candle | Overnight gap | -0.6% | ❌ against |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-02-20 15:00 px $398.19 (RSI 93, vol 1.9x)

### Setup: bullish_harami (111 fulfillments in 15y)

### 2026-06-12 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -5.99%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-10.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -5.6% | · context |
| Momentum | RSI | 37 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.4 | ❌ against |
| Momentum | MACD hist | -5.406 | ❌ against |
| Momentum | Stochastic %K | 10 | ✅ supports |
| Volatility | Bollinger %B | 0.09 | ✅ supports |
| Volatility | ATR% | 3.12 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +2.2% / hi -19.3% | · context |
| Candle | Body / wicks | body 0.18%  up-wick 3%  lo-wick 89% | · context |
| Candle | Patterns firing | hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-12 14:30 px $384.40 (RSI 84, vol 0.6x)

### 2026-03-30 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: +3.71%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-20.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -6.8% | · context |
| Momentum | RSI | 25 (oversold) | ✅ supports |
| Momentum | RSI slope | -0.8 | ❌ against |
| Momentum | MACD hist | -2.947 | ❌ against |
| Momentum | Stochastic %K | 5 | ✅ supports |
| Volatility | Bollinger %B | 0.04 | ✅ supports |
| Volatility | ATR% | 2.44 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 28 | ✅ supports |
| Structure | Dist to 20d low/high | lo +0.7% / hi -15.1% | ✅ supports |
| Candle | Body / wicks | body 0.81%  up-wick 38%  lo-wick 30% | · context |
| Candle | Overnight gap | +1.4% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-30 13:50 px $360.97 (RSI 92, vol 0.6x)

### 2026-03-23 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: -6.28%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-15.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.9% | · context |
| Momentum | RSI | 33 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.6 | ❌ against |
| Momentum | MACD hist | -0.612 | ❌ against |
| Momentum | Stochastic %K | 9 | ✅ supports |
| Volatility | Bollinger %B | 0.04 | ✅ supports |
| Volatility | ATR% | 2.22 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 44 | · context |
| Structure | Dist to 20d low/high | lo +0.8% / hi -7.8% | ✅ supports |
| Candle | Body / wicks | body 0.23%  up-wick 60%  lo-wick 24% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-23 14:10 px $386.60 (RSI 54, vol 0.5x)
