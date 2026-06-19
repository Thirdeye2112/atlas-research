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

## Iteration 5-6 — 5-min SMC trigger gated by daily Stage-2 (the pivot that worked)

Built compute-once event table (extract_5m_events.py, 2.55M Stage-2-gated 5m
BOS/sweep triggers, top 2000 liquid) + instant sweeper (sweep_5m_events.py).
R-multiple outcomes (target vs swing-low stop), train + last-12mo OOS, net 0.05R cost.

**The daily Stage-2 gate lifts the 5m trigger** (iter 5: BOS +0.097->+0.139R gross).
Full sweep (iter 6) maps the win-rate/target tradeoff:

| bos +vol+rsi+notext | target | win% OOS | exp OOS (net) |
|---|---|---|---|
| | 1.0R | 48.7 | -0.032 |
| | 1.5R | 38.6 | +0.017 |
| | 2.0R | 31.2 | +0.060 |
| | 2.5R | 25.4 | +0.097 |
| | 3.0R | 20.8 | +0.125 |

**Findings:**
- First OOS-positive, cost-surviving edge in the project: bos + Stage-2 + full
  confluence, +0.10..0.125R OOS at 2.5-3R. Confluence helps win at every target.
- Sweep (liquidity-grab) trigger is weaker than BOS; often negative net of cost.
- **Win-rate vs target tradeoff is exhausted**: high win% (≈48% @1R) loses money
  (cost + stops); profitable configs win only ~20-31%. Low win rate is NORMAL for
  a breakout system. Target tuning cannot give both high win% AND positive exp.
- Cost (0.05R) is optimistic for 5m; the 3R config has the most cushion.

**Next lever (not targets): entry/stop quality** — retest/pullback entry with a
tighter structure stop + VCP base requirement. Built in iter 7.

## Iteration 7 — retest entry + VCP (FULL universe, 3.55M events)

Correcting a 25-ticker preview that looked like a VCP breakthrough — it did NOT
hold at scale:
- **VCP ≈ plain confluence** at full scale (no real lift). full+vcp@1.5R was
  +0.055R on 25 tickers but **-0.008R train** on the full set.
- **Retest entry is decisively negative everywhere** (tight structure stop gets
  noise-stopped on 5m). Dropped.
- **No config clears 40%+ win AND positive on both splits.** Win-rate ceiling for
  these 5m breakouts is ~48-50% (at 1R) — just under the cost-adjusted breakeven
  (~52%). Win rate is NOT improvable past ~30% while staying profitable.
- Robust edge = bos + confluence @2.5-3R: ~20% win, +0.06-0.09R TRAIN net of
  0.05R cost (OOS higher, but 2025-26 bull tailwind, not robustness).

**Conclusion:** 5-min Stage-2 breakouts are a genuine but modest, low-win-rate,
cost-sensitive, fat-tailed edge. Target/confluence/VCP/retest are exhausted.
The one untested lever is EXIT design (partial-at-1R + trailing runner), which
needs richer path capture than the current summary. Otherwise: accept the
low-win-rate profitable profile, or stress-test cost (0.10R) + regime split.

---

## Iteration 8 — EXIT design solves it (full universe, 2.07M events, 1,904 tickers)

The win-rate problem was an EXIT problem, not a selection problem. With a
breakeven+trailing-runner exit (move stop to BE at +1R, then trail giving back
1R from the peak), the bos + Stage-2 + confluence setup achieves:

| exit (full confluence) | win_tr | exp_tr | win_oos | exp_oos | exp_oosNON-bull | exp@0.10R |
|---|---|---|---|---|---|---|
| fixed_2R   | 39% | +0.037 | 40% | +0.060 | +0.005 | +0.010 |
| fixed_3R   | 35% | +0.090 | 36% | +0.125 | +0.061 | +0.075 |
| **be_runner** | **50%** | **+0.298** | **51%** | **+0.345** | **+0.263** | **+0.295** |
| partial    | 50% | +0.127 | 51% | +0.157 | +0.096 | +0.107 |

**be_runner passes every robustness gate** (positive train AND OOS AND non-bull
regime AND at 0.10R cost) AND held at full scale (where VCP did not). It
dominates all fixed/partial exits on both win% (~50%) and expectancy (~+0.3R).

