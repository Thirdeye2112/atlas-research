# AMZN — detection QA + evidence cards (daily, 15y)

## 1. Detection integrity

- bullish_engulfing meets definition: **105/105** (100%)
- bearish_engulfing meets definition: **164/164** (100%)
- long candlesticks that are above 200-EMA: **409/591** (69%)
- 'big up' days (close-to-close) with positive cc_ret: **1/1**
- 'big down' days (close-to-close) with negative cc_ret: **1/1**
- gap days (|gap|>=6.3%) the old open->close detector under-saw: **23/38** (61%)

_Gap fix: switched significant-move detection from open→close to **close-to-close**; 23 large-gap days that the old detector under-saw are now captured._

### Marquee-date sanity check (candle vs close-to-close vs gap)

- **2020-03-12** (COVID crash): candle -2.6% · **close-to-close -7.9%** · gap -5.4% · RSI 32 · patterns —
- **2020-03-13** (COVID rebound): candle +1.7% · **close-to-close +6.5%** · gap +4.7% · RSI 41 · patterns ['hammer']
- **2022-09-13** (CPI selloff): candle -3.2% · **close-to-close -7.1%** · gap -4.0% · RSI 44 · patterns —
- **2025-04-03** (tariff crash): candle -2.5% · **close-to-close -9.0%** · gap -6.6% · RSI 31 · patterns —
- **2025-04-09** (tariff-pause rally): candle +11.0% · **close-to-close +12.0%** · gap +0.9% · RSI 48 · patterns —

## 2. Evidence cards — biggest rises & drops (close-to-close, gap-inclusive)

