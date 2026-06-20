# CONSENSUS — Key Research Findings

## Jarvis Indicator (UI name for OMNI — Oscar Carboni's proprietary)

**Confirmed formula:** EMA(Low, 82)  
**Backtested on:** SPY daily bars, 2011-2026 (n=3,750 bars)

### Why EMA of Lows?

Oscar describes OMNI as "landing on the bottom of candles." Standard close-based EMA sits *through* the body; EMA of lows sits at the candle *floor*.

Variant comparison results:

| Variant        | Above Lows % | Avg Dist Low % | Cross-Up Hit% (5d) | n signals |
|----------------|-------------|----------------|---------------------|-----------|
| **ema_lows_82**| **99.1%**   | **+0.47%**     | **55.3%**           | 94        |
| ema_lows_87    | 99.0%       | +0.51%         | 54.3%               | 91        |
| ema_lows_89    | 99.1%       | +0.53%         | 54.0%               | 90        |
| hma_82         | 97.2%       | +0.50%         | 56.1%               | 94        |
| ema_lows_55    | 97.4%       | +0.28%         | 52.1%               | 108       |
| ema_close_87   | 90.3%       | +1.44%         | 52.1%               | 88        |

**Why period 82:** Highest `above_lows_pct` combined with a compact average distance (+0.47%) — it sits just above lows without floating too high.

### SPY Cross-Up Hit Rates (SPY-specific, 2011-2026)

| Horizon | Hit Rate | Avg Return | n    |
|---------|---------|------------|------|
| 1d      | 51.1%   | +0.16%     | 94   |
| 5d      | 55.3%   | +0.44%     | 94   |
| 10d     | 60.6%   | +0.88%     | 94   |
| **20d** | **81.9%**| **+1.74%** | **94** |

The 20-day result is exceptional. When SPY's close crosses above OMNI(82), 82% of the time SPY is higher 20 trading days later.

### ML Features (added to ALL_FEATURES, v1.5)

| Feature          | Description                                           |
|------------------|-------------------------------------------------------|
| `omni_82_value`  | Raw EMA(Low, 82) indicator value                      |
| `omni_82_above`  | 1.0 if Close > OMNI, else 0.0                         |
| `omni_82_distance` | (Close − OMNI) / OMNI — % above or below            |
| `omni_82_slope`  | (OMNI − OMNI[−5]) / OMNI[−5] — fractional trend     |
| `omni_82_bounce` | 1.0 if Low within 0.5% of OMNI and Close > Open      |

### Conditional Patterns (migration 0015)

- `omni_82_cross_up` / `omni_82_cross_down` — trend change signals
- `omni_82_above_3d` / `omni_82_above_5d` — sustained above OMNI
- `omni_82_bounce` / `omni_82_bounce_1pct` — support hold entry
- `omni_82_green_slope` — above OMNI with rising OMNI (strongest)

---

## OSCAR Oscillator

**Formula:** `A = max(High, N); B = min(Low, N); rough = (Close - B)/(A - B)*100; oscar[i] = oscar[i-1]*2/3 + rough*1/3`

A smoothed stochastic oscillator (0–100 range). Cross above 50 = bullish signal.

### SPY Cross-Up Hit Rates by Period

| Period | n signals | Hit% 5d | Avg Ret% |
|--------|-----------|---------|---------|
| 8      | 188       | 61.2%   | 0.195%  |
| 21     | 92        | 62.0%   | 0.088%  |
| 34     | 64        | 64.1%   | 0.054%  |
| 55     | 51        | **76.5%** | **0.540%** |
| 87     | 33        | 69.7%   | 0.858%  |
| 89     | 33        | 72.7%   | 0.790%  |

Period 55 has best hit rate; period 87 has best return-per-signal.

---

## Calendar Conditional Patterns (migration 0018)

Backtested on SP500 aggregate (2019-2026).

