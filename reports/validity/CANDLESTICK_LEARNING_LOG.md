# Candlestick Knowledge Layer — Learning Log

A running, append-only log of the iterative loop: measure → diagnose → fix → re-run.
Every number comes from a query actually executed against candlestick_events /
candlestick_outcomes (full-DB backtest, 2020-01-01 → 2026-06-17, daily bars).

Return horizons are TRADING DAYS: return_1/6/12/24. Primary swing horizon = **12d (~2.5 wks)**.
Directional win = bullish→fwd>0, bearish→fwd<0. Win-rate is outlier-robust; means are not.

---

## Iteration 1 — Naive win/loss (baseline)

**Data:** 6,162 tickers, 4,470,398 events/outcomes, 0 errors.

**Finding — the mean is contaminated, the median is the truth.**
- `max(return_12) = +2,499,900%`. Means are garbage; baseline *mean* 12d = +6.2% but
  *median* = **−0.17%**, fracup = **47.7%** (this universe bleeds down).
- Every pattern clusters at median −0.7%…0.0%, up-rate 45–48.7%. **No directional
  separation between patterns.** Bullish patterns are the *worst*
  (Three White Soldiers −0.69% / 45% up).
- Volume slice: `low` vol = median −0.48% / 44.8% up (worst); normal/high ≈ −0.05% / ~48%.
  → **low-volume events are noise/bleed.**

**Verdict:** raw candlestick patterns alone have ~zero (slightly inverted) directional edge.

---

## Iteration 1.5 — Data-quality root cause + cleaning

- Contamination is **sub-penny, ~zero-volume dead tickers** (Yahoo $0.0001 placeholder /
  unadjusted reverse-split prints). e.g. PPCB 2025-01-29: $0.01 → "$625" on 32 shares.
  Confirmed `adjusted_close` carries the same bad jump (not a split-column bug).
- Scale: |daily move|>50% = 5,570 bars/1,424 tickers; >500% = 254 bars/114 tickers (≈0.08%).
- **Tradeable filter** (price ≥ $5 & dollar-vol ≥ $1M at the signal bar) keeps 2,676,029
  of 4.47M events and makes means sane (range −0.71%…+0.07%).
- On the CLEAN universe @12d, win-rates still ~50% (bearish 50.1–51.6%, bullish 46.9–49.5%);
  inversion persists. **Cleaning removes the garbage but does not create edge.**

TODO (data): build an outlier verifier vs an independent source (Stooq/yfinance) for
*borderline* big moves on liquid names (real news vs bad print). Obvious junk
(sub-penny / ~0 volume) is filtered deterministically without external lookup.

---

## Iteration 2 — Context conditioning (clean universe, 12d)

Sliced bullish/bearish pools by prior_trend, vwap_position, regime, volume_context.

**Bug found — `prior_trend` is a DEAD CONSTANT ('neutral' for 100% of events).**
`calculate_context()` reads `df.iloc[idx].get('prior_trend','neutral')` but the bars df
never has a `prior_trend` column, so it always defaults. (Same class of bug as the dead
`data_quality_score`.) **We have been evaluating reversal patterns with no knowledge of the
trend they're supposed to reverse.**

**The key insight:** candlestick reversal patterns are *conditional on a prior trend by
definition* — a Hammer after a downtrend is a bullish reversal; a Hammer in a flat drift is
nothing. With prior_trend broken, every reversal was scored context-blind → explains the
no-edge result.

Other slices:
- `vwap_position` above/below ≈ 50% (no edge). The "at" bucket (61% bearish / 35% bullish)
  is an **artifact of the idx<20 warmup default** (regime='neutral' & vwap='at' overlap the
  same ~7.9k rows) — exclude it.
- `volume_context`: high volume modestly aids follow-through; low volume hurts (bullish-low
  46.5% / med −0.58%). Confirms the volume-as-noise thesis.

**Verdict:** one-way context gives little; the missing ingredient is a *real* prior-trend
classification, plus the swing-pivot view (what happens at true highest-highs / lowest-lows).

---

## Iteration 3 — Multi-timeframe confirmation (weekly + daily)

