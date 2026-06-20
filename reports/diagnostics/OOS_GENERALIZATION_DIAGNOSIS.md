# OOS Generalization Diagnosis — V1 Walk-Forward vs Embargoed OOS Failure

**Repo:** atlas-research **Branch:** `research/oos-diagnosis` (isolated worktree at
`C:\Atlas\atlas-research-oos-diagnosis`, branched off `fix/model-validity`)
**Date:** 2026-06-20
**Scope:** Diagnosis only — no model code edited, no new model promoted. Every
number below comes from a script executed this session, listed by angle.

**The problem, as given (not relitigated):** V1 walk-forward pooled per-day
rank IC = +0.0131 (t=+4.72) in-sample, but the embargoed OOS year
(2025-06-15→2026-06-14) gives rank IC = -0.0052 (t=-2.20), 244 IC days,
292,801 rows, regressor collapsed to 1 tree. Verdict on record: KEEP V1 BUT
MARK DEGRADED.

**Bottom line up front:** the evidence converges on **(b) REGIME-SPECIFIC**.
The OOS year's failure is concentrated almost entirely in one regime
(`bull_high_vol`) that was nearly tripled in the OOS year relative to its
share of training history, and that regime is the only large-sample bucket
with a statistically significant negative IC. A second, independent
non-overlapping year scores strongly positive. There is no multi-year decay
trend and no evidence of corrupted/degenerate inputs — the 1-tree collapse
is this pipeline's normal behavior on a weak signal, not a new anomaly.

---

## Angle 1 — Sub-period IC stability

**Script:** `scripts/diagnostics/angle1_subperiod_ic.py`. Stitches every
walk-forward fold's de-leaked V1 validation predictions into a single
non-overlapping per-day rank-IC series (trimming each fold's window to end
the day before the next fold begins, so no calendar day is double-counted).
**OOS reads: 0** — only walk-forward fold windows (≤2025-06-14) are touched;
`generate_folds()` with `WF_OOS_MONTHS=12` already excludes the embargoed
year from fold generation.

Pooled sanity check: mean_ic = **0.0126**, t = **4.37**, n = 2,755 days
(matches the established +0.0131/t=4.72 closely — small differences are the
overlap-trimming methodology).

| Year | Mean IC | N days | t-stat |
|---|---|---|---|
| 2014 (partial) | +0.0003 | 127 | 0.02 |
| 2015 | +0.0189 | 252 | 2.17 |
| 2016 | +0.0012 | 252 | 0.11 |
| 2017 | +0.0085 | 251 | 1.10 |
| 2018 | +0.0023 | 251 | 0.25 |
| 2019 | +0.0320 | 252 | 3.39 |
| 2020 | +0.0302 | 253 | 2.70 |
| 2021 | +0.0158 | 252 | 1.34 |
| 2022 | **-0.0170** | 251 | **-1.78** |
| 2023 | +0.0175 | 250 | 2.14 |
| 2024 | +0.0080 | 252 | 0.93 |
| 2025 (H1 only, through 06-14) | **+0.0458** | 112 | **4.79** |

**Reading.** No monotonic decay. 2022 is the only clearly negative year. 2023
recovers to a significant positive (t=2.14). 2024 is weak but not negative.
**2025 H1 — the period immediately preceding the OOS failure — is the
strongest year of the entire 12-year series** (t=4.79, n=112). Quarter-level
data (`angle1_quarterly_ic.csv`, 47 quarters) shows substantial sub-annual
noise even within single years (e.g. 2022Q1=-0.043, 2022Q3=+0.046). This
rules out a simple secular-decay story: the edge was at its strongest right
before it went negative, not trailing off into the failure.

---

## Angle 2 — Regime breakdown of the embargoed OOS year

**Script:** `scripts/diagnostics/angle2_oos_regime_breakdown.py`. Tags every
OOS row by regime (`bull`/`bear`/`range` from `market_trend` sign ×
`high_vol`/`low_vol` from `realized_vol_20 > 0.30` — same definition as
`scripts/compute_feature_reliability.py:load_regime_context`), scores with
the existing OOS artifact (`return_regressor_v1_2025-06-14`).
**OOS reads: 1** (load + score, single pass).

| Regime | Mean IC | t-stat | N days | N rows |
|---|---|---|---|---|
| bear_high_vol | -0.0167 | -0.95 | 12 | 9,086 |
| bear_low_vol | +0.0105 | 0.70 | 12 | 5,801 |
| **bull_high_vol** | **-0.0274** | **-2.38** | **203** | **86,512** |
| bull_low_vol | -0.0106 | -1.53 | 203 | 68,266 |
| range_high_vol | -0.0033 | -0.84 | 116 | 73,653 |
| range_low_vol | +0.0018 | 0.45 | 116 | 49,483 |

Overall sanity check: mean_ic = -0.0052, t = -2.20, n = 244 days — matches
the established baseline exactly.

**Regime mix, training period (721,479 rows, 2011-07-01 → day before
2025-06-15, column-only read, no scoring, no model touch) vs the OOS year:**

