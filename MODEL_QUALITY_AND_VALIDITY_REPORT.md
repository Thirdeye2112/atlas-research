# Model Quality & Validity Report

**Repo:** atlas-research **Branch:** `fix/model-validity`
**Date:** 2026-06-17
**Scope:** Phase 0 (baseline + logging), Phase 1 (validity fixes), Phase 2 (V1-vs-V3 experiment + single OOS).

Every number below comes from a run executed in this session. Statements not
backed by a computed metric are explicitly labelled **(conjecture)**.

Established findings I was told not to relitigate are upheld by this session's
numbers: the model is **not** signal-free — the clean 11-fold walk-forward gives
a pooled per-day rank IC t-stat of **+4.72** (V1). Folds that train only 1–3
trees are honest early-stopping on a weak 5-day signal, confirmed again here.

---

## 1. Bugs found in Phases 0–1 (with before/after evidence)

### 0b — Console logging silently drops records on Windows (cp1252)
**Bug.** `utils/logging.py` sent structlog through a `StreamHandler(sys.stdout)`.
On Windows stdout defaults to cp1252; any record containing a non-Latin-1
character raises `UnicodeEncodeError` inside colorama. Python's `logging` module
**swallows** that handler error, so the offending record — including
`wf.fold_complete` metric lines — is silently dropped from the console.

- **Before (reproduced):** under `PYTHONIOENCODING=cp1252`, emitting a record
  containing `→` (U+2192) raised
  `UnicodeEncodeError: 'charmap' codec can't encode character '→'` from
  `cp1252.py` via `colorama/ansitowin32.py`. The plain ASCII `->` arrow does
  *not* crash — so the original "->" diagnosis was imprecise; the real trigger
  is any non-cp1252 character.
- **Fix.** `_utf8_stream()` reconfigures the handler stream to UTF-8 with
  `errors="backslashreplace"` (falls back to wrapping `.buffer`).
- **After:** same cp1252 emit now prints `…note='arrow → survives'…` and
  `post-fix stdout encoding: utf-8`. The clean DB walk-forward run logged **0**
  `UnicodeEncodeError` / `Logging error` lines across all folds.
- **DB independence:** fold metrics persist regardless of the console handler —
  `run_fold` writes `model_registry` *before* the `wf.fold_complete` log call,
  so a dropped console line never loses the DB row.

### 1a — Purge gap counted calendar days, not trading days
**Bug.** `dataset.apply_purge_gap` cut training at `val_start - timedelta(days=purge_days)`.
The 5-day label is in **trading** days, so over weekends/holidays ~1–2 trading
days still leaked into the boundary.

- **Before:** baseline fold used `purge_cutoff=2023-06-28, rows_purged=573`
  (calendar). The repo's own unit test `test_removes_trailing_rows` **failed**
  (a year-gap train set produced `rows_purged=0`).
- **Fix.** Re-implemented to drop rows on the last `WF_PURGE_DAYS` **distinct
  trading dates** of the training set.
- **After:** `trading_dates_purged=5` (e.g. smoke run `purge_cutoff=2017-12-22,
  rows_purged=880, trading_dates_purged=5`). Added 3 unit tests
  (`test_purges_exactly_n_trading_dates`, `test_counts_trading_days_not_calendar`,
  plus the now-passing original). `pytest tests/test_models.py` = 42 passed.

### 1b — 5-day labels withheld for ~60 trading days (longest-horizon gate)
**Bug.** `label_factory._build_labels_for_ticker` skipped a date unless
`i + max(HORIZONS)` (= 60, for `return_60d`) future bars existed, so a fully
computable 5-day label was withheld for ~60 trading days.

- **Before:** `labels` table maxed at **2026-03-18**; parquet `label_return_5d` /
  `label_positive_5d` columns were **absent from 2026-03-20 onward**;
  `load_date_range` logged `schema_fallback` and dropped those rows.
- **Fix.** Gate now writes a **partial row** as soon as the shortest horizon is
  computable (longer horizons fill NULL, backfilled later). One-time repair:
  `scripts/backfill_recent_labels.py` (scoped + batched) recomputed **359,702**
  label rows (**334,932** with `return_5d`); `scripts/inject_labels_into_parquet.py`
  left-joined them onto the **59** existing parquet files *without* regenerating
  features (the current `feature_snapshots` EAV is sparser than the exported
  parquet, so a re-export would have shrunk every file).
- **After:** labels now present through **2026-06-05**; `load_date_range` over
  2026-03-20→2026-06-05 returned **67,521** labeled rows with **zero**
  `schema_fallback`. Only the natural ≤5-trading-day right edge
  (2026-06-08→06-14) remains unlabeled, as it must.

### 1c — `data_quality_score` is a dead constant; the quality filter is inert
**Bug.** The `>= 0.70` filter and the feature were both no-ops.
- **Before (measured across the corpus):** `data_quality_score` has
  `nunique == 1` (value `1.0`) on every sampled file from 2011→2026;
  `quality_dropped == 0` on every fold.
