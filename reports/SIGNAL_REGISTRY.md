# Signal Registry — `mr_score` (mean-reversion)

**Status:** registered as a pipeline feature (2026-06-28). Computed nightly by
`atlas_research.features.mean_reversion.compute` via `feature_factory.build_features`
→ columns `mr_score`, `mr_oversold` in the feature matrix.

## Definition
Per bar, standardize (trailing 252d) and combine the consensus mean-reversion
components, higher = more oversold / extended-down / high-vol:

```
mr_score = mean( -z(rsi) -z(bb_pct) -z(dist_ema20) -z(dist_ema200) -z(stoch_k) +z(atr_pct) )
mr_oversold = 1 if mr_score >= 1.0
```

## Validation (how it was earned)
- **Cross-stock consensus (10 names):** rsi_oversold +IC in 10/10 stocks, bb_break_dn
  10/10, dist_ema200 −IC 9/10, overbought oscillators −IC 8/10. Mean reversion is
  the universal sign, not momentum. (`reports/stocks/CROSS_STOCK_SUMMARY.md`)
- **Embargoed walk-forward, net of 5bps:** 1,492 OOS trades, +0.70%/5d vs +0.48%
  baseline → **+0.22% excess, t=4.49**, positive in 8/10 names and every test
  window 2014–2026; robust to 20bps. (`reports/stocks/WALKFORWARD_VALIDATION.md`)
- **5m corroboration (2023+):** daily signals whose next session **closed above
  VWAP** returned **+2.29%/5d, 65% win** vs +0.57%/53% when the bounce failed —
  the intraday layer roughly doubles the edge. (`reports/stocks/DAILY_5M_CORROBORATION.md`)

## Known limits (use it right)
- **Not a standalone buy&hold-beater.** As an in/out long-only timing system it
  underperforms basket buy&hold (CAGR ~7% vs ~27%) due to cash drag in a bull
  market; **tight stops make it worse.** (`reports/stocks/STRATEGY_EQUITY.md`)
- Best used as: an **entry-timing / ranking feature** in combination (e.g. inside
  the model feature set), confirmed intraday by next-day close > VWAP — not as a
  market-timing on/off switch.

## V4 = V3 + mr_score — VALIDATED (promote candidate)
Embargoed walk-forward, identical folds/purge/normalisation to the V1/V3 harness
(`scripts/run_v3_v4_experiment.py`, `reports/validity/v3_v4_experiment.json`):

| set | WF mean_ic | WF t | OOS mean_ic | OOS t |
|-----|-----------:|-----:|------------:|------:|
| V3            | +0.0053 | 1.70 | +0.0105* | 3.23* |
| **V4 (+mr_score)** | **+0.0073** | **2.44** | **+0.0209** | **3.73** |

\*V3 OOS from the identical prior pipeline (run_v1_v3_experiment). Adding mr_score
lifts WF IC ~+38% (t 1.70→2.44) and roughly **doubles the held-out OOS year**
(+0.0105 → +0.0209). Recommend promoting V4.

## Promoted to production (2026-06-28)
V4 is now the active feature set. `MODEL_FEATURE_SET_VERSION` defaults to `v4`
(`config/settings.py`: `TRAIN_FEATURES_V4 = V3 + mr_score`). Because the existing
parquet matrices do **not** carry `mr_score` (the nightly export predates the
`feature_factory` wiring), it is merged on-the-fly in `dataset.load_date_range`
from `exports/parquet/mr_score_lookup.parquet` on `(ticker, date)` — the same path
the experiment validated — exactly mirroring how the V3 interaction features are
added in-loader (not stored in parquet).

`score_oos.py` with `v4` reproduced the validated edge on the embargoed
2025-06→2026-06 block: **OOS mean_ic = 0.0209** (vs V3 0.0105), rank_ic 0.0335,
and wrote a `model_registry` row with `feature_set_version='v4'` + `model.joblib`.

The full nightly walk-forward retrain was then run via `run_training.py`
(env `MODEL_FEATURE_SET_VERSION=v4`): **11 folds OK, 0 errors, mean rank_ic 0.0426,
mean clf_auc 0.5224**, writing a `feature_set_version='v4'` `model_registry` row +
`model.joblib` per fold (12 `v4` rows total incl. the OOS). Memory stayed well
within budget (per-fold loads are small). V4 is fully live end-to-end.

## Deferred
- **Options volume/direction**: no options data ingested yet (no DB tables). When
  ingested, add the flow features to `mean_reversion`/a new module and re-test
  whether they sharpen the entries.
