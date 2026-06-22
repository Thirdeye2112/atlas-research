# Adversarial Verification of the Dome/Leg Early-Signature Result

**Mandate: try to BREAK it.** The prior run (`research/dome-leg-signature`, commits `e2b6d60` + `318c4ba`)
reported r(early_gain, leg_amp) = 0.61–0.75, called "non-tautological," stable out-of-sample, replicated on
13 stocks. This report does not assume that result is correct. Numbers are reported before conclusions
throughout. Read-only against all existing tables; writes only to the new `research_dome_leg_verification`
table and this report.

- **Run ID:** `20260622T014224Z-f9b954c4`
- **Git branch:** `research/dome-leg-verify` (off `fix/model-validity`)
- **Scopes tested:** `original_3` (AAPL/NKE/INTC, the tickers the original claim was built on) and `fresh_5`
  (CSCO, CMCSA, MU, AAL, GM — not used in either the original 3-stock or the prior 10-stock run)
- **Non-tautological filter applied throughout:** `leg_bars > EARLY_N(5)` (same filter the original report used)

---

## CHECK 1 — Tautology / shared-bar and shared-accounting leakage

**Method.** Independently reconstructed `early_gain` (the move from the leg's start `a` to `close[a.idx+5]`)
and `leg_amp` (the move from `a` to the leg's peak `b`, `b.idx > a.idx+5` after the filter). First confirmed,
literally, which bars each quantity touches: `leg_amp` uses only `low[a.idx]` and `high[b.idx]`; `early_gain`
uses `low[a.idx]` and `close[a.idx+5]`. **No individual bar is double-counted** between the two for legs
longer than the early window — but that is not the only way to leak. `leg_amp` is the move over the
**entire** path `a -> b`, and that path passes through `close[a.idx+5]` by construction. So even with zero
bar overlap, `leg_amp` is an additive function of `early_gain` plus whatever happens afterward
(`remaining_amp`, defined as the move from `close[a.idx+5]` to `b`, entirely disjoint in both bars AND
accounting). If `remaining_amp` is unpredictable from `early_gain`, `leg_amp = early_gain + remaining_amp`
*still* correlates with `early_gain` through pure variance arithmetic, with no real predictive content.
Recomputed r against this strictly disjoint target.

| Scope | Leg | r(early, **TOTAL** leg_amp) [replicates the original] | n | r(early, **REMAINING** amp, disjoint) | n |
|---|---|---|---|---|---|
| original_3 | up | 0.689 | 6,862 | **0.177** | 6,862 |
| original_3 | down | 0.736 | 6,829 | **0.165** | 6,829 |
| fresh_5 | up | 0.684 | 13,216 | **0.141** | 13,216 |
| fresh_5 | down | 0.705 | 13,083 | **0.195** | 13,083 |

The TOTAL-leg_amp column reproduces the original report's range almost exactly (0.61–0.75 there, 0.68–0.74
here — same ballpark, confirming this is the same underlying measurement). The disjoint/REMAINING-amp column
**collapses to 0.14–0.20** — a drop of roughly 75-80%.

**Verdict: FAIL.** The original "non-tautological" filter (excluding `leg_bars <= 5`) was necessary but not
sufficient. It removed the case where the early window literally *is* the whole leg, but did not address the
deeper issue: `leg_amp` is an additive decomposition that *contains* `early_gain` as a component of the same
monotonic path, even when no bar is shared. Most of the reported 0.61–0.75 correlation is attributable to this
accounting structure, not to early bars predicting later ones.

---

## CHECK 2 — Look-ahead in "confirmed pivot" timing

**Method.** `structure.swing_pivots(width=3)` (confirmed by re-reading the source): a bar `i` is a swing low
only if `low[i]` is the strict minimum over `[i-3, i+3]` — **this requires 3 bars *after* `i`** to be known.
So bar `a.idx` is not knowable as "the leg's start" until bar `a.idx+3`. The original measurement's early
window is `[a.idx, a.idx+5]` — bars `a.idx+1, a.idx+2, a.idx+3` occur *before* the pivot is causally
confirmable. The original docstring's claim ("leg geometry... established from the two pivots that define the
leg itself, both already-confirmed by the time the leg exists") is true of the leg's *existence* but not of
the *early-signature window*, which starts measuring before confirmation. Recomputed with the window shifted
to start at the actual confirmation bar (`a.idx+3`), keeping the disjoint (Check 1) fix applied simultaneously.

| Scope | Leg | r(early CONFIRMED, REMAINING amp, disjoint) | n |
|---|---|---|---|
| original_3 | up | 0.105 | 4,500 |
| original_3 | down | **0.030** | 4,543 |
| fresh_5 | up | 0.044 | 8,718 |
| fresh_5 | down | 0.083 | 8,645 |

Fixing both issues together drops the correlation further, to roughly 0.03–0.11 — `original_3` down-leg is
essentially zero (0.030).

**The secondary metric the original report also relied on — `early_slope` vs. `corr_depth` (the depth of the
move that *ends* the leg, a wholly separate future segment `b->c`) — was already structurally disjoint in bars
and accounting from the start.** Re-tested with the same confirmation-timing fix:

| Scope | Leg | r(early_slope NAIVE, corr_depth) | n | r(early_slope CONFIRMED, corr_depth) | n |
|---|---|---|---|---|---|
| original_3 | up | 0.203 | 3,281 | 0.241 | 3,281 |
| original_3 | down | 0.174 | 3,386 | 0.128 | 3,386 |
| fresh_5 | up | 0.203 | 6,414 | 0.157 | 6,414 |
| fresh_5 | down | 0.223 | 6,519 | 0.182 | 6,519 |

This one **does not collapse** — it stays in the 0.13–0.24 range after the same look-ahead fix, consistent
with the original report's 0.19–0.34 (smaller, since the original used the un-confirmed window, but the same
order of magnitude and clearly non-zero).

