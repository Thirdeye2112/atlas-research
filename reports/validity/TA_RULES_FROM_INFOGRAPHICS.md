# Trading Rules Mined from Infographics (set 1 of ~3)

Purpose: extract concrete, **backtestable** rules from trader infographics to
enhance the Atlas candlestick/MTF system. Everything here is a HYPOTHESIS to
test against our data — consistent with the finding that candlesticks alone are
a coin flip (see CANDLESTICK_LEARNING_LOG.md iter 1-3). The recurring message
across all sources: **patterns are timing, not direction; the edge is the
trend filter + stock selection + selectivity + risk-defined exits.**

Sources: Ishan/EdgeWithIshan, GreenWorkshops, Mark Minervini (SEPA).

---

## A. Trend / structure gates  → upgrade the structure classifier
Replaces my crude 20-day-return / 10-week-return buckets with battle-tested defs.

**EMA stack (9 / 21 / 50 / 200), daily:**
- Price **> 200 EMA** → long-only regime ("only BUY"). Below → avoid.
- **21–50 EMA = the pullback zone** → where controlled-pullback entries live.
- Price **< 50 EMA** → avoid the stock.
- Rule: "Never buy strength — buy controlled pullbacks." (entry in pullback zone, not at highs)
- Exit fully **below 50 EMA**.

**Weekly primary trend:** price above the **30-week MA** → engage; below → protect capital.
(30-wk ≈ 150-day; this is our weekly gate, better-defined than the 10-wk return.)

**Minervini Trend Template (daily, all must hold):**
1. Price > 50, 150, 200 SMA
2. 50 SMA > 150 SMA > 200 SMA (proper stacking)
3. 200 SMA rising ≥ ~1 month
4. Price within 25% of 52-week high
5. Price ≥ 30% above 52-week low

All computable from raw_bars (daily). → build `trend_template_pass` boolean +
`ema_regime` (above200 / pullback_zone / below50) per ticker/date.

## B. Stock selection  → selectivity filter ("trade only the best")
- **Relative Strength**: stock beats the index; RS Rating > 70 (ideally 85-90+).
  We already have rs_spy_20/60/120 → formalize a cross-sectional RS percentile.
- **Structure**: higher highs + higher lows (uptrend skeleton).
- **Volume**: heavy/expanding volume on breakouts; institutional accumulation
  = increasing volume on up days.

## C. Setup definition  → the "A+ setup" subset (the missing high-prob filter)
Two archetypes, both require trend gate (A) + selection (B):
1. **Controlled pullback**: in an uptrend (price>200EMA, RS strong), pull back
   into the 21–50 EMA zone, then a bullish trigger candle → enter next day
   above the bullish candle's high. (= the bull-flag/continuation idea.)
2. **Tight-base / VCP breakout**: volatility contraction (shrinking ATR/range,
   tightening bases) → breakout above the base on heavy volume, price above a
   rising MA.
"Without setup → no trade. No exceptions." → encode as a confluence threshold:
only score events that pass trend + selection + setup.

## D. Outcome / exit framework  → R-MULTIPLE labeling (big upgrade)
Our backtest currently labels outcomes as fixed-horizon close-to-close returns
(return_12 etc.). These sources define success in **R-multiples**:
- **Risk (R)** = entry − stop, stop = just **below recent swing low**.
- **Position size** = (Capital × 1%) ÷ R  (fixed fractional risk).
- **Target** = minimum **1:2 R:R**; book partial at 2R; exit remainder below 50 EMA.
→ New outcome label per setup: did it reach **+2R before hitting the swing-low
stop** (win) or stop-out first (loss)? This is far more realistic than a fixed
12-day return and matches the swing focus. Compute from the bar path (we have
MFE/MAE machinery already in intraday_outcomes).

## E. Execution principles  → design constraints (not directly codeable)
- Fewer trades, A+ only; "no edge = no trade"; patience > activity.
- Define exit BEFORE entry; don't exit emotionally; great setups retest.
- "The move wasn't the opportunity — the execution was."
→ Encode indirectly: high selectivity (C), predefined R-multiple exits (D), and
  measuring whether the *plan* (2R target / swing-low stop) would have worked.