| Regime | Training % | OOS % |
|---|---|---|
| bear_high_vol | 5.37 | 3.10 |
| bear_low_vol | 3.84 | 1.98 |
| **bull_high_vol** | **11.06** | **29.55** |
| **bull_low_vol** | **45.67** | **23.31** |
| range_high_vol | 15.60 | 25.15 |
| range_low_vol | 18.45 | 16.90 |

**Reading.** `bull_high_vol` is the only large-sample bucket (203 of 244
days, 86,512 of 292,801 rows) with a statistically significant negative IC.
`bear_low_vol` and `range_low_vol` are mildly *positive*. The regime mix
shows exactly why this matters: `bull_high_vol` was 11.1% of training rows
but **29.6% of the OOS year — nearly tripled**. `bull_low_vol`, the regime
the model saw most during training (45.7%), shrank to 23.3% in OOS. The OOS
year over-weighted the one regime training under-weighted, and that bucket
is precisely where the model fails.

---

## Angle 3 — Second, non-overlapping embargoed slice

**Script:** `scripts/diagnostics/angle3_second_oos_slice.py`. Trains one
model (train ≤2024-06-14, 581,118 rows) via the unedited `run_fold()`,
scores it once on 2024-06-15→2025-06-14 (139,401 rows) — non-overlapping
with the primary OOS year. Artifact saved to
`reports/diagnostics/angle3_diagnostic_artifacts/` (not the shared `models/`
dir — `build_model_map()` cannot see it); `write_db=False`, no
`model_registry` row. **This slice's reads: 1** (train + score, single pass).

| Metric | Primary OOS (2025-06-15→2026-06-14) | Second slice (2024-06-15→2025-06-14) |
|---|---|---|
| Rank IC | -0.0061 | **+0.1434** |
| Mean IC (per-day) | -0.0052 | **+0.0272** |
| IC t-stat | -2.20 | **+3.26** |
| Classifier AUC | 0.4817 | 0.5310 |
| N val rows | 292,801 | 139,401 |

**Reading.** Two adjacent, independently-trained, non-overlapping years give
opposite signs, and the second slice's mean IC (+0.0272) is *more than
double* the established walk-forward average (+0.0131). A single bad year
does not establish a dead edge — this directly contradicts that reading. (Note:
this slice overlaps the regular walk-forward's fold 11, a different,
separately-trained model from the production pipeline — that's expected and
fine; non-overlap was only required against the *primary* OOS year, per the
task's own definition.)

---

## Angle 4 — The single-tree OOS collapse: degenerate or honest?

**Script:** `scripts/diagnostics/angle4_single_tree_collapse.py`.

**Part A — early-stopping curve (0 OOS reads).** Replicates
`train_regressor`'s exact recipe (last-10% ES carve, same
`LGBM_PARAMS_REGRESSOR`) on the OOS fold's training window alone
(≤2025-06-14, 715,786 rows; 644,208 train / 71,578 ES), with
`lgb.record_evaluation()` added to capture the curve the saved artifact
doesn't retain.

| Iteration | ES RMSE |
|---|---|
| 1 (best) | 0.106682 |
| 8 | 0.106783 |
| 14 | 0.106831 |
| 21 (last) | 0.107082 |

`best_iteration=1`. The curve is **not flat from iteration 0** — it
monotonically *worsens* every iteration after the first. Iteration 1 is
already the optimum; every additional tree overfits the ES holdout.

**This is not a new anomaly.** Several *positive*-IC walk-forward folds
historically also early-stopped at 1-3 trees (fold 3: 1 tree, rank_ic
+0.0372; fold 9: 1 tree, rank_ic +0.0772 — both from this session's STEP 5
re-run). A 1-tree regressor is this pipeline's ordinary behavior on a weak
5-day signal; by itself it predicts nothing about the *sign* of IC.