**Verdict: FAIL for the headline early_gain-vs-leg_amp metric** (further, real leakage found on top of Check
1 — down to ~0.03–0.11). **PASS for the early_slope-vs-corr_depth metric** (survives the same fix essentially
intact).

---

## CHECK 3 — Is the surviving correlation even surprising? (permutation test + trivial baseline)

**Method.** Permutation null: shuffle the pairing between `early_gain` and `remaining_amp` 2,000 times
(scrambling which early window belongs to which leg), recompute r each time, and locate the real (Check-1-fixed)
r in that null distribution. Separately, compare against a **trivial baseline**: does a single bar's own move
right after the leg start predict the outcome about as well as the fancy 5-bar window?

| Scope | Leg | Real r (disjoint, Check 1 only) | Permutation null | Perm. p-value | Trivial: r(1st bar, TOTAL leg_amp) | Trivial: r(1st bar, REMAINING amp) |
|---|---|---|---|---|---|---|
| original_3 | up | 0.177 | N(0.0001, 0.0121) | **0.0000** | 0.329 | 0.151 |
| original_3 | down | 0.165 | N(0.0002, 0.0122) | **0.0000** | 0.299 | 0.123 |
| fresh_5 | up | 0.141 | N(0.0001, 0.0089) | **0.0000** | 0.320 | 0.124 |
| fresh_5 | down | 0.195 | N(0.0002, 0.0089) | **0.0000** | 0.288 | 0.106 |

And for the surviving corr_depth metric:

| Scope | Leg | Trivial: r(1st bar move, corr_depth) | n |
|---|---|---|---|
| original_3 | up | 0.149 | 4,987 |
| original_3 | down | 0.124 | 5,049 |
| fresh_5 | up | 0.158 | 9,714 |
| fresh_5 | down | 0.132 | 9,842 |

**Verdict: PASS on significance** — every real r is ~15-20 standard deviations outside its permutation null
(p=0.0000 at 2,000 permutations); none of the surviving correlation is noise. **But PASS-with-caveat on
novelty**: the disjoint 5-bar early signature (r=0.14–0.20 before the look-ahead fix, 0.03–0.11 after it) is
*not* clearly better than a single bar's own move (r=0.11–0.15 against the same disjoint target) — in fact
once the look-ahead fix is also applied, the trivial 1-bar baseline is **larger** than the 5-bar "early
signature" in every cell. For corr_depth, the 5-bar confirmed signature (0.13–0.24) beats the 1-bar trivial
baseline (0.12–0.16) in 2 of 4 cells and is roughly tied in the other 2. **The relationship that survives is
real but is mostly ordinary short-horizon momentum/autocorrelation, not a distinctly "early-signature" effect
that a single bar wouldn't already tell you.**

