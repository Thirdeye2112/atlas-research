# NVDA — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **129/129** (100%)
- bearish_engulfing meets definition: **162/162** (100%)
- long candlesticks that are above 200-EMA: **432/639** (68%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=6.4%) the old open->close detector under-saw: **20/38** (53%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 20 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -4.1% · **close-to-close -12.2%** · gap -8.5% · RSI 36 · patterns —
- **2020-03-13** (COVID rebound): candle +4.5% · **close-to-close +11.3%** · gap +6.6% · RSI 45 · patterns —
- **2022-09-13** (CPI selloff): candle -4.9% · **close-to-close -9.5%** · gap -4.8% · RSI 31 · patterns ['bear_flag']
- **2025-04-03** (tariff crash): candle -1.7% · **close-to-close -7.8%** · gap -6.3% · RSI 33 · patterns ['bear_flag']
- **2025-04-09** (tariff-pause rally): candle +15.6% · **close-to-close +18.7%** · gap +2.7% · RSI 52 · patterns —

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2016-11-11 significant RISE (+29.8% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: +6.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+67.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +24.4% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +22.7 | ✅ supports |
| Momentum | MACD hist | +0.023 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.46 | ❌ against |
| Volatility | ATR% | 4.02 | · context |
| Volume | Volume vs 20d | 4.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 58 | · context |
| Structure | Dist to 20d low/high | lo +25.5% / hi -0.9% | · context |
| Candle | Body / wicks | body 10.64%  up-wick 8%  lo-wick 10% | · context |
| Candle | Overnight gap | +17.3% | ✅ supports |
| Candle | Patterns firing | hs_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2023-05-25 significant RISE (+24.4% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +3.55%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+70.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +25.8% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +18.7 | ✅ supports |
| Momentum | MACD hist | +0.550 | ✅ supports |
| Momentum | Stochastic %K | 87 | · context |
| Volatility | Bollinger %B | 1.40 | ❌ against |
| Volatility | ATR% | 3.83 | · context |
| Volume | Volume vs 20d | 3.3x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 62 | · context |
| Structure | Dist to 20d low/high | lo +28.7% / hi -3.9% | · context |
| Candle | Body / wicks | body 1.41%  up-wick 34%  lo-wick 47% | · context |
| Candle | Overnight gap | +26.1% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2018-11-16 significant DROP (-18.8% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -6.92%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-30.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -20.8% | ❌ against |
| Momentum | RSI | 29 (oversold) | ❌ against |
| Momentum | RSI slope | -9.0 | ✅ supports |
| Momentum | MACD hist | -0.029 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 5 | · context |
| Volatility | Bollinger %B | -0.20 | ❌ against |
| Volatility | ATR% | 8.49 | · context |
| Volume | Volume vs 20d | 2.9x | ✅ supports |
| Volume | MFI | 61 | · context |
| Structure | Dist to 20d low/high | lo +1.7% / hi -43.1% | · context |
| Candle | Body / wicks | body 0.68%  up-wick 69%  lo-wick 19% | · context |
| Candle | Overnight gap | -19.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-09 significant RISE (+18.7% close-to-close)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -8.61%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +4.0% | · context |
| Momentum | RSI | 52 (neutral) | · context |
| Momentum | RSI slope | +18.6 | ✅ supports |
| Momentum | MACD hist | -0.350 | ❌ against |
| Momentum | Stochastic %K | 78 | · context |
| Volatility | Bollinger %B | 0.57 | · context |
| Volatility | ATR% | 6.90 | · context |
| Volume | Volume vs 20d | 1.9x | ✅ supports |
| Volume | MFI | 38 | · context |
| Structure | Dist to 20d low/high | lo +24.2% / hi -7.5% | · context |
| Candle | Body / wicks | body 15.61%  up-wick 4%  lo-wick 8% | · context |
| Candle | Overnight gap | +2.7% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2025-04-09 13:45 px $99.49 (RSI 97, vol 0.6x)

### 2020-03-16 significant DROP (-18.5% close-to-close)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +8.29%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -22.4% | ❌ against |
| Momentum | RSI | 35 (neutral) | · context |
| Momentum | RSI slope | -0.7 | ✅ supports |
| Momentum | MACD hist | -0.203 | ✅ supports |
| Momentum | Stochastic %K | 3 | · context |
| Volatility | Bollinger %B | -0.11 | ❌ against |
| Volatility | ATR% | 9.96 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +1.2% / hi -61.1% | · context |
| Candle | Body / wicks | body 7.54%  up-wick 43%  lo-wick 7% | · context |
| Candle | Overnight gap | -11.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2017-05-10 significant RISE (+17.8% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +5.30%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+36.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +15.6% | ❌ against |
| Momentum | RSI | 76 (overbought) | ❌ against |
| Momentum | RSI slope | +27.4 | ✅ supports |
| Momentum | MACD hist | +0.031 | ✅ supports |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 1.38 | ❌ against |
| Volatility | ATR% | 2.90 | · context |
| Volume | Volume vs 20d | 4.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 74 | · context |
| Structure | Dist to 20d low/high | lo +21.3% / hi -0.4% | · context |
| Candle | Body / wicks | body 6.12%  up-wick 7%  lo-wick 3% | · context |
| Candle | Overnight gap | +11.0% | ✅ supports |
| Candle | Patterns firing | hs_bottom, bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2020-03-24 significant RISE (+17.2% close-to-close)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: +5.79%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+14.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +5.0% | ❌ against |
| Momentum | RSI | 52 (neutral) | · context |
| Momentum | RSI slope | +11.6 | ✅ supports |
| Momentum | MACD hist | -0.044 | ❌ against |
| Momentum | Stochastic %K | 67 | · context |
| Volatility | Bollinger %B | 0.55 | · context |
| Volatility | ATR% | 9.19 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +27.5% / hi -14.3% | · context |
| Candle | Body / wicks | body 8.81%  up-wick 14%  lo-wick 4% | · context |
| Candle | Overnight gap | +7.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-01-27 significant DROP (-17.0% close-to-close)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: -1.49%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-1.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -13.9% | ❌ against |
| Momentum | RSI | 34 (neutral) | · context |
| Momentum | RSI slope | -25.5 | ✅ supports |
| Momentum | MACD hist | -0.756 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 5 | · context |
| Volatility | Bollinger %B | -0.24 | ❌ against |
| Volatility | ATR% | 6.08 | · context |
| Volume | Volume vs 20d | 3.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 42 | · context |
| Structure | Dist to 20d low/high | lo +1.5% / hi -29.3% | · context |
| Candle | Body / wicks | body 5.11%  up-wick 31%  lo-wick 15% | · context |
| Candle | Overnight gap | -12.5% | ✅ supports |
| Candle | Patterns firing | hs_top, double_top | · context |

- **5m confirmation:** VWAP loss at 2025-01-27 14:35 px $126.13 (RSI 0, vol 0.6x)

### 2024-02-22 significant RISE (+16.4% close-to-close)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: +0.73%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+66.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.9% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +10.3 | ✅ supports |
| Momentum | MACD hist | -0.081 | ❌ against |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.01 | ❌ against |
| Volatility | ATR% | 3.88 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 62 | · context |
| Structure | Dist to 20d low/high | lo +22.9% / hi -0.0% | · context |
| Candle | Body / wicks | body 4.68%  up-wick 1%  lo-wick 18% | · context |
| Candle | Overnight gap | +11.2% | ✅ supports |
| Candle | Patterns firing | morning_star | · context |

- **5m confirmation:** VWAP reclaim at 2024-02-23 17:00 px $802.01 (RSI 60, vol 0.8x)

### 2016-05-13 significant RISE (+15.2% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: +8.17%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+35.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.1% | ❌ against |
| Momentum | RSI | 76 (overbought) | ❌ against |
| Momentum | RSI slope | +20.9 | ✅ supports |
| Momentum | MACD hist | +0.005 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 2.83 | · context |
| Volume | Volume vs 20d | 5.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 68 | · context |
| Structure | Dist to 20d low/high | lo +16.1% / hi -0.0% | · context |
| Candle | Body / wicks | body 4.57%  up-wick 1%  lo-wick 9% | · context |
| Candle | Overnight gap | +10.2% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2023-05-25 GAP RISE (gap +26.1%, day +24.4%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +3.55%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+70.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +25.8% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +18.7 | ✅ supports |
| Momentum | MACD hist | +0.550 | ✅ supports |
| Momentum | Stochastic %K | 87 | · context |
| Volatility | Bollinger %B | 1.40 | ❌ against |
| Volatility | ATR% | 3.83 | · context |
| Volume | Volume vs 20d | 3.3x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 62 | · context |
| Structure | Dist to 20d low/high | lo +28.7% / hi -3.9% | · context |
| Candle | Body / wicks | body 1.41%  up-wick 34%  lo-wick 47% | · context |
| Candle | Overnight gap | +26.1% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2018-11-16 GAP DROP (gap -19.3%, day -18.8%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -6.92%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-30.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -20.8% | ❌ against |
| Momentum | RSI | 29 (oversold) | ❌ against |
| Momentum | RSI slope | -9.0 | ✅ supports |
| Momentum | MACD hist | -0.029 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 5 | · context |
| Volatility | Bollinger %B | -0.20 | ❌ against |
| Volatility | ATR% | 8.49 | · context |
| Volume | Volume vs 20d | 2.9x | ✅ supports |
| Volume | MFI | 61 | · context |
| Structure | Dist to 20d low/high | lo +1.7% / hi -43.1% | · context |
| Candle | Body / wicks | body 0.68%  up-wick 69%  lo-wick 19% | · context |
| Candle | Overnight gap | -19.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2016-11-11 GAP RISE (gap +17.3%, day +29.8%)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: +6.13%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+67.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +24.4% | ❌ against |
| Momentum | RSI | 79 (overbought) | ❌ against |
| Momentum | RSI slope | +22.7 | ✅ supports |
| Momentum | MACD hist | +0.023 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.46 | ❌ against |
| Volatility | ATR% | 4.02 | · context |
| Volume | Volume vs 20d | 4.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 58 | · context |
| Structure | Dist to 20d low/high | lo +25.5% / hi -0.9% | · context |
| Candle | Body / wicks | body 10.64%  up-wick 8%  lo-wick 10% | · context |
| Candle | Overnight gap | +17.3% | ✅ supports |
| Candle | Patterns firing | hs_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2019-01-28 GAP DROP (gap -14.7%, day -13.8%)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: +8.09%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-31.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -6.7% | ❌ against |
| Momentum | RSI | 42 (neutral) | · context |
| Momentum | RSI slope | -15.7 | ✅ supports |
| Momentum | MACD hist | +0.033 | ❌ against |
| Momentum | Stochastic %K | 23 | · context |
| Volatility | Bollinger %B | 0.30 | · context |
| Volatility | ATR% | 6.73 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 57 | · context |
| Structure | Dist to 20d low/high | lo +7.5% / hi -16.6% | · context |
| Candle | Body / wicks | body 1.07%  up-wick 34%  lo-wick 52% | · context |
| Candle | Overnight gap | -14.7% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2024-08-05 GAP DROP (gap -14.2%, day -6.4%)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +8.53%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+14.7%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -12.7% | ❌ against |
| Momentum | RSI | 36 (neutral) | · context |
| Momentum | RSI slope | -5.8 | ✅ supports |
| Momentum | MACD hist | -2.043 | ✅ supports |
| Momentum | Stochastic %K | 29 | · context |
| Volatility | Bollinger %B | 0.03 | ❌ against |
| Volatility | ATR% | 7.83 | · context |
| Volume | Volume vs 20d | 1.6x | ✅ supports |
| Volume | MFI | 31 | · context |
| Structure | Dist to 20d low/high | lo +9.7% / hi -35.5% | · context |
| Candle | Body / wicks | body 9.11%  up-wick 23%  lo-wick 11% | · context |
| Candle | Overnight gap | -14.2% | ✅ supports |

- **5m confirmation:** VWAP loss at 2024-08-05 18:45 px $99.32 (RSI 43, vol 1.5x)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (67 fulfillments in 15y)

### 2026-05-11 bull_flag (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: +1.31%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+22.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +7.9% | ❌ against |
| Momentum | RSI | 68 (neutral) | · context |
| Momentum | RSI slope | +5.1 | ✅ supports |
| Momentum | MACD hist | +0.726 | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 1.01 | ❌ against |
| Volatility | ATR% | 3.08 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 54 | · context |
| Structure | Dist to 20d low/high | lo +13.1% / hi -1.3% | · context |
| Candle | Body / wicks | body 2.52%  up-wick 34%  lo-wick 2% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-11 14:00 px $217.93 (RSI 91, vol 0.6x)

### 2025-10-09 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -5.59%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+27.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +5.2% | ❌ against |
| Momentum | RSI | 67 (neutral) | · context |
| Momentum | RSI slope | +8.7 | ✅ supports |
| Momentum | MACD hist | +0.958 | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 0.96 | ❌ against |
| Volatility | ATR% | 2.69 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 67 | · context |
| Structure | Dist to 20d low/high | lo +12.5% / hi -1.4% | · context |
| Candle | Body / wicks | body 0.18%  up-wick 64%  lo-wick 28% | · context |
| Candle | Overnight gap | +1.6% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-09 14:50 px $193.55 (RSI 59, vol 0.6x)

### 2025-07-28 bull_flag (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: +1.84%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+34.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +6.4% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +2.4 | ✅ supports |
| Momentum | MACD hist | -0.096 | ❌ against |
| Momentum | Stochastic %K | 98 | · context |
| Volatility | Bollinger %B | 0.89 | · context |
| Volatility | ATR% | 2.13 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 66 | · context |
| Structure | Dist to 20d low/high | lo +14.3% / hi -0.1% | · context |
| Candle | Body / wicks | body 1.57%  up-wick 8%  lo-wick 2% | · context |
| Candle | Patterns firing | marubozu, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-07-30 13:30 px $177.23 (RSI 66, vol 2.7x)

### Setup: double_bottom (90 fulfillments in 15y)

### 2026-04-15 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.83%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+13.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +8.5% | ❌ against |
| Momentum | RSI | 70 (neutral) | · context |
| Momentum | RSI slope | +7.8 | ✅ supports |
| Momentum | MACD hist | +2.916 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.06 | ❌ against |
| Volatility | ATR% | 2.70 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 64 | · context |
| Structure | Dist to 20d low/high | lo +17.4% / hi -0.8% | · context |
| Candle | Body / wicks | body 1.19%  up-wick 33%  lo-wick 17% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-15 19:35 px $198.43 (RSI 68, vol 1.3x)

### 2026-04-13 double_bottom (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: +6.73%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+8.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +5.1% | ❌ against |
| Momentum | RSI | 62 (neutral) | · context |
| Momentum | RSI slope | +5.4 | ✅ supports |
| Momentum | MACD hist | +2.046 | ✅ supports |
| Momentum | Stochastic %K | 97 | · context |
| Volatility | Bollinger %B | 0.96 | ❌ against |
| Volatility | ATR% | 2.79 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 56 | · context |
| Structure | Dist to 20d low/high | lo +13.2% / hi -0.4% | · context |
| Candle | Body / wicks | body 1.76%  up-wick 9%  lo-wick 7% | · context |
| Candle | Overnight gap | -1.4% | ❌ against |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-14 13:40 px $192.28 (RSI 74, vol 1.9x)

### 2026-03-10 double_bottom (long)

**Corroborating: 2  |  Contradicting: 2**  → next 5d: -1.54%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+6.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +0.2% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | +7.6 | ✅ supports |
| Momentum | MACD hist | -0.479 | ❌ against |
| Momentum | Stochastic %K | 44 | · context |
| Volatility | Bollinger %B | 0.45 | · context |
| Volatility | ATR% | 3.41 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +5.5% / hi -7.0% | · context |
| Candle | Body / wicks | body 1.30%  up-wick 38%  lo-wick 9% | · context |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-10 14:10 px $183.20 (RSI 89, vol 0.8x)

### Setup: inverted_hammer (54 fulfillments in 15y)

### 2026-01-15 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 1**  → next 5d: +0.33%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +0.9% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +1.9 | ✅ supports |
| Momentum | MACD hist | -0.147 | ❌ against |
| Momentum | Stochastic %K | 49 | · context |
| Volatility | Bollinger %B | 0.59 | · context |
| Volatility | ATR% | 2.81 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 55 | · context |
| Structure | Dist to 20d low/high | lo +8.9% / hi -3.5% | · context |
| Candle | Body / wicks | body 0.29%  up-wick 79%  lo-wick 5% | · context |
| Candle | Overnight gap | +1.8% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-15 15:30 px $188.19 (RSI 69, vol 0.4x)

### 2025-09-08 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: +5.61%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+17.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -3.6% | · context |
| Momentum | RSI | 39 (neutral) | ✅ supports |
| Momentum | RSI slope | -3.7 | ❌ against |
| Momentum | MACD hist | -1.913 | ❌ against |
| Momentum | Stochastic %K | 21 | · context |
| Volatility | Bollinger %B | 0.08 | ✅ supports |
| Volatility | ATR% | 2.93 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 50 | · context |
| Structure | Dist to 20d low/high | lo +2.5% / hi -9.6% | · context |
| Candle | Body / wicks | body 0.45%  up-wick 73%  lo-wick 6% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-09-08 14:25 px $170.21 (RSI 59, vol 0.8x)

### 2024-11-01 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +9.03%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+28.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -0.0% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | -7.1 | ❌ against |
| Momentum | MACD hist | -1.089 | ❌ against |
| Momentum | Stochastic %K | 42 | · context |
| Volatility | Bollinger %B | 0.40 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 3.45 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +7.7% / hi -6.7% | · context |
| Candle | Body / wicks | body 0.52%  up-wick 70%  lo-wick 5% | · context |
| Candle | Overnight gap | +1.5% | ✅ supports |
| Candle | Patterns firing | inverted_hammer, bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2024-11-01 17:20 px $136.22 (RSI 46, vol 1.5x)

### Setup: bullish_harami (129 fulfillments in 15y)

### 2026-06-08 bullish_harami (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.83%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -2.7% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | -7.5 | ❌ against |
| Momentum | MACD hist | -2.159 | ❌ against |
| Momentum | Stochastic %K | 15 | ✅ supports |
| Volatility | Bollinger %B | 0.14 | ✅ supports |
| Volatility | ATR% | 3.98 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +2.1% / hi -13.4% | · context |
| Candle | Body / wicks | body 0.73%  up-wick 6%  lo-wick 59% | · context |
| Candle | Overnight gap | +2.5% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-08 14:35 px $208.48 (RSI 69, vol 0.5x)

### 2026-03-23 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -5.96%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.2% | · context |
| Momentum | RSI | 42 (neutral) | · context |
| Momentum | RSI slope | -1.6 | ❌ against |
| Momentum | MACD hist | -0.873 | ❌ against |
| Momentum | Stochastic %K | 23 | · context |
| Volatility | Bollinger %B | 0.18 | ✅ supports |
| Volatility | ATR% | 3.28 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +2.2% / hi -12.5% | · context |
| Candle | Body / wicks | body 0.91%  up-wick 31%  lo-wick 24% | · context |
| Candle | Overnight gap | +2.6% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-23 13:45 px $177.45 (RSI 87, vol 0.4x)

### 2026-03-16 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -4.14%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+5.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.4% | · context |
| Momentum | RSI | 49 (neutral) | · context |
| Momentum | RSI slope | +0.5 | ✅ supports |
| Momentum | MACD hist | -0.195 | ❌ against |
| Momentum | Stochastic %K | 37 | · context |
| Volatility | Bollinger %B | 0.41 | · context |
| Volatility | ATR% | 3.36 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 47 | · context |
| Structure | Dist to 20d low/high | lo +4.7% / hi -7.9% | · context |
| Candle | Body / wicks | body 0.14%  up-wick 76%  lo-wick 21% | · context |
| Candle | Overnight gap | +1.5% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-16 14:10 px $184.28 (RSI 63, vol 0.7x)