---

---

# Set 2 (MACD/RSI/EMA roles, Kotegawa, Stage Analysis, "Learn Again")

## F. Indicator ROLES — confluence stack (we already have rsi_14, macd_histogram)
- **EMA = direction** (foundation; "no EMA bias → no trade"). Ignore in chop.
- **MACD = trend-strength CONFIRMATION, not entry**: histogram rising = momentum
  intact; use to hold winners / avoid early exits. (12,26,9). Histogram > crossover.
- **RSI = pullback TIMING, most misused**: use RSI *cooling* inside an uptrend to
  time a healthy pullback entry — NOT as an oversold-reversal / top-bottom picker.
  "RSI confirms, it never predicts." Never use RSI against the trend.
- **Combine:** EMA defines direction → MACD confirms strength → RSI times the
  pullback. **If EMA & MACD disagree, wait** (require agreement = confluence gate).
→ Encodable now: regime(EMA) AND macd_histogram>0/ rising AND rsi pullback-then-turn.

## G. STAGE ANALYSIS (Weinstein) — the master trend classifier  ⭐ new
Classify every ticker/date into a stage using the **30-week MA** (≈150-day) +
slope + structure. This supersedes my up/down/flat buckets:
- **Stage 1 Accumulation**: sideways tight base, low vol, MA flattening. (no rush)
- **Stage 2 Advancing/Markup**: clean breakout, higher highs+lows, price > rising
  30-wk MA. **← the ONLY stage to buy longs.**
- **Stage 3 Distribution**: price stalls near top, wider candles, failed breakouts,
  vol rising. (reduce exposure)
- **Stage 4 Decline**: breakdown, lower highs+lows, below MA. (stay out / short only)
Rule: buy only Stage 2; hold while price > 30-wk MA; reduce in Stage 3; out in Stage 4.
→ Build `stage` (1-4) from raw_bars: 30-wk MA level+slope, price vs MA, HH/HL structure.

## H. Consolidation → breakout trigger (Kotegawa / VCP, precise)  ⭐ new
Quiet base (ALL true): range tight over last N bars, **no candle > 1.5× recent
average** range, MA flat (not falling), low volatility/interest.
**Imbalance/entry trigger**: breakout candle **CLOSES above the range high (not a
wick)**, candle size **≥ recent average** (range expansion), price **> 30-wk MA**.
**No trade if**: price far above MA (extended/chased), move already printed (late).
→ Encodable: base-tightness detector (rolling range/ATR contraction) + breakout
  bar with close>range_high & size>=avg & not-extended. Pairs with the 5-min layer
  as the *trigger* timeframe.

## I. Risk circuit breakers (reinforced across sources)
- 1–2% capital risk/trade; stop below recent swing low; size = risk ÷ stop-dist.
- **3 consecutive losses → idea is wrong, stop & reassess** (regime circuit breaker).
- Don't chase extended price; "one setup only."

## CONVERGENCE (why these are strong priors)
Independent successful traders repeat the SAME few mechanics — treat as high-prior
hypotheses to test first:
1. **30-week MA as the master trend gate** (Kotegawa, Weinstein Stage 2, Minervini
   150-day, GreenWorkshops) — appears in nearly every source.
2. **Tight base → volatility-expansion breakout** (VCP, Kotegawa quiet→imbalance,
   Stage 1→2) — the dominant entry archetype.
3. **Indicators = confirmation/timing, never standalone signal** (matches our
   iter-1..3 finding that candles alone are a coin flip).
4. **Selectivity + fixed-risk R-multiple exits** over prediction.

## Proposed next experiment (ties it together)
On the clean tradeable universe, define the **A+ long setup**:
`price > 200EMA  AND  RS_percentile > 70  AND  (pullback into 21–50 EMA OR tight-base breakout)  AND  volume confirmation`
then label outcomes as **2R-target-before-swing-low-stop**, and compare win-rate
/ expectancy of A+ setups vs. all-events baseline. Hypothesis: selectivity +
trend filter + R-multiple exits turns the candlestick coin flip into a real
edge. The 5-min layer then becomes the entry *trigger* within an A+ daily setup.
