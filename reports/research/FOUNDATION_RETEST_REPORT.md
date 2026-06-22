# Foundation Retest: One Stock, Conditional TA, Timeframe Corroboration

**MEASURE & REPORT ONLY.** Tests the hypothesis that scoring every TA tool at every bar and averaging (setup-formation v2's confluence approach) washes out moments where a SPECIFIC tool, in a SPECIFIC state, with higher-timeframe agreement, actually has edge. One stock (**AAPL**), examined deeply, conditional triggers only -- not kitchen-sink averaging. Run without auto-approving prose verdicts: numbers first, conclusions second. A null is a valid, expected result; this report does not tune toward a positive.

- **Run ID:** `20260622T054700Z-5809600e`
- **Git commit:** `25accacc430d3c43cb96a21fcf51b47aba81dbfa` (branch `research/foundation-retest`)
- **Timestamp (UTC):** 2026-06-22T05:47:26.862561+00:00
- **Ticker:** AAPL (5m), 67,241 bars [2023-01-03 14:30:00+00:00 .. 2026-06-18 17:10:00+00:00]
- **Walk-forward split:** 70% train / 30% held-out, split at 2025-06-05 17:25:00+00:00
- **K horizons (bars):** [3, 6, 12] | **R multiples / ATR stop:** [1, 2, 3] / 1.0x ATR
- **Total wall time:** 26.6s
- **Trigger instances:** 181,677 trigger x K rows, 100,863 baseline rows

## Stock selection

**AAPL**, not SPY. This is the one ticker present in every phase of this research arc (setup-formation v1/v2, pattern-fulfillment, dome-leg) -- the deepest existing context to cross-reference against. SPY is an index ETF (a composite of 500 names with fundamentally different participation/arbitrage dynamics), which would not extend the "four prior single-name 5m tests" comparison this run is meant to continue. AAPL is also genuinely liquid with a long, clean 5m history (2023-01-03 onward, confirmed in Step 0).

## Step 0. Data / execution integrity audit

**Session grid, duplicates, OHLC sanity:** 67,241 5m bars, zero duplicate (ticker, ts) rows, zero OHLC sanity violations (high>=low, close within [low,high] always held). Per-day bar-count distribution: 857 full 78-bar sessions, 7 known-holiday 42-bar half days (Thanksgiving Fri, July 3, Christmas Eve -- all calendar-correct), 2 other partial days (1 legitimate half day with some additional internal gaps on 2025-07-03, 1 the most-recent/still-accumulating day), and **one genuine, unexplained short day** (2024-12-23, only 11 bars ending 10:20 ET -- not a known holiday or half day). Flagged for transparency; at 11 of 67,241 bars (0.02%) it cannot materially affect any aggregate result in this report. 3 isolated zero-volume bars (0.004%), scattered, OHLC otherwise sane on each. Timezone conversion verified correct across DST transitions (every session's first bar converts to exactly 09:30 America/New_York, summer and winter alike).

**PIT/causality spot-check (hand-recomputed independently, not by re-running compute_features and comparing to itself):** EMA9, RSI14, VWAP, and ATR14 at a bar deep in the dataset (index 50000) were each recomputed from raw OHLCV using only bars at or before that index, by separate from-scratch code. All four matched `compute_features()`'s output to floating-point precision -- confirms these columns are genuinely causal, not just claimed to be.

**A genuine bug was found and is the headline Step 0 result.** `compute_features()`'s `vwap_cross_up` column is broken: `above_vwap.shift(1)` upcasts a bool Series to `object` dtype to hold the leading NaN, and Python's `~` operator on that object-dtype series triggers bitwise-int semantics (`~True`=-2, `~False`=-1, **both truthy**), so `above_vwap & ~above_vwap_prev` collapses to just `above_vwap` itself. Verified independently: a genuine binary crossing series must have equal (+-1) up- and down-transition counts; the stored `vwap_cross_up`/`vwap_cross_down` columns showed 34,954 vs 3,121 -- a 10-to-1 violation of that identity, while a from-scratch manual transition count gave 3,121 vs 3,121 (balanced, matching `vwap_cross_down`, which is unaffected -- it negates the proper bool-dtype `above_vwap` column directly, never the shifted/upcast one). **This bug is in shared production code and was not fixed here** (this branch is read-only on existing code) -- this study's own `vwap_reclaim` trigger is computed safely instead, via the same numpy-array shift pattern already used for the EMA-cross trigger. Retroactive implication: setup-formation v2's "vwap" confluence tool and pattern-fulfillment's "vwap" pattern (its single largest instance count, 151,692 rows) both used the buggy column for their bullish/reclaim side -- their reclaim-side numbers should be treated as unreliable; their loss/rejection-side numbers (using `vwap_cross_down`) were not affected.

All other tool definitions were independently balance-checked the same way (macd_bull_cross=2,558 vs macd_bear_cross=2,557 -- balanced; rsi/volume/ema rates all plausible) -- no other bug found.

## Step 1. The gap-protocol standard, applied

Read `src/atlas_research/ta/gaps.py` (branch `feat/gaps`) in full. What makes it sound, and what was carried into this study:

1. **State explicitly, per signal, the EXACT bar at which it becomes causally knowable** -- gaps.py's FVG docstring: "Look-ahead: CRITICAL. The FVG is ONLY confirmed at C3's CLOSE... Downstream consumers must not use this signal before C3 closes." Applied here: every one of this study's 8 tool families has an explicit code-comment stating its exact knowable-at bar -- most critically the swing-pivot trigger (decision_idx = pivot_idx + width, not pivot_idx -- the exact mistake research/dome-leg-verify found broken in a prior phase, applied correctly here from the start, not patched in afterward).
2. **Track detection-timestamp and confirmation-timestamp as distinct fields even when they coincide** -- gaps.py's schema carries both `ts` and `detect_close_ts` separately. Applied: this study's `decision_ts` is always defined as the earliest causally-knowable bar, never the bar that merely defines the pattern's geometry.
3. **Minimize and precisely enumerate which bars contribute to a signal** -- FVG detection uses only C1 and C3's high/low; C2's content doesn't matter, and the docstring says so explicitly. Applied: every trigger here is a single-bar instantaneous event (no multi-bar "early window" of the kind that caused research/dome-leg-verify's tautology finding).
4. **Reuse the textbook/existing definition rather than inventing thresholds** -- gaps.py uses the literal standard SMC/ICT 3-bar imbalance definition, no invented tolerance. Applied: 4 of the 8 tool families reuse `compute_features()`'s already-PIT-verified columns unmodified (RSI reclaim, MACD cross, VWAP -- recomputed safely per the Step 0 finding -- and the channel/swing-pivot machinery reused verbatim from prior phases); the FVG-fill trigger reproduces gaps.py's own `compute_fvgs()` logic exactly.
5. **Document input preconditions explicitly** -- gaps.py: "Must be sorted ascending by ts. Single ticker only." Applied throughout this study's own docstrings.

## Step 2. Conditional per-tool results: edge over baseline

8 tool families, 16 directional trigger_types, K in {3,6,12}. **48 (trigger_type x K) cells tested.** Baseline = random-direction entries, identical ATR R-bracket, same K, fixed seed -- note the baseline itself is not exactly zero (same mechanical reason found in pattern-fulfillment and dome-leg: "highest R-target reached before the stop" is asymmetric, wins uncapped at 1/2/3R, losses always exactly -1R). Edge = trigger expectancy MINUS the matching baseline cell's expectancy, in held-out data. Sorted by p-value (most tempting-looking first) -- **none survive correction; see the bold-faced BH-FDR column.**

| Trigger | K | n(is) | E(is) | n(ho) | E(ho) | Edge over baseline (ho) | p vs baseline | Survives BH-FDR |
|---|---|---|---|---|---|---|---|---|
| swing_pivot_high_confirmed | 3 | 2,262 | +0.0652R | 902 | +0.1236R | +0.0829R | 0.0079 | no |
| swing_pivot_high_confirmed | 6 | 2,262 | +0.0650R | 902 | +0.1485R | +0.0914R | 0.0090 | no |
| swing_pivot_high_confirmed | 12 | 2,262 | +0.0808R | 902 | +0.1457R | +0.0917R | 0.0128 | no |
| channel_break_down | 12 | 940 | -0.0230R | 447 | -0.0719R | -0.1259R | 0.0143 | no |
| channel_break_up | 6 | 1,036 | -0.0283R | 398 | -0.0685R | -0.1256R | 0.0203 | no |
| channel_break_up | 12 | 1,036 | -0.0291R | 398 | -0.0719R | -0.1260R | 0.0254 | no |
| channel_break_down | 6 | 940 | -0.0190R | 447 | -0.0533R | -0.1104R | 0.0262 | no |
| volume_spike_red | 3 | 1,852 | +0.0225R | 670 | +0.1284R | +0.0877R | 0.0326 | no |
| channel_break_up | 3 | 1,036 | -0.0400R | 398 | -0.0629R | -0.1037R | 0.0366 | no |
| channel_break_down | 3 | 940 | -0.0208R | 447 | -0.0517R | -0.0925R | 0.0430 | no |
| swing_pivot_low_confirmed | 3 | 2,131 | +0.1161R | 916 | +0.0928R | +0.0521R | 0.0901 | no |
| volume_spike_green | 3 | 2,026 | +0.0178R | 694 | +0.1075R | +0.0668R | 0.1056 | no |
| ema9_cross_up | 6 | 4,694 | +0.0426R | 2,074 | +0.0173R | -0.0398R | 0.1121 | no |
| volume_spike_red | 12 | 1,852 | +0.0318R | 670 | +0.1259R | +0.0719R | 0.1126 | no |
| ema9_cross_up | 12 | 4,694 | +0.0562R | 2,074 | +0.0145R | -0.0395R | 0.1309 | no |
| vwap_loss | 6 | 2,196 | +0.0279R | 925 | +0.0045R | -0.0526R | 0.1429 | no |
| volume_spike_red | 6 | 1,852 | +0.0268R | 670 | +0.1175R | +0.0605R | 0.1738 | no |
| swing_pivot_low_confirmed | 12 | 2,131 | +0.1141R | 916 | +0.1027R | +0.0487R | 0.1814 | no |
| vwap_loss | 3 | 2,196 | +0.0240R | 925 | -0.0020R | -0.0427R | 0.1833 | no |
| volume_spike_green | 6 | 2,026 | +0.0336R | 694 | +0.1144R | +0.0573R | 0.2017 | no |
| volume_spike_green | 12 | 2,026 | +0.0403R | 694 | +0.1119R | +0.0579R | 0.2072 | no |
| macd_bear_cross | 3 | 1,770 | +0.0209R | 787 | -0.0004R | -0.0411R | 0.2266 | no |
| rsi_reclaim_bull | 6 | 1,337 | +0.0670R | 643 | +0.0073R | -0.0497R | 0.2327 | no |
| macd_bull_cross | 6 | 1,770 | +0.0316R | 788 | +0.0155R | -0.0415R | 0.2747 | no |
| macd_bear_cross | 6 | 1,770 | +0.0292R | 787 | +0.0208R | -0.0363R | 0.3490 | no |
| swing_pivot_low_confirmed | 6 | 2,131 | +0.1190R | 916 | +0.0890R | +0.0319R | 0.3567 | no |
| macd_bull_cross | 12 | 1,770 | +0.0394R | 788 | +0.0216R | -0.0324R | 0.4153 | no |
| rsi_reclaim_bull | 12 | 1,337 | +0.0621R | 643 | +0.0222R | -0.0319R | 0.4655 | no |
| fvg_fill_bearish | 3 | 5,894 | +0.0534R | 2,431 | +0.0542R | +0.0135R | 0.5274 | no |
| macd_bear_cross | 12 | 1,770 | +0.0287R | 787 | +0.0305R | -0.0236R | 0.5598 | no |
| macd_bull_cross | 3 | 1,770 | +0.0293R | 788 | +0.0218R | -0.0190R | 0.5735 | no |
| ema9_cross_down | 6 | 4,693 | +0.0300R | 2,074 | +0.0443R | -0.0128R | 0.6127 | no |
| ema9_cross_down | 12 | 4,693 | +0.0386R | 2,074 | +0.0429R | -0.0111R | 0.6733 | no |
| ema9_cross_up | 3 | 4,694 | +0.0367R | 2,074 | +0.0319R | -0.0089R | 0.6953 | no |
| vwap_loss | 12 | 2,196 | +0.0169R | 925 | +0.0394R | -0.0146R | 0.6971 | no |
| fvg_fill_bearish | 12 | 5,894 | +0.0701R | 2,431 | +0.0624R | +0.0083R | 0.7369 | no |
| fvg_fill_bullish | 6 | 6,630 | +0.0846R | 2,420 | +0.0492R | -0.0079R | 0.7414 | no |
| rsi_reclaim_bear | 3 | 1,443 | +0.0043R | 594 | +0.0542R | +0.0135R | 0.7438 | no |
| ema9_cross_down | 3 | 4,693 | +0.0177R | 2,074 | +0.0336R | -0.0071R | 0.7548 | no |
| rsi_reclaim_bull | 3 | 1,337 | +0.0357R | 643 | +0.0298R | -0.0110R | 0.7760 | no |
| fvg_fill_bullish | 3 | 6,630 | +0.0846R | 2,420 | +0.0346R | -0.0061R | 0.7786 | no |
| vwap_reclaim | 6 | 2,196 | +0.0364R | 925 | +0.0473R | -0.0098R | 0.7848 | no |
| rsi_reclaim_bear | 12 | 1,443 | +0.0264R | 594 | +0.0660R | +0.0120R | 0.7993 | no |
| fvg_fill_bullish | 12 | 6,630 | +0.0852R | 2,420 | +0.0494R | -0.0046R | 0.8537 | no |
| vwap_reclaim | 12 | 2,196 | +0.0436R | 925 | +0.0578R | +0.0038R | 0.9196 | no |
| vwap_reclaim | 3 | 2,196 | +0.0296R | 925 | +0.0428R | +0.0021R | 0.9489 | no |
| fvg_fill_bearish | 6 | 5,894 | +0.0636R | 2,431 | +0.0575R | +0.0004R | 0.9860 | no |
| rsi_reclaim_bear | 6 | 1,443 | +0.0134R | 594 | +0.0571R | +0.0000R | 1.0000 | no |

**48 cells eligible (held-out n>=30), 0 survive BH-FDR at q=0.1.**

## Step 3. Timeframe corroboration: does daily agreement improve the edge?

For each trigger_type at K=6 (the headline horizon, to bound the extra multiple-testing cost), split into decision points where the prior trading day's daily trend AGREES with the trigger's direction vs. DISAGREES, comparing realized R directly (not vs. baseline -- this is an agrees-vs-disagrees test, not an edge-over-baseline test). **16 cells tested.**

| Trigger | n(agree) | E(agree, ho) | n(disagree) | E(disagree, ho) | p (agree vs disagree) | Survives BH-FDR |
|---|---|---|---|---|---|---|
| fvg_fill_bearish | 622 | -0.0239R | 1,252 | +0.0869R | 0.0294 | no |
| volume_spike_green | 387 | +0.0402R | 180 | +0.2106R | 0.0937 | no |
| ema9_cross_up | 1,071 | +0.0078R | 562 | +0.0827R | 0.1682 | no |
| macd_bull_cross | 415 | +0.0271R | 209 | +0.1416R | 0.1894 | no |
| vwap_reclaim | 492 | +0.0103R | 246 | +0.0990R | 0.2769 | no |
| swing_pivot_low_confirmed | 468 | +0.0860R | 239 | +0.1621R | 0.3415 | no |
| fvg_fill_bullish | 1,295 | +0.0520R | 624 | +0.1005R | 0.3564 | no |
| rsi_reclaim_bear | 168 | +0.0802R | 312 | -0.0146R | 0.3566 | no |
| channel_break_up | 181 | -0.0246R | 124 | -0.1307R | 0.3757 | no |
| volume_spike_red | 156 | +0.0936R | 356 | +0.1665R | 0.4930 | no |
| rsi_reclaim_bull | 338 | +0.0267R | 150 | +0.0906R | 0.5252 | no |
| vwap_loss | 247 | -0.0505R | 491 | -0.0103R | 0.6146 | no |
| macd_bear_cross | 207 | +0.0272R | 415 | -0.0165R | 0.6166 | no |
| channel_break_down | 131 | -0.1150R | 225 | -0.0722R | 0.6983 | no |
| swing_pivot_high_confirmed | 251 | +0.1349R | 474 | +0.1504R | 0.8370 | no |
| ema9_cross_down | 562 | +0.0317R | 1,070 | +0.0284R | 0.9516 | no |

**16 cells eligible, 0 survive BH-FDR.** Descriptively (none of this is significant after correction, so read as color, not a finding): in most cells the point estimate for DISAGREEING with the daily trend is *higher*, not lower, than agreeing -- the opposite of the corroboration hypothesis' predicted direction. Since nothing here clears the multiple-testing bar, this should not be read as "counter-trend is better" -- only as "no evidence that agreement helps, and what little signal exists doesn't point the hypothesized way."

## Step 4. Validation (the six checks)

No `RESULT_VALIDATION_TEMPLATE.md` exists on this branch (checked across all branches) -- using the six checks named in the brief directly.

1. **Disjointness (target doesn't contain the feature).** Every trigger here is a single-bar instantaneous event (a cross, a reclaim, a confirmed pivot, a filled gap) -- not a multi-bar "early window" measured against a target that structurally contains it (the exact failure mode `research/dome-leg-verify` found in the dome-leg study). The R-bracket forward window always starts at decision_idx+1, strictly after the trigger's own defining bar(s). **PASS by construction.**
2. **Causal availability (no look-ahead).** Applied the dome-leg-verify lesson directly: the swing-pivot trigger's decision_idx is `pivot_idx + width`, not `pivot_idx` (Step 1/comments). The channel-break trigger's decision_idx is the break bar itself (the forward scan that finds it never looks behind the fit bar). The FVG-fill trigger's decision_idx is always >= the bar where the zone was confirmed (C3). **PASS.**
3. **Trivial baseline (beat last-bar momentum).** A purely mechanical "last bar was green -> long, last bar was red -> short" baseline (no tool involved) was computed across all 66,321 valid bars: expectancy +0.0351R (K=3), +0.0440R (K=6), +0.0477R (K=12) -- in the same range as the random-direction baseline and in the same range as nearly every trigger cell above. **No surviving cell exists to test against this baseline specifically** (Step 2 found zero); the comparison is reported for completeness and shows the same pattern as elsewhere in this research arc: most apparent edges are within noise of trivial momentum.
4. **Suspicious replication.** No cell replicated "too cleanly" in a way that would itself be suspicious (the opposite problem from dome-leg's 13-stock replication of an artifact) -- nothing here is clean enough to raise that flag; the closest near-miss (`swing_pivot_high_confirmed`) is consistent in *sign* across K=3/6/12 (a mildly encouraging, not suspicious, property) but inconsistent in significance and does not survive correction.
5. **OOS train/held-out split.** Chronological, 70/30 per the standard convention this whole research arc uses; confirmed clean in the run log (in-sample ends and held-out begins at the documented split timestamp, no overlap).
6. **Multiple-testing correction.** Benjamini-Hochberg FDR at q=0.1, applied separately to the Step 2 pool (48 cells) and the Step 3 pool (16 cells). **Total multiple-testing denominator: 64 cells. Survivors: 0 (Step 2) + 0 (Step 3) = 0.**

## Verdict

**64 cells tested (48 trigger x K, 16 daily-agreement). 0 survive.** That is the number to lead with, and the
plain answer to the user's hypothesis is: no, on this one stock, examined this deeply, no conditional tool
pocket -- with or without daily agreement -- shows positive expectancy over baseline that survives multiple
testing. This is the fifth measurement in this research arc (after setup-formation v1, v2, pattern-fulfillment,
and dome-leg's headline claim) to come back null once judged the same honest way.

- **The hypothesis behind this run -- that kitchen-sink averaging was washing out a real conditional pocket --
  is not supported by this stock's data.** Isolating each of 8 tools into its own specific trigger state,
  measuring forward expectancy only in those exact moments, and comparing to a matched baseline (not zero) is
  a meaningfully different and more targeted test than setup-formation v2's confluence-count averaging. It
  still found nothing that survives. The "averaging washes out signal" theory cannot be ruled out everywhere
  it might apply, but it does not rescue the picture on AAPL 5m with these 8 tools.

- **The closest near-miss, `swing_pivot_high_confirmed`, is informative precisely because it is NOT being
  declared a finding.** It shows positive edge over baseline at all three K horizons (+0.083R, +0.091R,
  +0.092R), the same sign in-sample and held-out, uncorrected p-values of 0.008-0.013 -- numbers that would
  look like a discovery in a report that didn't correct for the 48 hypotheses actually tested. After BH-FDR
  (which requires p <= 0.0021 for the smallest p-value in a 48-cell pool at q=0.10), it does not survive. The
  direction is intuitive (a confirmed swing high tends to be followed by at least some pullback, consistent
  with the textbook expectation) and it is the one cell in this whole report that would reward a dedicated
  adversarial follow-up (per the dome-leg-verify precedent) if this line of research continues -- but per the
  brief's own instruction, it is flagged as a CANDIDATE requiring full adversarial verification, not trusted.
  Do not act on it as-is.

- **The `channel_break_*` cells show a consistent, intuitive-but-unproven "fade the breakout" pattern**
  (-0.09R to -0.13R edge, both directions, all three K) that also doesn't survive correction (p=0.014-0.043)
  -- worth knowing exists, not worth trusting.

- **Step 3's timeframe-corroboration hypothesis is not supported either, and what weak signal exists points
  the wrong way.** Zero of 16 daily-agreement cells survive correction, and in most cells the raw point
  estimate for *disagreeing* with the daily trend is higher than agreeing. Since none of this clears the
  multiple-testing bar, the honest conclusion is "no evidence daily agreement helps" -- not "counter-trend
  is better." Both directions are equally unproven; only the lack of support for the hypothesized direction
  is solid.

- **Step 0's data-integrity audit found something more durable than any of the trigger results: a genuine,
  independently-verified bug in `vwap_cross_up`** (a pandas dtype-upcast-meets-Python-bitwise-NOT footgun,
  confirmed via the mathematical identity that a binary crossing series must have balanced up/down transition
  counts -- the stored column violated it 10-to-1). This is shared production code, used by two prior phases
  of this research arc (setup-formation v2's confluence tool, and pattern-fulfillment's single
  largest-population trigger). It was not a cause of any null result in this report (this study computed its
  own VWAP cross safely from the start), but it is a concrete, retroactive answer to part of the user's "we
  suspect execution issues" framing: at least one of them was real, it was findable by a simple balance check,
  and it had gone undetected through two full research phases. The other 7 tool families' definitions were
  independently balance-checked and found sound.

- **Was the right standard applied?** Yes, per Step 1's checklist (causal-bar precision, disjoint single-event
  triggers, no invented thresholds) and Step 4's six checks, all explicitly walked through above. The
  methodology that produced this null is the same rigor that has now been applied, cumulatively, across five
  measurements in this research arc -- this is not a weaker or less careful test than the ones that came
  before it; if anything, conditioning on specific tool states with an explicit baseline-over-edge framing is
  a *more* targeted test than the kitchen-sink confluence approach it was built to challenge, and it still
  found nothing that survives.

**Bottom line:** mostly null, as the brief itself predicted as the honest likely outcome, with one feature
worth carrying forward (the swing-pivot-high near-miss, flagged as a candidate, not a finding) and one
concrete process win (the VWAP bug, now documented and avoided). No conditional pocket on this stock, with
this measurement standard, is trustworthy enough to act on.

## Example charts

- `fr_swing_pivot_high_NEARMISS_WIN.png`: the closest near-miss trigger, a clean WIN (R=2) -- a confirmed
  swing high followed by a grind down to target. Tempting in isolation; still doesn't survive correction.
- `fr_channel_break_up_FADE_LOSS.png`: instructive precisely because it looks wrong at first glance. A long
  breakout entry at $291.36 (ATR=$0.39, stop=$290.97) gets stopped out one bar later by a routine $0.04
  undershoot (low $290.93) -- ordinary noise, nothing dramatic. The stock then gaps up to $294+ over the
  following weekend, which would have been a large winner had the position not already been closed. Both
  things are true at once: the R-bracket correctly recorded a loss, and the stock went on to rally hard --
  a concrete illustration of why a tight, mechanical ATR stop and "the trade eventually worked out" are not
  the same question, and why this report measures the former, not the latter.

## Reproducibility

- Full aggregates: `reports/research/foundation_retest_summary.json` (run `20260622T054700Z-5809600e`)
- Run log: `reports/research/foundation_retest_run_log.jsonl`
- Raw rows: `research_foundation_retest`, `research_foundation_retest_baseline` tables, `WHERE run_id = '20260622T054700Z-5809600e'`
- Example charts: `reports/research/charts/` (prefixed `fr_`)