- **Fix / decision.** Removed `data_quality_score` from the training feature
  sets (**V1 39→38, V3 49→48**) — it carried zero information. The hard filter is
  left in place but **documented as inert**; making the upstream scorer
  discriminate is a separate ingest-pipeline task (would require re-running
  validation and re-exporting all parquet) and was out of scope.

### 1d — Platt calibration leaked the validation fold
**Bug.** `train_classifier` fit Platt on `(X_val, y_val)` and then scored
probabilities on that **same** `X_val`; that scaler is saved in the bundle and
later serves the `predictions` table.
- **Fix.** Refit Platt on the **early-stopping holdout** (`X_es, y_es`, carved
  from training, never scored downstream); skip calibration when raw-score
  `std < 0.01` (`CALIBRATION_MIN_STD`) so degenerate 1–3-tree folds don't collapse
  to a near-zero slope.
- **After:** logs show `calibration='platt(es_holdout)'` on healthy folds and
  `calibration='skipped (degenerate)'` (e.g. `raw_std=0.00216`) on 1-tree folds.
  AUC/rank-IC are unchanged by construction (Platt is monotonic); only Brier and
  absolute probabilities move. No model is calibrated on the fold it scores.

### 1e — No embargoed out-of-sample hold-out
**Bug.** `generate_folds` ran to `data_end` with nothing reserved, contradicting
its own docstring.
- **Fix.** Added `WF_OOS_MONTHS` (default 12). `generate_folds`/`run_walk_forward`
  now reserve the final months; `oos_window()` exposes the embargoed range.
- **After:** folds dropped from 12 → **11**; OOS = **2025-06-15 → 2026-06-14** is
  never touched during fold selection and is scored exactly once (§3).

### 1f — Normalisation ranked binary flags; in-sample train dates mismatched
- **Bug A.** `cross_sectional_normalize` ranked binary flags despite its
  docstring. **Fix:** flags detected by value-set ⊆ {−1,0,1} and excluded
  (covers `above_sma*`, `*_above`, `market_trend`, bounce flags, binary
  interaction products).
- **Bug B.** `run_fold` passed `val_dates.iloc[:n]` as the dates for
  *training*-sample predictions, making in-sample IC meaningless. **Fix:** use
  the sampled rows' own `train_dates`.

`pytest tests/` after all Phase-0/1 changes: **153 passed, 2 failed**. The 2
failures (`TestTrend::test_all_keys`, `test_array_entry_point_matches_df_entry_point`)
are **pre-existing and unrelated** (stale feature-factory key lists: `quality_tier`,
`distance_sma20_momentum`); they fail identically on the untouched baseline and
are out of scope for this task.

---

## 2. The model-quality experiment: V1 vs V3

Both feature sets were trained on **identical** OOS-embargoed folds using the
fixed pipeline (`scripts/run_v1_v3_experiment.py`). Per-day rank IC is pooled
across all 11 validation folds; the t-stat uses every validation day.

| Metric | V1 (38 feat) | V3 (48 feat) | Winner |
|---|---|---|---|
| Pooled per-day mean rank IC | **+0.0131** | +0.0106 | **V1** |
| Per-day IC t-stat | **+4.72** | +3.25 | **V1** |
| Valid IC days (n) | 2958 | 2156 | — |
| Naive 2-sided p | 2.5e-06 | 1.2e-03 | **V1** |
| Bonferroni p (×3 trials) | **7.5e-06** | 3.5e-03 | **V1** |
| Classifier AUC (mean) | **0.5252** | 0.5234 | **V1** |
| Classifier Brier (mean, lower=better) | **0.2507** | 0.2520 | **V1** |
| Decile spread (top−bottom) | **+0.0015** | +0.0009 | **V1** |
| Decile monotonicity (ρ) | +0.56 | **+0.76** | V3 |

**V1 wins 7 of 8 metrics**; V3 wins only decile monotonicity.

**Multiple-comparison discipline (2c).** V3 is the 3rd variant tested (after V1
and V2). The hurdle was per-day IC t-stat **≥ ~3**. V3 clears t≥3 (3.25) in
isolation, but it **loses to V1 on the head-to-head IC** and on AUC/Brier/spread,
and its Bonferroni-adjusted p (3.5e-3) is an order of magnitude weaker than V1's
(7.5e-6). A V3 win that only edges past the bar while losing to the incumbent is
**not proven** — exactly the case the discipline is meant to catch.

**Sign-stability of the V3 interactions vs the V1 base features they target.**
The interactions *did* stabilise signs across folds — usually more stable than
their base feature:

