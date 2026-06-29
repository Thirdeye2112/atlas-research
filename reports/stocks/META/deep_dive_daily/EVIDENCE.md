# META — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **131/131** (100%)
- bearish_engulfing meets definition: **146/146** (100%)
- long candlesticks that are above 200-EMA: **442/619** (71%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=6.5%) the old open->close detector under-saw: **25/36** (69%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 25 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -3.2% · **close-to-close -9.3%** · gap -6.3% · RSI 26 · patterns —
- **2020-03-13** (COVID rebound): candle +4.1% · **close-to-close +10.2%** · gap +5.9% · RSI 38 · patterns —
- **2022-09-13** (CPI selloff): candle -5.2% · **close-to-close -9.4%** · gap -4.4% · RSI 40 · patterns ['marubozu', 'double_top', 'double_top', 'bear_flag']
- **2025-04-03** (tariff crash): candle -2.7% · **close-to-close -9.0%** · gap -6.5% · RSI 29 · patterns ['bear_flag']
- **2025-04-09** (tariff-pause rally): candle +15.0% · **close-to-close +14.8%** · gap -0.2% · RSI 49 · patterns ['bullish_engulfing', 'tweezer_bottom']

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2013-07-25 significant RISE (+29.6% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +9.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+29.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +29.9% | ❌ against |
| Momentum | RSI | 88 (overbought) | ❌ against |
| Momentum | RSI slope | +28.1 | ✅ supports |
| Momentum | MACD hist | +0.577 | ✅ supports |
| Momentum | Stochastic %K | 95 | · context |
| Volatility | Bollinger %B | 1.49 | ❌ against |
| Volatility | ATR% | 3.34 | · context |
| Volume | Volume vs 20d | 7.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 92 | · context |
| Structure | Dist to 20d low/high | lo +29.7% / hi -1.5% | · context |
| Candle | Body / wicks | body 2.44%  up-wick 24%  lo-wick 37% | · context |
| Candle | Overnight gap | +26.5% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-02-03 significant DROP (-26.4% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -4.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-26.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -23.1% | ❌ against |
| Momentum | RSI | 25 (oversold) | ❌ against |
| Momentum | RSI slope | -25.3 | ✅ supports |
| Momentum | MACD hist | -3.772 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.35 | ❌ against |
| Volatility | ATR% | 7.01 | · context |
| Volume | Volume vs 20d | 5.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 29 | · context |
| Structure | Dist to 20d low/high | lo +0.8% / hi -42.7% | · context |
| Candle | Body / wicks | body 2.82%  up-wick 27%  lo-wick 16% | · context |
| Candle | Overnight gap | -24.3% | ✅ supports |
| Candle | Patterns firing | hs_top | · context |

- **5m confirmation:** VWAP loss at 2022-02-03 16:50 px $242.52 (RSI 37, vol 0.3x)

### 2022-10-27 significant DROP (-24.6% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -9.22%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-48.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -25.4% | ❌ against |
| Momentum | RSI | 24 (oversold) | ❌ against |
| Momentum | RSI slope | -25.9 | ✅ supports |
| Momentum | MACD hist | -1.143 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.44 | ❌ against |
| Volatility | ATR% | 8.54 | · context |
| Volume | Volume vs 20d | 5.0x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 37 | · context |
| Structure | Dist to 20d low/high | lo +1.6% / hi -45.4% | · context |
| Candle | Body / wicks | body 0.04%  up-wick 74%  lo-wick 25% | · context |
| Candle | Overnight gap | -24.5% | ✅ supports |
| Candle | Patterns firing | double_top | · context |

- **5m confirmation:** VWAP loss at 2022-10-27 15:10 px $99.86 (RSI 53, vol 1.0x)

### 2023-02-02 significant RISE (+23.3% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -5.75%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +30.9% | ❌ against |
| Momentum | RSI | 86 (overbought) | ❌ against |
| Momentum | RSI slope | +16.6 | ✅ supports |
| Momentum | MACD hist | +3.190 | ✅ supports |
| Momentum | Stochastic %K | 87 | · context |
| Volatility | Bollinger %B | 1.38 | ❌ against |
| Volatility | ATR% | 3.94 | · context |
| Volume | Volume vs 20d | 4.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 83 | · context |
| Structure | Dist to 20d low/high | lo +34.0% / hi -4.4% | · context |
| Candle | Body / wicks | body 2.94%  up-wick 49%  lo-wick 19% | · context |
| Candle | Overnight gap | +19.8% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2023-02-03 15:20 px $192.33 (RSI 54, vol 0.6x)

### 2024-02-02 significant RISE (+20.3% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -1.45%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+55.1%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +22.1% | ❌ against |
| Momentum | RSI | 86 (overbought) | ❌ against |
| Momentum | RSI slope | +21.2 | ✅ supports |
| Momentum | MACD hist | +5.250 | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 1.38 | ❌ against |
| Volatility | ATR% | 3.06 | · context |
| Volume | Volume vs 20d | 4.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 81 | · context |
| Structure | Dist to 20d low/high | lo +27.1% / hi -2.3% | · context |
| Candle | Body / wicks | body 3.35%  up-wick 33%  lo-wick 20% | · context |
| Candle | Overnight gap | +16.4% | ✅ supports |

- **5m confirmation:** (no clean intraday trigger in window)

### 2012-10-24 significant RISE (+19.1% close-to-close)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: -8.82%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +14.2% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +24.5 | ✅ supports |
| Momentum | MACD hist | +0.164 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 81 | · context |
| Volatility | Bollinger %B | 1.05 | ❌ against |
| Volatility | ATR% | 4.53 | · context |
| Volume | Volume vs 20d | 4.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 64 | · context |
| Structure | Dist to 20d low/high | lo +19.1% / hi -4.4% | · context |
| Candle | Body / wicks | body 3.73%  up-wick 9%  lo-wick 27% | · context |
| Candle | Overnight gap | +23.7% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2018-07-26 significant DROP (-19.0% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +0.06%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-2.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ❌ against |
| Trend | Dist from 20-EMA | -13.3% | ❌ against |
| Momentum | RSI | 30 (neutral) | · context |
| Momentum | RSI slope | -41.6 | ✅ supports |
| Momentum | MACD hist | -1.832 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 6 | · context |
| Volatility | Bollinger %B | -0.24 | ❌ against |
| Volatility | ATR% | 3.78 | · context |
| Volume | Volume vs 20d | 6.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 54 | · context |
| Structure | Dist to 20d low/high | lo +1.4% / hi -24.0% | · context |
| Candle | Body / wicks | body 0.78%  up-wick 61%  lo-wick 18% | · context |
| Candle | Overnight gap | -19.6% | ✅ supports |
| Candle | Patterns firing | shooting_star | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-04-28 significant RISE (+17.6% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: +1.24%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-25.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +1.3% | · context |
| Momentum | RSI | 50 (neutral) | · context |
| Momentum | RSI slope | +19.4 | ✅ supports |
| Momentum | MACD hist | -2.325 | ❌ against |
| Momentum | Stochastic %K | 65 | · context |
| Volatility | Bollinger %B | 0.45 | · context |
| Volatility | ATR% | 5.16 | · context |
| Volume | Volume vs 20d | 3.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 29 | ✅ supports |
| Structure | Dist to 20d low/high | lo +17.9% / hi -15.1% | · context |
| Candle | Body / wicks | body 1.38%  up-wick 18%  lo-wick 64% | · context |
| Candle | Overnight gap | +16.0% | ✅ supports |
| Candle | Patterns firing | hammer, morning_star | · context |

- **5m confirmation:** VWAP reclaim at 2022-04-28 15:15 px $200.79 (RSI 49, vol 0.8x)

### 2016-01-28 significant RISE (+15.5% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +1.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+15.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +9.8% | ❌ against |
| Momentum | RSI | 64 (neutral) | · context |
| Momentum | RSI slope | +19.5 | ✅ supports |
| Momentum | MACD hist | +0.840 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 94 | · context |
| Volatility | Bollinger %B | 1.09 | ❌ against |
| Volatility | ATR% | 3.87 | · context |
| Volume | Volume vs 20d | 2.8x | ✅ supports |
| Volume | MFI | 45 | · context |
| Structure | Dist to 20d low/high | lo +18.1% / hi -1.1% | · context |
| Candle | Body / wicks | body 1.78%  up-wick 22%  lo-wick 43% | · context |
| Candle | Overnight gap | +13.5% | ✅ supports |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-04-09 significant RISE (+14.8% close-to-close)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -14.25%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +1.5% | · context |
| Momentum | RSI | 49 (neutral) | · context |
| Momentum | RSI slope | +19.6 | ✅ supports |
| Momentum | MACD hist | -2.376 | ❌ against |
| Momentum | Stochastic %K | 68 | · context |
| Volatility | Bollinger %B | 0.55 | · context |
| Volatility | ATR% | 5.69 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 50 | · context |
| Structure | Dist to 20d low/high | lo +17.7% / hi -8.2% | · context |
| Candle | Body / wicks | body 15.02%  up-wick 2%  lo-wick 8% | · context |
| Candle | Patterns firing | bullish_engulfing, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-04-09 13:45 px $512.67 (RSI 95, vol 1.1x)

## 3. Gap events (overnight gaps the old detector missed)

### 2013-07-25 GAP RISE (gap +26.5%, day +29.6%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +9.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+29.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +29.9% | ❌ against |
| Momentum | RSI | 88 (overbought) | ❌ against |
| Momentum | RSI slope | +28.1 | ✅ supports |
| Momentum | MACD hist | +0.577 | ✅ supports |
| Momentum | Stochastic %K | 95 | · context |
| Volatility | Bollinger %B | 1.49 | ❌ against |
| Volatility | ATR% | 3.34 | · context |
| Volume | Volume vs 20d | 7.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 92 | · context |
| Structure | Dist to 20d low/high | lo +29.7% / hi -1.5% | · context |
| Candle | Body / wicks | body 2.44%  up-wick 24%  lo-wick 37% | · context |
| Candle | Overnight gap | +26.5% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-10-27 GAP DROP (gap -24.5%, day -24.6%)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -9.22%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-48.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -25.4% | ❌ against |
| Momentum | RSI | 24 (oversold) | ❌ against |
| Momentum | RSI slope | -25.9 | ✅ supports |
| Momentum | MACD hist | -1.143 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.44 | ❌ against |
| Volatility | ATR% | 8.54 | · context |
| Volume | Volume vs 20d | 5.0x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 37 | · context |
| Structure | Dist to 20d low/high | lo +1.6% / hi -45.4% | · context |
| Candle | Body / wicks | body 0.04%  up-wick 74%  lo-wick 25% | · context |
| Candle | Overnight gap | -24.5% | ✅ supports |
| Candle | Patterns firing | double_top | · context |

- **5m confirmation:** VWAP loss at 2022-10-27 15:10 px $99.86 (RSI 53, vol 1.0x)

### 2022-02-03 GAP DROP (gap -24.3%, day -26.4%)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: -4.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-26.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -23.1% | ❌ against |
| Momentum | RSI | 25 (oversold) | ❌ against |
| Momentum | RSI slope | -25.3 | ✅ supports |
| Momentum | MACD hist | -3.772 | ✅ supports |
| Momentum | MACD cross | bearish cross | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.35 | ❌ against |
| Volatility | ATR% | 7.01 | · context |
| Volume | Volume vs 20d | 5.9x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 29 | · context |
| Structure | Dist to 20d low/high | lo +0.8% / hi -42.7% | · context |
| Candle | Body / wicks | body 2.82%  up-wick 27%  lo-wick 16% | · context |
| Candle | Overnight gap | -24.3% | ✅ supports |
| Candle | Patterns firing | hs_top | · context |

- **5m confirmation:** VWAP loss at 2022-02-03 16:50 px $242.52 (RSI 37, vol 0.3x)

### 2012-10-24 GAP RISE (gap +23.7%, day +19.1%)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: -8.82%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-17.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +14.2% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +24.5 | ✅ supports |
| Momentum | MACD hist | +0.164 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 81 | · context |
| Volatility | Bollinger %B | 1.05 | ❌ against |
| Volatility | ATR% | 4.53 | · context |
| Volume | Volume vs 20d | 4.8x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 64 | · context |
| Structure | Dist to 20d low/high | lo +19.1% / hi -4.4% | · context |
| Candle | Body / wicks | body 3.73%  up-wick 9%  lo-wick 27% | · context |
| Candle | Overnight gap | +23.7% | ✅ supports |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2023-02-02 GAP RISE (gap +19.8%, day +23.3%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -5.75%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +30.9% | ❌ against |
| Momentum | RSI | 86 (overbought) | ❌ against |
| Momentum | RSI slope | +16.6 | ✅ supports |
| Momentum | MACD hist | +3.190 | ✅ supports |
| Momentum | Stochastic %K | 87 | · context |
| Volatility | Bollinger %B | 1.38 | ❌ against |
| Volatility | ATR% | 3.94 | · context |
| Volume | Volume vs 20d | 4.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 83 | · context |
| Structure | Dist to 20d low/high | lo +34.0% / hi -4.4% | · context |
| Candle | Body / wicks | body 2.94%  up-wick 49%  lo-wick 19% | · context |
| Candle | Overnight gap | +19.8% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2023-02-03 15:20 px $192.33 (RSI 54, vol 0.6x)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (51 fulfillments in 15y)

### 2026-01-29 bull_flag (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: -9.22%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +12.4% | ❌ against |
| Momentum | RSI | 74 (overbought) | ❌ against |
| Momentum | RSI slope | +13.2 | ✅ supports |
| Momentum | MACD hist | +9.480 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 2.86 | · context |
| Volume | Volume vs 20d | 3.4x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 69 | · context |
| Structure | Dist to 20d low/high | lo +18.7% / hi -0.8% | · context |
| Candle | Body / wicks | body 0.12%  up-wick 18%  lo-wick 79% | · context |
| Candle | Overnight gap | +10.3% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2025-08-12 bull_flag (long)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -4.88%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+24.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +6.0% | ❌ against |
| Momentum | RSI | 66 (neutral) | · context |
| Momentum | RSI slope | +4.0 | ✅ supports |
| Momentum | MACD hist | +4.234 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 0.92 | ❌ against |
| Volatility | ATR% | 2.43 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 52 | · context |
| Structure | Dist to 20d low/high | lo +12.5% / hi -0.5% | · context |
| Candle | Body / wicks | body 2.20%  up-wick 17%  lo-wick 3% | · context |
| Candle | Overnight gap | +0.9% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-08-12 14:15 px $784.40 (RSI 78, vol 0.9x)

### 2025-07-31 bull_flag (long)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: -1.50%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+23.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +8.2% | ❌ against |
| Momentum | RSI | 70 (neutral) | · context |
| Momentum | RSI slope | +22.8 | ✅ supports |
| Momentum | MACD hist | +1.073 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 88 | · context |
| Volatility | Bollinger %B | 1.37 | ❌ against |
| Volatility | ATR% | 2.55 | · context |
| Volume | Volume vs 20d | 3.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 46 | · context |
| Structure | Dist to 20d low/high | lo +10.6% / hi -1.5% | · context |
| Candle | Body / wicks | body 0.23%  up-wick 50%  lo-wick 41% | · context |
| Candle | Overnight gap | +11.5% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-07-31 14:00 px $779.24 (RSI 88, vol 0.4x)

### Setup: double_bottom (96 fulfillments in 15y)

### 2026-05-27 double_bottom (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -1.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-1.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +2.7% | · context |
| Momentum | RSI | 57 (neutral) | · context |
| Momentum | RSI slope | +11.5 | ✅ supports |
| Momentum | MACD hist | +1.546 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 93 | · context |
| Volatility | Bollinger %B | 0.85 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.51 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 52 | · context |
| Structure | Dist to 20d low/high | lo +6.7% / hi -6.1% | · context |
| Candle | Body / wicks | body 4.24%  up-wick 11%  lo-wick 1% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-27 13:55 px $610.98 (RSI 94, vol 0.5x)

### 2026-05-27 double_bottom (long)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -1.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-1.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +2.7% | · context |
| Momentum | RSI | 57 (neutral) | · context |
| Momentum | RSI slope | +11.5 | ✅ supports |
| Momentum | MACD hist | +1.546 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 93 | · context |
| Volatility | Bollinger %B | 0.85 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.51 | · context |
| Volume | Volume vs 20d | 1.4x | · context |
| Volume | MFI | 52 | · context |
| Structure | Dist to 20d low/high | lo +6.7% / hi -6.1% | · context |
| Candle | Body / wicks | body 4.24%  up-wick 11%  lo-wick 1% | · context |
| Candle | Overnight gap | -0.5% | ❌ against |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-27 13:55 px $610.98 (RSI 94, vol 0.5x)

### 2026-03-04 double_bottom (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: -1.93%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+0.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +1.8% | · context |
| Momentum | RSI | 55 (neutral) | · context |
| Momentum | RSI slope | +5.4 | ✅ supports |
| Momentum | MACD hist | +0.978 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 83 | · context |
| Volatility | Bollinger %B | 0.75 | · context |
| Volatility | ATR% | 2.94 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 56 | · context |
| Structure | Dist to 20d low/high | lo +5.9% / hi -3.2% | · context |
| Candle | Body / wicks | body 1.48%  up-wick 33%  lo-wick 2% | · context |
| Candle | Overnight gap | +0.4% | ✅ supports |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-04 19:00 px $668.13 (RSI 46, vol 1.6x)

### Setup: inverted_hammer (53 fulfillments in 15y)

### 2026-05-14 inverted_hammer (long)

**Corroborating: 1  |  Contradicting: 3**  → next 5d: -1.79%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.9% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | +6.2 | ✅ supports |
| Momentum | MACD hist | -3.673 | ❌ against |
| Momentum | Stochastic %K | 29 | · context |
| Volatility | Bollinger %B | 0.35 | · context |
| Volatility | ATR% | 2.82 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 37 | · context |
| Structure | Dist to 20d low/high | lo +4.2% / hi -11.8% | · context |
| Candle | Body / wicks | body 0.39%  up-wick 61%  lo-wick 11% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-15 15:55 px $613.27 (RSI 46, vol 0.4x)

### 2026-05-07 inverted_hammer (long)

**Corroborating: 1  |  Contradicting: 3**  → next 5d: +0.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-5.1%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -2.6% | · context |
| Momentum | RSI | 44 (neutral) | · context |
| Momentum | RSI slope | +4.4 | ✅ supports |
| Momentum | MACD hist | -7.352 | ❌ against |
| Momentum | Stochastic %K | 22 | · context |
| Volatility | Bollinger %B | 0.22 | · context |
| Volatility | ATR% | 3.14 | · context |
| Volume | Volume vs 20d | 0.8x | · context |
| Volume | MFI | 38 | · context |
| Structure | Dist to 20d low/high | lo +3.0% / hi -12.1% | · context |
| Candle | Body / wicks | body 0.34%  up-wick 71%  lo-wick 10% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-07 13:50 px $621.68 (RSI 88, vol 0.5x)

### 2025-09-08 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 1**  → next 5d: +1.65%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+14.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +0.4% | · context |
| Momentum | RSI | 52 (neutral) | · context |
| Momentum | RSI slope | +1.5 | ✅ supports |
| Momentum | MACD hist | -2.225 | ❌ against |
| Momentum | Stochastic %K | 67 | · context |
| Volatility | Bollinger %B | 0.43 | · context |
| Volatility | ATR% | 2.15 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 43 | · context |
| Structure | Dist to 20d low/high | lo +4.1% / hi -5.8% | · context |
| Candle | Body / wicks | body 0.49%  up-wick 73%  lo-wick 2% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-09-08 15:55 px $762.39 (RSI 55, vol 0.8x)

### Setup: bullish_harami (118 fulfillments in 15y)

### 2026-03-30 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +7.21%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-18.0%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -10.9% | · context |
| Momentum | RSI | 27 (oversold) | ✅ supports |
| Momentum | RSI slope | +1.5 | ✅ supports |
| Momentum | MACD hist | -9.589 | ❌ against |
| Momentum | Stochastic %K | 12 | ✅ supports |
| Volatility | Bollinger %B | 0.02 | ✅ supports |
| Volatility | ATR% | 3.68 | · context |
| Volume | Volume vs 20d | 1.5x | · context |
| Volume | MFI | 27 | ✅ supports |
| Structure | Dist to 20d low/high | lo +3.0% / hi -25.4% | · context |
| Candle | Body / wicks | body 0.00%  up-wick 29%  lo-wick 71% | · context |
| Candle | Overnight gap | +2.0% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-30 14:55 px $534.88 (RSI 50, vol 0.6x)

### 2026-01-15 bullish_harami (long)

**Corroborating: 5  |  Contradicting: 4**  → next 5d: +6.11%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-6.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.8% | · context |
| Momentum | RSI | 37 (neutral) | ✅ supports |
| Momentum | RSI slope | -2.2 | ❌ against |
| Momentum | MACD hist | -4.731 | ❌ against |
| Momentum | Stochastic %K | 11 | ✅ supports |
| Volatility | Bollinger %B | -0.03 | ✅ supports |
| Volatility | ATR% | 2.41 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 34 | · context |
| Structure | Dist to 20d low/high | lo +1.1% / hi -8.5% | ✅ supports |
| Candle | Body / wicks | body 0.38%  up-wick 34%  lo-wick 43% | · context |
| Candle | Overnight gap | +0.5% | ✅ supports |
| Candle | Patterns firing | bullish_harami, tweezer_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-15 14:50 px $618.10 (RSI 81, vol 0.6x)

### 2025-11-13 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: -3.40%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-9.7%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -7.9% | · context |
| Momentum | RSI | 27 (oversold) | ✅ supports |
| Momentum | RSI slope | -2.9 | ❌ against |
| Momentum | MACD hist | -6.402 | ❌ against |
| Momentum | Stochastic %K | 6 | ✅ supports |
| Volatility | Bollinger %B | 0.20 | ✅ supports |
| Volatility | ATR% | 3.27 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 16 | ✅ supports |
| Structure | Dist to 20d low/high | lo +1.4% / hi -24.5% | ✅ supports |
| Candle | Body / wicks | body 0.52%  up-wick 31%  lo-wick 47% | · context |
| Candle | Overnight gap | +0.7% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2025-11-13 20:55 px $609.96 (RSI 66, vol 5.0x)
