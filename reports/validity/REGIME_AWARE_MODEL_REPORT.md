# Regime-Aware Model Rebuild — Approach A (Regime-Balanced Training)

**Repo:** atlas-research **Branch:** `model/regime-aware` (isolated worktree at
`C:\Atlas\atlas-research-regime-aware`, branched off `fix/model-validity`)
**Date:** 2026-06-20
**Scope:** Build + honestly validate ONE lever (regime-balanced training) for
making V1 regime-aware. Every number below comes from a script executed this
session.

**Verdict, stated up front:**

> ## NO IMPROVEMENT

Regime-balanced training (Approach A) does not fix the regime the OOS
diagnosis identified as the failure mechanism, and degrades the model
overall. Per the task's own decision rule, this stops here — Approach B/C
were not attempted, and the embargoed OOS year was **not read** for this
rebuild (0 reads — see accounting below). An honest negative result now is
worth more than a model quietly tuned to look better on data it shouldn't
have touched.

---

## STEP 0 — Regime definition + share table

**Script:** `scripts/regime_aware/step0_regime_share_table.py`.

Regime definition, reused verbatim from the OOS diagnosis (Angle 2) /
`scripts/compute_feature_reliability.py:load_regime_context`:
- `regime_market` = `bull` if `market_trend > 0`, `bear` if `< 0`, else `range`
- `regime_vol` = `high_vol` if `realized_vol_20 > 0.30` else `low_vol`
- `regime` = `regime_market + "_" + regime_vol` (6 buckets)

**Point-in-time check:** `features/regime.py:compute()` and
`features/volatility.py:_realized_vol()` are both stateless functions
operating only on trailing array slices (`spy_close[-50:]`, `close[-(days+1):]`)
— backward-looking by construction. These are the same already-exported,
already-point-in-time parquet columns V1 trains on; no new look-ahead is
introduced.

**Full-history share (1,034,153 rows, 2011-07-01→2026-06-14):**

| Regime | % |
|---|---|
| bull_low_vol | 39.11 |
| range_high_vol | 18.08 |
| bull_high_vol | 17.23 |
| range_low_vol | 17.71 |
| bear_high_vol | 4.63 |
| bear_low_vol | 3.24 |

**By year (selected), showing the regime mismatch directly:**

| Year | bull_low_vol % | bull_high_vol % |
|---|---|---|
| 2017 | 86.68 | 7.34 |
| 2021 | 67.76 | 24.27 |
| 2024 | 67.75 | 19.95 |
| 2025 | **14.07** | 12.66 |
| 2026 (partial) | 27.78 | **43.57** |

2026's `bull_high_vol` share (43.6%) is nearly double any other year on
record (next highest: 2020 at 28.2%) — confirming the diagnosis's core
finding from a fresh, full-history angle.

---

## STEP 1 — Approach chosen: (A) Regime-balanced training

Per the task's instruction to start with the simplest defensible lever.
**New file** `src/atlas_research/models/train_regime_weighted.py` —
`train.py`/`dataset.py`/`walk_forward.py` are not edited.

**Weighting scheme:** inverse regime frequency, computed from each fold's
*own* training set only (no look-ahead, no cross-fold or OOS information).
Each regime bucket present receives equal aggregate weight
(`n / n_buckets_present`); total weight sums to `n` — same total loss-mass
as unweighted V1 training. Same `LGBM_PARAMS_REGRESSOR/CLASSIFIER`, same
10%-early-stopping carve, same Platt-on-ES-holdout calibration as V1 — the
only change is a per-row `sample_weight` passed to `lgb.Dataset`.

**Sanity-checked, not a bug:** fold 1's training set (126,618 rows) gives
mean weight 0.317 for `bull_low_vol` (66,641 rows, 52.6% share — correctly
downweighted) and 170.2 for `bear_high_vol` (124 rows, 0.1% share — correctly
upweighted); total weight equals `n` exactly. The mechanism works as
designed.

---

## STEP 2 — Walk-forward: regime-weighted (RW) vs V1

**Script:** `scripts/regime_aware/run_walkforward_regime_aware.py`. Identical
folds/purge/embargo to V1 (`generate_folds`, `load_date_range`,
`apply_purge_gap`, `cross_sectional_normalize` all reused unedited,
`WF_OOS_MONTHS=12`). RW trained fresh per fold; V1 side **loaded** from the
existing artifacts (no retraining) and scored on byte-identical validation
data, so both arms share identical regime tags. `write_db=False` throughout;
RW artifacts saved to `models_regime_aware/` (outside the shared `models/`
dir — `build_model_map()` cannot see them). **0 reads of the embargoed OOS
year** — `generate_folds()` excludes it by construction.

