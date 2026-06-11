# Signal Expansion Roadmap

Atlas Research conditional probability engine — signal categories, patterns, and implementation status.

---

## Signal Categories

### 1. Classic Mean-Reversion / Momentum (original 0010)
| Pattern | Condition | Universe |
|---------|-----------|----------|
| consecutive_down_3/5 | N consecutive down days | SP500 |
| consecutive_up_3/5 | N consecutive up days | SP500 |
| oversold_rsi_30/35 | RSI < threshold | SP500 |
| overbought_rsi_70 | RSI > threshold | SP500 |
| gap_down_2/4pct | Open gap down ≥ N% | SP500 |
| near_52w_low_5pct | Within 5% of 52-week low | SP500 |
| near_52w_high_5pct | Within 5% of 52-week high | SP500 |
| high_volume_2x | Volume ≥ 2× 20-day avg | SP500 |

### 2. SPY-Specific Directional (added mid-session)
| Pattern | Condition | Universe |
|---------|-----------|----------|
| spy_down_3d/4d/5d | SPY down N consecutive days | SPY |
| spy_up_3d/4d/5d | SPY up N consecutive days | SPY |

**Key finding:** spy_down_5d shows 72.9% 5-day hit rate (n=48) — strongest mean-reversion signal in the dataset.

### 3. Technical Structure (migration 0012)
| Pattern | Condition | Notes |
|---------|-----------|-------|
| nr7 | Today's range narrowest of last 7 days | Volatility contraction signal |
| breakout_52w_high | Close > prior 52-week high | Momentum breakout |
| volume_climax_down | Vol ≥ 2× avg AND down day | Capitulation / selling exhaustion |
| volume_climax_up | Vol ≥ 2× avg AND up day | Euphoria / buying exhaustion |
| gap_up_2/4pct | Open gap up ≥ N% | Gap-fill mean reversion |
| near_52w_high_3pct | Within 3% of 52-week high | Tighter resistance test |
| near_52w_low_3pct | Within 3% of 52-week low | Tighter support test |
| oversold_rsi_25 | RSI < 25 | Extreme oversold |
| overbought_rsi_65 | RSI > 65 | Slightly overbought |
| consecutive_down_2/up_2 | 2-day streaks | Short-term momentum |

### 4. Intermarket / Cross-Asset (migration 0012)
| Pattern | Condition | Universe | Rationale |
|---------|-----------|----------|-----------|
| tlt_up_5d | TLT up 5 consecutive days | TLT | Risk-off signal: bonds rising |
| tlt_down_5d | TLT down 5 consecutive days | TLT | Risk-on signal: bond selloff |
| gld_up_5d | GLD up 5 consecutive days | GLD | Inflation / safe-haven demand |
| spy_below_sma200 | SPY < 200-day SMA | SPY | Bear market regime |
| spy_above_sma50 | SPY > 50-day SMA | SPY | Bull market regime |
| vix_spike_30 | VIX > 30 | ^VIX | Fear spike — historically bullish for equities at extremes |

### 5. Calendar / Seasonal (migration 0012)
| Pattern | Condition | Notes |
|---------|-----------|-------|
| end_of_month_3d | Last 3 trading days of month | Institutional rebalancing window |
| turn_of_month_3d | First 3 trading days of month | Fresh capital deployment |
| monday_seasonality | Trades on Monday | Weekend news digestion |
| friday_seasonality | Trades on Friday | Pre-weekend position squaring |

**Implementation note:** Calendar patterns look at returns of the full SP500 universe on these dates, not a filtered sub-universe.

### 6. OMNI — EMA(Low, 82), Confirmed (migrations 0013, 0014, 0015)

**Confirmed formula: EMA(Low, 82)**  
Oscar describes OMNI as landing "on the bottom of candles." Backtests confirm EMA(Low, 82) sits at the candle floor (99.1% of bars above the low) with a 81.9% hit rate for SPY 20-day forward returns after cross-up.

| Pattern | Condition | Notes |
|---------|-----------|-------|
| omni_82_cross_up | Close crosses above EMA(Low, 82) | OMNI "turns green" |
| omni_82_cross_down | Close crosses below EMA(Low, 82) | OMNI "turns red" |
| omni_82_above_3d | Close above OMNI for 3+ days | Sustained green |
| omni_82_bounce | Low within 0.5% of OMNI + Close > Open | Support hold entry |
| omni_82_green_slope | Above OMNI AND slope rising | Strongest long condition |