| Interaction | interaction stability | base feature | base stability |
|---|---|---|---|
| return_5d_x_below_200dma | 1.00 | return_5d | 0.55 |
| return_1d_x_below_200dma | 1.00 | return_1d | 1.00 |
| omni_82_distance_x_above_200dma | 0.91 | omni_82_distance | 0.73 |
| omni_82_above_x_above_200dma | 0.91 | omni_82_above | 0.82 |
| return_3d_x_below_200dma | 0.88 | return_3d | 0.73 |
| realized_vol_20_x_below_200dma | 0.75 | realized_vol_20 | 0.64 |
| realized_vol_60_x_below_200dma | 0.75 | realized_vol_60 | 0.55 |
| rs_spy_20_x_bull | 0.64 | rs_spy_20 | 0.64 |
| omni_82_slope_x_above_200dma | 0.55 | omni_82_slope | 0.55 |
| rs_spy_60_x_bull | 0.55 | rs_spy_60 | 0.73 |

**Key result:** stabilising the signs did **not** translate into higher
aggregate IC — V1 (with the raw, sign-unstable features) still wins. The gradient
booster already extracts the regime-conditional value the hand-built interactions
encode, so V3 mostly adds 10 correlated columns (more variance, no net signal).

---

## 3. Out-of-sample result (single shot, winner only)

Per §2, **V1 is the chosen candidate**. It was trained once on all pre-OOS data
(2011-07-01 → 2025-06-14, trading-day purged) and scored **once** on the embargoed
OOS (2025-06-15 → 2026-06-14). No iteration against the OOS.

| OOS metric (V1) | value |
|---|---|
| Per-day mean rank IC | **−0.0052** |
| Per-day IC t-stat | **−2.20** (naive p = 0.029) |
| Valid IC days (n) | 244 |
| Rows scored | 292,801 |
| Decile spread (top−bottom) | +0.0052 (top +0.0038, bottom −0.0014) |
| Decile monotonicity (ρ) | +0.54 |
| Regressor trees trained | **1** (early-stopped) |

**Reading.** The walk-forward signal does **not** persist into the most recent
unseen year. The OOS rank IC is marginally **negative** (t=−2.20, single trial,
p≈0.03 — would not survive any multiple-comparison adjustment), while the decile
spread is weakly **positive** — i.e. the relationship sits essentially at the
noise floor with mixed sign, not a clean edge and not a strong anti-signal. The
OOS regressor early-stopped at a single tree, meaning almost no learnable 5-day
structure remained in the recent training window.

---

## 4. Verdict

> ## KEEP V1 BUT MARK DEGRADED

Tied directly to the numbers:

1. **Not PROMOTE V3** — V3 loses to V1 on 7/8 validation metrics and on the
   head-to-head IC/AUC/Brier; its sign-stability gain did not become predictive
   gain. V3 is not proven (2c).
2. **V1 is the best available model** — it clears the t≥3 hurdle decisively on
   the clean 11-fold walk-forward (t=+4.72, Bonferroni p=7.5e-6), upholding the
   established "not signal-free" finding.
3. **But not production-ready as-is** — on the single embargoed OOS year the rank
   IC is marginally negative (t=−2.20) and the regressor collapses to one tree.
   The edge is period/regime-dependent and **did not generalise** to 2025-06→2026-06.

Therefore: keep V1 as the incumbent, **mark it DEGRADED** — do not promote, do
not treat its ranks/probabilities as production-grade until the OOS rank IC
recovers to positive with a defensible t-stat. This is a recommendation; **no
model was auto-promoted** and the final call is yours.

---

## 5. What I did NOT do, and why

- **Did not tune LightGBM, force more trees, raise learning rate, or change early
  stopping** — forbidden by the brief; the shallow folds are honest.
- **Did not add any indicator, signal, scoring layer, or engine** — forbidden.
- **Did not fix the upstream `data_quality_score` scorer** — it would require
  re-running ingest validation and re-exporting all 3,761 parquet files, and
  verges on adding a scoring layer. Removed the dead feature and flagged the
  inert filter instead (1c).
- **Did not re-export parquet from `feature_snapshots`** for the label backfill —
  that table is now sparser than the exported parquet, so a re-export would have
  *shrunk* the files. Injected labels into the existing rows instead (1b).
- **Did not auto-promote any model or set `MODEL_FEATURE_SET_VERSION`** — the
  verdict is a recommendation; promotion is yours.
- **Did not iterate against the OOS** — it was scored exactly once on the chosen
  candidate.
- **Did not fix the 2 pre-existing feature-factory test failures** — unrelated to
  model validity and out of scope; flagged in §1.
- **Did not compute a full closed-form Deflated Sharpe Ratio** — I used the
  per-day IC t-stat with a Bonferroni (×3-trial) adjustment as the
  multiple-comparison control, which is sufficient to show V3 is not proven; a
  formal DSR would not change the verdict **(conjecture)**.

### Environment note (action needed from you)
An automated `git pull origin main` / `reset to origin/main` loop on this repo
repeatedly reset `fix/model-validity` and wiped my tracked commits mid-session
(my work survived in orphaned commits `ea29bf0` → `58b88fc` and was restored).
Untracked artifacts (this report, `reports/validity/*.json`,
`scripts/run_v1_v3_experiment.py`) survive resets; tracked code does not. To keep
these fixes, the branch needs to be pushed / the auto-sync paused, or my commits
will be clobbered again.