Built a weekly+daily trend classifier from raw_bars (adjusted_close, split-safe):
WEEKLY = sign of ~10-week return (W-FRI closes); DAILY = sign of 20-day return.
Re-measured daily candlestick directional win @12d on the clean universe
(price>=$5, $vol>=$1M, ~4,280 tickers) conditioned on the higher-timeframe trend.

**Headline — trading WITH the weekly trend gives NO edge:**
| pool | vs weekly | n | win% |
|---|---|---|---|
| bull | with (uptrend)   | 129,686 | 49.0 |
| bull | against          | 122,832 | 50.0 |
| bear | with (downtrend) | 109,304 | 49.7 |
| bear | against          | 177,039 | 50.3 |

Across the full weekly×daily grid every real bucket sits **47.9–51.0%** (the only
outliers are tiny 'na'/warmup buckets, n<6k — ignore). Best real bucket ≈ 51%.
Notably **bull-in-confirmed-uptrend (weekly up + daily up) = 48.3%** — bullish
candles in extended uptrends slightly *mean-revert* (short-term exhaustion).

**Verdict (robust):** even with proper weekly+daily MTF confirmation, single
daily candlestick patterns have **no standalone 12-day edge**. This matches the
rigorous literature and is a real finding, not a pipeline failure — it tells us
the daily candlestick layer is not an edge by itself.

**Implication / pivot:** the edge (if any) lives in
(a) the **5-min entry-timing layer** — candlesticks may matter for intraday
    timing of a higher-TF setup (this was the user's original thesis: 5-min
    triggers confirmed by daily/weekly). The 5.5yr Alpaca 5-min pull enables
    this next.
(b) candlesticks as **features inside** the existing conviction/confluence/ML
    stack, not as standalone signals.
(c) high-selectivity setups (S/R, volume profile) rather than every instance.

Next: once 5-min ingest completes, run THIS SAME MTF methodology on 5-min
signals (5m pattern -> confirm vs daily+weekly trend -> measure outcome).

---

## Iteration 4 — A+ setup (convergent playbook) + R-multiple labeling

Built a daily Stage-Analysis + filter classifier (EMA 9/21/50/200, SMA 50/150/200,
ADX, RSI, MACD-hist, Weinstein stage, RS-vs-SPY, extension) and labeled outcomes
as R-multiples (2R target vs swing-low stop, 24d horizon, split-safe adj OHLC).
Tested on bullish candlestick events, full liquid universe (368,341 events).

| bucket | n | win%(2R) | exp(R) |
|---|---|---|---|
| ALL bullish events | 368,341 | 26.8 | +0.037 |
| +stage2 | 143,791 | 25.9 | +0.054 |
| +adx>25 | 145,876 | 25.8 | +0.039 |
| +pullback_zone | 28,569 | 32.0 | +0.030 |
| A+ (full stack) | 16,489 | 13.2 | +0.035 |

**Verdict:** the A+ stack (+0.035R) ≈ baseline (+0.037R) — NO edge at the daily
timeframe. Only Stage 2 gives a faint lift (+0.054R). Baseline ~breakeven is
mostly 2021-26 bull drift. (The earlier 30-ticker preview's +0.274R was
small-sample noise from mega-caps.)

**Conclusion across iter 1-4:** daily candlesticks carry no standalone swing edge,
and neither MTF trend confirmation (iter 3) nor the full convergent A+ filter
stack (iter 4) rescues them. The daily layer is **context/selection, not trigger**.
Next: move the trigger search to the **5-min layer** (now being ingested, ~5yr
deep) — SMC primitives (sweep+reclaim, FVG fill, BOS; TA_RULES set 4) gated by a
daily Stage-2 uptrend, labeled by the same 2R/swing-stop R-multiple.

---

## (superseded) Fixes that were queued for Iteration 3
1. **Compute a real prior_trend** from raw_bars (e.g. N-day return / SMA slope before the
   signal) — done in analysis (join events→raw_bars), no 8h re-run needed.
2. **Exclude warmup-default artifacts** (idx<20) from all stats.
3. **Swing-pivot analysis (user idea):** detect local highest-highs / lowest-lows over a
   window and study which patterns + contexts cluster around true swing turns.
4. Keep the tradeable filter (price ≥ $5, $vol ≥ $1M); treat pennies as noise except on
   volume-backed big moves (flag & analyze those separately).
