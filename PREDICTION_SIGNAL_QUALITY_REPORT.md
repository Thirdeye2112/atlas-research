# Prediction Signal Quality Report

**Date:** 2026-06-16
**Scope:** Make the `predictions` table contain usable, differentiated signal fields for atlas-alpha. Pipeline-output fixes only — no new models, no formula changes, no new indicators.
**Demonstration date:** 2026-06-14 (latest available feature parquet); 6,079 `return_regressor` rows re-scored with the fixed pipeline.

---

## Root cause

All three degenerate fields (`rank_percentile`, `confidence`, `probability_positive`) traced to **one** cause plus a selection issue:

1. **Platt calibrator collapse.** The newest-by-mtime artifact (`return_regressor_v3_2025-07-01`) has a Platt scaler with slope ≈ **0.042**. `prob = sigmoid(0.042·raw + 0.075)` maps the whole universe to ~0.525 regardless of input. Since `confidence = |prob−0.5|·2` and `rank_percentile = rank(prob)`, the collapse propagated to all three fields. The **raw** classifier output was fine (45 distinct, range 0.484–0.579) — only the calibration layer was broken.
2. **Coarse model resolution.** The same fold's regressor has **1 tree** (7 distinct `expected_return` values) and the classifier has 7 trees (45 distinct). Many folds early-stop at 1–3 trees. This is why even after the fix a residual rank plateau remains.
3. **Combo metadata never attached.** `attach_meta_scores.py` (the Meta-Signal Engine tagger) was not run in the nightly, leaving `combo_*` columns 100% NULL. It also had two NaN-handling bugs that crashed it / wrote the literal string `'NaN'`.

The rank tie (53% at exactly 0.7313) was **not** caused by missing features, default fills, or identical feature vectors — verified **0%** of the 6,079 rows share an identical feature vector. It was the degenerate model output being ranked.

---

## Fixes applied (pipeline only)

| # | File | Fix |
|---|---|---|
| 1 | `src/atlas_research/models/predict.py` | Platt-degeneracy guard: if calibrated prob std < 0.01 and the raw classifier std is larger, fall back to the raw classifier probabilities (same trained model, no new weights). |
| 2 | `src/atlas_research/models/predict.py` | `rank_percentile` now ranks `probability_positive` with an `expected_return` tie-break so it is smoothly distributed instead of plateaued. |
| 3 | `src/atlas_research/models/predict.py` | `raw_confidence` and `calibrated_confidence` always populated (default to `confidence`, overwritten by the adaptive `ConfidenceCalibrator` when history exists). |
| 4 | `scripts/attach_meta_scores.py` | Fixed `combo_sample_size` NaN→int crash and the `combo_status`/`combo_key` `'NaN'`-string bug (float NaN is truthy, so `x or None` failed). |
| 5 | `src/atlas_research/ingest/yahoo_ingest.py` | Normalize tickers to Yahoo symbols (`BRK.B → BRK-B`) for download; store rows under the canonical ticker. |
| 6 | `src/atlas_research/pipelines/nightly_pipeline.py` + `db/repository.py` | Ingest failures are now **non-fatal warnings**: the run stays `complete` (not `failed`) but the failed tickers stay visible in `error_message`. `complete_research_run` gained an explicit `status` param. |
| 7 | `scripts/run_training.py` | Added `--date` to `--predict-only` so a specific parquet date can be re-scored. |
| 8 | `atlas-alpha/.../routes/research-ml.ts` | `/intraday/similarity/:ticker` returns `{available:false, reason:"no_similarity_data"}` (HTTP 200) instead of 404. |

---

## Before / After (2026-06-14, 6,079 rows)

### rank_percentile distribution
| metric | before | after |
|---|---|---|
| distinct values | **7** | **45** |
| largest single-value share | **52.7%** (at 0.7313) | **30.2%** (at 0.7752) |
| range | 0.0032 – 0.9975 | 0.0010 – 0.9632 |

### confidence distribution
| metric | before | after |
|---|---|---|
| distinct values | 7 | 45 |
| mean | 0.0496 | **0.1261** |
| range | 0.0493 – 0.0497 | 0.0016 – 0.1579 |

### probability_positive distribution
| metric | before | after |
|---|---|---|
| distinct values | 7 | 45 |
| mean | 0.5248 | 0.5630 |
| range | 0.5247 – 0.5249 | 0.4843 – 0.5790 |

### combo_key / combo_status null rate
| field | before | after |
|---|---|---|
| `combo_key` non-null | 0 / 6079 (**100% NULL**) | 6079 / 6079 (**0% NULL**) |
| `combo_status` non-null | 0 / 6079 (100% NULL) | 1280 / 6079 |
| `raw_confidence` non-null | 0 / 6079 | 6079 / 6079 |
| `calibrated_confidence` non-null | 0 / 6079 | 6079 / 6079 |
| distinct combo_keys | 0 | 133 |

### combo_status distribution (after)
| status | rows |
|---|---|
| PROMOTED | 620 |
| REJECTED | 353 |
| CANDIDATE | 255 |
| INSUFFICIENT | 52 |
| (null — combo_key has no scored combination yet) | 4,799 |

---

## Nightly health status

- **BRK.B**: now normalized to `BRK-B` and ingests successfully (verified: 6 bars fetched, stored under canonical `BRK.B`, last close 495.52).
- **DAWN, GSX, IAS, MGRM**: genuinely delisted / no Yahoo data — they remain non-fatal warnings (cannot be recovered without a different data source).
- **Run status**: verified end-to-end that a run with ingest failures now records `status='complete'` with `error_message="ingest_failures(5): ['BRK.B','DAWN','GSX','IAS','MGRM']"` — non-fatal and visible.
- The existing `2026-06-14` nightly record still shows `failed` (historical); it will be superseded by the next nightly run using the fixed code. `/api/research/pipeline/health` reports overall `status: healthy` (all critical tables present).

---

## Remaining limitations

1. **The underlying model has almost no edge.** Walk-forward metrics: classifier AUC ≈ 0.495–0.507 (≈ random), rank_ic ≈ 0.01. The fields are now structurally differentiated and usable, but their *predictive* power is limited. The real remedy is retraining — explicitly out of scope here ("no new models").
2. **Coarse model resolution drives the residual 30% rank plateau.** Many walk-forward folds early-stop at 1–3 trees (the selected fold's regressor has 1 tree). With so few leaf values the model genuinely cannot distinguish large groups of tickers. Fixing this requires retraining with corrected early-stopping, not a pipeline change.
3. **Artifact selection is still newest-by-mtime**, which happened to pick the weakest fold. Recommend selecting the `model_registry` champion by `rank_ic`. Left unchanged to avoid destabilizing the live pipeline in this pass.
4. **`probability_positive` remains centred ~0.56** — differentiated but weak, reflecting the model's limited signal. Treat as a soft input, not a calibrated probability.
5. **`combo_status` is populated for 1,280 / 6,079 (21%)**; the remainder receive a `combo_key` but no scored combination exists for their bucket yet (only 133 distinct combos are scored in `signal_combination_scores`). This grows as more combinations accumulate sample size.
