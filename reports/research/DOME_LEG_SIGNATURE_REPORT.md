# Dome / Leg Early-Signature Study

**MEASURE & REPORT ONLY.** Continues two open threads already in this codebase plus a user-led exploratory pass this session: (1) the dome-symmetry audit (branch `research/dome-symmetry`), which found `swing_legs()` only ever detected the bullish up-leg/'dome' and never its bearish mirror, the down-leg/'bowl'; (2) the original swing_leg commit's own open question, "do the first 2-5 bars predict the hump height & correction?"; (3) whether candle geometry at confirmed swing tops/bottoms (real, large, replicated across tickers) translates into anything usable in real time, with zero look-ahead. Not a predictor, not a trading signal.

- **Run ID:** `20260621T225140Z-93e39c70`
- **Git commit:** `25accacc430d3c43cb96a21fcf51b47aba81dbfa` (branch `research/dome-leg-signature`)
- **Timestamp (UTC):** 2026-06-21T22:52:14.357644+00:00
- **Tickers:** AAPL, NKE, INTC (5m, same 3 as the rest of this research arc)
- **Pivot width / significance filter:** width=3, amp >= 2.5x ATR14 from the prior opposite pivot
- **Early-signature window:** first 5 bars off the leg start
- **Real-time filter thresholds:** wick% > 30.0, range/ATR > 1.1, vol_ratio > 1.15
- **Walk-forward split:** 70% train / 30% held-out, chronological per ticker
- **Total wall time:** 33.9s
- **Legs detected:** 19,697 | **Real-time filter+baseline rows:** 311,103

## Background: the dome-symmetry gap (prior work, not by this session)

`src/atlas_research/ta/patterns.py::swing_legs()` only ever paired a swing LOW followed by a swing HIGH (the bullish 'dome': rise -> peak -> correction). A prior session (branch `research/dome-symmetry`, commit `dbc98ee`) confirmed empirically that all 172,707 `swing_leg` rows in `pattern_memory` are `direction='long'`, `leg_amp` and `early_gain` all non-negative, all daily -- a textbook one-sided-detector fingerprint. A follow-up commit (`0535cdb`) wrote a symmetric down-leg detector (`swing_legs_down()` / `swing_legs_all()`) but stopped short of wiring it into `pattern_memory` or running it on 5m, flagged 'awaiting go'. Neither commit is merged into `fix/model-validity` or pushed to origin. This measurement reproduces that detector's field semantics directly (see Scoping) on 5m, for both orientations, rather than depending on the unmerged branch.

## Part A. Candle geometry: leg start vs. leg peak/trough

At the moment a swing pivot is confirmed (not real-time -- see Part C for that), is there a congruent, mirror-symmetric candle signature at the START of a leg (the low for an up-leg/dome, the high for a down-leg/bowl) versus its PEAK/TROUGH (the terminal extreme)? Pooled across AAPL/NKE/INTC, 19,697 legs.


**up-leg** (start = swing LOW (dome begins) -> peak = swing HIGH (dome top)), n=9,850

| Feature | At start | At peak/trough |
|---|---|---|
| body % | 50.51 | 50.56 |
| upper wick % | 13.69 | 35.09 |
| lower wick % | 35.62 | 14.14 |
| range/ATR | 1.18 | 1.12 |
| volume ratio | 1.39 | 1.27 |
| close position in range % | 57.97 | 42.59 |
| is_green % | 44.4% | 53.2% |

**down-leg** (start = swing HIGH (bowl begins) -> trough = swing LOW (bowl bottom)), n=9,847

| Feature | At start | At peak/trough |
|---|---|---|
| body % | 50.56 | 50.34 |
| upper wick % | 35.49 | 13.85 |
| lower wick % | 13.77 | 35.62 |
| range/ATR | 1.18 | 1.13 |
| volume ratio | 1.38 | 1.28 |
| close position in range % | 41.55 | 57.51 |
| is_green % | 52.1% | 43.6% |

Up-leg starts and down-leg peaks/troughs mirror each other exactly (both are 'bottom-type' bars: dominant lower wick, close high in range), and up-leg peaks mirror down-leg starts (both 'top-type': dominant upper wick, close low in range) -- confirming the symmetry the dome-symmetry audit predicted but never measured. Counterintuitive nuance: the turning bar itself is still often green at a top (53%) and red at a bottom (44% green) -- the wick, not the bar's own color, carries the rejection signal.

## Part B. Does the early signature predict the eventual leg size? (in-sample vs. held-out)

For each leg, `early_gain`/`early_slope` = the magnitude move over the first 5 bars off the (already-confirmed) start. Correlated against `leg_amp` (the eventual total move) and `corr_depth` (the depth of the move that ENDS the leg -- a genuinely separate future event, no time overlap with the early window at all). The 'ALL' column includes legs shorter than the early window itself (where early_gain *is* almost the whole leg, by construction); the 'non-tautological' column restricts to legs longer than the early window, so the early bars are a genuine partial sample, not the whole answer.

