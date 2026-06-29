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

## To promote into a model
`mr_score` flows into the nightly feature matrix automatically. To let a model
train on it, add it to the next `model_feature_set_version` (V4 candidate) and
walk-forward it through the standard pipeline alongside the V3 set.

## Deferred
- **Options volume/direction**: no options data ingested yet (no DB tables). When
  ingested, add the flow features to `mean_reversion`/a new module and re-test
  whether they sharpen the entries.