| Pattern           | Horizon | N      | Hit%  | Avg Ret | p-value | Notes                              |
|-------------------|---------|--------|-------|---------|---------|-------------------------------------|
| `fomc_day`        | 5d      | 10,742 | 50.9% | −0.23%  | <0.001  | Flat 5d; mean-reversion risk        |
| `fomc_day`        | 20d     | 10,742 | 58.2% | +0.89%  | <0.001  | Bullish 20d after FOMC              |
| `opex_week`       | 5d      | 78,474 | 53.8% | +0.22%  | <0.001  | Mild bullish bias in OPEX week      |
| `opex_week`       | 20d     | 78,474 | 58.8% | +1.13%  | <0.001  | Strong 20d bullish drift            |
| `month_end_3d`    | 5d      | 95,271 | 55.2% | +0.32%  | <0.001  | Month-end effect confirmed          |
| `month_end_3d`    | 20d     | 95,271 | 57.1% | +0.89%  | <0.001  | Consistent 20d positive drift       |

**Key insight:** FOMC day is weak/negative at 1-5d horizon but consistently bullish at 20d. Month-end and OPEX week show reliable bullish drift across horizons.

---

## Sector Rotation Patterns (migration 0019)

Using `sector_relative_strength` table (38,638 rows, 11 SPDR ETFs, 2011-2026).

| Pattern            | Horizon | N     | Hit%      | Avg Ret   | p-value | Interpretation                    |
|--------------------|---------|-------|-----------|-----------|---------|-----------------------------------|
| `xlv_leading_20d`  | 5d      | 30    | **86.7%** | +0.91%    | 0.004   | XLV top-2 for 20d → very bullish  |
| `xlv_leading_20d`  | 10d     | 30    | **83.3%** | +1.16%    | 0.002   |                                   |
| `xlv_leading_20d`  | 20d     | 30    | **93.3%** | +2.63%    | <0.001  | Best single pattern found         |
| `xle_leading_20d`  | 5d      | 199   | 53.3%     | −0.08%    | 0.660   | Not significant short-term        |
| `xle_leading_20d`  | 20d     | 199   | 65.8%     | +1.06%    | 0.002   | Inflation regime = bullish 20d    |
| `xly_vs_xlp`       | 5d      | 2,139 | 60.7%     | +0.20%    | <0.001  | Risk-on rotation confirmed        |
| `xly_vs_xlp`       | 20d     | 2,139 | 67.7%     | +0.85%    | <0.001  | Discretionary > Staples = bullish |

**Key insight:** `xlv_leading_20d` is the strongest SPY pattern found — **93.3% 20d hit rate** (n=30, p<0.001). When Health Care has led for 20 consecutive days, SPY continues higher. The XLY > XLP risk-on signal (n=2,139) is the most statistically robust.

---

## ML Model Quality (v1.5 — retrained 2026-06-11)

**Walk-forward results after Jarvis (OMNI) backfill (192/192 tickers):**

| Metric | v1.4 (pre-Jarvis) | v1.5 (post-Jarvis) | Change |
|--------|----------------|-----------------|--------|
| WF Mean IC | 0.0269 | **0.0546** | +103% (doubled) |
| WF Folds | 5 | **12** | +7 folds |
| Mean AUC | ~0.51 | **0.5239** | +0.014 |
| Features | 27 | **33** | +6 OMNI features |

**Top features by regressor gain (model `2025-07-01`):**

| Rank | Feature | Gain | Note |
|------|---------|------|------|
| 1 | above_sma20 | 119 | |
| **2** | **omni_82_above** | **96** | OMNI confirmed top-2 |
| **3** | **omni_82_bounce** | **58** | Support bounce signal |
| 4 | above_sma200 | 54 | |
| 5 | spy_above_sma50 | 52 | |

**Classifier top-5:** above_sma20 (56,722) → above_sma200 (54,166) → omni_82_above (50,666) → spy_above_sma50 (48,476) → omni_82_bounce (40,164)

**Edge tier:** IC 0.0546 = "Moderate edge" (threshold: <0.02 Early stage, <0.04 Developing, <0.06 Moderate edge, ≥0.06 Strong edge)

---

## Feature Set Experiment (2026-06-14)

### Feature Health Classification (28 features, model v1, target label_return_5d)