Recommended config: **5m BOS, daily Stage-2 gate, confluence (vol+rsi+notext),
breakeven@1R + trail give-back-1R, ~1-day horizon.** (VCP optional; ~no lift.)

Caveats: expectancy is mean R — fat-tailed (trail captures big runners; many
trades exit ~breakeven, hence ~50% "win"). Horizon is 1 day (intraday/overnight),
not multi-day swing. Frequent signals (~1/ticker/day) -> in practice take a subset.

Status: this is the project's first robust, win-rate-respectable, cost- and
regime-surviving edge. Next: productionize (wire as an Atlas signal; paper-validate).

---

## (superseded) Fixes that were queued for Iteration 3
1. **Compute a real prior_trend** from raw_bars (e.g. N-day return / SMA slope before the
   signal) — done in analysis (join events→raw_bars), no 8h re-run needed.
2. **Exclude warmup-default artifacts** (idx<20) from all stats.
3. **Swing-pivot analysis (user idea):** detect local highest-highs / lowest-lows over a
   window and study which patterns + contexts cluster around true swing turns.
4. Keep the tradeable filter (price ≥ $5, $vol ≥ $1M); treat pennies as noise except on
   volume-backed big moves (flag & analyze those separately).

## Iteration 9 — Portfolio reality check (deflates iter 8)

Turned the be_runner per-trade edge into a portfolio (1% risk/trade sizing,
max-concurrent cap, 2% daily-loss, compounding) on full confluence.

- **R distribution is extreme**: median R = 0.00 (half exit ~breakeven), mean
  +0.36 carried by a tiny tail (q99.9=19R, **max=815R** = untradeable artifact).
- Capping runners at a realistic 3R: edge = +0.119R train / +0.150R OOS net cost
  (vs +0.30 uncapped). Real but modest.
- Portfolio at REALISTIC settings (max 3 trades/day, 3R cap, 1% risk):
  TRAIN 2.03x / 17% CAGR / Sharpe 0.61 / maxDD -55%; **OOS 0.80x / -20% CAGR /
  Sharpe -0.62**. OOS LOSES at honest sizing; drawdowns severe.
- The eye-popping high-concurrency multiples (10000x+) are compounding artifacts
  (risking 20%/day) — not real.

**Verdict: NOT deployable as-is.** The iter-8 ~50%-win/+0.3R was true per-trade
but does not survive realistic sizing OOS. Root cause: trigger fires far too
often (400k signals); we never truly applied "A+ only / few trades" selectivity.
Do NOT wire into Atlas yet. Next: drastically increase selectivity (fewer,
higher-quality setups), re-run portfolio; this also motivates steps 3 (audit)
and 4 (learning loop).

## Iteration 10 — Audit-corrected portfolio (artifact-free, realistic stops)

Stop-floor (v4) dropped max R 815->29 but be_runner mean expectancy barely moved
(+0.303 train / +0.356 OOS full confluence) -> the edge mean is NOT an artifact
of the extreme outliers (too rare); it's the legitimate fat tail (q95~3.7R).

Portfolio (be_runner, full confluence, r_cap 10R, 1% risk, realistic stops):
- TRAIN: 3/day 16x Sharpe 1.73 DD -27%; 5/day 132x Sharpe 2.25 DD -26%.
- OOS:   3/day 1.04x +3.8%CAGR Sharpe 0.18 DD -24%; 5/day 1.60x Sharpe 1.08 DD -29%.
- High-concurrency (10-20/day) multiples are compounding artifacts -> ignore.

Note: iter-9's "OOS loses" used a 3R cap that removes the fat tail the edge needs;
the honest picture (r_cap 10) is MARGINAL positive OOS, fat-tail-dependent, ~25-30% DD.

**Audit verdict:** method sound (no lookahead, realistic stops, costs+regime applied);
data is the overhang (free IEX 5m thin -> stop-floor mitigates, SIP would be cleaner);
edge is real but marginal/fragile/high-DD. Needs better TRADE SELECTION (step 4
learning loop) before it's trustworthy or deployable. Atlas wiring still on hold.