| Leg | Portion | n | r(early_gain, leg_amp) ALL | r(...) non-tautological | r(early_slope, corr_depth) |
|---|---|---|---|---|---|
| up | in_sample | 7,043 | r=0.693 (p=<0.0001) | r=0.611, n=4,873 (p=<0.0001) | r=0.190, n=5,190 (p=<0.0001) |
| up | held_out | 2,807 | r=0.801 (p=<0.0001) | r=0.736, n=1,989 (p=<0.0001) | r=0.336, n=2,083 (p=<0.0001) |
| down | in_sample | 7,042 | r=0.807 (p=<0.0001) | r=0.716, n=4,845 (p=<0.0001) | r=0.247, n=5,316 (p=<0.0001) |
| down | held_out | 2,805 | r=0.790 (p=<0.0001) | r=0.749, n=1,984 (p=<0.0001) | r=0.233, n=2,038 (p=<0.0001) |

**This is the strongest, most stable finding in this entire research arc.** The non-tautological correlation is large (r=0.61-0.75) and does **not decay** out-of-sample -- if anything it is slightly larger held-out than in-sample for 3 of 4 cells. The genuinely forward-looking early_slope-vs-corr_depth correlation (r=0.19-0.34) is smaller but also stable/replicating, not an overfit artifact.

## Part C. The real-time angle: does the shape signature work with zero look-ahead?

Every bar (not just confirmed pivots) screened in real time for the same shape combination found at confirmed tops/bottoms (dominant wick + elevated range/ATR + elevated volume), compared to a random-bar baseline at the same forward horizons, pooled across tickers.

| Filter | K | Portion | Pattern mean fwd R | n | Baseline mean fwd R | n | p vs baseline |
|---|---|---|---|---|---|---|---|
| bottom_like | 3 | in_sample | -0.1078 | 5,991 | +0.0098 | 42,121 | 0.0677 |
| bottom_like | 3 | held_out | +0.0874 | 3,084 | +0.0063 | 17,878 | 0.3463 |
| bottom_like | 6 | in_sample | -0.2095 | 5,991 | +0.0168 | 42,121 | 0.0055 |
| bottom_like | 6 | held_out | +0.1148 | 3,084 | +0.0614 | 17,877 | 0.6163 |
| bottom_like | 12 | in_sample | -0.1988 | 5,991 | +0.0201 | 42,121 | 0.0378 |
| bottom_like | 12 | held_out | +0.2090 | 3,084 | +0.2003 | 17,872 | 0.9527 |
| bottom_like | 24 | in_sample | -0.1747 | 5,991 | -0.0041 | 42,121 | 0.2054 |
| bottom_like | 24 | held_out | +0.3399 | 3,084 | +0.3335 | 17,864 | 0.9730 |
| top_like | 3 | in_sample | +0.0040 | 5,819 | +0.0098 | 42,121 | 0.9329 |
| top_like | 3 | held_out | +0.0777 | 2,888 | +0.0063 | 17,878 | 0.4319 |
| top_like | 6 | in_sample | -0.0143 | 5,819 | +0.0168 | 42,121 | 0.7144 |
| top_like | 6 | held_out | +0.2320 | 2,888 | +0.0614 | 17,877 | 0.1384 |
| top_like | 12 | in_sample | -0.1145 | 5,819 | +0.0201 | 42,121 | 0.2289 |
| top_like | 12 | held_out | +0.2623 | 2,888 | +0.2003 | 17,872 | 0.6768 |
| top_like | 24 | in_sample | -0.0317 | 5,819 | -0.0041 | 42,121 | 0.8392 |
| top_like | 24 | held_out | +0.3350 | 2,888 | +0.3335 | 17,864 | 0.9933 |

**Pooled across tickers, none of this replicates.** The one nominally low p-value (`bottom_like`, K=6, in-sample, p=0.0055) is in the WRONG direction (negative mean forward return for a filter meant to flag bottoms) and does not replicate held-out (p=0.62, flips positive) -- the textbook in-sample-only artifact this research arc keeps surfacing. Per-ticker (not shown in the pooled table; see `dome_leg_signature_summary.json` raw rows via `research_dome_leg_realtime`), the exploratory pass found AAPL trending positive regardless of filter direction, NKE trending negative regardless of filter direction, and INTC mixed -- i.e. ticker-level drift dominates a pure shape filter with no confirmation lag, exactly why Part B's confirmed-pivot framing works where Part C's real-time framing does not.

## Scoping notes