### 2012-04-27 significant RISE (+15.7% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -1.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +16.4% | ❌ against |
| Momentum | RSI | 78 (overbought) | ❌ against |
| Momentum | RSI slope | +23.1 | ✅ supports |
| Momentum | MACD hist | +0.116 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 3.00 | · context |
| Volume | Volume vs 20d | 4.2x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 72 | · context |
| Structure | Dist to 20d low/high | lo +19.0% / hi -0.8% | · context |
| Candle | Body / wicks | body 0.90%  up-wick 22%  lo-wick 54% | · context |
| Candle | Overnight gap | +14.7% | ✅ supports |
| Candle | Patterns firing | hanging_man, double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-04-24 significant RISE (+14.1% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -4.99%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+28.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.7% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +21.4 | ✅ supports |
| Momentum | MACD hist | +0.212 | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 1.46 | ❌ against |
| Volatility | ATR% | 2.50 | · context |
| Volume | Volume vs 20d | 4.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 70 | · context |
| Structure | Dist to 20d low/high | lo +17.6% / hi -1.7% | · context |
| Candle | Body / wicks | body 1.39%  up-wick 55%  lo-wick 0% | · context |
| Candle | Overnight gap | +12.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-04-29 significant DROP (-14.0% close-to-close)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -7.65%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-22.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bear | ✅ supports |
| Trend | Dist from 20-EMA | -16.1% | ❌ against |
| Momentum | RSI | 29 (oversold) | ❌ against |
| Momentum | RSI slope | -4.3 | ✅ supports |
| Momentum | MACD hist | -2.647 | ✅ supports |
| Momentum | Stochastic %K | 7 | · context |
| Volatility | Bollinger %B | -0.17 | ❌ against |
| Volatility | ATR% | 5.48 | · context |
| Volume | Volume vs 20d | 3.7x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 27 | · context |
| Structure | Dist to 20d low/high | lo +2.1% / hi -35.5% | · context |
| Candle | Body / wicks | body 4.29%  up-wick 10%  lo-wick 29% | · context |
| Candle | Overnight gap | -10.2% | ✅ supports |

- **5m confirmation:** VWAP loss at 2022-04-29 13:35 px $2568.16 (RSI 0, vol 0.8x)

### 2015-01-30 significant RISE (+13.7% close-to-close)

**Corroborating: 6  |  Contradicting: 3**  → next 5d: +5.57%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.4%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +15.1% | ❌ against |
| Momentum | RSI | 76 (overbought) | ❌ against |
| Momentum | RSI slope | +24.8 | ✅ supports |
| Momentum | MACD hist | +0.246 | ✅ supports |
| Momentum | Stochastic %K | 93 | · context |
| Volatility | Bollinger %B | 1.39 | ❌ against |
| Volatility | ATR% | 3.28 | · context |
| Volume | Volume vs 20d | 4.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 71 | · context |
| Structure | Dist to 20d low/high | lo +19.5% / hi -1.4% | · context |
| Candle | Body / wicks | body 2.37%  up-wick 26%  lo-wick 30% | · context |
| Candle | Overnight gap | +11.1% | ✅ supports |
| Candle | Patterns firing | hs_bottom, double_bottom, double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-02-04 significant RISE (+13.5% close-to-close)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -2.76%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +3.7% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +9.7 | ✅ supports |
| Momentum | MACD hist | +0.955 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 0.65 | · context |
| Volatility | ATR% | 4.46 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +14.1% / hi -5.9% | · context |
| Candle | Body / wicks | body 1.31%  up-wick 34%  lo-wick 47% | · context |
| Candle | Overnight gap | +12.1% | ✅ supports |

- **5m confirmation:** (no clean intraday trigger in window)

### 2017-10-27 significant RISE (+13.2% close-to-close)

**Corroborating: 8  |  Contradicting: 3**  → next 5d: +0.97%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+18.2%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +11.0% | ❌ against |
| Momentum | RSI | 78 (overbought) | ❌ against |
| Momentum | RSI slope | +31.8 | ✅ supports |
| Momentum | MACD hist | +0.267 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 97 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 2.13 | · context |
| Volume | Volume vs 20d | 4.5x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 79 | · context |
| Structure | Dist to 20d low/high | lo +13.7% / hi -0.4% | · context |
| Candle | Body / wicks | body 4.05%  up-wick 8%  lo-wick 14% | · context |
| Candle | Overnight gap | +8.8% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2011-10-26 significant DROP (-12.7% close-to-close)

**Corroborating: 6  |  Contradicting: 2**  → next 5d: +8.68%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-2.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -13.0% | ❌ against |
| Momentum | RSI | 33 (neutral) | · context |
| Momentum | RSI slope | -24.0 | ✅ supports |
| Momentum | MACD hist | -0.158 | ✅ supports |
| Momentum | Stochastic %K | 4 | · context |
| Volatility | Bollinger %B | -0.11 | ❌ against |
| Volatility | ATR% | 5.29 | · context |
| Volume | Volume vs 20d | 3.3x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 39 | · context |
| Structure | Dist to 20d low/high | lo +1.0% / hi -24.3% | · context |
| Candle | Body / wicks | body 2.60%  up-wick 35%  lo-wick 17% | · context |
| Candle | Overnight gap | -10.3% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2022-11-10 significant RISE (+12.2% close-to-close)

**Corroborating: 4  |  Contradicting: 3**  → next 5d: -1.84%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-24.7%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -4.9% | · context |
| Momentum | RSI | 41 (neutral) | · context |
| Momentum | RSI slope | +14.7 | ✅ supports |
| Momentum | MACD hist | -1.154 | ❌ against |
| Momentum | Stochastic %K | 30 | · context |
| Volatility | Bollinger %B | 0.34 | · context |
| Volatility | ATR% | 5.82 | · context |
| Volume | Volume vs 20d | 1.8x | ✅ supports |
| Volume | MFI | 29 | ✅ supports |
| Structure | Dist to 20d low/high | lo +11.1% / hi -25.6% | · context |
| Candle | Body / wicks | body 3.97%  up-wick 29%  lo-wick 18% | · context |
| Candle | Overnight gap | +7.9% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2022-11-10 15:40 px $95.57 (RSI 47, vol 1.1x)

### 2025-04-09 significant RISE (+12.0% close-to-close)

**Corroborating: 3  |  Contradicting: 3**  → next 5d: -8.78%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.2%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +0.1% | · context |
| Momentum | RSI | 48 (neutral) | · context |
| Momentum | RSI slope | +15.7 | ✅ supports |
| Momentum | MACD hist | -0.718 | ❌ against |
| Momentum | Stochastic %K | 66 | · context |
| Volatility | Bollinger %B | 0.48 | · context |
| Volatility | ATR% | 5.52 | · context |
| Volume | Volume vs 20d | 2.0x | ✅ supports |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +15.6% / hi -7.9% | · context |
| Candle | Body / wicks | body 11.03%  up-wick 7%  lo-wick 10% | · context |
| Candle | Overnight gap | +0.9% | ✅ supports |

- **5m confirmation:** VWAP reclaim at 2025-04-09 13:45 px $173.36 (RSI 97, vol 0.7x)

### 2014-01-31 significant DROP (-11.0% close-to-close)

**Corroborating: 5  |  Contradicting: 3**  → next 5d: +0.67%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+7.8%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -8.4% | ❌ against |
| Momentum | RSI | 35 (neutral) | · context |
| Momentum | RSI slope | -7.5 | ✅ supports |
| Momentum | MACD hist | -0.170 | ✅ supports |
| Momentum | Stochastic %K | 2 | · context |
| Volatility | Bollinger %B | -0.37 | ❌ against |
| Volatility | ATR% | 3.42 | · context |
| Volume | Volume vs 20d | 4.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +0.3% / hi -13.8% | · context |
| Candle | Body / wicks | body 3.52%  up-wick 21%  lo-wick 5% | · context |
| Candle | Overnight gap | -7.8% | ✅ supports |
| Candle | Patterns firing | double_top, double_top | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

## 3. Gap events (overnight gaps the old detector missed)

### 2015-07-24 GAP RISE (gap +20.1%, day +9.8%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: +1.27%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+35.6%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +13.2% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +5.9 | ✅ supports |
| Momentum | MACD hist | +0.295 | ✅ supports |
| Momentum | Stochastic %K | 67 | · context |
| Volatility | Bollinger %B | 1.14 | ❌ against |
| Volatility | ATR% | 2.97 | · context |
| Volume | Volume vs 20d | 5.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 72 | · context |
| Structure | Dist to 20d low/high | lo +19.6% / hi -9.7% | · context |
| Candle | Body / wicks | body 8.56%  up-wick 3%  lo-wick 0% | · context |
| Candle | Overnight gap | +20.1% | ✅ supports |
| Candle | Patterns firing | marubozu, bull_flag | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2012-04-27 GAP RISE (gap +14.7%, day +15.7%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -1.26%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+16.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +16.4% | ❌ against |
| Momentum | RSI | 78 (overbought) | ❌ against |
| Momentum | RSI slope | +23.1 | ✅ supports |
| Momentum | MACD hist | +0.116 | ✅ supports |
| Momentum | Stochastic %K | 96 | · context |
| Volatility | Bollinger %B | 1.42 | ❌ against |
| Volatility | ATR% | 3.00 | · context |
| Volume | Volume vs 20d | 4.2x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 72 | · context |
| Structure | Dist to 20d low/high | lo +19.0% / hi -0.8% | · context |
| Candle | Body / wicks | body 0.90%  up-wick 22%  lo-wick 54% | · context |
| Candle | Overnight gap | +14.7% | ✅ supports |
| Candle | Patterns firing | hanging_man, double_bottom | · context |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2015-04-24 GAP RISE (gap +12.6%, day +14.1%)

**Corroborating: 7  |  Contradicting: 3**  → next 5d: -4.99%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+28.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +14.7% | ❌ against |
| Momentum | RSI | 82 (overbought) | ❌ against |
| Momentum | RSI slope | +21.4 | ✅ supports |
| Momentum | MACD hist | +0.212 | ✅ supports |
| Momentum | Stochastic %K | 90 | · context |
| Volatility | Bollinger %B | 1.46 | ❌ against |
| Volatility | ATR% | 2.50 | · context |
| Volume | Volume vs 20d | 4.6x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 70 | · context |
| Structure | Dist to 20d low/high | lo +17.6% / hi -1.7% | · context |
| Candle | Body / wicks | body 1.39%  up-wick 55%  lo-wick 0% | · context |
| Candle | Overnight gap | +12.6% | ✅ supports |

- **5m confirmation:** (no 5m bars near date — pre-2023)

### 2025-10-31 GAP RISE (gap +12.2%, day +9.6%)

**Corroborating: 7  |  Contradicting: 2**  → next 5d: +0.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+13.7%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +8.7% | ❌ against |
| Momentum | RSI | 67 (neutral) | · context |
| Momentum | RSI slope | +7.0 | ✅ supports |
| Momentum | MACD hist | +2.319 | ✅ supports |
| Momentum | Stochastic %K | 84 | · context |
| Volatility | Bollinger %B | 1.26 | ❌ against |
| Volatility | ATR% | 2.81 | · context |
| Volume | Volume vs 20d | 3.1x | ✅ supports |
| Volume | Volume climax | yes | ✅ supports |
| Volume | MFI | 60 | · context |
| Structure | Dist to 20d low/high | lo +13.6% / hi -2.6% | · context |
| Candle | Body / wicks | body 2.35%  up-wick 6%  lo-wick 4% | · context |
| Candle | Overnight gap | +12.2% | ✅ supports |
| Candle | Patterns firing | marubozu, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2025-10-31 13:50 px $248.89 (RSI 96, vol 0.5x)

### 2022-02-04 GAP RISE (gap +12.1%, day +13.5%)

**Corroborating: 5  |  Contradicting: 2**  → next 5d: -2.76%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | +3.7% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +9.7 | ✅ supports |
| Momentum | MACD hist | +0.955 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 86 | · context |
| Volatility | Bollinger %B | 0.65 | · context |
| Volatility | ATR% | 4.46 | · context |
| Volume | Volume vs 20d | 2.7x | ✅ supports |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +14.1% / hi -5.9% | · context |
| Candle | Body / wicks | body 1.31%  up-wick 34%  lo-wick 47% | · context |
| Candle | Overnight gap | +12.1% | ✅ supports |

- **5m confirmation:** (no clean intraday trigger in window)

## 4. Setup evidence cards — why each setup fired (recent fulfillments)

### Setup: bull_flag (57 fulfillments in 15y)

### 2026-05-01 bull_flag (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +1.65%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+19.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +7.9% | ❌ against |
| Momentum | RSI | 78 (overbought) | ❌ against |
| Momentum | RSI slope | +2.6 | ✅ supports |
| Momentum | MACD hist | +1.163 | ✅ supports |
| Momentum | Stochastic %K | 82 | · context |
| Volatility | Bollinger %B | 0.82 | · context |
| Volatility | ATR% | 2.79 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 77 | · context |
| Structure | Dist to 20d low/high | lo +22.1% / hi -2.1% | · context |
| Candle | Body / wicks | body 1.01%  up-wick 48%  lo-wick 27% | · context |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2026-05-01 17:20 px $269.35 (RSI 51, vol 0.9x)

### 2025-07-11 bull_flag (long)

**Corroborating: 5  |  Contradicting: 0**  → next 5d: +0.49%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.3%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +3.3% | · context |
| Momentum | RSI | 64 (neutral) | · context |
| Momentum | RSI slope | +2.6 | ✅ supports |
| Momentum | MACD hist | +0.117 | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 0.87 | · context |
| Volatility | ATR% | 2.04 | · context |
| Volume | Volume vs 20d | 1.1x | · context |
| Volume | MFI | 67 | · context |
| Structure | Dist to 20d low/high | lo +7.9% / hi -0.7% | · context |
| Candle | Body / wicks | body 0.64%  up-wick 39%  lo-wick 28% | · context |
| Candle | Overnight gap | +0.6% | ✅ supports |
| Candle | Patterns firing | bull_flag | · context |

- **5m confirmation:** (no clean intraday trigger in window)

### 2025-06-27 bull_flag (long)

**Corroborating: 8  |  Contradicting: 2**  → next 5d: +0.08%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+11.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +5.4% | ❌ against |
| Momentum | RSI | 68 (neutral) | · context |
| Momentum | RSI slope | +12.1 | ✅ supports |
| Momentum | MACD hist | +0.110 | ✅ supports |
| Momentum | MACD cross | bullish cross | ✅ supports |
| Momentum | Stochastic %K | 100 | · context |
| Volatility | Bollinger %B | 1.09 | ❌ against |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.33 | · context |
| Volume | Volume vs 20d | 2.8x | ✅ supports |
| Volume | MFI | 60 | · context |
| Structure | Dist to 20d low/high | lo +9.7% / hi +0.0% | · context |
| Candle | Body / wicks | body 1.54%  up-wick 0%  lo-wick 48% | · context |
| Candle | Overnight gap | +1.3% | ✅ supports |
| Candle | Patterns firing | double_bottom, bull_flag | · context |

- **5m confirmation:** VWAP reclaim at 2025-06-27 19:20 px $219.48 (RSI 66, vol 1.2x)

### Setup: double_bottom (120 fulfillments in 15y)

### 2026-04-08 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +12.32%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +4.9% | ❌ against |
| Momentum | RSI | 61 (neutral) | · context |
| Momentum | RSI slope | +7.9 | ✅ supports |
| Momentum | MACD hist | +1.608 | ✅ supports |
| Momentum | Stochastic %K | 82 | · context |
| Volatility | Bollinger %B | 1.11 | ❌ against |
| Volatility | ATR% | 2.82 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +10.0% / hi -2.2% | · context |
| Candle | Body / wicks | body 1.13%  up-wick 36%  lo-wick 25% | · context |
| Candle | Overnight gap | +4.7% | ✅ supports |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-09 13:35 px $224.60 (RSI 79, vol 1.6x)

### 2026-04-08 double_bottom (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: +12.32%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+1.0%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +4.9% | ❌ against |
| Momentum | RSI | 61 (neutral) | · context |
| Momentum | RSI slope | +7.9 | ✅ supports |
| Momentum | MACD hist | +1.608 | ✅ supports |
| Momentum | Stochastic %K | 82 | · context |
| Volatility | Bollinger %B | 1.11 | ❌ against |
| Volatility | ATR% | 2.82 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 49 | · context |
| Structure | Dist to 20d low/high | lo +10.0% / hi -2.2% | · context |
| Candle | Body / wicks | body 1.13%  up-wick 36%  lo-wick 25% | · context |
| Candle | Overnight gap | +4.7% | ✅ supports |
| Candle | Patterns firing | double_bottom, double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-09 13:35 px $224.60 (RSI 79, vol 1.6x)

### 2026-04-07 double_bottom (long)

**Corroborating: 2  |  Contradicting: 2**  → next 5d: +16.49%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-2.4%) | ❌ against |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | +1.9% | · context |
| Momentum | RSI | 54 (neutral) | · context |
| Momentum | RSI slope | +4.2 | ✅ supports |
| Momentum | MACD hist | +1.010 | ✅ supports |
| Momentum | Stochastic %K | 91 | · context |
| Volatility | Bollinger %B | 0.77 | · context |
| Volatility | ATR% | 2.69 | · context |
| Volume | Volume vs 20d | 0.7x | · context |
| Volume | MFI | 41 | · context |
| Structure | Dist to 20d low/high | lo +6.8% / hi -1.5% | · context |
| Candle | Body / wicks | body 1.20%  up-wick 4%  lo-wick 44% | · context |
| Candle | Overnight gap | -0.7% | ❌ against |
| Candle | Patterns firing | double_bottom | · context |

- **5m confirmation:** VWAP reclaim at 2026-04-07 15:50 px $210.75 (RSI 69, vol 0.6x)

### Setup: inverted_hammer (41 fulfillments in 15y)

### 2026-03-23 inverted_hammer (long)

**Corroborating: 4  |  Contradicting: 2**  → next 5d: -4.37%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-4.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -0.6% | · context |
| Momentum | RSI | 47 (neutral) | · context |
| Momentum | RSI slope | +2.9 | ✅ supports |
| Momentum | MACD hist | +0.278 | ✅ supports |
| Momentum | Stochastic %K | 36 | · context |
| Volatility | Bollinger %B | 0.43 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.72 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 45 | · context |
| Structure | Dist to 20d low/high | lo +3.6% / hi -4.9% | · context |
| Candle | Body / wicks | body 0.17%  up-wick 81%  lo-wick 9% | · context |
| Candle | Overnight gap | +2.2% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-23 14:45 px $212.18 (RSI 83, vol 0.5x)

### 2026-02-10 inverted_hammer (long)

**Corroborating: 3  |  Contradicting: 4**  → next 5d: -1.05%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-7.6%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -9.7% | · context |
| Momentum | RSI | 27 (oversold) | ✅ supports |
| Momentum | RSI slope | -1.7 | ❌ against |
| Momentum | MACD hist | -4.116 | ❌ against |
| Momentum | Stochastic %K | 14 | ✅ supports |
| Volatility | Bollinger %B | -0.06 | ✅ supports |
| Volatility | ATR% | 3.73 | · context |
| Volume | Volume vs 20d | 1.2x | · context |
| Volume | MFI | 44 | · context |
| Structure | Dist to 20d low/high | lo +3.2% / hi -19.7% | · context |
| Candle | Body / wicks | body 0.88%  up-wick 62%  lo-wick 9% | · context |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2026-02-11 15:30 px $206.12 (RSI 48, vol 0.5x)

### 2025-09-15 inverted_hammer (long)

**Corroborating: 5  |  Contradicting: 1**  → next 5d: -1.64%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+9.5%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | +0.7% | · context |
| Momentum | RSI | 53 (neutral) | · context |
| Momentum | RSI slope | +1.7 | ✅ supports |
| Momentum | MACD hist | -0.221 | ❌ against |
| Momentum | Stochastic %K | 56 | · context |
| Volatility | Bollinger %B | 0.61 | · context |
| Volatility | BB squeeze | yes (energy coiled) | ✅ supports |
| Volatility | ATR% | 2.15 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 48 | · context |
| Structure | Dist to 20d low/high | lo +4.7% / hi -3.2% | · context |
| Candle | Body / wicks | body 0.35%  up-wick 67%  lo-wick 9% | · context |
| Candle | Overnight gap | +1.1% | ✅ supports |
| Candle | Patterns firing | inverted_hammer | · context |

- **5m confirmation:** VWAP reclaim at 2025-09-16 13:45 px $234.00 (RSI 73, vol 2.5x)

### Setup: bullish_harami (113 fulfillments in 15y)

### 2026-06-04 bullish_harami (long)

**Corroborating: 3  |  Contradicting: 2**  → next 5d: -4.84%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+8.9%) | ✅ supports |
| Trend | EMA stack 9/20/50 | mixed | · context |
| Trend | Dist from 20-EMA | -3.2% | · context |
| Momentum | RSI | 43 (neutral) | · context |
| Momentum | RSI slope | -1.1 | ❌ against |
| Momentum | MACD hist | -3.054 | ❌ against |
| Momentum | Stochastic %K | 22 | · context |
| Volatility | Bollinger %B | 0.05 | ✅ supports |
| Volatility | ATR% | 2.74 | · context |
| Volume | Volume vs 20d | 0.9x | · context |
| Volume | MFI | 44 | · context |
| Structure | Dist to 20d low/high | lo +2.4% / hi -9.0% | · context |
| Candle | Body / wicks | body 0.26%  up-wick 50%  lo-wick 34% | · context |
| Candle | Overnight gap | +1.2% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-06-04 17:15 px $254.07 (RSI 46, vol 1.5x)