**ML features added (ALL_FEATURES v1.5):**
- `omni_82_value` — raw indicator value
- `omni_82_above` — 1.0 if Close > OMNI
- `omni_82_distance` — (Close − OMNI) / OMNI (%)
- `omni_82_slope` — fractional change in OMNI over 5 bars
- `omni_82_bounce` — support hold binary

**SPY 20-day cross-up hit rate: 81.9% (n=94, 2011–2026)**

### 7. OSCAR Oscillator — Fibonacci Periods (migration 0013)
**Formula:** OSCAR(N) = smoothed stochastic  
```
A = rolling_max(High, N)
B = rolling_min(Low, N)
rough = (Close - B) / (A - B) * 100
oscar[i] = oscar[i-1] × 2/3 + rough × 1/3
```
Cross above/below 50 = signal trigger (analogous to stochastic crossover)

| Pattern | Period | Fibonacci? |
|---------|--------|-----------|
| oscar_34_cross_up | 34 | Yes (F9) |
| oscar_55_cross_up | 55 | Yes (F10) |
| oscar_87_cross_up | 87 | Near F(10)+F(9) |
| oscar_89_cross_up | 89 | Yes (F11) |
| oscar_144_cross_up | 144 | Yes (F12) |

**SPY variants:** spy_oscar_87_cross_up, spy_oscar_55_cross_up, spy_oscar_89_cross_up

**ML features added:** `oscar_87_value` (oscillator value 0-100), `oscar_87_above_50` (binary)

---

## ETF Universe (config/universe.csv)
Added for intermarket and sector analysis:

| Ticker | Description |
|--------|-------------|
| SPY, QQQ, IWM, DIA | Broad market benchmarks |
| XLK, XLF, XLE, XLV, XLI, XLP, XLU, XLY, XLB, XLRE, XLC | SPDR sector ETFs |
| GLD | Gold — inflation / safe-haven |
| TLT | 20+ year Treasury — interest rate / risk-off |
| UUP | US Dollar index — currency regime |
| HYG, LQD | High-yield and investment-grade credit — risk appetite |
| ^VIX | CBOE Volatility Index — fear gauge |
| ^TNX | 10-year Treasury yield |

---

## Sector → Ticker Mapping (for transcript extraction)
Oscar's language → tradeable symbols used in extraction prompt:

| Oscar Says | Maps To |
|-----------|---------|
| "tech" / "technology" | XLK |
| "financials" / "banks" | XLF |
| "energy" / "oil" / "crude oil" | XLE |
| "healthcare" / "biotech" | XLV |
| "industrials" | XLI |
| "consumer staples" / "staples" | XLP |
| "utilities" | XLU |
| "consumer discretionary" / "retail" | XLY |
| "materials" / "copper" | XLB |
| "real estate" / "REIT" | XLRE |
| "communication" / "media" | XLC |
| "gold" / "precious metals" | GLD |
| "bonds" / "treasuries" | TLT |
| "small caps" / "Russell" | IWM |
| "Nasdaq" | QQQ |
| "Dow" / "blue chips" | DIA |
| "S&P" / "the market" | SPY |
| "VIX" / "volatility" | VIX |

---

## Implementation Files
| File | Role |
|------|------|
| `src/atlas_research/conditional/engine.py` | Condition evaluators + backtest runner |
| `src/atlas_research/features/omni_proxy.py` | OMNI/OSCAR computation (pure numpy) |
| `src/atlas_research/features/feature_factory.py` | ML feature pipeline (calls omni_proxy.compute) |
| `db/migrations/0010_conditional_probability_engine.sql` | Original 12 patterns |
| `db/migrations/0012_expanded_signals.sql` | 24 new patterns (calendar, intermarket, technical) |
| `db/migrations/0013_omni_oscar_patterns.sql` | 16 OMNI/OSCAR patterns |
| `db/migrations/0014_omni_lows_patterns.sql` | 19 EMA-of-lows variant patterns |
| `db/migrations/0015_omni_82_patterns.sql` | 12 OMNI-82 confirmed patterns |
| `config/settings.py` | OMNI_FEATURES in ALL_FEATURES (model training) |
| `config/universe.csv` | 193 securities including sector ETFs |
| `scripts/ingest_transcripts.py` | Transcript ingestion with sector mapping in SYSTEM_PROMPT |

---

## Pattern Count Summary
| Migration | Patterns Added | Total |
|-----------|---------------|-------|
| 0010 | 12 | 12 |
| (session) | 4 SPY-specific | 16 |
| 0012 | 24 | 40 |
| 0013 | 16 | 56 |
| 0014 | 19 | 75 |
| 0015 | 12 | 87 |