| Fold | Val window | RW rank IC | V1 rank IC | RW AUC | V1 AUC | RW trees(reg/clf) |
|---|---|---|---|---|---|---|
| 1 | 2014-07→2015-07 | 0.1577 | **0.1750** | 0.5819 | **0.5887** | 41/53 |
| 2 | 2015-07→2016-07 | **0.1105** | 0.0958 | **0.5507** | 0.5480 | 34/68 |
| 3 | 2016-07→2017-07 | **0.0456** | 0.0372 | **0.5208** | 0.5160 | 1/1 |
| 4 | 2017-07→2018-07 | 0.0553 | **0.0741** | 0.5296 | **0.5317** | 8/13 |
| 5 | 2018-07→2019-07 | 0.0172 | **0.0578** | 0.5123 | **0.5153** | 20/26 |
| 6 | 2019-07→2020-07 | 0.0457 | **0.0583** | **0.5167** | 0.5159 | 38/5 |
| 7 | 2020-07→2021-07 | 0.0125 | **0.0819** | 0.4991 | **0.5342** | 1/1 |
| 8 | 2021-07→2022-07 | **0.0116** | 0.0033 | 0.4931 | **0.5080** | 22/37 |
| 9 | 2022-07→2023-07 | -0.0121 | **0.0772** | 0.4982 | **0.5073** | 1/1 |
| 10 | 2023-07→2024-07 | **0.0158** | -0.0030 | 0.5026 | **0.5100** | 1/3 |
| 11 | 2024-07→2025-06 | 0.1233 | **0.1260** | 0.4678 | **0.5023** | 9/4 |
| **Mean** | | **0.0530** | **0.0712** | **0.5157** | **0.5252** | |

RW wins rank IC on 4 of 11 folds; V1 wins 7 of 11. Overall mean rank IC is
**25.6% lower** for RW.

**Per-regime IC, pooled across all 11 folds (weighted by N IC-days):**