| Category | Count | Key Features |
|---|---|---|
| STRONG | 0 | — |
| USEFUL | 4 | omni_82_distance (IC=+0.0242), omni_82_above (IC=+0.0149), realized_vol_20, volume_ratio_20 |
| WEAK | 12 | atr_14 (sign_stab=0.00), dollar_volume_20, omni_82_bounce, omni_82_slope, realized_vol_60, distance_sma200, rs_spy_120, above_sma200, above_sma50, return_60d, rs_spy_60, distance_sma50 |
| DEGRADING | 12 | return_1d/3d/5d/10d/20d, rsi_14, macd_histogram, above_sma20, distance_sma20, rs_spy_20, roc_20, omni_82_value |

### Pruning Experiment (parquet 2011-2026, 80/20 time split)

| Feature Set | n_feat | IC | Verdict |
|---|---|---|---|
| features_current (V1 baseline) | 39 | +0.0172 | — |
| **features_remove_degrading (V2)** | **27** | **+0.0397** | **+131%** |
| features_mean_reversion_plus_omni | 14 | +0.0155 | — |

### Holdout Validation (trained 2011-2025, evaluated 2025-07-01 to 2026-03-17)

| Metric | V1 (39 feat) | V2 (27 feat) | Winner |
|---|---|---|---|
| Mean Rank IC | +0.0196 | +0.0152 | **V1** |
| IC Std (lower) | +0.1065 | +0.1030 | V2 |
| Decile Spread | +0.0020 | +0.0014 | **V1** |
| AUC | +0.5000 | +0.4943 | **V1** |
| Brier (lower) | +0.3333 | +0.3362 | **V1** |
| Top Decile Return | +0.0040 | +0.0045 | V2 |
| Bot Decile Return | +0.0020 | +0.0031 | V2 |

**Verdict: KEEP V1.** V1 wins 4/7 metrics on the untouched holdout (2025-07-01 to 2026-03-17).
The pruning experiment's V2 advantage (historical 80/20 split) does not replicate in the live holdout
period. The 2025-2026 bull market may favour the trend/momentum features that V2 removes.

**V2 is ready as a rollback option.** `MODEL_FEATURE_SET_VERSION=v2` in `.env` activates V2 training.
Reassess after 6 months of new parquet data or a change in market regime.

**Prediction overlap:** 39.5% Jaccard on top-decile tickers per day — V2 is selecting materially
different stocks from V1, confirming they are not equivalent models.

---

## Regime Sensitivity Study (2026-06-15)

Full study results in `reports/REGIME_SENSITIVITY_REPORT.md` and `feature_regime_performance` table.

### Classification (39 features, 6 regimes, 3,697 dates)

| Class | Count | Features |
|---|---|---|
| Always Useful | 0 | — (no feature passes all 6 regimes at IC>0.01 + sign_stab>0.55) |
| Regime Sensitive | 20 | omni_82_distance/above/slope, realized_vol_20/60, rs_spy_120, return_10/20/60d, distance_sma20/50/200, above_sma20/50/200, rsi_14, roc_20, rs_spy_20/60, volume_ratio_20, omni_82_slope |
| Mostly Noise | 12 | regime-defining cols (constant within subset) + Momentum V2 features (insufficient history) |
| Potentially Harmful | 7 | return_1d/3d/5d, macd_histogram, atr_14, dollar_volume_20, omni_82_value |

### Key Findings

1. **OMNI is bull/low-vol/above-200DMA specific:** `omni_82_distance` IC = +0.026 (bull), +0.038 (low_vol), +0.031 (above_200dma) vs. -0.011 (bear), -0.020 (below_200dma). Signal reverses in downtrends.
2. **Realized vol is a bear-market / crisis signal:** `realized_vol_20` IC = +0.053 in bear, +0.046 below_200dma. Best bear-regime features in the set.
3. **Momentum features are mean-reverting:** return_1d/3d/5d have negative IC in ALL regimes. Not "harmful" in LightGBM (model uses them with implicit negative weights) but classified as harmful by raw IC sign.
4. **No feature is universally useful** — every feature's contribution changes by market regime. This motivates V3 regime-aware design.

### V3 Feature Set Direction

V3 = TRAIN_FEATURES_V1 base + regime interaction features. Do NOT prune further.