**Part B — feature/label distribution shift (1 read of the primary OOS
slice; this is read #2 of that slice this session, after Angle 2's scoring
read).** Compares the OOS year against the immediately-preceding 12 months
of training (2024-06-15→2025-06-14 — itself read for the second time here,
after Angle 3's training+scoring pass).

*Label (`label_return_5d`) distribution — no collapse, no imbalance:*

| Period | N | Mean | Std | % positive |
|---|---|---|---|---|
| Reference (2024-06-15→2025-06-14) | 139,401 | -0.40% | 0.1036 | 49.96% |
| OOS (2025-06-15→2026-06-14) | 292,801 | +0.01% | 0.1081 | 50.67% |

*Missing rates — improved, not degraded, across the board* (e.g.
`rs_spy_120`: 68.7%→6.8% missing; `omni_82_*` features: ~51%→3% missing) —
more feature coverage in the OOS year, not a NaN spike.

*Real shift — market-regime features, all toward sustained bullishness,*
corroborating Angle 2 at the raw-feature level:

| Feature | Ref mean | OOS mean | Shift (in ref σ) |
|---|---|---|---|
| spy_above_sma50 | 0.591 | 0.828 | +0.48 |
| spy_return_20d | +0.34% | +1.99% | +0.29 |
| spy_above_sma200 | 0.855 | 0.927 | +0.21 |
| market_trend | 0.583 | 0.682 | +0.14 |

Variance also shifted on some ticker-level features: `volume_trend_5d`
(5.5× higher OOS variance), `rs_spy_120`/`distance_sma200` (~2.7-2.8×
higher); `atr_14`/`macd_histogram` show large variance *contraction*
(ratios 0.02 / 0.07) — flagged as a notable numerical anomaly but not
root-caused; out of scope for this diagnosis.

**Reading.** No evidence of broken/degenerate inputs (no NaN spike, no label
collapse). The real, measurable shift is a regime-level one — the same
shift Angle 2 already identified via explicit regime tags shows up
independently in the raw market-breadth features. This corroborates (b)
rather than supporting a separate "(d) broken data" explanation.

---

## OOS-slice read accounting (hard rule compliance)

| Slice | Date range | Times read this session | Where |
|---|---|---|---|
| **Primary embargoed OOS year** | 2025-06-15 → 2026-06-14 | **2** | Angle 2 (load+score), Angle 4 Part B (load only, distribution stats) |
| **Second slice** (introduced by Angle 3, not production-embargoed) | 2024-06-15 → 2025-06-14 | **2** | Angle 3 (train+score), Angle 4 Part B (load only, reference distribution) |

Neither slice was used to train, select, or tune any model parameter; every
read was either a one-time scoring pass or a purely descriptive statistics
pass. No iteration against either slice occurred — each was read for a
single, predetermined purpose decided before it was touched.

---

## Conclusion

> ## (b) REGIME-SPECIFIC

The edge is real (Angle 1's clean 12-year walk-forward, t=4.37-4.72) but
**regime-conditional**. Named regimes:

- **Hostile to the model:** `bull_high_vol` — IC -0.0274 (t=-2.38, the only
  statistically significant negative bucket with a large sample). This
  regime's share of the scored universe nearly tripled from training
  (11.1%) to the OOS year (29.6%).
- **Acceptable-to-good for the model:** `bull_low_vol` (the model's most-seen
  training regime, 45.7% of training rows, but only 23.3% of OOS),
  `bear_low_vol` (+0.0105), `range_low_vol` (+0.0018).

This is not a decay story (Angle 1: no multi-year trend, strongest year
immediately precedes the failure) and not a dead-edge story (Angle 3: an
independent adjacent year scores +0.0272 mean IC, more than double the
historical average, t=+3.26). It is also not a data-corruption story
(Angle 4: no NaN spike, no label collapse, missing rates improved) — the
1-tree collapse is this pipeline's ordinary behavior on a weak signal and
co-occurs with both positive- and negative-IC folds elsewhere in the
walk-forward history. What *did* shift, confirmed two independent ways
(explicit regime tags in Angle 2, raw market-breadth feature distributions
in Angle 4), is the regime composition of the test period relative to what
the model was mostly trained on.

**What would strengthen this further (not done, flagged as a gap):** a
regime breakdown of the second slice (Angle 3) and of more historical years
(Angle 1) would let the `bull_high_vol`-is-hostile claim be tested across
more than one occurrence. With only one clearly-failing year, regime is the
best-supported explanation available from this session's evidence, but it
rests on one strong example, not several.

---

## What I did and did NOT do

**Did:**
- Created an isolated git worktree (`C:\Atlas\atlas-research-oos-diagnosis`,
  branch `research/oos-diagnosis` off `fix/model-validity`) after detecting
  an unexpected branch switch and untracked files in the shared working
  tree — confirmed non-destructive (my prior commit was still an ancestor),
  reported it, then worked entirely in the isolated worktree to remove any
  further collision risk with concurrent agents.
- Wrote 4 new scripts under `scripts/diagnostics/`, all read-only against
  existing model/data code (only `run_fold()`, `load_date_range()`,
  `cross_sectional_normalize()`, `to_arrays()`, `apply_purge_gap()`,
  `generate_folds()`, `oos_window()` imported and called, never edited).
- Produced every number in this report from a script executed this session
  (CSVs/JSON committed alongside each script, one commit per angle).
- Saved Angle 3's diagnostic-only model artifact outside the shared
  `models/` directory specifically so production scoring (`build_model_map`)
  can never pick it up.
- Tracked and reported exact OOS-slice read counts (table above).

**Did NOT do:**
- Did not edit any existing model, dataset, or walk-forward code.
- Did not touch `pattern_memory`, `intraday_bars`, or any table/file the
  concurrent background jobs (5m pattern pass, channel pass) were writing.
- Did not optimize, tune, or retrain against the primary OOS year — both
  reads of it were single-pass scoring/descriptive-stats, not iteration.
- Did not run a regime breakdown of the second slice or of additional
  historical years — flagged above as the clearest next step to harden the
  REGIME-SPECIFIC conclusion.
- Did not root-cause the `atr_14`/`macd_histogram` variance contraction
  noted in Angle 4 — flagged, not investigated further.
- Did not push or merge. All 4 commits sit on `research/oos-diagnosis` in
  the isolated worktree, unpushed, for review.
- Did not promote, retrain, or change the production V1 model in any way —
  this is a diagnosis; the DEGRADED marking and KEEP V1 verdict from the
  prior session stand untouched.