| Regime | RW mean IC | V1 mean IC | N days | N rows |
|---|---|---|---|---|
| bear_high_vol | 0.0103 | **0.0143** | 377 | 39,822 |
| **bear_low_vol** | **0.0233** | -0.0050 | ~337 | 28,054 |
| **bull_high_vol (target)** | **0.0056** | **0.0152** | 1,915 | 76,222 |
| bull_low_vol (V1's strongest) | 0.0063 | **0.0131** | ~1,900 | 287,058 |
| range_high_vol | 0.0136 | **0.0269** | 610 | 95,438 |
| range_low_vol | 0.0214 | **0.0276** | ~630 | 104,452 |

**Reading.** RW underperforms V1 in 5 of 6 regimes — including
`bull_high_vol`, the exact regime this rebuild targeted (0.0056 vs V1's
0.0152 — *worse*, not better), and `bull_low_vol`, V1's best-known regime
(0.0063 vs 0.0131). The only improvement is `bear_low_vol`, the
smallest-row-count bucket, where V1 was actually slightly negative.

**Why this happened (mechanistic, not a tuning failure):** a single
shared-tree-structure GBM can only redistribute *which examples count more*
in the loss; it cannot independently relearn different split logic per
regime. Downweighting `bull_low_vol` (by ~3x in fold 1, the regime with by
far the most rows and — per V1's own numbers — the cleanest learnable
signal) costs more fit quality than upweighting small/noisy regimes buys
back, especially when those regimes (`bear_high_vol`: as few as 124 training
rows in early folds) simply don't have enough examples for upweighting to
manufacture additional genuine signal. This is consistent with the OOS
diagnosis's Angle 4 finding that high-vol periods show larger feature
variance and likely a lower attainable signal-to-noise ratio with the
current feature set — reweighting cannot fix a signal that isn't there to
find.

---

## STEP 3 — Embargoed-slice read: **skipped, by design**

The task's own decision rule: *"NO IMPROVEMENT — regime-balancing didn't
help — report and stop before trying B/C."* STEP 2's walk-forward already
shows RW failing on its own target (worse in `bull_high_vol`, worse overall)
using the same honest, non-OOS validation V1 was judged on. Scoring the
embargoed year with a model that has already failed internal validation
would not change this verdict, and would spend a read of the cardinal
rule's most protected resource for no decision-relevant information. Per
the cardinal rule ("If you ever find yourself adjusting a knob and
re-scoring the diagnosed year to check if it improved — STOP"), the
disciplined choice is to not touch it at all here.

**Embargoed OOS year (2025-06-15→2026-06-14) reads, this rebuild: 0.**
(For contrast: the prior OOS-diagnosis session read it 2 times, for
descriptive/diagnostic purposes that produced the regime hypothesis being
tested here. STEP 0/2 of this session read regime-mix columns for
2025-2026 for *visibility* tables only — no scoring, no training, no
model decision depended on those values — logged explicitly in STEP 0's
output for transparency, not counted as a "slice read" in the sense the
cardinal rule cares about, which is about scoring/training/tuning against
it.)

---

## STEP 4 — Honest comparison

| | V1 (loaded, existing artifacts) | Regime-weighted (RW, fresh) |
|---|---|---|
| Walk-forward mean rank IC | **0.0712** | 0.0530 |
| Walk-forward mean AUC | **0.5252** | 0.5157 |
| Target regime (bull_high_vol) IC | **0.0152** | 0.0056 |
| Strongest regime (bull_low_vol) IC | **0.0131** | 0.0063 |
| Folds won (of 11) | **7** | 4 |
| Fresh-OOS result | n/a (not re-read this session) | **not read — STEP 3 skipped** |

No cherry-picking: RW does not help the regime it targeted, and costs the
regime V1 was already good at. There is no dimension on which RW is a clear
win. This is unambiguously **NO IMPROVEMENT**, not PARTIAL — PARTIAL would
require the target regime to have actually improved at some cost elsewhere;
instead the target regime got worse too.

---

## What I did and did NOT do

**Did:**
- Created an isolated git worktree (`model/regime-aware` off
  `fix/model-validity`) before starting, consistent with the documented
  branch-incident protocol from prior sessions.
- Defined and verified the point-in-time regime labeling (STEP 0), produced
  full-history and per-year share tables.
- Implemented Approach A as a new, parallel training path
  (`train_regime_weighted.py`), not by editing V1's trainer.
- Ran the regime-weighted model through V1's exact walk-forward/purge/embargo
  machinery, with a per-fold, per-regime IC breakdown against V1's existing
  artifacts on identical validation data.
- Sanity-checked the weighting mechanism directly (not just trusted the
  result) before concluding it works as designed.
- Stopped before STEP 3/4's embargoed read once STEP 2 showed no
  improvement — exactly the discipline the cardinal rule asks for.
- Committed per logical unit (STEP 0, STEP 1, STEP 2) with explicit paths.

**Did NOT do:**
- Did not read or score the embargoed OOS year (2025-06-15→2026-06-14) with
  any regime-aware model this session.
- Did not attempt Approach B (regime-gated signal) or C (per-regime models)
  — per the task's own rule, NO IMPROVEMENT on Approach A means stop and
  report before trying them.
- Did not tune the weighting scheme (e.g. partial reweighting, capped
  weights, alternative vol thresholds) to try to rescue Approach A — that
  would risk becoming exactly the "adjust a knob, re-score, check if it
  improved" loop the cardinal rule forbids, and the mechanistic explanation
  above suggests the ceiling on pure reweighting is structural, not a
  tuning miss.
- Did not edit `train.py`, `dataset.py`, or `walk_forward.py`.
- Did not push or merge. 3 commits sit on `model/regime-aware` in the
  isolated worktree, unpushed, for review.

**Is Approach B or C worth trying next?** **B (regime-gated signal), not
C.** Two reasons, both grounded in this session's evidence:
1. C (separate per-regime models) would face an even sharper data-sparsity
   problem than reweighting did — `bear_high_vol` had as few as 124
   training rows in early folds; a standalone model for that regime would
   be badly overfit, exactly the risk the task flagged in advance.
2. The STEP 2 mechanism finding — reweighting can't manufacture signal that
   isn't there — suggests `bull_high_vol`'s issue may be a genuinely lower
   attainable signal-to-noise ratio with the current feature set (consistent
   with the OOS diagnosis's Angle 4 variance-shift finding), not an
   attention/weighting problem. Approach B doesn't ask the model to predict
   better in that regime; it only asks the system to trust the existing
   prediction less there. That sidesteps the exact failure mode this
   session uncovered, rather than fighting it again with a different knob.