Recommended interaction features to add:
- `omni_82_distance * spy_above_sma200` — OMNI signal only when above 200DMA
- `realized_vol_20 * (1 - spy_above_sma200)` — vol signal only when below 200DMA
- `omni_82_slope * market_trend` — OMNI slope aligned with market direction

Exclusion candidates (no regime where IC > 0): `atr_14`, `dollar_volume_20`.

---

## Feature Set V3 Experiment (2026-06-15)

Full results in `reports/FEATURE_SET_V3_REPORT.md`.

**V3 = V1 (39 features) + 10 regime-interaction features (49 total)**

Interaction features computed on-the-fly from existing parquet columns; no backfill needed.
Injected at load time in `dataset.py` and `predict.py` via `regime_interactions.add_interactions()`.

### Holdout Comparison (2025-07-01 to 2026-03-17, 32,757 rows, 179 dates)

| Metric | V1 | V3 | Winner |
|---|---|---|---|
| Mean Rank IC | +0.0196 | +0.0154 | **V1** |
| IC Std | +0.1065 | +0.1096 | **V1** |
| Sharpe | +2.93 | +2.23 | **V1** |
| Decile Spread | +0.0020 | +0.0014 | **V1** |
| AUC | +0.5000 | +0.5014 | V3 |
| Brier | +0.3333 | +0.3326 | V3 |
| Top Decile Return | +0.0040 | +0.0044 | V3 |
| Bot Decile Return | +0.0020 | +0.0031 | V3 |

**Result: TIE (4/8 each). V3 does NOT meet the >= 5 of 8 promotion threshold.**

### Walk-Forward Comparison (12 folds)

| | V1 (clean 2026-06-15 run) | V3 (this run) |
|---|---|---|
| Mean Rank IC | **+0.0599** | +0.0467 |
| Prediction overlap | — | 48.4% Jaccard (top-decile) |

**Verdict: KEEP V1.** V3 loses on both holdout and walk-forward rank IC.
Root cause: 2025-2026 holdout is a bull market; OMNI features already work well above 200DMA
without needing the interaction. V3 may show advantage in a bear/high-vol regime.

V3 is preserved as `MODEL_FEATURE_SET_VERSION=v3`. Reassess after first bear regime.

---

## Caveat — 2026-06-19 model-validity session

The "Current System State" section immediately below is **stale** as of
this date. Verified facts that supersede it (full detail:
`reports/validity/MODEL_VALIDITY_FIXES_REPORT.md`):

- **Active feature count is 38, not 39.** `data_quality_score` was dropped
  from `TRAIN_FEATURES_V1` (dead constant, `nunique==1` across the whole
  corpus) in a prior session, before this one.
- **Walk-forward is 11 folds, not 12.** `WF_OOS_MONTHS` (default 12) now
  embargoes the final year from fold selection; the old 12th fold's
  validation window (2025-07→2026-06) is exactly the now-reserved range, not
  an independent extra fold.
- **This session's clean 11-fold re-run: mean rank IC = 0.0712, mean AUC =
  0.5248** (vs. the 0.0599 below, which was the pre-embargo, 12-fold,
  39-feature number — a different fold sample, not a regression).
- **OOS reconfirmed degraded:** single-shot OOS score (2025-06-15→2026-06-14)
  gives rank IC -0.0061 / mean IC -0.0052 — matches the prior session's
  independent -0.0052 finding. "KEEP V1 BUT MARK DEGRADED" still stands.
- **Production model artifact pointer below (`return_regressor_v1_2025-07-01`)
  predates the OOS embargo** — it was trained on the now-reserved window.
  The current walk-forward's last fold artifact is
  `return_regressor_v1_2024-07-01`; the current OOS-scored artifact is
  `return_regressor_v1_2025-06-14`.
- **Conviction/confluence backtest numbers moved** (VERY_HIGH 5d HR 55.6%→
  54.2%, 5+ aligned 58.1%→54.4%, both permutation tests losing significance)
  between the committed reports and this session's re-run — confirmed
  **not attributable to the model fixes**; dominated by a +67% change in
  scored population and a probability-tier activation from concurrent,
  unrelated work. See the linked report §4 before citing either report's
  numbers as a clean comparison.