- **Significant pivots**, not raw fractal pivots: `structure.swing_pivots(width=3)` finds every micro zigzag; legs are only built from pivot-to-pivot moves >= 2.5x ATR14, to study real trend changes rather than noise (consistent across amp_mult=2.0/2.5/3.0 and width=3/5 in the exploratory pass).
- **Leg field semantics reproduce, rather than import, `research/dome-symmetry`'s `_legs()`/`swing_legs_down()`/`swing_legs_all()`** (commit `0535cdb`): that branch is fully committed but not pushed to origin and not merged into `fix/model-validity` -- reproduced in `dome_leg_signature_common.py` rather than depending on an unmerged branch, the same reasoning used for `feat/channels-and-5m` in the pattern-fulfillment phase.
- **Look-ahead guard, explicit**: a leg's `start_idx`/`peak_idx`/`early_*` fields are established from the two pivots that define the leg itself, both already confirmed by the time the leg exists. `corr_depth`/`corr_bars` derive from a THIRD, later pivot -- a forward outcome used only as the dependent variable in Part B, never as an input feature. This is the identical rule the dome-symmetry audit specified and never violated.
- **Part C's filter thresholds are the same ones found, descriptively, in Part A/the prior exploration** (wick% > 30, range/ATR > 1.1, vol_ratio > 1.15) -- not re-tuned or optimized against Part C's own outcome data, to avoid circularity.
- **The real-time filter test is pooled across tickers** for the headline table (consistent with the rest of this research arc's reporting grain); per-ticker sign inconsistency is discussed qualitatively above since it's the main explanation for the pooled null.

## Verdict

**Plain answer: the dome/bowl symmetry is real, the early-signature-predicts-eventual-size finding is the strongest and most stable result in this entire research arc, and the real-time angle is a clean, honest null — for the same reason every other forward-prediction test in this arc has been null.**

- **The dome-symmetry audit's prediction is confirmed.** Once you build the down-leg (bowl) the same way as the up-leg (dome), the candle geometry is an exact mirror: up-leg starts and down-leg peaks are both "bottom-type" bars (dominant lower wick ~35-36%, close high in the bar ~58%, more often red); up-leg peaks and down-leg starts are both "top-type" (dominant upper wick ~35%, close low ~42%, more often green). The bowl is exactly as detectable as the dome — the original detector's blind spot was a real gap, not a non-issue, and this measurement is independent evidence the proposed mirror fix in `research/dome-symmetry` is worth merging.

- **The early-signature question, finally answered: yes, decisively.** The first 5 bars off a confirmed swing point predict the eventual leg size with r=0.61–0.75 (non-tautological, i.e. excluding legs short enough that the early window *is* the whole leg) — and this does not decay out-of-sample; it's slightly *larger* held-out for 3 of 4 cells. The more interesting variant — does early speed predict the depth of the *correction that ends* the leg, a wholly separate future event — is smaller but still real and replicating (r=0.19–0.34, both legs, both portions, all p<0.0001). This is a genuinely actionable-shaped result: once a swing point is confirmed (the standard ~3-bar fractal lag), watching the next few bars' momentum is a strong, stable signal for how far the move will run and how sharp the eventual reversal will be.

- **The real-time angle does not work, and the reason is informative, not just "another null."** Screening every bar in real time (zero look-ahead) for the exact shape combination that's descriptively true at confirmed turns produces no replicating directional edge — pooled results swing from strongly negative (in-sample) to flat-to-positive (held-out) for both filter directions, and per-ticker the sign is simply inconsistent (AAPL net-positive on both filters, NKE net-negative on both, INTC mixed), meaning ticker-level drift dominates a context-free shape filter. The shape genuinely marks "something is turning" (Part A, B) but cannot, on its own and without the pivot-confirmation lag, tell you *that this specific bar* is the turn rather than just a volatile bar mid-trend. This is the fourth and cleanest illustration in this research arc of the same underlying lesson: retrospective/descriptive correlation and real-time predictive power are different questions, and this codebase's patterns keep answering the first one well and the second one poorly.

- **Practical implication:** the actionable piece here isn't "detect the shape in real time and trade it" (null, per Part C) — it's "once a swing point is confirmed by the existing, standard lag, the next few bars are unusually informative about how big the move will get" (real, per Part B). That is a meaningfully different and more modest claim than a real-time entry signal, but it is the one piece of this whole research arc with a large, replicating, non-overfit effect size.

## Reproducibility

- Full aggregates: `reports/research/dome_leg_signature_summary.json` (run `20260621T225140Z-93e39c70`)
- Run log: `reports/research/dome_leg_signature_run_log.jsonl`
- Raw rows: `research_dome_leg_signature`, `research_dome_leg_realtime` tables, `WHERE run_id = '20260621T225140Z-93e39c70'`
- Example charts: `reports/research/charts/` (prefixed `dl_`)