### 2026-03-30 bullish_harami (long)

**Corroborating: 6  |  Contradicting: 4**  → next 5d: +6.38%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | below (-8.5%) | ❌ against |
| Trend | EMA stack 9/20/50 | bear | ❌ against |
| Trend | Dist from 20-EMA | -3.8% | · context |
| Momentum | RSI | 40 (neutral) | ✅ supports |
| Momentum | RSI slope | -5.2 | ❌ against |
| Momentum | MACD hist | -0.580 | ❌ against |
| Momentum | Stochastic %K | 10 | ✅ supports |
| Volatility | Bollinger %B | 0.03 | ✅ supports |
| Volatility | ATR% | 2.84 | · context |
| Volume | Volume vs 20d | 1.0x | · context |
| Volume | MFI | 28 | ✅ supports |
| Structure | Dist to 20d low/high | lo +0.9% / hi -9.7% | ✅ supports |
| Candle | Body / wicks | body 0.26%  up-wick 61%  lo-wick 25% | · context |
| Candle | Overnight gap | +1.1% | ✅ supports |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-03-30 13:55 px $201.50 (RSI 76, vol 0.6x)

### 2026-01-21 bullish_harami (long)

**Corroborating: 2  |  Contradicting: 2**  → next 5d: +5.06%

| Category | Signal | Value | Read |
|---|---|---|---|
| Trend | 200-EMA | above (+3.8%) | ✅ supports |
| Trend | EMA stack 9/20/50 | bull | ✅ supports |
| Trend | Dist from 20-EMA | -1.9% | · context |
| Momentum | RSI | 45 (neutral) | · context |
| Momentum | RSI slope | -9.8 | ❌ against |
| Momentum | MACD hist | -0.928 | ❌ against |
| Momentum | Stochastic %K | 27 | · context |
| Volatility | Bollinger %B | 0.31 | · context |
| Volatility | ATR% | 2.36 | · context |
| Volume | Volume vs 20d | 1.3x | · context |
| Volume | MFI | 51 | · context |
| Structure | Dist to 20d low/high | lo +2.9% / hi -7.6% | · context |
| Candle | Body / wicks | body 0.10%  up-wick 18%  lo-wick 78% | · context |
| Candle | Patterns firing | bullish_harami | · context |

- **5m confirmation:** VWAP reclaim at 2026-01-21 14:45 px $229.80 (RSI 91, vol 0.8x)