---

## Current System State (as of 2026-06-15)

### Infrastructure
- **Migrations applied:** 0001 through 0029
- **Tables:** raw_bars, feature_snapshots, feature_snapshots_wide, model_registry, feature_regime_performance, feature_review_flags, experimental_score_snapshots, score_backtest_results, feature_pruning_results, conditional_patterns, conditional_pattern_results, sector_relative_strength, market_calendar, transcript_sessions, transcript_chunks

### ML Pipeline
- **Features:** 39 (PHASE1 + REGIME + OMNI_82 + MOMENTUM_V2 + data_quality_score) — active set V1
- **Defined feature sets:**
  - `TRAIN_FEATURES_V1` (39) — **PRODUCTION**
  - `TRAIN_FEATURES_V2` (27) — static pruning, failed holdout, rollback only
  - `TRAIN_FEATURES_V3` (49) — V1 + 10 regime interactions, experimental, failed holdout vs V1
- **Active set:** V1 (default). Override via `MODEL_FEATURE_SET_VERSION` in `.env`
- **Current model:** `return_regressor_v1_2025-07-01`, walk-forward 12 folds, **mean rank IC = 0.0599**
- **Training complete:** 2026-06-15. All 12 folds written with `feature_set_version='v1'` in model_registry.
- **Predictions written:** 6,079 tickers scored for 2026-06-14 (mean prob=0.5248, mean rank IC=0.592)
- **Model artifact:** `models/return_regressor_v1_2025-07-01/model.joblib`
- **V3 model artifact:** `models/return_regressor_v3_2025-07-01/model.joblib` (experimental, not in production)

### Conditional Probability Engine
- **Patterns:** 95+ (migrations 0010-0019)
- **Evaluators:** 39 (includes calendar + sector rotation types)
- **Latest results:** xlv_leading_20d 93.3% 20d, xly_vs_xlp 60.7% 5d

### Data
- **Universe:** 194 tickers (universe.csv)
- **Sector ETFs:** 11 SPDR ETFs + SPY tracked in sector_relative_strength
- **Market calendar:** 271 events (73 FOMC, 108 OPEX, 36 quarter-end, 36 triple witching, 18 half-year)
- **Transcripts:** 829 sessions found, 150 chunks stored (extraction pending API key)

### API Endpoints
- `GET /api/research/conditional/spy` — SPY streak + calendar_context
- `GET /api/research/conditional/context/:ticker` — active patterns
- `GET /api/research/conditional/pattern/:name` — full pattern stats
- `GET /api/research/sectors/snapshot` — today's sector RS rankings + regime
- `GET /api/research/sectors/history/:ticker` — sector RS history (60d)
- `GET /api/research/signal/:ticker` — ML signal (includes OMNI features)

### UI Components (Dashboard.tsx)
- `MLSignalBadge` — ML prediction + OMNI indicator
- `ConditionalNarrative` — active conditional patterns
- `SectorRotationBadge` — today's sector rotation + regime label

---

## Implementation Files

- `src/atlas_research/features/omni_proxy.py` — all indicator functions
- `src/atlas_research/conditional/engine.py` — 39 condition evaluators (incl. calendar + sector)
- `scripts/compute_sector_rs.py` — computes sector_relative_strength table
- `scripts/seed_market_calendar.py` — seeds market_calendar table
- `scripts/run_conditional_calendar.py` — calendar context detector + backtests
- `db/migrations/0013_omni_oscar_patterns.sql` — OSCAR/OMNI-87 patterns
- `db/migrations/0014_omni_lows_patterns.sql` — EMA-of-lows variants
- `db/migrations/0015_omni_82_patterns.sql` — OMNI-82 confirmed patterns
- `db/migrations/0016_sector_relative_strength.sql` — sector RS table
- `db/migrations/0017_market_calendar.sql` — market calendar table
- `db/migrations/0018_calendar_patterns.sql` — calendar conditional patterns
- `db/migrations/0019_sector_rotation_patterns.sql` — sector rotation patterns
- `config/settings.py` — OMNI_FEATURES added to ALL_FEATURES