---

## CHECK 4 — Recompute the report's own numbers; audit the prose

**Method.** Pulled raw rows directly from `research_dome_leg_signature` (read-only) for both committed
run_ids and recomputed every published r independently (fresh Pearson + Fisher-z p-value code, not the
original aggregation script).

| | up in-sample | up held-out | down in-sample | down held-out |
|---|---|---|---|---|
| Report's published r(early_gain, leg_amp) | 0.611 | 0.736 | 0.716 | 0.749 |
| **Recomputed from raw rows, independently** | **0.611** | **0.736** | **0.716** | **0.749** |

**Exact match.** No arithmetic or transcription error — the published numbers are correct given the report's
own definitions. The 10-stock figures (Part D) were spot-checked the same way and also matched.

**Split sanity** (chronological, no train/test contamination): confirmed for all 3 tickers —
`in_sample_max_ts <= held_out_min_ts` holds with no gap-violations (e.g. AAPL: in-sample max
`2025-06-05 10:00`, held-out min `2025-06-05 10:45` — clean).

**Prose audit against what Checks 1-3 found:**

| Claim in the original report | Status |
|---|---|
| "non-tautological" (i.e., `leg_bars > early_n` is sufficient to remove tautology) | **Overstated.** Necessary but not sufficient — Check 1 found the deeper accounting-overlap issue this filter did not address. |
| "LOOK-AHEAD GUARD... both already-confirmed by the time the leg exists" | **Misleading.** True of the leg's existence, not of the early-signature window, which starts 3 bars before the pivot is knowable (Check 2). |
| "does not decay out-of-sample; if anything it is slightly larger held-out" | **Numerically true of the metric as defined**, but the metric itself is the inflated one — stability of an artifact is not evidence the artifact is real. |
| "the strongest, most stable finding in this entire research arc" | **Not supported** once corrected; see overall verdict below. |
| "replicated on 13 stocks" (used as evidence of robustness) | **True, but not actually strong evidence here** — see note below. |

**A subtlety worth stating plainly**: the original report treated "replicates across 13 sector-diverse
stocks" as evidence the finding was real rather than an artifact. That reasoning does not hold for *this
specific kind* of artifact. An accounting identity (total = early + remaining) is a mathematical property of
any monotonic-ish price path; it has no reason to vary by sector, market cap, or ticker. **A pure artifact of
this type would be expected to replicate just as cleanly as a real phenomenon** — so the 13-stock replication,
while a correct and useful check in general, does not distinguish "real" from "artifact" in this particular
case. This session's own `fresh_5` re-test (Checks 1-3 above) demonstrates exactly that: both the inflated
number *and* the deflated, corrected number replicate equally well across tickers.

**Verdict: PASS on arithmetic (no calculation errors), FAIL on the report's interpretive claims** (tautology-
free, look-ahead-safe, and "strongest finding" claims were each overstated relative to what a fully disjoint,
causally-clean measurement supports).

---

## CHECK 5 — Independent replication on fresh tickers, corrected methodology

CSCO, CMCSA, MU, AAL, GM — chosen only for 5m data coverage, not used in the original 3 or the prior 10-stock
run. The corrected (disjoint + causally-clean) methodology was applied throughout Checks 1-3 to this `fresh_5`
scope in parallel with `original_3`, not as an afterthought:

| Metric | original_3 | fresh_5 |
|---|---|---|
| r(early, TOTAL leg_amp) -- the original, inflated metric | 0.689 / 0.736 | 0.684 / 0.705 |
| r(early CONFIRMED, REMAINING amp) -- fully corrected | 0.105 / **0.030** | 0.044 / 0.083 |
| r(early_slope CONFIRMED, corr_depth) -- the metric that survives | 0.241 / 0.128 | 0.157 / 0.182 |

