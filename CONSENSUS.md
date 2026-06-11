# CONSENSUS — Key Research Findings

## OMNI Indicator (Oscar Carboni)

**Confirmed formula:** EMA(Low, 82)  
**Backtested on:** SPY daily bars, 2011-2026 (n=3,750 bars)

### Why EMA of Lows?

Oscar describes OMNI as "landing on the bottom of candles." Standard close-based EMA sits *through* the body; EMA of lows sits at the candle *floor*.

Variant comparison results:

| Variant        | Above Lows % | Avg Dist Low % | Cross-Up Hit% (5d) | n signals |
|----------------|-------------|----------------|---------------------|-----------|
| **ema_lows_82**| **99.1%**   | **+0.47%**     | **55.3%**           | 94        |
| ema_lows_87    | 99.0%       | +0.51%         | 54.3%               | 91        |
| ema_lows_89    | 99.1%       | +0.53%         | 54.0%               | 90        |
| hma_82         | 97.2%       | +0.50%         | 56.1%               | 94        |
| ema_lows_55    | 97.4%       | +0.28%         | 52.1%               | 108       |
| ema_close_87   | 90.3%       | +1.44%         | 52.1%               | 88        |

**Why period 82:** Highest `above_lows_pct` combined with a compact average distance (+0.47%) — it sits just above lows without floating too high.

### SPY Cross-Up Hit Rates (SPY-specific, 2011-2026)

| Horizon | Hit Rate | Avg Return | n    |
|---------|---------|------------|------|
| 1d      | 51.1%   | +0.16%     | 94   |
| 5d      | 55.3%   | +0.44%     | 94   |
| 10d     | 60.6%   | +0.88%     | 94   |
| **20d** | **81.9%**| **+1.74%** | **94** |

The 20-day result is exceptional. When SPY's close crosses above OMNI(82), 82% of the time SPY is higher 20 trading days later.

### ML Features (added to ALL_FEATURES, v1.5)

| Feature          | Description                                           |
|------------------|-------------------------------------------------------|
| `omni_82_value`  | Raw EMA(Low, 82) indicator value                      |
| `omni_82_above`  | 1.0 if Close > OMNI, else 0.0                         |
| `omni_82_distance` | (Close − OMNI) / OMNI — % above or below            |
| `omni_82_slope`  | (OMNI − OMNI[−5]) / OMNI[−5] — fractional trend     |
| `omni_82_bounce` | 1.0 if Low within 0.5% of OMNI and Close > Open      |

### Conditional Patterns (migration 0015)

- `omni_82_cross_up` / `omni_82_cross_down` — trend change signals
- `omni_82_above_3d` / `omni_82_above_5d` — sustained above OMNI
- `omni_82_bounce` / `omni_82_bounce_1pct` — support hold entry
- `omni_82_green_slope` — above OMNI with rising OMNI (strongest)

---

## OSCAR Oscillator

**Formula:** `A = max(High, N); B = min(Low, N); rough = (Close - B)/(A - B)*100; oscar[i] = oscar[i-1]*2/3 + rough*1/3`

A smoothed stochastic oscillator (0–100 range). Cross above 50 = bullish signal.

### SPY Cross-Up Hit Rates by Period

| Period | n signals | Hit% 5d | Avg Ret% |
|--------|-----------|---------|---------|
| 8      | 188       | 61.2%   | 0.195%  |
| 21     | 92        | 62.0%   | 0.088%  |
| 34     | 64        | 64.1%   | 0.054%  |
| 55     | 51        | **76.5%** | **0.540%** |
| 87     | 33        | 69.7%   | 0.858%  |
| 89     | 33        | 72.7%   | 0.790%  |

Period 55 has best hit rate; period 87 has best return-per-signal.

---

## Implementation Files

- `src/atlas_research/features/omni_proxy.py` — all indicator functions
- `src/atlas_research/conditional/engine.py` — 33 condition evaluators
- `db/migrations/0013_omni_oscar_patterns.sql` — OSCAR/OMNI-87 patterns
- `db/migrations/0014_omni_lows_patterns.sql` — EMA-of-lows variants
- `db/migrations/0015_omni_82_patterns.sql` — OMNI-82 confirmed patterns
- `config/settings.py` — OMNI_FEATURES added to ALL_FEATURES