**Verdict: PASS.** The corrected, much smaller effect sizes replicate on fresh tickers at the same reduced
magnitude as on the original 3 -- this is not an idiosyncrasy of AAPL/NKE/INTC's specific corrected numbers
either. Both the inflated and the deflated versions of this result are general across tickers; only the
deflated version is causally honest.

---

## Summary table

| Check | Result |
|---|---|
| 1. Tautology (accounting overlap) | **FAIL** — r collapses from ~0.7 to ~0.14–0.20 (a ~75-80% reduction) once leg-size is measured strictly after the early window |
| 2. Look-ahead (pivot confirmation timing) | **FAIL** for the headline metric (further collapse to ~0.03–0.11); **PASS** for the early_slope/corr_depth metric (survives at 0.13–0.24) |
| 3. Permutation / triviality | **PASS** on statistical significance (p=0.0000, not noise); **caveat** — barely beats, and sometimes loses to, a trivial 1-bar momentum baseline |
| 4. Recompute / prose audit | **PASS** on arithmetic; **FAIL** on the report's "non-tautological," "look-ahead-safe," and "strongest finding" claims |
| 5. Fresh-ticker replication, corrected method | **PASS** — the smaller, honest effect size replicates too |

## Overall verdict

**The headline claim does not survive. A smaller, real, but largely unremarkable signal does.**

The reported r=0.61–0.75 between the first 5 bars off a confirmed swing point and the eventual leg size was
real *data*, correctly computed under its own definition, and that definition's flaw — measuring a path
segment against a target that structurally contains it, compounded by a 3-bar look-ahead window in what
should have been a strictly causal measurement — explains the great majority of the reported effect. Once
both issues are fixed:

- **Corrected effect size, headline metric (early signature vs. how much further the leg goes):** r ≈
  **0.03–0.11** (vs. the reported 0.61–0.75). This is a reduction of roughly **85-95%**. `original_3` down-leg
  is statistically indistinguishable from zero (r=0.030). This part of the original claim is **broken**.
- **Corrected effect size, secondary metric (early momentum vs. depth of the eventual correction):** r ≈
  **0.13–0.24** (vs. the reported 0.19–0.34, itself only mildly inflated since this metric was already mostly
  disjoint). This part **survives**, is statistically robust (far outside the permutation null), and
  replicates on fresh tickers — but Check 3 shows it is only modestly better than (and in half the tested
  cells, no better than) a trivial single-bar momentum proxy. **Real, but mostly not novel.**
- **Was it novel or trivial?** Mostly trivial. Both surviving correlations are in the same range as ordinary
  short-horizon return autocorrelation/momentum persistence (1-bar baseline: r=0.11–0.16 against the same
  targets). The 5-bar "early signature" framing does not add much over knowing the first single bar's move.
- **Did the auto-mode verdict overstate anything?** Yes, materially. The original report's "non-tautological,"
  "look-ahead-safe," and "strongest, most stable finding in this entire research arc" claims do not survive
  this review. The arithmetic was correct; the methodology and the resulting interpretation were not.

This is exactly the kind of result the task brief said would count as a success if found: the original number
was an artifact, substantially (not entirely) a product of how the metric was constructed rather than of
genuine forward predictability. The corrected, honest version of this study finds a small, statistically real
but practically modest momentum-persistence effect — closer in spirit to the null results found everywhere
else in this research arc (setup-formation v1/v2, pattern-fulfillment, and dome-leg-signature's own Part C)
than to the standout finding the prior report claimed.

## Reproducibility

- Raw verification metrics: `research_dome_leg_verification` table, `WHERE run_id = '20260622T014224Z-f9b954c4'`
- Supporting JSON (Checks 1/2/4 raw numbers): `reports/research/dome_leg_verify_results.json`
- All computation independently re-implemented in this worktree (`scripts/research/dome_leg_verify*.py`,
  `run_dome_leg_verify_full.py`) rather than calling into `research/dome-leg-signature`'s own code, so a bug in
  the original implementation could not be silently reused by its own verifier. `structure.swing_pivots` (the
  one shared primitive, a simple, previously-audited fractal-pivot finder) was reused as-is; everything
  downstream of it (significance filtering, leg pairing, early-window definition, all four correlation
  variants, the permutation test, and the trivial baseline) was written fresh for this review.
